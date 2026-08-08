#!/usr/bin/env python3
"""Capture the title screen via Gearlynx's MCP server (APS-027: used to
confirm the version string renders inside the 160x102 screen)."""
import argparse
import base64
import importlib.util
import os
import subprocess
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "verify_audio", os.path.join(_here, "verify-audio-gearlynx.py"))
_va = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_va)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", default="dist/asteroid-patrol.lnx")
    parser.add_argument("--symbols", default="build/asteroid-patrol.lbl")
    parser.add_argument("--out", default="/tmp/gearlynx-title.png")
    parser.add_argument("--wait", type=float, default=3.0)
    args = parser.parse_args()

    proc = subprocess.Popen(
        [_va.GEARLYNX, "--headless", "--mcp-http", "--mcp-http-port",
         str(_va.MCP_PORT), args.rom, args.symbols],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                _va.call("initialize", {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "title-shot", "version": "0.1"}})
                break
            except Exception:
                time.sleep(0.3)
        else:
            print("MCP server did not come up", file=sys.stderr)
            return 1
        _va.tool("debug_continue")
        time.sleep(args.wait)
        shot = _va.tool("get_screenshot", id_=3)
        with open(args.out, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print(args.out)
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
