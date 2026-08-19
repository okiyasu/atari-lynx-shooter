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
SHOT_SFX_OUTPUTS = (
    (1, 15, 28, 3),
    (1, 12, 22, 3),
)
# Static helper address in the release map: main.o CODE starts at 0x0298,
# and sound_backend_apply_all is offset 0x0309 in that object.
SOUND_APPLY_ALL_ADDRESS = 0x05A1
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


def label_address(symbols_path, symbol):
    for line in Path(symbols_path).read_text(encoding="utf-8").splitlines():
        match = re.match(
            r"^al\s+([0-9A-Fa-f]{6})\s+\." + re.escape(symbol) + r"$",
            line,
        )
        if match:
            return int(match.group(1), 16)
    raise RuntimeError("cannot locate {} in label file".format(symbol))


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


def wait_for_breakpoint(id_, description):
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        status = tool("debug_get_status", id_=id_)
        id_ += 1
        if status["paused"]:
            if not status["at_breakpoint"]:
                raise RuntimeError(
                    "paused before {} breakpoint".format(description)
                )
            return id_
        time.sleep(0.005)
    raise RuntimeError("timed out waiting for {} breakpoint".format(description))


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


def sound_state_snapshot(game_address, id_):
    raw = read_bytes(game_address + GAME_OFFSET_SOUND, 22, id_)
    return {
        "raw": raw.hex(),
        "bgm_active": raw[0],
        "bgm_id": raw[1],
        "bgm_step": raw[2],
        "bgm_remaining": raw[3],
        "bass_step": raw[4],
        "bass_remaining": raw[5],
        "sfx_id": raw[6],
        "sfx_step": raw[7],
        "sfx_remaining": raw[8],
        "pending_stage_clear": raw[9],
        "output_bgm": list(raw[10:14]),
        "output_bgm_bass": list(raw[14:18]),
        "output_sfx": list(raw[18:22]),
    }


def diagnostic_event(diagnostic, name, payload):
    if diagnostic is not None:
        diagnostic["events"].append({"event": name, **payload})


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
    parser.add_argument(
        "--diagnostic-output", type=Path, default=None,
        help="write non-invasive game/sound/MIKEY boundary evidence as JSON",
    )
    args = parser.parse_args()

    diagnostic = None
    result_code = 1
    if args.diagnostic_output is not None:
        diagnostic = {
            "diagnostic": "MIKEY audio channel boundary",
            "channel": args.channel,
            "seconds": args.seconds,
            "rom": str(args.rom),
            "events": [],
        }

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
        if diagnostic is not None:
            diagnostic.update({
                "game_address": "0x%04X" % game_address,
                "voice_state_address": "0x%04X" % voice_address,
                "logical_volume_address": "0x%04X" % (
                    game_address + LOGICAL_VOLUME_OFFSETS[args.channel]
                ),
            })
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
        diagnostic_event(diagnostic, "stable_title", {
            "game": game_snapshot(game_address, request_id),
            "voice": voice_snapshot(voice_address, request_id + 1),
            "sound": sound_state_snapshot(game_address, request_id + 2),
        })
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
        diagnostic_event(diagnostic, "stage1_bgm_started", {
            "game": game_snapshot(game_address, request_id),
            "voice": voice_snapshot(voice_address, request_id + 1),
            "sound": sound_state_snapshot(game_address, request_id + 2),
        })

        sync_address = label_address(
            Path(args.symbols), "_game_display_sync_complete"
        )
        apply_address = SOUND_APPLY_ALL_ADDRESS if args.channel == 1 else None
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
            # Stop at the real sound-apply entry. Injecting at the later sync
            # callback lets the short SFX be consumed by the next sound tick
            # before sound_backend_apply_all observes it.
            tool(
                "set_breakpoint",
                {"address": f"{apply_address:04X}"},
                id_=request_id,
            )
            request_id += 1
            tool(
                "set_breakpoint",
                {"address": f"{sync_address:04X}"},
                id_=request_id,
            )
            request_id += 1
            tool("debug_continue", id_=request_id)
            request_id += 1
            request_id = wait_for_breakpoint(
                request_id, "first sound apply before SFX injection"
            )
            diagnostic_event(diagnostic, "before_sfx_injection", {
                "game": game_snapshot(game_address, request_id),
                "voice": voice_snapshot(voice_address, request_id + 1),
                "sound": sound_state_snapshot(game_address, request_id + 2),
                "mikey": tool("get_mikey_audio", {"channel": 1}, id_=request_id + 3),
            })
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
            diagnostic_event(diagnostic, "after_sfx_injection", {
                "game": game_snapshot(game_address, request_id),
                "voice": voice_snapshot(voice_address, request_id + 1),
                "sound": sound_state_snapshot(game_address, request_id + 2),
                "mikey": tool("get_mikey_audio", {"channel": 1}, id_=request_id + 3),
            })
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
        else:
            request_id = wait_for_channel_active(
                args.channel, game_address, voice_address, request_id
            )
            tool(
                "set_breakpoint",
                {"address": f"{sync_address:04X}"},
                id_=request_id,
            )
            request_id += 1

        shot = tool("get_screenshot", id_=request_id)
        request_id += 1
        with open(args.screenshot, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print(f"screenshot: {args.screenshot}")

        last_backup = None
        note_changes = []
        gain_pairs = set()
        gain_mismatches = []
        start = time.monotonic()
        req_id = request_id
        logical_address = game_address + LOGICAL_VOLUME_OFFSETS[args.channel]
        sample_index = 0
        while time.monotonic() - start < args.seconds:
            tool("debug_continue", id_=req_id)
            req_id += 1
            req_id = wait_for_breakpoint(
                req_id, "sound apply boundary sample %d" % (sample_index + 1)
            )
            logical = read_byte(logical_address, req_id)
            req_id += 1
            ch = tool("get_mikey_audio", {"channel": args.channel}, id_=req_id)
            req_id += 1
            regs = {r[0]: r[2] for r in ch["registers"]}
            backup = regs.get("backup")
            hardware_volume = int(regs.get("volume", "0x00"), 16)
            if ch["enabled"]:
                expected = scaled_volume(logical)
                if hardware_volume != expected:
                    gain_mismatches.append((logical, hardware_volume, expected))
                else:
                    gain_pairs.add((logical, hardware_volume))
            if ch["enabled"] and backup != last_backup:
                elapsed = time.monotonic() - start
                note_changes.append((elapsed, backup, regs.get("volume")))
                last_backup = backup
            diagnostic_event(diagnostic, "apply_boundary", {
                "sample_index": sample_index + 1,
                "logical_volume": logical,
                "expected_hardware_volume": scaled_volume(logical),
                "mikey": ch,
                "registers": regs,
                "logical_memory_readback": read_bytes(
                    logical_address, 1, req_id + 2
                ).hex(),
                "game": game_snapshot(game_address, req_id),
                "voice": voice_snapshot(voice_address, req_id + 1),
                "sound": sound_state_snapshot(game_address, req_id + 2),
            })
            sample_index += 1
            if args.channel == 1:
                # Re-arm at the next real apply entry, after the previous
                # apply has been observed and before production can consume
                # another short SFX.
                tool("debug_continue", id_=req_id)
                req_id += 1
                req_id = wait_for_breakpoint(
                    req_id, "next sound apply before SFX rearm"
                )
                sfx_step = sample_index % len(SHOT_SFX_OUTPUTS)
                sound_before_rearm = sound_state_snapshot(game_address, req_id)
                req_id += 1
                logical_memory_before_rearm = read_bytes(
                    logical_address, 1, req_id
                ).hex()
                req_id += 1
                write_bytes(
                    game_address + GAME_OFFSET_SFX_STATE,
                    [1, sfx_step, 4, 0],
                    req_id,
                )
                req_id += 1
                write_bytes(
                    game_address + GAME_OFFSET_OUTPUT_SFX,
                    list(SHOT_SFX_OUTPUTS[sfx_step]),
                    req_id,
                )
                req_id += 1
                diagnostic_event(diagnostic, "sfx_rearm", {
                    "sample_index": sample_index,
                    "sfx_step": sfx_step,
                    "game": game_snapshot(game_address, req_id),
                    "voice": voice_snapshot(voice_address, req_id + 1),
                    "sound_before_rearm": sound_before_rearm,
                    "logical_memory_before_rearm": logical_memory_before_rearm,
                    "mikey_before_rearm": ch,
                })

        tool("remove_breakpoint", {"address": f"{sync_address:04X}"}, id_=req_id)
        req_id += 1
        if apply_address is not None:
            tool("remove_breakpoint", {"address": f"{apply_address:04X}"}, id_=req_id)
            req_id += 1

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
            if diagnostic is not None:
                diagnostic["trace_lines"] = channel_trace[:200]

        minimum_note_changes = 1 if args.channel == 1 else 2
        if len(note_changes) < minimum_note_changes:
            print(
                "FAIL: fewer than %d distinct pitches observed -- channel is silent or "
                "stuck on one note",
                minimum_note_changes,
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
        result_code = 0
        return 0
    except RuntimeError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    finally:
        if diagnostic is not None:
            diagnostic["exit_code"] = result_code
            args.diagnostic_output.parent.mkdir(parents=True, exist_ok=True)
            args.diagnostic_output.write_text(
                json.dumps(diagnostic, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
