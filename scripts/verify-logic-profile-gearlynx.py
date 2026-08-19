#!/usr/bin/env python3
"""APS-053 v016 catch-up logic unit-cost and path attribution verifier.

This is a verifier-only diagnostic.  It runs the existing cadence ROM and
observes consecutive ``_game_update_logic`` entries.  Each breakpoint is
removed before the current call is stepped out; the next breakpoint is then
installed for the next entry.  No ROM-internal instrumentation or source
change is made by this script.
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
SECTION_VERIFIER = ROOT / "scripts" / "verify-section-profile-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17778
LOGIC_UPDATE_COUNT = 10
BATCH_COUNT = 2
GAME_PHASE_NORMAL = 1
GAME_PHASE_BOSS = 3
MAX_TIMER2_DELTA = 0x100


def load_frame_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_logic_profile_base", FRAME_VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    module.GEARLYNX = GEARLYNX
    module.CADENCE_BATCH_TIMEOUT_SECONDS = 240.0
    return module


def load_section_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_section_profile_v015", SECTION_VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    module.GEARLYNX = GEARLYNX
    return module


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_timer_value(value):
    if isinstance(value, int):
        return value
    text = str(value)
    try:
        return int(text, 16)
    except ValueError:
        return int(text, 10)


def timer_current(timer):
    current = timer.get("current")
    return None if current is None else parse_timer_value(current)


def timer_backup(timer):
    backup = timer.get("backup")
    return None if backup is None else parse_timer_value(backup)


def timer2_upcounter_delta(previous, current, backup):
    if previous is None or current is None or backup is None:
        return None
    modulus = backup + 1
    if modulus <= 0 or modulus > MAX_TIMER2_DELTA:
        return None
    return (current - previous) % modulus


def start_paused(frame, rom, symbols, game_address):
    command = [
        GEARLYNX, "--headless", "--mcp-http", "--mcp-http-port",
        str(MCP_PORT), str(rom), str(symbols),
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for attempt in range(40):
        try:
            frame.call("initialize", {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {
                    "name": "aps053-logic-profile", "version": "1",
                },
            })
            break
        except Exception:
            if attempt == 39:
                process.terminate()
                raise
            time.sleep(0.2)
    frame.tool("debug_continue", request_id=2)
    request_id = 3
    stable = 0
    deadline = time.monotonic() + 12.0
    while time.monotonic() < deadline:
        state = frame.read_bytes(game_address + frame.GAME_OFFSET_STAGE, 2,
                                 request_id)
        request_id += 1
        if state == bytes([1, frame.GAME_PHASE_TITLE]):
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
    request_id += 1
    request_id = wait_paused(frame, request_id, "stable TITLE")
    return process, request_id


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_paused(frame, request_id, description):
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = frame.tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status.get("paused"):
            return request_id
        time.sleep(0.01)
    raise RuntimeError("timed out waiting for pause: %s" % description)


def step_out_current(frame, request_id):
    frame.tool("debug_step_out", request_id=request_id)
    return request_id + 1


def finish_logic_probe_callback(frame, address, request_id):
    address_hex = "%04X" % address
    frame.tool("set_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    frame.tool("debug_continue", request_id=request_id)
    request_id += 1
    request_id = frame.wait_for_breakpoint(
        request_id, "cadence logic probe callback",
    )
    frame.tool("remove_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    return step_out_current(frame, request_id)


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
    game = frame.read_bytes(game_address + frame.GAME_OFFSET_STAGE, 5,
                            request_id)
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


def profile_addresses(frame, symbols):
    names = {
        "logic_entry": "_game_update_logic",
        "logic_probe": "_cadence_probe_logic_update",
        "logic_counter": "_cadence_probe_logic_update_count",
        "vblank_counter": "_cadence_probe_vblank_count",
        "elapsed_counter": "_cadence_probe_elapsed_vblank_count",
        "sound_counter": "_cadence_probe_sound_tick_count",
        "active": "_cadence_probe_active",
        "target_phase": "_cadence_probe_target_phase",
        "armed": "_cadence_probe_armed",
        "complete": "_cadence_probe_complete",
    }
    return {
        key: frame.symbol_address(symbols, value)
        for key, value in names.items()
    }


def reset_probe(frame, addresses, phase, request_id):
    frame.write_bytes(addresses["active"], [0], request_id)
    request_id += 1
    for key, size in (("logic_counter", 4), ("vblank_counter", 2),
                      ("elapsed_counter", 4), ("sound_counter", 4)):
        frame.write_bytes(addresses[key], [0] * size, request_id)
        request_id += 1
    frame.write_bytes(addresses["target_phase"], [phase], request_id)
    request_id += 1
    frame.write_bytes(addresses["armed"], [0], request_id)
    request_id += 1
    frame.write_bytes(addresses["complete"], [0], request_id)
    request_id += 1
    frame.write_bytes(addresses["active"], [1], request_id)
    return request_id + 1


def u16(frame, address, request_id):
    return int.from_bytes(frame.read_bytes(address, 2, request_id), "little")


def u32(frame, address, request_id):
    return int.from_bytes(frame.read_bytes(address, 4, request_id), "little")


def hit_snapshot(frame, addresses, game_address, enemy_address, hit_index,
                 request_id):
    request_id, fixture = fixture_observation(
        frame, game_address, enemy_address, request_id,
    )
    timer = timer_snapshot(frame, request_id)
    request_id += 1
    return request_id, {
        "hit": hit_index,
        "logic_update_count": u32(frame, addresses["logic_counter"],
                                   request_id),
        "vblank_counter": u16(frame, addresses["vblank_counter"],
                               request_id + 1),
        "elapsed_vblank_count": u32(frame, addresses["elapsed_counter"],
                                     request_id + 2),
        "sound_tick_count": u32(frame, addresses["sound_counter"],
                                 request_id + 3),
        "timer2": timer,
        "timer2_current_numeric": timer_current(timer),
        "timer2_backup_numeric": timer_backup(timer),
        "fixture": fixture,
    }, request_id + 4


def fixture_valid(row, fixture):
    state = row["fixture"]
    return (
        state["phase"] == fixture["phase"] and
        state["boss_active"] == fixture["bosses"] and
        state["normal_enemy_count"] == fixture["normal_enemies"]
    )


def pair_deltas(rows):
    pairs = []
    for previous, current in zip(rows, rows[1:]):
        logic_delta = current["logic_update_count"] - \
            previous["logic_update_count"]
        vblank_delta = (current["vblank_counter"] -
                        previous["vblank_counter"]) & 0xFFFF
        timer_delta = timer2_upcounter_delta(
            previous["timer2_current_numeric"],
            current["timer2_current_numeric"],
            current["timer2_backup_numeric"],
        )
        probe_reset = current["vblank_counter"] < previous["vblank_counter"]
        pairs.append({
            "from_hit": previous["hit"],
            "to_hit": current["hit"],
            "logic_update_delta": logic_delta,
            "probe_vblank_delta": None if probe_reset else vblank_delta,
            "probe_vblank_counter_reset": probe_reset,
            "probe_elapsed_vblank_delta": current["elapsed_vblank_count"] -
            previous["elapsed_vblank_count"],
            "timer2_current_delta_upcounter_ticks": timer_delta,
        })
    return pairs


def run_logic_batch(frame, rom, symbols, fixture, batch_index):
    game_address = frame.symbol_address(symbols, "_game")
    enemy_address = frame.symbol_address(symbols, "_game_enemies")
    addresses = profile_addresses(frame, symbols)
    process, request_id = start_paused(frame, rom, symbols, game_address)
    rows = []
    try:
        request_id = reset_probe(frame, addresses, fixture["phase"],
                                 request_id)
        for hit_index in range(1, LOGIC_UPDATE_COUNT + 1):
            request_id = frame.inject_state(
                game_address, enemy_address, fixture["normal_enemies"],
                fixture["bosses"], fixture["phase"], request_id,
            )
            address_hex = "%04X" % addresses["logic_entry"]
            frame.tool("set_breakpoint", {"address": address_hex},
                        request_id)
            request_id += 1
            frame.tool("debug_continue", request_id=request_id)
            request_id += 1
            request_id = frame.wait_for_breakpoint(
                request_id, "logic update %d batch %d" %
                (hit_index, batch_index),
            )
            request_id, row, request_id = hit_snapshot(
                frame, addresses, game_address, enemy_address, hit_index,
                request_id,
            )
            frame.tool("remove_breakpoint", {"address": address_hex},
                       request_id)
            request_id += 1
            rows.append(row)
            if hit_index < LOGIC_UPDATE_COUNT:
                request_id = step_out_current(frame, request_id)
        request_id = step_out_current(frame, request_id)
        request_id = finish_logic_probe_callback(
            frame, addresses["logic_probe"], request_id,
        )
        completed_count = u32(frame, addresses["logic_counter"], request_id)
        request_id += 1
        pairs = pair_deltas(rows)
        return {
            "batch": batch_index,
            "hit_count": len(rows),
            "rows": rows,
            "pair_deltas": pairs,
            "completed_probe_logic_updates": completed_count,
            "fixture_valid": all(fixture_valid(row, fixture) for row in rows),
            "logic_delta_all_one": all(
                pair["logic_update_delta"] == 1 for pair in pairs
            ),
        }
    finally:
        try:
            frame.write_bytes(addresses["active"], [0], request_id)
        except Exception:
            pass
        stop_process(process)


def batch_unit_summary(batch):
    pairs = batch["pair_deltas"]
    vblank = [pair["probe_vblank_delta"] for pair in pairs
              if pair["probe_vblank_delta"] is not None]
    elapsed = [pair["probe_elapsed_vblank_delta"] for pair in pairs]
    timer = [pair["timer2_current_delta_upcounter_ticks"]
             for pair in pairs
             if pair["timer2_current_delta_upcounter_ticks"] is not None]
    return {
        "pair_count": len(pairs),
        "logic_update_delta_values": [
            pair["logic_update_delta"] for pair in pairs
        ],
        "probe_vblank_counter_delta_values": vblank,
        "probe_vblank_counter_reset_count": sum(
            pair["probe_vblank_counter_reset"] for pair in pairs
        ),
        "probe_vblank_counter_delta_median": statistics.median(vblank)
        if vblank else None,
        "probe_elapsed_vblank_delta_values": elapsed,
        "probe_elapsed_vblank_delta_median": statistics.median(elapsed),
        "timer2_current_delta_values": timer,
        "timer2_current_delta_median": statistics.median(timer)
        if timer else None,
        "fixture_valid": batch["fixture_valid"],
        "logic_delta_all_one": batch["logic_delta_all_one"],
        "completed_probe_logic_updates": batch[
            "completed_probe_logic_updates"
        ],
    }


def logic_fixture_summary(batches):
    summaries = [batch_unit_summary(batch) for batch in batches]
    all_vblank = [value for summary in summaries
                  for value in summary["probe_vblank_counter_delta_values"]]
    return {
        "batch_summaries": summaries,
        "logic_update_count_per_batch": [batch["hit_count"]
                                          for batch in batches],
        "median_probe_vblank_counter_per_logic_update": statistics.median(
            all_vblank
        ) if all_vblank else None,
        "fixture_valid": all(summary["fixture_valid"] for summary in summaries),
        "logic_delta_all_one": all(
            summary["logic_delta_all_one"] for summary in summaries
        ),
    }


def run_section_negative_control(section, args):
    frame = section.load_frame_module()
    section.FRAME_COUNT = 10
    fixture = {"name": "0-enemy NORMAL", "normal_enemies": 0,
               "bosses": 0, "phase": section.GAME_PHASE_NORMAL}
    process_batches = section.profile_fixture(
        frame, args.rom, args.symbols, fixture,
    )
    profile = section.fixture_summary(process_batches)
    control = section.run_unprofiled_zero(frame, args.rom, args.symbols)
    deltas = [abs(a - b) for a, b in zip(
        profile["batch_medians_vblank"],
        [batch["median_vblank"] for batch in control],
    )]
    control_medians = [batch["median_vblank"] for batch in control]
    relatives = [delta / float(value) for delta, value in zip(
        deltas, control_medians,
    )]
    passed = all(delta <= 1 and relative <= 0.05
                 for delta, relative in zip(deltas, relatives))
    return {
        "fixture": fixture,
        "profile_breakpoints": {
            "batch_medians_vblank": profile["batch_medians_vblank"],
            "batch_maxima_vblank": profile["batch_maxima_vblank"],
            "breakpoints_per_frame": ["A", "B", "C"],
            "raw": process_batches,
        },
        "no_profile_breakpoints": {
            "batch_medians_vblank": control_medians,
            "completion_breakpoint_only": True,
            "raw": control,
        },
        "absolute_median_deltas_vblank": deltas,
        "relative_median_deltas": relatives,
        "thresholds": {"absolute_vblank": 1, "relative": 0.05},
        "debugger_timing_contamination": not passed,
        "passed": passed,
    }


def path_resolution(frame, symbols):
    labels = frame.label_symbols(symbols)
    return {
        "resolved": {
            name: ("%04X" % labels[name])
            for name in ("_game_update_logic", "_game_sound_tick")
            if name in labels
        },
        "static_internal_boundaries_not_resolved": [
            "update_normal", "update_boss",
        ],
        "static_address_inference_used": False,
        "source_basis": {
            "update_normal": "src/game.c:1278-1400, called by game_update_logic when phase NORMAL",
            "update_boss": "src/game.c:1436-1472, called by game_update_logic otherwise",
            "dispatch": "src/game.c:1585-1594",
        },
    }


def immutable_snapshot(frame, args):
    separation = frame.verify_rom_separation(args)
    return {
        "release_rom": separation["normal_rom"],
        "cadence_rom": separation["cadence_rom"],
        "map_layout": {
            "normal": separation["normal_rom"]["layout"],
            "cadence": separation["cadence_rom"]["layout"],
        },
        "files": {
            "release_map": {"path": str(args.normal_map),
                            "sha256": sha256(args.normal_map),
                            "size_bytes": args.normal_map.stat().st_size},
            "cadence_map": {"path": str(args.cadence_map),
                            "sha256": sha256(args.cadence_map),
                            "size_bytes": args.cadence_map.stat().st_size},
        },
    }


def add_path_attribution(item, fixture):
    path = "update_boss" if fixture["phase"] == GAME_PHASE_BOSS \
        else "update_normal"
    item["path_attribution"] = {
        "selected_path": path,
        "logic_updates": LOGIC_UPDATE_COUNT,
        "path_share": {path: 1.0},
        "basis": "live fixture phase plus src/game.c dispatch; no internal breakpoint",
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
                        default=Path("evidence/APS-053/logic-profile-v016.json"))
    args = parser.parse_args()
    # The shared frame verifier names the cadence map ``map``; retain the
    # explicit argparse destination for this script's public CLI.
    args.map = args.cadence_map
    frame = load_frame_module()
    evidence = {
        "aps": "APS-053",
        "version": "v016",
        "diagnostic_only": True,
        "release_runtime_modified": False,
        "status": "FAIL",
        "method": {
            "target": "_game_update_logic entry",
            "logic_updates_per_fixture_batch": LOGIC_UPDATE_COUNT,
            "batches_per_fixture": BATCH_COUNT,
            "breakpoint_protocol": "set -> hit -> snapshot -> remove -> step_out -> re-arm",
            "timer2_and_probe_delta": True,
        },
    }
    before = None
    try:
        before = immutable_snapshot(frame, args)
        evidence["rom_before"] = before
        evidence["symbol_resolution"] = path_resolution(frame, args.symbols)
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
            batches = [run_logic_batch(
                frame, args.rom, args.symbols, fixture, batch_index,
            ) for batch_index in range(1, BATCH_COUNT + 1)]
            item = {
                "fixture": fixture,
                "batches": batches,
                "summary": logic_fixture_summary(batches),
            }
            add_path_attribution(item, fixture)
            fixture_results.append(item)
        evidence["fixtures"] = fixture_results
        evidence["negative_control"] = run_section_negative_control(
            load_section_module(), args,
        )
        evidence["rom_after"] = immutable_snapshot(frame, args)
        evidence["rom_map_unchanged"] = before == evidence["rom_after"]
        fixture_valid = all(item["summary"]["fixture_valid"]
                            and item["summary"]["logic_delta_all_one"]
                            for item in fixture_results)
        control_pass = evidence["negative_control"]["passed"]
        evidence["branch_decisions"] = {
            "fixture_validity": "PASS" if fixture_valid else "FAIL",
            "logic_unit_cost_recorded": "PASS",
            "internal_path_bisection": "attribution-only; static boundaries absent",
            "debugger_timing_contamination": "PASS" if control_pass else "FAIL",
            "optimization_gate": "BLOCKED; verifier-only diagnosis",
            "phase_3r": "BLOCKED; no repair or threshold change",
        }
        evidence["design_difference"] = {
            "v2_hsize_vsize_primary_cause": "withdrawal_candidate",
            "basis": "logic entry unit-cost and phase-dispatch attribution; no runtime change",
            "design_document_v2_unchanged": True,
        }
        evidence["status"] = (
            "PASS" if fixture_valid and control_pass and
            evidence["rom_map_unchanged"] else "FAIL"
        )
    except Exception as error:
        evidence["error"] = "%s: %s" % (type(error).__name__, error)
        evidence["traceback"] = traceback.format_exc()
        if before is not None:
            try:
                evidence["rom_after"] = immutable_snapshot(frame, args)
                evidence["rom_map_unchanged"] = before == evidence["rom_after"]
            except Exception as snapshot_error:
                evidence["rom_after_error"] = str(snapshot_error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("%s: APS-053 logic-profile evidence %s" %
          (evidence["status"], args.output))
    if "error" in evidence:
        print("FAIL: %s" % evidence["error"], file=sys.stderr)
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
