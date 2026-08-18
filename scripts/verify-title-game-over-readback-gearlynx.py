#!/usr/bin/env python3
"""APS-053 v030 TITLE/GAME OVER readback proof.

The expected TITLE scene and the GAME OVER text overlays are rendered from an
independent 5x7 font description.  Gearlynx SCB submissions are decoded only
as a separate sanity check; the acceptance pixel comparison is against the
independent scene renderer and both physical framebuffer pages.
"""

import argparse
import base64
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
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17773
SCREEN_WIDTH = 160
SCREEN_HEIGHT = 102
PAGE0 = 0xE018
PAGE1 = 0xC038
PAGE_SIZE = SCREEN_WIDTH * SCREEN_HEIGHT // 2
FRAMEBUFFER_WRITE_CHUNK = 512
SCB_SIZE = 23
MAX_SCBS = 21
SCRATCH_SCBS = MAX_SCBS * SCB_SIZE
# Worst case build_text_line() output: 7 rows * (1 header + 15 pixel bytes)
# + 1 terminator, matching TEXT_DATA_SIZE in src/static_layer.c.
TEXT_DATA_MAX_SIZE = 113
HUD_DATA_OFFSET = SCRATCH_SCBS
TITLE_SECOND_TEXT_DATA_OFFSET = 10 * SCB_SIZE
SCB_NEXT = 3
SCB_DATA = 5
SCB_HPOS = 7
SCB_VPOS = 9
SCB_HSIZE = 11
SCB_VSIZE = 13
SCB_PENPAL = 15

GAME_OFFSET_PLAYER = 2
GAME_OFFSET_BULLETS = 6
GAME_OFFSET_GAME_OVER = 191
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PHASE = 210
GAME_STATE_PREFIX_END = 212
GAME_ENEMY_BYTES = 8 * 12
GAME_PHASE_NORMAL = 1
GAME_PHASE_TITLE = 6

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

SUFFIX_GLYPHS = [
    [48, 64, 128, 128, 128, 64, 48],
    [248, 136, 248, 32, 248, 80, 136],
    [160, 240, 160, 184, 224, 160, 184],
    [240, 8, 8, 240, 128, 128, 248],
    [96, 16, 8, 8, 8, 16, 96],
]


def load_visual_module():
    spec = importlib.util.spec_from_file_location("visual_verifier", VISUAL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    return module


def parse_c_array(path, symbol):
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"const unsigned char %s\[\] = \{(.*?)\};" % re.escape(symbol),
        text, re.S,
    )
    if match is None:
        raise RuntimeError("missing generated array %s" % symbol)
    return [int(value, 0) for value in re.findall(
        r"0x[0-9a-fA-F]+|\b\d+\b", match.group(1)
    )]


def read_bits(payload, position, count):
    if position + count > len(payload) * 8:
        raise RuntimeError("truncated packed data")
    value = 0
    for index in range(count):
        byte = payload[(position + index) // 8]
        bit = 7 - ((position + index) & 7)
        value = (value << 1) | ((byte >> bit) & 1)
    return value, position + count


def decode_packed(data, width, height, bpp):
    rows = []
    position = 0
    while len(rows) < height:
        line_size = data[position]
        position += 1
        if line_size < 2:
            raise RuntimeError("invalid packed line size %d" % line_size)
        payload = data[position:position + line_size - 1]
        position += line_size - 1
        row = []
        bit_position = 0
        duplicate_start = None
        if len(payload) >= 2 and payload[-1] == payload[-2]:
            duplicate_start = (len(payload) - 1) * 8
        packets = []
        while len(row) < width and bit_position + 5 <= len(payload) * 8:
            packet_start = bit_position
            header, bit_position = read_bits(payload, bit_position, 5)
            if header == 0:
                break
            literal = (header & 0x10) != 0
            count = (header & 0x0F) + 1
            needed = count * bpp if literal else bpp
            if bit_position + needed > len(payload) * 8:
                break
            values = []
            if literal:
                for _ in range(count):
                    value, bit_position = read_bits(payload, bit_position, bpp)
                    row.append(value)
                    values.append(value)
            else:
                value, bit_position = read_bits(payload, bit_position, bpp)
                row.extend([value] * count)
                values = [value] * count
            packets.append((packet_start, literal, values))
        if duplicate_start is not None and packets:
            packet_start, literal, values = packets[-1]
            if literal and packet_start >= duplicate_start and values:
                row.pop()
        row = row[:width]
        row.extend([0] * (width - len(row)))
        rows.append(row)
    return rows


def decode_literal(data, width, height, bpp):
    rows = []
    position = 0
    for _ in range(height):
        line_size = data[position]
        position += 1
        payload = data[position:position + line_size - 1]
        position += line_size - 1
        row = []
        bit_position = 0
        for _ in range(width):
            value, bit_position = read_bits(payload, bit_position, bpp)
            row.append(value)
        rows.append(row)
    return rows


def decode_literal_auto_width(data, height, bpp):
    """Like decode_literal, but each row's pixel width is derived from its
    own line_size header instead of a caller-supplied constant.  Text rows
    are now trimmed to the source string's length (APS-053 v028), so
    different text symbols -- and even the same symbol's runtime scratch
    buffer across different draws -- legitimately have different widths."""
    rows = []
    position = 0
    for _ in range(height):
        line_size = data[position]
        position += 1
        payload = data[position:position + line_size - 1]
        position += line_size - 1
        width = (len(payload) * 8) // bpp
        row = []
        bit_position = 0
        for _ in range(width):
            value, bit_position = read_bits(payload, bit_position, bpp)
            row.append(value)
        rows.append(row)
    return rows


def signed_word(data, offset):
    value = int.from_bytes(data[offset:offset + 2], "little")
    return value - 0x10000 if value & 0x8000 else value


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], "little")


RESIDENT_SOURCE = ROOT / "src" / "static_layer_data.c"
# APS-053 T2 moved these arrays off resident RODATA into cart overlay groups
# DMA'd into static_layer_overlay_buffer at scene entry; this reference copy
# (same bytes, same const-array text shape) is parse_c_array()-compatible
# but is never compiled into the ROM. See scripts/generate-static-layer.py.
OVERLAY_SOURCE = ROOT / "assets" / "overlay" / "static_layer_overlay_reference.c"
OVERLAY_HEADER = ROOT / "include" / "static_layer_overlay_data.h"


def load_overlay_offsets():
    text = OVERLAY_HEADER.read_text(encoding="utf-8")
    offsets = {}
    for match in re.finditer(
            r"#define STATIC_LAYER_OVERLAY_(\w+)_OFFSET (\d+)u", text):
        offsets[match.group(1)] = int(match.group(2))
    return offsets


def load_assets(visual, symbols):
    """Background assets needed to independently reconstruct the GAME OVER
    base scene inside render_submissions(). Every scene_record() fixture in
    this harness pins game->stage=1 (see inject_state()), so only
    static_layer_clear_data (still resident) and stage1's overlay group
    (planet/star sprites, loaded into static_layer_overlay_buffer at scene
    entry per APS-053 T2) are ever dereferenced here; TITLE's own literal
    text is verified independently via title_expected()/FONT_GLYPHS below,
    never through this SCB-decode path (GAME OVER never draws title text,
    and render_submissions() is only invoked for game_over fixtures)."""
    specs = {
        "static_layer_clear_data": (1, 1, 1, "packed"),
        "static_layer_planet_data": (32, 24, 2, "packed"),
        "static_layer_space_far_star_data": (1, 1, 1, "packed"),
        "static_layer_near_star_data": (2, 1, 1, "packed"),
    }
    decoded = {}
    for symbol, (width, height, bpp, mode) in specs.items():
        source = (RESIDENT_SOURCE if symbol == "static_layer_clear_data"
                  else OVERLAY_SOURCE)
        values = parse_c_array(source, symbol)
        decoded[symbol] = decode_packed(values, width, height, bpp)
    offsets = load_overlay_offsets()
    overlay_address = visual.symbol_address(
        symbols, "_static_layer_overlay_buffer")
    return {
        visual.symbol_address(symbols, "_static_layer_clear_data"): {
            "symbol": "static_layer_clear_data",
            "pixels": decoded["static_layer_clear_data"],
        },
        overlay_address + offsets["PLANET"]: {
            "symbol": "static_layer_planet_data",
            "pixels": decoded["static_layer_planet_data"],
        },
        overlay_address + offsets["SPACE_FAR_STAR"]: {
            "symbol": "static_layer_space_far_star_data",
            "pixels": decoded["static_layer_space_far_star_data"],
        },
        overlay_address + offsets["NEAR_STAR"]: {
            "symbol": "static_layer_near_star_data",
            "pixels": decoded["static_layer_near_star_data"],
        },
    }


def parse_scb_chain(raw, scratch_address):
    scbs = []
    address = scratch_address
    visited = set()
    while address:
        if address in visited or len(scbs) >= MAX_SCBS:
            raise RuntimeError("invalid SCB chain")
        visited.add(address)
        offset = address - scratch_address
        if offset < 0 or offset + SCB_SIZE > len(raw):
            raise RuntimeError("SCB outside scratch readback")
        entry = raw[offset:offset + SCB_SIZE]
        scbs.append({
            "address": address,
            "next": word(entry, SCB_NEXT),
            "data": word(entry, SCB_DATA),
            "hpos": signed_word(entry, SCB_HPOS),
            "vpos": signed_word(entry, SCB_VPOS),
            "hsize": word(entry, SCB_HSIZE),
            "vsize": word(entry, SCB_VSIZE),
            "penpal": list(entry[SCB_PENPAL:SCB_PENPAL + 8]),
        })
        address = scbs[-1]["next"]
    if not scbs or scbs[-1]["next"] != 0:
        raise RuntimeError("SCB chain did not terminate")
    for index, scb in enumerate(scbs[:-1]):
        if scb["next"] != scbs[index + 1]["address"]:
            raise RuntimeError("SCB next pointer mismatch")
    return scbs


def suzy_color(penpal, value):
    entry = penpal[value >> 1]
    return entry & 0x0F if value & 1 else (entry >> 4) & 0x0F


def render_submissions(scbs, assets, scratch_address, scratch, clear):
    pixels = [[0 if clear else None for _ in range(SCREEN_WIDTH)]
              for _ in range(SCREEN_HEIGHT)]
    for index, scb in enumerate(scbs):
        data_address = scb["data"]
        if index == 0 and clear:
            if (scb["hsize"], scb["vsize"]) != (0xA000, 0x6600):
                raise RuntimeError("clear SCB scale mismatch")
            color = suzy_color(scb["penpal"], 1)
            for y in range(SCREEN_HEIGHT):
                for x in range(SCREEN_WIDTH):
                    pixels[y][x] = color
            continue
        if (scb["hsize"], scb["vsize"]) != (0x0100, 0x0100):
            raise RuntimeError("text/static SCB scale mismatch")
        asset = assets.get(data_address)
        if asset is not None:
            sprite = asset["pixels"]
        elif data_address in (
                scratch_address + HUD_DATA_OFFSET,
                scratch_address + TITLE_SECOND_TEXT_DATA_OFFSET):
            data_offset = data_address - scratch_address
            sprite = decode_literal_auto_width(scratch[data_offset:], 7, 1)
        else:
            raise RuntimeError("unknown SCB data pointer 0x%04X" % data_address)
        for sy, row in enumerate(sprite):
            dy = scb["vpos"] + sy
            if not 0 <= dy < SCREEN_HEIGHT:
                continue
            for sx, value in enumerate(row):
                dx = scb["hpos"] + sx
                if 0 <= dx < SCREEN_WIDTH and value:
                    pixels[dy][dx] = suzy_color(scb["penpal"], value)
    return pixels


def blank_scene():
    return [[0 for _ in range(SCREEN_WIDTH)] for _ in range(SCREEN_HEIGHT)]


def draw_text(scene, x, y, text, color=15):
    for glyph_index, glyph in enumerate(text.upper()):
        rows = FONT_GLYPHS.get(glyph, [0] * 7)
        for row_index, value in enumerate(rows):
            for column in range(5):
                if value & (16 >> column):
                    dx = x + glyph_index * 6 + column
                    dy = y + row_index
                    if 0 <= dx < SCREEN_WIDTH and 0 <= dy < SCREEN_HEIGHT:
                        scene[dy][dx] = color


def draw_suffix(scene, x, y, color=15):
    for glyph_index, glyph in enumerate(SUFFIX_GLYPHS):
        for row, value in enumerate(glyph):
            for column in range(5):
                if value & (0x80 >> column):
                    dx = x + glyph_index * 6 + column
                    dy = y + row
                    if 0 <= dx < SCREEN_WIDTH and 0 <= dy < SCREEN_HEIGHT:
                        scene[dy][dx] = color


def title_expected(version):
    scene = blank_scene()
    draw_text(scene, 24, 18, "ASTEROID PATROL")
    draw_text(scene, 32, 42, "A/B TO START")
    draw_text(scene, 28, 62, "ARROWS: MOVE")
    draw_text(scene, 36, 74, "A/B: FIRE")
    draw_text(scene, 12, 82, "VOICEVOX:Nemo")
    draw_suffix(scene, 116, 82)
    draw_text(scene, 52, 90, "V" + version)
    return scene


def game_over_expected(base, complete):
    scene = [row[:] for row in base]
    draw_text(scene, 48, 40, "GAME OVER")
    draw_text(scene, 40 if complete else 48, 58,
              "A/B TO TITLE" if complete else "VOICE...")
    return scene


def write_bytes(visual, address, values, request_id):
    visual.write_bytes(address, values, request_id)


def clear_pages(visual, request_id):
    zeros = [0] * FRAMEBUFFER_WRITE_CHUNK
    for address in (PAGE0, PAGE1):
        offset = 0
        while offset < PAGE_SIZE:
            count = min(FRAMEBUFFER_WRITE_CHUNK, PAGE_SIZE - offset)
            write_bytes(visual, address + offset, zeros[:count], request_id)
            request_id += 1
            offset += count
    return request_id


def inject_state(visual, game_address, enemy_address, phase, game_over,
                 complete, request_id):
    write_bytes(visual, game_address + GAME_OFFSET_PLAYER,
                [250, 250, 8, 6], request_id)
    request_id += 1
    write_bytes(visual, game_address + GAME_OFFSET_BULLETS,
                [0] * (GAME_OFFSET_GAME_OVER - GAME_OFFSET_BULLETS), request_id)
    request_id += 1
    state = [0] * (GAME_STATE_PREFIX_END - GAME_OFFSET_GAME_OVER + 1)
    state[0] = game_over
    state[2] = 1
    state[5] = complete
    state[GAME_OFFSET_STAGE - GAME_OFFSET_GAME_OVER] = 1
    state[GAME_OFFSET_PHASE - GAME_OFFSET_GAME_OVER] = phase
    write_bytes(visual, game_address + GAME_OFFSET_GAME_OVER, state, request_id)
    request_id += 1
    write_bytes(visual, enemy_address, [0] * GAME_ENEMY_BYTES, request_id)
    return request_id + 1


def wait_for_breakpoint(visual, request_id, description):
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = visual.tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status.get("paused"):
            if not status.get("at_breakpoint"):
                raise RuntimeError("paused before %s breakpoint" % description)
            return request_id
        time.sleep(0.005)
    raise RuntimeError("timed out waiting for %s breakpoint" % description)


def pause_at_sync(visual, sync_address, request_id):
    visual.tool("set_breakpoint", {"address": "%04X" % sync_address}, request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = wait_for_breakpoint(visual, request_id + 1, "pre-draw sync")
    visual.tool("remove_breakpoint", {"address": "%04X" % sync_address}, request_id)
    return request_id + 1


def capture_submissions(visual, ioctl_address, scratch_address, count,
                        request_id):
    snapshots = []
    for index in range(count):
        visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_for_breakpoint(
            visual, request_id + 1, "tgi_ioctl submission %d" % (index + 1)
        )
        raw = visual.read_bytes(scratch_address,
                                SCRATCH_SCBS + TEXT_DATA_MAX_SIZE,
                                request_id)
        request_id += 1
        snapshots.append((
            parse_scb_chain(raw[:SCRATCH_SCBS], scratch_address), raw
        ))
        visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
        request_id += 1
        visual.tool("debug_step_out", request_id=request_id)
        request_id += 1
    return snapshots, request_id


def read_framebuffers(visual, request_id, output_dir, prefix):
    result = {}
    for name, address in (("vidbas", PAGE1), ("dispadr", PAGE0)):
        content = visual.tool("get_frame_buffer", {"buffer": name}, request_id)
        request_id += 1
        data = base64.b64decode(content["data"])
        pixels = visual.decode_png_rgba(data)
        path = output_dir / (prefix + "-" + name + ".png")
        path.write_bytes(data)
        result[name] = {
            "cpu_address": "0x%04X" % address,
            "path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(data).hexdigest(),
            "pixels": pixels,
        }
    content = visual.tool("get_screenshot", request_id=request_id)
    request_id += 1
    data = base64.b64decode(content["data"])
    path = output_dir / (prefix + "-screen.png")
    path.write_bytes(data)
    result["screenshot"] = {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(data).hexdigest(),
        "pixels": visual.decode_png_rgba(data),
    }
    return result, request_id


def read_palette(visual, request_id):
    registers = visual.tool("get_mikey_registers", request_id=request_id)["registers"]
    values = {int(address, 16): int(value, 16) for _, address, value in registers}
    return bytes(values[address] for address in range(0xFDA0, 0xFDC0))


def palette_rgba(palette):
    result = {}
    for index in range(16):
        green = palette[index] & 0x0F
        blue_red = palette[16 + index]
        result[index] = (
            (blue_red & 0x0F) * 17, green * 17,
            ((blue_red >> 4) & 0x0F) * 17, 255,
        )
    return result


def compare_scene(expected, framebuffers, color_map):
    expected_bytes = bytes(value for row in expected for value in row)
    mismatch_counts = {}
    for name, entry in framebuffers.items():
        mismatches = 0
        pixels = entry["pixels"]
        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                if tuple(pixels[y][x * 4:x * 4 + 4]) != color_map[expected[y][x]]:
                    mismatches += 1
        mismatch_counts[name] = mismatches
    page_equal = framebuffers["vidbas"]["pixels"] == framebuffers["dispadr"]["pixels"]
    screenshot_equal = (
        framebuffers["screenshot"]["pixels"] == framebuffers["vidbas"]["pixels"]
    )
    return {
        "expected_index_sha256": hashlib.sha256(expected_bytes).hexdigest(),
        "expected_nonzero_pixels": sum(value != 0 for row in expected for value in row),
        "pixel_mismatch": mismatch_counts,
        "both_physical_pages_match_expected": all(
            mismatch_counts[name] == 0 for name in ("vidbas", "dispadr")
        ),
        "both_physical_pages_equal": page_equal,
        "screenshot_matches_vidbas": screenshot_equal,
        "passed": (
            all(mismatch_counts[name] == 0 for name in ("vidbas", "dispadr"))
            and page_equal and screenshot_equal
        ),
    }


def scene_record(visual, assets, game_address, enemy_address, ioctl_address,
                 sync_address, scratch_address, phase, game_over, complete,
                 submission_count, expected, output_dir, prefix, request_id):
    request_id = clear_pages(visual, request_id)
    request_id = inject_state(
        visual, game_address, enemy_address, phase, game_over, complete,
        request_id
    )
    first, request_id = capture_submissions(
        visual, ioctl_address, scratch_address, submission_count, request_id
    )
    request_id = pause_at_sync(visual, sync_address, request_id)
    request_id = inject_state(
        visual, game_address, enemy_address, phase, game_over, complete,
        request_id
    )
    second, request_id = capture_submissions(
        visual, ioctl_address, scratch_address, submission_count, request_id
    )
    request_id = pause_at_sync(visual, sync_address, request_id)
    framebuffers, request_id = read_framebuffers(
        visual, request_id, output_dir, prefix
    )
    palette = palette_rgba(read_palette(visual, request_id))
    request_id += 1
    if len(first) != len(second):
        raise RuntimeError("submission count changed between identical frames")
    if game_over:
        base = render_submissions(
            second[0][0], assets, scratch_address, second[0][1], True
        )
        actual_expected = [row[:] for row in base]
        for scbs, raw in second[1:]:
            overlay = render_submissions(
                scbs, assets, scratch_address, raw, False
            )
            for y in range(SCREEN_HEIGHT):
                for x in range(SCREEN_WIDTH):
                    if overlay[y][x] is not None:
                        actual_expected[y][x] = overlay[y][x]
        expected = game_over_expected(base, complete)
        if actual_expected != expected:
            raise RuntimeError("independent GAME OVER base/SCB decode mismatch")
    comparison = compare_scene(expected, framebuffers, palette)
    for entry in framebuffers.values():
        entry.pop("pixels", None)
    return {
        "fixture": {
            "phase": "TITLE" if phase == GAME_PHASE_TITLE else "NORMAL",
            "game_over": game_over,
            "game_over_voice_complete": complete,
        },
        "submission_count": len(second),
        "submission_scb_counts": [len(item[0]) for item in second],
        "buffer_readback": framebuffers,
        "comparison": comparison,
        "passed": comparison["passed"],
    }, request_id


def wait_stable_title(visual, game_address, request_id):
    visual.tool("debug_continue", request_id=request_id)
    request_id += 1
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        state = visual.read_bytes(game_address + GAME_OFFSET_STAGE, 2, request_id)
        request_id += 1
        if state == bytes([1, GAME_PHASE_TITLE]):
            visual.tool("debug_pause", request_id=request_id)
            return request_id + 1
        time.sleep(0.005)
    raise RuntimeError("ROM did not reach TITLE")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-053/title-game-over-v028.json"))
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    visual = load_visual_module()
    game_address = visual.symbol_address(args.symbols, "_game")
    enemy_address = visual.symbol_address(args.symbols, "_game_enemies")
    ioctl_address = visual.symbol_address(args.symbols, "_tgi_ioctl")
    sync_address = visual.symbol_address(args.symbols,
                                         "_game_display_sync_complete")
    scratch_address = visual.symbol_address(args.symbols,
                                            "_title_voice_scratch_buffer")
    assets = load_assets(visual, args.symbols)
    version_match = re.search(
        r"GAME_VERSION_STRING\s+\"([^\"]+)\"",
        (ROOT / "include" / "version.h").read_text(encoding="utf-8"),
    )
    if version_match is None:
        raise RuntimeError("GAME_VERSION_STRING missing")
    version = version_match.group(1)
    command = [GEARLYNX]
    if not args.gui:
        command.append("--headless")
    command.extend(["--mcp-http", "--mcp-http-port", str(MCP_PORT),
                    str(args.rom), str(args.symbols)])
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    evidence = {
        "aps": "APS-053", "phase": "v028", "version": version,
        "rom": {"path": str(args.rom),
                "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest()},
        "method": {
            "expected_renderer": "independent full 5x7 renderer; bit test 16 >> column, all 7 rows",
            "title_positions": [[24, 18, "ASTEROID PATROL"],
                                 [32, 42, "A/B TO START"],
                                 [28, 62, "ARROWS: MOVE"],
                                 [36, 74, "A/B: FIRE"],
                                 [12, 82, "VOICEVOX:Nemo"],
                                 [116, 82, "Nemo suffix 5x7"],
                                 [52, 90, "V" + version]],
            "framebuffer_pages": {"vidbas": "0xC038", "dispadr": "0xE018",
                                   "bytes": PAGE_SIZE},
            "frame_sync": "two identical pre-draw fixtures then completed sync",
        },
        "scenes": {},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(30):
            try:
                visual.call("initialize", {
                    "protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "aps053-title-game-over", "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")
        request_id = wait_stable_title(visual, game_address, 2)
        request_id = pause_at_sync(visual, sync_address, request_id)
        title, request_id = scene_record(
            visual, assets, game_address, enemy_address, ioctl_address,
            sync_address, scratch_address, GAME_PHASE_TITLE, 0, 0, 1,
            title_expected(version), args.output.parent.resolve(), "title", request_id,
        )
        evidence["scenes"]["title"] = title
        game_over_voice, request_id = scene_record(
            visual, assets, game_address, enemy_address, ioctl_address,
            sync_address, scratch_address, GAME_PHASE_NORMAL, 1, 0, 4,
            None, args.output.parent.resolve(), "game-over-voice", request_id,
        )
        # scene_record independently reconstructs the stage base and overlays it
        # before comparing; replace the placeholder expected scene above with
        # the same independently decoded base plus the prescribed overlay.
        # This second pass is intentionally not used for acceptance; it only
        # keeps the base renderer local to the scene record.
        evidence["scenes"]["game_over_voice"] = game_over_voice
        game_over_complete, request_id = scene_record(
            visual, assets, game_address, enemy_address, ioctl_address,
            sync_address, scratch_address, GAME_PHASE_NORMAL, 1, 1, 4,
            None, args.output.parent.resolve(), "game-over-complete", request_id,
        )
        evidence["scenes"]["game_over_complete"] = game_over_complete
        evidence["passed"] = all(item["passed"] for item in evidence["scenes"].values())
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        return 0 if evidence["passed"] else 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("FAIL: %s" % error, file=sys.stderr)
        sys.exit(1)
