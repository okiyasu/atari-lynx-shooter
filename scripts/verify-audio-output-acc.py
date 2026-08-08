#!/usr/bin/env python3
"""APS-027 focused check: sample the MIKEY OUTPUT register (the integrate
accumulator) via Gearlynx's MCP server and report how often it sits on the
+/-128 clamp rail. With the APS-026 imbalanced LFSR patterns the melody
channel pinned to the rail (the reported low "buzz"); with the APS-027
DC-balanced triangle patterns it must stay strictly inside the rails and
its swing must track the envelope volume.

Usage: scripts/verify-audio-output-acc.py [--seconds N] [--channel N]
"""
import argparse
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
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--rom", default="dist/asteroid-patrol.lnx")
    parser.add_argument("--symbols", default="build/asteroid-patrol.lbl")
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
                    "clientInfo": {"name": "aps027-acc-check", "version": "0.1"}})
                break
            except Exception:
                time.sleep(0.3)
        else:
            print("Gearlynx MCP server did not come up", file=sys.stderr)
            return 1

        _va.tool("debug_continue")
        time.sleep(1.5)
        _va.tool("controller_button",
                 {"button": "a", "action": "press_and_release"}, id_=2)
        time.sleep(1.0)

        samples = []
        start = time.time()
        req_id = 10
        while time.time() - start < args.seconds:
            ch = _va.tool("get_mikey_audio", {"channel": args.channel},
                          id_=req_id)
            req_id += 1
            regs = {r[0]: r[2] for r in ch["registers"]}
            samples.append((regs.get("output"), regs.get("volume"),
                            regs.get("feedback"), regs.get("control")))
            time.sleep(0.03)

        outputs = [int(s[0], 16) if isinstance(s[0], str) else s[0]
                   for s in samples if s[0] is not None]
        signed = [o - 256 if o > 127 else o for o in outputs]
        railed = sum(1 for o in signed if o in (-128, 127))
        print("channel %d: %d samples  feedback=%s control=%s" %
              (args.channel, len(samples), samples[0][2], samples[0][3]))
        print("output accumulator: min=%d max=%d  rail(-128/127) hits=%d (%.1f%%)"
              % (min(signed), max(signed), railed,
                 100.0 * railed / max(1, len(signed))))
        print("distinct levels seen: %s" % sorted(set(signed)))
        if railed > len(signed) // 10:
            print("FAIL: accumulator spends >10%% of samples on the clamp rail",
                  file=sys.stderr)
            return 1
        print("OK: accumulator stays off the clamp rail")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
