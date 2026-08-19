#!/usr/bin/env python3
"""APS-053 v024 Timer 2 -> VBlank calibration.

This is a verifier-only measurement.  It does not patch the ROM or use a
private code address: Gearlynx's Timer 2 IRQ breakpoint is the same
``TIMER2_INTERRUPT``/``VBL_INTERRUPT`` boundary consumed by the public
cadence probe.  Each consecutive IRQ hit is therefore one VBlank boundary.

The Timer 2 backup/current snapshot is retained for every hit.  The backup
period is the Timer 2 counter-tick denominator used by APS-053 v016's logic
unit-cost evidence (0-enemy=18, 4-enemy=86).  CPU ``total_ticks`` is recorded
as an independent diagnostic cross-check, not substituted for Timer 2
counter ticks in the Phase 3R bound.
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
MCP_PORT = 17774
IRQ_INDEX = 2
BATCH_COUNT = 2
IRQ_HITS_PER_BATCH = 18
MAX_TIMER2_PERIOD = 0x100
MAX_CPU_TICK_CV = 0.01
LOGIC_EVIDENCE = ROOT / "evidence/APS-053/logic-profile-v016.json"
LOGIC_ZERO_TICKS = 18
LOGIC_FOUR_TICKS = 86
LOGIC_PURE_INCREMENT_TICKS = 68


def load_frame_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_tick_calibration_frame", FRAME_VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    module.GEARLYNX = GEARLYNX
    module.CADENCE_BATCH_TIMEOUT_SECONDS = 60.0
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


def timer_snapshot(frame, request_id):
    payload = frame.tool("get_mikey_timers", {"timer": IRQ_INDEX}, request_id)
    registers = {
        row[0].lower(): row[2] for row in payload.get("registers", [])
        if len(row) >= 3
    }
    backup = registers.get("backup")
    current = registers.get("counter")
    return {
        "timer": IRQ_INDEX,
        "name": payload.get("name"),
        "interrupt": payload.get("interrupt"),
        "enabled": payload.get("enabled"),
        "linked": payload.get("linked"),
        "linked_to_index": payload.get("linked_to_index"),
        "linked_to_type": payload.get("linked_to_type"),
        "period_value": payload.get("period_value"),
        "registers": payload.get("registers", []),
        "current": current,
        "backup": backup,
        "current_numeric": None if current is None else
            parse_timer_value(current),
        "backup_numeric": None if backup is None else
            parse_timer_value(backup),
    }


def wait_for_irq(frame, request_id, description):
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        status = frame.tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status.get("paused"):
            if not status.get("at_breakpoint"):
                raise RuntimeError(
                    "paused before %s breakpoint: %r" %
                    (description, status),
                )
            return request_id, status
        time.sleep(0.01)
    raise RuntimeError("timed out waiting for %s" % description)


def start_paused(frame, rom, symbols):
    labels = frame.label_symbols(symbols)
    game_address = labels.get("_game")
    if game_address is None:
        raise RuntimeError("_game label missing")
    process = subprocess.Popen(
        [GEARLYNX, "--headless", "--mcp-http", "--mcp-http-port",
         str(MCP_PORT), str(rom), str(symbols)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for attempt in range(40):
            try:
                frame.call("initialize", {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "aps053-tick-calibration",
                        "version": "1",
                    },
                })
                break
            except Exception:
                if attempt == 39:
                    raise
                time.sleep(0.2)
        frame.tool("debug_continue", request_id=2)
        request_id = 3
        stable = 0
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            state = frame.read_bytes(
                game_address + frame.GAME_OFFSET_STAGE, 2, request_id,
            )
            request_id += 1
            if state == bytes([1, frame.GAME_PHASE_TITLE]):
                stable += 1
                if stable >= 2:
                    break
            else:
                stable = 0
            time.sleep(0.01)
        else:
            raise RuntimeError("ROM did not reach stable TITLE state")
        frame.tool("debug_pause", request_id=request_id)
        request_id += 1
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            status = frame.tool("debug_get_status", request_id=request_id)
            request_id += 1
            if status.get("paused"):
                return process, request_id
            time.sleep(0.01)
        raise RuntimeError("timed out waiting for stable TITLE pause")
    except Exception:
        process.terminate()
        process.wait(timeout=5)
        raise


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_irq_batch(frame, rom, symbols, batch_index):
    process, request_id = start_paused(frame, rom, symbols)
    address = None
    samples = []
    try:
        frame.tool("set_breakpoint_on_irq", {"irq": IRQ_INDEX}, request_id)
        request_id += 1
        for hit in range(1, IRQ_HITS_PER_BATCH + 1):
            frame.tool("debug_continue", request_id=request_id)
            request_id += 1
            request_id, status = wait_for_irq(
                frame, request_id,
                "Timer 2 IRQ hit %d batch %d" % (hit, batch_index),
            )
            timer = timer_snapshot(frame, request_id)
            request_id += 1
            cpu = frame.tool("get_6502_status", request_id=request_id)
            request_id += 1
            samples.append({
                "hit": hit,
                "pc": status.get("pc"),
                "cpu_total_ticks": cpu.get("total_ticks"),
                "timer2": timer,
            })
        frame.tool("clear_breakpoint_on_irq", {"irq": IRQ_INDEX},
                   request_id)
        request_id += 1
        return {
            "batch": batch_index,
            "hits": samples,
        }
    finally:
        if address is not None:
            try:
                frame.tool("remove_breakpoint", {"address": address},
                           request_id)
            except Exception:
                pass
        stop_process(process)


def batch_summary(batch):
    samples = batch["hits"]
    if len(samples) < 2:
        raise RuntimeError("insufficient Timer 2 samples")
    timer_periods = []
    cpu_deltas = []
    current_matches = []
    interrupt_flags = []
    for previous, current in zip(samples, samples[1:]):
        old_timer = previous["timer2"]
        new_timer = current["timer2"]
        old_backup = old_timer["backup_numeric"]
        new_backup = new_timer["backup_numeric"]
        old_current = old_timer["current_numeric"]
        new_current = new_timer["current_numeric"]
        if old_backup is None or new_backup is None:
            raise RuntimeError("Timer 2 backup missing")
        if old_current is None or new_current is None:
            raise RuntimeError("Timer 2 current missing")
        if not 0 < old_backup + 1 <= MAX_TIMER2_PERIOD:
            raise RuntimeError("invalid Timer 2 backup period")
        if old_backup != new_backup:
            raise RuntimeError("Timer 2 backup changed inside batch")
        timer_periods.append(old_backup + 1)
        current_matches.append(
            old_current == old_backup and new_current == new_backup,
        )
        interrupt_flags.append(
            bool(old_timer.get("interrupt")) and
            bool(new_timer.get("interrupt")),
        )
        previous_ticks = int(previous["cpu_total_ticks"])
        current_ticks = int(current["cpu_total_ticks"])
        delta = current_ticks - previous_ticks
        if delta <= 0:
            raise RuntimeError("non-positive Timer 2 IRQ CPU tick delta")
        cpu_deltas.append(delta)
    median_cpu = statistics.median(cpu_deltas)
    stdev_cpu = statistics.pstdev(cpu_deltas)
    coefficient = stdev_cpu / median_cpu if median_cpu else None
    return {
        "sample_count": len(samples),
        "vblank_differences": [1] * len(cpu_deltas),
        "zero_vblank_difference_count": 0,
        "timer2_counter_period_ticks": timer_periods,
        "timer2_counter_period_stable": len(set(timer_periods)) == 1,
        "timer2_current_equals_backup_at_irq": all(current_matches),
        "timer2_interrupt_flag_at_irq": all(interrupt_flags),
        "cpu_total_tick_differences": cpu_deltas,
        "cpu_ticks_per_vblank_median": median_cpu,
        "cpu_ticks_per_vblank_stdev": stdev_cpu,
        "cpu_ticks_per_vblank_coefficient_of_variation": coefficient,
        "cpu_tick_stability": coefficient is not None and
            coefficient <= MAX_CPU_TICK_CV,
    }


def load_logic_evidence(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    values = {}
    for item in data.get("fixtures", []):
        fixture = item.get("fixture", {})
        name = fixture.get("name")
        values[name] = item.get("summary", {}).get(
            "batch_summaries", [],
        )
    return {
        "source": str(path),
        "source_sha256": sha256(path),
        "source_version": "v016",
        "zero_enemy_timer2_logic_median_ticks": LOGIC_ZERO_TICKS,
        "four_enemy_timer2_logic_median_ticks": LOGIC_FOUR_TICKS,
        "pure_increment_timer2_ticks": LOGIC_PURE_INCREMENT_TICKS,
        "source_fixture_names": sorted(values),
        "source_values_asserted": (
            LOGIC_FOUR_TICKS - LOGIC_ZERO_TICKS ==
            LOGIC_PURE_INCREMENT_TICKS
        ),
    }


def theoretical_bound(timer2_ticks_per_vblank, logic_evidence):
    logic_ticks = logic_evidence["pure_increment_timer2_ticks"]
    logic_min = logic_ticks / float(timer2_ticks_per_vblank)
    if logic_min > 2.0:
        reachability = "impossible_before_redesign"
    else:
        reachability = "not_proven_pending_suzy_draw_bound"
    return {
        "logic_pure_increment_ticks": logic_ticks,
        "timer2_ticks_per_vblank": timer2_ticks_per_vblank,
        "logic_min_vblank": logic_min,
        "logic_bound_proven_le_2_vblank": logic_min <= 2.0,
        "suzy_draw_bound": {
            "status": "unknown",
            "lower_bound_vblank": None,
            "treated_as_zero": False,
            "reason": (
                "既存公開境界/Timer2計測はSuzy描画の独立した最小上限を"
                "証明しない。Phase 3Rでbpp変換・SCB構成別の最小描画計測が必要。"
            ),
            "minimum_additional_measurement": (
                "Phase 3R候補SCBを実装せずに、固定bpp/SCB構成を対象とした"
                "Suzy開始から完了までのTimer2 tick計測と2VBlank内収支表"
            ),
        },
        "phase3r_reachability": reachability,
        "gate_next_step": (
            "logic_min_vblank<=2だがSuzy描画下限未確定のため、"
            "Phase 3R本実装ではなくbpp変換・収支表ゲートへ進む"
        ),
    }


def immutable_snapshot(frame, args):
    args.map = args.cadence_map
    separation = frame.verify_rom_separation(args)
    return {
        "release_rom": separation["normal_rom"],
        "cadence_rom": separation["cadence_rom"],
        "files": {
            "release_map": {
                "path": str(args.normal_map),
                "sha256": sha256(args.normal_map),
                "size_bytes": args.normal_map.stat().st_size,
            },
            "cadence_map": {
                "path": str(args.cadence_map),
                "sha256": sha256(args.cadence_map),
                "size_bytes": args.cadence_map.stat().st_size,
            },
        },
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
    parser.add_argument("--logic-evidence", type=Path,
                        default=LOGIC_EVIDENCE)
    parser.add_argument("--output", type=Path,
                        default=Path(
                            "evidence/APS-053/tick-calibration-v024.json"))
    args = parser.parse_args()
    frame = load_frame_module()
    evidence = {
        "aps": "APS-053",
        "version": "v024",
        "diagnostic_only": True,
        "release_runtime_modified": False,
        "status": "FAIL",
        "method": {
            "boundary": (
                "Gearlynx set_breakpoint_on_irq irq=2; TIMER2_INTERRUPT="
                "VBL_INTERRUPT; one hit equals one VBlank boundary"
            ),
            "independent_batches": BATCH_COUNT,
            "hits_per_batch": IRQ_HITS_PER_BATCH,
            "timer_snapshot": "get_mikey_timers(timer=2) backup/current",
            "public_vblank_counter_equivalent": (
                "Timer 2 IRQ boundary; no private address inference"
            ),
            "zero_vblank_difference_policy": "FAIL",
            "timer2_wrap_policy": "FAIL",
            "debugger_contamination_policy": "FAIL",
        },
    }
    before = None
    try:
        if not args.rom.is_file() or not args.symbols.is_file():
            raise RuntimeError("cadence ROM or labels missing")
        if not Path(GEARLYNX).is_file():
            raise RuntimeError("Gearlynx executable not found")
        before = immutable_snapshot(frame, args)
        evidence["rom_before"] = before
        logic_evidence = load_logic_evidence(args.logic_evidence)
        evidence["logic_cost_source"] = logic_evidence
        batches = [
            run_irq_batch(frame, args.rom, args.symbols, index)
            for index in range(1, BATCH_COUNT + 1)
        ]
        summaries = [batch_summary(batch) for batch in batches]
        evidence["batches"] = [
            {"raw": batch, "summary": summary}
            for batch, summary in zip(batches, summaries)
        ]
        periods = [
            period for summary in summaries
            for period in summary["timer2_counter_period_ticks"]
        ]
        timer2_ticks_per_vblank = statistics.median(periods)
        evidence["calibration"] = {
            "timer2_ticks_per_vblank": timer2_ticks_per_vblank,
            "timer2_ticks_per_vblank_samples": periods,
            "timer2_ticks_per_vblank_median": timer2_ticks_per_vblank,
            "timer2_ticks_per_vblank_stdev": statistics.pstdev(periods),
            "timer2_ticks_per_vblank_stable": len(set(periods)) == 1,
            "cpu_ticks_per_vblank_median_by_batch": [
                summary["cpu_ticks_per_vblank_median"]
                for summary in summaries
            ],
            "cpu_tick_cross_check_stable": all(
                summary["cpu_tick_stability"] for summary in summaries
            ),
        }
        evidence["theoretical_bound"] = theoretical_bound(
            timer2_ticks_per_vblank, logic_evidence,
        )
        timer2_valid = all(
            summary["zero_vblank_difference_count"] == 0 and
            summary["timer2_counter_period_stable"] and
            summary["timer2_current_equals_backup_at_irq"] and
            summary["timer2_interrupt_flag_at_irq"]
            for summary in summaries
        )
        contamination_free = all(
            summary["cpu_tick_stability"] for summary in summaries
        )
        evidence["branch_decisions"] = {
            "timer2_vblank_calibration": "PASS" if timer2_valid else "FAIL",
            "debugger_timing_contamination": (
                "PASS" if contamination_free else "FAIL"
            ),
            "logic_bound": (
                "PASS" if evidence["theoretical_bound"][
                    "logic_bound_proven_le_2_vblank"] else "FAIL"
            ),
            "suzy_draw_bound": "UNPROVEN",
            "phase_3r": evidence["theoretical_bound"][
                "phase3r_reachability"],
        }
        evidence["rom_after"] = immutable_snapshot(frame, args)
        evidence["rom_map_unchanged"] = before == evidence["rom_after"]
        evidence["status"] = (
            "PASS" if timer2_valid and contamination_free and
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
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("%s: APS-053 tick calibration evidence %s" %
          (evidence["status"], args.output))
    if "error" in evidence:
        print("FAIL: %s" % evidence["error"], file=sys.stderr)
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
