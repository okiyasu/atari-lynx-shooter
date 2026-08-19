#!/usr/bin/env python3
"""APS-053 v047: gate(a) full-frame section breakdown.

v046 measured the movable SCB chain's own cost (scb_begin/finish_enter/
finish_exit, scripts/verify-phase-3r-gate-a-breakdown-gearlynx.py) at
0.779 VBlank for the boss+4-enemies+full-bullets fixture -- gate(a)'s
2 VBlank target achieved for that slice. But that harness's own
`pre_movable_ticks` field (everything before scb_begin) measured 9.35
VBlank (full fixture) / 9.95 VBlank (empty), confirming v040's finding
that ~9 VBlank of gate(a)'s cost lives outside the movable SCB path
entirely and remains unidentified. This script decomposes that 9 VBlank
into named sections using only public (non-static) symbols already
linked into the cadence ROM -- no internal function addresses are
guessed, consistent with every prior APS-053 gate(a) diagnostic.

Sections (boundaries are one-shot breakpoints on public symbols, armed,
hit once, and removed before the next boundary is armed -- the same
set-hit-remove-per-boundary technique v019 established after v018's
simultaneous-multi-breakpoint approach caused the emulator's MCP server
to stop responding):

  A input_timing_to_logic:   prior display_request -> first
                              game_update_logic() entry this frame
                              (input poll, game_timing_consume_vblanks,
                              logic-update-count computation)
  B logic_loop:               first game_update_logic() entry -> first
                              game_sound_tick() entry (the whole
                              elapsed-vblanks-scaled logic update loop,
                              game_update_logic may run several times
                              per frame but only the first entry is a
                              breakpoint target)
  C sound_loop_and_wait:       first game_sound_tick() entry ->
                              game_display_sync_complete() entry (the
                              sound update loop, sound_backend_apply_all,
                              and GAME_DISPLAY_READY_WAIT's tgi_busy()
                              poll)
  D sync_to_static_layer:      game_display_sync_complete() entry ->
                              static_layer_draw() entry (draw_game's own
                              prologue up to its first call)
  E static_layer_and_overlay:  static_layer_draw() entry -> movable SCB
                              chain's scb_begin marker (background SCB
                              construction/submission, draw_phase_overlay,
                              draw_environment's TGI overlays, draw_mask
                              when dying)
  F movable_scb_and_suzy:      scb_begin -> scb_finish_exit (the slice
                              v046 already measured and optimized to
                              0.779 VBlank; reported here again for a
                              same-run cross-check against the v046b
                              evidence, not a new measurement target)
  G finish_to_display_request: scb_finish_exit -> this frame's
                              display_request() entry (game_over text,
                              display_request() call itself)

A+B+C+D+E should sum close to breakdown's pre_movable_ticks; F should
match v046b's scb_build+pure_suzy; A..G should sum close to
total_frame_ticks. Diagnostic only -- does not modify any production
code path, scheduling, or the movable SCB chain.
"""

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE_A_MODULE_PATH = (
    ROOT / "scripts" / "verify-phase-3r-gate-a-full-fixture-gearlynx.py"
)
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17783

FRAME_SAMPLES_PER_BATCH = 15
BATCH_COUNT = 2
# See verify-phase-3r-gate-a-breakdown-gearlynx.py WARMUP_FRAMES comment:
# the ROM probe's own internal warmup counter needs to settle before
# recording starts.
WARMUP_FRAMES = 9
STABLE_TITLE_TIMEOUT = 12.0

# v024 calibration (evidence/APS-053/tick-calibration-v024.json,
# 184,668 CPU ticks/VBlank median, CV=0.00074), the same constant used by
# verify-phase-3r-gate-a-breakdown-gearlynx.py.
TICKS_PER_VBLANK = 184668.0

SECTION_KEYS = (
    "a_input_timing_to_logic",
    "b_logic_loop",
    "c_sound_loop_and_wait",
    "d_sync_to_static_layer",
    "e1_static_layer_scb_build",
    "e2_static_layer_suzy_and_overlay",
    "f_movable_scb_and_suzy",
    "g_finish_to_display_request",
)


def load_gate_a_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_gate_a_full_fixture", GATE_A_MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    return module


def one_breakpoint(g, address, request_id, description):
    address_hex = "%04X" % address
    g.tool("set_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    g.tool("debug_continue", request_id=request_id)
    request_id += 1
    request_id = g.wait_for_breakpoint(request_id, description)
    g.tool("remove_breakpoint", {"address": address_hex}, request_id)
    return request_id + 1


def read_total_ticks(g, request_id):
    payload = g.tool("get_6502_status", request_id=request_id)
    return request_id + 1, payload["total_ticks"]


def read_u16(g, address, request_id):
    value = int.from_bytes(g.read_bytes(address, 2, request_id), "little")
    return request_id + 1, value


def resolve_addresses(g, symbols):
    return {
        "game": g.symbol_address(symbols, "_game"),
        "enemies": g.symbol_address(symbols, "_game_enemies"),
        "display_request": g.symbol_address(symbols, "_game_display_request"),
        "update_logic": g.symbol_address(symbols, "_game_update_logic"),
        "sound_tick": g.symbol_address(symbols, "_game_sound_tick"),
        "display_sync_complete": g.symbol_address(
            symbols, "_game_display_sync_complete"),
        "static_layer_draw": g.symbol_address(symbols, "_static_layer_draw"),
        "static_layer_pre_finish": g.symbol_address(
            symbols, "_static_layer_split_marker_pre_finish"),
        "scb_begin": g.symbol_address(symbols, "_scb_split_marker_begin"),
        "scb_finish_exit": g.symbol_address(
            symbols, "_scb_split_marker_finish_exit"),
        "vblank_count": g.symbol_address(
            symbols, "_cadence_probe_vblank_count"),
        "probe_armed": g.symbol_address(symbols, "_cadence_probe_armed"),
    }


def start_paused(g, rom, symbols, port):
    command = [
        GEARLYNX, "--headless", "--mcp-http", "--mcp-http-port", str(port),
        str(rom), str(symbols),
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for attempt in range(40):
        try:
            g.call("initialize", {
                "protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "aps053-frame-breakdown",
                               "version": "1"},
            })
            break
        except Exception:
            if attempt == 39:
                process.terminate()
                raise RuntimeError("Gearlynx MCP server did not start")
            time.sleep(0.2)
    g.tool("debug_continue", request_id=2)
    request_id = 3
    game_address = g.symbol_address(symbols, "_game")
    deadline = time.monotonic() + STABLE_TITLE_TIMEOUT
    stable = 0
    while time.monotonic() < deadline:
        state = g.read_bytes(game_address + g.GAME_OFFSET_STAGE, 2,
                             request_id)
        request_id += 1
        if state == bytes([1, g.GAME_PHASE_TITLE]):
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
        time.sleep(0.01)
    else:
        process.terminate()
        raise RuntimeError("ROM did not reach stable TITLE state")
    g.tool("debug_pause", request_id=request_id)
    request_id += 1
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = g.tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status.get("paused"):
            return process, request_id
        time.sleep(0.01)
    process.terminate()
    raise RuntimeError("did not pause after stable TITLE")


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def inject_empty_fixture(g, game_address, enemy_address, request_id):
    """Same clearing as verify-phase-3r-gate-a-breakdown-gearlynx.py's
    empty fixture: 0 enemies, boss inactive, 0 bullets, GAME_PHASE_NORMAL."""
    g.write_bytes(game_address + 164, [0] * (191 - 164), request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_PLAYER, [8, 0, 8, 6],
                 request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_BULLETS,
                 [0] * (g.GAME_MAX_PLAYER_BULLETS * 5), request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_ENEMY_BULLETS,
                 [0] * (g.GAME_MAX_ENEMY_BULLETS * 5), request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_POWER_ITEM, [0] * 4,
                 request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_BOSS, [0] * 14, request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_GAME_OVER, [0], request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_TITLE_VOICE_PENDING,
                 [0, 0, 0, 0], request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_DYING, [0, 0, 0], request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_STAGE,
                 [1, g.GAME_PHASE_NORMAL, 0, 0], request_id)
    request_id += 1
    g.write_bytes(enemy_address, g.enemy_records(0), request_id)
    return request_id + 1


def run_batch(g, rom, symbols, port, fixture_kind, batch_index):
    process, request_id = start_paused(g, rom, symbols, port)
    try:
        addresses = resolve_addresses(g, symbols)
        inject = (g.inject_full_fixture if fixture_kind == "full"
                 else lambda ga, ea, rid: inject_empty_fixture(g, ga, ea, rid))
        request_id = inject(addresses["game"], addresses["enemies"],
                            request_id)
        g.write_bytes(addresses["probe_armed"], [1], request_id)
        request_id += 1
        warmup_vblanks = []
        d_prev = None
        for warm in range(WARMUP_FRAMES):
            request_id = one_breakpoint(
                g, addresses["display_request"], request_id,
                "%s batch %d warm-up %d" % (fixture_kind, batch_index, warm),
            )
            request_id, vblank_raw = read_u16(g, addresses["vblank_count"],
                                              request_id)
            request_id, d_prev = read_total_ticks(g, request_id)
            warmup_vblanks.append(vblank_raw)
            request_id = inject(addresses["game"], addresses["enemies"],
                                request_id)
        frames = []
        for index in range(FRAME_SAMPLES_PER_BATCH):
            desc = "%s batch %d frame %d" % (fixture_kind, batch_index, index)
            request_id = one_breakpoint(
                g, addresses["update_logic"], request_id, desc + " logic")
            request_id, t_logic = read_total_ticks(g, request_id)
            request_id = one_breakpoint(
                g, addresses["sound_tick"], request_id, desc + " sound")
            request_id, t_sound = read_total_ticks(g, request_id)
            request_id = one_breakpoint(
                g, addresses["display_sync_complete"], request_id,
                desc + " sync")
            request_id, t_sync = read_total_ticks(g, request_id)
            request_id = one_breakpoint(
                g, addresses["static_layer_draw"], request_id,
                desc + " static_layer")
            request_id, t_static = read_total_ticks(g, request_id)
            request_id = one_breakpoint(
                g, addresses["static_layer_pre_finish"], request_id,
                desc + " static_layer_pre_finish")
            request_id, t_static_pre_finish = read_total_ticks(
                g, request_id)
            request_id = one_breakpoint(
                g, addresses["scb_begin"], request_id, desc + " scb_begin")
            request_id, t_scb_begin = read_total_ticks(g, request_id)
            request_id = one_breakpoint(
                g, addresses["scb_finish_exit"], request_id,
                desc + " scb_finish_exit")
            request_id, t_scb_exit = read_total_ticks(g, request_id)
            request_id = one_breakpoint(
                g, addresses["display_request"], request_id,
                desc + " display_request")
            request_id, vblank_raw = read_u16(g, addresses["vblank_count"],
                                              request_id)
            request_id, d_this = read_total_ticks(g, request_id)
            request_id = inject(addresses["game"], addresses["enemies"],
                                request_id)

            sections = {
                "a_input_timing_to_logic": t_logic - d_prev,
                "b_logic_loop": t_sound - t_logic,
                "c_sound_loop_and_wait": t_sync - t_sound,
                "d_sync_to_static_layer": t_static - t_sync,
                "e1_static_layer_scb_build": t_static_pre_finish - t_static,
                "e2_static_layer_suzy_and_overlay":
                    t_scb_begin - t_static_pre_finish,
                "f_movable_scb_and_suzy": t_scb_exit - t_scb_begin,
                "g_finish_to_display_request": d_this - t_scb_exit,
            }
            frame = {
                "frame": index,
                "total_ticks": {
                    "prev_display_request": d_prev, "logic": t_logic,
                    "sound": t_sound, "sync": t_sync, "static": t_static,
                    "static_pre_finish": t_static_pre_finish,
                    "scb_begin": t_scb_begin, "scb_exit": t_scb_exit,
                    "display_request": d_this,
                },
                "sections": sections,
                "total_frame_ticks": d_this - d_prev,
                "vblank_count_since_prev_display_request": vblank_raw,
            }
            frames.append(frame)
            d_prev = d_this
        return {
            "batch": batch_index,
            "fixture": fixture_kind,
            "warmup_vblank_counts": warmup_vblanks,
            "frames": frames,
        }
    finally:
        stop_process(process)


def summarize(values):
    return {
        "samples": len(values), "values": values,
        "median": statistics.median(values), "min": min(values),
        "max": max(values),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path,
                        default=Path("dist/asteroid-patrol-cadence.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol-cadence.lbl"))
    parser.add_argument("--output", type=Path, default=Path(
        "evidence/APS-053/phase-3r-frame-breakdown-v047.json"))
    args = parser.parse_args()

    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")

    g = load_gate_a_module()

    evidence = {
        "aps": "APS-053", "phase": "3R2", "brief": None,
        "status": "blocked",
        "rom": {
            "path": str(args.rom),
            "size_bytes": args.rom.stat().st_size,
            "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
        },
        "method": {
            "sections": [
                "a_input_timing_to_logic", "b_logic_loop",
                "c_sound_loop_and_wait", "d_sync_to_static_layer",
                "e1_static_layer_scb_build",
                "e2_static_layer_suzy_and_overlay",
                "f_movable_scb_and_suzy",
                "g_finish_to_display_request",
            ],
            "markers": {
                "a_start": "prior frame's _game_display_request entry",
                "a_end/b_start": "_game_update_logic entry (first hit "
                    "this frame only)",
                "b_end/c_start": "_game_sound_tick entry (first hit this "
                    "frame only)",
                "c_end/d_start": "_game_display_sync_complete entry",
                "d_end/e1_start": "_static_layer_draw entry",
                "e1_end/e2_start": "_static_layer_split_marker_pre_finish "
                    "(new v047 diagnostic marker, static_layer.c "
                    "finish_layer(), right before tgi_sprite(SCBS))",
                "e2_end/f_start": "_scb_split_marker_begin (movable SCB "
                    "chain begin, unchanged from v040/v046)",
                "f_end/g_start": "_scb_split_marker_finish_exit (movable "
                    "SCB chain + Suzy submit complete)",
                "g_end": "this frame's _game_display_request entry",
            },
            "timer": "get_6502_status().total_ticks, tick-exact (NOT 1:1 "
                "with CPU cycles -- see evidence/APS-053/README.md v044 "
                "correction, ~4.4-5.0x a nominal 4MHz cycle)",
            "ticks_per_vblank_calibration": TICKS_PER_VBLANK,
            "frames_per_batch": FRAME_SAMPLES_PER_BATCH,
            "independent_batch_count": BATCH_COUNT,
            "warmup_frames": WARMUP_FRAMES,
        },
    }

    try:
        results = {}
        for fixture_kind in ("full", "empty"):
            batches = []
            for batch_index in range(1, BATCH_COUNT + 1):
                print("running %s fixture batch %d..." %
                      (fixture_kind, batch_index))
                batch = run_batch(g, args.rom, args.symbols, MCP_PORT,
                                  fixture_kind, batch_index)
                batches.append(batch)
                medians = {
                    key: statistics.median(
                        f["sections"][key] for f in batch["frames"])
                    for key in SECTION_KEYS
                }
                print("  " + " ".join(
                    "%s=%d(%.3fVB)" % (k, v, v / TICKS_PER_VBLANK)
                    for k, v in medians.items()))
                print("  total_frame median=%d(%.3fVB) vblank=%d" % (
                    statistics.median(
                        f["total_frame_ticks"] for f in batch["frames"]),
                    statistics.median(
                        f["total_frame_ticks"] for f in batch["frames"]) /
                        TICKS_PER_VBLANK,
                    statistics.median(
                        f["vblank_count_since_prev_display_request"]
                        for f in batch["frames"]),
                ))
            all_frames = [f for b in batches for f in b["frames"]]
            section_summary = {
                key: summarize([f["sections"][key] for f in all_frames])
                for key in SECTION_KEYS
            }
            results[fixture_kind] = {
                "batches": batches,
                "warmup_vblank_counts_by_batch": [
                    b["warmup_vblank_counts"] for b in batches
                ],
                "sections": section_summary,
                "total_frame_ticks": summarize(
                    [f["total_frame_ticks"] for f in all_frames]),
                "vblank_count_since_prev_display_request": summarize(
                    [f["vblank_count_since_prev_display_request"]
                     for f in all_frames]),
            }

        evidence["results"] = results
        evidence["status"] = "done"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("done: %s" % args.output)
        return 0
    except Exception as error:
        evidence["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("BLOCKED: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
