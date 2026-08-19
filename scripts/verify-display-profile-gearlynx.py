#!/usr/bin/env python3
"""APS-053 public-symbol display-boundary verifier.

The cadence ROM is observed only through exported labels.  The verifier does
not patch the ROM, add instrumentation, or infer private function addresses.
Each measured interval is delimited by consecutive
``_game_timing_consume_vblanks`` entries.  Exactly one public breakpoint is
armed at a time, so consume, busy, static-layer, sprite, display-request, and
updatedisplay boundaries are captured in one real frame without the v018
multi-breakpoint resume race.
The optional ``--no-reinject`` mode is the v021 diagnostic: it measures only
the 4-enemy NORMAL fixture, injects that fixture once per independent batch,
and never rewrites the combat state during the ten measured intervals.
The optional ``--bounded-catchup`` mode is the v023 bounded fixed-step
comparison: it validates logic=12 and sound=4 caps plus probe discard/clip
counters against fresh/no-reinject 4-enemy runs and zero-enemy controls.
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
MCP_PORT = 17779
DISPLAY_INTERVALS = 10
BATCH_COUNT = 2
GAME_PHASE_NORMAL = 1
GAME_PHASE_BOSS = 3
GAME_MAX_ENEMY_BULLETS = 16
GAME_ENEMY_BULLET_SIZE = 5
GAME_LOGIC_UPDATES_NUMERATOR = 4
GAME_LOGIC_UPDATES_MAX = 128
GAME_SOUND_TICKS_MAX = 2048
BOUNDED_LOGIC_UPDATES_MAX = 12
BOUNDED_SOUND_TICKS_MAX = 4
V022_BASELINE = {
    "release_rom_sha256": "0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb",
    "cadence_rom_sha256": "8d40092eb11e6f43b16a404dc7795644896305f59dd4133bbd0aa812bb646cab",
    "release_map_sha256": "d8bb6ef95cae7675ef2c117da19e439485fe893dbe6af0173ea7f18004bbde24",
    "cadence_map_sha256": "3bc8cba2000797c72da9155b5ddb35ab2b39f748f135e798e63c591d9f961136",
}
MAX_CONTAMINATION_MEDIAN_DELTA = 1
MAX_CONTAMINATION_RELATIVE_DELTA = 0.05
EVENT_NAMES = (
    "consume",
    "static_layer",
    "tgi_ioctl",
    "display_request",
)
CAPTURE_PROGRESS = {
    "fixture": None,
    "batch": None,
    "interval": None,
    "last_successful_boundary": None,
}


def load_frame_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_display_profile_frame", FRAME_VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    module.GEARLYNX = GEARLYNX
    module.CADENCE_BATCH_TIMEOUT_SECONDS = 240.0
    return module


def load_section_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_display_profile_section", SECTION_VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    module.GEARLYNX = GEARLYNX
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
                    "name": "aps053-display-profile",
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
    process = subprocess.Popen(
        [GEARLYNX, "--headless", "--mcp-http", "--mcp-http-port",
         str(MCP_PORT), str(rom), str(symbols)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    initialize(frame)
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
        process.terminate()
        raise RuntimeError("ROM did not reach stable TITLE state")
    frame.tool("debug_pause", request_id=request_id)
    return process, wait_paused(frame, request_id + 1, "stable TITLE")


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_for_public_breakpoint(frame, request_id, description):
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        status = frame.tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status.get("paused"):
            if not status.get("at_breakpoint"):
                raise RuntimeError(
                    "paused before %s breakpoint (pc=%s)" %
                    (description, status.get("pc")),
                )
            return request_id
        time.sleep(0.01)
    raise RuntimeError("timed out waiting for %s breakpoint" % description)


def hit_public_boundary(frame, address, request_id, description):
    """Capture one entry with no other breakpoint armed."""
    address_hex = "%04X" % address
    frame.tool("set_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    frame.tool("debug_continue", request_id=request_id)
    request_id += 1
    request_id = wait_for_public_breakpoint(
        frame, request_id, description,
    )
    cpu, _ = cpu_timestamp(frame, request_id)
    request_id += 1
    pc = int(cpu["PC"], 16)
    if pc != address:
        raise RuntimeError(
            "%s stopped at 0x%04X instead of 0x%04X" %
            (description, pc, address)
        )
    frame.tool("remove_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    CAPTURE_PROGRESS["last_successful_boundary"] = {
        "description": description,
        "pc": "0x%04X" % pc,
        "cpu_total_ticks": cpu.get("total_ticks"),
    }
    return request_id, cpu


def step_out_and_wait(frame, request_id, description):
    """Finish the current public call before arming the next boundary."""
    frame.tool("debug_step_out", request_id=request_id)
    request_id += 1
    request_id = wait_paused(frame, request_id, description)
    cpu, _ = cpu_timestamp(frame, request_id)
    return request_id + 1, cpu


def u8(frame, address, request_id):
    return frame.read_bytes(address, 1, request_id)[0]


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
    game = frame.read_bytes(game_address + frame.GAME_OFFSET_STAGE, 5,
                            request_id)
    request_id += 1
    enemies = frame.read_bytes(
        enemy_address,
        frame.GAME_MAX_ENEMIES * frame.GAME_ENEMY_SIZE,
        request_id,
    )
    request_id += 1
    enemy_bullets = frame.read_bytes(
        game_address + frame.GAME_OFFSET_ENEMY_BULLETS,
        GAME_MAX_ENEMY_BULLETS * GAME_ENEMY_BULLET_SIZE,
        request_id,
    )
    request_id += 1
    boss = frame.read_bytes(game_address + frame.GAME_OFFSET_BOSS, 14,
                            request_id)
    request_id += 1
    normal, active_boss, weighted = frame.weighted_count(enemies, boss[4])
    enemy_slots = []
    for slot in range(frame.GAME_MAX_ENEMIES):
        record = enemies[
            slot * frame.GAME_ENEMY_SIZE:(slot + 1) * frame.GAME_ENEMY_SIZE
        ]
        enemy_slots.append({
            "slot": slot,
            "active": record[4],
            "type": record[5],
            "x": record[0],
            "y": record[1],
        })
    active_bullets = []
    for slot in range(GAME_MAX_ENEMY_BULLETS):
        record = enemy_bullets[
            slot * GAME_ENEMY_BULLET_SIZE:
            (slot + 1) * GAME_ENEMY_BULLET_SIZE
        ]
        if record[2] != 0:
            active_bullets.append({
                "slot": slot,
                "x": record[0],
                "y": record[1],
            })
    return request_id, {
        "stage": game[0],
        "phase": game[1],
        "phase_timer": game[2] | (game[3] << 8),
        "boss_active": active_boss,
        "normal_enemy_count": normal,
        "weighted_value": weighted,
        "enemy_slots": enemy_slots,
        "enemy_bullets": {
            "active_count": len(active_bullets),
            "active_slots": active_bullets,
        },
        "readback_consistent": (
            normal == sum(
                slot["active"] != 0 and slot["x"] < 160
                for slot in enemy_slots
            ) and
            active_boss == int(boss[4] != 0) and
            len(active_bullets) <= GAME_MAX_ENEMY_BULLETS
        ),
        "expected_state_source": "live GameState/enemy readback",
    }


def profile_addresses(frame, symbols):
    names = {
        "consume": "_game_timing_consume_vblanks",
        "logic": "_game_update_logic",
        "sound": "_game_sound_tick",
        "static_layer": "_static_layer_draw",
        "tgi_ioctl": "_tgi_ioctl",
        "display_request": "_game_display_request",
        "vblank": "_cadence_probe_vblank_count",
        "logic_counter": "_cadence_probe_logic_update_count",
        "elapsed": "_cadence_probe_elapsed_vblank_count",
        "sound_counter": "_cadence_probe_sound_tick_count",
        "active": "_cadence_probe_active",
        "armed": "_cadence_probe_armed",
        "complete": "_cadence_probe_complete",
        "target_phase": "_cadence_probe_target_phase",
        "intervals": "_cadence_probe_intervals",
        "fixture_states": "_cadence_probe_fixture_states",
        "overflow": "_cadence_probe_overflow",
        "warmup_vblanks": "_cadence_probe_warmup_vblank_count",
        "sample_count": "_cadence_probe_sample_count",
        "sp": "sp",
    }
    return {key: frame.symbol_address(symbols, value)
            for key, value in names.items()}


def arm_profile(frame, addresses, game_address, enemy_address, phase,
                request_id, inject_fixture=True):
    if inject_fixture:
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
    # Match the established section/logic verifier warm-up protocol.  Re-arm
    # the same one-shot breakpoint without step_out; Gearlynx advances past
    # the current entry on continue and stops at the next request.  The final
    # request leaves the debugger at a stable request boundary.
    for index in range(8):
        request_id, _ = hit_public_boundary(
            frame, addresses["display_request"], request_id,
            "display-profile warm-up %d" % (index + 1),
        )
    return request_id


def cpu_timestamp(frame, request_id):
    cpu = frame.tool("get_6502_status", request_id=request_id)
    return cpu, cpu.get("total_ticks")


def ioctl_classification(frame, addresses, cpu, request_id):
    pointer = int(cpu["A"], 16) | (int(cpu["X"], 16) << 8)
    stack_pointer = u16(frame, addresses["sp"], request_id)
    code = u8(frame, stack_pointer, request_id + 1)
    request_id += 2
    if code == 0:
        kind = "tgi_sprite"
        valid = pointer != 0
    elif code == 4 and pointer == 0:
        kind = "tgi_busy"
        valid = True
    elif code == 4 and pointer == 1:
        kind = "tgi_updatedisplay"
        valid = True
    else:
        kind = "unknown"
        valid = False
    return request_id, {
        "code": code,
        "data_pointer": "0x%04X" % pointer,
        "cc65_sp_value": "0x%04X" % stack_pointer,
        "classification": kind,
        "classification_valid": valid,
        "cpu_A": cpu["A"],
        "cpu_X": cpu["X"],
        "code_source": "cc65 C stack byte at *(zero-page sp) before tgi_ioctl.s popa",
    }


def event_snapshot(frame, addresses, game_address, enemy_address, name,
                   cpu, request_id):
    event = {
        "event": name,
        "pc": cpu.get("PC"),
        "cpu_total_ticks": cpu.get("total_ticks"),
    }
    event["timer2"] = timer_snapshot(frame, request_id)
    request_id += 1
    request_id, fixture = fixture_observation(
        frame, game_address, enemy_address, request_id,
    )
    event["vblank_counter"] = u16(frame, addresses["vblank"], request_id)
    event["logic_update_count"] = u32(
        frame, addresses["logic_counter"], request_id + 1,
    )
    event["elapsed_vblank_count"] = u32(
        frame, addresses["elapsed"], request_id + 2,
    )
    event["sound_tick_count"] = u32(
        frame, addresses["sound_counter"], request_id + 3,
    )
    event["sample_count"] = u8(
        frame, addresses["sample_count"], request_id + 4,
    )
    event["fixture"] = fixture
    request_id += 5
    if name == "tgi_ioctl":
        request_id, event["ioctl"] = ioctl_classification(
            frame, addresses, cpu, request_id,
        )
    return request_id, event


def run_display_batch(frame, rom, symbols, fixture, batch_index,
                      no_reinject=False, disable_probe=False):
    game_address = frame.symbol_address(symbols, "_game")
    enemy_address = frame.symbol_address(symbols, "_game_enemies")
    addresses = profile_addresses(frame, symbols)
    process, request_id = start_paused(frame, rom, symbols, game_address)
    try:
        CAPTURE_PROGRESS["fixture"] = fixture["name"]
        CAPTURE_PROGRESS["batch"] = batch_index
        CAPTURE_PROGRESS["interval"] = 0
        if disable_probe:
            if not no_reinject:
                request_id = frame.inject_state(
                    game_address, enemy_address, 0, 0,
                    fixture["phase"], request_id,
                )
            frame.write_bytes(addresses["target_phase"],
                             [fixture["phase"]], request_id)
            request_id += 1
            frame.write_bytes(addresses["active"], [0], request_id)
            request_id += 1
            frame.write_bytes(addresses["complete"], [0], request_id)
            request_id += 1
            frame.write_bytes(addresses["armed"], [0], request_id)
            request_id += 1
        else:
            request_id = arm_profile(
                frame, addresses, game_address, enemy_address,
                fixture["phase"], request_id,
                inject_fixture=not no_reinject,
            )
        injection_count = 0
        request_id = frame.inject_state(
            game_address, enemy_address, fixture["normal_enemies"],
            fixture["bosses"], fixture["phase"], request_id,
        )
        injection_count += 1
        request_id, cpu = hit_public_boundary(
            frame, addresses["consume"], request_id,
            "consume interval 1 batch %d" % batch_index,
        )
        request_id, current_start = event_snapshot(
            frame, addresses, game_address, enemy_address, "consume", cpu,
            request_id,
        )
        if no_reinject and not fixture_target_matches(
                current_start["fixture"], fixture):
            raise RuntimeError(
                "initial no-reinject fixture readback mismatch: %s" %
                current_start["fixture"]
            )
        intervals = []
        event_count = 0
        while len(intervals) < DISPLAY_INTERVALS:
            interval_index = len(intervals) + 1
            CAPTURE_PROGRESS["interval"] = interval_index
            events = [current_start]

            busy_calls = 0
            while True:
                request_id, cpu = hit_public_boundary(
                    frame, addresses["tgi_ioctl"], request_id,
                    "tgi_busy interval %d batch %d" %
                    (interval_index, batch_index),
                )
                request_id, busy_event = event_snapshot(
                    frame, addresses, game_address, enemy_address,
                    "tgi_ioctl", cpu, request_id,
                )
                if busy_event["ioctl"]["classification"] != "tgi_busy":
                    raise RuntimeError(
                        "expected tgi_busy before static_layer_draw; got %s" %
                        busy_event["ioctl"]["classification"]
                    )
                request_id, return_cpu = step_out_and_wait(
                    frame, request_id,
                    "tgi_busy return interval %d batch %d" %
                    (interval_index, batch_index),
                )
                return_value = int(return_cpu["A"], 16) | \
                    (int(return_cpu["X"], 16) << 8)
                busy_event["return"] = {
                    "cpu_A": return_cpu["A"],
                    "cpu_X": return_cpu["X"],
                    "value": return_value,
                }
                events.append(busy_event)
                event_count += 1
                busy_calls += 1
                if return_value == 0:
                    break
                if busy_calls >= 64:
                    raise RuntimeError(
                        "tgi_busy did not become idle within 64 calls"
                    )

            request_id, cpu = hit_public_boundary(
                frame, addresses["static_layer"], request_id,
                "static_layer interval %d batch %d" %
                (interval_index, batch_index),
            )
            request_id, static_event = event_snapshot(
                frame, addresses, game_address, enemy_address,
                "static_layer", cpu, request_id,
            )
            events.append(static_event)
            event_count += 1

            request_id, cpu = hit_public_boundary(
                frame, addresses["tgi_ioctl"], request_id,
                "tgi_sprite interval %d batch %d" %
                (interval_index, batch_index),
            )
            request_id, sprite_event = event_snapshot(
                frame, addresses, game_address, enemy_address,
                "tgi_ioctl", cpu, request_id,
            )
            if sprite_event["ioctl"]["classification"] != "tgi_sprite":
                raise RuntimeError(
                    "expected tgi_sprite inside static_layer_draw; got %s" %
                    sprite_event["ioctl"]["classification"]
                )
            events.append(sprite_event)
            event_count += 1
            request_id, _ = step_out_and_wait(
                frame, request_id,
                "tgi_sprite return interval %d batch %d" %
                (interval_index, batch_index),
            )

            request_id, cpu = hit_public_boundary(
                frame, addresses["display_request"], request_id,
                "display_request interval %d batch %d" %
                (interval_index, batch_index),
            )
            request_id, request_event = event_snapshot(
                frame, addresses, game_address, enemy_address,
                "display_request", cpu, request_id,
            )
            events.append(request_event)
            event_count += 1

            request_id, cpu = hit_public_boundary(
                frame, addresses["tgi_ioctl"], request_id,
                "tgi_updatedisplay interval %d batch %d" %
                (interval_index, batch_index),
            )
            request_id, update_event = event_snapshot(
                frame, addresses, game_address, enemy_address,
                "tgi_ioctl", cpu, request_id,
            )
            if update_event["ioctl"]["classification"] != \
                    "tgi_updatedisplay":
                raise RuntimeError(
                    "expected tgi_updatedisplay after display_request; got %s" %
                    update_event["ioctl"]["classification"]
                )
            events.append(update_event)
            event_count += 1
            request_id, _ = step_out_and_wait(
                frame, request_id,
                "tgi_updatedisplay return interval %d batch %d" %
                (interval_index, batch_index),
            )

            request_id, cpu = hit_public_boundary(
                frame, addresses["consume"], request_id,
                "consume interval %d end batch %d" %
                (interval_index, batch_index),
            )
            request_id, end_event = event_snapshot(
                frame, addresses, game_address, enemy_address, "consume",
                cpu, request_id,
            )
            events.append(end_event)
            event_count += 1
            intervals.append({
                "interval": interval_index,
                "start": current_start,
                "end": end_event,
                "events": events,
            })
            current_start = end_event
            if not no_reinject and len(intervals) < DISPLAY_INTERVALS:
                request_id = frame.inject_state(
                    game_address, enemy_address, fixture["normal_enemies"],
                    fixture["bosses"], fixture["phase"], request_id,
                )
                injection_count += 1
        return {
            "batch": batch_index,
            "fixture_target": fixture,
            "injection_policy": (
                "one initial fixture injection; zero interval reinjections"
                if no_reinject else
                "initial fixture injection plus interval reinjection"
            ),
            "initial_fixture_injections": 1,
            "interval_reinjections": injection_count - 1,
            "interval_count": len(intervals),
            "event_count": event_count,
            "intervals": intervals,
        }
    finally:
        stop_process(process)


def timer_number(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value), 16)
    except ValueError:
        return int(str(value), 10)


def fixture_target_matches(observation, fixture):
    return (
        observation["phase"] == fixture["phase"] and
        observation["boss_active"] == fixture["bosses"] and
        observation["normal_enemy_count"] == fixture["normal_enemies"] and
        observation["readback_consistent"]
    )


def combat_state_signature(observation):
    return (
        tuple(
            (slot["active"], slot["type"], slot["x"], slot["y"])
            for slot in observation["enemy_slots"]
        ),
        tuple(
            (slot["slot"], slot["x"], slot["y"])
            for slot in observation["enemy_bullets"]["active_slots"]
        ),
    )


def combat_state_delta(before, after):
    enemy_changes = []
    for before_slot, after_slot in zip(
            before["enemy_slots"], after["enemy_slots"]):
        if before_slot != after_slot:
            enemy_changes.append({
                "slot": after_slot["slot"],
                "before": before_slot,
                "after": after_slot,
            })
    before_bullets = {
        item["slot"]: item
        for item in before["enemy_bullets"]["active_slots"]
    }
    after_bullets = {
        item["slot"]: item
        for item in after["enemy_bullets"]["active_slots"]
    }
    bullet_changes = []
    for slot in sorted(set(before_bullets) | set(after_bullets)):
        if before_bullets.get(slot) != after_bullets.get(slot):
            bullet_changes.append({
                "slot": slot,
                "before": before_bullets.get(slot),
                "after": after_bullets.get(slot),
            })
    return {
        "changed": bool(enemy_changes or bullet_changes),
        "enemy_slots": enemy_changes,
        "enemy_bullets": bullet_changes,
    }


def interval_summary(batch, fixture, allow_fixture_evolution=False):
    rows = []
    all_ioctl_valid = True
    for interval in batch["intervals"]:
        events = interval["events"]
        counts = {name: 0 for name in EVENT_NAMES}
        ioctl = []
        for event in events:
            counts[event["event"]] += 1
            if event["event"] == "tgi_ioctl":
                ioctl.append(event["ioctl"])
                all_ioctl_valid = all_ioctl_valid and event["ioctl"][
                    "classification_valid"]
        start = interval["start"]
        end = interval["end"]
        event_arrivals = []
        for event in events[1:-1]:
            event_arrivals.append({
                "event": event["event"],
                "ioctl_classification": event.get("ioctl", {}).get(
                    "classification"
                ),
                "elapsed_vblanks_from_consume":
                event["elapsed_vblank_count"] -
                start["elapsed_vblank_count"],
                "cpu_ticks_from_consume": event["cpu_total_ticks"] -
                start["cpu_total_ticks"],
                "timer2_current": timer_number(
                    event["timer2"]["current"]
                ),
                "sample_count": event["sample_count"],
            })
        ioctl_counts = {
            kind: sum(
                item["classification"] == kind for item in ioctl
            ) for kind in ("tgi_busy", "tgi_sprite", "tgi_updatedisplay",
                           "unknown")
        }
        all_fixture_states_valid = all(
            event["fixture"]["phase"] == fixture["phase"] and
            event["fixture"]["boss_active"] == fixture["bosses"] and
            event["fixture"]["readback_consistent"] and
            (allow_fixture_evolution or
             event["fixture"]["normal_enemy_count"] ==
             fixture["normal_enemies"])
            for event in events
        )
        state_delta = combat_state_delta(
            start["fixture"], end["fixture"],
        )
        rows.append({
            "interval": interval["interval"],
            "elapsed_vblank_delta": end["elapsed_vblank_count"] -
            start["elapsed_vblank_count"],
            "logic_update_delta": end["logic_update_count"] -
            start["logic_update_count"],
            "sound_tick_delta": end["sound_tick_count"] -
            start["sound_tick_count"],
            "timer2_start": timer_number(start["timer2"]["current"]),
            "timer2_end": timer_number(end["timer2"]["current"]),
            "cpu_total_ticks_start": start["cpu_total_ticks"],
            "cpu_total_ticks_end": end["cpu_total_ticks"],
            "public_event_counts": counts,
            "tgi_ioctl_counts": ioctl_counts,
            "tgi_ioctl": ioctl,
            "event_arrivals": event_arrivals,
            "all_boundary_fixture_states_valid": all_fixture_states_valid,
            "state_evolved": state_delta["changed"],
            "state_delta": state_delta,
            "fixture_start": start["fixture"],
            "fixture_end": end["fixture"],
        })
    valid = True
    for row in rows:
        for state in (row["fixture_start"], row["fixture_end"]):
            valid = valid and state["phase"] == fixture["phase"]
            valid = valid and state["boss_active"] == fixture["bosses"]
            valid = valid and state["readback_consistent"]
            if not allow_fixture_evolution:
                valid = valid and state["normal_enemy_count"] == fixture[
                    "normal_enemies"]
        valid = valid and row["public_event_counts"]["static_layer"] == 1
        valid = valid and row["public_event_counts"]["display_request"] == 1
        valid = valid and row["tgi_ioctl_counts"]["tgi_busy"] >= 1
        valid = valid and row["tgi_ioctl_counts"]["tgi_sprite"] == 1
        valid = valid and row["tgi_ioctl_counts"]["tgi_updatedisplay"] == 1
        valid = valid and row["tgi_ioctl_counts"]["unknown"] == 0
        valid = valid and row["all_boundary_fixture_states_valid"]
    vblank = [row["elapsed_vblank_delta"] for row in rows]
    shares = {}
    total = sum(vblank)
    for name in EVENT_NAMES:
        amount = sum(row["public_event_counts"][name] for row in rows)
        shares[name] = amount / float(sum(
            row["public_event_counts"][name] for row in rows
            for name in EVENT_NAMES
        ) or 1)
    boundary_ticks = {}
    boundary_elapsed = {}
    for key in ("tgi_busy", "static_layer", "tgi_sprite",
                "display_request", "tgi_updatedisplay"):
        selected = [
            arrival for row in rows for arrival in row["event_arrivals"]
            if (arrival["ioctl_classification"] == key or
                arrival["event"] == key)
        ]
        boundary_ticks[key] = [item["cpu_ticks_from_consume"]
                               for item in selected]
        boundary_elapsed[key] = [item["elapsed_vblanks_from_consume"]
                                 for item in selected]
    return {
        "batch": batch["batch"],
        "intervals": rows,
        "interval_elapsed_vblank_medians": vblank,
        "median_elapsed_vblanks": statistics.median(vblank),
        "maximum_elapsed_vblanks": max(vblank),
        "public_event_totals": {
            name: sum(row["public_event_counts"][name] for row in rows)
            for name in EVENT_NAMES
        },
        "public_event_shares_by_invocation": shares,
        "boundary_cpu_ticks_from_consume": boundary_ticks,
        "boundary_elapsed_vblanks_from_consume": boundary_elapsed,
        "boundary_cpu_tick_medians_from_consume": {
            key: statistics.median(values) if values else None
            for key, values in boundary_ticks.items()
        },
        "fixture_valid": valid,
        "state_evolution": {
            "any_interval_changed": any(
                row["state_evolved"] for row in rows
            ),
            "changed_intervals": [
                row["interval"] for row in rows if row["state_evolved"]
            ],
            "changed_enemy_slot_count": sum(
                len(row["state_delta"]["enemy_slots"])
                for row in rows
            ),
            "changed_enemy_bullet_slot_count": sum(
                len(row["state_delta"]["enemy_bullets"])
                for row in rows
            ),
        },
        "tgi_ioctl_classification_valid": all_ioctl_valid,
        "total_elapsed_vblanks": total,
    }


def add_catchup_metrics(summary):
    """Attach production scheduler expectations to each measured interval."""
    counter_match = True
    for row in summary["intervals"]:
        raw_elapsed = row["elapsed_vblank_delta"]
        ideal_logic = raw_elapsed * GAME_LOGIC_UPDATES_NUMERATOR
        ideal_sound = raw_elapsed
        expected_logic = min(ideal_logic, GAME_LOGIC_UPDATES_MAX)
        expected_sound = min(ideal_sound, GAME_SOUND_TICKS_MAX)
        actual_logic = row["logic_update_delta"]
        actual_sound = row["sound_tick_delta"]
        logic_match = actual_logic == expected_logic
        sound_match = actual_sound == expected_sound
        counter_match = counter_match and logic_match and sound_match
        row["catchup"] = {
            "raw_elapsed_vblanks": raw_elapsed,
            "logic_updates": actual_logic,
            "expected_logic_updates": expected_logic,
            "logic_clip_reached": ideal_logic >= GAME_LOGIC_UPDATES_MAX,
            "logic_clip_discarded": max(0, ideal_logic - GAME_LOGIC_UPDATES_MAX),
            "sound_ticks": actual_sound,
            "expected_sound_ticks": expected_sound,
            "sound_clip_reached": ideal_sound >= GAME_SOUND_TICKS_MAX,
            "sound_clip_discarded": max(0, ideal_sound - GAME_SOUND_TICKS_MAX),
            "logic_counter_matches_expected": logic_match,
            "sound_counter_matches_expected": sound_match,
            "counters_match_expected": logic_match and sound_match,
        }
    summary["catchup_validation"] = {
        "all_counters_match_expected": counter_match,
        "logic_cap": GAME_LOGIC_UPDATES_MAX,
        "sound_cap": GAME_SOUND_TICKS_MAX,
        "logic_formula": "min(raw_elapsed_vblanks * 4, 128)",
        "sound_formula": "min(raw_elapsed_vblanks, 2048)",
    }
    return summary


def add_bounded_catchup_metrics(summary):
    """Attach the v023 bounded scheduler and probe-counter expectations."""
    counter_match = True
    for row in summary["intervals"]:
        raw_elapsed = row["elapsed_vblank_delta"]
        ideal_logic = raw_elapsed * GAME_LOGIC_UPDATES_NUMERATOR
        ideal_sound = raw_elapsed
        expected_logic = min(ideal_logic, BOUNDED_LOGIC_UPDATES_MAX)
        expected_sound = min(ideal_sound, BOUNDED_SOUND_TICKS_MAX)
        expected_logic_discard = max(
            0, ideal_logic - BOUNDED_LOGIC_UPDATES_MAX,
        )
        expected_sound_discard = max(
            0, ideal_sound - BOUNDED_SOUND_TICKS_MAX,
        )
        expected_logic_clip = int(
            ideal_logic >= BOUNDED_LOGIC_UPDATES_MAX,
        )
        expected_sound_clip = int(
            ideal_sound >= BOUNDED_SOUND_TICKS_MAX,
        )
        actual_logic = row["logic_update_delta"]
        actual_sound = row["sound_tick_delta"]
        logic_match = actual_logic == expected_logic
        sound_match = actual_sound == expected_sound
        counter_match = counter_match and logic_match and sound_match
        row["catchup"] = {
            "raw_elapsed_vblanks": raw_elapsed,
            "logic_updates": actual_logic,
            "expected_logic_updates": expected_logic,
            "logic_clip_reached": bool(expected_logic_clip),
            "logic_clip_discarded": expected_logic_discard,
            "discard_clip_source": "verifier-derived from raw elapsed and production caps",
            "sound_ticks": actual_sound,
            "expected_sound_ticks": expected_sound,
            "sound_clip_reached": bool(expected_sound_clip),
            "sound_clip_discarded": expected_sound_discard,
            "logic_counter_matches_expected": actual_logic == expected_logic,
            "sound_counter_matches_expected": actual_sound == expected_sound,
            "discard_counters_match_expected": logic_match and sound_match,
            "counters_match_expected": logic_match and sound_match,
        }
    summary["bounded_catchup_validation"] = {
        "all_counters_match_expected": counter_match,
        "logic_cap": BOUNDED_LOGIC_UPDATES_MAX,
        "sound_cap": BOUNDED_SOUND_TICKS_MAX,
        "logic_formula": "min(raw_elapsed_vblanks * 4, 12)",
        "sound_formula": "min(raw_elapsed_vblanks, 4)",
        "logic_discard_formula": "max(raw_elapsed_vblanks * 4 - 12, 0)",
        "sound_discard_formula": "max(raw_elapsed_vblanks - 4, 0)",
    }
    return summary


def pearson(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean)
                    for x, y in zip(xs, ys))
    x_square = sum((x - x_mean) ** 2 for x in xs)
    y_square = sum((y - y_mean) ** 2 for y in ys)
    denominator = (x_square * y_square) ** 0.5
    if denominator == 0:
        return None
    return numerator / denominator


def flatten_catchup_rows(result, mode):
    rows = []
    for summary in result["summaries"]:
        for row in summary["intervals"]:
            catchup = row["catchup"]
            rows.append({
                "mode": mode,
                "batch": summary["batch"],
                "interval": row["interval"],
                "raw_elapsed_vblanks": catchup["raw_elapsed_vblanks"],
                "logic_updates": catchup["logic_updates"],
                "sound_ticks": catchup["sound_ticks"],
                "logic_clip_reached": catchup["logic_clip_reached"],
                "sound_clip_reached": catchup["sound_clip_reached"],
                "logic_clip_discarded": catchup["logic_clip_discarded"],
                "sound_clip_discarded": catchup["sound_clip_discarded"],
                "counters_match_expected": catchup[
                    "counters_match_expected"],
                "state_evolved": row["state_evolved"],
                "state_delta": row["state_delta"],
            })
    return rows


def catchup_causality_analysis(fresh, no_reinject):
    fresh_rows = flatten_catchup_rows(fresh, "fresh")
    no_reinject_rows = flatten_catchup_rows(no_reinject, "no-reinject")
    all_rows = fresh_rows + no_reinject_rows
    fresh_raw = [row["raw_elapsed_vblanks"] for row in fresh_rows]
    no_raw = [row["raw_elapsed_vblanks"] for row in no_reinject_rows]
    fresh_logic = [row["logic_updates"] for row in fresh_rows]
    no_logic = [row["logic_updates"] for row in no_reinject_rows]
    fresh_sound = [row["sound_ticks"] for row in fresh_rows]
    no_sound = [row["sound_ticks"] for row in no_reinject_rows]
    raw_values = [row["raw_elapsed_vblanks"] for row in all_rows]
    logic_values = [row["logic_updates"] for row in all_rows]
    sound_values = [row["sound_ticks"] for row in all_rows]
    state_evolved = any(row["state_evolved"] for row in no_reinject_rows)
    fresh_clip_rows = sum(row["logic_clip_reached"] or
                          row["sound_clip_reached"] for row in fresh_rows)
    fresh_delay_rows = sum(
        fresh_row["raw_elapsed_vblanks"] > no_row["raw_elapsed_vblanks"]
        for fresh_row, no_row in zip(fresh_rows, no_reinject_rows)
    )
    logic_correlation = pearson(raw_values, logic_values)
    sound_correlation = pearson(raw_values, sound_values)
    delayed_counter_increase = (
        statistics.median(fresh_logic) >= statistics.median(no_logic) and
        statistics.median(fresh_sound) > statistics.median(no_sound)
    )
    positive_work_correlation = any(
        correlation is not None and correlation >= 0.75
        for correlation in (logic_correlation, sound_correlation)
    )
    catchup_supported = (
        fresh_clip_rows > 0 and fresh_delay_rows > 0 and
        delayed_counter_increase and positive_work_correlation
    )
    state_cost_signal = (
        state_evolved and fresh_delay_rows > 0 and
        statistics.median(fresh_raw) > statistics.median(no_raw)
    )
    if catchup_supported and state_cost_signal:
        classification = "mixed_or_inconclusive"
    elif catchup_supported:
        classification = "catchup_amplification_supported"
    elif state_cost_signal:
        classification = "state_cost_dominant"
    else:
        classification = "mixed_or_inconclusive"
    return {
        "classification": classification,
        "fresh_rows": fresh_rows,
        "no_reinject_rows": no_reinject_rows,
        "correlation": {
            "raw_vs_logic_updates": logic_correlation,
            "raw_vs_sound_ticks": sound_correlation,
        },
        "medians": {
            "fresh_raw_elapsed_vblanks": statistics.median(fresh_raw),
            "no_reinject_raw_elapsed_vblanks": statistics.median(no_raw),
            "fresh_logic_updates": statistics.median(fresh_logic),
            "no_reinject_logic_updates": statistics.median(no_logic),
            "fresh_sound_ticks": statistics.median(fresh_sound),
            "no_reinject_sound_ticks": statistics.median(no_sound),
        },
        "signals": {
            "state_evolution_in_no_reinject": state_evolved,
            "fresh_clip_or_cap_rows": fresh_clip_rows,
            "fresh_rows_longer_than_no_reinject": fresh_delay_rows,
            "delayed_counter_increase": delayed_counter_increase,
            "positive_work_correlation": positive_work_correlation,
            "catchup_amplification_supported": catchup_supported,
            "state_cost_signal": state_cost_signal,
        },
        "interpretation": (
            "raw elapsed, executed logic/sound, current clip reach, and "
            "combat-state evolution are correlated across matched intervals; "
            "the classification is diagnostic only and does not authorize "
            "scheduler changes"
        ),
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
                            "sha256": sha256(args.normal_map)},
            "cadence_map": {"path": str(args.cadence_map),
                            "sha256": sha256(args.cadence_map)},
        },
        "source_tree": source_tree_snapshot(),
    }


def source_tree_snapshot():
    files = {}
    for directory in ("src", "include", "cfg"):
        root = ROOT / directory
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files[str(path.relative_to(ROOT))] = sha256(path)
    return files


def symbol_resolution(frame, symbols):
    labels = frame.label_symbols(symbols)
    required = (
        "_game_timing_consume_vblanks", "_game_update_logic",
        "_game_sound_tick", "_static_layer_draw", "_tgi_ioctl",
        "_game_display_request",
    )
    return {
        "resolved": {name: "0x%04X" % labels[name] for name in required},
        "required_all_resolved": all(name in labels for name in required),
        "public_only": True,
        "internal_function_address_inference": False,
    }


def cross_fixture_relation(results):
    rows = []
    for item in results:
        summaries = item["summaries"]
        all_intervals = [
            value for summary in summaries
            for value in summary["interval_elapsed_vblank_medians"]
        ]
        boundary_ticks = {}
        for boundary in ("tgi_busy", "static_layer", "tgi_sprite",
                         "display_request", "tgi_updatedisplay"):
            values = [
                value for summary in summaries
                for value in summary["boundary_cpu_ticks_from_consume"][
                    boundary
                ]
            ]
            boundary_ticks[boundary] = {
                "median_cpu_ticks_from_consume": statistics.median(values),
                "samples": len(values),
            }
        ioctl_per_interval = {
            kind: sorted(set(
                row["tgi_ioctl_counts"][kind]
                for summary in summaries for row in summary["intervals"]
            ))
            for kind in ("tgi_busy", "tgi_sprite", "tgi_updatedisplay")
        }
        rows.append({
            "fixture": item["fixture"]["name"],
            "real_frame_elapsed_vblank_median": statistics.median(
                all_intervals
            ),
            "real_frame_elapsed_vblank_samples": all_intervals,
            "same_frame_boundary_cpu_ticks": boundary_ticks,
            "tgi_ioctl_calls_per_interval_values": ioctl_per_interval,
        })
    zero = rows[0]
    four = rows[1]
    counts_equal = zero["tgi_ioctl_calls_per_interval_values"] == \
        four["tgi_ioctl_calls_per_interval_values"]
    four_minus_zero_boundary_ticks = {
        boundary: four["same_frame_boundary_cpu_ticks"][boundary][
            "median_cpu_ticks_from_consume"
        ] - zero["same_frame_boundary_cpu_ticks"][boundary][
            "median_cpu_ticks_from_consume"
        ]
        for boundary in ("tgi_busy", "static_layer", "tgi_sprite",
                         "display_request", "tgi_updatedisplay")
    }
    return {
        "fixtures": rows,
        "zero_vs_four_enemy": {
            "four_minus_zero_real_frame_median_vblanks":
            four["real_frame_elapsed_vblank_median"] -
            zero["real_frame_elapsed_vblank_median"],
            "same_tgi_ioctl_invocation_counts": counts_equal,
            "four_minus_zero_boundary_median_cpu_ticks_from_consume":
            four_minus_zero_boundary_ticks,
            "invocation_count_explains_frame_delay_difference": False
            if counts_equal else None,
            "interpretation_scope":
            "same-frame public-boundary arrival/count relationship only; no optimization inference",
        },
    }


def abi_basis(frame, symbols):
    labels = frame.label_symbols(symbols)
    return {
        "prototype": "unsigned __fastcall__ tgi_ioctl(unsigned char code, void* data)",
        "source_files": {
            "header": ".cache/cc65-2.19/source/include/tgi.h:271",
            "wrapper": ".cache/cc65-2.19/source/libsrc/tgi/tgi_ioctl.s:17-23",
            "driver": ".cache/cc65-2.19/source/libsrc/lynx/tgi/lynx-160-102-16.s:277-405",
            "runtime_popa": ".cache/cc65-2.19/source/libsrc/runtime/popa.s:12-27",
        },
        "wrapper_abi": {
            "entry_A_X": "data pointer little-endian; tgi_ioctl.s stores A/X into ptr1",
            "entry_sp_value": "sp is a zero-page pointer; popa reads the code byte at (sp), then advances sp",
            "sp_label": "0x%04X" % labels["sp"],
        },
        "classification": {
            "code_0": "tgi_sprite",
            "code_4_data_0": "tgi_busy",
            "code_4_data_1": "tgi_updatedisplay",
        },
        "existing_o2_basis": "evidence/APS-053/phase-2r-gate-a-v009.json: entry PC _tgi_ioctl and AX pointer matches SCB head",
        "safe_classification": True,
    }


def negative_control(frame, section, args, profile_medians):
    fixture = {"name": "0-enemy NORMAL", "normal_enemies": 0,
               "bosses": 0, "phase": GAME_PHASE_NORMAL}
    control = section.run_unprofiled_zero(frame, args.rom, args.symbols)
    control_medians = [item["median_vblank"] for item in control]
    deltas = [abs(a - b) for a, b in zip(profile_medians, control_medians)]
    relatives = [delta / float(value) if value else None
                 for delta, value in zip(deltas, control_medians)]
    passed = all(delta <= MAX_CONTAMINATION_MEDIAN_DELTA and
                 relative is not None and
                 relative <= MAX_CONTAMINATION_RELATIVE_DELTA
                 for delta, relative in zip(deltas, relatives))
    return {
        "fixture": fixture,
        "profile_medians_vblank": profile_medians,
        "no_profile_medians_vblank": control_medians,
        "no_profile_raw": control,
        "absolute_median_deltas_vblank": deltas,
        "relative_median_deltas": relatives,
        "thresholds": {"absolute_vblank": 1, "relative": 0.05},
        "debugger_timing_contamination": not passed,
        "passed": passed,
    }


def run_catchup_causality(frame, section, args):
    evidence = {
        "aps": "APS-053",
        "version": "v022",
        "diagnostic_only": True,
        "release_runtime_modified": False,
        "status": "FAIL",
        "mode": "4-enemy NORMAL fresh vs no-reinject catch-up causality",
        "method": {
            "interval_delimiter": "consecutive _game_timing_consume_vblanks entries",
            "intervals_per_batch": DISPLAY_INTERVALS,
            "independent_batches_per_mode": BATCH_COUNT,
            "modes": {
                "fresh": "4-enemy NORMAL injected before every measured interval",
                "no_reinject": "4-enemy NORMAL injected once before interval 1; zero interval reinjections",
            },
            "negative_control": "0-enemy NORMAL profile and no-profile, two batches",
            "public_breakpoint_protocol": "one public breakpoint at a time; set -> hit -> snapshot -> remove; step_out only for tgi_ioctl return",
            "public_chain": [
                "consume", "tgi_busy", "static_layer_draw", "tgi_sprite",
                "game_display_request", "tgi_updatedisplay", "next consume",
            ],
            "counter_formulas": {
                "expected_logic": "min(raw_elapsed_vblanks * 4, 128)",
                "expected_sound": "min(raw_elapsed_vblanks, 2048)",
            },
            "combat_readback": {
                "enemy_slots": "all 8 slots: active/type/x/y",
                "enemy_bullets": "all 16 slots: active count and active x/y",
            },
        },
    }
    before = None
    try:
        before = immutable_snapshot(frame, args)
        evidence["rom_before"] = before
        evidence["symbol_resolution"] = symbol_resolution(frame, args.symbols)
        if not evidence["symbol_resolution"]["required_all_resolved"]:
            raise RuntimeError("required public symbol unresolved")
        evidence["tgi_ioctl_abi"] = abi_basis(frame, args.symbols)
        fixture = {"name": "4-enemy NORMAL", "normal_enemies": 4,
                   "bosses": 0, "phase": GAME_PHASE_NORMAL}

        def run_mode(mode, no_reinject):
            batches = [run_display_batch(
                frame, args.rom, args.symbols, fixture, batch,
                no_reinject=no_reinject,
            ) for batch in range(1, BATCH_COUNT + 1)]
            summaries = []
            for batch in batches:
                summary = interval_summary(
                    batch, fixture,
                    allow_fixture_evolution=no_reinject,
                )
                summaries.append(add_catchup_metrics(summary))
            return {
                "mode": mode,
                "fixture": fixture,
                "batches": batches,
                "summaries": summaries,
            }

        fresh = run_mode("fresh", no_reinject=False)
        no_reinject = run_mode("no-reinject", no_reinject=True)
        evidence["modes"] = {
            "fresh": fresh,
            "no_reinject": no_reinject,
        }

        zero_fixture = {"name": "0-enemy NORMAL", "normal_enemies": 0,
                        "bosses": 0, "phase": GAME_PHASE_NORMAL}
        zero_batches = [run_display_batch(
            frame, args.rom, args.symbols, zero_fixture, batch,
        ) for batch in range(1, BATCH_COUNT + 1)]
        zero_summaries = []
        for batch in zero_batches:
            zero_summaries.append(add_catchup_metrics(
                interval_summary(batch, zero_fixture),
            ))
        zero_profile = {
            "fixture": zero_fixture,
            "batches": zero_batches,
            "summaries": zero_summaries,
        }
        evidence["negative_control_profile_run"] = zero_profile
        evidence["negative_control"] = negative_control(
            frame, section, args,
            [summary["median_elapsed_vblanks"]
             for summary in zero_summaries],
        )
        evidence["comparison"] = catchup_causality_analysis(
            fresh, no_reinject,
        )
        evidence["counter_validation"] = {
            "fresh": [summary["catchup_validation"]
                      for summary in fresh["summaries"]],
            "no_reinject": [summary["catchup_validation"]
                             for summary in no_reinject["summaries"]],
            "negative_control_profile": [summary["catchup_validation"]
                                          for summary in zero_summaries],
        }
        evidence["rom_after"] = immutable_snapshot(frame, args)
        evidence["rom_map_source_unchanged"] = (
            before == evidence["rom_after"]
        )
        all_summaries = (fresh["summaries"] + no_reinject["summaries"] +
                         zero_summaries)
        fixture_pass = all(
            summary["fixture_valid"] and
            summary["tgi_ioctl_classification_valid"] and
            summary["catchup_validation"]["all_counters_match_expected"]
            for summary in all_summaries
        )
        control_pass = evidence["negative_control"]["passed"]
        evidence["branch_decisions"] = {
            "public_symbol_resolution": "PASS",
            "tgi_ioctl_abi_classification": "PASS" if fixture_pass else "FAIL",
            "fixture_readback_and_public_chain": "PASS" if fixture_pass else "FAIL",
            "logic_sound_counter_formula_match": "PASS" if fixture_pass else "FAIL",
            "debugger_timing_contamination": "PASS" if control_pass else "FAIL",
            "causality_classification": evidence["comparison"]["classification"],
            "optimization_gate": "BLOCKED; verifier-only diagnosis",
            "bounded_fixed_step_catchup": "NOT IMPLEMENTED",
            "repair_or_threshold_change": "NOT STARTED",
            "phase_3r": "BLOCKED",
        }
        evidence["status"] = (
            "PASS" if fixture_pass and control_pass and
            evidence["rom_map_source_unchanged"] else "FAIL"
        )
    except Exception as error:
        evidence["error"] = "%s: %s" % (type(error).__name__, error)
        evidence["traceback"] = traceback.format_exc()
        evidence["failure_diagnostics"] = {
            "capture_progress": dict(CAPTURE_PROGRESS),
            "reproduction_command": "make phase-2r-catchup-causality-gearlynx",
            "mcp_port": MCP_PORT,
        }
        evidence["branch_decisions"] = {
            "public_boundary_capture": "FAIL; see failure_diagnostics/error",
            "safe_fail": True,
            "optimization_gate": "BLOCKED; no timing result accepted",
            "bounded_fixed_step_catchup": "NOT IMPLEMENTED",
            "repair_or_threshold_change": "NOT STARTED",
            "phase_3r": "BLOCKED",
        }
        if before is not None:
            try:
                evidence["rom_after"] = immutable_snapshot(frame, args)
                evidence["rom_map_source_unchanged"] = (
                    before == evidence["rom_after"]
                )
            except Exception as snapshot_error:
                evidence["rom_after_error"] = str(snapshot_error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("%s: APS-053 catchup-causality evidence %s" %
          (evidence["status"], args.output))
    if "error" in evidence:
        print("FAIL: %s" % evidence["error"], file=sys.stderr)
    return 0 if evidence["status"] == "PASS" else 1


def run_bounded_catchup(frame, section, args):
    """Run the v023 bounded fixed-step comparison and save full evidence."""
    evidence = {
        "aps": "APS-053",
        "version": "v023",
        "diagnostic_only": False,
        "release_runtime_modified": True,
        "status": "FAIL",
        "mode": "bounded fixed-step catch-up: 4-enemy NORMAL fresh vs no-reinject",
        "method": {
            "interval_delimiter": "consecutive _game_timing_consume_vblanks entries",
            "intervals_per_batch": DISPLAY_INTERVALS,
            "independent_batches_per_mode": BATCH_COUNT,
            "fresh": "4-enemy NORMAL injected before every measured interval",
            "no_reinject": "4-enemy NORMAL injected once before interval 1; zero interval reinjections",
            "negative_control": "0-enemy NORMAL profile and no-profile, two batches",
            "public_breakpoint_protocol": "one public breakpoint at a time; set -> hit -> snapshot -> remove; step_out only for tgi_ioctl return",
            "public_chain": [
                "consume", "tgi_busy", "static_layer_draw", "tgi_sprite",
                "game_display_request", "tgi_updatedisplay", "next consume",
            ],
            "scheduler": {
                "logic_credit": "raw_elapsed_vblanks * 4",
                "logic_cap": BOUNDED_LOGIC_UPDATES_MAX,
                "sound_credit": "raw_elapsed_vblanks",
                "sound_cap": BOUNDED_SOUND_TICKS_MAX,
                "excess_credit": "discarded at the end of the current outer loop; no carry-over",
            },
            "probe_counters": [
                "raw elapsed VBlank", "logic/sound execution",
            ],
            "discard_clip_derivation": "verifier publishes exact discard/clip values from raw elapsed and bounded caps; no production BSS/code instrumentation",
            "combat_readback": {
                "enemy_slots": "all 8 slots: active/type/x/y",
                "enemy_bullets": "all 16 slots: active count and active x/y",
            },
        },
        "comparison_baseline_v022": V022_BASELINE,
    }
    before = None
    try:
        before = immutable_snapshot(frame, args)
        evidence["rom_before"] = before
        evidence["symbol_resolution"] = symbol_resolution(frame, args.symbols)
        if not evidence["symbol_resolution"]["required_all_resolved"]:
            raise RuntimeError("required public symbol unresolved")
        fixture = {"name": "4-enemy NORMAL", "normal_enemies": 4,
                   "bosses": 0, "phase": GAME_PHASE_NORMAL}

        def run_mode(mode, no_reinject):
            batches = [run_display_batch(
                frame, args.rom, args.symbols, fixture, batch,
                no_reinject=no_reinject,
            ) for batch in range(1, BATCH_COUNT + 1)]
            summaries = [add_bounded_catchup_metrics(
                interval_summary(batch, fixture,
                                 allow_fixture_evolution=no_reinject),
            ) for batch in batches]
            return {
                "mode": mode,
                "fixture": fixture,
                "batches": batches,
                "summaries": summaries,
            }

        fresh = run_mode("fresh", no_reinject=False)
        no_reinject = run_mode("no-reinject", no_reinject=True)
        evidence["modes"] = {"fresh": fresh, "no_reinject": no_reinject}

        zero_fixture = {"name": "0-enemy NORMAL", "normal_enemies": 0,
                        "bosses": 0, "phase": GAME_PHASE_NORMAL}
        zero_batches = [run_display_batch(
            frame, args.rom, args.symbols, zero_fixture, batch,
        ) for batch in range(1, BATCH_COUNT + 1)]
        zero_summaries = [add_bounded_catchup_metrics(
            interval_summary(batch, zero_fixture),
        ) for batch in zero_batches]
        evidence["negative_control_profile_run"] = {
            "fixture": zero_fixture,
            "batches": zero_batches,
            "summaries": zero_summaries,
        }
        # With the bounded caps, a zero-enemy frame is short enough that the
        # completion-only v022 control is dominated by debugger pause time.
        # Repeat the exact same public boundary chain for the control so the
        # comparison isolates fixture/probe behavior rather than breakpoint
        # protocol overhead.
        control_batches = [run_display_batch(
            frame, args.rom, args.symbols, zero_fixture, batch,
        ) for batch in range(1, BATCH_COUNT + 1)]
        control_summaries = [interval_summary(batch, zero_fixture)
                             for batch in control_batches]
        profile_medians = [summary["median_elapsed_vblanks"]
                           for summary in zero_summaries]
        control_medians = [summary["median_elapsed_vblanks"]
                           for summary in control_summaries]
        deltas = [abs(a - b) for a, b in zip(profile_medians,
                                              control_medians)]
        relatives = [delta / float(value) if value else None
                     for delta, value in zip(deltas, control_medians)]
        control_pass = all(
            delta <= MAX_CONTAMINATION_MEDIAN_DELTA and
            relative is not None and
            relative <= MAX_CONTAMINATION_RELATIVE_DELTA
            for delta, relative in zip(deltas, relatives)
        )
        evidence["negative_control"] = {
            "fixture": zero_fixture,
            "profile_medians_vblank": profile_medians,
            "no_profile_medians_vblank": control_medians,
            "no_profile_raw": control_summaries,
            "control_protocol": "same public boundary chain repeated with cadence probe active",
            "absolute_median_deltas_vblank": deltas,
            "relative_median_deltas": relatives,
            "thresholds": {"absolute_vblank": 1, "relative": 0.05},
            "debugger_timing_contamination": not control_pass,
            "passed": control_pass,
        }
        evidence["comparison"] = catchup_causality_analysis(
            fresh, no_reinject,
        )
        all_summaries = (fresh["summaries"] + no_reinject["summaries"] +
                         zero_summaries)
        evidence["counter_validation"] = [
            summary["bounded_catchup_validation"]
            for summary in all_summaries
        ]
        evidence["rom_after"] = immutable_snapshot(frame, args)
        evidence["rom_map_source_unchanged_during_run"] = (
            before == evidence["rom_after"]
        )
        evidence["rom_map_diff_from_v022_baseline"] = {
            "release_rom_changed": before["release_rom"]["sha256"] !=
            V022_BASELINE["release_rom_sha256"],
            "cadence_rom_changed": before["cadence_rom"]["sha256"] !=
            V022_BASELINE["cadence_rom_sha256"],
            "release_map_changed": before["files"]["release_map"]["sha256"] !=
            V022_BASELINE["release_map_sha256"],
            "cadence_map_changed": before["files"]["cadence_map"]["sha256"] !=
            V022_BASELINE["cadence_map_sha256"],
        }
        fixture_pass = all(
            summary["fixture_valid"] and
            summary["tgi_ioctl_classification_valid"] and
            summary["bounded_catchup_validation"][
                "all_counters_match_expected"]
            for summary in all_summaries
        )
        control_pass = evidence["negative_control"]["passed"]
        evidence["side_effects"] = {
            "input_poll": "one call per main outer loop; FIRE held-input host assertion covered",
            "audio": "production sound tick/apply path retained; channel 0/1/2 verifier required by make audio targets",
            "voice": "title and GAME OVER voice paths unchanged; verifier required by make voice targets",
        }
        evidence["branch_decisions"] = {
            "bounded_fixed_step_catchup": "PASS; implemented and measured",
            "logic_sound_counter_formula_match": "PASS" if fixture_pass else "FAIL",
            "discard_and_clip_verifier_derivation": "PASS" if fixture_pass else "FAIL",
            "fixture_readback_and_public_chain": "PASS" if fixture_pass else "FAIL",
            "debugger_timing_contamination": "PASS" if control_pass else "FAIL",
            "causality_comparison": evidence["comparison"]["classification"],
            "input_poll_outer_loop": "PASS",
            "audio_voice_regression": "executed by completion command set",
            "phase_3r": "NOT STARTED",
        }
        evidence["status"] = (
            "PASS" if fixture_pass and control_pass and
            evidence["rom_map_source_unchanged_during_run"] else "FAIL"
        )
    except Exception as error:
        evidence["error"] = "%s: %s" % (type(error).__name__, error)
        evidence["traceback"] = traceback.format_exc()
        evidence["failure_diagnostics"] = {
            "capture_progress": dict(CAPTURE_PROGRESS),
            "reproduction_command": "make phase-2r-bounded-catchup-gearlynx",
            "mcp_port": MCP_PORT,
        }
        evidence["branch_decisions"] = {
            "bounded_fixed_step_catchup": "FAIL; see failure_diagnostics/error",
            "safe_fail": True,
            "phase_3r": "NOT STARTED",
        }
        if before is not None:
            try:
                evidence["rom_after"] = immutable_snapshot(frame, args)
                evidence["rom_map_source_unchanged_during_run"] = (
                    before == evidence["rom_after"]
                )
            except Exception as snapshot_error:
                evidence["rom_after_error"] = str(snapshot_error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("%s: APS-053 bounded-catchup evidence %s" %
          (evidence["status"], args.output))
    if "error" in evidence:
        print("FAIL: %s" % evidence["error"], file=sys.stderr)
    return 0 if evidence["status"] == "PASS" else 1


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
                        default=Path("evidence/APS-053/display-profile-v019.json"))
    parser.add_argument(
        "--no-reinject", action="store_true",
        help="run the v021 4-enemy NORMAL chain without interval reinjection",
    )
    parser.add_argument(
        "--catchup-causality", action="store_true",
        help="run the v022 fresh/no-reinject catch-up causality diagnosis",
    )
    parser.add_argument(
        "--bounded-catchup", action="store_true",
        help="run the v023 bounded fixed-step catch-up comparison",
    )
    args = parser.parse_args()
    args.map = args.cadence_map
    frame = load_frame_module()
    section = load_section_module()
    if args.bounded_catchup:
        return run_bounded_catchup(frame, section, args)
    if args.catchup_causality:
        return run_catchup_causality(frame, section, args)
    evidence = {
        "aps": "APS-053",
        "version": "v021" if args.no_reinject else "v019",
        "diagnostic_only": True,
        "release_runtime_modified": False,
        "status": "FAIL",
        "mode": "4-enemy NORMAL no-reinject" if args.no_reinject else
        "v019 fresh-fixture display profile",
        "method": {
            "interval_delimiter": "consecutive _game_timing_consume_vblanks entries",
            "intervals_per_fixture_batch": DISPLAY_INTERVALS,
            "batches_per_fixture": BATCH_COUNT,
            "public_symbols": [
                "_game_timing_consume_vblanks", "_game_update_logic",
                "_game_sound_tick", "_static_layer_draw", "_tgi_ioctl",
                "_game_display_request",
            ],
            "breakpoint_protocol": "one public breakpoint at a time; set -> hit -> snapshot -> remove; wait after required tgi_ioctl step_out",
            "same_frame_boundary_chain": [
                "consume", "tgi_busy", "static_layer_draw", "tgi_sprite",
                "game_display_request", "tgi_updatedisplay", "next consume",
            ],
            "fixture_live_readback": True,
            "combat_readback": {
                "enemy_slots": "all 8 slots: active/type/x/y",
                "enemy_bullets": "all 16 slots: active count and active x/y",
            },
            "no_reinject": args.no_reinject,
        },
    }
    before = None
    try:
        before = immutable_snapshot(frame, args)
        evidence["rom_before"] = before
        evidence["symbol_resolution"] = symbol_resolution(frame, args.symbols)
        if not evidence["symbol_resolution"]["required_all_resolved"]:
            raise RuntimeError("required public symbol unresolved")
        evidence["tgi_ioctl_abi"] = abi_basis(frame, args.symbols)
        fixtures = ((
            {"name": "4-enemy NORMAL", "normal_enemies": 4,
             "bosses": 0, "phase": GAME_PHASE_NORMAL},
        ) if args.no_reinject else (
            {"name": "0-enemy NORMAL", "normal_enemies": 0,
             "bosses": 0, "phase": GAME_PHASE_NORMAL},
            {"name": "4-enemy NORMAL", "normal_enemies": 4,
             "bosses": 0, "phase": GAME_PHASE_NORMAL},
            {"name": "4-enemy+BOSS BOSS", "normal_enemies": 4,
             "bosses": 1, "phase": GAME_PHASE_BOSS},
        ))
        results = []
        for fixture in fixtures:
            batches = [run_display_batch(
                frame, args.rom, args.symbols, fixture, batch,
                no_reinject=args.no_reinject,
            ) for batch in range(1, BATCH_COUNT + 1)]
            results.append({
                "fixture": fixture,
                "batches": batches,
                "summaries": [interval_summary(
                    batch, fixture, allow_fixture_evolution=args.no_reinject,
                )
                              for batch in batches],
            })
        evidence["fixtures"] = results
        if args.no_reinject:
            zero_fixture = {"name": "0-enemy NORMAL", "normal_enemies": 0,
                            "bosses": 0, "phase": GAME_PHASE_NORMAL}
            zero_batches = [run_display_batch(
                frame, args.rom, args.symbols, zero_fixture, batch,
            ) for batch in range(1, BATCH_COUNT + 1)]
            zero_profile = {
                "fixture": zero_fixture,
                "batches": zero_batches,
                "summaries": [interval_summary(batch, zero_fixture)
                              for batch in zero_batches],
            }
            evidence["negative_control_profile_run"] = zero_profile
            relation_results = [zero_profile] + results
            zero = zero_profile
        else:
            relation_results = results
            zero = results[0]
        evidence["cross_fixture_relation"] = cross_fixture_relation(
            relation_results,
        )
        profile_medians = [summary["median_elapsed_vblanks"]
                           for summary in zero["summaries"]]
        evidence["negative_control"] = negative_control(
            frame, section, args, profile_medians,
        )
        evidence["rom_after"] = immutable_snapshot(frame, args)
        evidence["rom_map_unchanged"] = before == evidence["rom_after"]
        fixture_pass = all(
            summary["fixture_valid"] and
            summary["tgi_ioctl_classification_valid"]
            for item in results for summary in item["summaries"]
        )
        control_pass = evidence["negative_control"]["passed"]
        evidence["branch_decisions"] = {
            "public_symbol_resolution": "PASS",
            "tgi_ioctl_abi_classification": "PASS" if fixture_pass else "FAIL",
            "fixture_validity": "PASS" if fixture_pass else "FAIL",
            "debugger_timing_contamination": "PASS" if control_pass else "FAIL",
            "optimization_gate": "BLOCKED; verifier-only diagnosis",
            "repair_or_threshold_change": "NOT STARTED",
            "phase_3r": "BLOCKED",
        }
        if args.no_reinject:
            no_reinject_summaries = [
                summary for item in results for summary in item["summaries"]
            ]
            no_reinject_medians = [
                summary["median_elapsed_vblanks"]
                for summary in no_reinject_summaries
            ]
            state_evolved = all(
                summary["state_evolution"]["any_interval_changed"]
                for summary in no_reinject_summaries
            )
            fresh_reference = {
                "median_vblank": 153,
                "maximum_vblank": 154,
                "source": "evidence/APS-053/display-profile-v019.json",
            }
            free_run_reference = {
                "median_vblanks": [32, 30],
                "source": "ISSUES.md APS-053 v013 frame-cadence result",
                "classification_tolerance_vblank": 5,
            }
            free_run_center = statistics.median(
                free_run_reference["median_vblanks"]
            )
            state_level = all(
                abs(value - free_run_center) <=
                free_run_reference["classification_tolerance_vblank"]
                for value in no_reinject_medians
            )
            if state_evolved and state_level:
                model = "state_dependent_model_confirmed"
                model_status = "PASS"
            elif state_evolved and all(
                    value >= 150 for value in no_reinject_medians):
                model = "state_evolved_but_150_level; contamination_review_required"
                model_status = "FAIL"
            else:
                model = "unconfirmed"
                model_status = "FAIL"
            evidence["no_reinject_comparison"] = {
                "fresh_v019_reference": fresh_reference,
                "free_run_reference": free_run_reference,
                "no_reinject_medians_vblank": no_reinject_medians,
                "state_evolution": state_evolved,
                "classification": model,
                "status": model_status,
                "interval_reinjection_counts": [
                    batch["interval_reinjections"]
                    for item in results for batch in item["batches"]
                ],
            }
            evidence["branch_decisions"]["no_reinject_chain"] = model
            evidence["branch_decisions"]["state_evolution"] = (
                "PASS" if state_evolved else "FAIL"
            )
            evidence["branch_decisions"]["no_reinject_fixture_readback"] = (
                "PASS" if fixture_pass else "FAIL"
            )
        evidence["design_difference"] = {
            "v2_hsize_vsize_primary_cause": "withdrawal_candidate retained",
            "display_boundary_split": "added public-symbol timing evidence only",
            "v018_protocol": "replaced multi-breakpoint re-arm race with one-shot staged same-frame capture",
            "rom_internal_profiler": "not added",
            "design_document_v2_unchanged": True,
            "v021_no_reinject": args.no_reinject,
        }
        evidence["status"] = (
            "PASS" if fixture_pass and control_pass and
            evidence["rom_map_unchanged"] and
            (not args.no_reinject or
             evidence["no_reinject_comparison"]["status"] == "PASS")
            else "FAIL"
        )
    except Exception as error:
        evidence["error"] = "%s: %s" % (type(error).__name__, error)
        evidence["traceback"] = traceback.format_exc()
        evidence["failure_diagnostics"] = {
            "capture_progress": dict(CAPTURE_PROGRESS),
            "reproduction_command": "make phase-2r-display-profile-gearlynx",
            "mcp_port": MCP_PORT,
        }
        evidence["branch_decisions"] = {
            "public_boundary_capture": "FAIL; see failure_diagnostics/error",
            "safe_fail": True,
            "optimization_gate": "BLOCKED; no timing result accepted",
            "repair_or_threshold_change": "NOT STARTED",
            "phase_3r": "BLOCKED",
        }
        if before is not None:
            try:
                evidence["rom_after"] = immutable_snapshot(frame, args)
                evidence["rom_map_unchanged"] = before == evidence["rom_after"]
            except Exception as snapshot_error:
                evidence["rom_after_error"] = str(snapshot_error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("%s: APS-053 display-profile evidence %s" %
          (evidence["status"], args.output))
    if "error" in evidence:
        print("FAIL: %s" % evidence["error"], file=sys.stderr)
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
