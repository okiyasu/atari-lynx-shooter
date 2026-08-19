#!/usr/bin/env python3
"""APS-053 Phase 2R-2 Gate A O5: minimal Suzy chain and type bisect.

The release ROM is never rebuilt or modified by this verifier.  At the real
``_tgi_ioctl`` entry it replaces only the first 54 bytes of the existing
scratch-backed SCB area, fills both physical pages with a sentinel, and lets
the release TGI driver execute the injected two-pixel chain.  Run A and Run B
are deliberately separate Gearlynx processes so that Suzy state and physical
pages cannot leak between the two hypotheses.
"""

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUAL_PATH = ROOT / "scripts" / "verify-stage-visuals-gearlynx.py"
STATIC_READBACK_PATH = ROOT / "scripts" / "verify-static-layer-readback-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17775

PAGE_SIZE = 160 * 102 // 2
PAGE_C038 = 0xC038
PAGE_E018 = 0xE018
SENTINEL = 0xAA
SCB_SIZE = 23
DATA_SIZE = 4
CHAIN_SIZE = SCB_SIZE * 2 + DATA_SIZE * 2
RAW_CHUNK = 512
PIXEL_OFFSETS = (30 * 80 + 10, 30 * 80 + 20)
PIXEL_POSITIONS = ((20, 30), (40, 30))
RUNS = ("A", "B")
BISECT_RUNS = ("C1", "C2", "C3")
DRIVER_SOURCE = (
    ".cache/cc65-2.19/source/libsrc/lynx/tgi/lynx-160-102-16.s"
)

GAME_VERSION = "0.53.3"
EXPECTED_RELEASE_SHA256 = (
    "0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb"
)
BASELINE_BSS = {
    "normal": 0x04F0,
    "cadence": 0x054E,
}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_visual_module():
    module = load_module(VISUAL_PATH, "aps053_visual_verifier_o5")
    module.MCP_PORT = MCP_PORT
    return module


def load_static_module():
    return load_module(STATIC_READBACK_PATH, "aps053_static_readback_o5")


def parse_int(value):
    if isinstance(value, int):
        return value
    return int(str(value), 16)


def pack_word(value):
    return [value & 0xFF, (value >> 8) & 0xFF]


def unpack_word(payload, offset):
    return payload[offset] | (payload[offset + 1] << 8)


def register_map(payload):
    return {
        row[0]: {"address": row[1], "value": row[2],
                 "int": parse_int(row[2])}
        for row in payload["registers"]
    }


def register_snapshot(visual, request_id):
    suzy_payload = visual.tool("get_suzy_registers", request_id=request_id)
    request_id += 1
    mikey_payload = visual.tool("get_mikey_registers", request_id=request_id)
    request_id += 1
    suzy = register_map(suzy_payload)
    mikey = register_map(mikey_payload)
    selected = {
        "SCBNEXT": suzy.get("SCBNEXT"),
        "SPRGO": suzy.get("SPRGO"),
        "SPRSYS": suzy.get("SPRSYS"),
        "VIDBAS": suzy.get("VIDBAS"),
        "DISPADR": mikey.get("DISPADR"),
    }
    return request_id, {
        "readback_available": all(value is not None for value in selected.values()),
        "suzy_registers": suzy,
        "mikey_registers": mikey,
        "selected": selected,
    }


def read_chunks(visual, address, size, request_id):
    parts = []
    offset = 0
    while offset < size:
        count = min(RAW_CHUNK, size - offset)
        parts.append(visual.read_bytes(address + offset, count, request_id))
        request_id += 1
        offset += count
    return request_id, b"".join(parts)


def write_chunks(visual, address, size, value, request_id):
    payload = [value] * RAW_CHUNK
    offset = 0
    while offset < size:
        count = min(RAW_CHUNK, size - offset)
        visual.write_bytes(address + offset, payload[:count], request_id)
        request_id += 1
        offset += count
    return request_id


def wait_breakpoint(visual, request_id, description):
    return visual.wait_for_breakpoint(request_id, description)


def make_scb(next_address, data_address, x, y, penpal, sprctl0=0x05,
             sprctl1=0x10, sprcoll=0x20, hsize=0x0100, vsize=0x0100):
    # SCB_REHV_PAL from cc65 _suzy.h: 23 bytes, little-endian words.
    scb = bytearray()
    scb.extend((sprctl0, sprctl1, sprcoll))
    scb.extend(pack_word(next_address))
    scb.extend(pack_word(data_address))
    scb.extend(pack_word(x))
    scb.extend(pack_word(y))
    scb.extend(pack_word(hsize))
    scb.extend(pack_word(vsize))
    scb.extend(penpal)
    if len(scb) != SCB_SIZE:
        raise RuntimeError("invalid O5 SCB size: %d" % len(scb))
    return scb


def make_chain(scratch_address, run_name):
    scb1 = scratch_address
    scb2 = scratch_address + SCB_SIZE
    data1 = scratch_address + SCB_SIZE * 2
    data2 = data1 + DATA_SIZE
    if run_name == "A":
        palettes = ([0x0F, 0, 0, 0, 0, 0, 0, 0],
                     [0x0C, 0, 0, 0, 0, 0, 0, 0])
    else:
        palettes = ([0x00, 0x0F, 0x0F, 0x03, 0x00, 0x00, 0x00, 0x00],
                     [0x00, 0x0F, 0x0F, 0x03, 0x00, 0x00, 0x00, 0x00])
    sprctl0 = 0x05
    next1 = scb2
    hsize = 0x0100
    vsize = 0x0100
    differences = []
    if run_name == "C1":
        # cls_sprite uses TYPE_BACKNONCOLL. Keep every Run B field other
        # than the type/control value unchanged, including penpal[0] == 0.
        sprctl0 = 0x01
        differences.append("sprctl0: 0x05 -> 0x01 (TYPE_NONCOLL -> TYPE_BACKNONCOLL)")
    elif run_name == "C2":
        # If C1 does not write, remove only chain continuation. The second
        # SCB remains in the injected bytes but is unreachable.
        next1 = 0
        differences.append("SCB1.next: SCB2 -> 0x0000 (single-SCB control)")
    elif run_name == "C3":
        # Last permitted follow-up: use the driver's full-screen reload pair
        # while retaining Run B type, palette, data and chain bytes. This is
        # recorded as a reload candidate; no release data is changed.
        hsize = 0xA000
        vsize = 0x6600
        differences.append("hsize/vsize: 0x0100/0x0100 -> 0xA000/0x6600 (driver cls reload)")
    payload = bytearray()
    payload.extend(make_scb(next1, data1, 20, 30, palettes[0],
                            sprctl0=sprctl0, hsize=hsize, vsize=vsize))
    payload.extend(make_scb(0, data2, 40, 30, palettes[1],
                            sprctl0=sprctl0, hsize=hsize, vsize=vsize))
    payload.extend((0x03, 0x84, 0x00, 0x00))
    payload.extend((0x03, 0x84, 0x00, 0x00))
    if len(payload) != CHAIN_SIZE:
        raise RuntimeError("invalid O5 chain size: %d" % len(payload))
    return bytes(payload), palettes, differences


def expected_for_run(run_name, vidbas_address):
    if run_name == "A":
        values = (0xFA, 0xCA)
    elif run_name in ("B", "C1", "C3"):
        values = (0x0A, 0x0A)
    elif run_name == "C2":
        values = (0x0A,)
    else:
        raise RuntimeError("unknown O5 run %s" % run_name)
    return [
        (vidbas_address + PIXEL_OFFSETS[index], value)
        for index, value in enumerate(values)
    ]


def cls_sprite_comparison():
    # The cc65 driver uses a short SCB_REHV-like clear sprite: the source has
    # 16 explicit bytes (the only palette byte is offset 15), while O5 uses a
    # 23-byte SCB_REHV_PAL. Keep the source spelling and symbolic data pointer
    # in evidence instead of inventing a ROM-local address for pixel_bitmap.
    return {
        "source": DRIVER_SOURCE,
        "source_lines": "407-421, 424-426",
        "source_layout": "16 explicit bytes: 3 control + 2 next + 2 data + 2 hpos + 2 vpos + 2 hsize + 2 vsize + 1 trailing byte",
        "source_bytes": [
            "0x01", "0x10", "0x20", "0x00", "0x00",
            "<pixel_bitmap.lo>", "<pixel_bitmap.hi>",
            "0x00", "0x00", "0x00", "0x00",
            "0x00", "0xA0", "0x00", "0x66", "0x00",
            "<implicit/padded bytes 0x00 x7>",
        ],
        "data_bytes": ["0x03", "0x84", "0x00", "0x00"],
        "run_b_scb_bytes": [
            "0x05", "0x10", "0x20", "next->SCB2", "data1",
            "0x14", "0x00", "0x1E", "0x00", "0x00", "0x01",
            "0x00", "0x01", "0x00", "0x00", "0x0F", "0x0F",
            "0x03", "0x00", "0x00", "0x00", "0x00", "0x00",
        ],
        "field_differences": [
            "sprctl0/type: 0x01 TYPE_BACKNONCOLL vs 0x05 TYPE_NONCOLL",
            "next: 0x0000 vs SCB2 for SCB1",
            "data pointer: pixel_bitmap vs injected data1/data2 (data bytes identical)",
            "hpos/vpos: 0/0 vs (20,30)/(40,30)",
            "hsize/vsize: 0xA000/0x6600 vs 0x0100/0x0100",
            "palette: driver has one trailing palette byte 0x00; Run B has 8 bytes 00 0F 0F 03 00 00 00 00",
        ],
        "same_fields": [
            "sprctl1=0x10 PACKED|REHV",
            "sprcoll=0x20 NO_COLLIDE",
            "packed data=03 84 00 00",
        ],
    }


def chain_record(payload, scratch_address):
    records = []
    for index in range(2):
        offset = index * SCB_SIZE
        entry = payload[offset:offset + SCB_SIZE]
        records.append({
            "address": "0x%04X" % (scratch_address + offset),
            "sprctl0": "0x%02X" % entry[0],
            "sprctl1": "0x%02X" % entry[1],
            "sprcoll": "0x%02X" % entry[2],
            "next": "0x%04X" % unpack_word(entry, 3),
            "data": "0x%04X" % unpack_word(entry, 5),
            "hpos": unpack_word(entry, 7),
            "vpos": unpack_word(entry, 9),
            "hsize": "0x%04X" % unpack_word(entry, 11),
            "vsize": "0x%04X" % unpack_word(entry, 13),
            "penpal": ["0x%02X" % value for value in entry[15:23]],
        })
    return records


def map_value(map_path, symbol):
    match = re.search(
        r"(?:^|\s)" + re.escape(symbol) + r"\s+([0-9A-Fa-f]{6})\s+",
        map_path.read_text(encoding="utf-8"), re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("cannot locate %s in %s" % (symbol, map_path))
    return int(match.group(1), 16)


def map_segment(map_path, name):
    match = re.search(
        r"^" + re.escape(name) +
        r"\s+([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})\s+"
        r"([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{5})\s*$",
        map_path.read_text(encoding="utf-8"), re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("cannot locate %s segment in %s" % (name, map_path))
    return {
        "start": "0x%04X" % int(match.group(1), 16),
        "end": "0x%04X" % int(match.group(2), 16),
        "size": int(match.group(3), 16),
        "size_hex": "0x%04X" % int(match.group(3), 16),
        "align": "0x%02X" % int(match.group(4), 16),
    }


def map_layout(map_path, kind):
    segments = {name: map_segment(map_path, name)
                for name in ("STARTUP", "CODE", "RODATA", "DATA", "BSS")}
    main_start = map_value(map_path, "__MAIN_START__")
    main_size = map_value(map_path, "__MAIN_SIZE__")
    stack_size = map_value(map_path, "__STACKSIZE__")
    main_end = main_start + main_size
    bss_end = int(segments["BSS"]["end"], 16) + 1
    spare = main_end - bss_end
    baseline = BASELINE_BSS[kind]
    return {
        "kind": kind,
        "map": str(map_path),
        "segments": segments,
        "main_start": "0x%04X" % main_start,
        "main_size": main_size,
        "main_size_hex": "0x%04X" % main_size,
        "main_end_exclusive": "0x%04X" % main_end,
        "main_spare_after_bss_bytes": spare,
        "stack_reserved_bytes": stack_size,
        "bss_bytes": segments["BSS"]["size"],
        "bss_baseline_bytes": baseline,
        "bss_non_increased": segments["BSS"]["size"] <= baseline,
        "main_spare_at_least_256": spare >= 256,
    }


def page_record(raw, page_address, path, expected_addresses):
    path.write_bytes(raw)
    changed = []
    for offset, after in enumerate(raw):
        if after != SENTINEL:
            changed.append({
                "address": "0x%04X" % (page_address + offset),
                "offset": offset,
                "before": "0x%02X" % SENTINEL,
                "after": "0x%02X" % after,
            })
    expected_values = {
        address: value for address, value in expected_addresses
        if page_address <= address < page_address + PAGE_SIZE
    }
    return {
        "cpu_address": "0x%04X" % page_address,
        "bytes": len(raw),
        "raw_file": path.name,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "sentinel": "0x%02X" % SENTINEL,
        "changed_byte_count": len(changed),
        "changed_bytes": changed,
        "expected_target_bytes": [
            {"address": "0x%04X" % address,
             "expected": "0x%02X" % value,
             "actual": "0x%02X" % raw[address - page_address]}
            for address, value in expected_values.items()
        ],
    }


def page_values(raw, page_address, addresses):
    return [raw[address - page_address] for address in addresses
            if page_address <= address < page_address + PAGE_SIZE]


def run_case(args, visual, static_module, game_address, enemy_address,
             ioctl_address, sync_address, scratch_address, run_name,
             output_dir):
    process = subprocess.Popen(
        [GEARLYNX] + ([] if args.gui else ["--headless"]) + [
            "--mcp-http", "--mcp-http-port", str(MCP_PORT),
            str(args.rom), str(args.symbols),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    request_id = 1
    result = {
        "run": run_name,
        "process_isolated": True,
        "rom_sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
        "scratch_address": "0x%04X" % scratch_address,
    }
    try:
        for _ in range(30):
            try:
                visual.call("initialize", {
                    "protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "aps053-o5", "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start for Run %s" % run_name)

        voice_active_address = scratch_address + 640 + 6
        request_id = static_module.wait_stable_title(
            visual, game_address, voice_active_address, request_id
        )
        visual.tool("set_breakpoint", {"address": "%04X" % sync_address}, request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_breakpoint(
            visual, request_id + 1, "O5 pre-draw boundary Run %s" % run_name
        )
        visual.tool("remove_breakpoint", {"address": "%04X" % sync_address}, request_id)
        request_id += 1
        request_id = static_module.state_injection(
            visual, game_address, enemy_address, 1, request_id
        )
        request_id = write_chunks(visual, PAGE_C038, PAGE_SIZE, SENTINEL, request_id)
        request_id = write_chunks(visual, PAGE_E018, PAGE_SIZE, SENTINEL, request_id)
        request_id, c038_prefill = read_chunks(
            visual, PAGE_C038, PAGE_SIZE, request_id
        )
        request_id, e018_prefill = read_chunks(
            visual, PAGE_E018, PAGE_SIZE, request_id
        )
        result["sentinel_prefill"] = {
            "value": "0x%02X" % SENTINEL,
            "page_c038_all_sentinel": all(value == SENTINEL for value in c038_prefill),
            "page_e018_all_sentinel": all(value == SENTINEL for value in e018_prefill),
            "page_c038_sha256": hashlib.sha256(c038_prefill).hexdigest(),
            "page_e018_sha256": hashlib.sha256(e018_prefill).hexdigest(),
        }

        visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_breakpoint(
            visual, request_id + 1, "O5 _tgi_ioctl entry Run %s" % run_name
        )
        entry_cpu = visual.tool("get_6502_status", request_id=request_id)
        request_id += 1
        request_id, entry_registers = register_snapshot(visual, request_id)
        request_id, original_chain = read_chunks(
            visual, scratch_address, CHAIN_SIZE, request_id
        )
        chain, palettes, differences = make_chain(scratch_address, run_name)
        visual.write_bytes(scratch_address, list(chain), request_id)
        request_id += 1
        request_id, injected_readback = read_chunks(
            visual, scratch_address, CHAIN_SIZE, request_id
        )
        result["entry"] = {
            "breakpoint": "0x%04X" % ioctl_address,
            "cpu": entry_cpu,
            "pc_matches_ioctl": int(entry_cpu["PC"], 16) == ioctl_address,
            "registers": entry_registers,
            "fastcall_candidates": {
                "AX_little_endian": "0x%04X" % (
                    int(entry_cpu["A"], 16) | (int(entry_cpu["X"], 16) << 8)
                ),
                "XA_little_endian": "0x%04X" % (
                    int(entry_cpu["X"], 16) | (int(entry_cpu["A"], 16) << 8)
                ),
            },
            "fastcall_pointer_matches_scb_head": any(
                value == "0x%04X" % scratch_address
                for value in (
                    "0x%04X" % (int(entry_cpu["A"], 16) |
                                (int(entry_cpu["X"], 16) << 8)),
                    "0x%04X" % (int(entry_cpu["X"], 16) |
                                (int(entry_cpu["A"], 16) << 8)),
                )
            ),
            "original_chain_sha256": hashlib.sha256(original_chain).hexdigest(),
            "injected_chain_bytes": CHAIN_SIZE,
            "injected_chain_sha256": hashlib.sha256(chain).hexdigest(),
            "injected_chain_write_readback_match": injected_readback == chain,
            "injected_chain": chain_record(chain, scratch_address),
            "data1": ["0x%02X" % value for value in chain[46:50]],
            "data2": ["0x%02X" % value for value in chain[50:54]],
            "penpal": [["0x%02X" % value for value in palette]
                       for palette in palettes],
            "bisect_differences": differences,
        }
        visual.tool("debug_step_out", request_id=request_id)
        request_id += 1
        visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
        request_id += 1
        return_cpu = visual.tool("get_6502_status", request_id=request_id)
        request_id += 1
        request_id, return_registers = register_snapshot(visual, request_id)
        request_id, c038 = read_chunks(visual, PAGE_C038, PAGE_SIZE, request_id)
        request_id, e018 = read_chunks(visual, PAGE_E018, PAGE_SIZE, request_id)

        selected = return_registers["selected"]
        vidbas = selected["VIDBAS"]
        dispadr = selected["DISPADR"]
        if vidbas is None or dispadr is None:
            raise RuntimeError("Run %s missing VIDBAS/DISPADR readback" % run_name)
        vidbas_address = vidbas["int"]
        dispadr_address = dispadr["int"]
        if vidbas_address not in (PAGE_C038, PAGE_E018):
            raise RuntimeError("Run %s returned invalid VIDBAS 0x%04X" %
                               (run_name, vidbas_address))
        expected_values = expected_for_run(run_name, vidbas_address)
        pages = {}
        for page_address, raw, label in (
                (PAGE_C038, c038, "c038"), (PAGE_E018, e018, "e018")):
            path = output_dir / ("phase-2r-o5-run-%s-%s.bin" %
                                 (run_name.lower(), label))
            pages["0x%04X" % page_address] = page_record(
                raw, page_address, path, expected_values
            )
        target_raw = c038 if vidbas_address == PAGE_C038 else e018
        actual = page_values(target_raw, vidbas_address,
                             [address for address, _ in expected_values])
        expected = [value for _, value in expected_values]
        result["return"] = {
            "cpu": return_cpu,
            "registers": return_registers,
            "return_register_readback_available": return_registers["readback_available"],
            "physical_page_mapping": {
                "VIDBAS": "0x%04X" % vidbas_address,
                "DISPADR": "0x%04X" % dispadr_address,
                "target_page_cpu_address": "0x%04X" % vidbas_address,
                "draw_page_selected_from_return_VIDBAS": True,
                "hardcoded_draw_page_used": False,
            },
            "expected_pixel_positions": [
                {"x": x, "y": y,
                 "address": "0x%04X" % address,
                 "expected_byte": "0x%02X" % value}
                for (x, y), (address, value) in
                zip(PIXEL_POSITIONS, expected_values)
            ],
            "target_page_actual_bytes": ["0x%02X" % value for value in actual],
            "target_page_expected_bytes": ["0x%02X" % value for value in expected],
            "target_page_expected_values_match": actual == expected,
            "target_page_both_pixels_match": (
                len(expected) == 2 and actual == expected
            ),
            "pages": pages,
        }
        target_changed = any(
            record["changed_byte_count"] != 0
            for record in pages.values()
            if record["cpu_address"] == "0x%04X" % vidbas_address
        )
        result["diagnosis"] = {
            "run_expected_bytes_match": actual == expected,
            "changed_byte_addresses_recorded": True,
            "other_physical_page_read": True,
            "classification": (
                "expected_values_match" if actual == expected
                else "no_target_pixel_write" if not target_changed
                else "partial_or_wrong_pixel_write"
            ),
        }
        return result
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def release_layout(args):
    if not args.map.is_file() or not args.cadence_map.is_file():
        raise RuntimeError("normal/cadence map files are required for O5 evidence")
    return {
        "normal": map_layout(args.map, "normal"),
        "cadence": map_layout(args.cadence_map, "cadence"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path, default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--map", type=Path, default=Path("build/asteroid-patrol.map"))
    parser.add_argument("--cadence-map", type=Path,
                        default=Path("build/asteroid-patrol-cadence.map"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-053/phase-2r-o5-v012.json"))
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    if not args.rom.is_file() or not args.symbols.is_file():
        raise RuntimeError("release ROM/label file is missing")
    rom_sha256 = hashlib.sha256(args.rom.read_bytes()).hexdigest()
    if rom_sha256 != EXPECTED_RELEASE_SHA256:
        raise RuntimeError("release ROM SHA-256 changed: %s" % rom_sha256)
    if GAME_VERSION not in (ROOT / "include" / "version.h").read_text(encoding="utf-8"):
        raise RuntimeError("release version is not %s" % GAME_VERSION)

    visual = load_visual_module()
    static_module = load_static_module()
    game_address = visual.symbol_address(args.symbols, "_game")
    enemy_address = visual.symbol_address(args.symbols, "_game_enemies")
    ioctl_address = visual.symbol_address(args.symbols, "_tgi_ioctl")
    sync_address = visual.symbol_address(args.symbols,
                                         "_game_display_sync_complete")
    scratch_address = visual.symbol_address(
        args.symbols, "_title_voice_scratch_buffer"
    )
    output_dir = args.output.parent
    evidence = {
        "aps": "APS-053",
        "phase": "2R-2",
        "gate": "A",
        "diagnostic": "O5 minimal SCB chain Run A/B",
        "version": GAME_VERSION,
        "status": "blocked",
        "rom": {
            "path": str(args.rom),
            "size_bytes": args.rom.stat().st_size,
            "sha256": rom_sha256,
            "expected_release_sha256": EXPECTED_RELEASE_SHA256,
            "release_sha256_unchanged": rom_sha256 == EXPECTED_RELEASE_SHA256,
        },
        "release_layout": release_layout(args),
        "symbols": {
            "_game": "0x%04X" % game_address,
            "_game_enemies": "0x%04X" % enemy_address,
            "_tgi_ioctl": "0x%04X" % ioctl_address,
            "_game_display_sync_complete": "0x%04X" % sync_address,
            "_title_voice_scratch_buffer": "0x%04X" % scratch_address,
        },
        "physical_framebuffers": {
            "page_c038": {"cpu_address": "0xC038", "bytes": PAGE_SIZE},
            "page_e018": {"cpu_address": "0xE018", "bytes": PAGE_SIZE},
        },
        "method": {
            "release_source_or_rom_modified": False,
            "fixture": "TITLE stable -> sync breakpoint -> GAME_PHASE_STAGE_INTRO, player (250,250), enemies inactive",
            "entry": "real _tgi_ioctl breakpoint; AX/XA and SCB head recorded",
            "chain_bytes": CHAIN_SIZE,
            "scb_layout": "SCB_REHV_PAL 23B x2, data 4B x2, scratch head",
            "data_bytes": ["0x03", "0x84", "0x00", "0x00"],
            "sentinel": "0x%02X" % SENTINEL,
            "return_registers": ["SCBNEXT", "SPRGO", "SPRSYS", "VIDBAS", "DISPADR"],
            "raw_page_read": "CPU read_bytes at 0xC038/0xE018; no screenshot/framebuffer API",
            "run_process_isolation": "Run A and Run B use separate Gearlynx processes",
            "bisect_max_followups": len(BISECT_RUNS),
            "bisect_policy": "Run C1/C2/C3 only after Run B no-write; stop at first separating result",
        },
        "driver_cls_sprite_comparison": cls_sprite_comparison(),
        "runs": [],
    }
    try:
        for run_name in RUNS:
            result = run_case(
                args, visual, static_module, game_address, enemy_address,
                ioctl_address, sync_address, scratch_address, run_name,
                output_dir,
            )
            evidence["runs"].append(result)
            print("Run %s: %s" % (
                run_name,
                "PASS" if result["diagnosis"]["run_expected_bytes_match"] else "MISMATCH",
            ))
        run_a, run_b = evidence["runs"]
        bisect_attempts = []
        if run_b["diagnosis"]["classification"] == "no_target_pixel_write":
            for run_name in BISECT_RUNS:
                result = run_case(
                    args, visual, static_module, game_address, enemy_address,
                    ioctl_address, sync_address, scratch_address, run_name,
                    output_dir,
                )
                evidence["runs"].append(result)
                bisect_attempts.append(run_name)
                print("Run %s: %s" % (
                    run_name,
                    "PASS" if result["diagnosis"]["run_expected_bytes_match"]
                    else "MISMATCH",
                ))
                if result["diagnosis"]["run_expected_bytes_match"]:
                    break
        else:
            evidence["diagnosis_note"] = "Run B separated without follow-up; bisect not needed"
        bisect_results = [
            item for item in evidence["runs"] if item["run"] in BISECT_RUNS
        ]
        a_match = run_a["diagnosis"]["run_expected_bytes_match"]
        b_match = run_b["diagnosis"]["run_expected_bytes_match"]
        b_no_target_write = run_b["diagnosis"]["classification"] == (
            "no_target_pixel_write"
        )
        both_pages_recorded = all(
            len(result["return"]["pages"]) == 2
            for result in evidence["runs"]
        )
        layout_ok = all(
            item["main_spare_at_least_256"] and item["bss_non_increased"]
            for item in evidence["release_layout"].values()
        )
        evidence["diagnosis"] = {
            "run_a_both_pixels_match": a_match,
            "run_b_both_pixels_match": b_match,
            "bisect_attempts": bisect_attempts,
            "bisect_maximum_not_exceeded": len(bisect_attempts) <= len(BISECT_RUNS),
            "bisect_results": [
                {
                    "run": item["run"],
                    "classification": item["diagnosis"]["classification"],
                    "expected_values_match": item["diagnosis"]["run_expected_bytes_match"],
                    "differences": item["entry"].get("bisect_differences", []),
                }
                for item in bisect_results
            ],
            "all_changed_bytes_saved_with_before_after": True,
            "run_a_b_run_b_separate_processes": True,
            "main_spare_and_bss_guard": layout_ok,
            "classification": (
                "penpal_nibble_mapping_error_confirmed"
                if a_match and b_match else
                "cls_type_control_difference_separated"
                if a_match and b_no_target_write and any(
                    item["run"] == "C1" and
                    item["diagnosis"]["run_expected_bytes_match"]
                    for item in bisect_results
                ) else
                "run_a_nonzero_penpal0_draws; run_b_zero_penpal0_no_target_write"
                if a_match and b_no_target_write else
                "O5_pixel_or_chain_result_requires_followup"
            ),
            "expected_interpretation": {
                "Run A": "VIDBAS+30*80+10=0xFA, VIDBAS+30*80+20=0xCA",
                "Run B": "same addresses=0x0A, release penpal[0]=0",
            },
            "unresolved_if_mismatch": [
                "first-only: conditional A' order-swap chain test",
                "location mismatch: HPOS/nibble/offset candidates",
                "no change: SCB control/data format or Suzy chain execution",
            ],
        }
        evidence["status"] = (
            "done" if evidence["diagnosis"]["classification"] !=
            "O5_pixel_or_chain_result_requires_followup" else "blocked"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        return 0
    except Exception as error:
        evidence["error"] = str(error)
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print("BLOCKED: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
