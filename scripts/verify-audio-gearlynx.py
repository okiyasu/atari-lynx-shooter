#!/usr/bin/env python3
"""Verify BGM playback in Gearlynx via its built-in MCP server (APS-024/025).

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
confirmation. Exits non-zero if the channel never becomes active or never
changes pitch (both indicate a broken/silent BGM rather than a "beepy but
working" one).
"""
import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.request

GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17766
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--channel", type=int, default=0, help="0=A/melody, 2=C/bass")
    parser.add_argument(
        "--rom", default="dist/asteroid-patrol.lnx", help="ROM path (relative to cwd)"
    )
    parser.add_argument(
        "--symbols", default="build/asteroid-patrol.lbl", help="Symbol file path"
    )
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

        tool("debug_continue")
        time.sleep(1.5)  # let the title screen render
        tool(
            "controller_button", {"button": "a", "action": "press_and_release"}, id_=2
        )
        time.sleep(1.0)  # let game_start() run and enable BGM

        shot = tool("get_screenshot", id_=3)
        with open(args.screenshot, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print(f"screenshot: {args.screenshot}")

        last_backup = None
        note_changes = []
        start = time.time()
        req_id = 10
        while time.time() - start < args.seconds:
            ch = tool("get_mikey_audio", {"channel": args.channel}, id_=req_id)
            req_id += 1
            regs = {r[0]: r[2] for r in ch["registers"]}
            backup = regs.get("backup")
            if ch["enabled"] and backup != last_backup:
                elapsed = time.time() - start
                note_changes.append((elapsed, backup, regs.get("volume")))
                last_backup = backup
            time.sleep(args.poll_interval)

        print(f"channel {args.channel}: {len(note_changes)} note change(s) in {args.seconds}s")
        for elapsed, backup, vol in note_changes:
            print(f"  t={elapsed:6.2f}s  backup=0x{backup}  volume=0x{vol}")

        if len(note_changes) < 2:
            print(
                "FAIL: fewer than 2 distinct pitches observed -- BGM is silent or "
                "stuck on one note",
                file=sys.stderr,
            )
            return 1
        print("OK: channel is active and cycling through multiple pitches")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
