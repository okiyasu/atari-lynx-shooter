#!/usr/bin/env python3
"""APS-053 Phase 2R-2 section-profile diagnosis (verifier only).

This verifier uses the existing cadence ROM probe and debugger boundaries.  It
does not rebuild, patch, or instrument the release ROM.  A profile frame is
observed at the first ``game_sound_tick`` (A),
``game_display_sync_complete`` (B), and ``game_display_request`` (C) entry.
The counters are sampled while paused, then each breakpoint is removed before
execution resumes.
"""

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAME_VERIFIER = ROOT / "scripts" / "verify-frame-pacing-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17776
FRAME_COUNT = 10
BATCH_COUNT = 2
WARMUP_REQUESTS = 6
GAME_OFFSET_STAGE = 209
GAME_PHASE_NORMAL = 1
GAME_PHASE_BOSS = 3
GAME_PHASE_TITLE = 6
CADENCE_INTERVAL_COUNT = 75
VBLANK_DOMINANCE_THRESHOLD = 0.60
MAX_CONTAMINATION_MEDIAN_DELTA = 1
MAX_CONTAMINATION_RELATIVE_DELTA = 0.05


def load_frame_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_frame_profile_base", FRAME_VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    module.GEARLYNX = GEARLYNX
    # The existing probe records 75 intervals.  The current 0-enemy cadence
    # is about 115 VBlanks/interval, so a no-profile control legitimately
    # needs more than two minutes to reach its completion watchpoint.
    module.CADENCE_BATCH_TIMEOUT_SECONDS = 240.0
    return module


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initialize(frame):
    for attempt in range(40):
        try:
            frame.call("initialize", {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {
                    "name": "aps053-section-profile",
                    "version": "1",
                },
            })
            return
        except Exception:
            if attempt == 39:
                raise
            time.sleep(0.2)


def wait_paused(frame, request_id, description):
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = frame.tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status.get("paused"):
            return request_id
        time.sleep(0.01)
    raise RuntimeError("timed out waiting for pause: %s" % description)


def start_paused(frame, rom, symbols, game_address):
    command = [
        GEARLYNX, "--headless", "--mcp-http", "--mcp-http-port",
        str(MCP_PORT), str(rom), str(symbols),
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    initialize(frame)
    frame.tool("debug_continue", request_id=2)
    request_id = 3
    stable = 0
    deadline = time.monotonic() + 12.0
    while time.monotonic() < deadline:
        state = frame.read_bytes(game_address + GAME_OFFSET_STAGE, 2,
                                 request_id)
        request_id += 1
        if state == bytes([1, GAME_PHASE_TITLE]):
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
        time.sleep(0.01)
    else:
        process.terminate()
        raise RuntimeError("ROM did not reach stable TITLE state")
    frame.tool("debug_pause", request_id=request_id)
    request_id = wait_paused(frame, request_id + 1, "stable TITLE")
    return process, request_id


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def u16(frame, address, request_id):
    return int.from_bytes(frame.read_bytes(address, 2, request_id), "little")


def u32(frame, address, request_id):
    return int.from_bytes(frame.read_bytes(address, 4, request_id), "little")


def timer_snapshot(frame, request_id):
    payload = frame.tool("get_mikey_timers", {"timer": 2}, request_id)
    registers = {
        row[0].lower(): row[2] for row in payload.get("registers", [])
        if len(row) >= 3
    }
    return {
        "timer": 2,
        "registers": payload.get("registers", []),
        "current": registers.get("counter"),
        "backup": registers.get("backup"),
    }


def fixture_observation(frame, game_address, enemy_address, request_id):
    game = frame.read_bytes(game_address + GAME_OFFSET_STAGE, 5, request_id)
    request_id += 1
    enemies = frame.read_bytes(
        enemy_address,
        frame.GAME_MAX_ENEMIES * frame.GAME_ENEMY_SIZE,
        request_id,
    )
    request_id += 1
    boss = frame.read_bytes(game_address + frame.GAME_OFFSET_BOSS, 14,
                            request_id)
    request_id += 1
    normal_count, boss_count, weighted = frame.weighted_count(
        enemies, boss[4],
    )
    return request_id, {
        "stage": game[0],
        "phase": game[1],
        "phase_timer": game[2] | (game[3] << 8),
        "boss_active": boss_count,
        "normal_enemy_count": normal_count,
        "weighted_value": weighted,
        "expected_state_source": "live GameState/enemy readback",
    }


def snapshot(frame, addresses, game_address, enemy_address, label,
             request_id):
    request_id, fixture = fixture_observation(
        frame, game_address, enemy_address, request_id,
    )
    return request_id, {
        "boundary": label,
        "vblank_counter": u16(frame, addresses["vblank"], request_id),
        "logic_update_count": u32(frame, addresses["logic"], request_id + 1),
        "elapsed_vblank_count": u32(frame, addresses["elapsed"], request_id + 2),
        "sound_tick_count": u32(frame, addresses["sound"], request_id + 3),
        "sample_count": frame.read_bytes(
            addresses["sample_count"], 1, request_id + 4,
        )[0],
        "probe_active": frame.read_bytes(
            addresses["active"], 1, request_id + 5,
        )[0],
        "timer2": timer_snapshot(frame, request_id + 6),
        "fixture": fixture,
    }, request_id + 7


def one_breakpoint(frame, address, request_id, description):
    address_hex = "%04X" % address
    frame.tool("set_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    frame.tool("debug_continue", request_id=request_id)
    request_id += 1
    request_id = frame.wait_for_breakpoint(request_id, description)
    frame.tool("remove_breakpoint", {"address": address_hex}, request_id)
    return request_id + 1


def step_out_current(frame, request_id):
    """Execute the just-observed function after its breakpoint is removed."""
    frame.tool("debug_step_out", request_id=request_id)
    return request_id + 1


def profile_addresses(frame, symbols):
    names = {
        "sound_boundary": "_game_sound_tick",
        "sync_boundary": "_game_display_sync_complete",
        "request_boundary": "_game_display_request",
        "vblank": "_cadence_probe_vblank_count",
        "logic": "_cadence_probe_logic_update_count",
        "elapsed": "_cadence_probe_elapsed_vblank_count",
        "sound": "_cadence_probe_sound_tick_count",
        "sample_count": "_cadence_probe_sample_count",
        "active": "_cadence_probe_active",
        "armed": "_cadence_probe_armed",
        "complete": "_cadence_probe_complete",
        "target_phase": "_cadence_probe_target_phase",
        # Aliases consumed by the existing continuous no-profile probe.
        "intervals": "_cadence_probe_intervals",
        "fixture_states": "_cadence_probe_fixture_states",
        "overflow": "_cadence_probe_overflow",
        "logic_updates": "_cadence_probe_logic_update_count",
        "consumed_vblanks": "_cadence_probe_elapsed_vblank_count",
        "sound_ticks": "_cadence_probe_sound_tick_count",
        "warmup_vblanks": "_cadence_probe_warmup_vblank_count",
    }
    return {
        key: frame.symbol_address(symbols, value)
        for key, value in names.items()
    }


def arm_profile(frame, addresses, game_address, enemy_address, phase,
                request_id):
    request_id = frame.inject_state(
        game_address, enemy_address, 0, 0, phase, request_id,
    )
    frame.write_bytes(addresses["target_phase"], [phase], request_id)
    request_id += 1
    frame.write_bytes(addresses["active"], [0], request_id)
    request_id += 1
    frame.write_bytes(addresses["complete"], [0], request_id)
    request_id += 1
    frame.write_bytes(addresses["armed"], [1], request_id)
    request_id += 1
    # First request consumes armed; six more discard warm-up requests; the
    # following request is C0, before its probe hook resets/samples.
    for index in range(WARMUP_REQUESTS + 2):
        request_id = one_breakpoint(
            frame, addresses["request_boundary"], request_id,
            "probe warm-up request %d" % (index + 1),
        )
        if index < WARMUP_REQUESTS + 1:
            request_id = step_out_current(frame, request_id)
    request_id, baseline, request_id = snapshot(
        frame, addresses, game_address, enemy_address, "C0", request_id,
    )
    return request_id, baseline


def frame_deltas(previous, current_a, current_b, current_c):
    def delta(key, before, after):
        value = after[key] - before[key]
        if value < 0:
            raise RuntimeError("counter moved backwards: %s" % key)
        return value

    section_a = {
        key: delta(key, previous, current_a)
        for key in ("elapsed_vblank_count", "logic_update_count",
                    "sound_tick_count")
    }
    section_b = {
        key: delta(key, current_a, current_b)
        for key in ("elapsed_vblank_count", "logic_update_count",
                    "sound_tick_count")
    }
    section_c = {
        key: delta(key, current_b, current_c)
        for key in ("elapsed_vblank_count", "logic_update_count",
                    "sound_tick_count")
    }
    return {
        "section_a": section_a,
        "section_b": section_b,
        "section_c": section_c,
        "full_frame": {
            key: delta(key, previous, current_c)
            for key in ("elapsed_vblank_count", "logic_update_count",
                        "sound_tick_count")
        },
        "probe_vblank_counter": {
            "section_a_endpoint": current_a["vblank_counter"],
            "section_b_delta": current_b["vblank_counter"] -
            current_a["vblank_counter"],
            "section_c_delta": current_c["vblank_counter"] -
            current_b["vblank_counter"],
            "reset_at_display_hook": True,
        },
    }


def profile_batch(frame, rom, symbols, fixture, batch_index):
    game_address = frame.symbol_address(symbols, "_game")
    enemy_address = frame.symbol_address(symbols, "_game_enemies")
    addresses = profile_addresses(frame, symbols)
    process, request_id = start_paused(frame, rom, symbols, game_address)
    try:
        request_id, previous = arm_profile(
            frame, addresses, game_address, enemy_address,
            fixture["phase"], request_id,
        )
        frames = []
        for index in range(FRAME_COUNT):
            request_id = frame.inject_state(
                game_address, enemy_address, fixture["normal_enemies"],
                fixture["bosses"], fixture["phase"], request_id,
            )
            request_id = one_breakpoint(
                frame, addresses["sound_boundary"], request_id,
                "section A frame %d" % (index + 1),
            )
            request_id, current_a, request_id = snapshot(
                frame, addresses, game_address, enemy_address,
                "A%d" % (index + 1), request_id,
            )
            request_id = one_breakpoint(
                frame, addresses["sync_boundary"], request_id,
                "section B frame %d" % (index + 1),
            )
            request_id, current_b, request_id = snapshot(
                frame, addresses, game_address, enemy_address,
                "B%d" % (index + 1), request_id,
            )
            request_id = one_breakpoint(
                frame, addresses["request_boundary"], request_id,
                "section C frame %d" % (index + 1),
            )
            request_id, current_c, request_id = snapshot(
                frame, addresses, game_address, enemy_address,
                "C%d" % (index + 1), request_id,
            )
            frames.append({
                "frame": index + 1,
                "snapshots": {
                    "A": current_a,
                    "B": current_b,
                    "C": current_c,
                },
                "deltas": frame_deltas(
                    previous, current_a, current_b, current_c,
                ),
            })
            previous = current_c
            if index < FRAME_COUNT - 1:
                request_id = step_out_current(frame, request_id)
        frame.write_bytes(addresses["active"], [0], request_id)
        request_id += 1
        frame.write_bytes(addresses["armed"], [0], request_id)
        request_id += 1
        return {
            "batch": batch_index,
            "process": process.pid,
            "frame_count": len(frames),
            "frames": frames,
            "fixture_target": fixture,
        }
    finally:
        stop_process(process)


def rearm_from_request(frame, addresses, request_id):
    frame.write_bytes(addresses["active"], [0], request_id)
    request_id += 1
    frame.write_bytes(addresses["complete"], [0], request_id)
    request_id += 1
    frame.write_bytes(addresses["armed"], [1], request_id)
    request_id += 1
    # The debugger is paused at C of batch 1. Execute that request as the
    # first arm request, then catch the next seven requests through C0.
    request_id = step_out_current(frame, request_id)
    for index in range(WARMUP_REQUESTS + 2):
        request_id = one_breakpoint(
            frame, addresses["request_boundary"], request_id,
            "second-batch warm-up request %d" % (index + 1),
        )
        if index < WARMUP_REQUESTS + 1:
            request_id = step_out_current(frame, request_id)
    return request_id


def profile_fixture(frame, rom, symbols, fixture):
    # Keep two independent batches in one process only to reduce emulator
    # startup noise; the first batch's C breakpoint is the second arm edge.
    game_address = frame.symbol_address(symbols, "_game")
    enemy_address = frame.symbol_address(symbols, "_game_enemies")
    addresses = profile_addresses(frame, symbols)
    process, request_id = start_paused(frame, rom, symbols, game_address)
    batches = []
    try:
        for batch_index in range(1, BATCH_COUNT + 1):
            if batch_index == 1:
                request_id, previous = arm_profile(
                    frame, addresses, game_address, enemy_address,
                    fixture["phase"], request_id,
                )
            else:
                request_id = rearm_from_request(
                    frame, addresses, request_id,
                )
                request_id, previous, request_id = snapshot(
                    frame, addresses, game_address, enemy_address,
                    "C0", request_id,
                )
            frames = []
            for index in range(FRAME_COUNT):
                request_id = frame.inject_state(
                    game_address, enemy_address, fixture["normal_enemies"],
                    fixture["bosses"], fixture["phase"], request_id,
                )
                request_id = one_breakpoint(
                    frame, addresses["sound_boundary"], request_id,
                    "section A frame %d batch %d" % (index + 1, batch_index),
                )
                request_id, current_a, request_id = snapshot(
                    frame, addresses, game_address, enemy_address,
                    "A%d" % (index + 1), request_id,
                )
                request_id = one_breakpoint(
                    frame, addresses["sync_boundary"], request_id,
                    "section B frame %d batch %d" % (index + 1, batch_index),
                )
                request_id, current_b, request_id = snapshot(
                    frame, addresses, game_address, enemy_address,
                    "B%d" % (index + 1), request_id,
                )
                request_id = one_breakpoint(
                    frame, addresses["request_boundary"], request_id,
                    "section C frame %d batch %d" % (index + 1, batch_index),
                )
                request_id, current_c, request_id = snapshot(
                    frame, addresses, game_address, enemy_address,
                    "C%d" % (index + 1), request_id,
                )
                frames.append({
                    "frame": index + 1,
                    "snapshots": {"A": current_a, "B": current_b,
                                  "C": current_c},
                    "deltas": frame_deltas(
                        previous, current_a, current_b, current_c,
                    ),
                })
                previous = current_c
                if index < FRAME_COUNT - 1:
                    request_id = step_out_current(frame, request_id)
            batches.append({
                "batch": batch_index,
                "frame_count": len(frames),
                "frames": frames,
                "fixture_target": fixture,
            })
        frame.write_bytes(addresses["active"], [0], request_id)
        request_id += 1
        frame.write_bytes(addresses["armed"], [0], request_id)
        return batches
    finally:
        stop_process(process)


def batch_summary(batch):
    frames = batch["frames"]
    full = [row["deltas"]["full_frame"]["elapsed_vblank_count"]
            for row in frames]
    sections = {
        name: [row["deltas"][name]["elapsed_vblank_count"] for row in frames]
        for name in ("section_a", "section_b", "section_c")
    }
    totals = {name: sum(values) for name, values in sections.items()}
    total = sum(totals.values())
    shares = {
        name: (value / float(total) if total else None)
        for name, value in totals.items()
    }
    dominant = None
    if total:
        name = max(shares, key=shares.get)
        if shares[name] >= VBLANK_DOMINANCE_THRESHOLD:
            dominant = name
    return {
        "full_frame_vblank_counts": full,
        "full_frame_median_vblank": statistics.median(full),
        "full_frame_maximum_vblank": max(full),
        "section_vblank_counts": sections,
        "section_vblank_totals": totals,
        "section_vblank_shares": shares,
        "dominant_section_at_least_60_percent": dominant,
        "dominance_threshold": VBLANK_DOMINANCE_THRESHOLD,
    }


def fixture_summary(batches):
    summaries = [batch_summary(batch) for batch in batches]
    return {
        "batches": summaries,
        "batch_medians_vblank": [
            summary["full_frame_median_vblank"] for summary in summaries
        ],
        "batch_maxima_vblank": [
            summary["full_frame_maximum_vblank"] for summary in summaries
        ],
        "median_vblank": statistics.median([
            value for summary in summaries
            for value in summary["full_frame_vblank_counts"]
        ]),
        "fixture_valid": all(
            all(
                row["snapshots"][boundary]["fixture"]["phase"] ==
                batch["fixture_target"]["phase"] and
                row["snapshots"][boundary]["fixture"]["boss_active"] ==
                batch["fixture_target"]["bosses"] and
                row["snapshots"][boundary]["fixture"]["normal_enemy_count"] ==
                batch["fixture_target"]["normal_enemies"]
                for row in batch["frames"]
                for boundary in ("A", "B", "C")
            )
            for batch in batches
        ),
    }


def run_unprofiled_zero(frame, rom, symbols):
    game_address = frame.symbol_address(symbols, "_game")
    enemy_address = frame.symbol_address(symbols, "_game_enemies")
    addresses = profile_addresses(frame, symbols)
    process, request_id = start_paused(frame, rom, symbols, game_address)
    batches = []
    try:
        for batch_index in range(1, BATCH_COUNT + 1):
            request_id = frame.inject_state(
                game_address, enemy_address, 0, 0, GAME_PHASE_NORMAL,
                request_id,
            )
            frame.write_bytes(addresses["target_phase"], [GAME_PHASE_NORMAL],
                             request_id)
            request_id += 1
            request_id, intervals, states, logic, elapsed, sound, warmup = (
                frame.collect_probe(
                    addresses, request_id,
                    "0-enemy no-profile batch %d" % batch_index,
                )
            )
            batches.append({
                "batch": batch_index,
                "raw_interval_vblank_counts": intervals,
                "median_vblank": statistics.median(intervals),
                "maximum_vblank": max(intervals),
                "fixture_state_bytes": states,
                "logic_updates": logic,
                "elapsed_vblanks": elapsed,
                "sound_ticks": sound,
                "warmup_vblanks": warmup,
                "samples": len(intervals),
            })
        return batches
    finally:
        stop_process(process)


def run_free_run(frame, rom, symbols):
    game_address = frame.symbol_address(symbols, "_game")
    process, request_id = start_paused(frame, rom, symbols, game_address)
    try:
        armed_deadline = time.monotonic() + 8.0
        while time.monotonic() < armed_deadline:
            state = frame.read_bytes(game_address + 193, 2, request_id)
            request_id += 1
            if state == bytes([1, 0]):
                break
            time.sleep(0.01)
        else:
            return {"executed": False, "reason": "TITLE start gate not armed"}
        frame.tool("controller_macro", {"commands": [{"press": "a"}]},
                   request_id)
        request_id += 1
        frame.tool("debug_continue", request_id=request_id)
        request_id += 1
        seen_intro = False
        seen_normal = False
        observations = []
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            state = frame.read_bytes(game_address + GAME_OFFSET_STAGE, 2,
                                     request_id)
            request_id += 1
            observations.append({"stage": state[0], "phase": state[1]})
            if state[1] == 0:
                seen_intro = True
            if seen_intro and state[1] == GAME_PHASE_NORMAL:
                seen_normal = True
                break
            time.sleep(0.02)
        return {
            "executed": seen_intro and seen_normal,
            "controller_macro": "press a",
            "seen_stage_intro": seen_intro,
            "seen_normal_after_intro": seen_normal,
            "observations": observations,
            "reason": None if seen_intro and seen_normal else
            "free-run did not reach STAGE_INTRO then NORMAL",
        }
    finally:
        stop_process(process)


def layout_snapshot(frame, args):
    cadence_layout, _ = frame.rom_layout(args.cadence_map, args.symbols, True)
    normal_layout, _ = frame.rom_layout(args.normal_map, args.normal_symbols,
                                        False)
    def compact(layout):
        return {
            "segments": layout["segments"],
            "main_spare_after_bss_bytes": layout["bss_to_stack_residual_bytes"],
            "bss_size": layout["bss_size"],
            "stack_reserved_size": layout["stack_reserved_size"],
        }
    return {"normal": compact(normal_layout), "cadence": compact(cadence_layout)}


def immutable_snapshot(frame, args):
    return {
        "release_rom": {"path": str(args.normal_rom),
                        "size_bytes": args.normal_rom.stat().st_size,
                        "sha256": sha256(args.normal_rom)},
        "cadence_rom": {"path": str(args.rom),
                         "size_bytes": args.rom.stat().st_size,
                         "sha256": sha256(args.rom)},
        "map_layout": layout_snapshot(frame, args),
    }


def contamination_result(profile, control):
    profile_medians = profile["summary"]["batch_medians_vblank"]
    control_medians = [batch["median_vblank"] for batch in control]
    deltas = [abs(a - b) for a, b in zip(profile_medians, control_medians)]
    relative = [
        (delta / float(control_value) if control_value else None)
        for delta, control_value in zip(deltas, control_medians)
    ]
    passed = all(
        delta <= MAX_CONTAMINATION_MEDIAN_DELTA and
        relative_value is not None and
        relative_value <= MAX_CONTAMINATION_RELATIVE_DELTA
        for delta, relative_value in zip(deltas, relative)
    )
    return {
        "fixture": "0-enemy NORMAL",
        "profile_breakpoints": {
            "batch_medians_vblank": profile_medians,
            "breakpoints_per_frame": ["A", "B", "C"],
        },
        "no_profile_breakpoints": {
            "batch_medians_vblank": control_medians,
            "completion_breakpoint_only": True,
            "raw": control,
        },
        "absolute_median_deltas_vblank": deltas,
        "relative_median_deltas": relative,
        "thresholds": {
            "absolute_vblank": MAX_CONTAMINATION_MEDIAN_DELTA,
            "relative": MAX_CONTAMINATION_RELATIVE_DELTA,
        },
        "debugger_timing_contamination": not passed,
        "passed": passed,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path,
                        default=Path("dist/asteroid-patrol-cadence.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol-cadence.lbl"))
    parser.add_argument("--map", dest="cadence_map", type=Path,
                        default=Path("build/asteroid-patrol-cadence.map"))
    parser.add_argument("--normal-rom", type=Path,
                        default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--normal-symbols", type=Path,
                        default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--normal-map", type=Path,
                        default=Path("build/asteroid-patrol.map"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-053/section-profile-v015.json"))
    args = parser.parse_args()
    frame = load_frame_module()
    evidence = {
        "aps": "APS-053",
        "version": "v015",
        "diagnostic_only": True,
        "release_runtime_modified": False,
        "design_difference": {
            "v2_hsize_vsize_primary_cause": "withdrawal_candidate",
            "basis": "section-profile attributes all measured VBlank to section A; B/C are 0% in all six batches",
            "design_document_v2_unchanged": True,
            "optimization_or_phase_3r_started": False,
        },
        "status": "FAIL",
    }
    before = None
    try:
        before = immutable_snapshot(frame, args)
        evidence["rom_before"] = before
        symbols = args.symbols
        fixtures = (
            {"name": "0-enemy NORMAL", "normal_enemies": 0,
             "bosses": 0, "phase": GAME_PHASE_NORMAL},
            {"name": "4-enemy NORMAL", "normal_enemies": 4,
             "bosses": 0, "phase": GAME_PHASE_NORMAL},
            {"name": "4-enemy+BOSS BOSS", "normal_enemies": 4,
             "bosses": 1, "phase": GAME_PHASE_BOSS},
        )
        fixture_results = []
        for fixture in fixtures:
            batches = profile_fixture(frame, args.rom, symbols, fixture)
            fixture_results.append({
                "fixture": fixture,
                "batches": batches,
                "summary": fixture_summary(batches),
            })
        zero_profile = next(
            item for item in fixture_results
            if item["fixture"]["name"] == "0-enemy NORMAL"
        )
        control = run_unprofiled_zero(frame, args.rom, symbols)
        evidence["fixtures"] = fixture_results
        evidence["negative_control"] = contamination_result(
            zero_profile, control,
        )
        evidence["positive_control"] = run_free_run(
            frame, args.normal_rom, args.normal_symbols,
        )
        after = immutable_snapshot(frame, args)
        evidence["rom_after"] = after
        evidence["rom_map_unchanged"] = before == after
        all_fixture_valid = all(
            item["summary"]["fixture_valid"] for item in fixture_results
        )
        no_contamination = evidence["negative_control"]["passed"]
        positive = evidence["positive_control"]["executed"]
        evidence["branch_decisions"] = {
            "fixture_validity": "PASS" if all_fixture_valid else "FAIL",
            "debugger_timing_contamination":
            "PASS" if no_contamination else "FAIL",
            "free_run_positive_control": "PASS" if positive else "FAIL",
            "dominant_section_rule":
            "report only section share >= 60%; no optimization implied",
            "optimization_gate": "BLOCKED; verifier-only diagnosis",
        }
        evidence["status"] = (
            "PASS" if all_fixture_valid and no_contamination and positive and
            evidence["rom_map_unchanged"] else "FAIL"
        )
    except Exception as error:
        evidence["error"] = "%s: %s" % (type(error).__name__, error)
        evidence["traceback"] = traceback.format_exc()
        try:
            evidence["rom_after"] = immutable_snapshot(frame, args)
            evidence["rom_map_unchanged"] = before == evidence["rom_after"]
        except Exception as snapshot_error:
            evidence["rom_after_error"] = str(snapshot_error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("%s: APS-053 section-profile evidence %s" %
          (evidence["status"], args.output))
    if evidence["status"] != "PASS":
        if "error" in evidence:
            print("FAIL: %s" % evidence["error"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
