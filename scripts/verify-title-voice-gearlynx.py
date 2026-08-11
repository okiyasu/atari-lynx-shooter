#!/usr/bin/env python3
"""Verify both 7,936.508 Hz channel-D voices, stop, and transitions."""

import argparse
import base64
import importlib.util
import json
import subprocess
import sys
import time
import urllib.request
import re
from pathlib import Path

GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17767
TITLE_VOICE_SAMPLE_COUNT = 17408
GAME_OVER_VOICE_SAMPLE_COUNT = 11691
TITLE_VOICE_TIMER_BACKUP = 125
TITLE_VOICE_TIMER_CONTROL = 0xD8
TITLE_VOICE_TIMER_PERIOD_US = TITLE_VOICE_TIMER_BACKUP + 1
TITLE_VOICE_RATE_HZ = 1_000_000 / TITLE_VOICE_TIMER_PERIOD_US
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}
GAME_OFFSET_IN_MAIN_BSS = 12
GAME_OFFSET_LIVES = 190
GAME_OFFSET_GAME_OVER = 191
GAME_OFFSET_RESTART_ARMED = 192
GAME_OFFSET_TITLE_START_ARMED = 193
GAME_OFFSET_TITLE_VOICE_PENDING = 194
GAME_OFFSET_GAME_OVER_VOICE_PENDING = 195
GAME_OFFSET_GAME_OVER_VOICE_COMPLETE = 196
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PHASE = 210
GAME_OFFSET_SOUND = 213
GAME_OFFSET_SFX_STATE = GAME_OFFSET_SOUND + 6
GAME_OFFSET_OUTPUT_SFX = GAME_OFFSET_SOUND + 18


def main_bss_game_address(map_path):
    text = Path(map_path).read_text(encoding="utf-8")
    segment = re.search(r"^BSS\s+([0-9A-F]{6})\s", text, re.MULTILINE)
    module = re.search(
        r"^main\.o:\n(?:.*\n)*?\s+BSS\s+Offs=([0-9A-F]{6})\s+",
        text,
        re.MULTILINE,
    )
    if segment is None or module is None:
        raise RuntimeError("cannot locate main.o BSS in linker map")
    return (
        int(segment.group(1), 16)
        + int(module.group(1), 16)
        + GAME_OFFSET_IN_MAIN_BSS
    )


def label_address(symbols_path, symbol):
    for line in Path(symbols_path).read_text(encoding="utf-8").splitlines():
        match = re.match(r"^al\s+([0-9A-Fa-f]{6})\s+\." +
                         re.escape(symbol) + r"$", line)
        if match:
            return int(match.group(1), 16)
    raise RuntimeError(f"cannot locate {symbol} in label file")


def map_value(map_path, symbol):
    text = Path(map_path).read_text(encoding="utf-8")
    match = re.search(
        r"(?:^|\s)" + re.escape(symbol) + r"\s+([0-9A-Fa-f]{6})\s+",
        text, re.MULTILINE,
    )
    if match is None:
        raise RuntimeError(f"cannot locate {symbol} in linker map")
    return int(match.group(1), 16)


def stack_end_exclusive(map_path):
    return (map_value(map_path, "__MAIN_START__") +
            map_value(map_path, "__MAIN_SIZE__") +
            map_value(map_path, "__STACKSIZE__"))


def bss_end_exclusive(map_path):
    text = Path(map_path).read_text(encoding="utf-8")
    match = re.search(
        r"^BSS\s+([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})\s+",
        text, re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("cannot locate BSS range in linker map")
    return int(match.group(2), 16) + 1


def write_bytes(address, values, id_):
    tool(
        "write_memory",
        {
            "area": 0,
            "offset": f"{address:04X}",
            "bytes": bytes(values).hex(" "),
        },
        id_=id_,
    )


def read_bytes(address, size, id_):
    memory = tool(
        "read_memory",
        {"area": 0, "offset": f"{address:04X}", "size": size},
        id_=id_,
    )
    return bytes.fromhex(memory["data"])


def wait_for_game_bytes(game_address, offset, size, predicate, id_, description):
    deadline = time.monotonic() + 5.0
    latest = None
    while time.monotonic() < deadline:
        latest = read_bytes(game_address + offset, size, id_)
        id_ += 1
        if predicate(latest):
            return latest, id_
        time.sleep(0.005)
    raise RuntimeError(f"timed out waiting for {description}: last={latest!r}")


def wait_until_paused(id_):
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        status = tool("debug_get_status", id_=id_)
        id_ += 1
        if status["paused"]:
            return id_
        time.sleep(0.005)
    raise RuntimeError("Gearlynx did not pause before state injection")


def wait_for_breakpoint(id_, description):
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = tool("debug_get_status", id_=id_)
        id_ += 1
        if status["paused"]:
            if not status["at_breakpoint"]:
                raise RuntimeError(f"paused before {description} breakpoint")
            return id_
        time.sleep(0.005)
    raise RuntimeError(f"timed out waiting for {description} breakpoint")


def continue_to_breakpoint(id_, description):
    tool("debug_continue", id_=id_)
    return wait_for_breakpoint(id_ + 1, description)


def call(method, params=None, id_=1):
    body = json.dumps(
        {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    ).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{MCP_PORT}/mcp", data=body, headers=HEADERS
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def tool(name, arguments=None, id_=1):
    result = call("tools/call", {"name": name, "arguments": arguments or {}}, id_)
    if "error" in result:
        raise RuntimeError(f"{name} failed: {result['error']}")
    content = result["result"]["content"][0]
    if content.get("type") == "image":
        return content
    return json.loads(content["text"])


def registers(channel, id_):
    state = tool("get_mikey_audio", {"channel": channel}, id_=id_)
    return state, {register[0]: register[2] for register in state["registers"]}


def timer_registers(timer, id_):
    state = tool("get_mikey_timers", {"timer": timer}, id_=id_)
    return state, {register[0]: register[2] for register in state["registers"]}


def trace_lines(id_):
    first = tool("get_trace_log", {"count": 1000, "start": 0}, id_)
    total = first["total_entries"]
    lines = list(first["lines"])
    start = first["count"]
    while start < total:
        page = tool("get_trace_log", {"count": 1000, "start": start}, id_ + start)
        lines.extend(page["lines"])
        start += page["count"]
    return lines


def title_voice_state_address(map_path):
    text = Path(map_path).read_text(encoding="utf-8")
    segment = re.search(r"^BSS\s+([0-9A-F]{6})\s", text, re.MULTILINE)
    module = re.search(
        r"^title_voice\.o:\n(?:.*\n)*?\s+BSS\s+Offs=([0-9A-F]{6})\s+"
        r"Size=([0-9A-F]{6})",
        text,
        re.MULTILINE,
    )
    if not segment or not module:
        raise RuntimeError("cannot locate title_voice.o BSS in linker map")
    # title_voice.c intentionally keeps underrun as its final BSS byte.
    return (
        int(segment.group(1), 16)
        + int(module.group(1), 16)
        + int(module.group(2), 16)
        - 1
    )


def load_voice_gain_reference():
    gain_path = Path(__file__).resolve().with_name("generate-title-voice-gain.py")
    spec = importlib.util.spec_from_file_location("title_voice_gain", gain_path)
    gain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gain)
    return gain


def expected_dac_samples(voice_path, count):
    generator_path = Path(__file__).resolve().with_name("generate-title-voice.py")
    spec = importlib.util.spec_from_file_location("title_voice_generator", generator_path)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    packed = Path(voice_path).read_bytes()
    predictor = 0
    step_index = 0
    gain = load_voice_gain_reference()
    raw_output = []
    gained_output = []
    for sample_index in range(count):
        byte = packed[sample_index // 2]
        code = byte & 0x0F if sample_index % 2 == 0 else byte >> 4
        step = generator.STEP_TABLE[step_index]
        difference = step >> 3
        if code & 1:
            difference += step >> 2
        if code & 2:
            difference += step >> 1
        if code & 4:
            difference += step
        predictor += -difference if code & 8 else difference
        predictor = max(-32768, min(32767, predictor))
        step_index += generator.INDEX_DELTA[code & 7]
        step_index = max(0, min(88, step_index))
        raw_dac = (predictor >> 8) & 0xFF
        raw_output.append(raw_dac)
        gained_output.append(gain.gain_dac_byte(raw_dac))
    return raw_output, gained_output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", default="dist/asteroid-patrol.lnx")
    parser.add_argument("--symbols", default="build/asteroid-patrol.lbl")
    parser.add_argument("--map", default="build/asteroid-patrol.map")
    parser.add_argument("--mode", choices=("title", "game-over"), default="title")
    parser.add_argument("--voice")
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--poll-interval", type=float, default=0.01)
    parser.add_argument("--screenshot", default="/tmp/gearlynx-title-voice-check.png")
    parser.add_argument(
        "--gui", action="store_true",
        help="launch the Gearlynx GUI while running the same checks",
    )
    args = parser.parse_args()
    if args.voice is None:
        args.voice = (
            "assets/voice/title-start.adpcm"
            if args.mode == "title"
            else "assets/voice/game-over.adpcm"
        )
    voice_sample_count = (
        TITLE_VOICE_SAMPLE_COUNT
        if args.mode == "title"
        else GAME_OVER_VOICE_SAMPLE_COUNT
    )

    command = [GEARLYNX]
    if not args.gui:
        command.append("--headless")
    command.extend([
        "--mcp-http", "--mcp-http-port", str(MCP_PORT),
        args.rom, args.symbols,
    ])
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                call(
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "ryoko-title-voice-verify",
                            "version": "0.1",
                        },
                    },
                )
                break
            except Exception:
                time.sleep(0.3)
        else:
            print("Gearlynx MCP server did not come up", file=sys.stderr)
            return 1

        game_address = main_bss_game_address(Path(args.map))
        stack_low_water_address = label_address(
            Path(args.symbols), "_game_timing_stack_low_water"
        )
        stack_floor = bss_end_exclusive(Path(args.map))
        stack_start = (
            map_value(Path(args.map), "__MAIN_START__") +
            map_value(Path(args.map), "__MAIN_SIZE__")
        )
        stack_top = stack_end_exclusive(Path(args.map))
        tool("debug_continue")
        initial, request_id = wait_for_game_bytes(
            game_address,
            GAME_OFFSET_STAGE,
            2,
            lambda state: state == bytes([1, 6]),
            2,
            "stable TITLE state",
        )
        if initial != bytes([1, 6]):
            raise RuntimeError("computed GameState address failed TITLE check")
        tool(
            "set_trace_log",
            {
                "enabled": True,
                "filters": {
                    "cart": False,
                    "cpu": False,
                    "cpu_irq": False,
                    "debug_messages": False,
                    "mikey_audio": True,
                    "mikey_timers": True,
                    "mikey_uart": False,
                    "suzy_input": False,
                    "suzy_math": False,
                    "suzy_sprites": False,
                },
            },
        )
        if args.mode == "title":
            _, request_id = wait_for_game_bytes(
                game_address,
                GAME_OFFSET_TITLE_START_ARMED,
                2,
                lambda state: state == bytes([1, 0]),
                request_id,
                "TITLE armed gate",
            )
            tool(
                "controller_macro",
                {"commands": [{"press": "a"}]},
                request_id,
            )
        else:
            print(
                "Gearlynx GAME OVER trigger: lives=0, dying=1, final explosion "
                "SFX final step; ROM update_player_death performs the transition"
            )
            tool("debug_pause", id_=2)
            request_id = wait_until_paused(3)
            write_bytes(game_address + GAME_OFFSET_LIVES, [0], request_id)
            request_id += 1
            write_bytes(
                game_address + GAME_OFFSET_GAME_OVER,
                [0, 0, 0, 0, 0, 0, 1],
                request_id,
            )
            request_id += 1
            write_bytes(game_address + GAME_OFFSET_STAGE, [1, 1], request_id)
            request_id += 1
            write_bytes(
                game_address + GAME_OFFSET_SFX_STATE,
                [5, 3, 1, 0],
                request_id,
            )
            request_id += 1
            write_bytes(
                game_address + GAME_OFFSET_OUTPUT_SFX,
                [1, 4, 9, 2],
                request_id,
            )
            request_id += 1
            tool("controller_macro", {"commands": [{"press": "a"}]}, id_=request_id)
            request_id += 1
            tool("debug_continue", id_=request_id)

        outputs = []
        nonzero = []
        stopped_samples = 0
        start = time.time()
        request_id = 100
        transitioned = False
        wait_observations = []
        wait_transition_elapsed = None
        wait_counter_values = []
        wait_counter_verified = False
        timer_state = None
        timer_regs = None
        active_screenshot = None
        while time.time() - start < args.timeout:
            _, regs = registers(3, request_id)
            request_id += 1
            output = int(regs.get("output", "0x00"), 16)
            elapsed = time.time() - start
            outputs.append(output)
            if args.mode == "title":
                game_state = read_bytes(
                    game_address + GAME_OFFSET_TITLE_START_ARMED,
                    GAME_OFFSET_SOUND - GAME_OFFSET_TITLE_START_ARMED + 1,
                    request_id,
                )
                request_id += 1
                wait_ticks = game_state[0]
                pending = game_state[
                    GAME_OFFSET_TITLE_VOICE_PENDING
                    - GAME_OFFSET_TITLE_START_ARMED
                ]
                phase = game_state[
                    GAME_OFFSET_PHASE - GAME_OFFSET_TITLE_START_ARMED
                ]
                bgm_active = game_state[
                    GAME_OFFSET_SOUND - GAME_OFFSET_TITLE_START_ARMED
                ]
                if phase == 6 and pending == 2:
                    wait_observations.append((elapsed, wait_ticks, bgm_active))
                elif phase != 6 and wait_observations and wait_transition_elapsed is None:
                    wait_transition_elapsed = elapsed
            if output != 0:
                nonzero.append((elapsed, output))
                stopped_samples = 0
                if args.mode == "game-over" and active_screenshot is None:
                    active_path = Path(args.screenshot)
                    active_screenshot = active_path.with_name(
                        active_path.stem + "-active" + active_path.suffix
                    )
                    active_shot = tool("get_screenshot", id_=request_id)
                    request_id += 1
                    active_screenshot.write_bytes(
                        base64.b64decode(active_shot["data"])
                    )
                if timer_state is None:
                    timer_state, timer_regs = timer_registers(3, request_id)
                    request_id += 1
                    if args.mode == "title":
                        tool("debug_pause", id_=request_id)
                        request_id = wait_until_paused(request_id + 1)
                        wait_address = (
                            game_address + GAME_OFFSET_TITLE_START_ARMED
                        )
                        wait_address_hex = f"{wait_address:04X}"
                        tool(
                            "set_breakpoint",
                            {
                                "address": wait_address_hex,
                                "execute": False,
                                "write": True,
                            },
                            id_=request_id,
                        )
                        request_id = continue_to_breakpoint(
                            request_id + 1, "title wait counter initialization"
                        )
                        for expected_wait in range(38, -1, -1):
                            wait_state = read_bytes(
                                game_address + GAME_OFFSET_TITLE_START_ARMED,
                                GAME_OFFSET_SOUND
                                - GAME_OFFSET_TITLE_START_ARMED + 1,
                                request_id,
                            )
                            request_id += 1
                            wait_value = wait_state[0]
                            wait_pending = wait_state[
                                GAME_OFFSET_TITLE_VOICE_PENDING
                                - GAME_OFFSET_TITLE_START_ARMED
                            ]
                            wait_phase = wait_state[
                                GAME_OFFSET_PHASE
                                - GAME_OFFSET_TITLE_START_ARMED
                            ]
                            wait_bgm = wait_state[
                                GAME_OFFSET_SOUND
                                - GAME_OFFSET_TITLE_START_ARMED
                            ]
                            wait_counter_values.append(wait_value)
                            if (
                                wait_value != expected_wait
                                or wait_pending != 2
                                or wait_phase != 6
                                or wait_bgm != 0
                            ):
                                raise RuntimeError(
                                    "invalid title wait breakpoint state: "
                                    f"expected={expected_wait} value={wait_value} "
                                    f"pending={wait_pending} phase={wait_phase} "
                                    f"bgm={wait_bgm}"
                                )
                            if expected_wait != 0:
                                request_id = continue_to_breakpoint(
                                    request_id, "title wait counter decrement"
                                )
                        tool(
                            "remove_breakpoint",
                            {"address": wait_address_hex},
                            id_=request_id,
                        )
                        request_id += 1
                        tool("debug_continue", id_=request_id)
                        request_id += 1
                        wait_counter_verified = True
                        start = time.time()
            elif nonzero:
                stopped_samples += 1
                if stopped_samples >= 20:
                    channel_a, _ = registers(0, request_id)
                    request_id += 1
                    if args.mode == "game-over" or channel_a["enabled"]:
                        transitioned = True
                        break
            time.sleep(args.poll_interval)

        shot = tool("get_screenshot", id_=request_id)
        with open(args.screenshot, "wb") as screenshot:
            screenshot.write(base64.b64decode(shot["data"]))
        request_id += 1
        channel_a, _ = registers(0, request_id)
        request_id += 1
        state_address = title_voice_state_address(args.map)
        memory = tool(
            "read_memory",
            {"area": 0, "offset": f"{state_address - 4:04X}", "size": 5},
            request_id,
        )
        state_bytes = bytes.fromhex(memory["data"])
        remaining = state_bytes[0] | (state_bytes[1] << 8)
        active = state_bytes[3]
        underrun = state_bytes[4]
        request_id += 1
        tool("set_trace_log", {"enabled": False}, request_id)
        request_id += 1
        trace = trace_lines(request_id)
        traced_dac = []
        timer3_irqs = []
        for line in trace:
            match = re.search(r"AUDIO 3  OUT=\$([0-9A-F]{2})", line)
            if match:
                traced_dac.append(int(match.group(1), 16))
            match = re.search(r"TIMER 3  IRQ  Backup:\$([0-9A-F]{2})", line)
            if match:
                timer3_irqs.append(int(match.group(1), 16))
        raw_dac, expected_dac = expected_dac_samples(
            args.voice, voice_sample_count
        )
        gain = load_voice_gain_reference()
        clamp_count = sum(gain.gain_would_clamp(value) for value in raw_dac)
        silent_tail = 0
        for value in reversed(raw_dac):
            if value != 0:
                break
            silent_tail += 1
        trace_offset = None
        for offset in range(min(9, len(traced_dac))):
            if traced_dac[offset : offset + voice_sample_count] == expected_dac:
                trace_offset = offset
                break

        distinct = len(set(outputs))
        print(
            "channel D: samples={} nonzero={} distinct={} first_nonzero={} "
            "last_nonzero={} final=0x{:02x}".format(
                len(outputs),
                len(nonzero),
                distinct,
                "{:.3f}s".format(nonzero[0][0]) if nonzero else "none",
                "{:.3f}s".format(nonzero[-1][0]) if nonzero else "none",
                outputs[-1] if outputs else 0,
            )
        )
        print(f"channel A enabled after voice: {channel_a['enabled']}")
        if args.mode == "title" and wait_observations:
            observed_wait_seconds = (
                wait_transition_elapsed - wait_observations[0][0]
                if wait_transition_elapsed is not None else -1.0
            )
            print(
                "title post-voice wait: first_tick={} last_tick={} "
                "observations={} observed_seconds={:.6f} expected_ticks=38 "
                "expected_seconds={:.6f} poll_interval={:.6f}".format(
                    wait_observations[0][1], wait_observations[-1][1],
                    len(wait_observations), observed_wait_seconds,
                    38 / 75, args.poll_interval,
                )
            )
        if args.mode == "title":
            print(
                "title wait breakpoint trace: values={} transitions={} "
                "wall_clock_advisory_only=True".format(
                    wait_counter_values,
                    max(0, len(wait_counter_values) - 1),
                )
            )
        if timer_state is not None:
            print(
                "Timer 3 active: backup={} control={} period_us={} "
                "effective_rate_hz={:.3f} enabled={} reload={} interrupt={}".format(
                    timer_regs["backup"],
                    timer_regs["control_a"],
                    TITLE_VOICE_TIMER_PERIOD_US,
                    TITLE_VOICE_RATE_HZ,
                    timer_state["enabled"],
                    timer_state["reload"],
                    timer_state["interrupt"],
                )
            )
        print(
            f"{args.mode} voice state: remaining={remaining} active={active} "
            f"underrun={underrun}"
        )
        stack_low_water = int.from_bytes(
            read_bytes(stack_low_water_address, 2, request_id), "little"
        )
        stack_pointer_in_range = stack_start <= stack_low_water <= stack_top
        stack_used = (
            stack_top - stack_low_water if stack_pointer_in_range else None
        )
        stack_unused = (
            stack_low_water - stack_start if stack_pointer_in_range else 0
        )
        print(
            "stack high-water: lowest_cc65_sp=0x{:04x} bss_end_exclusive=0x{:04x} "
            "stack_start=0x{:04x} stack_end_exclusive=0x{:04x} "
            "stack_pointer_in_range={} stack_used_bytes={} "
            "unused_bytes_between_stack_start_and_low_water={} required=128".format(
                stack_low_water, stack_floor, stack_start, stack_top,
                stack_pointer_in_range, stack_used, stack_unused
            )
        )
        print(
            f"assembly decode trace: DAC_writes={len(traced_dac)} "
            f"all_{voice_sample_count}_exact={trace_offset is not None} "
            f"prefix_writes={trace_offset} Timer3_IRQs={len(timer3_irqs)}"
        )
        raw_signed = [gain.signed_sample(value) for value in raw_dac]
        gained_signed = [gain.signed_sample(value) for value in expected_dac]
        print(
            "gain reference: before_min={} before_max={} before_peak={} "
            "after_min={} after_max={} after_peak={} clamp={} "
            "clamp_ratio={:.6%} silent_tail={}".format(
                min(raw_signed), max(raw_signed),
                max(abs(min(raw_signed)), abs(max(raw_signed))),
                min(gained_signed), max(gained_signed),
                max(abs(min(gained_signed)), abs(max(gained_signed))),
                clamp_count, clamp_count / voice_sample_count, silent_tail,
            )
        )
        print(f"screenshot: {args.screenshot}")
        if active_screenshot is not None:
            print(f"active voice screenshot: {active_screenshot}")
        if trace_offset is None:
            print(
                f"trace prefix: actual={traced_dac[:24]} expected={expected_dac[:24]}",
                file=sys.stderr,
            )
        if not nonzero:
            print("FAIL: channel D did not expose sustained varying PCM", file=sys.stderr)
            return 1
        if silent_tail < 800 or any(expected_dac[-silent_tail:]):
            print("FAIL: gained DAC reference did not preserve silent tail", file=sys.stderr)
            return 1
        if stopped_samples < 20 or outputs[-1] != 0:
            print("FAIL: channel D did not return to stable zero", file=sys.stderr)
            return 1
        if args.mode == "title":
            if not transitioned or not channel_a["enabled"]:
                print("FAIL: Stage 1 BGM did not start after voice completion", file=sys.stderr)
                return 1
            if not wait_counter_verified or wait_counter_values != list(
                range(38, -1, -1)
            ):
                print(
                    "FAIL: title post-voice wait was not 38 silent 75Hz ticks",
                    file=sys.stderr,
                )
                return 1
        else:
            gate = read_bytes(
                game_address + GAME_OFFSET_GAME_OVER, 6, request_id + 1
            )
            print(
                "GAME OVER gate: game_over={} restart_armed={} pending={} complete={}".format(
                    gate[0], gate[1], gate[4], gate[5]
                )
            )
            if channel_a["enabled"] or gate[0] != 1 or gate[1] != 0 or gate[4] != 0 or gate[5] != 1:
                print("FAIL: GAME OVER voice did not unlock release-press gate cleanly", file=sys.stderr)
                return 1
            request_id += 2
            tool(
                "controller_macro",
                {"commands": [{"release": "a"}]},
                id_=request_id,
            )
            request_id += 1
            released_gate, request_id = wait_for_game_bytes(
                game_address,
                GAME_OFFSET_GAME_OVER,
                2,
                lambda state: state == bytes([1, 1]),
                request_id,
                "GAME OVER release gate",
            )
            tool(
                "controller_macro",
                {"commands": [{"press": "a"}]},
                id_=request_id,
            )
            request_id += 1
            returned_state, request_id = wait_for_game_bytes(
                game_address,
                GAME_OFFSET_GAME_OVER,
                GAME_OFFSET_PHASE - GAME_OFFSET_GAME_OVER + 1,
                lambda state: (
                    state[0] == 0
                    and state[GAME_OFFSET_PHASE - GAME_OFFSET_GAME_OVER] == 6
                ),
                request_id,
                "release-press TITLE return",
            )
            returned_phase = returned_state[GAME_OFFSET_PHASE - GAME_OFFSET_GAME_OVER]
            stable_held_polls = 0
            while stable_held_polls < 8:
                held_state = read_bytes(
                    game_address + GAME_OFFSET_GAME_OVER,
                    GAME_OFFSET_PHASE - GAME_OFFSET_GAME_OVER + 1,
                    request_id,
                )
                request_id += 1
                if (
                    held_state[0] != 0
                    or held_state[
                        GAME_OFFSET_TITLE_START_ARMED - GAME_OFFSET_GAME_OVER
                    ] != 0
                    or held_state[
                        GAME_OFFSET_TITLE_VOICE_PENDING - GAME_OFFSET_GAME_OVER
                    ] != 0
                    or held_state[GAME_OFFSET_PHASE - GAME_OFFSET_GAME_OVER] != 6
                ):
                    print(
                        "FAIL: held return press retriggered the TITLE gate",
                        file=sys.stderr,
                    )
                    return 1
                stable_held_polls += 1
                time.sleep(0.005)
            tool(
                "controller_macro",
                {"commands": [{"release": "a"}]},
                id_=request_id,
            )
            print(
                "GAME OVER release/press: armed={} returned_game_over={} "
                "returned_phase={} held_title_polls={}".format(
                    released_gate[1], returned_state[0], returned_phase,
                    stable_held_polls,
                )
            )
            if returned_state[0] != 0 or returned_phase != 6:
                print("FAIL: release-press did not return to title exactly once", file=sys.stderr)
                return 1
        if remaining != 0 or active != 0 or underrun != 0:
            print("FAIL: title voice stream ended with an underrun", file=sys.stderr)
            return 1
        if not stack_pointer_in_range or stack_unused < 128:
            print(
                "FAIL: stack high-water leaves fewer than 128 unused bytes",
                file=sys.stderr,
            )
            return 1
        if timer_state is None or timer_regs is None:
            print("FAIL: Timer 3 was not observed during voice playback", file=sys.stderr)
            return 1
        if (
            int(timer_regs["backup"], 16) != TITLE_VOICE_TIMER_BACKUP
            or int(timer_regs["control_a"], 16) != TITLE_VOICE_TIMER_CONTROL
            or not timer_state["enabled"]
            or not timer_state["reload"]
            or not timer_state["interrupt"]
            or timer_state["period_value"] != 0
        ):
            print("FAIL: Timer 3 is not configured for 126 us reload IRQ", file=sys.stderr)
            return 1
        if len(timer3_irqs) != voice_sample_count or any(
            backup != TITLE_VOICE_TIMER_BACKUP for backup in timer3_irqs
        ):
            print("FAIL: Timer 3 IRQ count/rate did not match one IRQ per sample", file=sys.stderr)
            return 1
        if trace_offset is None:
            print("FAIL: full assembly decode differs from C89 IMA reference", file=sys.stderr)
            return 1
        if args.mode == "title":
            print(
                "OK: title voice varied channel D, stopped, waited 38 ticks, "
                "and transitioned to Stage 1"
            )
        else:
            print("OK: GAME OVER voice varied channel D, stopped, and unlocked input gate")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    sys.exit(main())
