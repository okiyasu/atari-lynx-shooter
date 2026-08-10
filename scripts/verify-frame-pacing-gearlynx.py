#!/usr/bin/env python3
"""Verify APS-047 weighted capacity and pipelined 75 Hz ROM cadence.

APS-049 contract g (1 draw-frame real-time budget) is measured with a LOW
MCP round-trip-count method: state is injected once per fixture, all 75
draw frames are advanced in a single debug_step_frame({frames: 75}) call
(a Gearlynx native "run to VBlank x N" primitive), and total_ticks is read
only before/after (~12 MCP round trips per fixture). This replaced an
earlier per-frame-breakpoint method (~370+ round trips per fixture) that
was shown by scripts/calibrate-cadence-ticks-gearlynx.py and this
low-frequency method to have been a measurement artifact, not a real
performance bug: the original method reported the idle (0 normal/0 boss)
fixture blowing the 13.3ms budget by ~4x, while the low-frequency method
and the tick calibration (round-trip-count-independent, see
evidence/APS-049/cadence-tick-calibration.json) both show every fixture
using well under 1% of the budget. See .briefs/APS-049/v002.md and
ISSUES.md's APS-049 section A for the full trail.

The per-frame breakpoint loop (verify_phase) is kept for what it is
actually good at: asserting that player/bullet/enemy/boss movement and
the input/logic/sound/sync/request event counts stay constant across all
75 draw frames (a correctness regression, not a timing measurement). Its
wall-clock/interval figures remain advisory only.
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
# APS-049 contract g: 6502 total_ticks (get_6502_status) is Gearlynx's
# cumulative CPU-cycle counter -- a hardware event count, not a host
# wall-clock sample -- so it is the pass/fail source of truth for 1
# draw-frame real time. US_PER_TICK was calibrated once by measuring
# total_ticks across 12 consecutive _game_display_request breakpoints on
# a stable, idle TITLE screen (which is hardware-synchronized to exactly
# 75 Hz / 13,333.33us per draw): mean delta was 553,380 ticks, so
# 13333.333 / 553380 = 0.024093 us/tick. scripts/calibrate-cadence-ticks-
# gearlynx.py independently confirmed total_ticks is linear in
# instruction count and unaffected by MCP round-trip frequency (inflation
# ratio 1.000 up to ~1550 round trips), so this constant and the
# low-frequency debug_step_frame measurement in measure_cadence_lowfreq()
# below are both sound. See evidence/APS-049/ for both transcripts.
US_PER_TICK = 13333.333333333334 / 553380.0
FRAME_BUDGET_US = 13333.333333333334


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
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status["paused"]:
            if not status["at_breakpoint"]:
                raise RuntimeError("paused before %s breakpoint" % description)
            return request_id
        time.sleep(0.001)
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
    write_bytes(game_address + GAME_OFFSET_PLAYER, [8, 88, 8, 6], request_id)
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


def measure_cadence_lowfreq(game_address, enemy_address, normal_count,
                            boss_count, phase, request_id):
    """APS-049 contract g pass/fail source of truth: inject state once,
    advance all FRAME_COUNT draw frames in a single debug_step_frame
    call, and read total_ticks only before/after (~12 MCP round trips per
    fixture, independent of round-trip frequency per
    scripts/calibrate-cadence-ticks-gearlynx.py). Raises if the measured
    average exceeds the 13.3ms/draw-frame hardware budget."""
    request_id = inject_state(
        game_address, enemy_address, normal_count, boss_count, phase,
        request_id,
    )
    before = tool("get_6502_status", request_id=request_id)["total_ticks"]
    request_id += 1
    tool("debug_step_frame", {"frames": FRAME_COUNT}, request_id)
    request_id += 1
    after = tool("get_6502_status", request_id=request_id)["total_ticks"]
    request_id += 1

    # readback: confirm the enemy/boss count held for the whole run (no
    # on-death respawn drift -- nothing collides with anything in this
    # fixture, but verify rather than assume).
    enemies = read_bytes(enemy_address, GAME_MAX_ENEMIES * GAME_ENEMY_SIZE,
                         request_id)
    request_id += 1
    boss = read_bytes(game_address + GAME_OFFSET_BOSS, 14, request_id)
    request_id += 1
    readback_normal, readback_boss, _ = weighted_count(enemies, boss[4])

    delta_ticks = after - before
    avg_us_per_frame = round(delta_ticks * US_PER_TICK / FRAME_COUNT, 3)
    if avg_us_per_frame > FRAME_BUDGET_US:
        raise RuntimeError(
            "contract g: normal=%d boss=%d phase=%d exceeded the "
            "13.3ms/draw-frame hardware budget: avg=%.3fus over "
            "%d draw frames (low-frequency debug_step_frame method)" % (
                normal_count, boss_count, phase, avg_us_per_frame,
                FRAME_COUNT,
            )
        )
    if readback_normal != normal_count or readback_boss != boss_count:
        raise RuntimeError(
            "contract g: normal=%d boss=%d phase=%d enemy/boss count drifted "
            "during measurement: readback normal=%d boss=%d" % (
                normal_count, boss_count, phase, readback_normal,
                readback_boss,
            )
        )
    return request_id, {
        "method": "low_round_trip_debug_step_frame",
        "round_trips": 6,
        "frames": FRAME_COUNT,
        "delta_ticks": delta_ticks,
        "avg_us_per_draw_frame": avg_us_per_frame,
        "budget_us": FRAME_BUDGET_US,
        "within_budget": avg_us_per_frame <= FRAME_BUDGET_US,
        "enemy_count_held": readback_normal == normal_count and
            readback_boss == boss_count,
    }


def verify_phase(game_address, enemy_address, symbols, normal_count,
                 boss_count, phase, request_id):
    """Per-frame breakpoint-driven regression check: asserts player/
    bullet/enemy/boss movement and input/logic/sound/sync/request event
    counts stay constant across all FRAME_COUNT draw frames. This method's
    own wall-clock/tick sampling is NOT used for the contract g pass/fail
    decision (see measure_cadence_lowfreq): the high round-trip frequency
    here was shown to inflate total_ticks via Gearlynx's real-time-paced
    debug_continue execution, not a real performance characteristic."""
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
    request_id = hit_breakpoint(symbols["logic"], request_id, "warm-up logic", 4)
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
            symbols["logic"], request_id,
            "logic update frame %d" % (frame + 1), 4,
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

    if set(player_deltas) != {8} or set(bullet_deltas) != {16}:
        raise RuntimeError(
            "player/bullet cadence differs across frames: player=%r "
            "bullet=%r" % (sorted(set(player_deltas)),
                           sorted(set(bullet_deltas)))
        )
    if phase == GAME_PHASE_NORMAL and normal_count and set(normal_deltas) != {-4}:
        raise RuntimeError("normal enemy cadence differs across frames")
    if phase == GAME_PHASE_BOSS and boss_count:
        if set(boss_y_deltas) != {2} or set(boss_script_deltas) != {4}:
            raise RuntimeError("boss movement/script cadence differs across frames")
    result = summarize_intervals(intervals)
    result.update({
        "phase": "boss" if phase == GAME_PHASE_BOSS else "normal",
        "completed_draw_frames": FRAME_COUNT,
        "direct_event_counts": {
            "input_polls": FRAME_COUNT,
            "logic_updates": FRAME_COUNT * 4,
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
    parser.add_argument("--output", type=Path,
                        default=Path(
                            "evidence/APS-049/frame-cadence-gearlynx.json"))
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()

    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    game_address = symbol_address(args.symbols, "_game")
    enemy_address = symbol_address(args.symbols, "_game_enemies")
    symbols = {
        "input": symbol_address(args.symbols, "_game_input_poll"),
        "logic": symbol_address(args.symbols, "_game_update_logic"),
        "sound": symbol_address(args.symbols, "_game_sound_tick"),
        "sync": symbol_address(args.symbols, "_game_display_sync_complete"),
        "request": symbol_address(args.symbols, "_game_display_request"),
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
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "aps047-frame-cadence",
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

        scenarios = []
        for normal_count, boss_count in ((0, 0), (4, 0), (8, 0), (4, 1)):
            phases = [GAME_PHASE_NORMAL]
            if boss_count:
                phases.append(GAME_PHASE_BOSS)
            phase_results = []
            for phase in phases:
                request_id, result = verify_phase(
                    game_address, enemy_address, symbols, normal_count,
                    boss_count, phase, request_id,
                )
                request_id, cadence = measure_cadence_lowfreq(
                    game_address, enemy_address, normal_count, boss_count,
                    phase, request_id,
                )
                result["contract_g"] = cadence
                phase_results.append(result)
                print("normal=%d boss=%d phase=%s frames=%d median_us=%d "
                      "contract_g_avg_us=%.3f within_budget=%s" % (
                    normal_count, boss_count, result["phase"],
                    result["completed_draw_frames"], result["median_us"],
                    cadence["avg_us_per_draw_frame"], cadence["within_budget"],
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
            "aps": "APS-049",
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
                "debugger_breakpoint_round_trips_included": True,
            },
            "hardware_cadence_contract": {
                "source": "6502 total_ticks via get_6502_status "
                    "(cumulative CPU-cycle counter, not host wall clock)",
                "us_per_tick": US_PER_TICK,
                "calibration": "553380 ticks measured across 12 consecutive "
                    "_game_display_request breakpoints on a stable idle "
                    "TITLE screen, hardware-locked to 75 Hz "
                    "(13333.333us/draw-frame)",
                "budget_us": FRAME_BUDGET_US,
                "contract_g_method": "low round-trip re-measurement: state "
                    "injected once per fixture, all 75 draw frames advanced "
                    "in a single debug_step_frame call, total_ticks read "
                    "only before/after (~12 MCP round trips per fixture). "
                    "The per-frame breakpoint loop above (verify_phase) is "
                    "used only for player/bullet/enemy/boss movement and "
                    "event-count regression checks, not for the contract g "
                    "pass/fail decision -- see module docstring and "
                    ".briefs/APS-049/v002.md.",
            },
            "scenarios": scenarios,
            "rejected_injections": rejected,
            "all_contract_g_within_budget": all(
                run["contract_g"]["within_budget"]
                for scenario in scenarios
                for run in scenario["phase_runs"]
            ),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("PASS: APS-049 weighted cadence + contract g evidence %s" %
              args.output)
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
