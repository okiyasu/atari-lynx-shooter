#!/usr/bin/env python3
"""APS-056: capture the real enemy-bullet SCB path on the CADENCE ROM.

The diagnostic ROM snapshots the 16 enemy-bullet SCB slots immediately before
the production tgi_sprite() call. This verifier injects controlled GameState
fixtures, captures the real movable-chain submission, and records source
active/x/y together with SPRCTL1, hpos/vpos, slot linkage, and data pointers.
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
STATIC_READBACK = ROOT / "scripts" / "verify-static-layer-readback-gearlynx.py"
VISUAL_SCRIPT = ROOT / "scripts" / "verify-stage-visuals-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17784

GAME_OFFSET_PLAYER = 2
GAME_OFFSET_BULLETS = 6
GAME_OFFSET_ENEMY_BULLETS = 66
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PHASE = 210
GAME_OFFSET_PHASE_TIMER = 211
GAME_STATE_WRITE_END = 213
GAME_ENEMY_SIZE = 12
GAME_MAX_ENEMIES = 8
GAME_MAX_ENEMY_BULLETS = 16
GAME_HUD_HEIGHT = 10
SCB_SKIP = 0x04
SCB_REUSEPAL = 0x08
SCB_NEXT = 3
SCB_DATA = 5
SCB_HPOS = 7
SCB_VPOS = 9
SCB_NOREUSE_SIZE = 11
SCB_PAL_SIZE = 19
CHAIN_SIZES = ([SCB_PAL_SIZE] + [SCB_NOREUSE_SIZE] * 2 +
               [SCB_PAL_SIZE] + [SCB_NOREUSE_SIZE] * 0 +
               [SCB_PAL_SIZE] + [SCB_NOREUSE_SIZE] * 8 +
               [SCB_PAL_SIZE] * 3 + [SCB_NOREUSE_SIZE] * 12 +
               [SCB_PAL_SIZE] + [SCB_NOREUSE_SIZE] * 16)
ENEMY_BULLET_CHAIN_START = 29


def load_visual_module():
    spec = importlib.util.spec_from_file_location(
        "aps056_visual", VISUAL_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    return module


def load_static_module():
    spec = importlib.util.spec_from_file_location(
        "aps056_static_readback", STATIC_READBACK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    return module


def signed_word(data, offset):
    value = int.from_bytes(data[offset:offset + 2], "little")
    return value - 0x10000 if value & 0x8000 else value


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], "little")


def parse_chain(visual, chain_head, request_id):
    entries = []
    address = chain_head
    for index, size in enumerate(CHAIN_SIZES):
        raw = visual.read_bytes(address, SCB_PAL_SIZE, request_id)
        request_id += 1
        entries.append({
            "chain_index": index,
            "address": address,
            "sprctl1": raw[1],
            "next_address": word(raw, SCB_NEXT),
            "data_address": word(raw, SCB_DATA),
            "hpos": signed_word(raw, SCB_HPOS),
            "vpos": signed_word(raw, SCB_VPOS),
            "raw": list(raw[:size]),
        })
        if index == len(CHAIN_SIZES) - 1:
            if entries[-1]["next_address"] != 0:
                raise RuntimeError("movable SCB chain did not terminate")
        else:
            address = entries[-1]["next_address"]
            if address == 0:
                raise RuntimeError("movable SCB chain ended at index %d" % index)
    return request_id, entries


def wait_for_breakpoint(visual, request_id, description):
    return visual.wait_for_breakpoint(request_id, description)


def drain_to_sync(visual, sync_address, request_id, description):
    visual.tool("set_breakpoint", {"address": "%04X" % sync_address},
                request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = wait_for_breakpoint(visual, request_id + 1, description)
    visual.tool("remove_breakpoint", {"address": "%04X" % sync_address},
                request_id)
    return request_id + 1


def inject_fixture(visual, game_address, enemy_address, fixture, request_id):
    player_x, player_y = fixture["player"]
    visual.write_bytes(game_address + GAME_OFFSET_PLAYER,
                       [player_x, player_y, 8, 6], request_id)
    request_id += 1

    state = [0] * (GAME_STATE_WRITE_END - GAME_OFFSET_BULLETS + 1)
    bullet_offset = GAME_OFFSET_ENEMY_BULLETS - GAME_OFFSET_BULLETS
    x, y, active, velocity_x, velocity_y = fixture["bullet"]
    state[bullet_offset:bullet_offset + 5] = [
        x, y, active, velocity_x & 0xFF, velocity_y & 0xFF]
    state[GAME_OFFSET_STAGE - GAME_OFFSET_BULLETS] = 1
    state[GAME_OFFSET_PHASE - GAME_OFFSET_BULLETS] = 1
    state[GAME_OFFSET_PHASE_TIMER - GAME_OFFSET_BULLETS] = 0
    state[GAME_OFFSET_PHASE_TIMER - GAME_OFFSET_BULLETS + 1] = 0
    visual.write_bytes(game_address + GAME_OFFSET_BULLETS, state, request_id)
    request_id += 1
    visual.write_bytes(enemy_address,
                       [0] * (GAME_MAX_ENEMIES * GAME_ENEMY_SIZE), request_id)
    return request_id + 1


def capture_fixture(visual, game_address, enemy_address,
                    ioctl_address, sync_address, fixture, request_id,
                    name):
    request_id = drain_to_sync(
        visual, sync_address, request_id, "%s pre-draw boundary" % name)
    request_id = inject_fixture(
        visual, game_address, enemy_address, fixture, request_id)

    visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address},
                request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    pointer_hits = []
    for _ in range(96):
        request_id = wait_for_breakpoint(
            visual, request_id + 1, "%s tgi_ioctl" % name)
        cpu = visual.tool("get_6502_status", request_id=request_id)
        request_id += 1
        candidate = int(cpu["A"], 16) | (int(cpu["X"], 16) << 8)
        if candidate >= 0x1000:
            pointer_hits.append(candidate)
            if len(pointer_hits) == 2:
                break
        visual.tool("debug_continue", request_id=request_id)
        request_id += 1
    if len(pointer_hits) != 2:
        raise RuntimeError("%s: expected static and movable SCB hits, got %d" %
                           (name, len(pointer_hits)))

    state_raw = visual.read_bytes(
        game_address + GAME_OFFSET_ENEMY_BULLETS,
        GAME_MAX_ENEMY_BULLETS * 5, request_id)
    request_id += 1
    request_id, chain = parse_chain(visual, pointer_hits[1], request_id)
    slots = []
    for index in range(GAME_MAX_ENEMY_BULLETS):
        source = state_raw[index * 5:index * 5 + 5]
        scb = chain[ENEMY_BULLET_CHAIN_START + index]
        slots.append({
            "index": index,
            "source_active": source[2],
            "source_x": source[0],
            "source_y": source[1],
            "sprctl1": scb["sprctl1"],
            "hpos": scb["hpos"],
            "vpos": scb["vpos"],
            "slot_address": scb["address"],
            "next_address": scb["next_address"],
            "data_address": scb["data_address"],
        })
    trace = {"slot_count": len(slots), "slots": slots,
             "movable_chain_head": pointer_hits[1],
             "chain_entry_count": len(chain),
             "game_enemy_bullets": list(state_raw)}

    visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address},
                request_id)
    request_id += 1
    visual.tool("debug_step_out", request_id=request_id)
    request_id += 1
    return request_id, trace


def validate_trace(trace):
    checks = {
        "slot_count_16": trace["slot_count"] == GAME_MAX_ENEMY_BULLETS,
        "chain_entry_count_45": trace["chain_entry_count"] == 45,
        "slot_addresses_unique": len({s["slot_address"] for s in trace["slots"]}) == 16,
        "chain_next_mapping": all(
            s["next_address"] == (trace["slots"][i + 1]["slot_address"]
                                   if i < 15 else 0)
            for i, s in enumerate(trace["slots"])),
        "data_pointers_nonzero_and_shared": (
            all(s["data_address"] != 0 for s in trace["slots"]) and
            len({s["data_address"] for s in trace["slots"]}) == 1),
    }
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path,
                        default=Path("dist/asteroid-patrol-aps056-diagnostic.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol-aps056-diagnostic.lbl"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-056/scb-trace-v002.json"))
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    if not args.rom.is_file() or not args.symbols.is_file():
        raise RuntimeError("diagnostic ROM/label file is missing")

    visual = load_visual_module()
    static_module = load_static_module()
    process = None
    evidence = {
        "aps": "APS-056", "version": "v002", "status": "blocked",
        "rom": {"path": str(args.rom),
                "size_bytes": args.rom.stat().st_size,
                "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest()},
        "fixtures": [],
        "method": {
            "capture": "real _tgi_ioctl movable-chain submission",
            "snapshot": "main.c after enemy-bullet SCB predicate and before tgi_sprite",
            "chain_layout": "env header/2 env/player/enemy header/8 enemy/boss/power/pbullet header/12 pbullet/ebullet header/16 ebullet",
            "production_sprctl1": {"REUSEPAL": SCB_REUSEPAL,
                                    "SKIP": SCB_SKIP},
        },
    }

    try:
        command = [GEARLYNX]
        if not args.gui:
            command.append("--headless")
        command.extend(["--mcp-http", "--mcp-http-port", str(MCP_PORT),
                        str(args.rom.resolve()), str(args.symbols.resolve())])
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        for _ in range(120):
            try:
                visual.call("initialize", {
                    "protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "aps056-diagnostic", "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")

        game_address = visual.symbol_address(args.symbols, "_game")
        enemy_address = visual.symbol_address(args.symbols, "_game_enemies")
        ioctl_address = visual.symbol_address(args.symbols, "_tgi_ioctl")
        sync_address = visual.symbol_address(
            args.symbols, "_game_display_sync_complete")
        scratch_address = visual.symbol_address(
            args.symbols, "_title_voice_scratch_buffer")
        voice_active_address = scratch_address + 640 + 6
        evidence["symbols"] = {
            "game": game_address, "game_enemies": enemy_address,
            "tgi_ioctl": ioctl_address,
            "display_sync": sync_address,
        }

        request_id = static_module.wait_stable_title(
            visual, game_address, voice_active_address, 1)
        fixtures = [
            ("collision_before_draw", {
                "player": (100, 40), "bullet": (102, 40, 1, -2, 0)}),
            ("active_in_play", {
                "player": (20, 70), "bullet": (100, 40, 1, 0, 0)}),
            ("active_above_hud", {
                "player": (20, 70), "bullet": (100, 9, 1, 0, 0)}),
        ]
        for name, fixture in fixtures:
            request_id, trace = capture_fixture(
                visual, game_address, enemy_address,
                ioctl_address, sync_address, fixture, request_id, name)
            checks = validate_trace(trace)
            slot0 = trace["slots"][0]
            if name == "collision_before_draw":
                checks["collision_source_inactive"] = slot0["source_active"] == 0
                checks["collision_slot_skip"] = (
                    slot0["sprctl1"] & SCB_SKIP) != 0
            elif name == "active_in_play":
                checks["active_source_preserved"] = slot0["source_active"] != 0
                checks["active_slot_not_skipped"] = (
                    slot0["sprctl1"] & SCB_SKIP) == 0
                checks["active_coordinates_copied"] = (
                    slot0["hpos"] == slot0["source_x"] and
                    slot0["vpos"] == slot0["source_y"])
            else:
                checks["above_hud_source_preserved"] = slot0["source_active"] != 0
                checks["above_hud_slot_skip"] = (
                    slot0["sprctl1"] & SCB_SKIP) != 0
            result = {"name": name, "fixture": fixture, "trace": trace,
                      "checks": checks, "passed": all(checks.values())}
            evidence["fixtures"].append(result)
            print("%s: %s" % (name, "PASS" if result["passed"] else "FAIL"))

        evidence["status"] = "PASS" if all(
            item["passed"] for item in evidence["fixtures"]) else "FAIL"
        return 0 if evidence["status"] == "PASS" else 1
    except Exception as error:
        evidence["error"] = str(error)
        return 2
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("FAIL: %s" % error, file=sys.stderr)
        sys.exit(1)
