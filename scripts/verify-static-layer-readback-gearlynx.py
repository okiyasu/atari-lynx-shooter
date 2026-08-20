#!/usr/bin/env python3
"""APS-053 Phase 2R-2 static SCB and framebuffer readback contract.

The verifier stops at the real tgi_ioctl sprite submission entry, reads the
SCB chain from the shared scratch buffer, then renders the submitted SCBs
independently and compares both Lynx TGI framebuffer pages. Dynamic gameplay
objects are placed outside the framebuffer so the comparison covers only the
static background and HUD layers.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import re
import struct
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUAL_PATH = ROOT / "scripts" / "verify-stage-visuals-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17771
SCREEN_WIDTH = 160
SCREEN_HEIGHT = 102
PAGE_SIZE = SCREEN_WIDTH * SCREEN_HEIGHT // 2
FRAMEBUFFER_WRITE_CHUNK = 512
PAGE0 = 0xE018
PAGE1 = 0xC038
GAME_OFFSET_PLAYER = 2
GAME_OFFSET_BULLETS = 6
GAME_OFFSET_GAME_OVER = 191
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PLANET_OFFSET = 200
GAME_OFFSET_FAR_STAR_OFFSET = 202
GAME_OFFSET_NEAR_STAR_OFFSET = 203
GAME_OFFSET_PHASE_STAGE_INTRO = 210
GAME_STATE_PREFIX_END = 213
GAME_PHASE_STAGE_INTRO = 0
GAME_ENEMY_BYTES = 8 * 12
SCB_SIZE = 23
MAX_SCBS = 21
SCRATCH_SCBS = MAX_SCBS * SCB_SIZE
# Worst case build_text_line() output: 7 rows * (1 header + 15 pixel bytes)
# + 1 terminator, matching TEXT_DATA_SIZE in src/static_layer.c (APS-053 T1
# unified the HUD onto the 5x7 build_text_line() path).
# v049 (Path B, .briefs/APS-053/v048.md/v049.md Fable5 design): HUD cells
# are 8px wide (1 byte/cell, no byte-boundary straddling), not
# build_text_line()'s 6px pitch -- HUD_DATA is now 7*(1+20)+1 = 148 bytes
# (was 7*(1+15)+1 = 113), width 20*8 = 160px (was 120px).
HUD_DATA_MAX_SIZE = 148
HUD_WIDTH = 20 * 8
HUD_HEIGHT = 7
SCB_SPRCTL0 = 0
SCB_SPRCTL1 = 1
SCB_NEXT = 3
SCB_DATA = 5
SCB_HPOS = 7
SCB_VPOS = 9
SCB_HSIZE = 11
SCB_VSIZE = 13
SCB_PENPAL = 15


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
        raise RuntimeError("truncated Suzy pixel stream")
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
        if position >= len(data):
            raise RuntimeError("packed sprite ended at row %d" % len(rows))
        line_size = data[position]
        position += 1
        if line_size == 0:
            raise RuntimeError("packed sprite ended early at row %d" % len(rows))
        if line_size == 1:
            raise RuntimeError("unexpected Suzy quadrant marker at row %d" % len(rows))
        payload = data[position:position + line_size - 1]
        position += line_size - 1
        row = []
        bit_position = 0
        packets = []
        duplicate_start = None
        if len(payload) >= 2 and payload[-1] == payload[-2]:
            duplicate_start = (len(payload) - 1) * 8
        while len(row) < width and bit_position + 5 <= len(payload) * 8:
            packet_start = bit_position
            header, bit_position = read_bits(payload, bit_position, 5)
            if header == 0:
                break
            literal = (header & 0x10) != 0
            count = (header & 0x0F) + 1
            # Packed packets carry one pixel value and repeat it; literal
            # packets carry all values. Treating both as count*bpp truncates
            # valid 2bpp runs before the next packet header.
            required_bits = count * bpp if literal else bpp
            if bit_position + required_bits > len(payload) * 8:
                # A packed line may end exactly on a byte boundary, or carry
                # the encoder's duplicated final byte workaround. In both
                # cases the remaining bits are padding, not another packet.
                if (duplicate_start is not None and
                        packet_start == duplicate_start and literal and
                        bit_position + bpp <= len(payload) * 8):
                    # The hardware consumes the first value bit available in
                    # a truncated literal packet that begins in the duplicate
                    # byte, then stops at the line boundary.
                    value, bit_position = read_bits(payload, bit_position, bpp)
                    row.append(value)
                break
            if literal:
                values = []
                for _ in range(count):
                    value, bit_position = read_bits(payload, bit_position, bpp)
                    row.append(value)
                    values.append(value)
            else:
                value, bit_position = read_bits(payload, bit_position, bpp)
                row.extend([value] * count)
                values = [value] * count
            packets.append((packet_start, literal, values))
        # sp65 duplicates a final byte when the line ends with a set bit.
        # Suzy can consume the packet header in that duplicate byte but does
        # not emit its final incomplete literal value. Keep the independent
        # renderer aligned with that hardware boundary behavior without
        # trimming valid packets that end before the duplicate byte.
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
    for row_index in range(height):
        if position >= len(data):
            raise RuntimeError("literal sprite ended at row %d" % row_index)
        line_size = data[position]
        position += 1
        if line_size < 1:
            raise RuntimeError("invalid literal line size %d" % line_size)
        payload = data[position:position + line_size - 1]
        position += line_size - 1
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
# (same bytes, same const-array text shape, generated alongside the real
# assets/overlay/*.bin payloads) is parse_c_array()-compatible but is never
# compiled into the ROM. See scripts/generate-static-layer.py.
OVERLAY_SOURCE = ROOT / "assets" / "overlay" / "static_layer_overlay_reference.c"
OVERLAY_HEADER = ROOT / "include" / "static_layer_overlay_data.h"
# Which overlay-group members are resident in static_layer_overlay_buffer for
# each stage; mirrors the OVERLAY_GROUPS stage1/stage2/stage3 members in
# scripts/generate-static-layer.py. Only the background/star sprites are
# listed here (not the star position tables, which this harness doesn't
# exercise, matching the pre-T2 asset set below).
STAGE_OVERLAY_MEMBERS = {
    1: [("PLANET", "static_layer_planet_data"),
        ("SPACE_FAR_STAR", "static_layer_space_far_star_data"),
        ("NEAR_STAR", "static_layer_near_star_data")],
    2: [("MOUNTAIN", "static_layer_mountain_data"),
        ("MID_CLOUD", "static_layer_mid_cloud_data"),
        ("NEAR_CLOUD", "static_layer_near_cloud_data")],
    3: [("CAVE_WALL", "static_layer_cave_wall_data"),
        ("CAVE_ROCK", "static_layer_cave_rock_data"),
        ("CAVE_NEAR", "static_layer_cave_near_data")],
}


def load_overlay_offsets():
    text = OVERLAY_HEADER.read_text(encoding="utf-8")
    offsets = {}
    for match in re.finditer(
            r"#define STATIC_LAYER_OVERLAY_(\w+)_OFFSET (\d+)u", text):
        offsets[match.group(1)] = int(match.group(2))
    return offsets


def load_static_assets():
    assets = {
        "static_layer_clear_data": (1, 1, 1, "packed", RESIDENT_SOURCE),
        "static_layer_planet_data": (32, 24, 2, "packed", OVERLAY_SOURCE),
        "static_layer_mountain_data": (192, 21, 1, "packed", OVERLAY_SOURCE),
        "static_layer_mid_cloud_data": (160, 44, 1, "packed", OVERLAY_SOURCE),
        "static_layer_near_cloud_data": (160, 26, 1, "packed", OVERLAY_SOURCE),
        "static_layer_cave_wall_data": (192, 61, 1, "packed", OVERLAY_SOURCE),
        "static_layer_cave_rock_data": (160, 89, 1, "packed", OVERLAY_SOURCE),
        "static_layer_cave_near_data": (160, 79, 1, "packed", OVERLAY_SOURCE),
        "static_layer_space_far_star_data": (1, 1, 1, "packed", OVERLAY_SOURCE),
        "static_layer_near_star_data": (2, 1, 1, "packed", OVERLAY_SOURCE),
    }
    result = {}
    for symbol, (width, height, bpp, mode, source) in assets.items():
        values = parse_c_array(source, symbol)
        result[symbol] = {
            "width": width,
            "height": height,
            "bpp": bpp,
            "mode": mode,
            "data": values,
            "pixels": decode_packed(values, width, height, bpp),
        }
    return result


def suzy_pixel_color(penpal, value):
    """Resolve a Suzy pixel value to its 4-bit palette color.

    Suzy stores two palette entries per penpal byte: odd pixel values use
    the low nibble and even pixel values use the high nibble.
    """
    if value < 0 or value >= 16:
        raise RuntimeError("Suzy pixel index out of range: %d" % value)
    palette_index = value >> 1
    if palette_index >= len(penpal):
        raise RuntimeError("Suzy palette entry missing for pixel %d" % value)
    palette_byte = penpal[palette_index]
    if value & 1:
        return palette_byte & 0x0F
    return (palette_byte >> 4) & 0x0F


def render_scb_chain(scbs, data_to_asset, scratch_address, scratch_bytes):
    pixels = [[0 for _ in range(SCREEN_WIDTH)] for _ in range(SCREEN_HEIGHT)]
    for index, scb in enumerate(scbs):
        hsize = scb["hsize"]
        vsize = scb["vsize"]
        data_address = scb["data"]
        if index == 0:
            if (hsize, vsize) != (0xA000, 0x6600):
                raise RuntimeError(
                    "clear SCB scale mismatch: hsize=0x%04X vsize=0x%04X" %
                    (hsize, vsize)
                )
            color = suzy_pixel_color(scb["penpal"], 1)
            for y in range(SCREEN_HEIGHT):
                for x in range(SCREEN_WIDTH):
                    pixels[y][x] = color
            continue
        if (hsize, vsize) != (0x0100, 0x0100):
            raise RuntimeError(
                "non-clear SCB scale mismatch at index %d: "
                "hsize=0x%04X vsize=0x%04X" % (index, hsize, vsize)
            )
        asset = data_to_asset.get(data_address)
        if asset is not None:
            sprite = asset["pixels"]
        elif data_address == scratch_address + SCRATCH_SCBS:
            sprite = decode_literal(scratch_bytes, HUD_WIDTH, HUD_HEIGHT, 1)
            asset = {"width": HUD_WIDTH, "height": HUD_HEIGHT, "bpp": 1}
        else:
            raise RuntimeError(
                "SCB[%d] data pointer 0x%04X is not a known static asset/HUD" %
                (index, data_address)
            )
        for sy, row in enumerate(sprite):
            dy = scb["vpos"] + sy
            if dy < 0 or dy >= SCREEN_HEIGHT:
                continue
            for sx, value in enumerate(row):
                dx = scb["hpos"] + sx
                if dx < 0 or dx >= SCREEN_WIDTH or value == 0:
                    continue
                pixels[dy][dx] = suzy_pixel_color(scb["penpal"], value)
    return pixels


def flatten_indices(pixels):
    return bytes(value for row in pixels for value in row)


def read_framebuffer_png(visual, buffer_name, request_id):
    content = visual.tool("get_frame_buffer", {"buffer": buffer_name}, request_id)
    if content.get("type") != "image":
        raise RuntimeError("Gearlynx %s framebuffer did not return PNG" % buffer_name)
    data = base64.b64decode(content["data"])
    return data, visual.decode_png_rgba(data)


def read_screenshot_png(visual, request_id):
    content = visual.tool("get_screenshot", request_id=request_id)
    if content.get("type") != "image":
        raise RuntimeError("Gearlynx screenshot did not return PNG")
    data = base64.b64decode(content["data"])
    return data, visual.decode_png_rgba(data)


def compare_indexed_pixels(expected, actual_a, actual_b, color_map):
    if len(actual_a) != SCREEN_HEIGHT or len(actual_b) != SCREEN_HEIGHT:
        raise RuntimeError("Gearlynx framebuffer dimensions mismatch")
    mismatches = []
    for y in range(SCREEN_HEIGHT):
        for x in range(SCREEN_WIDTH):
            expected_color = color_map.get(expected[y][x])
            actual_color = tuple(actual_a[y][x * 4:x * 4 + 4])
            other_color = tuple(actual_b[y][x * 4:x * 4 + 4])
            if expected_color is None:
                mismatches.append({"x": x, "y": y, "reason": "palette_missing",
                                   "index": expected[y][x]})
            elif actual_color != expected_color:
                mismatches.append({"x": x, "y": y, "reason": "pixel",
                                   "index": expected[y][x],
                                   "expected_rgba": list(expected_color),
                                   "actual_rgba": list(actual_color)})
            if actual_color != other_color:
                mismatches.append({"x": x, "y": y, "reason": "buffer_divergence",
                                   "vidbas_rgba": list(actual_color),
                                   "dispadr_rgba": list(other_color)})
            if len(mismatches) >= 20:
                return mismatches, color_map
    return mismatches, color_map


def stage_palette_rgba(visual, stage):
    generator = visual.load_generator()
    palettes = visual.generated_palettes(
        generator, ROOT / "assets" / "stages" / "stages.json"
    )
    palette = palettes[stage - 1]
    return {
        index: tuple(visual.palette_rgb(palette, index)) + (255,)
        for index in range(16)
    }


def rgba_histogram(rows):
    counts = {}
    for row in rows:
        for x in range(SCREEN_WIDTH):
            color = tuple(row[x * 4:x * 4 + 4])
            counts[str(color)] = counts.get(str(color), 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8])


def parse_scb_chain(raw, scratch_address):
    scbs = []
    address = scratch_address
    visited = set()
    while address != 0:
        if address in visited:
            raise RuntimeError("SCB chain cycle at 0x%04X" % address)
        if len(scbs) >= MAX_SCBS:
            raise RuntimeError("SCB chain exceeds %d entries" % MAX_SCBS)
        visited.add(address)
        offset = address - scratch_address
        if offset < 0 or offset + SCB_SIZE > len(raw):
            raise RuntimeError("SCB address outside scratch readback: 0x%04X" % address)
        entry = raw[offset:offset + SCB_SIZE]
        scbs.append({
            "address": address,
            "sprctl0": entry[SCB_SPRCTL0],
            "sprctl1": entry[SCB_SPRCTL1],
            "sprcoll": entry[2],
            "next": word(entry, SCB_NEXT),
            "data": word(entry, SCB_DATA),
            "hpos": signed_word(entry, SCB_HPOS),
            "vpos": signed_word(entry, SCB_VPOS),
            "hsize": word(entry, SCB_HSIZE),
            "vsize": word(entry, SCB_VSIZE),
            "penpal": list(entry[SCB_PENPAL:SCB_PENPAL + 8]),
        })
        address = scbs[-1]["next"]
    if not scbs:
        raise RuntimeError("empty SCB chain")
    for index, scb in enumerate(scbs[:-1]):
        expected = scbs[index + 1]["address"]
        if scb["next"] != expected:
            raise RuntimeError("SCB[%d] next=0x%04X expected=0x%04X" %
                               (index, scb["next"], expected))
    if scbs[-1]["next"] != 0:
        raise RuntimeError("SCB chain did not terminate")
    return scbs


def state_injection(visual, game_address, enemy_address, stage, request_id):
    # Keep the stage in intro for a deterministic static-only fixture. The
    # player is outside the 160x102 display and all enemy/object slots are off.
    visual.write_bytes(game_address + GAME_OFFSET_PLAYER,
                       [250, 250, 8, 6], request_id)
    visual.write_bytes(game_address + GAME_OFFSET_BULLETS,
                       [0] * (GAME_OFFSET_GAME_OVER - GAME_OFFSET_BULLETS),
                       request_id + 1)
    state = [0] * (GAME_STATE_PREFIX_END - GAME_OFFSET_GAME_OVER + 1)
    state[GAME_OFFSET_STAGE - GAME_OFFSET_GAME_OVER] = stage
    state[GAME_OFFSET_PHASE_STAGE_INTRO - GAME_OFFSET_GAME_OVER] = (
        GAME_PHASE_STAGE_INTRO
    )
    state[GAME_OFFSET_PLANET_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    state[GAME_OFFSET_FAR_STAR_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    state[GAME_OFFSET_NEAR_STAR_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    visual.write_bytes(game_address + GAME_OFFSET_GAME_OVER, state, request_id + 2)
    visual.write_bytes(enemy_address, [0] * GAME_ENEMY_BYTES, request_id + 3)
    return request_id + 4


def clear_framebuffer_pages(visual, request_id):
    """Remove prior-frame pixels before the static-only fixture begins."""
    payload = [0] * FRAMEBUFFER_WRITE_CHUNK
    for address in (PAGE0, PAGE1):
        offset = 0
        while offset < PAGE_SIZE:
            count = min(FRAMEBUFFER_WRITE_CHUNK, PAGE_SIZE - offset)
            visual.write_bytes(address + offset, payload[:count], request_id)
            request_id += 1
            offset += count
    return request_id


def wait_stable_title(visual, game_address, voice_active_address, request_id):
    visual.tool("debug_continue", request_id=2)
    request_id = 3
    stable = 0
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        state = visual.read_bytes(game_address + 209, 2, request_id)
        request_id += 1
        voice_active = visual.read_bytes(voice_active_address, 1, request_id)
        request_id += 1
        if state == bytes([1, 6]) and voice_active == b"\x00":
            stable += 1
            if stable == 2:
                visual.tool("debug_pause", request_id=request_id)
                return request_id + 1
        else:
            stable = 0
        time.sleep(0.005)
    raise RuntimeError("ROM did not reach stable TITLE")


def verify_stage(visual, game_address, enemy_address, ioctl_address,
                 sync_address, logic_address, sound_address, scratch_address,
                 assets, stage, request_id,
                 output_dir):
    # Enter the main loop's pre-draw boundary first. This drains a draw that
    # may already have been in flight when the TITLE state was paused, so the
    # first _tgi_ioctl hit below belongs to this stage's static layer.
    visual.tool("set_breakpoint", {"address": "%04X" % sync_address}, request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = visual.wait_for_breakpoint(request_id + 1,
                                            "stage %d pre-draw boundary" % stage)
    visual.tool("remove_breakpoint", {"address": "%04X" % sync_address}, request_id)
    request_id += 1
    request_id = clear_framebuffer_pages(visual, request_id)
    request_id = state_injection(visual, game_address, enemy_address, stage,
                                 request_id)
    visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = visual.wait_for_breakpoint(request_id + 1,
                                            "stage %d SCB submission" % stage)
    scratch = visual.read_bytes(scratch_address, MAX_SCBS * SCB_SIZE + HUD_DATA_MAX_SIZE,
                                request_id)
    request_id += 1
    scbs = parse_scb_chain(scratch[:MAX_SCBS * SCB_SIZE], scratch_address)
    scratch_hud = scratch[MAX_SCBS * SCB_SIZE:MAX_SCBS * SCB_SIZE + HUD_DATA_MAX_SIZE]
    # static_layer_clear_data stays resident with a fixed symbol address; the
    # other assets live at run-time-variable offsets within the single
    # shared static_layer_overlay_buffer, loaded per scene (APS-053 T2).
    # Only this stage's three overlay members are resident at capture time,
    # so data_to_asset must be rebuilt per stage rather than reused globally.
    overlay_offsets = load_overlay_offsets()
    overlay_address = visual.symbol_address(
        Path("build/asteroid-patrol.lbl"), "_static_layer_overlay_buffer"
    )
    data_to_asset = {
        assets["static_layer_clear_data"]["address"]:
            assets["static_layer_clear_data"],
    }
    for offset_name, symbol in STAGE_OVERLAY_MEMBERS[stage]:
        data_to_asset[overlay_address + overlay_offsets[offset_name]] = \
            assets[symbol]
    expected = render_scb_chain(scbs, data_to_asset, scratch_address,
                                scratch_hud)
    expected_indices = flatten_indices(expected)
    visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
    request_id += 1
    visual.tool("debug_step_out", request_id=request_id)
    request_id += 1
    # The first draw used the fixture injected at the pre-draw sync boundary.
    # Reach the next sync boundary, inject again before its draw, and capture
    # that second identical frame for the other physical page.
    visual.tool("set_breakpoint", {"address": "%04X" % sync_address}, request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = visual.wait_for_breakpoint(
        request_id + 1, "stage %d second-frame pre-draw sync" % stage
    )
    visual.tool("remove_breakpoint", {"address": "%04X" % sync_address}, request_id)
    request_id += 1
    request_id = state_injection(visual, game_address, enemy_address, stage,
                                 request_id)
    visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = visual.wait_for_breakpoint(
        request_id + 1, "stage %d second-frame SCB submission" % stage
    )
    repeated_scratch = visual.read_bytes(
        scratch_address, MAX_SCBS * SCB_SIZE + HUD_DATA_MAX_SIZE, request_id
    )
    request_id += 1
    repeated_scbs = parse_scb_chain(
        repeated_scratch[:MAX_SCBS * SCB_SIZE], scratch_address
    )
    scbs = repeated_scbs
    repeated_hud = repeated_scratch[MAX_SCBS * SCB_SIZE:
                                    MAX_SCBS * SCB_SIZE + HUD_DATA_MAX_SIZE]
    expected = render_scb_chain(repeated_scbs, data_to_asset, scratch_address,
                                repeated_hud)
    expected_indices = flatten_indices(expected)
    visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
    request_id += 1
    visual.tool("debug_step_out", request_id=request_id)
    request_id += 1
    # The following sync swaps the second identical frame into the front
    # buffer, leaving both physical pages with the same static readback.
    visual.tool("set_breakpoint", {"address": "%04X" % sync_address}, request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = visual.wait_for_breakpoint(
        request_id + 1, "stage %d second-frame completed sync" % stage
    )
    visual.tool("remove_breakpoint", {"address": "%04X" % sync_address}, request_id)
    request_id += 1
    page0_png, page0 = read_framebuffer_png(visual, "vidbas", request_id)
    request_id += 1
    page1_png, page1 = read_framebuffer_png(visual, "dispadr", request_id)
    request_id += 1
    screenshot_png, screenshot = read_screenshot_png(visual, request_id)
    request_id += 1
    (output_dir / ("stage%d-vidbas.png" % stage)).write_bytes(page0_png)
    (output_dir / ("stage%d-dispadr.png" % stage)).write_bytes(page1_png)
    (output_dir / ("stage%d-screen.png" % stage)).write_bytes(screenshot_png)
    color_map = stage_palette_rgba(visual, stage)
    mismatch_list, color_map = compare_indexed_pixels(
        expected, page0, page1, color_map
    )
    expected_nonzero = sum(
        1 for row in expected for value in row if value != 0
    )
    buffers_equal = page0 == page1
    return request_id, {
        "stage": stage,
        "scb_count": len(scbs),
        "scb_chain": scbs,
        "expected_index_sha256": hashlib.sha256(expected_indices).hexdigest(),
        "palette_rgba_map": {str(index): list(color)
                              for index, color in color_map.items()},
        "buffer_readback": {
            "vidbas": {"cpu_address": "0x%04X" % PAGE1,
                       "png": "stage%d-vidbas.png" % stage,
                       "png_sha256": hashlib.sha256(page0_png).hexdigest()},
            "dispadr": {"cpu_address": "0x%04X" % PAGE0,
                         "png": "stage%d-dispadr.png" % stage,
                         "png_sha256": hashlib.sha256(page1_png).hexdigest()},
            "screenshot": {"png": "stage%d-screen.png" % stage,
                           "png_sha256": hashlib.sha256(screenshot_png).hexdigest()},
            "page_size": PAGE_SIZE,
            "expected_nonzero_pixels": expected_nonzero,
            "vidbas_rgba_histogram": rgba_histogram(page0),
            "dispadr_rgba_histogram": rgba_histogram(page1),
            "buffers_equal": buffers_equal,
            "both_match_expected": not mismatch_list,
            "mismatches": mismatch_list,
        },
        "passed": not mismatch_list,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path, default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-053/phase-2r-v006.json"))
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
    logic_address = visual.symbol_address(args.symbols, "_game_update_logic")
    sound_address = visual.symbol_address(args.symbols, "_game_sound_tick")
    scratch_address = visual.symbol_address(args.symbols,
                                         "_title_voice_scratch_buffer")
    voice_active_address = scratch_address + 640 + 6
    assets = load_static_assets()
    label_path = args.symbols
    for symbol, entry in assets.items():
        entry["symbol"] = "_" + symbol
    # static_layer_clear_data is the only asset with a fixed resident symbol
    # left after APS-053 T2; the other nine live at stage-dependent offsets
    # within _static_layer_overlay_buffer, resolved per stage in
    # verify_stage() via STAGE_OVERLAY_MEMBERS instead.
    assets["static_layer_clear_data"]["address"] = visual.symbol_address(
        label_path, assets["static_layer_clear_data"]["symbol"]
    )
    command = [GEARLYNX]
    if not args.gui:
        command.append("--headless")
    command.extend(["--mcp-http", "--mcp-http-port", str(MCP_PORT),
                    str(args.rom), str(args.symbols)])
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    version_match = re.search(
        r"GAME_VERSION_STRING\s+\"([^\"]+)\"",
        (ROOT / "include" / "version.h").read_text(encoding="utf-8"),
    )
    if version_match is None:
        raise RuntimeError("GAME_VERSION_STRING missing")
    evidence = {
        "aps": "APS-053",
        "phase": "2R-2",
        "version": version_match.group(1),
        "rom": {"path": str(args.rom),
                "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest()},
        "method": {
            "scb_capture": "breakpoint at real _tgi_ioctl entry before SPRGO",
            "fixture": "GAME_PHASE_STAGE_INTRO, player x/y=250, enemy/object slots inactive",
            "framebuffer_pages": {"page0": "0xE018", "page1": "0xC038",
                                   "bytes": PAGE_SIZE},
            "dynamic_pixel_mask": "none required; dynamic objects are off-screen",
        },
        "stages": [],
    }
    try:
        for _ in range(30):
            try:
                visual.call("initialize", {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "aps053-static-readback",
                                   "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")
        request_id = wait_stable_title(
            visual, game_address, voice_active_address, 3
        )
        for stage in (1, 2, 3):
            request_id, result = verify_stage(
                visual, game_address, enemy_address, ioctl_address, sync_address,
                logic_address, sound_address, scratch_address, assets, stage,
                request_id, args.output.parent,
            )
            evidence["stages"].append(result)
            print("stage=%d scb_count=%d page0/page1=%s expected_sha256=%s" %
                  (stage, result["scb_count"],
                   "PASS" if result["passed"] else "FAIL",
                   result["expected_index_sha256"]))
        evidence["passed"] = all(stage["passed"] for stage in evidence["stages"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
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
