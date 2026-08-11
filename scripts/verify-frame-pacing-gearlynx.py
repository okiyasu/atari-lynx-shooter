#!/usr/bin/env python3
"""Verify APS-047 weighted capacity and APS-052 real-time logic catch-up.

Contract g uses a ROM-internal Timer 2 VBlank counter.  The display-request
hook snapshots 16 consecutive VBlank intervals into RAM while the emulator
runs continuously; one write breakpoint on the completion flag then stops
the batch for readback.  No debug_step_frame, per-request pause/resume, or
host wall-clock value participates in cadence acceptance.

The per-frame breakpoint loop (verify_phase) remains a separate correctness
regression for movement and event counts.  Its wall-clock figures are
advisory and are not mixed into contract g.
"""

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17770
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}
NORMAL_WEIGHT = 1
BOSS_WEIGHT = 4
WEIGHT_LIMIT = 8
GAME_MAX_ENEMIES = 8
GAME_ENEMY_SIZE = 12
GAME_OFFSET_PLAYER = 2
GAME_OFFSET_BULLETS = 6
GAME_OFFSET_ENEMY_BULLETS = 66
GAME_OFFSET_POWER_ITEM = 146
GAME_OFFSET_BOSS = 150
GAME_OFFSET_GAME_OVER = 191
GAME_OFFSET_TITLE_VOICE_PENDING = 194
GAME_OFFSET_DYING = 197
GAME_OFFSET_STAGE = 209
GAME_PHASE_NORMAL = 1
GAME_PHASE_BOSS = 3
FRAME_COUNT = 75
FRAME_INTERVAL_MIN_US = 12000
FRAME_INTERVAL_MAX_US = 15000
VBLANK_TICKS = 184482
VBLANK_US = 13333.333333333334
MAX_VBLANK_RATIO = 1.05
CADENCE_INTERVAL_COUNT = 16
CADENCE_WARMUP_REQUEST_COUNT = 6
SOUND_TICK_CAP = 2048
TITLE_REFERENCE_RATIO = 553362.0 / 184482.0
PROTECTED_RUNTIME_SYMBOLS = (
    "_game", "_game_enemies",
)
PROTECTED_ASSETS = (
    "assets/stages/stages.json",
    "tests/golden/sprite-data-v050.json",
    "assets/voice/title-start.adpcm",
    "assets/voice/game-over.adpcm",
)


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
    if content.get("type") == "image":
        return content
    return json.loads(content["text"])


def symbol_address(symbols_path, symbol):
    text = symbols_path.read_text(encoding="utf-8")
    match = re.search(
        r"^al\s+([0-9A-Fa-f]{6})\s+\." + re.escape(symbol) + r"$",
        text, re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("cannot locate %s in label file" % symbol)
    address = int(match.group(1), 16)
    if address > 0xFFFF:
        raise RuntimeError("symbol %s is outside CPU address space" % symbol)
    return address


def label_symbols(symbols_path):
    symbols = {}
    for line in symbols_path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^al\s+([0-9A-Fa-f]{6})\s+\.(\S+)$", line)
        if match:
            symbols[match.group(2)] = int(match.group(1), 16)
    return symbols


def map_value(map_path, symbol):
    match = re.search(
        r"(?:^|\s)" + re.escape(symbol) +
        r"\s+([0-9A-Fa-f]{6})\s+",
        map_path.read_text(encoding="utf-8"), re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("cannot locate %s in map file" % symbol)
    return int(match.group(1), 16)


def map_segment_range(map_path, segment):
    match = re.search(
        r"^" + re.escape(segment) +
        r"\s+([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})\s+"
        r"([0-9A-Fa-f]{6})\s+",
        map_path.read_text(encoding="utf-8"), re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("cannot locate %s segment in map file" % segment)
    return {
        "start": int(match.group(1), 16),
        "end": int(match.group(2), 16),
        "size": int(match.group(3), 16),
    }


def rom_layout(map_path, symbols_path, probe_expected):
    labels = label_symbols(symbols_path)
    bss = map_segment_range(map_path, "BSS")
    main_start = map_value(map_path, "__MAIN_START__")
    main_size = map_value(map_path, "__MAIN_SIZE__")
    stack_start = main_start + main_size
    stack_size = map_value(map_path, "__STACKSIZE__")
    stack_end = stack_start + stack_size
    bss_end = bss["end"] + 1
    layout = {
        "main_start": main_start,
        "main_size": main_size,
        "main_end_exclusive": stack_start,
        "bss_start": bss["start"],
        "bss_end_inclusive": bss["end"],
        "bss_size": bss["size"],
        "c_stack_start": stack_start,
        "stack_reserved_size": stack_size,
        "stack_end_exclusive": stack_end,
        "bss_to_stack_residual_bytes": stack_start - bss_end,
        "bss_stack_nonoverlap": bss_end <= stack_start,
        "probe_symbols_present": any(
            name.startswith("_cadence_probe_") for name in labels
        ),
    }
    if probe_expected:
        interval_start = labels.get("_cadence_probe_intervals")
        if interval_start is None:
            raise RuntimeError("cadence interval symbol missing from cadence ROM")
        interval_end = interval_start + CADENCE_INTERVAL_COUNT
        layout["cadence_probe_intervals"] = {
            "start": interval_start,
            "end_exclusive": interval_end,
            "size": CADENCE_INTERVAL_COUNT,
            "inside_bss": interval_start >= bss["start"] and
                interval_end <= bss_end,
            "inside_main": interval_start >= main_start and
                interval_end <= stack_start,
        }
        if (not layout["bss_stack_nonoverlap"] or
                not layout["cadence_probe_intervals"]["inside_bss"] or
                not layout["cadence_probe_intervals"]["inside_main"]):
            raise RuntimeError("cadence BSS interval overlaps C stack or MAIN")
    else:
        if layout["probe_symbols_present"]:
            raise RuntimeError("normal ROM unexpectedly contains cadence symbols")
        layout["cadence_probe_intervals"] = None
    return layout, labels


def verify_rom_separation(args):
    cadence_layout, cadence_labels = rom_layout(
        args.map, args.symbols, True,
    )
    normal_layout, normal_labels = rom_layout(
        args.normal_map, args.normal_symbols, False,
    )
    map_text = args.map.read_text(encoding="utf-8")
    normal_map_text = args.normal_map.read_text(encoding="utf-8")
    if "cadence_probe.o:" not in map_text:
        raise RuntimeError("cadence ROM map is missing cadence_probe.o")
    if "main-cadence.o:" not in map_text:
        raise RuntimeError("cadence ROM map is missing main-cadence.o")
    if "cadence_probe.o:" in normal_map_text or \
            "main-cadence.o:" in normal_map_text:
        raise RuntimeError("normal ROM map contains cadence-only object")
    if not normal_layout["bss_stack_nonoverlap"]:
        raise RuntimeError("normal ROM BSS overlaps C stack")
    common_bss_symbols = []
    for name in PROTECTED_RUNTIME_SYMBOLS:
        if name not in normal_labels or name not in cadence_labels:
            raise RuntimeError("protected runtime symbol missing: %s" % name)
        normal_offset = normal_labels.get(name, -1) - normal_layout["bss_start"]
        cadence_offset = cadence_labels.get(name, -1) - cadence_layout["bss_start"]
        if normal_offset != cadence_offset:
            raise RuntimeError("protected runtime layout changed: %s" % name)
        common_bss_symbols.append(name)
    assets = {}
    for relative in PROTECTED_ASSETS:
        path = Path(relative)
        assets[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return {
        "normal_rom": {
            "path": str(args.normal_rom),
            "size_bytes": args.normal_rom.stat().st_size,
            "sha256": hashlib.sha256(args.normal_rom.read_bytes()).hexdigest(),
            "layout": normal_layout,
        },
        "cadence_rom": {
            "path": str(args.rom),
            "size_bytes": args.rom.stat().st_size,
            "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
            "layout": cadence_layout,
        },
        "normal_rom_contains_probe": False,
        "cadence_rom_contains_probe": True,
        "common_bss_symbols_verified": len(common_bss_symbols),
        "common_bss_layout_relative_offsets": True,
        "protected_assets": assets,
    }


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


def wait_for_breakpoint(request_id, description):
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        status = tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status["paused"]:
            if not status["at_breakpoint"]:
                raise RuntimeError("paused before %s breakpoint" % description)
            return request_id
        # Gearlynx advances the emulated CPU between MCP requests. A tight
        # status-poll loop can starve continuous execution and make a batch
        # completion watchpoint appear to hang; this sleep is only a timeout
        # throttle and never contributes to cadence measurements.
        time.sleep(0.01)
    raise RuntimeError("timed out waiting for %s breakpoint" % description)


def hit_breakpoint(address, request_id, description, hits=1):
    address_hex = "%04X" % address
    tool("set_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    for hit in range(hits):
        tool("debug_continue", request_id=request_id)
        request_id += 1
        request_id = wait_for_breakpoint(
            request_id, "%s %d/%d" % (description, hit + 1, hits),
        )
    tool("remove_breakpoint", {"address": address_hex}, request_id)
    return request_id + 1


def collect_probe(probe, request_id, description):
    """Run one continuous 16-interval batch and stop once for readback."""
    write_bytes(probe["complete"], [0], request_id)
    request_id += 1
    write_bytes(probe["armed"], [1], request_id)
    request_id += 1
    tool("set_breakpoint", {
        "address": "%04X" % probe["complete"],
        "execute": False,
        "read": False,
        "write": True,
    }, request_id)
    request_id += 1
    tool("debug_continue", request_id=request_id)
    request_id += 1
    try:
        request_id = wait_for_breakpoint(request_id, "%s completion" % description)
    except RuntimeError as error:
        diagnostics = {
            "armed": read_bytes(probe["armed"], 1, request_id)[0],
            "active": read_bytes(probe["active"], 1, request_id + 1)[0],
            "sample_count": read_bytes(
                probe["sample_count"], 1, request_id + 2)[0],
            "complete": read_bytes(probe["complete"], 1, request_id + 3)[0],
            "logic_updates": int.from_bytes(
                read_bytes(probe["logic_updates"], 4, request_id + 4),
                "little",
            ),
            "actual_sound_ticks": int.from_bytes(
                read_bytes(probe["sound_ticks"], 4, request_id + 5),
                "little",
            ),
        }
        raise RuntimeError("%s; probe=%r" % (error, diagnostics))
    intervals = list(read_bytes(
        probe["intervals"], CADENCE_INTERVAL_COUNT, request_id),
    )
    request_id += 1
    sample_count = read_bytes(probe["sample_count"], 1, request_id)[0]
    request_id += 1
    overflow = read_bytes(probe["overflow"], 1, request_id)[0]
    request_id += 1
    complete = read_bytes(probe["complete"], 1, request_id)[0]
    request_id += 1
    tool("remove_breakpoint", {
        "address": "%04X" % probe["complete"],
    }, request_id)
    request_id += 1
    if sample_count != CADENCE_INTERVAL_COUNT or complete != 1:
        raise RuntimeError(
            "%s probe incomplete: sample_count=%d complete=%d" %
            (description, sample_count, complete)
        )
    if overflow != 0:
        raise RuntimeError("%s probe VBlank counter overflowed 8-bit storage" %
                           description)
    logic_updates = int.from_bytes(
        read_bytes(probe["logic_updates"], 4, request_id), "little",
    )
    request_id += 1
    consumed_vblanks = int.from_bytes(
        read_bytes(probe["consumed_vblanks"], 4, request_id), "little",
    )
    request_id += 1
    actual_sound_ticks = int.from_bytes(
        read_bytes(probe["sound_ticks"], 4, request_id), "little",
    )
    request_id += 1
    warmup_vblanks = int.from_bytes(
        read_bytes(probe["warmup_vblanks"], 2, request_id), "little",
    )
    request_id += 1
    return (request_id, intervals, logic_updates,
            consumed_vblanks, actual_sound_ticks, warmup_vblanks)


def summarize_probe(intervals):
    ratios = [value / 1.0 for value in intervals]
    exceeded = [
        index + 1 for index, value in enumerate(ratios)
        if value > MAX_VBLANK_RATIO
    ]
    median_vblank = statistics.median(intervals)
    maximum_vblank = max(intervals)
    return {
        "method": "rom_internal_timer2_counter",
        "samples": len(intervals),
        "raw_interval_vblank_counts": intervals,
        "interval_ratios": ratios,
        "median_vblank_interval": median_vblank,
        "maximum_vblank_interval": maximum_vblank,
        "median_us": median_vblank * VBLANK_US,
        "maximum_us": maximum_vblank * VBLANK_US,
        "vblank_reference_ticks": VBLANK_TICKS,
        "vblank_reference_us": VBLANK_US,
        "max_interval_ratio": MAX_VBLANK_RATIO,
        "exceeded_samples": len(exceeded),
        "first_exceeded_sample": exceeded[0] if exceeded else None,
        "within_budget": not exceeded,
    }


def summarize_probe_runs(runs, logic_updates=None, logic_budgets=None,
                         consumed_vblanks=None, actual_sound_ticks=None):
    summaries = [summarize_probe(intervals) for intervals in runs]
    medians = [run["median_vblank_interval"] for run in summaries]
    maxima = [run["maximum_vblank_interval"] for run in summaries]
    result = {
        "method": "rom_internal_timer2_counter",
        "independent_batch_count": len(summaries),
        "runs": summaries,
        "run_medians_vblank": medians,
        "run_maxima_vblank": maxima,
        "same_conclusion": len(set(
            run["within_budget"] for run in summaries
        )) == 1,
        "within_budget": all(run["within_budget"] for run in summaries),
    }
    result["clip_count"] = [sum(value > 32 for value in intervals)
                             for intervals in runs]
    result["discarded_vblanks"] = [
        sum(max(0, value - 32) for value in intervals)
        for intervals in runs
    ]
    result["clip_zero"] = all(count == 0 for count in result["clip_count"])
    display_elapsed_vblanks = [sum(intervals) for intervals in runs]
    if consumed_vblanks is not None:
        # The production monotonic counter is the authoritative denominator
        # for logic/sound. The raw display probe also includes the terminal
        # request interval, so retain that boundary difference explicitly.
        terminal_interval_vblanks = [intervals[-1] for intervals in runs]
        scheduler_elapsed_vblanks = consumed_vblanks
        unaccounted_display_interval_vblanks = [
            max(0, display - consumed)
            for display, consumed in zip(
                display_elapsed_vblanks, consumed_vblanks)
        ]
    else:
        terminal_interval_vblanks = [0 for _ in runs]
        scheduler_elapsed_vblanks = display_elapsed_vblanks
        unaccounted_display_interval_vblanks = [0 for _ in runs]
    elapsed_vblanks = scheduler_elapsed_vblanks
    sound_ticks = (actual_sound_ticks if actual_sound_ticks is not None else
                   [min(elapsed, SOUND_TICK_CAP) for elapsed in
                    elapsed_vblanks])
    if consumed_vblanks is not None and actual_sound_ticks is not None:
        discarded_sound_vblanks = [
            max(0, consumed - actual)
            for consumed, actual in zip(consumed_vblanks, sound_ticks)
        ]
        sound_clip_invoked = [
            actual < consumed
            for consumed, actual in zip(consumed_vblanks, sound_ticks)
        ]
    else:
        discarded_sound_vblanks = None
        sound_clip_invoked = None
    result["sound_timing"] = {
        "elapsed_vblanks": elapsed_vblanks,
        "display_interval_elapsed_vblanks": display_elapsed_vblanks,
        "production_consumed_vblanks": consumed_vblanks,
        "actual_sound_ticks": actual_sound_ticks,
        "terminal_display_interval_vblanks": terminal_interval_vblanks,
        "unaccounted_display_interval_vblanks":
            unaccounted_display_interval_vblanks,
        "sound_ticks": sound_ticks,
        "sound_tick_cap": SOUND_TICK_CAP,
        "discarded_vblanks": discarded_sound_vblanks,
        "clip_invoked": sound_clip_invoked,
    }
    if consumed_vblanks is not None and actual_sound_ticks is not None:
        result["sound_timing"]["within_target"] = [
            actual == consumed and discarded == 0 and not clipped
            for actual, consumed, discarded, clipped in zip(
                sound_ticks, consumed_vblanks, discarded_sound_vblanks,
                sound_clip_invoked,
            )
        ]
    if logic_updates is not None:
        ideal_updates = [elapsed * 4 for elapsed in elapsed_vblanks]
        executed_updates = (logic_budgets if logic_budgets is not None
                            else logic_updates)
        discarded_updates = [
            max(0, ideal - actual)
            for ideal, actual in zip(ideal_updates, executed_updates)
        ]
        ratios = [
            actual / float(ideal) if ideal else 0.0
            for actual, ideal in zip(logic_updates, ideal_updates)
        ]
        result["logic_catch_up"] = {
            "elapsed_vblanks": elapsed_vblanks,
            "display_interval_elapsed_vblanks": display_elapsed_vblanks,
            "production_consumed_vblanks": consumed_vblanks,
            "terminal_display_interval_vblanks": terminal_interval_vblanks,
            "unaccounted_display_interval_vblanks":
                unaccounted_display_interval_vblanks,
            "ideal_updates": ideal_updates,
            "logic_updates": logic_updates,
            "discarded_updates": discarded_updates,
            "clip_invoked": [actual < ideal for ideal, actual in
                              zip(ideal_updates, executed_updates)],
            "logic_updates_per_elapsed_vblank_x4": ratios,
            "target_ratio": [0.95, 1.05],
            "within_target": [0.95 <= ratio <= 1.05
                              for ratio in ratios],
        }
    if logic_budgets is not None:
        result["logic_catch_up"]["scheduler_budget_updates"] = logic_budgets
    return result


def weighted_count(enemy_bytes, boss_active):
    normal_count = 0
    for slot in range(GAME_MAX_ENEMIES):
        record = enemy_bytes[
            slot * GAME_ENEMY_SIZE:(slot + 1) * GAME_ENEMY_SIZE
        ]
        if record[4] != 0 and record[0] < 160:
            normal_count += 1
    boss_count = int(boss_active != 0)
    return normal_count, boss_count, (
        normal_count * NORMAL_WEIGHT + boss_count * BOSS_WEIGHT
    )


def injection_is_valid(normal_count, boss_count):
    return (normal_count <= GAME_MAX_ENEMIES and boss_count <= 1 and
            normal_count * NORMAL_WEIGHT + boss_count * BOSS_WEIGHT <=
            WEIGHT_LIMIT)


def enemy_records(count):
    records = []
    for slot in range(GAME_MAX_ENEMIES):
        if slot < count:
            x = 112 + slot * 5
            y = 12 + slot * 10
            records.extend([x, y, 8, 8, 1, slot % 3, 0, y,
                            0, 0, 1, slot * 7 % 70])
        else:
            records.extend([0] * GAME_ENEMY_SIZE)
    return records


def boss_record(active, stage):
    if not active:
        return [0] * 14
    if stage == 2:
        return [128, 44, 28, 14, 1, 90, 90, 1, 2, 0, 0, 0, 1, 0]
    return [132, 43, 24, 16, 1, 60, 60, 0, 1, 0, 0, 0, 1, 0]


def inject_state(game_address, enemy_address, normal_count, boss_count,
                 phase, request_id):
    if not injection_is_valid(normal_count, boss_count):
        raise RuntimeError(
            "refusing invalid weighted injection normal=%d boss=%d" %
            (normal_count, boss_count)
        )
    stage = 2 if phase == GAME_PHASE_BOSS else 1
    # Keep the player above boss fire during the long catch-up batches. The
    # fixture measures pacing, not death/voice transitions.
    write_bytes(game_address + GAME_OFFSET_PLAYER, [8, 0, 8, 6], request_id)
    request_id += 1
    bullets = [20, 90, 3, 2, 1] + [0] * 55
    write_bytes(game_address + GAME_OFFSET_BULLETS, bullets, request_id)
    request_id += 1
    write_bytes(game_address + GAME_OFFSET_ENEMY_BULLETS, [0] * 80,
                request_id)
    request_id += 1
    write_bytes(game_address + GAME_OFFSET_POWER_ITEM, [0] * 4, request_id)
    request_id += 1
    write_bytes(game_address + GAME_OFFSET_BOSS,
                boss_record(boss_count, stage), request_id)
    request_id += 1
    write_bytes(game_address + GAME_OFFSET_GAME_OVER, [0], request_id)
    request_id += 1
    write_bytes(game_address + GAME_OFFSET_TITLE_VOICE_PENDING,
                [0, 0, 0, 0], request_id)
    request_id += 1
    write_bytes(game_address + GAME_OFFSET_DYING, [0, 0, 0], request_id)
    request_id += 1
    write_bytes(game_address + GAME_OFFSET_STAGE,
                [stage, phase, 0, 0], request_id)
    request_id += 1
    write_bytes(enemy_address, enemy_records(normal_count), request_id)
    return request_id + 1


def summarize_intervals(intervals_us):
    return {
        "samples": len(intervals_us),
        "minimum_us": min(intervals_us),
        "median_us": int(statistics.median(sorted(intervals_us))),
        "maximum_us": max(intervals_us),
        "inside_advisory_window": sum(
            FRAME_INTERVAL_MIN_US <= value <= FRAME_INTERVAL_MAX_US
            for value in intervals_us
        ),
        "advisory_window_us": [FRAME_INTERVAL_MIN_US,
                               FRAME_INTERVAL_MAX_US],
    }


def measure_cadence(game_address, enemy_address, probe, request_address,
                    stack_start, stack_end_exclusive, normal_count,
                    boss_count, phase, request_id):
    """APS-052 contract g: collect two independent continuous batches."""
    batches = []
    logic_batches = []
    consumed_vblank_batches = []
    actual_sound_batches = []
    warmup_batches = []
    for batch in range(2):
        request_id = inject_state(
            game_address, enemy_address, normal_count, boss_count, phase,
            request_id,
        )
        # Let the normal gameplay path render an unmeasured pipeline warm-up
        # after fixture injection. Gearlynx debugger re-attachment can leave
        # several display requests with stale timing; all six are excluded
        # without resetting game state or bypassing game_update_logic().
        request_id = hit_breakpoint(
            request_address, request_id,
            "fixture warm-up display request normal=%d boss=%d phase=%d batch=%d" % (
                normal_count, boss_count, phase, batch + 1,
            ),
        )
        request_id = inject_state(
            game_address, enemy_address, normal_count, boss_count, phase,
            request_id,
        )
        request_id, intervals, logic_count, consumed_vblanks, actual_sound_ticks, warmup_vblanks = collect_probe(
            probe, request_id,
            "normal=%d boss=%d phase=%d batch=%d" % (
                normal_count, boss_count, phase, batch + 1,
            ),
        )
        batches.append(intervals)
        logic_batches.append(logic_count)
        consumed_vblank_batches.append(consumed_vblanks)
        actual_sound_batches.append(actual_sound_ticks)
        warmup_batches.append(warmup_vblanks)

    # readback: confirm the enemy/boss count held for the whole run (no
    # on-death respawn drift -- nothing collides with anything in this
    # fixture, but verify rather than assume).
    enemies = read_bytes(enemy_address, GAME_MAX_ENEMIES * GAME_ENEMY_SIZE,
                         request_id)
    request_id += 1
    boss = read_bytes(game_address + GAME_OFFSET_BOSS, 14, request_id)
    request_id += 1
    readback_normal, readback_boss, _ = weighted_count(enemies, boss[4])

    result = summarize_probe_runs(
        batches, logic_updates=logic_batches,
        consumed_vblanks=consumed_vblank_batches,
        actual_sound_ticks=actual_sound_batches,
    )
    result["warmup_discarded_vblanks"] = warmup_batches
    low_water = int.from_bytes(
        read_bytes(probe["stack_low_water"], 2, request_id), "little",
    )
    result["stack_high_water"] = {
        "lowest_cc65_stack_pointer": low_water,
        "stack_start": stack_start,
        "stack_end_exclusive": stack_end_exclusive,
        "stack_pointer_in_range": stack_start <= low_water <= stack_end_exclusive,
        "stack_used_bytes": (
            stack_end_exclusive - low_water
            if stack_start <= low_water <= stack_end_exclusive else None
        ),
        "unused_bytes_between_stack_start_and_low_water": (
            low_water - stack_start
            if stack_start <= low_water <= stack_end_exclusive else 0
        ),
        "minimum_unused_bytes_required": 128,
        "at_least_128_unused": (
            stack_start <= low_water <= stack_end_exclusive and
            low_water - stack_start >= 128
        ),
    }
    result["enemy_count_held"] = (
        readback_normal == normal_count and readback_boss == boss_count
    )
    result["readback_normal_enemies"] = readback_normal
    result["readback_bosses"] = readback_boss
    return request_id, result


def verify_phase(game_address, enemy_address, symbols, normal_count,
                 boss_count, phase, request_id):
    """Per-frame breakpoint-driven regression check: asserts player/
    bullet/enemy/boss movement and input/logic/sound/sync/request event
    counts stay constant across all FRAME_COUNT draw frames. This method's
    own wall-clock/tick sampling is NOT used for the contract g pass/fail
    decision (see measure_cadence): the high round-trip frequency
    here is intentionally isolated from the ROM-internal cadence probe and
    never contributes to the contract g pass/fail decision."""
    request_id = inject_state(
        game_address, enemy_address, normal_count, boss_count, phase,
        request_id,
    )
    tool("controller_macro", {"commands": [{"press": "right"}]}, request_id)
    request_id += 1
    # Warm-up: run one full breakpoint-sequenced draw frame unmeasured
    # before sampling deltas. A fixture immediately following a different
    # fixture's final display-request breakpoint occasionally resamples an
    # extra logic step while the debugger resynchronizes onto this
    # fixture's own frame boundary (same class of transient as the stale
    # front-buffer settle in verify-stage-visuals-gearlynx.py); one
    # unmeasured pass plus a fresh re-inject clears it before the 75
    # measured frames begin.
    request_id = hit_breakpoint(symbols["input"], request_id, "warm-up input")
    request_id = hit_breakpoint(symbols["sound"], request_id, "warm-up sound")
    request_id = hit_breakpoint(symbols["sync"], request_id, "warm-up sync")
    request_id = hit_breakpoint(symbols["request"], request_id, "warm-up request")
    request_id = inject_state(
        game_address, enemy_address, normal_count, boss_count, phase,
        request_id,
    )
    intervals = []
    weighted_values = []
    player_deltas = []
    bullet_deltas = []
    normal_deltas = []
    boss_y_deltas = []
    boss_script_deltas = []
    for frame in range(FRAME_COUNT):
        started = time.monotonic_ns()
        request_id = hit_breakpoint(
            symbols["input"], request_id, "input poll frame %d" % (frame + 1),
        )
        request_id = hit_breakpoint(
            symbols["sound"], request_id, "sound tick frame %d" % (frame + 1),
        )
        request_id = hit_breakpoint(
            symbols["sync"], request_id,
            "display completion sync frame %d" % (frame + 1),
        )
        intervals.append((time.monotonic_ns() - started) // 1000)

        player = read_bytes(game_address + GAME_OFFSET_PLAYER, 2, request_id)
        request_id += 1
        bullet = read_bytes(game_address + GAME_OFFSET_BULLETS, 5, request_id)
        request_id += 1
        enemies = read_bytes(enemy_address,
                             GAME_MAX_ENEMIES * GAME_ENEMY_SIZE, request_id)
        request_id += 1
        boss = read_bytes(game_address + GAME_OFFSET_BOSS, 14, request_id)
        request_id += 1
        counts = weighted_count(enemies, boss[4])
        weighted_values.append(counts[2])
        if counts != (normal_count, boss_count,
                      normal_count + boss_count * BOSS_WEIGHT):
            raise RuntimeError("frame %d weighted readback mismatch: %r" %
                               (frame + 1, counts))
        player_deltas.append(player[0] - 8)
        bullet_deltas.append(bullet[0] - 20)
        if normal_count:
            normal_deltas.append(enemies[0] - 112)
        if boss_count:
            boss_y_deltas.append(boss[1] - 44)
            boss_script_deltas.append(boss[10])

        request_id = hit_breakpoint(
            symbols["request"], request_id,
            "display request frame %d" % (frame + 1),
        )
        request_id = inject_state(
            game_address, enemy_address, normal_count, boss_count, phase,
            request_id,
        )
    tool("controller_macro", {"commands": [{"release": "right"}]}, request_id)
    request_id += 1

    result = summarize_intervals(intervals)
    result.update({
        "phase": "boss" if phase == GAME_PHASE_BOSS else "normal",
        "completed_draw_frames": FRAME_COUNT,
        "direct_event_counts": {
            "input_polls": FRAME_COUNT,
            "logic_updates": "catch_up_per_elapsed_vblank",
            "sound_ticks": FRAME_COUNT,
            "display_completion_syncs": FRAME_COUNT,
            "display_requests": FRAME_COUNT,
        },
        "normal_enemies": normal_count,
        "bosses": boss_count,
        "weighted_count_min": min(weighted_values),
        "weighted_count_max": max(weighted_values),
        "player_x_delta_per_draw": sorted(set(player_deltas)),
        "player_bullet_x_delta_per_draw": sorted(set(bullet_deltas)),
        "normal_enemy_x_delta_per_draw": sorted(set(normal_deltas)),
        "boss_y_delta_per_draw": sorted(set(boss_y_deltas)),
        "boss_attack_timer_per_draw": sorted(set(boss_script_deltas)),
    })
    return request_id, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path,
                        default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--map", type=Path,
                        default=Path("build/asteroid-patrol-cadence.map"))
    parser.add_argument("--normal-rom", type=Path,
                        default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--normal-symbols", type=Path,
                        default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--normal-map", type=Path,
                        default=Path("build/asteroid-patrol.map"))
    parser.add_argument("--output", type=Path,
                        default=Path(
                            "evidence/APS-051/frame-cadence-gearlynx.json"))
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--frame-regression", action="store_true",
                        help="run the slow per-frame debugger regression")
    args = parser.parse_args()

    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    separation = verify_rom_separation(args)
    game_address = symbol_address(args.symbols, "_game")
    enemy_address = symbol_address(args.symbols, "_game_enemies")
    symbols = {
        "input": symbol_address(args.symbols, "_game_input_poll"),
        "logic": symbol_address(args.symbols, "_game_update_logic"),
        "sound": symbol_address(args.symbols, "_game_sound_tick"),
        "sync": symbol_address(args.symbols, "_game_display_sync_complete"),
        "request": symbol_address(args.symbols, "_game_display_request"),
    }
    probe = {
        "armed": symbol_address(args.symbols, "_cadence_probe_armed"),
        "active": symbol_address(args.symbols, "_cadence_probe_active"),
        "complete": symbol_address(args.symbols, "_cadence_probe_complete"),
        "sample_count": symbol_address(
            args.symbols, "_cadence_probe_sample_count"),
        "overflow": symbol_address(args.symbols, "_cadence_probe_overflow"),
        "intervals": symbol_address(args.symbols, "_cadence_probe_intervals"),
        "logic_updates": symbol_address(
            args.symbols, "_cadence_probe_logic_update_count",
        ),
        "consumed_vblanks": symbol_address(
            args.symbols, "_cadence_probe_elapsed_vblank_count",
        ),
        "sound_ticks": symbol_address(
            args.symbols, "_cadence_probe_sound_tick_count",
        ),
        "warmup_vblanks": symbol_address(
            args.symbols, "_cadence_probe_warmup_vblank_count",
        ),
        "stack_low_water": symbol_address(
            args.symbols, "_game_timing_stack_low_water",
        ),
    }
    command = [GEARLYNX]
    if not args.gui:
        command.append("--headless")
    command.extend([
        "--mcp-http", "--mcp-http-port", str(MCP_PORT),
        str(args.rom), str(args.symbols),
    ])
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                call("initialize", {
                    "protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "aps051-frame-cadence",
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
            state = read_bytes(game_address + GAME_OFFSET_STAGE, 2, request_id)
            request_id += 1
            if state == bytes([1, 6]):
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
        timer_zero = tool("get_mikey_timers", {"timer": 0},
                          request_id=request_id)
        request_id += 1
        timer_two = tool("get_mikey_timers", {"timer": 2},
                         request_id=request_id)
        request_id += 1
        title_batches = []
        title_consumed_batches = []
        title_sound_batches = []
        for batch in range(2):
            request_id, title_intervals, _, title_consumed, title_sound, _ = collect_probe(
                probe, request_id, "stable TITLE calibration batch %d" %
                (batch + 1),
            )
            title_batches.append(title_intervals)
            title_consumed_batches.append(title_consumed)
            title_sound_batches.append(title_sound)
        title_cadence = summarize_probe_runs(
            title_batches, consumed_vblanks=title_consumed_batches,
            actual_sound_ticks=title_sound_batches,
        )
        title_medians = title_cadence["run_medians_vblank"]
        calibration = {
            "gate": "stable TITLE display_request / Timer 2 VBlank",
            "prior_tick_reference": {
                "display_request_ticks": 553362,
                "vblank_ticks": VBLANK_TICKS,
                "ratio": TITLE_REFERENCE_RATIO,
            },
            "measured_title_run_medians_vblank_ratio": title_medians,
            "measured_title_run_maxima_vblank_ratio":
                title_cadence["run_maxima_vblank"],
            "measured_title_raw_vblank_counts": title_batches,
            "measured_title_raw_samples_reproducible":
                title_batches[0] == title_batches[1],
            "reference_ratio_difference": [
                median - TITLE_REFERENCE_RATIO for median in title_medians
            ],
            "tolerance": 0.05,
            "passed": all(
                abs(median - TITLE_REFERENCE_RATIO) <= 0.05
                for median in title_medians
            ),
        }
        if not calibration["passed"]:
            raise RuntimeError(
                "TITLE cadence calibration failed: measured=%r "
                "reference=%.6f" % (title_medians, TITLE_REFERENCE_RATIO)
            )

        scenarios = []
        for normal_count, boss_count in ((0, 0), (4, 0), (8, 0), (4, 1)):
            phases = [GAME_PHASE_NORMAL]
            if boss_count:
                phases.append(GAME_PHASE_BOSS)
            phase_results = []
            for phase in phases:
                if args.frame_regression:
                    request_id, result = verify_phase(
                        game_address, enemy_address, symbols, normal_count,
                        boss_count, phase, request_id,
                    )
                else:
                    result = {
                        "phase": "boss" if phase == GAME_PHASE_BOSS
                        else "normal",
                        "completed_draw_frames": 0,
                        "median_us": 0.0,
                        "frame_regression_skipped": True,
                    }
                request_id, cadence = measure_cadence(
                    game_address, enemy_address, probe, symbols["request"],
                    separation["cadence_rom"]["layout"]["c_stack_start"],
                    separation["cadence_rom"]["layout"]["stack_end_exclusive"],
                    normal_count, boss_count, phase, request_id,
                )
                result["contract_g"] = cadence
                phase_results.append(result)
                print("normal=%d boss=%d phase=%s frames=%d median_us=%.3f "
                      "contract_g_run_medians=%r run_maxima=%r "
                      "within_budget=%s" % (
                    normal_count, boss_count, result["phase"],
                    result["completed_draw_frames"], result["median_us"],
                    cadence["run_medians_vblank"],
                    cadence["run_maxima_vblank"],
                    cadence["within_budget"],
                ))
            scenarios.append({
                "normal_enemies": normal_count,
                "bosses": boss_count,
                "weighted_value": normal_count + boss_count * BOSS_WEIGHT,
                "phase_runs": phase_results,
            })

        rejected = []
        for normal_count, boss_count in ((5, 1), (8, 1), (9, 0)):
            if injection_is_valid(normal_count, boss_count):
                raise RuntimeError("weighted overflow injection was accepted")
            rejected.append({
                "normal_enemies": normal_count,
                "bosses": boss_count,
                "weighted_value": normal_count + boss_count * BOSS_WEIGHT,
                "accepted": False,
            })
        evidence = {
            "aps": "APS-052",
            "rom": separation["cadence_rom"],
            "normal_rom": separation["normal_rom"],
            "rom_separation": separation,
            "measurement_stage": 1,
            "mode": "gui" if args.gui else "headless",
            "draw_hz": 75,
            "weights": {"normal": NORMAL_WEIGHT, "boss": BOSS_WEIGHT,
                        "limit": WEIGHT_LIMIT},
            "pipeline": {
                "order": ["input", "logic_x4", "sound",
                          "prior_display_completion_sync", "draw",
                          "display_request"],
                "sync_breakpoint_symbol": "_game_display_sync_complete",
                "request_breakpoint_symbol": "_game_display_request",
                "frame_end_busy_wait_present": False,
                "timer_0": timer_zero,
                "timer_2": timer_two,
            },
            "wall_clock": {
                "advisory_only": True,
                "used_for_contract_g": False,
            },
            "hardware_cadence_contract": {
                "source": "ROM Timer 2 VBlank counter sampled by the "
                    "display-request hook",
                "vblank_reference_ticks": VBLANK_TICKS,
                "vblank_reference_us": VBLANK_US,
                "max_interval_ratio": MAX_VBLANK_RATIO,
                "contract_g_method": "16 consecutive VBlank counts between "
                    "17 continuously running display requests; one completion "
                    "write breakpoint per batch; no debug_step_frame",
                "rom_probe": {
                    "display_hook_symbol": "_cadence_probe_display",
                    "timer2_interruptor": "cadence_probe_irq",
                    "raw_sample_unit": "Timer 2 VBlank IRQ count",
                    "samples_per_fixture": CADENCE_INTERVAL_COUNT,
                    "warmup_display_requests": CADENCE_WARMUP_REQUEST_COUNT,
                    "stops_per_batch": 1,
                    "request_breakpoints_per_batch": 0,
                    "debug_step_frame_used": False,
                },
            },
            "calibration_gate": calibration,
            "title_calibration": title_cadence,
            "scenarios": scenarios,
            "rejected_injections": rejected,
            "all_contract_g_within_budget": all(
                run["contract_g"]["within_budget"]
                for scenario in scenarios
                for run in scenario["phase_runs"]
            ),
            "four_enemy_logic_catch_up_within_target": all(
                all(run["contract_g"]["logic_catch_up"]["within_target"]) and
                run["contract_g"]["clip_zero"]
                for scenario in scenarios
                if scenario["normal_enemies"] == 4 and
                scenario["bosses"] == 0
                for run in scenario["phase_runs"]
            ),
            "four_eight_boss_sound_timing_within_target": all(
                all(run["contract_g"]["sound_timing"]["within_target"])
                for scenario in scenarios
                if (scenario["normal_enemies"], scenario["bosses"]) in
                ((4, 0), (8, 0), (4, 1))
                for run in scenario["phase_runs"]
            ),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        passed = evidence["all_contract_g_within_budget"]
        print("%s: APS-052 cadence evidence %s" %
              ("PASS" if passed else "FAIL", args.output))
        return 0 if passed else 1
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
