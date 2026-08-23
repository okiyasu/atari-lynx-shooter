#!/usr/bin/env python3
"""APS-056 v011 direct Gearlynx/MCP enemy-bullet verification.

The harness does not require the ROM to reach the interactive TITLE state.
It pauses at the first completed display-sync boundary, injects a collision-
free two-bullet GameState fixture, and records the exported one-shot trace,
the real movable-chain SCBs at ``_tgi_ioctl``, and the post-swap framebuffer.
Headless and GUI launches are separate attempts so a startup failure in one
path cannot be mistaken for a Gearlynx rendering result.
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

# cc65 GameState layout for the diagnostic ROM. The leading enemies pointer
# occupies two bytes; APS-055's enemy_bullet_move_phase occupies byte 8.
GAME_OFFSET_PLAYER = 2
GAME_OFFSET_BULLETS = 9
GAME_OFFSET_ENEMY_BULLETS = 69
GAME_OFFSET_STAGE = 212
GAME_OFFSET_PHASE = 213
GAME_OFFSET_PHASE_TIMER = 214
GAME_STATE_WRITE_END = 215
GAME_ENEMY_SIZE = 12
GAME_MAX_ENEMIES = 8
GAME_MAX_ENEMY_BULLETS = 16
GAME_HUD_HEIGHT = 10

TRACE_SLOT_SIZE = 11
TRACE_HEADER_SIZE = 8
TRACE_SIZE = TRACE_HEADER_SIZE + GAME_MAX_ENEMY_BULLETS * TRACE_SLOT_SIZE
TRACE_BEFORE_MARKER = 0xA5
TRACE_AFTER_MARKER = 0x5A
SCB_SPRCTL0 = 0
SCB_SPRCTL1 = 1
SCB_NEXT = 3
SCB_DATA = 5
SCB_HPOS = 7
SCB_VPOS = 9
SCB_SIZE = 19
SCB_SKIP = 0x04
SCB_REUSEPAL = 0x08
SCB_BPP1_NONCOLL = 0x05


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_visual_module():
    module = load_module("aps056_visual", VISUAL_SCRIPT)
    module.MCP_PORT = MCP_PORT
    return module


def load_static_module():
    module = load_module("aps056_static_readback", STATIC_READBACK)
    module.MCP_PORT = MCP_PORT
    return module


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], "little")


def signed_word(data, offset):
    value = word(data, offset)
    return value - 0x10000 if value & 0x8000 else value


def parse_trace(raw):
    if len(raw) != TRACE_SIZE:
        raise RuntimeError("unexpected APS-056 trace size: %d" % len(raw))
    trace = {
        "latched": raw[0],
        "active_count": raw[1],
        "visible_count": raw[2],
        "header_penpal0": raw[3],
        "submit_before": raw[4],
        "submit_after": raw[5],
        "submit_count": raw[6],
        "slot_count": raw[7],
        "slots": [],
    }
    for index in range(GAME_MAX_ENEMY_BULLETS):
        offset = TRACE_HEADER_SIZE + index * TRACE_SLOT_SIZE
        trace["slots"].append({
            "index": raw[offset],
            "sprctl0": raw[offset + 1],
            "sprctl1": raw[offset + 2],
            "hpos": signed_word(raw, offset + 3),
            "vpos": signed_word(raw, offset + 5),
            "data": word(raw, offset + 7),
            "next": word(raw, offset + 9),
        })
    return trace


def parse_scb(address, raw):
    return {
        "address": address,
        "sprctl0": raw[SCB_SPRCTL0],
        "sprctl1": raw[SCB_SPRCTL1],
        "next": word(raw, SCB_NEXT),
        "data": word(raw, SCB_DATA),
        "hpos": signed_word(raw, SCB_HPOS),
        "vpos": signed_word(raw, SCB_VPOS),
        "penpal": list(raw[11:19]),
        "raw": list(raw),
    }


def wait_for_breakpoint(visual, request_id, description):
    return visual.wait_for_breakpoint(request_id, description)


def inject_fixture(visual, game_address, enemy_address, fixture, request_id):
    player_x, player_y = fixture["player"]
    visual.write_bytes(game_address + GAME_OFFSET_PLAYER,
                       [player_x, player_y, 8, 6], request_id)
    request_id += 1

    state = [0] * (GAME_STATE_WRITE_END - GAME_OFFSET_BULLETS + 1)
    bullet_offset = GAME_OFFSET_ENEMY_BULLETS - GAME_OFFSET_BULLETS
    for slot, bullet in fixture["bullets"].items():
        x, y, active, velocity_x, velocity_y = bullet
        offset = bullet_offset + slot * 5
        state[offset:offset + 5] = [
            x, y, active, velocity_x & 0xFF, velocity_y & 0xFF]
    state[GAME_OFFSET_STAGE - GAME_OFFSET_BULLETS] = 1
    state[GAME_OFFSET_PHASE - GAME_OFFSET_BULLETS] = 1
    state[GAME_OFFSET_PHASE_TIMER - GAME_OFFSET_BULLETS] = 0
    state[GAME_OFFSET_PHASE_TIMER - GAME_OFFSET_BULLETS + 1] = 0
    visual.write_bytes(game_address + GAME_OFFSET_BULLETS, state, request_id)
    request_id += 1
    visual.write_bytes(game_address + 8, [0], request_id)
    request_id += 1
    visual.write_bytes(enemy_address,
                       [0] * (GAME_MAX_ENEMIES * GAME_ENEMY_SIZE), request_id)
    return request_id + 1


def read_chain(visual, root, request_id):
    entries = []
    seen = set()
    address = root
    while address != 0 and address not in seen and len(entries) < 64:
        seen.add(address)
        raw = bytes(visual.read_bytes(address, SCB_SIZE, request_id))
        request_id += 1
        if len(raw) != SCB_SIZE:
            raise RuntimeError("short SCB readback at 0x%04X" % address)
        entry = parse_scb(address, raw)
        entries.append(entry)
        address = entry["next"]
    if address != 0 and address in seen:
        raise RuntimeError("SCB chain cycle at 0x%04X" % address)
    if not entries:
        raise RuntimeError("empty SCB chain")
    return request_id, entries


def find_bullet_slots(chain, trace):
    data_address = trace["slots"][0]["data"]
    for start in range(len(chain) - GAME_MAX_ENEMY_BULLETS + 1):
        candidate = chain[start:start + GAME_MAX_ENEMY_BULLETS]
        if all(entry["data"] == data_address for entry in candidate):
            return candidate
    return None


def validate_trace(trace, state_raw):
    checks = {
        "latched": trace["latched"] == 1,
        "active_count_2": trace["active_count"] == 2,
        "visible_count_1": trace["visible_count"] == 1,
        "header_penpal_danger": trace["header_penpal0"] == 6,
        "submit_before_marker": trace["submit_before"] == TRACE_BEFORE_MARKER,
        "submit_after_marker": trace["submit_after"] == TRACE_AFTER_MARKER,
        "submit_count_1": trace["submit_count"] == 1,
        "slot_count_16": trace["slot_count"] == GAME_MAX_ENEMY_BULLETS,
        "slot_indices_0_to_15": [s["index"] for s in trace["slots"]] ==
            list(range(GAME_MAX_ENEMY_BULLETS)),
        "sprctl0_follower_slots_1bpp_noncoll": all(
            s["sprctl0"] == SCB_BPP1_NONCOLL
            for s in trace["slots"][1:]),
        "slot0_fields_captured": all(
            key in trace["slots"][0]
            for key in ("sprctl0", "sprctl1", "hpos", "vpos",
                        "data", "next")),
        "data_pointers_nonzero_and_shared": (
            all(s["data"] != 0 for s in trace["slots"]) and
            len({s["data"] for s in trace["slots"]}) == 1),
        "next_pointers_bounded": (
            all(s["next"] != 0 for s in trace["slots"][:-1]) and
            trace["slots"][-1]["next"] == 0),
        "source_active_slots_0_and_3": (
            state_raw[2] != 0 and state_raw[3 * 5 + 2] != 0),
        "slot0_render_fields_recorded": all(
            key in trace["slots"][0]
            for key in ("sprctl0", "sprctl1", "hpos", "vpos")),
        "slot3_render_fields_recorded": all(
            key in trace["slots"][3]
            for key in ("sprctl0", "sprctl1", "hpos", "vpos")),
    }
    return checks


def validate_direct_slots(slots, trace, fixture):
    slot0 = slots[0]
    slot3 = slots[3]
    expected_slot0 = {
        "sprctl0": SCB_BPP1_NONCOLL,
        "sprctl1": SCB_REUSEPAL,
        "hpos": fixture["bullets"][0][0],
        "vpos": fixture["bullets"][0][1],
    }
    expected_slot3 = {
        "sprctl0": SCB_BPP1_NONCOLL,
        "sprctl1": SCB_REUSEPAL | SCB_SKIP,
        "hpos": fixture["bullets"][3][0],
        "vpos": fixture["bullets"][3][1],
    }
    checks = {
        "chain_has_16_enemy_bullet_slots": len(slots) == GAME_MAX_ENEMY_BULLETS,
        "chain_slot_fields_read": all(
            entry["sprctl0"] == SCB_BPP1_NONCOLL and
            entry["data"] != 0 for entry in slots[1:]),
        "chain_data_matches_trace": all(
            entry["data"] == trace["slots"][index]["data"]
            for index, entry in enumerate(slots)),
        "chain_next_mapping": all(
            entry["next"] == (slots[index + 1]["address"]
                               if index + 1 < len(slots) else 0)
            for index, entry in enumerate(slots)),
        "slot0_matches_expected_fixture": all(
            slot0[key] == value for key, value in expected_slot0.items()),
        "slot3_matches_expected_hud_skip": all(
            slot3[key] == value for key, value in expected_slot3.items()),
        "slot0_expected_sprctl0": (
            slot0["sprctl0"] == expected_slot0["sprctl0"]),
        "slot0_expected_sprctl1": (
            slot0["sprctl1"] == expected_slot0["sprctl1"]),
        "slot0_expected_hpos": (
            slot0["hpos"] == expected_slot0["hpos"]),
        "slot0_expected_vpos": (
            slot0["vpos"] == expected_slot0["vpos"]),
        "slot3_expected_sprctl0": (
            slot3["sprctl0"] == expected_slot3["sprctl0"]),
        "slot3_expected_sprctl1": (
            slot3["sprctl1"] == expected_slot3["sprctl1"]),
        "slot3_expected_hpos": (
            slot3["hpos"] == expected_slot3["hpos"]),
        "slot3_expected_vpos": (
            slot3["vpos"] == expected_slot3["vpos"]),
    }
    return checks


def pixel_probe(rows, x, y, color):
    pixels = []
    for yy in range(y, y + 2):
        for xx in range(x, x + 2):
            pixels.append(list(rows[yy][xx * 4:xx * 4 + 4]))
    return {"pixels": pixels, "color_match": any(
        tuple(pixel) == tuple(color) for pixel in pixels)}


def start_gearlynx(visual, args, mode):
    command = [GEARLYNX]
    if mode == "headless":
        command.append("--headless")
    command.extend(["--mcp-http", "--mcp-http-port", str(MCP_PORT),
                    str(args.rom.resolve()), str(args.symbols.resolve())])
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    for _ in range(120):
        try:
            visual.call("initialize", {
                "protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "aps056-diagnostic", "version": "9"},
            })
            return process
        except Exception:
            time.sleep(0.5)
    process.terminate()
    process.wait(timeout=5)
    raise RuntimeError("Gearlynx %s MCP server did not start" % mode)


def capture_mode(args, mode, visual, static_module):
    process = None
    result = {"mode": mode, "status": "blocked"}
    try:
        process = start_gearlynx(visual, args, mode)
        symbols = {
            name: visual.symbol_address(args.symbols, name)
            for name in ("_game", "_game_enemies",
                         "_game_display_sync_complete", "_tgi_ioctl",
                         "_aps056_scb_trace")
        }
        result["symbols"] = symbols
        result["initial_debug_status"] = visual.tool(
            "debug_get_status", request_id=2)
        request_id = 3
        visual.tool("set_breakpoint",
                    {"address": "%04X" % symbols["_game_display_sync_complete"]},
                    request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_for_breakpoint(
            visual, request_id + 1, "initial display-sync boundary")
        visual.tool("remove_breakpoint", {
            "address": "%04X" % symbols["_game_display_sync_complete"]},
            request_id)
        request_id += 1

        fixture = {
            "player": (20, 70),
            "bullets": {
                0: (100, 40, 1, 0, 0),
                3: (80, 9, 1, 0, 0),
            },
        }
        request_id = inject_fixture(
            visual, symbols["_game"], symbols["_game_enemies"],
            fixture, request_id)
        visual.tool("set_breakpoint",
                    {"address": "%04X" % symbols["_tgi_ioctl"]},
                    request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id += 1

        trace_at_ioctl = None
        direct_slots = None
        ioctl_hits = []
        for _ in range(96):
            request_id = wait_for_breakpoint(
                visual, request_id, "movable SCB tgi_ioctl")
            cpu = visual.tool("get_6502_status", request_id=request_id)
            request_id += 1
            pointer = int(cpu["A"], 16) | (int(cpu["X"], 16) << 8)
            trace_raw = bytes(visual.read_bytes(
                symbols["_aps056_scb_trace"], TRACE_SIZE, request_id))
            request_id += 1
            trace_at_ioctl = parse_trace(trace_raw)
            hit = {"pointer": "0x%04X" % pointer,
                   "trace_latched": trace_at_ioctl["latched"]}
            if pointer >= 0x1000:
                request_id, chain = read_chain(visual, pointer, request_id)
                slots = find_bullet_slots(chain, trace_at_ioctl)
                hit["chain_entries"] = len(chain)
                if slots is not None:
                    direct_slots = slots
                    hit["enemy_bullet_slots"] = True
                    ioctl_hits.append(hit)
                    break
            hit["enemy_bullet_slots"] = False
            ioctl_hits.append(hit)
            visual.tool("debug_continue", request_id=request_id)
            request_id += 1
        if direct_slots is None or trace_at_ioctl is None:
            raise RuntimeError("real enemy-bullet SCB chain not found")
        visual.tool("remove_breakpoint",
                    {"address": "%04X" % symbols["_tgi_ioctl"]},
                    request_id)
        request_id += 1
        visual.tool("debug_step_out", request_id=request_id)
        request_id += 1

        visual.tool("set_breakpoint", {
            "address": "%04X" % symbols["_game_display_sync_complete"]},
            request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_for_breakpoint(
            visual, request_id + 1, "post-submit display-sync boundary")
        visual.tool("remove_breakpoint", {
            "address": "%04X" % symbols["_game_display_sync_complete"]},
            request_id)
        request_id += 1

        state_raw = bytes(visual.read_bytes(
            symbols["_game"] + GAME_OFFSET_ENEMY_BULLETS,
            GAME_MAX_ENEMY_BULLETS * 5, request_id))
        request_id += 1
        trace = parse_trace(bytes(visual.read_bytes(
            symbols["_aps056_scb_trace"], TRACE_SIZE, request_id)))
        request_id += 1
        checks = validate_trace(trace, state_raw)
        direct_checks = validate_direct_slots(direct_slots, trace, fixture)
        checks.update({"direct_" + key: value
                       for key, value in direct_checks.items()})

        output_stem = args.output.with_name(
            args.output.stem + "-" + mode)
        screen_png, screen_rows = static_module.read_screenshot_png(
            visual, request_id)
        request_id += 1
        vidbas_png, vidbas_rows = static_module.read_framebuffer_png(
            visual, "vidbas", request_id)
        request_id += 1
        dispadr_png, dispadr_rows = static_module.read_framebuffer_png(
            visual, "dispadr", request_id)
        output_stem.parent.mkdir(parents=True, exist_ok=True)
        screen_path = output_stem.with_name(output_stem.name + "-screen.png")
        vidbas_path = output_stem.with_name(output_stem.name + "-vidbas.png")
        dispadr_path = output_stem.with_name(output_stem.name + "-dispadr.png")
        screen_path.write_bytes(screen_png)
        vidbas_path.write_bytes(vidbas_png)
        dispadr_path.write_bytes(dispadr_png)
        color = static_module.stage_palette_rgba(visual, 1)[6]
        probes = {
            "screenshot": pixel_probe(screen_rows, 100, 40, color),
            "vidbas": pixel_probe(vidbas_rows, 100, 40, color),
            "dispadr": pixel_probe(dispadr_rows, 100, 40, color),
        }
        result.update({
            "status": "PASS" if all(checks.values()) else "FAIL",
            "fixture": fixture,
            "state_enemy_bullets": [list(state_raw[index:index + 5])
                                     for index in range(0, len(state_raw), 5)],
            "trace": trace,
            "trace_at_ioctl": trace_at_ioctl,
            "direct_scb_slots": direct_slots,
            "checks": checks,
            "interpretation": {
                "scb_layout": {
                    "sprctl0": 0,
                    "sprctl1": 1,
                    "next": 3,
                    "data": 5,
                    "hpos": 7,
                    "vpos": 9,
                    "size": 11,
                },
                "game_state_slot0": list(state_raw[0:5]),
                "game_state_slot3": list(state_raw[15:20]),
                "trace_slot0": trace["slots"][0],
                "trace_slot3": trace["slots"][3],
                "direct_scb_slot0": direct_slots[0],
                "direct_scb_slot3": direct_slots[3],
                "expected_slot0": {
                    "sprctl0": SCB_BPP1_NONCOLL,
                    "sprctl1": SCB_REUSEPAL,
                    "hpos": fixture["bullets"][0][0],
                    "vpos": fixture["bullets"][0][1],
                },
                "expected_slot3": {
                    "sprctl0": SCB_BPP1_NONCOLL,
                    "sprctl1": SCB_REUSEPAL | SCB_SKIP,
                    "hpos": fixture["bullets"][3][0],
                    "vpos": fixture["bullets"][3][1],
                },
            },
            "ioctl_hits": ioctl_hits,
            "frame": {
                "screen_png": str(screen_path),
                "vidbas_png": str(vidbas_path),
                "dispadr_png": str(dispadr_path),
                "screen_sha256": hashlib.sha256(screen_png).hexdigest(),
                "vidbas_sha256": hashlib.sha256(vidbas_png).hexdigest(),
                "dispadr_sha256": hashlib.sha256(dispadr_png).hexdigest(),
                "bullet_color_index": 6,
                "bullet_color_rgba": list(color),
                "pixel_probe": probes,
                "pages_equal": vidbas_rows == dispadr_rows,
            },
        })
        return result
    except Exception as error:
        result["error"] = str(error)
        try:
            result["failure_debug_status"] = visual.tool(
                "debug_get_status", request_id=6000)
        except Exception:
            pass
        return result
    finally:
        if process is not None:
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
                        default=Path("evidence/APS-056/scb-trace-v011.json"))
    parser.add_argument("--mode", choices=("headless", "gui", "both"),
                        default="both")
    args = parser.parse_args()
    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    if not args.rom.is_file() or not args.symbols.is_file():
        raise RuntimeError("diagnostic ROM/label file is missing")

    static_module = load_static_module()
    modes = ("headless", "gui") if args.mode == "both" else (args.mode,)
    evidence = {
        "aps": "APS-056",
        "version": "v011",
        "status": "blocked",
        "rom": {"path": str(args.rom),
                "size_bytes": args.rom.stat().st_size,
                "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest()},
        "method": {
            "startup": "separate Gearlynx GUI/MCP and headless/MCP attempts",
            "fixture_boundary": "_game_display_sync_complete read_memory/write_memory",
            "trace": "one-shot GameAps056ScbTrace before/after tgi_sprite",
            "direct_scb": "real _tgi_ioctl chain readback, 16 enemy-bullet slots",
            "frame": "post-submit sync get_screenshot and vidbas/dispadr readback",
            "game_state_offsets": {
                "enemy_bullets": GAME_OFFSET_ENEMY_BULLETS,
                "stage": GAME_OFFSET_STAGE,
                "phase": GAME_OFFSET_PHASE,
            },
        },
        "attempts": [],
    }
    for mode in modes:
        visual = load_visual_module()
        attempt = capture_mode(args, mode, visual, static_module)
        evidence["attempts"].append(attempt)
        print("%s: %s" % (mode, attempt["status"]))
    successful = [item for item in evidence["attempts"]
                  if item["status"] == "PASS"]
    failed = [item for item in evidence["attempts"]
              if item["status"] == "FAIL"]
    if evidence["attempts"] and not failed and len(successful) == len(
            evidence["attempts"]):
        evidence["status"] = "PASS"
    elif failed:
        evidence["status"] = "FAIL"
    else:
        evidence["status"] = "blocked"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return 0 if evidence["status"] == "PASS" else 1 if failed else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("FAIL: %s" % error, file=sys.stderr)
        sys.exit(1)
