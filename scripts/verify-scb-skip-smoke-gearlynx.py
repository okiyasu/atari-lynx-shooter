#!/usr/bin/env python3
"""APS-053 v044 pre-implementation required check #2: SCB SKIP smoke test.

Before implementing the static SCB chain (movable_scb pool -> named static
structs, SKIP-bit-driven activation, one non-SKIPped palette header per
multi-slot kind reused via REUSEPAL), .briefs/APS-053/v044.md requires two
minimal-procedure confirmations on the real hardware model (gearlynx) or the
design must be reverted to the next-relink alternative:

  (a) SPRCTL1's SKIP bit (0x04, _suzy.h:91) actually makes Suzy skip drawing
      an otherwise-identical, otherwise-visible SCB.
  (b) A palette-only header SCB (empty data, a single 0x00 byte -- a
      self-terminating PACKED sprite with zero rows) draws zero pixels and
      still correctly latches its penpal for a following REUSEPAL SCB to
      use.

Method: reuses the proven APS-053 v011/v012/O5 technique (also the basis of
scripts/verify-static-layer-readback-gearlynx.py): static_layer_draw()
builds its own SCB chain directly in the memory title_voice.h documents as
shared scratch (title_voice_scratch_buffer, unused before any voice starts),
so overwriting that scratch with a hand-built chain before letting the
already-in-flight real _tgi_ioctl(tgi_sprite) call proceed substitutes the
content Suzy actually draws. No ROM code is patched, no register is forced;
release ROM and source are untouched by this script.

Chain (single submission, 4 SCBs, 68 bytes total, well inside the 640-byte
scratch buffer):

  SCB1 (SCB_RENONE_PAL, active, own penpal[0]=0x0F)      -> visible pixel
  SCB2 (SCB_RENONE_PAL, SKIP set, own penpal[0]=0x0C)    -> must NOT draw
  SCB3 (SCB_RENONE_PAL, active, own penpal[0]=0x03,
        data = 1-byte empty sprite {0x00})               -> must draw 0px
  SCB4 (SCB_RENONE, active, REUSEPAL, no own penpal)     -> must draw with
                                                              SCB3's pen[0]

All four share one screen row (y=30) at x=20/40/60/80 (byte offsets 10/20/
30/40 within that row's 80-byte half, matching the proven v011/v012 O5
pixel-address convention). The target framebuffer page is sentinel-filled
(0xAA) before the chain runs, so any unexpected write anywhere on the page
is visible as a byte that no longer equals the sentinel.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUAL_PATH = ROOT / "scripts" / "verify-stage-visuals-gearlynx.py"
STATIC_READBACK_PATH = ROOT / "scripts" / "verify-static-layer-readback-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17783

PAGE_SIZE = 160 * 102 // 2
PAGE_C038 = 0xC038
PAGE_E018 = 0xE018
SENTINEL = 0xAA
RAW_CHUNK = 512

# _suzy.h bit values (SCB control bytes).
BPP_1 = 0x00
TYPE_NONCOLL = 0x05
PACKED = 0x00
RENONE = 0x00
REUSEPAL = 0x08
SKIP = 0x04
NO_COLLIDE = 0x20

SCB_RENONE_SIZE = 11
SCB_RENONE_PAL_SIZE = 19

# Proven minimal single-row packed sprite (APS-053 O5,
# evidence/APS-053/phase-2r-o5-v011.json / v012.json): draws a real,
# nonzero-color pixel. Reused verbatim rather than re-derived.
ACTIVE_DATA = bytes((0x03, 0x84, 0x00, 0x00))
# v044-required "1-byte empty sprite": a PACKED row with row-byte-count 0,
# i.e. self-terminating with zero rows drawn.
EMPTY_DATA = bytes((0x00,))

ROW_Y = 30
ROW_BYTE_BASE = ROW_Y * 80
SCB1_X, SCB2_X, SCB3_X, SCB4_X = 20, 40, 60, 80
SCB1_OFFSET = ROW_BYTE_BASE + SCB1_X // 2
SCB2_OFFSET = ROW_BYTE_BASE + SCB2_X // 2
SCB4_OFFSET = ROW_BYTE_BASE + SCB4_X // 2

SCB1_PENPAL0 = 0x0F
SCB2_PENPAL0 = 0x0C
SCB3_PENPAL0 = 0x03


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pack_word(value):
    return [value & 0xFF, (value >> 8) & 0xFF]


def make_scb_renone_pal(sprctl0, sprctl1, sprcoll, next_addr, data_addr,
                         x, y, penpal0):
    scb = bytearray()
    scb.extend((sprctl0, sprctl1, sprcoll))
    scb.extend(pack_word(next_addr))
    scb.extend(pack_word(data_addr))
    scb.extend(pack_word(x))
    scb.extend(pack_word(y))
    scb.append(penpal0)
    scb.extend((0,) * 7)
    if len(scb) != SCB_RENONE_PAL_SIZE:
        raise RuntimeError("invalid SCB_RENONE_PAL size: %d" % len(scb))
    return bytes(scb)


def make_scb_renone(sprctl0, sprctl1, sprcoll, next_addr, data_addr, x, y):
    scb = bytearray()
    scb.extend((sprctl0, sprctl1, sprcoll))
    scb.extend(pack_word(next_addr))
    scb.extend(pack_word(data_addr))
    scb.extend(pack_word(x))
    scb.extend(pack_word(y))
    if len(scb) != SCB_RENONE_SIZE:
        raise RuntimeError("invalid SCB_RENONE size: %d" % len(scb))
    return bytes(scb)


def build_chain(scratch_address):
    scb1_addr = scratch_address
    scb2_addr = scb1_addr + SCB_RENONE_PAL_SIZE
    scb3_addr = scb2_addr + SCB_RENONE_PAL_SIZE
    scb4_addr = scb3_addr + SCB_RENONE_PAL_SIZE
    active_data_addr = scb4_addr + SCB_RENONE_SIZE
    empty_data_addr = active_data_addr + len(ACTIVE_DATA)

    sprctl0 = BPP_1 | TYPE_NONCOLL
    scb1 = make_scb_renone_pal(sprctl0, PACKED | RENONE, NO_COLLIDE,
                                scb2_addr, active_data_addr,
                                SCB1_X, ROW_Y, SCB1_PENPAL0)
    scb2 = make_scb_renone_pal(sprctl0, PACKED | RENONE | SKIP, NO_COLLIDE,
                                scb3_addr, active_data_addr,
                                SCB2_X, ROW_Y, SCB2_PENPAL0)
    scb3 = make_scb_renone_pal(sprctl0, PACKED | RENONE, NO_COLLIDE,
                                scb4_addr, empty_data_addr,
                                SCB3_X, ROW_Y, SCB3_PENPAL0)
    scb4 = make_scb_renone(sprctl0, PACKED | RENONE | REUSEPAL, NO_COLLIDE,
                            0, active_data_addr, SCB4_X, ROW_Y)
    payload = scb1 + scb2 + scb3 + scb4 + ACTIVE_DATA + EMPTY_DATA
    return payload, {
        "scb1": "0x%04X" % scb1_addr, "scb2": "0x%04X" % scb2_addr,
        "scb3": "0x%04X" % scb3_addr, "scb4": "0x%04X" % scb4_addr,
        "active_data": "0x%04X" % active_data_addr,
        "empty_data": "0x%04X" % empty_data_addr,
    }


def sentinel_fill(visual, address, size, request_id):
    payload = [SENTINEL] * RAW_CHUNK
    offset = 0
    while offset < size:
        count = min(RAW_CHUNK, size - offset)
        visual.write_bytes(address + offset, payload[:count], request_id)
        request_id += 1
        offset += count
    return request_id


def read_chunks(visual, address, size, request_id):
    parts = []
    offset = 0
    while offset < size:
        count = min(RAW_CHUNK, size - offset)
        parts.append(visual.read_bytes(address + offset, count, request_id))
        request_id += 1
        offset += count
    return request_id, b"".join(parts)


def register_snapshot(visual, request_id):
    suzy_payload = visual.tool("get_suzy_registers", request_id=request_id)
    request_id += 1
    mikey_payload = visual.tool("get_mikey_registers", request_id=request_id)
    request_id += 1
    suzy = {row[0]: row[2] for row in suzy_payload["registers"]}
    mikey = {row[0]: row[2] for row in mikey_payload["registers"]}
    return request_id, suzy, mikey


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path, default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-053/scb-skip-smoke-v044.json"))
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    if not args.rom.is_file() or not args.symbols.is_file():
        raise RuntimeError("ROM/label file is missing (build first)")

    visual = load_module(VISUAL_PATH, "aps053_skip_smoke_visual")
    visual.MCP_PORT = MCP_PORT
    static_module = load_module(STATIC_READBACK_PATH, "aps053_skip_smoke_static")

    rom_sha256 = hashlib.sha256(args.rom.read_bytes()).hexdigest()
    evidence = {
        "aps": "APS-053",
        "version": "v044",
        "check": "pre-implementation required check #2 (SKIP smoke)",
        "status": "blocked",
        "rom": {"path": str(args.rom), "sha256": rom_sha256,
                "size_bytes": args.rom.stat().st_size},
        "method": {
            "release_source_or_rom_modified": False,
            "technique": "overwrite title_voice_scratch_buffer (shared with "
                "static_layer's own SCB construction, see "
                "verify-static-layer-readback-gearlynx.py) before the "
                "already-in-flight real _tgi_ioctl(tgi_sprite) call "
                "proceeds via debug_step_out",
            "chain": "SCB1(active,pen0=0x0F) -> SCB2(SKIP,pen0=0x0C) -> "
                "SCB3(header,active,pen0=0x03,data=1-byte empty sprite) -> "
                "SCB4(REUSEPAL,active,no own penpal) -> terminator",
            "active_data_bytes": ["0x%02X" % b for b in ACTIVE_DATA],
            "empty_data_bytes": ["0x%02X" % b for b in EMPTY_DATA],
            "sentinel": "0x%02X" % SENTINEL,
        },
    }

    process = None
    try:
        process = __import__("subprocess").Popen(
            [GEARLYNX] + ([] if args.gui else ["--headless"]) + [
                "--mcp-http", "--mcp-http-port", str(MCP_PORT),
                str(args.rom), str(args.symbols),
            ], stdout=__import__("subprocess").DEVNULL,
            stderr=__import__("subprocess").DEVNULL,
        )
        for _ in range(30):
            try:
                visual.call("initialize", {
                    "protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "aps053-skip-smoke", "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")

        game_address = visual.symbol_address(args.symbols, "_game")
        ioctl_address = visual.symbol_address(args.symbols, "_tgi_ioctl")
        sync_address = visual.symbol_address(
            args.symbols, "_game_display_sync_complete")
        scratch_address = visual.symbol_address(
            args.symbols, "_title_voice_scratch_buffer")
        voice_active_address = scratch_address + 640 + 6
        evidence["symbols"] = {
            "_game": "0x%04X" % game_address,
            "_tgi_ioctl": "0x%04X" % ioctl_address,
            "_game_display_sync_complete": "0x%04X" % sync_address,
            "_title_voice_scratch_buffer": "0x%04X" % scratch_address,
        }

        request_id = static_module.wait_stable_title(
            visual, game_address, voice_active_address, 1)

        visual.tool("set_breakpoint", {"address": "%04X" % sync_address},
                   request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = visual.wait_for_breakpoint(
            request_id + 1, "pre-draw sync boundary")
        visual.tool("remove_breakpoint", {"address": "%04X" % sync_address},
                   request_id)
        request_id += 1

        request_id = sentinel_fill(visual, PAGE_C038, PAGE_SIZE, request_id)
        request_id = sentinel_fill(visual, PAGE_E018, PAGE_SIZE, request_id)
        request_id, c038_prefill = read_chunks(visual, PAGE_C038, PAGE_SIZE,
                                               request_id)
        request_id, e018_prefill = read_chunks(visual, PAGE_E018, PAGE_SIZE,
                                               request_id)
        evidence["sentinel_prefill"] = {
            "page_c038_all_sentinel": all(v == SENTINEL for v in c038_prefill),
            "page_e018_all_sentinel": all(v == SENTINEL for v in e018_prefill),
        }

        visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address},
                   request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = visual.wait_for_breakpoint(
            request_id + 1, "_tgi_ioctl entry (static layer SCB submission)")

        chain, addresses = build_chain(scratch_address)
        evidence["chain_addresses"] = addresses
        evidence["chain_bytes"] = len(chain)
        visual.write_bytes(scratch_address, list(chain), request_id)
        request_id += 1
        request_id, readback = read_chunks(visual, scratch_address,
                                           len(chain), request_id)
        evidence["chain_write_readback_match"] = readback == chain

        visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address},
                   request_id)
        request_id += 1
        visual.tool("debug_step_out", request_id=request_id)
        request_id += 1

        request_id, suzy, mikey = register_snapshot(visual, request_id)
        vidbas = int(suzy["VIDBAS"], 16)
        dispadr = int(mikey["DISPADR"], 16)
        evidence["registers"] = {"VIDBAS": "0x%04X" % vidbas,
                                 "DISPADR": "0x%04X" % dispadr}
        if vidbas not in (PAGE_C038, PAGE_E018):
            raise RuntimeError("unexpected VIDBAS 0x%04X" % vidbas)

        request_id, c038 = read_chunks(visual, PAGE_C038, PAGE_SIZE, request_id)
        request_id, e018 = read_chunks(visual, PAGE_E018, PAGE_SIZE, request_id)
        target = c038 if vidbas == PAGE_C038 else e018
        target_label = "c038" if vidbas == PAGE_C038 else "e018"

        changed = [i for i in range(PAGE_SIZE) if target[i] != SENTINEL]
        expected_changed = sorted({SCB1_OFFSET, SCB4_OFFSET})

        scb1_byte = target[SCB1_OFFSET]
        scb2_byte = target[SCB2_OFFSET]
        scb4_byte = target[SCB4_OFFSET]
        scb1_expected = ((SCB1_PENPAL0 & 0x0F) << 4) | SENTINEL & 0x0F
        scb4_expected = ((SCB3_PENPAL0 & 0x0F) << 4) | SENTINEL & 0x0F

        check_a_skip_honored = scb2_byte == SENTINEL
        check_b_header_zero_pixels = changed == expected_changed
        check_b_penpal_latched = scb4_byte == scb4_expected
        check_active_reference_drawn = scb1_byte == scb1_expected

        evidence["framebuffer"] = {
            "target_page": target_label,
            "target_page_cpu_address": "0x%04X" % vidbas,
            "other_page_untouched": (
                (e018 if target_label == "c038" else c038) ==
                bytes([SENTINEL] * PAGE_SIZE)
            ),
            "scb1_active_reference": {
                "offset": SCB1_OFFSET, "actual": "0x%02X" % scb1_byte,
                "expected": "0x%02X" % scb1_expected,
                "match": check_active_reference_drawn,
            },
            "scb2_skip_target": {
                "offset": SCB2_OFFSET, "actual": "0x%02X" % scb2_byte,
                "expected_if_skip_honored": "0x%02X" % SENTINEL,
                "expected_if_skip_ignored": "0x%02X" % (
                    ((SCB2_PENPAL0 & 0x0F) << 4) | (SENTINEL & 0x0F)),
                "skip_honored": check_a_skip_honored,
            },
            "scb4_reusepal_target": {
                "offset": SCB4_OFFSET, "actual": "0x%02X" % scb4_byte,
                "expected_from_scb3_penpal": "0x%02X" % scb4_expected,
                "match": check_b_penpal_latched,
            },
            "changed_byte_offsets": changed,
            "expected_changed_byte_offsets": expected_changed,
            "no_stray_writes": check_b_header_zero_pixels,
        }

        checks = {
            "a_skip_bit_prevents_draw": check_a_skip_honored,
            "b_empty_header_draws_zero_pixels": check_b_header_zero_pixels,
            "b_empty_header_latches_penpal_for_reusepal_follower":
                check_b_penpal_latched,
            "active_reference_sprite_drew_as_expected":
                check_active_reference_drawn,
            "chain_write_readback_match": evidence["chain_write_readback_match"],
        }
        evidence["checks"] = checks
        all_pass = all(checks.values())
        evidence["status"] = "PASS" if all_pass else "FAIL"
        evidence["design_implication"] = (
            "SCB static chain (SKIP-driven activation, always-non-SKIP "
            "palette headers) confirmed safe to implement" if all_pass else
            "design must be reverted to the next-relink alternative and "
            "reported to dev-front per .briefs/APS-053/v044.md"
        )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(("PASS" if all_pass else "FAIL") + ": " + json.dumps(checks))
        return 0 if all_pass else 1
    except Exception as error:
        evidence["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("BLOCKED: %s" % error, file=sys.stderr)
        return 2
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()


if __name__ == "__main__":
    sys.exit(main())
