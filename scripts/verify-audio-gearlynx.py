#!/usr/bin/env python3
"""Verify A/C BGM, B SFX, and APS-036 75% output gain in Gearlynx.

Launches Gearlynx headless with --mcp-http, starts the game, and samples
Mikey channel audio registers over time to detect note (pitch) changes.
This lets an AI agent confirm a BGM track actually plays a sequence of
distinct pitches -- something that previously required a human to listen,
because this environment has no Screen Recording/audio-capture permission
for the GUI build.

Usage:
    scripts/verify-audio-gearlynx.py [--seconds N] [--channel N] [--rom PATH]

Requires the ROM already built (make rom) and Gearlynx.app installed at
/Applications/Gearlynx.app. Prints one line per detected note change with
its wall-clock timestamp and the channel's pitch-determining register
(period reload aka "backup"), plus a screenshot saved to /tmp for visual
confirmation. Channel B uses a paused deterministic shot-SFX state injection
after Stage 1 NORMAL so its short contour cannot finish inside an input macro;
host tests cover the gameplay fire path. Exits non-zero if the selected channel
never becomes active, never changes pitch, or violates the logical-to-MIKEY
75% gain mapping.
"""
import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.request
import re
from pathlib import Path

GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17766
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}
GAME_OFFSET_IN_MAIN_BSS = 12
GAME_OFFSET_SOUND = 213
GAME_OFFSET_TITLE_START_ARMED = 193
GAME_OFFSET_TITLE_VOICE_PENDING = 194
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PHASE = 210
GAME_OFFSET_SFX_STATE = GAME_OFFSET_SOUND + 6
GAME_OFFSET_OUTPUT_SFX = GAME_OFFSET_SOUND + 18
GAME_PHASE_NORMAL = 1
GAME_PHASE_TITLE = 6
LOGICAL_VOLUME_OFFSETS = {
    0: GAME_OFFSET_SOUND + 12,
    2: GAME_OFFSET_SOUND + 16,
    1: GAME_OFFSET_SOUND + 20,
}


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


def read_byte(address, id_):
    result = tool(
        "read_memory",
        {"area": 0, "offset": f"{address:04X}", "size": 1},
        id_=id_,
    )
    return int(result["data"], 16)


def read_bytes(address, size, id_):
    result = tool(
        "read_memory",
        {"area": 0, "offset": f"{address:04X}", "size": size},
        id_=id_,
    )
    return bytes.fromhex(result["data"])


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


def title_voice_state_address(map_path):
    text = Path(map_path).read_text(encoding="utf-8")
    segment = re.search(r"^BSS\s+([0-9A-F]{6})\s", text, re.MULTILINE)
    module = re.search(
        r"^title_voice\.o:\n(?:.*\n)*?\s+BSS\s+Offs=([0-9A-F]{6})\s+"
        r"Size=([0-9A-F]{6})",
        text,
        re.MULTILINE,
    )
    if segment is None or module is None:
        raise RuntimeError("cannot locate title_voice.o BSS in linker map")
    return (
        int(segment.group(1), 16)
        + int(module.group(1), 16)
        + int(module.group(2), 16)
        - 1
    )


def game_snapshot(game_address, id_):
    state = read_bytes(
        game_address + GAME_OFFSET_TITLE_START_ARMED,
        GAME_OFFSET_SOUND - GAME_OFFSET_TITLE_START_ARMED + 1,
        id_,
    )
    return {
        "armed": state[0],
        "pending": state[1],
        "stage": state[GAME_OFFSET_STAGE - GAME_OFFSET_TITLE_START_ARMED],
        "phase": state[GAME_OFFSET_PHASE - GAME_OFFSET_TITLE_START_ARMED],
        "bgm_active": state[GAME_OFFSET_SOUND - GAME_OFFSET_TITLE_START_ARMED],
    }


def voice_snapshot(state_address, id_):
    state = read_bytes(state_address - 4, 5, id_)
    return {
        "remaining": state[0] | (state[1] << 8),
        "active": state[3],
        "underrun": state[4],
    }


def state_summary(game_state, voice_state):
    return (
        "stage={stage} phase={phase} armed={armed} pending={pending} "
        "bgm_active={bgm_active} voice_remaining={remaining} "
        "voice_active={active} voice_underrun={underrun}"
    ).format(**game_state, **voice_state)


def wait_for_game_state(game_address, voice_address, predicate, id_, description,
                        timeout=8.0):
    deadline = time.monotonic() + timeout
    latest_game = None
    latest_voice = None
    while time.monotonic() < deadline:
        latest_game = game_snapshot(game_address, id_)
        id_ += 1
        latest_voice = voice_snapshot(voice_address, id_)
        id_ += 1
        if predicate(latest_game, latest_voice):
            return latest_game, latest_voice, id_
        time.sleep(0.005)
    raise RuntimeError(
        "timed out waiting for {}: {}".format(
            description, state_summary(latest_game, latest_voice)
        )
    )


def wait_for_channel_active(channel, game_address, voice_address, id_, timeout=5.0):
    deadline = time.monotonic() + timeout
    latest_channel = None
    while time.monotonic() < deadline:
        latest_channel = tool("get_mikey_audio", {"channel": channel}, id_=id_)
        id_ += 1
        if latest_channel["enabled"]:
            return id_
        time.sleep(0.005)
    game_state = game_snapshot(game_address, id_)
    voice_state = voice_snapshot(voice_address, id_ + 1)
    raise RuntimeError(
        "timed out waiting for MIKEY channel {} active: {}; enabled={}".format(
            channel,
            state_summary(game_state, voice_state),
            latest_channel["enabled"] if latest_channel is not None else "unknown",
        )
    )


def wait_until_paused(id_):
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        status = tool("debug_get_status", id_=id_)
        id_ += 1
        if status["paused"]:
            return id_
        time.sleep(0.005)
    raise RuntimeError("Gearlynx did not pause before SFX state injection")


def scaled_volume(logical):
    scaled = logical * 3 // 4
    return 1 if logical != 0 and scaled == 0 else scaled


def call(method, params=None, id_=1):
    body = json.dumps(
        {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    ).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{MCP_PORT}/mcp", data=body, headers=HEADERS
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def tool(name, arguments=None, id_=1):
    result = call("tools/call", {"name": name, "arguments": arguments or {}}, id_)
    if "error" in result:
        raise RuntimeError(f"{name} failed: {result['error']}")
    content = result["result"]["content"][0]
    if content.get("type") == "image":
        return content
    return json.loads(content["text"])


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument(
        "--channel", type=int, choices=(0, 1, 2), default=0,
        help="0=A/melody, 1=B/SFX, 2=C/bass",
    )
    parser.add_argument(
        "--rom", default="dist/asteroid-patrol.lnx", help="ROM path (relative to cwd)"
    )
    parser.add_argument(
        "--symbols", default="build/asteroid-patrol.lbl", help="Symbol file path"
    )
    parser.add_argument("--map", default="build/asteroid-patrol.map")
    parser.add_argument("--poll-interval", type=float, default=0.1)
    parser.add_argument("--screenshot", default="/tmp/gearlynx-audio-check.png")
    args = parser.parse_args()

    proc = subprocess.Popen(
        [
            GEARLYNX,
            "--headless",
            "--mcp-http",
            "--mcp-http-port",
            str(MCP_PORT),
            args.rom,
            args.symbols,
        ],
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
                        "clientInfo": {"name": "ryoko-audio-verify", "version": "0.1"},
                    },
                )
                break
            except Exception:
                time.sleep(0.3)
        else:
            print("Gearlynx MCP server did not come up in time", file=sys.stderr)
            return 1

        game_address = main_bss_game_address(args.map)
        voice_address = title_voice_state_address(args.map)
        tool("debug_continue")
        _, _, request_id = wait_for_game_state(
            game_address,
            voice_address,
            lambda game, voice: (
                game["stage"] == 1
                and game["phase"] == GAME_PHASE_TITLE
                and game["armed"] == 1
                and game["pending"] == 0
                and voice["active"] == 0
            ),
            2,
            "stable armed TITLE",
        )
        tool(
            "controller_macro",
            {"commands": [{"press": "a"}]},
            id_=request_id,
        )
        request_id += 1
        _, _, request_id = wait_for_game_state(
            game_address,
            voice_address,
            lambda game, voice: (
                game["stage"] == 1
                and game["phase"] == GAME_PHASE_TITLE
                and game["pending"] == 1
                and voice["active"] != 0
            ),
            request_id,
            "TITLE input acceptance and voice start",
        )
        tool(
            "controller_macro",
            {"commands": [{"release": "a"}]},
            id_=request_id,
        )
        request_id += 1
        _, _, request_id = wait_for_game_state(
            game_address,
            voice_address,
            lambda game, voice: (
                game["stage"] == 1
                and game["phase"] != GAME_PHASE_TITLE
                and game["pending"] == 0
                and game["bgm_active"] == 1
                and voice["active"] == 0
                and voice["remaining"] == 0
            ),
            request_id,
            "title voice completion and Stage 1 BGM start",
        )

        if args.channel == 1:
            _, _, request_id = wait_for_game_state(
                game_address,
                voice_address,
                lambda game, voice: (
                    game["stage"] == 1
                    and game["phase"] == GAME_PHASE_NORMAL
                    and game["bgm_active"] == 1
                    and voice["active"] == 0
                ),
                request_id,
                "Stage 1 NORMAL before SFX trigger",
                timeout=15.0,
            )
            tool("debug_pause", id_=request_id)
            request_id += 1
            request_id = wait_until_paused(request_id)
            write_bytes(
                game_address + GAME_OFFSET_SFX_STATE,
                [1, 0, 4, 0],
                request_id,
            )
            request_id += 1
            write_bytes(
                game_address + GAME_OFFSET_OUTPUT_SFX,
                [1, 15, 28, 3],
                request_id,
            )
            request_id += 1
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
                        "mikey_timers": False,
                        "mikey_uart": False,
                        "suzy_input": False,
                        "suzy_math": False,
                        "suzy_sprites": False,
                    },
                },
                id_=request_id,
            )
            request_id += 1
            tool("debug_continue", id_=request_id)
            request_id += 1
        else:
            request_id = wait_for_channel_active(
                args.channel, game_address, voice_address, request_id
            )

        shot = tool("get_screenshot", id_=request_id)
        request_id += 1
        with open(args.screenshot, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print(f"screenshot: {args.screenshot}")

        last_backup = None
        note_changes = []
        gain_pairs = set()
        gain_mismatches = []
        start = time.time()
        req_id = request_id
        logical_address = game_address + LOGICAL_VOLUME_OFFSETS[args.channel]
        while time.time() - start < args.seconds:
            logical_before = read_byte(logical_address, req_id)
            req_id += 1
            ch = tool("get_mikey_audio", {"channel": args.channel}, id_=req_id)
            req_id += 1
            logical_after = read_byte(logical_address, req_id)
            req_id += 1
            regs = {r[0]: r[2] for r in ch["registers"]}
            backup = regs.get("backup")
            hardware_volume = int(regs.get("volume", "0x00"), 16)
            if ch["enabled"]:
                expected_before = scaled_volume(logical_before)
                expected_after = scaled_volume(logical_after)
                if hardware_volume not in (expected_before, expected_after):
                    gain_mismatches.append(
                        (logical_before, hardware_volume, logical_after)
                    )
                else:
                    logical = (
                        logical_before
                        if hardware_volume == expected_before
                        else logical_after
                    )
                    gain_pairs.add((logical, hardware_volume))
            if ch["enabled"] and backup != last_backup:
                elapsed = time.time() - start
                note_changes.append((elapsed, backup, regs.get("volume")))
                last_backup = backup
            time.sleep(args.poll_interval)

        print(f"channel {args.channel}: {len(note_changes)} note change(s) in {args.seconds}s")
        for elapsed, backup, vol in note_changes:
            print(f"  t={elapsed:6.2f}s  backup=0x{backup}  volume=0x{vol}")
        print(
            "75% gain logical->MIKEY: "
            + ", ".join(f"{logical}->{hardware}" for logical, hardware in sorted(gain_pairs))
        )
        if args.channel == 1:
            tool("set_trace_log", {"enabled": False}, id_=req_id)
            req_id += 1
            channel_trace = [line for line in trace_lines(req_id) if "AUDIO 1" in line]
            print("channel B trace:")
            for line in channel_trace[:80]:
                print("  " + line)

        if len(note_changes) < 2:
            print(
                "FAIL: fewer than 2 distinct pitches observed -- channel is silent or "
                "stuck on one note",
                file=sys.stderr,
            )
            return 1
        if not gain_pairs or gain_mismatches:
            print(
                f"FAIL: output gain mismatch samples={gain_mismatches[:8]}",
                file=sys.stderr,
            )
            return 1
        print("OK: channel is active and cycling through multiple pitches")
        return 0
    except RuntimeError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
