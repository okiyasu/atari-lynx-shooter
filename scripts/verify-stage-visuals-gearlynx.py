#!/usr/bin/env python3
"""Capture and verify normal, enemy cast, and boss visuals for all stages."""

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
GAME_OFFSET_IN_MAIN_BSS = 12
GAME_OFFSET_PLAYER = 0
GAME_OFFSET_ENEMIES = 4
GAME_ENEMY_SIZE = 14
GAME_MAX_ENEMIES = 4
GAME_OFFSET_BULLETS = 60
GAME_BULLET_SIZE = 5
GAME_MAX_BULLETS = 12
GAME_OFFSET_ENEMY_BULLETS = 120
GAME_ENEMY_BULLET_SIZE = 7
GAME_MAX_ENEMY_BULLETS = 16
GAME_OFFSET_POWER_ITEM = 232
GAME_OFFSET_GAME_OVER = 287
GAME_OFFSET_TITLE_VOICE_PENDING = 290
GAME_OFFSET_DYING = 293
GAME_OFFSET_ANIMATION_FRAME = 304
GAME_OFFSET_STAGE = 305
GAME_OFFSET_PHASE = 306
GAME_OFFSET_PHASE_TIMER = 307
GAME_OFFSET_BOSS_ACTIVE = 242
GAME_PHASE_STAGE_INTRO = 0
GAME_PHASE_NORMAL = 1
GAME_PHASE_WARNING = 2
GAME_PHASE_BOSS = 3
CAST_RECTS = ((40, 24, 8, 8), (80, 47, 8, 8), (120, 70, 8, 8))
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


def main_bss_game_address(map_path):
    text = map_path.read_text(encoding="utf-8")
    segment = re.search(r"^BSS\s+([0-9A-F]{6})\s", text, re.MULTILINE)
    module = re.search(
        r"^main\.o:\n(?:.*\n)*?\s+BSS\s+Offs=([0-9A-F]{6})\s+",
        text, re.MULTILINE,
    )
    if segment is None or module is None:
        raise RuntimeError("cannot locate main.o BSS in linker map")
    return (int(segment.group(1), 16) + int(module.group(1), 16) +
            GAME_OFFSET_IN_MAIN_BSS)


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


def generated_palettes(input_path):
    generator_path = Path(__file__).resolve().with_name("generate-stage-data.py")
    spec = importlib.util.spec_from_file_location("stage_generator", generator_path)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    document = generator.load_json(input_path)
    generator.validate(document)
    themes = {theme["id"]: theme for theme in document["themes"]}
    return [generator.palette_bytes(themes[stage["theme"]]["colors"])
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


def validate_cast_sprite_data(input_path):
    document = json.loads(input_path.read_text(encoding="utf-8"))
    sprites = {sprite["id"]: sprite for sprite in document["sprites"]}
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
            sprite = sprites[sprite_id]
            if sprite["width"] != 8 or sprite["height"] != 8:
                raise RuntimeError(
                    "stage %d type %d sprite rect mismatch: %dx%d" %
                    (stage_index + 1, enemy_type,
                     sprite["width"], sprite["height"])
                )
            signatures.append(tuple(frame_run_signature(frame)
                                    for frame in sprite["frames"]))
        if len(set(signatures)) != 3:
            raise RuntimeError(
                "stage %d cast does not use three distinct run/color sets" %
                (stage_index + 1)
            )
    return sprites


def validate_game_enemy_layout():
    # include/game.h uses only one-byte fields through GamePowerItem. These
    # equations independently meet the existing boss.active map offset and
    # prevent a guessed GameEnemy stride from reaching emulator memory.
    enemies_end = GAME_OFFSET_ENEMIES + GAME_MAX_ENEMIES * GAME_ENEMY_SIZE
    bullets_end = GAME_OFFSET_BULLETS + GAME_MAX_BULLETS * GAME_BULLET_SIZE
    enemy_bullets_end = (GAME_OFFSET_ENEMY_BULLETS +
                         GAME_MAX_ENEMY_BULLETS * GAME_ENEMY_BULLET_SIZE)
    if (enemies_end != GAME_OFFSET_BULLETS or
            bullets_end != GAME_OFFSET_ENEMY_BULLETS or
            enemy_bullets_end != GAME_OFFSET_POWER_ITEM or
            GAME_OFFSET_POWER_ITEM + 6 + 4 != GAME_OFFSET_BOSS_ACTIVE):
        raise RuntimeError("GameEnemy/GameState layout invariant mismatch")


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


def palette_rgb(palette, index):
    green = palette[index] & 0x0F
    blue_red = palette[16 + index]
    return ((blue_red & 0x0F) * 17, green * 17,
            ((blue_red >> 4) & 0x0F) * 17)


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
            grid = sprites[sprite_id]["frames"][candidate_frame]
            checked = 0
            for y, row in enumerate(grid):
                for x, role in enumerate(row):
                    if role == ".":
                        continue
                    expected = palette_rgb(palette, int(role, 16))
                    pixel_offset = (rect[0] + x) * 4
                    actual = tuple(
                        rows[rect[1] + y][pixel_offset:pixel_offset + 3]
                    )
                    if actual != expected:
                        mismatch = (
                            "frame=%d type=%d rect=%r pixel=(%d,%d) "
                            "actual=%r expected=%r role=%s" %
                            (candidate_frame, enemy_type, rect,
                             rect[0] + x, rect[1] + y, actual, expected, role)
                        )
                        break
                    checked += 1
                if mismatch is not None:
                    break
            if mismatch is not None:
                break
            if checked == 0:
                mismatch = "frame=%d type=%d has no rendered pixels" % (
                    candidate_frame, enemy_type,
                )
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
    drops_power = 1 if enemy_type in (2, 5, 8) else 0
    return [x, y, width, height, 1, enemy_type, 0, y,
            0, 0, 1, 255, 0, drops_power]


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
        active = state[enemy_base + slot * GAME_ENEMY_BULLET_SIZE + 4]
        if active != 0:
            raise RuntimeError(
                "stage %d cast enemy bullet %d active=%d" %
                (stage, slot, active)
            )
    power_active = state[GAME_OFFSET_POWER_ITEM - GAME_OFFSET_BULLETS + 4]
    if power_active != 0:
        raise RuntimeError("stage %d cast power item active=%d" %
                           (stage, power_active))
    return request_id + 1


def rectangles_overlap(left, right):
    return (left[0] < right[0] + right[2] and
            right[0] < left[0] + left[2] and
            left[1] < right[1] + right[3] and
            right[1] < left[1] + left[3])


def verify_cast_readback(game_address, stage, request_id):
    enemies = read_bytes(game_address + GAME_OFFSET_ENEMIES,
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

    player = tuple(read_bytes(game_address + GAME_OFFSET_PLAYER, 4,
                              request_id))
    request_id += 1
    visibility = read_bytes(game_address + GAME_OFFSET_DYING, 3, request_id)
    request_id += 1
    if (player[2:] != (8, 6) or player[0] + player[2] > 160 or
            player[1] < 10 or player[1] + player[3] > 102 or
            visibility[0] != 0 or visibility[2] != 0):
        raise RuntimeError(
            "stage %d cast player not normally visible: rect=%r "
            "dying=%d invincibility=%d" %
            (stage, player, visibility[0], visibility[2])
        )
    if any(rectangles_overlap(player, rect) for _, rect in actual):
        raise RuntimeError("stage %d cast overlaps player rect=%r cast=%r" %
                           (stage, player, actual))
    request_id = assert_no_transient_gameplay(game_address, request_id, stage)
    return request_id, actual


def inject_and_synchronize_cast(game_address, logic_address, sound_address,
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
        write_bytes(game_address + GAME_OFFSET_ENEMIES, records, request_id)
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
    return verify_cast_readback(game_address, stage, request_id)


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


def synchronize_completed_draw(game_address, logic_address, stage, phase,
                               require_boss, request_id):
    logic_hex = "%04X" % logic_address
    tool("set_breakpoint", {"address": logic_hex}, request_id)
    request_id += 1
    # The injected timer boundary changes phase in one of the four logic calls
    # per draw.  Eight subsequent game_update_logic entries guarantee one full
    # target-phase draw plus the following double-buffer display swap,
    # regardless of which call in the current draw frame received the state.
    for _ in range(8):
        request_id = continue_to_breakpoint(request_id,
                                            "post-transition logic")
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


def transition_and_synchronize(game_address, logic_address, stage,
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
        game_address, logic_address, stage, target_phase, require_boss,
        request_id,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path, default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--map", type=Path, default=Path("build/asteroid-patrol.map"))
    parser.add_argument("--input", type=Path, default=Path("assets/stages/stages.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/APS-034"))
    parser.add_argument("--gui", action="store_true",
                        help="launch the Gearlynx GUI while running the same checks")
    args = parser.parse_args()

    if not Path(GEARLYNX).is_file():
        print("Gearlynx executable not found", file=sys.stderr)
        return 1
    game_address = main_bss_game_address(args.map)
    logic_address = symbol_address(args.symbols, "_game_update_logic")
    sound_address = symbol_address(args.symbols, "_game_sound_tick")
    validate_game_enemy_layout()
    cast_sprites = validate_cast_sprite_data(args.input)
    palettes = generated_palettes(args.input)
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
                    "clientInfo": {"name": "aps034-visuals", "version": "1"},
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

        for stage in range(1, 4):
            request_id = transition_and_synchronize(
                game_address, logic_address, stage, GAME_PHASE_STAGE_INTRO,
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
            normal_png = capture(normal_path, request_id)
            request_id += 1
            if args.gui:
                verify_gui_matches_headless(normal_path, normal_png)

            request_id, cast_readback = inject_and_synchronize_cast(
                game_address, logic_address, sound_address, stage, request_id,
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
                cast_png, stage, animation_frame, cast_sprites, cast_palette,
            )
            if args.gui:
                verify_gui_matches_headless(cast_path, cast_png)

            request_id = transition_and_synchronize(
                game_address, logic_address, stage, GAME_PHASE_WARNING,
                119, GAME_PHASE_BOSS, True, request_id,
            )
            boss_path = args.output_dir / ("stage%d-boss.png" % stage)
            boss_png = capture(boss_path, request_id)
            request_id += 1
            if args.gui:
                verify_gui_matches_headless(boss_path, boss_png)
            print("stage %d NORMAL/CAST/BOSS palette OK cast=%r frame=%d" %
                  (stage, cast_readback, rendered_frame))
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
