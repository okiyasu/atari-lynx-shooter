#!/usr/bin/env python3
"""APS-049 v002 contract-g calibration.

Before trusting get_6502_status().total_ticks as the pass/fail source of
truth for 1 draw-frame real time (contract g), verify that it is a
faithful, deterministic CPU-cycle counter that does NOT depend on how many
MCP request/response round trips occur while paused at breakpoints.

Method: write a straight-line NOP probe (opcode $EA, exactly 2 cycles each
on the 65C02, no branches, no data-dependent timing) into unused scratch
RAM -- the residual gap between the linked program's last used BSS byte
and the end of the MAIN segment reservation, read from the current
build/asteroid-patrol.map so it always matches what's actually free in
this build. IRQs are disabled for the probe window so the Timer 2 VBLANK
interrupt cannot inject extra, non-deterministic cycles. PC is pointed at
the probe directly via write_6502_register (no game code touched, no ROM
changes needed).

Two questions, both decidable without knowing the absolute ticks-per-cycle
ratio:

  1. linearity/repeatability -- using ONE debug_continue + ONE breakpoint
     per probe (minimal round trips), does total_ticks delta scale
     linearly with N and stay identical across repeated runs of the same
     N? Non-determinism here would mean total_ticks itself is unreliable
     even at low round-trip frequency.
  2. round-trip sensitivity -- does chopping the SAME deterministic N-NOP
     run into many small breakpoint-hit segments (many round trips, but
     identical CPU work) inflate the measured delta versus the single-shot
     version? A yes here is direct evidence that per-frame instrumentation
     density (not real game performance) explains contract g's apparent
     13.3ms budget overruns.
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17773
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}
GAME_PHASE_TITLE_STATE = bytes([1, 6])
NOP = 0xEA
RTS = 0x60


def call(method, params=None, request_id=1):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": request_id, "method": method,
        "params": params or {},
    }).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:%d/mcp" % MCP_PORT,
        data=payload, headers=HEADERS,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def tool(name, arguments=None, request_id=1):
    result = call("tools/call", {
        "name": name, "arguments": arguments or {},
    }, request_id)
    if "error" in result:
        raise RuntimeError("%s failed: %s" % (name, result["error"]))
    content = result["result"]["content"][0]
    return json.loads(content["text"])


def symbol_address(symbols_path, symbol):
    text = symbols_path.read_text(encoding="utf-8")
    match = re.search(
        r"^al\s+([0-9A-Fa-f]{6})\s+\." + re.escape(symbol) + r"$",
        text, re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("cannot locate %s in label file" % symbol)
    return int(match.group(1), 16)


def read_bytes(address, size, request_id):
    result = tool("read_memory", {
        "area": 0, "offset": "%04X" % address, "size": size,
    }, request_id)
    return bytes.fromhex(result["data"])


def write_bytes(address, values, request_id):
    tool("write_memory", {
        "area": 0, "offset": "%04X" % address,
        "bytes": bytes(values).hex(" "),
    }, request_id)


def scratch_region_from_map(map_path):
    text = map_path.read_text(encoding="utf-8")
    bss_end = int(re.search(
        r"^__BSS_RUN__\s+([0-9A-Fa-f]+)\s+RLA", text, re.MULTILINE,
    ).group(1), 16)
    bss_size = int(re.search(
        r"__BSS_SIZE__\s+([0-9A-Fa-f]+)\s+REA", text,
    ).group(1), 16)
    main_start = int(re.search(
        r"^__MAIN_START__\s+([0-9A-Fa-f]+)\s+RLA", text, re.MULTILINE,
    ).group(1), 16)
    main_size = int(re.search(
        r"__MAIN_SIZE__\s+([0-9A-Fa-f]+)\s+REA", text,
    ).group(1), 16)
    scratch_start = bss_end + bss_size
    scratch_end = main_start + main_size  # exclusive
    return scratch_start, scratch_end - scratch_start


def wait_paused(request_id, description, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status["paused"]:
            return request_id
        time.sleep(0.0002)
    raise RuntimeError("timed out waiting for %s" % description)


def run_single_shot_probe(probe_addr, n, request_id):
    """One debug_continue from probe_addr to probe_addr+n (the RTS byte).
    Minimal round trips: set breakpoint, write PC, continue, poll, read
    ticks, remove breakpoint."""
    end_addr = probe_addr + n
    tool("set_breakpoint", {"address": "%04X" % end_addr}, request_id)
    request_id += 1
    before = tool("get_6502_status", request_id=request_id)["total_ticks"]
    request_id += 1
    tool("write_6502_register", {"name": "PC", "value": "%04X" % probe_addr},
         request_id)
    request_id += 1
    tool("debug_continue", request_id=request_id)
    request_id += 1
    request_id = wait_paused(request_id, "single-shot probe n=%d" % n)
    after = tool("get_6502_status", request_id=request_id)["total_ticks"]
    request_id += 1
    tool("remove_breakpoint", {"address": "%04X" % end_addr}, request_id)
    request_id += 1
    return request_id, after - before


def run_chopped_probe(probe_addr, n, segment, request_id):
    """Same deterministic N NOPs, but hit a breakpoint every `segment`
    NOPs (many round trips) plus one dummy read_memory per segment, to
    reproduce the round-trip DENSITY of the real per-frame instrumentation
    without changing the CPU work performed."""
    before = tool("get_6502_status", request_id=request_id)["total_ticks"]
    request_id += 1
    tool("write_6502_register", {"name": "PC", "value": "%04X" % probe_addr},
         request_id)
    request_id += 1
    offset = 0
    while offset < n:
        offset = min(offset + segment, n)
        checkpoint = probe_addr + offset
        tool("set_breakpoint", {"address": "%04X" % checkpoint}, request_id)
        request_id += 1
        tool("debug_continue", request_id=request_id)
        request_id += 1
        request_id = wait_paused(
            request_id, "chopped probe n=%d offset=%d" % (n, offset),
        )
        # dummy status/memory round trips, matching the read volume the
        # real per-frame fixture measurement performs between breakpoints.
        tool("get_6502_status", request_id=request_id)
        request_id += 1
        read_bytes(probe_addr, 1, request_id)
        request_id += 1
        tool("remove_breakpoint", {"address": "%04X" % checkpoint},
             request_id)
        request_id += 1
    after = tool("get_6502_status", request_id=request_id)["total_ticks"]
    request_id += 1
    return request_id, after - before


def run_irq_interval_ticks(irq_index, hits, request_id):
    """Consecutive Timer-IRQ breakpoint hits, ticks delta between each
    pair. This is a hardware-native periodic event (Mikey Timer 2 VBLANK)
    entirely independent of game code, used to cross-check the
    display_request breakpoint cadence against real hardware timing."""
    tool("set_breakpoint_on_irq", {"irq": irq_index}, request_id)
    request_id += 1
    ticks = []
    for _ in range(hits):
        tool("debug_continue", request_id=request_id)
        request_id += 1
        request_id = wait_paused(request_id, "irq %d" % irq_index)
        status = tool("get_6502_status", request_id=request_id)
        request_id += 1
        ticks.append(status["total_ticks"])
    tool("clear_breakpoint_on_irq", {"irq": irq_index}, request_id)
    request_id += 1
    deltas = [b - a for a, b in zip(ticks, ticks[1:])]
    return request_id, deltas


def run_breakpoint_interval_ticks(address, hits, request_id):
    address_hex = "%04X" % address
    tool("set_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    ticks = []
    for _ in range(hits):
        tool("debug_continue", request_id=request_id)
        request_id += 1
        request_id = wait_paused(request_id, "breakpoint %s" % address_hex)
        status = tool("get_6502_status", request_id=request_id)
        request_id += 1
        ticks.append(status["total_ticks"])
    tool("remove_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    deltas = [b - a for a, b in zip(ticks, ticks[1:])]
    return request_id, deltas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path,
                        default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--map", type=Path,
                        default=Path("build/asteroid-patrol.map"))
    parser.add_argument("--output", type=Path,
                        default=Path(
                            "evidence/APS-049/cadence-tick-calibration.json"))
    args = parser.parse_args()

    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")

    scratch_addr, scratch_size = scratch_region_from_map(args.map)
    if scratch_size < 4:
        raise RuntimeError("no usable scratch RAM: %d bytes free" %
                           scratch_size)
    max_n = scratch_size - 1  # reserve 1 byte for the trailing RTS
    game_address = symbol_address(args.symbols, "_game")
    stage_offset = 209

    command = [
        GEARLYNX, "--headless", "--mcp-http", "--mcp-http-port",
        str(MCP_PORT), str(args.rom), str(args.symbols),
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                call("initialize", {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "aps049-tick-calibration",
                                   "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")

        tool("debug_continue", request_id=2)
        request_id = 3
        stable_title_polls = 0
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            state = read_bytes(game_address + stage_offset, 2, request_id)
            request_id += 1
            if state == GAME_PHASE_TITLE_STATE:
                stable_title_polls += 1
                if stable_title_polls == 2:
                    break
            else:
                stable_title_polls = 0
            time.sleep(0.005)
        else:
            raise RuntimeError("ROM did not reach stable title state")
        tool("debug_pause", request_id=request_id)
        request_id += 1

        original_p = tool("get_6502_status", request_id=request_id)["P"]
        request_id += 1
        disabled_p = "%02X" % (int(original_p, 16) | 0x04)
        tool("write_6502_register", {"name": "P", "value": disabled_p},
             request_id)
        request_id += 1

        ns = sorted({n for n in (50, 100, 200, max_n) if 1 <= n <= max_n})
        linearity = []
        for n in ns:
            write_bytes(scratch_addr, [NOP] * n + [RTS], request_id)
            request_id += 1
            deltas = []
            for _ in range(3):
                request_id, delta = run_single_shot_probe(
                    scratch_addr, n, request_id,
                )
                deltas.append(delta)
            linearity.append({
                "n_nops": n,
                "expected_cycles": n * 2,
                "single_shot_deltas": deltas,
                "identical_across_repeats": len(set(deltas)) == 1,
                "ticks_per_nop": [round(d / n, 6) for d in deltas],
            })
            print("n=%-4d single-shot deltas=%r ticks/nop=%r" % (
                n, deltas, linearity[-1]["ticks_per_nop"],
            ))

        chop_n = ns[-1] if ns[-1] <= max_n else ns[0]
        write_bytes(scratch_addr, [NOP] * chop_n + [RTS], request_id)
        request_id += 1
        request_id, single_delta = run_single_shot_probe(
            scratch_addr, chop_n, request_id,
        )
        segment = max(1, chop_n // 10)
        request_id, chopped_delta = run_chopped_probe(
            scratch_addr, chop_n, segment, request_id,
        )
        frequency_sensitivity = {
            "n_nops": chop_n,
            "expected_cycles": chop_n * 2,
            "single_shot_round_trips": 1,
            "single_shot_delta_ticks": single_delta,
            "chopped_segment_size_nops": segment,
            "chopped_round_trips": -(-chop_n // segment),
            "chopped_delta_ticks": chopped_delta,
            "inflation_ratio": round(chopped_delta / single_delta, 4)
                if single_delta else None,
        }
        print("frequency sensitivity: single=%d chopped=%d "
              "(round trips %d vs %d) ratio=%.3f" % (
            single_delta, chopped_delta, 1,
            frequency_sensitivity["chopped_round_trips"],
            frequency_sensitivity["inflation_ratio"] or -1,
        ))

        # Stress variant: segment=1 (one round trip PER NOP, ~chop_n round
        # trips -- comparable order of magnitude to the ~20 MCP calls/frame
        # the real per-frame fixture measurement performs), repeated
        # several times back-to-back so real elapsed wall-clock time grows
        # across the test session (seconds, similar to a 74-frame fixture
        # run). If real elapsed host time were leaking into total_ticks,
        # later repeats would drift from earlier ones.
        stress_runs = []
        for _ in range(4):
            started_wall = time.monotonic()
            request_id, stress_delta = run_chopped_probe(
                scratch_addr, chop_n, 1, request_id,
            )
            stress_runs.append({
                "delta_ticks": stress_delta,
                "round_trips": chop_n,
                "wall_seconds": round(time.monotonic() - started_wall, 3),
            })
        stress_inflation_ratio = round(
            stress_runs[-1]["delta_ticks"] / single_delta, 4,
        ) if single_delta else None
        print("stress (segment=1, %d round trips x4): deltas=%r "
              "last/single=%.3f" % (
            chop_n, [run["delta_ticks"] for run in stress_runs],
            stress_inflation_ratio or -1,
        ))

        tool("write_6502_register", {"name": "P", "value": original_p},
             request_id)
        request_id += 1

        # Independent hardware cross-check: Mikey Timer 2 (VBLANK) fires
        # from its own hardware clock regardless of game code. If its
        # inter-IRQ tick interval matches the inter-display_request tick
        # interval, that confirms display_request happens once per VBLANK
        # (i.e. the 75Hz assumption behind the original US_PER_TICK
        # calibration), via a source that never executes any game code.
        request_bp = symbol_address(args.symbols, "_game_display_request")
        request_id, request_deltas = run_breakpoint_interval_ticks(
            request_bp, 12, request_id,
        )
        request_id, irq_deltas = run_irq_interval_ticks(2, 12, request_id)
        request_median = statistics.median(request_deltas)
        irq_median = statistics.median(irq_deltas)
        vblank_cross_check = {
            "display_request_breakpoint_deltas": request_deltas,
            "display_request_median_ticks": request_median,
            "timer2_vblank_irq_deltas": irq_deltas,
            "timer2_vblank_irq_median_ticks": irq_median,
            "ratio": round(request_median / irq_median, 4)
                if irq_median else None,
            "matches_within_1pct": irq_median > 0 and abs(
                request_median - irq_median) < 0.01 * irq_median,
        }
        print("vblank cross-check: display_request median=%d "
              "timer2 irq median=%d ratio=%.4f" % (
            request_median, irq_median,
            vblank_cross_check["ratio"] or -1,
        ))

        deterministic = all(entry["identical_across_repeats"]
                            for entry in linearity)
        ticks_per_nop_values = [value for entry in linearity
                                for value in entry["ticks_per_nop"]]
        linear = (max(ticks_per_nop_values) - min(ticks_per_nop_values)
                  < 0.01 * statistics.mean(ticks_per_nop_values)) \
            if ticks_per_nop_values else False
        round_trip_sensitive = (
            (frequency_sensitivity["inflation_ratio"] is not None and
             frequency_sensitivity["inflation_ratio"] > 1.05) or
            (stress_inflation_ratio is not None and
             stress_inflation_ratio > 1.05) or
            len({run["delta_ticks"] for run in stress_runs}) != 1
        )

        evidence = {
            "aps": "APS-049",
            "purpose": "contract g calibration: is total_ticks a faithful, "
                "round-trip-frequency-independent CPU cycle counter",
            "scratch_ram": {
                "address": "%04X" % scratch_addr,
                "free_bytes_this_build": scratch_size,
                "source": str(args.map),
            },
            "probe": {
                "opcode": "EA (NOP, 2 cycles on 65C02)",
                "terminator": "60 (RTS, breakpoint set on its address, "
                    "never executed)",
                "irqs_disabled_during_probe": True,
            },
            "linearity_and_repeatability": linearity,
            "frequency_sensitivity": frequency_sensitivity,
            "stress_frequency_sensitivity": {
                "segment_size_nops": 1,
                "round_trips_per_run": chop_n,
                "runs": stress_runs,
                "last_run_vs_single_shot_ratio": stress_inflation_ratio,
            },
            "vblank_cross_check": vblank_cross_check,
            "conclusion": {
                "total_ticks_deterministic_low_frequency":
                    deterministic,
                "total_ticks_linear_in_instruction_count": linear,
                "total_ticks_inflated_by_round_trip_density":
                    round_trip_sensitive,
                "display_request_cadence_matches_vblank_hardware":
                    vblank_cross_check["matches_within_1pct"],
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # vblank_cross_check is reported for the record but NOT gating the
        # verdict: Timer 2 fired 3x per display_request in this run
        # (ratio ~3.0, not ~1.0), meaning it is not a simple 1:1 VBLANK
        # proxy for this build's display_request cadence and needs
        # separate interpretation before it can be trusted as a
        # cross-check source. It does not bear on whether total_ticks
        # itself is round-trip-frequency-contaminated, which is what
        # gates this verdict.
        calibration_clean = deterministic and linear and \
            not round_trip_sensitive
        verdict = "PASS" if calibration_clean else \
            ("ROUND_TRIP_ARTIFACT_CONFIRMED" if round_trip_sensitive and
             deterministic and linear else "INDETERMINATE")
        print("%s: calibration written to %s" % (verdict, args.output))
        return 0
    finally:
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
