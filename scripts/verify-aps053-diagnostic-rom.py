#!/usr/bin/env python3
"""Verify APS-053's Suzy text ROM and fixed text assets.

This check does not use Gearlynx's renderer.  It validates the LNX artifact,
the version marker, the generator/runtime bit-mask split, and the generated
fixed text bytes against an independent full 5x7 font description.

The hardware L/R BIT TEST / "A V 0 5 6" diagnostic that this script
originally verified was removed in APS-053 T0-3 once the user confirmed the
font-corruption issue it was added to diagnose was resolved on real
hardware (v030). This script keeps validating the remaining fixed text
assets and ROM/version invariants.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_HEADER = ROOT / "include" / "version.h"
STATIC_LAYER = ROOT / "src" / "static_layer.c"
GENERATOR = ROOT / "scripts" / "generate-static-layer.py"
STATIC_DATA = ROOT / "src" / "static_layer_data.c"
# APS-053 T2 moved the fixed title text arrays off resident RODATA into a
# cart overlay group; this reference copy (generated alongside the real
# assets/overlay/title.bin payload) keeps them parse_c_array()-compatible.
OVERLAY_DATA = ROOT / "assets" / "overlay" / "static_layer_overlay_reference.c"

FONT_GLYPHS = {
    "A": [14, 17, 17, 31, 17, 17, 17],
    "B": [30, 17, 17, 30, 17, 17, 30],
    "C": [14, 17, 16, 16, 16, 17, 14],
    "D": [30, 17, 17, 17, 17, 17, 30],
    "E": [31, 16, 16, 30, 16, 16, 31],
    "F": [31, 16, 16, 30, 16, 16, 16],
    "G": [14, 17, 16, 23, 17, 17, 14],
    "H": [17, 17, 17, 31, 17, 17, 17],
    "I": [31, 4, 4, 4, 4, 4, 31],
    "J": [7, 2, 2, 2, 2, 18, 12],
    "K": [17, 18, 20, 24, 20, 18, 17],
    "L": [16, 16, 16, 16, 16, 16, 31],
    "M": [17, 27, 21, 21, 17, 17, 17],
    "N": [17, 25, 21, 19, 17, 17, 17],
    "O": [14, 17, 17, 17, 17, 17, 14],
    "P": [30, 17, 17, 30, 16, 16, 16],
    "Q": [14, 17, 17, 17, 21, 18, 13],
    "R": [30, 17, 17, 30, 20, 18, 17],
    "S": [15, 16, 16, 14, 1, 1, 30],
    "T": [31, 4, 4, 4, 4, 4, 4],
    "U": [17, 17, 17, 17, 17, 17, 14],
    "V": [17, 17, 17, 17, 10, 10, 4],
    "W": [17, 17, 17, 21, 21, 27, 17],
    "X": [17, 17, 10, 4, 10, 17, 17],
    "Y": [17, 17, 10, 4, 4, 4, 4],
    "Z": [31, 1, 2, 4, 8, 16, 31],
    "0": [14, 17, 19, 21, 25, 17, 14],
    "1": [4, 12, 4, 4, 4, 4, 14],
    "2": [14, 17, 1, 2, 4, 8, 31],
    "3": [30, 1, 1, 14, 1, 1, 30],
    "4": [2, 6, 10, 18, 31, 2, 2],
    "5": [31, 16, 16, 30, 1, 1, 30],
    "6": [14, 16, 16, 30, 17, 17, 14],
    "7": [31, 1, 2, 4, 8, 8, 8],
    "8": [14, 17, 17, 14, 17, 17, 14],
    "9": [14, 17, 17, 15, 1, 1, 14],
    "/": [1, 2, 2, 4, 4, 8, 16],
    ":": [0, 4, 4, 0, 0, 4, 4],
    ".": [0, 0, 0, 0, 0, 6, 6],
}

FIXED_TEXTS = {
    "ASTEROID PATROL": "static_layer_text_asteroid_patrol_data",
    "A/B TO START": "static_layer_text_ab_to_start_data",
    "ARROWS: MOVE": "static_layer_text_arrows_move_data",
    "A/B: FIRE": "static_layer_text_ab_fire_data",
    "VOICEVOX:Nemo": "static_layer_text_voicevox_nemo_data",
}


def parse_c_array(text, symbol):
    match = re.search(
        r"const unsigned char %s\[\] = \{(.*?)\};" % re.escape(symbol),
        text, re.S,
    )
    if match is None:
        raise RuntimeError("missing generated array %s" % symbol)
    return [int(value, 0) for value in re.findall(
        r"0x[0-9a-fA-F]+|\b\d+\b", match.group(1)
    )]


def append_bits(stream, value, count):
    for shift in range(count - 1, -1, -1):
        stream.append((value >> shift) & 1)


def pack_literal(text):
    length = min(len(text), 20)
    pixel_bytes = (length * 6 + 7) // 8
    data = []
    for row in range(7):
        data.append(pixel_bytes + 1)
        pixels = [0] * pixel_bytes
        pixel = 0
        for glyph in text[:length]:
            bits = FONT_GLYPHS.get(glyph.upper(), [0] * 7)[row]
            for column in range(5):
                if bits & (16 >> column):
                    pixels[pixel // 8] |= 0x80 >> (pixel & 7)
                pixel += 1
            pixel += 1
        data.extend(pixels)
    data.append(0)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-053/diagnostic-rom-v028.json"))
    parser.add_argument("--expected-version", default="0.53.9")
    args = parser.parse_args()

    rom = args.rom.resolve()
    payload = rom.read_bytes()
    version_text = VERSION_HEADER.read_text(encoding="utf-8")
    version_match = re.search(r'GAME_VERSION_STRING\s+"([^"]+)"', version_text)
    if version_match is None:
        raise RuntimeError("GAME_VERSION_STRING missing")
    version = version_match.group(1)
    if version != args.expected_version:
        raise RuntimeError("source version %s != expected %s" %
                           (version, args.expected_version))
    if payload[:4] != b"LYNX":
        raise RuntimeError("invalid LNX magic")
    bank0_page, bank1_page, lnx_version = struct.unpack_from("<HHH", payload, 4)
    if lnx_version != 1 or bank0_page not in (512, 1024, 2048) or bank1_page != 0:
        raise RuntimeError("invalid LNX header")
    payload_offsets = [index for index in range(len(payload))
                       if payload.startswith(version.encode("ascii"), index)]
    if len(payload_offsets) != 1:
        raise RuntimeError("expected exactly one version payload, found %d" %
                           len(payload_offsets))

    static_text = STATIC_LAYER.read_text(encoding="utf-8")
    generator_text = GENERATOR.read_text(encoding="utf-8")
    dynamic_block = static_text.split("static void build_text_line", 1)[1].split(
        "static const unsigned char*", 1)[0]
    generator_block = generator_text.split("def text_line_data", 1)[1].split(
        "fixed_texts =", 1)[0]
    if "(unsigned char)(16u >> column)" not in dynamic_block:
        raise RuntimeError("runtime dynamic text mask is not 16u >> column")
    if "bits & (16 >> column)" not in generator_block:
        raise RuntimeError("generator fixed text mask is not 16 >> column")
    if "static_layer_title_text(58, 28, 5u" in static_text:
        raise RuntimeError("removed L/R BIT TEST diagnostic is still wired into TITLE")
    if 'static_layer_text(62, 34, "A V 0 5 6"' in static_text:
        raise RuntimeError("removed A V 0 5 6 diagnostic is still wired into TITLE")

    data_text = OVERLAY_DATA.read_text(encoding="utf-8")
    fixed_checks = {}
    for text, symbol in FIXED_TEXTS.items():
        actual = parse_c_array(data_text, symbol)
        expected = pack_literal(text)
        if actual != expected:
            raise RuntimeError("fixed text mismatch: %s" % text)
        fixed_checks[text] = {
            "symbol": symbol,
            "bytes": len(actual),
            "sha256": hashlib.sha256(bytes(actual)).hexdigest(),
            "matches_independent_renderer": True,
        }

    evidence = {
        "aps": "APS-053",
        "phase": "v030",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "minimum versioned ROM for old-ROM/transfer separation",
        "version": version,
        "rom": {
            "path": str(rom),
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "payload_size": len(payload) - 64,
            "lnx": {"version": lnx_version, "bank0_page": bank0_page,
                    "bank1_page": bank1_page},
            "version_payload_offsets": payload_offsets,
        },
        "source": {
            "version_header_sha256": hashlib.sha256(
                VERSION_HEADER.read_bytes()).hexdigest(),
            "generator_sha256": hashlib.sha256(
                GENERATOR.read_bytes()).hexdigest(),
            "static_layer_runtime_sha256": hashlib.sha256(
                STATIC_LAYER.read_bytes()).hexdigest(),
            "static_layer_data_sha256": hashlib.sha256(
                STATIC_DATA.read_bytes()).hexdigest(),
            "runtime_dynamic_mask": "16u >> column",
            "generator_fixed_mask": "16 >> column",
            "fixed_texts": fixed_checks,
        },
        "classification": {
            "old_rom_or_wrong_file": "confirmed_possible_before_v026; separated by unique version 0.53.6",
            "LNX_header_or_payload_corruption": "not_observed_locally",
            "cc65_SCB_packing_or_penpal_mismatch": "not_determinable_on_physical_hardware",
            "real_hardware_transfer_identity": "not_determinable_locally",
        },
        "physical_confirmation_required": [
            "SHA-256 of the exact file sent to the cartridge writer must equal this ROM sha256",
            "TITLE must show V" + version,
            "record cartridge writer/transfer log and reset/reload procedure",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PASS: APS-053 v030 text asset ROM")
    print("ROM: %s size=%d sha256=%s version=%s payload_offset=0x%X" %
          (rom, len(payload), evidence["rom"]["sha256"], version,
           payload_offsets[0]))
    print("TEXT: fixed=%d independent full 5x7 renderer; dynamic masks verified" %
          len(fixed_checks))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("FAIL: %s" % error)
        raise SystemExit(1)
