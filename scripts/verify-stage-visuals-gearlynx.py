#!/usr/bin/env python3
"""APS-050 contract f: capture and verify normal, enemy cast, and boss
visuals for all stages against the preview-authored sprite source of
truth (assets/previews/*.json), not the collision-only stages.json
sprite entries. Expected pixels are derived the same way main.c's
draw_sprite()/draw_sprite_run_scaled() render them: each preview grid
cell maps to a scale x scale block on screen, offset by the generator-
computed per-sprite anchor (scripts/generate-stage-data.py's
sprite_anchor()). All sprites draw at 1x scale in APS-050. ROM run/
definition byte identity is contract e's job (scripts/verify-sprite-rom-
bytes.py) and is not duplicated here.
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
import urllib.request
import zlib
from pathlib import Path


GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17769
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}
GAME_OFFSET_PLAYER = 2
GAME_ENEMY_SIZE = 12
GAME_MAX_ENEMIES = 8
GAME_OFFSET_BULLETS = 6
GAME_BULLET_SIZE = 5
GAME_MAX_BULLETS = 12
GAME_OFFSET_ENEMY_BULLETS = 66
GAME_ENEMY_BULLET_SIZE = 5
GAME_MAX_ENEMY_BULLETS = 16
GAME_OFFSET_POWER_ITEM = 146
GAME_OFFSET_BOSS = 150
GAME_OFFSET_GAME_OVER = 191
GAME_OFFSET_TITLE_VOICE_PENDING = 194
GAME_OFFSET_DYING = 197
GAME_OFFSET_ANIMATION_FRAME = 207
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PHASE = 210
GAME_OFFSET_PHASE_TIMER = 211
GAME_OFFSET_BOSS_ACTIVE = 154
GAME_PHASE_STAGE_INTRO = 0
GAME_PHASE_NORMAL = 1
GAME_PHASE_WARNING = 2
GAME_PHASE_BOSS = 3
CAST_RECTS = ((40, 24, 8, 8), (80, 47, 8, 8), (120, 70, 8, 8))
PLAYER_COLLISION_SIZE = (8, 6)
ENEMY_COLLISION_SIZE = (8, 8)
BOSS_TARGETS = (
    ("coral_bastion", (24, 16)),
    ("amber_carrier", (28, 14)),
    ("violet_geode", (24, 24)),
)
CASTS = (
    ((0, "SCOUT", "scout"), (1, "SAUCER", "saucer"),
     (2, "DROPPER", "dropper")),
    ((3, "FIGHTER", "fighter"), (4, "BOMBER", "bomber"),
     (5, "SUPPLY", "supply")),
    ((6, "CAVE_BAT", "cave_bat"), (7, "ROCK_WORM", "rock_worm"),
     (8, "MINING_DRONE", "mining_drone")),
)


def call(method, params=None, request_id=1):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": request_id, "method": method,
        "params": params or {},
    }).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:%d/mcp" % MCP_PORT,
        data=payload, headers=HEADERS,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def tool(name, arguments=None, request_id=1):
    result = call("tools/call", {
        "name": name, "arguments": arguments or {},
    }, request_id)
    if "error" in result:
        raise RuntimeError("%s failed: %s" % (name, result["error"]))
    content = result["result"]["content"][0]
    if content.get("type") == "image":
        return content
    return json.loads(content["text"])


def symbol_address(symbols_path, symbol):
    text = symbols_path.read_text(encoding="utf-8")
    match = re.search(
        r"^al\s+([0-9A-Fa-f]{6})\s+\." + re.escape(symbol) + r"$",
        text, re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("cannot locate %s in label file" % symbol)
    address = int(match.group(1), 16)
    if address > 0xFFFF:
        raise RuntimeError("symbol %s is outside CPU address space" % symbol)
    return address


def load_generator():
    generator_path = Path(__file__).resolve().with_name("generate-stage-data.py")
    spec = importlib.util.spec_from_file_location("stage_generator", generator_path)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    return generator


def generated_palettes(gen, input_path):
    document = gen.load_json(input_path)
    gen.validate(document)
    themes = {theme["id"]: theme for theme in document["themes"]}
    return [gen.palette_bytes(themes[stage["theme"]]["colors"])
            for stage in document["stages"]]


def frame_run_signature(rows):
    runs = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            color = row[x]
            if color == ".":
                x += 1
                continue
            x0 = x
            while x + 1 < len(row) and row[x + 1] == color:
                x += 1
            runs.append((y, x0, x, color))
            x += 1
    return tuple(runs)


def load_sprite_visuals(gen, input_path):
    """Build the contract f expected-pixel source of truth: each sprite's
    frame 0/1 role grids (preview verbatim + anim_delta overlay), its
    generator-computed anchor, and its boss draw scale -- exactly what
    main.c's draw_sprite() consumes at runtime."""
    document = json.loads(input_path.read_text(encoding="utf-8"))
    stage_sprites = {sprite["id"]: sprite for sprite in document["sprites"]}
    if set(stage_sprites) != set(gen.SPRITE_CONTRACTS):
        raise RuntimeError(
            "APS-049 sprite id set mismatch between stages.json and "
            "generate-stage-data.py SPRITE_CONTRACTS"
        )
    previews, _, _ = gen.load_previews()
    if set(previews) != set(gen.SPRITE_CONTRACTS):
        raise RuntimeError(
            "APS-049 sprite id set mismatch between preview JSON and "
            "SPRITE_CONTRACTS"
        )
    sprites = {}
    for sprite_id, (kind, collision_w, collision_h, scale) in gen.SPRITE_CONTRACTS.items():
        stage_sprite = stage_sprites[sprite_id]
        if (stage_sprite["width"], stage_sprite["height"]) != (collision_w, collision_h):
            raise RuntimeError(
                "%s collision size mismatch: stages.json=%dx%d contract=%dx%d" %
                (sprite_id, stage_sprite["width"], stage_sprite["height"],
                 collision_w, collision_h)
            )
        preview = previews[sprite_id]
        frame0 = preview["grid"]
        frame1 = gen.apply_anim_delta(
            frame0, preview["anim_delta"], set(preview["roles"]),
            "contract-f/%s/anim_delta" % sprite_id,
        )
        anchor = gen.sprite_anchor(frame0, collision_w, collision_h, scale)
        sprites[sprite_id] = {
            "kind": kind,
            "scale": scale,
            "anchor": anchor,
            "frame0": frame0,
            "frame1": frame1,
            "frames": (frame0, frame1),
        }
    return sprites, document


def validate_cast_and_boss_mapping(sprites, document):
    enemy_types = document["enemy_types"]
    if len(enemy_types) != 9:
        raise RuntimeError("enemy sprite mapping count mismatch: %d" %
                           len(enemy_types))
    for stage_index, cast in enumerate(CASTS):
        signatures = []
        for enemy_type, engine_type, sprite_id in cast:
            mapping = enemy_types[enemy_type]
            if (mapping["engine_type"] != engine_type or
                    mapping["sprite"] != sprite_id):
                raise RuntimeError(
                    "stage %d type %d sprite mapping mismatch: %r" %
                    (stage_index + 1, enemy_type, mapping)
                )
            signatures.append(tuple(frame_run_signature(frame)
                                    for frame in sprites[sprite_id]["frames"]))
        if len(set(signatures)) != 3:
            raise RuntimeError(
                "stage %d cast does not use three distinct run/color sets" %
                (stage_index + 1)
            )
    appearances = {item["id"]: item["sprite"]
                   for item in document["boss_appearances"]}
    for stage_index, (sprite_id, collision_size) in enumerate(BOSS_TARGETS):
        boss = document["bosses"][stage_index]
        mapped = appearances[boss["appearance"]]
        if mapped != sprite_id or (boss["width"], boss["height"]) != collision_size:
            raise RuntimeError(
                "stage %d boss visual/collision mapping mismatch: sprite=%s "
                "collision=%dx%d" %
                (stage_index + 1, mapped, boss["width"], boss["height"])
            )


def validate_game_enemy_layout():
    bullets_end = GAME_OFFSET_BULLETS + GAME_MAX_BULLETS * GAME_BULLET_SIZE
    enemy_bullets_end = (GAME_OFFSET_ENEMY_BULLETS +
                         GAME_MAX_ENEMY_BULLETS * GAME_ENEMY_BULLET_SIZE)
    if (bullets_end != GAME_OFFSET_ENEMY_BULLETS or
            enemy_bullets_end != GAME_OFFSET_POWER_ITEM or
            GAME_OFFSET_POWER_ITEM + 4 + 4 != GAME_OFFSET_BOSS_ACTIVE):
        raise RuntimeError("GameEnemy/GameState layout invariant mismatch")
    if any(rect[2:] != ENEMY_COLLISION_SIZE for rect in CAST_RECTS):
        raise RuntimeError("cast enemy collision size is not 8x8")


def sprite_origin(sprites, sprite_id, rect_xy):
    dx, dy = sprites[sprite_id]["anchor"]
    return (rect_xy[0] + dx, rect_xy[1] + dy)


def sprite_size(sprites, sprite_id):
    scale = sprites[sprite_id]["scale"]
    return (16 * scale, 16 * scale)


def sprite_render_clip_counts(sprites, sprite_id, rect_xy):
    x, y = sprite_origin(sprites, sprite_id, rect_xy)
    width, height = sprite_size(sprites, sprite_id)
    clip_x = max(0, -x) + max(0, x + width - 160)
    clip_y = max(0, -y) + max(0, y + height - 102)
    return clip_x, clip_y


def assert_sprite_not_clipped(sprites, sprite_id, rect_xy, label):
    clip_x, clip_y = sprite_render_clip_counts(sprites, sprite_id, rect_xy)
    if clip_x != 0 or clip_y != 0:
        raise RuntimeError(
            "%s sprite rendered clipped: sprite=%s origin=%r clip_x=%d clip_y=%d" %
            (label, sprite_id, sprite_origin(sprites, sprite_id, rect_xy),
             clip_x, clip_y)
        )


def read_bytes(address, size, request_id):
    result = tool("read_memory", {
        "area": 0, "offset": "%04X" % address, "size": size,
    }, request_id)
    return bytes.fromhex(result["data"])


def write_bytes(address, values, request_id):
    tool("write_memory", {
        "area": 0, "offset": "%04X" % address,
        "bytes": bytes(values).hex(" "),
    }, request_id)


def read_palette(request_id):
    registers = tool("get_mikey_registers", request_id=request_id)["registers"]
    values = {int(address, 16): int(value, 16)
              for _, address, value in registers}
    return bytes(values[address] for address in range(0xFDA0, 0xFDC0))


def capture(output_path, request_id):
    shot = tool("get_screenshot", request_id=request_id)
    data = base64.b64decode(shot["data"])
    output_path.write_bytes(data)
    return data


def verify_gui_matches_headless(output_path, data):
    headless_path = output_path.parent.parent / output_path.name
    if not headless_path.is_file():
        raise RuntimeError("headless reference missing for %s" % output_path.name)
    expected = headless_path.read_bytes()
    if data != expected:
        raise RuntimeError(
            "GUI/headless PNG mismatch %s: gui=%s headless=%s" %
            (output_path.name, hashlib.sha256(data).hexdigest(),
             hashlib.sha256(expected).hexdigest())
        )


def decode_png_rgba(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Gearlynx screenshot is not PNG")
    offset = 8
    compressed = bytearray()
    width = height = None
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk = data[offset + 8:offset + 8 + length]
        offset += length + 12
        if chunk_type == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
            if (depth, color_type, interlace) != (8, 6, 0):
                raise RuntimeError(
                    "unsupported screenshot PNG format depth=%d color=%d "
                    "interlace=%d" % (depth, color_type, interlace)
                )
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break
    if (width, height) != (160, 102):
        raise RuntimeError("screenshot dimensions mismatch: %r" %
                           ((width, height),))
    raw = zlib.decompress(bytes(compressed))
    stride = width * 4
    previous = bytearray(stride)
    rows = []
    position = 0
    for _ in range(height):
        filter_type = raw[position]
        position += 1
        row = bytearray(raw[position:position + stride])
        position += stride
        for index in range(stride):
            left = row[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                estimate = left + above - upper_left
                left_distance = abs(estimate - left)
                above_distance = abs(estimate - above)
                corner_distance = abs(estimate - upper_left)
                if left_distance <= above_distance and left_distance <= corner_distance:
                    predictor = left
                elif above_distance <= corner_distance:
                    predictor = above
                else:
                    predictor = upper_left
            elif filter_type == 0:
                predictor = 0
            else:
                raise RuntimeError("unsupported PNG filter %d" % filter_type)
            row[index] = (row[index] + predictor) & 0xFF
        rows.append(row)
        previous = row
    return rows


def png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload +
            struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def encode_png_rgba(rows, width, height):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    return (b"\x89PNG\r\n\x1a\n" +
            png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height,
                                             8, 6, 0, 0, 0)) +
            png_chunk(b"IDAT", zlib.compress(raw, 9)) +
            png_chunk(b"IEND", b""))


def write_sprite_capture(png_data, origin, size, output_path, gui):
    """Crop the sprite's native-resolution capture. If the anchor-computed
    origin pushes part of the sprite past the 160x102 framebuffer edge
    (matching draw_clipped_hline()'s real clamp/drop behaviour), the
    off-screen columns/rows are padded black in the saved PNG and the
    clipped pixel count is returned alongside the hash so callers can
    surface it as evidence instead of silently losing the fact that a
    boundary clip happened."""
    source = decode_png_rgba(png_data)
    x, y = origin
    width, height = size
    clipped_columns = max(0, -x) + max(0, x + width - 160)
    clipped_rows = max(0, -y) + max(0, y + height - 102)
    cropped = []
    for row_index in range(height):
        source_y = y + row_index
        row = bytearray(width * 4)
        if 0 <= source_y < 102:
            source_row = source[source_y]
            for col_index in range(width):
                source_x = x + col_index
                if 0 <= source_x < 160:
                    row[col_index * 4:col_index * 4 + 4] = \
                        source_row[source_x * 4:source_x * 4 + 4]
        cropped.append(row)
    data = encode_png_rgba(cropped, width, height)
    output_path.write_bytes(data)
    if gui:
        verify_gui_matches_headless(output_path, data)
    return hashlib.sha256(data).hexdigest(), clipped_columns, clipped_rows


def palette_rgb(palette, index):
    green = palette[index] & 0x0F
    blue_red = palette[16 + index]
    return ((blue_red & 0x0F) * 17, green * 17,
            ((blue_red >> 4) & 0x0F) * 17)


def sprite_frame_mismatch(rows, sprite_id, origin, grid, scale, palette,
                          candidate_frame):
    """Pixels that fall outside the 160x102 framebuffer are skipped, not
    failed: draw_clipped_hline() in main.c clamps x to [0, GAME_SCREEN_
    WIDTH) per hline and drops the row entirely if y is out of range,
    exactly like a real Lynx would -- there is no pixel to compare there,
    on hardware or in the emulator capture."""
    checked = 0
    clipped = 0
    for gy, row in enumerate(grid):
        for gx, role in enumerate(row):
            if role == ".":
                continue
            expected = palette_rgb(palette, int(role, 16))
            for ry in range(scale):
                for rx in range(scale):
                    px = origin[0] + gx * scale + rx
                    py = origin[1] + gy * scale + ry
                    if px < 0 or py < 0 or px >= 160 or py >= 102:
                        clipped += 1
                        continue
                    pixel_offset = px * 4
                    actual = tuple(rows[py][pixel_offset:pixel_offset + 3])
                    if actual != expected:
                        return ("frame=%d sprite=%s origin=%r pixel=(%d,%d) "
                                "actual=%r expected=%r role=%s" %
                                (candidate_frame, sprite_id, origin, px, py,
                                 actual, expected, role))
                    checked += 1
    if checked == 0:
        return "frame=%d sprite=%s has no rendered pixels (clipped=%d)" % (
            candidate_frame, sprite_id, clipped,
        )
    return None


def verify_sprite_pixels(png_data, sprite_id, rect_xy, sprites, palette):
    rows = decode_png_rgba(png_data)
    origin = sprite_origin(sprites, sprite_id, rect_xy)
    scale = sprites[sprite_id]["scale"]
    mismatches = []
    for candidate_frame, grid in enumerate((sprites[sprite_id]["frame0"],
                                            sprites[sprite_id]["frame1"])):
        mismatch = sprite_frame_mismatch(
            rows, sprite_id, origin, grid, scale, palette, candidate_frame,
        )
        if mismatch is None:
            return candidate_frame
        mismatches.append(mismatch)
    raise RuntimeError("sprite framebuffer mismatch: %s" %
                       "; ".join(mismatches))


def locate_sprite_pixels(png_data, sprite_id, expected_rect_xy, sprites,
                         palette, radius):
    """Search near the anchor-computed origin. Candidates are not rejected
    for extending past the framebuffer edge -- sprite_frame_mismatch skips
    clipped pixels the same way draw_clipped_hline() drops them on real
    hardware -- but the origin itself must keep at least one grid cell of
    the sprite's *top-left* on screen, or every candidate would vacuously
    "match" with zero checked pixels."""
    rows = decode_png_rgba(png_data)
    expected_origin = sprite_origin(sprites, sprite_id, expected_rect_xy)
    scale = sprites[sprite_id]["scale"]
    for distance in range(radius + 1):
        for y_delta in range(-distance, distance + 1):
            for x_delta in range(-distance, distance + 1):
                if max(abs(x_delta), abs(y_delta)) != distance:
                    continue
                origin = (expected_origin[0] + x_delta,
                          expected_origin[1] + y_delta)
                if origin[0] >= 160 or origin[1] >= 102:
                    continue
                for candidate_frame, grid in enumerate(
                        (sprites[sprite_id]["frame0"],
                         sprites[sprite_id]["frame1"])):
                    mismatch = sprite_frame_mismatch(
                        rows, sprite_id, origin, grid, scale, palette,
                        candidate_frame,
                    )
                    if mismatch is None:
                        return candidate_frame, origin
    raise RuntimeError(
        "cannot locate %s within %d pixels of expected anchor origin %r "
        "(collision rect %r)" %
        (sprite_id, radius, expected_origin, expected_rect_xy)
    )


def verify_cast_pixels(png_data, stage, animation_frame, sprites, palette):
    rows = decode_png_rgba(png_data)
    mismatches = []
    # Gearlynx exposes the displayed front buffer, while GameState already
    # belongs to the following back-buffer draw. Accept either authored frame,
    # but require all three sprites to match one complete frame exactly.
    for candidate_frame in range(2):
        mismatch = None
        for slot, cast in enumerate(CASTS[stage - 1]):
            enemy_type, _, sprite_id = cast
            rect = CAST_RECTS[slot]
            origin = sprite_origin(sprites, sprite_id, rect[:2])
            scale = sprites[sprite_id]["scale"]
            grid = (sprites[sprite_id]["frame0"] if candidate_frame == 0
                   else sprites[sprite_id]["frame1"])
            mismatch = sprite_frame_mismatch(
                rows, sprite_id, origin, grid, scale, palette, candidate_frame,
            )
            if mismatch is not None:
                break
        if mismatch is None:
            return candidate_frame
        mismatches.append(mismatch)
    raise RuntimeError(
        "stage %d cast framebuffer mismatch memory_frame=%d: %s" %
        (stage, animation_frame, "; ".join(mismatches))
    )


def set_transition_state(game_address, stage, phase, timer, request_id):
    write_bytes(game_address + GAME_OFFSET_GAME_OVER, [0], request_id)
    write_bytes(game_address + GAME_OFFSET_TITLE_VOICE_PENDING, [0, 0, 0, 0],
                request_id + 1)
    write_bytes(game_address + GAME_OFFSET_STAGE,
                [stage, phase, timer & 0xFF, timer >> 8], request_id + 2)


def cast_enemy_record(enemy_type, rect):
    x, y, width, height = rect
    return [x, y, width, height, 1, enemy_type, 0, y,
            0, 0, 1, 0]


def assert_no_transient_gameplay(game_address, request_id, stage):
    state = read_bytes(game_address + GAME_OFFSET_BULLETS,
                       GAME_OFFSET_GAME_OVER - GAME_OFFSET_BULLETS,
                       request_id)
    for slot in range(GAME_MAX_BULLETS):
        active = state[slot * GAME_BULLET_SIZE + 4]
        if active != 0:
            raise RuntimeError(
                "stage %d cast player bullet %d active=%d" %
                (stage, slot, active)
            )
    enemy_base = GAME_OFFSET_ENEMY_BULLETS - GAME_OFFSET_BULLETS
    for slot in range(GAME_MAX_ENEMY_BULLETS):
        active = state[enemy_base + slot * GAME_ENEMY_BULLET_SIZE + 2]
        if active != 0:
            raise RuntimeError(
                "stage %d cast enemy bullet %d active=%d" %
                (stage, slot, active)
            )
    power_active = state[GAME_OFFSET_POWER_ITEM - GAME_OFFSET_BULLETS + 2]
    if power_active != 0:
        raise RuntimeError("stage %d cast power item active=%d" %
                           (stage, power_active))
    return request_id + 1


def rectangles_overlap(left, right):
    return (left[0] < right[0] + right[2] and
            right[0] < left[0] + left[2] and
            left[1] < right[1] + right[3] and
            right[1] < left[1] + left[3])


def read_visible_player(game_address, request_id, stage):
    player = tuple(read_bytes(game_address + GAME_OFFSET_PLAYER, 4,
                              request_id))
    request_id += 1
    visibility = read_bytes(game_address + GAME_OFFSET_DYING, 3, request_id)
    request_id += 1
    if (player[2:] != PLAYER_COLLISION_SIZE or
            player[0] + PLAYER_COLLISION_SIZE[0] > 160 or
            player[1] < 10 or player[1] + PLAYER_COLLISION_SIZE[1] > 102 or
            visibility[0] != 0 or visibility[2] != 0):
        raise RuntimeError(
            "stage %d player collision/visibility mismatch: rect=%r "
            "dying=%d invincibility=%d" %
            (stage, player, visibility[0], visibility[2])
        )
    return request_id, player


def read_active_boss(game_address, stage, request_id):
    record = read_bytes(game_address + GAME_OFFSET_BOSS, 5, request_id)
    request_id += 1
    rect = tuple(record[:4])
    expected_size = BOSS_TARGETS[stage - 1][1]
    if record[4] != 1 or rect[2:] != expected_size:
        raise RuntimeError(
            "stage %d boss collision readback mismatch: active=%d rect=%r "
            "expected_size=%r" %
            (stage, record[4], rect, expected_size)
        )
    return request_id, rect


def verify_cast_readback(game_address, enemy_address, stage, request_id):
    enemies = read_bytes(enemy_address,
                         GAME_MAX_ENEMIES * GAME_ENEMY_SIZE, request_id)
    request_id += 1
    actual = []
    for slot, expected in enumerate(CASTS[stage - 1]):
        record = enemies[slot * GAME_ENEMY_SIZE:(slot + 1) * GAME_ENEMY_SIZE]
        rect = tuple(record[:4])
        if (record[4] != 1 or record[5] != expected[0] or
                rect != CAST_RECTS[slot]):
            raise RuntimeError(
                "stage %d type %d rect readback failed: active=%d type=%d "
                "rect=%r expected=%r" %
                (stage, expected[0], record[4], record[5], rect,
                 CAST_RECTS[slot])
            )
        actual.append((record[5], rect))
    if enemies[3 * GAME_ENEMY_SIZE + 4] != 0:
        raise RuntimeError("stage %d cast enemy slot 3 remained active" % stage)

    request_id, player = read_visible_player(game_address, request_id, stage)
    if any(rectangles_overlap(player, rect) for _, rect in actual):
        raise RuntimeError("stage %d cast overlaps player rect=%r cast=%r" %
                           (stage, player, actual))
    request_id = assert_no_transient_gameplay(game_address, request_id, stage)
    return request_id, actual


def inject_and_synchronize_cast(game_address, enemy_address, logic_address, sound_address,
                                stage, request_id):
    request_id = assert_no_transient_gameplay(game_address, request_id, stage)
    sound_hex = "%04X" % sound_address
    records = []
    for slot, cast in enumerate(CASTS[stage - 1]):
        records.extend(cast_enemy_record(cast[0], CAST_RECTS[slot]))
    records.extend([0] * GAME_ENEMY_SIZE)
    logic_hex = "%04X" % logic_address
    # Inject immediately after each frame's logic and before draw_game. Two
    # identical draws cover the Lynx driver's back/front buffer handoff while
    # keeping memory readback and rendered rectangles identical.
    for _ in range(2):
        tool("set_breakpoint", {"address": sound_hex}, request_id)
        request_id += 1
        request_id = continue_to_breakpoint(request_id, "cast pre-draw sound")
        write_bytes(enemy_address, records, request_id)
        request_id += 1
        tool("remove_breakpoint", {"address": sound_hex}, request_id)
        request_id += 1
        tool("set_breakpoint", {"address": logic_hex}, request_id)
        request_id += 1
        request_id = continue_to_breakpoint(request_id, "cast completed draw")
        tool("remove_breakpoint", {"address": logic_hex}, request_id)
        request_id += 1
    state = read_bytes(game_address + GAME_OFFSET_STAGE, 2, request_id)
    request_id += 1
    if state != bytes([stage, GAME_PHASE_NORMAL]):
        raise RuntimeError("stage %d cast left NORMAL: state=%r" %
                           (stage, state))
    return verify_cast_readback(game_address, enemy_address, stage, request_id)


def wait_for_breakpoint(request_id, description):
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status["paused"]:
            if not status["at_breakpoint"]:
                raise RuntimeError("paused before %s breakpoint" % description)
            return request_id
        time.sleep(0.005)
    raise RuntimeError("timed out waiting for %s breakpoint" % description)


def continue_to_breakpoint(request_id, description):
    tool("debug_continue", request_id=request_id)
    return wait_for_breakpoint(request_id + 1, description)


def enter_stage_one_with_real_input(game_address, logic_address,
                                    sound_address, request_id):
    tool("controller_macro", {"commands": [{"release": "a"}]}, request_id)
    request_id += 1
    tool("controller_macro", {"commands": [{"press": "a"}]}, request_id)
    request_id += 1
    tool("debug_continue", request_id=request_id)
    request_id += 1
    deadline = time.monotonic() + 15.0
    released = False
    latest = None
    while time.monotonic() < deadline:
        latest = read_bytes(game_address + GAME_OFFSET_STAGE, 2, request_id)
        request_id += 1
        if not released:
            pending = read_bytes(
                game_address + GAME_OFFSET_TITLE_VOICE_PENDING, 1, request_id,
            )[0]
            request_id += 1
            if pending != 0:
                tool("controller_macro", {
                    "commands": [{"release": "a"}],
                }, request_id)
                request_id += 1
                released = True
        if latest == bytes([1, GAME_PHASE_NORMAL]):
            break
        time.sleep(0.005)
    else:
        raise RuntimeError("real TITLE input did not reach Stage 1 NORMAL: %r" %
                           (latest,))
    tool("debug_pause", request_id=request_id)
    request_id += 1
    request_id = synchronize_completed_draw(
        game_address, logic_address, sound_address, 1,
        GAME_PHASE_NORMAL, False, request_id,
    )
    return request_id


def synchronize_completed_draw(game_address, logic_address, sound_address,
                               stage, phase, require_boss, request_id):
    logic_hex = "%04X" % logic_address
    sound_hex = "%04X" % sound_address
    # Synchronize at the post-logic/pre-draw sound call, then wait for the next
    # logic entry after draw_game and tgi_busy have completed the front-buffer
    # handoff. Repeat once so GUI and headless capture the same fully rendered
    # target state instead of a valid GameState with a stale front buffer.
    for _ in range(2):
        tool("set_breakpoint", {"address": sound_hex}, request_id)
        request_id += 1
        request_id = continue_to_breakpoint(request_id,
                                            "post-transition pre-draw sound")
        tool("remove_breakpoint", {"address": sound_hex}, request_id)
        request_id += 1
        tool("set_breakpoint", {"address": logic_hex}, request_id)
        request_id += 1
        request_id = continue_to_breakpoint(request_id,
                                            "post-transition completed draw")
        tool("remove_breakpoint", {"address": logic_hex}, request_id)
        request_id += 1
    state = read_bytes(game_address + GAME_OFFSET_STAGE, 4, request_id)
    request_id += 1
    boss_active = None
    if require_boss:
        boss_active = read_bytes(game_address + GAME_OFFSET_BOSS_ACTIVE,
                                 1, request_id)
        request_id += 1
    if (state[:2] != bytes([stage, phase]) or
            (require_boss and boss_active != b"\x01")):
        raise RuntimeError(
            "stage %d left target before capture: state=%r active=%r" %
            (stage, state, boss_active)
        )
    return request_id


def transition_and_synchronize(game_address, logic_address, sound_address, stage,
                               source_phase, source_timer, target_phase,
                               require_boss, request_id):
    set_transition_state(game_address, stage, source_phase, source_timer,
                         request_id)
    request_id += 3
    phase_hex = "%04X" % (game_address + GAME_OFFSET_PHASE)
    tool("set_breakpoint", {
        "address": phase_hex, "execute": False, "write": True,
    }, request_id)
    request_id += 1
    request_id = continue_to_breakpoint(request_id, "phase write")
    tool("remove_breakpoint", {"address": phase_hex}, request_id)
    request_id += 1
    state = read_bytes(game_address + GAME_OFFSET_STAGE, 4, request_id)
    request_id += 1
    if state[:2] != bytes([stage, target_phase]):
        raise RuntimeError(
            "stage %d did not enter phase %d: %r" %
            (stage, target_phase, state)
        )
    return synchronize_completed_draw(
        game_address, logic_address, sound_address, stage, target_phase, require_boss,
        request_id,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path, default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--map", type=Path, default=Path("build/asteroid-patrol.map"))
    parser.add_argument("--input", type=Path, default=Path("assets/stages/stages.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/APS-050"))
    parser.add_argument("--gui", action="store_true",
                        help="launch the Gearlynx GUI while running the same checks")
    args = parser.parse_args()

    if not Path(GEARLYNX).is_file():
        print("Gearlynx executable not found", file=sys.stderr)
        return 1
    game_address = symbol_address(args.symbols, "_game")
    enemy_address = symbol_address(args.symbols, "_game_enemies")
    logic_address = symbol_address(args.symbols, "_game_update_logic")
    sound_address = symbol_address(args.symbols, "_game_sound_tick")
    validate_game_enemy_layout()
    gen = load_generator()
    sprites, document = load_sprite_visuals(gen, args.input)
    validate_cast_and_boss_mapping(sprites, document)
    palettes = generated_palettes(gen, args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [GEARLYNX]
    if not args.gui:
        command.append("--headless")
    command.extend([
        "--mcp-http", "--mcp-http-port", str(MCP_PORT),
        str(args.rom), str(args.symbols),
    ])
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        for _ in range(30):
            try:
                call("initialize", {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "aps050-visuals", "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")

        tool("debug_continue", request_id=2)
        request_id = 3
        deadline = time.monotonic() + 10.0
        stable_title_polls = 0
        while time.monotonic() < deadline:
            initial = read_bytes(game_address + GAME_OFFSET_STAGE, 2,
                                 request_id)
            request_id += 1
            if initial == bytes([1, 6]):
                stable_title_polls += 1
                if stable_title_polls == 2:
                    break
            else:
                stable_title_polls = 0
            time.sleep(0.005)
        else:
            raise RuntimeError("ROM did not reach stable title state")
        tool("debug_pause", request_id=request_id)
        request_id += 1
        initial = read_bytes(game_address + GAME_OFFSET_STAGE, 2, request_id)
        request_id += 1
        if initial != bytes([1, 6]):
            raise RuntimeError("computed GameState address failed title check")

        request_id = enter_stage_one_with_real_input(
            game_address, logic_address, sound_address, request_id,
        )
        actual_palette = read_palette(request_id)
        request_id += 1
        if actual_palette != bytes(palettes[0]):
            raise RuntimeError("actual-play Stage 1 palette mismatch")
        request_id, actual_player_rect = read_visible_player(
            game_address, request_id, 1,
        )
        actual_enemies = read_bytes(
            enemy_address, GAME_MAX_ENEMIES * GAME_ENEMY_SIZE, request_id,
        )
        request_id += 1
        actual_enemy = actual_enemies[:GAME_ENEMY_SIZE]
        if (actual_enemy[4] != 1 or actual_enemy[5] != 0 or
                actual_enemy[0] >= 160):
            raise RuntimeError("actual-play Stage 1 scout readback mismatch: %r" %
                               (actual_enemy,))
        actual_path = args.output_dir / "actual-play-stage1.png"
        actual_png = capture(actual_path, request_id)
        request_id += 1
        if args.gui:
            verify_gui_matches_headless(actual_path, actual_png)
        actual_player_frame = verify_sprite_pixels(
            actual_png, "player", actual_player_rect[:2], sprites,
            actual_palette,
        )
        actual_scout_frame, actual_scout_origin = locate_sprite_pixels(
            actual_png, "scout", tuple(actual_enemy[:2]), sprites,
            actual_palette, 4,
        )
        evidence = {
            "aps": "APS-050",
            "contract": "f",
            "mode": "gui" if args.gui else "headless",
            "expected_pixel_source": "assets/previews/*.json (frame 0 "
                "verbatim + anim_delta overlay for frame 1), offset by "
                "scripts/generate-stage-data.py sprite_anchor() and drawn "
                "at each sprite's 1x scale -- rom byte identity is "
                "contract e (scripts/verify-sprite-rom-bytes.py).",
            "sprite_geometry": {
                sprite_id: {
                    "scale": entry["scale"],
                    "anchor": list(entry["anchor"]),
                    "visual_size": list(sprite_size(sprites, sprite_id)),
                }
                for sprite_id, entry in sprites.items()
            },
            "actual_play": {
                "path": actual_path.name,
                "entry": "TITLE release/press A to Stage 1 NORMAL",
                "stage": 1,
                "phase": GAME_PHASE_NORMAL,
                "player_rect": list(actual_player_rect),
                "player_frame": actual_player_frame,
                "enemy_slot": 0,
                "enemy_type": int(actual_enemy[5]),
                "enemy_sprite": "scout",
                "enemy_rect": list(actual_enemy[:4]),
                "enemy_frame": actual_scout_frame,
                "enemy_rendered_origin": list(actual_scout_origin),
                "png_sha256": hashlib.sha256(actual_png).hexdigest(),
            },
            "injected_paths": [],
        }

        target_hashes = {}
        for stage in range(1, 4):
            request_id = transition_and_synchronize(
                game_address, logic_address, sound_address, stage,
                GAME_PHASE_STAGE_INTRO,
                89, GAME_PHASE_NORMAL, False, request_id,
            )
            palette = read_palette(request_id)
            request_id += 1
            if palette != bytes(palettes[stage - 1]):
                raise RuntimeError(
                    "stage %d hardware palette mismatch: actual=%s expected=%s" %
                    (stage, palette.hex(), bytes(palettes[stage - 1]).hex())
                )
            normal_path = args.output_dir / ("stage%d-normal.png" % stage)
            request_id, player_rect = read_visible_player(
                game_address, request_id, stage,
            )
            normal_png = capture(normal_path, request_id)
            request_id += 1
            if args.gui:
                verify_gui_matches_headless(normal_path, normal_png)
            player_frame = verify_sprite_pixels(
                normal_png, "player", player_rect[:2], sprites, palette,
            )
            if stage == 1:
                player_path = args.output_dir / "player.png"
                sha256, clip_x, clip_y = write_sprite_capture(
                    normal_png, sprite_origin(sprites, "player", player_rect[:2]),
                    sprite_size(sprites, "player"), player_path, args.gui,
                )
                target_hashes["player"] = {"sha256": sha256,
                                           "clipped_columns": clip_x,
                                           "clipped_rows": clip_y}

            request_id, cast_readback = inject_and_synchronize_cast(
                game_address, enemy_address, logic_address, sound_address, stage, request_id,
            )
            cast_palette = read_palette(request_id)
            request_id += 1
            if cast_palette != bytes(palettes[stage - 1]):
                raise RuntimeError(
                    "stage %d cast palette mismatch: actual=%s expected=%s" %
                    (stage, cast_palette.hex(),
                     bytes(palettes[stage - 1]).hex())
                )
            cast_path = args.output_dir / ("stage%d-cast.png" % stage)
            animation_frame = read_bytes(
                game_address + GAME_OFFSET_ANIMATION_FRAME, 1, request_id,
            )[0]
            request_id += 1
            cast_png = capture(cast_path, request_id)
            request_id += 1
            rendered_frame = verify_cast_pixels(
                cast_png, stage, animation_frame, sprites, cast_palette,
            )
            if args.gui:
                verify_gui_matches_headless(cast_path, cast_png)
            for slot, (_, _, sprite_id) in enumerate(CASTS[stage - 1]):
                sprite_path = args.output_dir / (sprite_id.replace("_", "-") +
                                                 ".png")
                sha256, clip_x, clip_y = write_sprite_capture(
                    cast_png, sprite_origin(sprites, sprite_id, CAST_RECTS[slot][:2]),
                    sprite_size(sprites, sprite_id), sprite_path, args.gui,
                )
                target_hashes[sprite_id] = {"sha256": sha256,
                                            "clipped_columns": clip_x,
                                            "clipped_rows": clip_y}

            request_id = transition_and_synchronize(
                game_address, logic_address, sound_address, stage,
                GAME_PHASE_WARNING,
                119, GAME_PHASE_BOSS, True, request_id,
            )
            boss_path = args.output_dir / ("stage%d-boss.png" % stage)
            request_id, boss_rect = read_active_boss(
                game_address, stage, request_id,
            )
            boss_png = capture(boss_path, request_id)
            request_id += 1
            if args.gui:
                verify_gui_matches_headless(boss_path, boss_png)
            boss_id = BOSS_TARGETS[stage - 1][0]
            boss_frame, boss_origin = locate_sprite_pixels(
                boss_png, boss_id, boss_rect[:2], sprites, palette, 4,
            )
            boss_target_path = args.output_dir / (
                boss_id.replace("_", "-") + ".png"
            )
            sha256, clip_x, clip_y = write_sprite_capture(
                boss_png, boss_origin, sprite_size(sprites, boss_id),
                boss_target_path, args.gui,
            )
            assert_sprite_not_clipped(
                sprites, boss_id, boss_rect[:2],
                "stage %d boss at stop_x=%d" % (stage, boss_rect[0]),
            )
            target_hashes[boss_id] = {"sha256": sha256,
                                      "clipped_columns": clip_x,
                                      "clipped_rows": clip_y}
            if clip_x != 0 or clip_y != 0:
                raise RuntimeError(
                    "stage %d boss stop_x=%d produced clip columns=%d rows=%d" %
                    (stage, boss_rect[0], clip_x, clip_y)
                )
            print("stage %d NORMAL/CAST/BOSS palette OK player_frame=%d "
                  "cast=%r cast_frame=%d boss_frame=%d boss_origin=%r "
                  "boss_clipped_columns=%d boss_clipped_rows=%d" %
                  (stage, player_frame, cast_readback, rendered_frame,
                   boss_frame, boss_origin, clip_x, clip_y))
            evidence["injected_paths"].append({
                "stage": stage,
                "normal": {
                    "path": normal_path.name,
                    "player_rect": list(player_rect),
                    "player_frame": player_frame,
                    "png_sha256": hashlib.sha256(normal_png).hexdigest(),
                },
                "cast": {
                    "path": cast_path.name,
                    "readback": [[enemy_type, list(rect)]
                                 for enemy_type, rect in cast_readback],
                    "animation_frame": rendered_frame,
                    "png_sha256": hashlib.sha256(cast_png).hexdigest(),
                },
                "boss": {
                    "path": boss_path.name,
                    "appearance": boss_id,
                    "rect": list(boss_rect),
                    "animation_frame": boss_frame,
                    "origin": list(boss_origin),
                    "png_sha256": hashlib.sha256(boss_png).hexdigest(),
                },
            })
        if set(target_hashes) != set(sprites):
            raise RuntimeError("not all thirteen sprite captures were written")
        for sprite_id in sprites:
            entry = target_hashes[sprite_id]
            print("capture %s sha256=%s clipped_columns=%d clipped_rows=%d" %
                  (sprite_id, entry["sha256"], entry["clipped_columns"],
                   entry["clipped_rows"]))
        evidence["individual_sprite_sha256"] = target_hashes
        metadata_name = ("runtime-sprite-gearlynx-gui.json" if args.gui else
                         "runtime-sprite-gearlynx.json")
        (args.output_dir / metadata_name).write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0
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
