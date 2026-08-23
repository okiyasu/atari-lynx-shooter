#!/usr/bin/env python3
"""APS-057 direct Gearlynx readback for the movable-chain Suzy scale.

Injects Stage 1, active Stage 2 WIND, and Stage 3 ROCKFALL warning/impact
fixtures immediately before draw, then reads SPRHSIZ/SPRVSIZ at the real
movable ``tgi_sprite`` submission.  The TGI primitive runs before this
submission, so this observes the exact handoff that previously inherited a
variable VSIZE.
"""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VISUAL_PATH = ROOT / "scripts" / "verify-stage-visuals-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17786

GAME_OFFSET_PLAYER = 2
# APS056_DIAGNOSTIC's GameState layout includes the cc65 enemy pointer,
# player credits, and enemy-bullet move phase before the bullet array.
GAME_OFFSET_BULLETS = 9
GAME_OFFSET_ENVIRONMENT = 167
GAME_ENVIRONMENT_SIZE = 19
GAME_OFFSET_GAME_OVER = 194
GAME_OFFSET_STAGE = 212
GAME_OFFSET_PHASE = 213
GAME_OFFSET_ANIMATION_FRAME = 210
GAME_STATE_TAIL_SIZE = 23
GAME_ENEMY_SIZE = 12
GAME_MAX_ENEMIES = 8
GAME_PHASE_NORMAL = 1

SUZY_SPRHSIZ = 0xFC18
SUZY_SPRVSIZ = 0xFC1A

CASES = (
    ("stage1-baseline", 1, "none"),
    ("stage2-wind-active", 2, "wind-active"),
    ("stage3-rock-warning", 3, "rock-warning"),
    ("stage3-rock-impact", 3, "rock-impact"),
)


def load_visual():
    spec = importlib.util.spec_from_file_location("visual", VISUAL_PATH)
    visual = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(visual)
    visual.MCP_PORT = MCP_PORT
    return visual


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], "little")


def wait_breakpoint(visual, request_id, description):
    return visual.wait_for_breakpoint(request_id, description)


def continue_to_breakpoint(visual, request_id, description):
    visual.tool("debug_continue", request_id=request_id)
    return wait_breakpoint(visual, request_id + 1, description)


def wait_stable_title(visual, game_address, request_id):
    visual.tool("debug_continue", request_id=request_id)
    request_id += 1
    deadline = time.monotonic() + 10.0
    stable = 0
    while time.monotonic() < deadline:
        state = visual.read_bytes(game_address + GAME_OFFSET_STAGE, 2,
                                  request_id)
        request_id += 1
        if state == bytes([1, 6]):
            stable += 1
            if stable == 2:
                visual.tool("debug_pause", request_id=request_id)
                return request_id + 1
        else:
            stable = 0
        time.sleep(0.005)
    raise RuntimeError("ROM did not reach stable title state")


def inject_fixture(visual, game_address, enemy_address, stage, environment,
                   request_id):
    visual.write_bytes(game_address + GAME_OFFSET_PLAYER,
                       [60, 70, 8, 6], request_id)
    request_id += 1
    visual.write_bytes(game_address + GAME_OFFSET_BULLETS,
                       [0] * (GAME_OFFSET_GAME_OVER - GAME_OFFSET_BULLETS),
                       request_id)
    request_id += 1
    visual.write_bytes(enemy_address, [0] * (GAME_MAX_ENEMIES * GAME_ENEMY_SIZE),
                       request_id)
    request_id += 1
    visual.write_bytes(game_address + GAME_OFFSET_ENVIRONMENT,
                       [0] * GAME_ENVIRONMENT_SIZE, request_id)
    request_id += 1

    tail = [0] * GAME_STATE_TAIL_SIZE
    tail[GAME_OFFSET_ANIMATION_FRAME - GAME_OFFSET_GAME_OVER] = 0
    tail[GAME_OFFSET_STAGE - GAME_OFFSET_GAME_OVER] = stage
    tail[GAME_OFFSET_PHASE - GAME_OFFSET_GAME_OVER] = GAME_PHASE_NORMAL
    visual.write_bytes(game_address + GAME_OFFSET_GAME_OVER, tail, request_id)
    request_id += 1

    environment_bytes = [0] * GAME_ENVIRONMENT_SIZE
    if environment == "wind-active":
        # asteroids[2] (6B), falling_rocks[2] (8B), GameWindBand (5B)
        environment_bytes[14:19] = [2, 30, 0, 150, 0]
    elif environment in ("rock-warning", "rock-impact"):
        state = 1 if environment == "rock-warning" else 3
        environment_bytes[6:12] = [80, 94, state, 10, 0, 0]
    visual.write_bytes(game_address + GAME_OFFSET_ENVIRONMENT,
                       environment_bytes, request_id)
    return request_id + 1


def read_scale(visual, request_id):
    payload = visual.tool("get_suzy_registers", request_id=request_id)
    request_id += 1
    registers = {row[0]: row[2] for row in payload["registers"]}
    return request_id, {
        "sprhsiz": int(str(registers["SPRHSIZ"]), 16),
        "sprvsiz": int(str(registers["SPRVSIZ"]), 16),
        "registers": {"SPRHSIZ": registers["SPRHSIZ"],
                       "SPRVSIZ": registers["SPRVSIZ"]},
    }


def run_case(visual, symbols, game_address, enemy_address, ioctl_address,
             stage, environment, label, request_id):
    request_id = inject_fixture(
        visual, game_address, enemy_address, stage, environment, request_id)
    visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address},
                request_id)
    request_id += 1
    real_hits = []
    movable_scale = None
    for _ in range(96):
        request_id = continue_to_breakpoint(
            visual, request_id, "%s tgi_ioctl" % label)
        cpu = visual.tool("get_6502_status", request_id=request_id)
        request_id += 1
        pointer = int(cpu["A"], 16) | (int(cpu["X"], 16) << 8)
        if pointer < 0x1000:
            continue
        real_hits.append(pointer)
        if len(real_hits) == 2:
            request_id, movable_scale = read_scale(visual, request_id)
            break
    if movable_scale is None:
        raise RuntimeError("%s: movable tgi_sprite submission not found" % label)
    visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address},
                request_id)
    request_id += 1
    visual.tool("debug_step_out", request_id=request_id)
    request_id += 1
    visual.tool("debug_pause", request_id=request_id)
    request_id += 1
    passed = (movable_scale["sprhsiz"] == 0x0100 and
              movable_scale["sprvsiz"] == 0x0100 and len(real_hits) == 2)
    return request_id, {
        "label": label,
        "stage": stage,
        "environment": environment,
        "real_tgi_ioctl_hits": ["0x%04X" % value for value in real_hits],
        "movable_scale": movable_scale,
        "passed": passed,
    }


def run_mode(args, gui):
    visual = load_visual()
    game_address = visual.symbol_address(args.symbols, "_game")
    enemy_address = visual.symbol_address(args.symbols, "_game_enemies")
    ioctl_address = visual.symbol_address(args.symbols, "_tgi_ioctl")
    command = [GEARLYNX]
    if not gui:
        command.append("--headless")
    command.extend(["--mcp-http", "--mcp-http-port", str(MCP_PORT),
                    str(args.rom), str(args.symbols)])
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                visual.call("initialize", {
                    "protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "aps057-scale", "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")
        request_id = wait_stable_title(visual, game_address, 2)
        cases = []
        for label, stage, environment in CASES:
            request_id, result = run_case(
                visual, args.symbols, game_address, enemy_address,
                ioctl_address, stage, environment, label, request_id)
            cases.append(result)
            print("%s %s" % (label, "PASS" if result["passed"] else "FAIL"))
        return {"mode": "gui" if gui else "headless", "cases": cases,
                "passed": all(case["passed"] for case in cases)}
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path,
                        default=Path("dist/asteroid-patrol-aps056-diagnostic.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol-aps056-diagnostic.lbl"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-057/sprite-scale-v001.json"))
    parser.add_argument("--mode", choices=("headless", "gui", "both"),
                        default="both")
    args = parser.parse_args()
    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    if not args.rom.is_file() or not args.symbols.is_file():
        raise RuntimeError("diagnostic ROM/label file is missing")
    modes = (False, True) if args.mode == "both" else (args.mode == "gui",)
    results = [run_mode(args, gui) for gui in modes]
    evidence = {
        "aps": "APS-057",
        "method": "get_suzy_registers readback of SPRHSIZ=$FC18 and SPRVSIZ=$FC1A at the second real-pointer _tgi_ioctl hit, the movable tgi_sprite submission",
        "rom": {"path": str(args.rom),
                "size_bytes": args.rom.stat().st_size,
                "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest()},
        "results": results,
        "passed": all(result["passed"] for result in results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("APS-057 verifier failed: %s" % error, file=sys.stderr)
        sys.exit(1)
