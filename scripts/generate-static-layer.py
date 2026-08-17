#!/usr/bin/env python3
"""Generate packed Suzy data for the static background/HUD layers."""

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.c"
OUT_C = ROOT / "src" / "static_layer_data.c"
OUT_H = ROOT / "include" / "static_layer_data.h"


def parse_rows(name, width, minimum=2):
    text = MAIN.read_text()
    if name not in text:
        text = subprocess.check_output(
            ["git", "show", "HEAD:src/main.c"], text=True)
    
    match = re.search(
        r"static const [^{;]+\b" + re.escape(name) + r"\[[^]]*\]\s*=\s*\{(.*?)\};",
        text,
        re.S,
    )
    if not match:
        raise SystemExit("cannot find " + name)
    rows = []
    for values in re.findall(r"\{([^{}]+)\}", match.group(1)):
        numbers = [int(value.rstrip("u"), 0) for value in re.findall(r"\d+", values)]
        if len(numbers) < minimum:
            raise SystemExit("invalid row in " + name)
        rows.append(numbers)
    return rows


def blank(width, height):
    return [[0 for _ in range(width)] for _ in range(height)]


def put_run(image, y, x0, x1, value):
    if 0 <= y < len(image):
        for x in range(max(0, x0), min(len(image[y]) - 1, x1) + 1):
            image[y][x] = value


def layer_from_runs(width, height, runs, value, period=None):
    image = blank(width, height)
    for row in runs:
        y, x0, x1 = row[:3]
        put_run(image, y, x0, x1, value)
    return image


def crop_y(image):
    nonempty = [index for index, row in enumerate(image) if any(row)]
    if not nonempty:
        return [[0]], 0
    first = min(nonempty)
    last = max(nonempty)
    return image[first:last + 1], first


def encode_packed(image, bits):
    """Match cc65 sp65's packed encoder, including its last-pixel workaround."""
    threshold = 2 if bits > 2 else 3 if bits > 1 else 4
    result = []

    def append_bits(stream, value, count):
        for shift in range(count - 1, -1, -1):
            stream.append((value >> shift) & 1)

    for source_line in image:
        last = -1
        for index, value in enumerate(source_line):
            if value != 0:
                last = index
        # Pen zero is transparent for TYPE_NONCOLL. Omitting only the
        # trailing transparent edge keeps one encoded line per source row,
        # while matching the compact shaped-sprite representation.
        line = source_line[:last + 1] if last >= 0 else [0]
        stream = []
        index = 0
        while index < len(line):
            run = 1
            while (index + run < len(line) and run < 16 and
                   line[index + run] == line[index]):
                run += 1
            if run >= threshold:
                append_bits(stream, 0, 1)
                append_bits(stream, run - 1, 4)
                append_bits(stream, line[index], bits)
                index += run
                continue

            values = [line[index]]
            index += 1
            while index < len(line) and len(values) < 16:
                probe = 1
                while (index + probe < len(line) and probe < 16 and
                       line[index + probe] == line[index]):
                    probe += 1
                if probe >= threshold:
                    break
                values.append(line[index])
                index += 1
            append_bits(stream, 1, 1)
            append_bits(stream, len(values) - 1, 4)
            for value in values:
                append_bits(stream, value, bits)

        line_bytes = []
        while stream:
            byte = 0
            for _ in range(8):
                byte = (byte << 1) | (stream.pop(0) if stream else 0)
            line_bytes.append(byte)
        if len(line_bytes) == 1:
            line_bytes.append(0)
        if line_bytes and (line_bytes[-1] & 1):
            line_bytes.append(line_bytes[-1])
        result.append(len(line_bytes) + 1)
        result.extend(line_bytes)

    result.append(0)
    return result


def c_array(name, values):
    lines = ["const unsigned char %s[] = {" % name]
    for start in range(0, len(values), 16):
        lines.append("    " + ", ".join("0x%02x" % v for v in values[start:start + 16]) + ",")
    lines.append("};")
    return "\n".join(lines)


def main():
    planet = parse_rows("planet_runs", 32)
    mountains = parse_rows("mountain_runs", 192)
    mid_groups = parse_rows("mid_clouds", 160, 2)
    near_groups = parse_rows("near_clouds", 160, 2)
    mid_shape = parse_rows("mid_cloud_shape", 12)
    near_shape = parse_rows("near_cloud_shape", 21)
    cave_wall = parse_rows("cave_wall_runs", 192)
    cave_rock = parse_rows("cave_rock_runs", 160)
    cave_near = parse_rows("cave_near_runs", 160)
    far_stars = parse_rows("far_stars", 160, 2)
    near_stars = parse_rows("near_stars", 160, 2)

    planet_image = blank(32, 24)
    for y, x0, x1, palette in planet:
        put_run(planet_image, y, x0, x1, palette + 1)

    mountain_image = layer_from_runs(192, 102, mountains, 1)
    mid_image = blank(160, 102)
    for x, y in mid_groups:
        for row, x0, x1 in mid_shape:
            put_run(mid_image, y + row, x + x0, x + x1, 1)
    near_image = blank(160, 102)
    for x, y in near_groups:
        for row, x0, x1 in near_shape:
            put_run(near_image, y + row, x + x0, x + x1, 1)

    wall_image = layer_from_runs(192, 102, cave_wall, 1)
    rock_image = layer_from_runs(160, 102, cave_rock, 1)
    cave_near_image = layer_from_runs(160, 102, cave_near, 1)

    glyphs = {
        "0": [7, 5, 5, 5, 7], "1": [2, 6, 2, 2, 7],
        "2": [7, 1, 7, 4, 7], "3": [7, 1, 7, 1, 7],
        "4": [5, 5, 7, 1, 1], "5": [7, 4, 7, 1, 7],
        "6": [7, 4, 7, 5, 7], "7": [7, 1, 2, 2, 2],
        "8": [7, 5, 7, 5, 7], "9": [7, 5, 7, 1, 7],
        "S": [7, 4, 7, 1, 7], "I": [7, 2, 2, 2, 7],
        "N": [5, 7, 7, 7, 5], "W": [5, 5, 5, 7, 2],
        "B": [6, 5, 6, 5, 6], "C": [7, 4, 4, 4, 7],
        "A": [2, 5, 7, 5, 5], "L": [4, 4, 4, 4, 7],
    }

    # The old TGI vector font is deliberately not linked into the ROM. These
    # compact 5x7 glyphs are the direct-Suzy replacement for title/overlay
    # text; the rows are five-bit images, left aligned in the source value.
    font_glyphs = {
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
    glyph_images = {}
    for glyph, rows in glyphs.items():
        glyph_images[glyph] = [[1 if row & (4 >> x) else 0 for x in range(3)]
                               for row in rows]

    layers = {
        "clear": ([[1]], 1, 0),
        "planet": (planet_image, 2, 0),
        "mountain": (crop_y(mountain_image)[0], 1, crop_y(mountain_image)[1]),
        "mid_cloud": (crop_y(mid_image)[0], 1, crop_y(mid_image)[1]),
        "near_cloud": (crop_y(near_image)[0], 1, crop_y(near_image)[1]),
        "cave_wall": (crop_y(wall_image)[0], 1, crop_y(wall_image)[1]),
        "cave_rock": (crop_y(rock_image)[0], 1, crop_y(rock_image)[1]),
        "cave_near": (crop_y(cave_near_image)[0], 1, crop_y(cave_near_image)[1]),
        "space_far_star": ([[1]], 1, 0),
        "near_star": ([[1, 1]], 1, 0),
    }
    output = ["/* Generated by scripts/generate-static-layer.py. */", "#include \"static_layer_data.h\"", ""]
    header = ["#ifndef STATIC_LAYER_DATA_H", "#define STATIC_LAYER_DATA_H", "", "#include <stddef.h>", ""]
    for name, (image, bits, y_offset) in layers.items():
        values = encode_packed(image, bits)
        output.append(c_array("static_layer_%s_data" % name, values))
        output.append("")
        header.append("#define STATIC_LAYER_%s_WIDTH %d" % (name.upper(), len(image[0])))
        header.append("#define STATIC_LAYER_%s_HEIGHT %d" % (name.upper(), len(image)))
        header.append("#define STATIC_LAYER_%s_Y_OFFSET %d" % (name.upper(), y_offset))
        header.append("#define STATIC_LAYER_%s_BPP %d" % (name.upper(), bits))
        header.append("extern const unsigned char static_layer_%s_data[];" % name)
        header.append("")
    output.append("const unsigned char static_layer_glyph_bits[] = {")
    output.append("    " + ", ".join(str(value) for rows in glyphs.values() for value in rows) + ",")
    output.append("};")
    output.append("")
    output.append("const unsigned char static_layer_font_bits[] = {")
    font_bits = [value for rows in font_glyphs.values() for value in rows]
    output.append("    " + ", ".join(str(value) for value in font_bits) + ",")
    output.append("};")
    output.append("")

    def text_line_data(text):
        # Trailing columns beyond the string are pen zero, which is
        # transparent for TYPE_NONCOLL; trimming the row to the string's
        # own length (instead of always padding to 20 glyph slots) shrinks
        # the literal payload with no visible difference.
        #
        # Each glyph occupies 5 pixel columns plus 1 transparent spacer
        # column (kerning), matching the suffix_glyphs pattern below.
        length = min(len(text), 20)
        pixel_bytes = (length * 6 + 7) // 8
        data = []
        for row in range(7):
            data.append(pixel_bytes + 1)
            pixels = [0] * pixel_bytes
            pixel = 0
            for glyph in text[:length]:
                bits = font_glyphs.get(glyph.upper(), [0] * 7)[row]
                for column in range(5):
                    if bits & (16 >> column):
                        pixels[pixel // 8] |= 0x80 >> (pixel & 7)
                    pixel += 1
                pixel += 1
            data.extend(pixels)
        data.append(0)
        return data

    fixed_texts = {
        "ASTEROID PATROL": "static_layer_text_asteroid_patrol_data",
        "A/B TO START": "static_layer_text_ab_to_start_data",
        "ARROWS: MOVE": "static_layer_text_arrows_move_data",
        "A/B: FIRE": "static_layer_text_ab_fire_data",
        "VOICEVOX:Nemo": "static_layer_text_voicevox_nemo_data",
    }
    for text, symbol in fixed_texts.items():
        values = text_line_data(text)
        output.append("const unsigned char %s[] = {" % symbol)
        output.append("    " + ", ".join(str(value) for value in values) + ",")
        output.append("};")
        output.append("")

    suffix_glyphs = [
        [48, 64, 128, 128, 128, 64, 48],
        [248, 136, 248, 32, 248, 80, 136],
        [160, 240, 160, 184, 224, 160, 184],
        [240, 8, 8, 240, 128, 128, 248],
        [96, 16, 8, 8, 8, 16, 96],
    ]
    suffix_data = []
    for row in range(7):
        suffix_data.append(5)
        pixels = [0] * 4
        pixel = 0
        for glyph in suffix_glyphs:
            for column in range(5):
                if glyph[row] & (0x80 >> column):
                    pixels[pixel // 8] |= 0x80 >> (pixel & 7)
                pixel += 1
            pixel += 1
        suffix_data.extend(pixels)
    suffix_data.append(0)
    output.append("const unsigned char static_layer_text_voicevox_suffix_data[] = {")
    output.append("    " + ", ".join(str(value) for value in suffix_data) + ",")
    output.append("};")
    output.append("")

    output.append("const unsigned char static_layer_near_star_x[] = {" +
                  ", ".join(str(row[0]) for row in near_stars) + "};")
    output.append("const unsigned char static_layer_near_star_y[] = {" +
                  ", ".join(str(row[1]) for row in near_stars) + "};")
    output.append("const unsigned char static_layer_far_star_x[] = {" +
                  ", ".join(str(row[0]) for row in far_stars) + "};")
    output.append("const unsigned char static_layer_far_star_y[] = {" +
                  ", ".join(str(row[1]) for row in far_stars) + "};")
    output.append("")
    header.extend([
        "#define STATIC_LAYER_GLYPH_COUNT %d" % len(glyphs),
        "extern const unsigned char static_layer_glyph_bits[];",
        "#define STATIC_LAYER_FONT_COUNT %d" % len(font_glyphs),
        "#define STATIC_LAYER_FONT_WIDTH 5",
        "#define STATIC_LAYER_FONT_HEIGHT 7",
        "extern const unsigned char static_layer_font_bits[];",
    ])
    for symbol in fixed_texts.values():
        header.append("extern const unsigned char %s[];" % symbol)
    header.append("extern const unsigned char static_layer_text_voicevox_suffix_data[];")
    header.extend([
        "#define STATIC_LAYER_NEAR_STAR_COUNT %d" % len(near_stars),
        "extern const unsigned char static_layer_near_star_x[];",
        "extern const unsigned char static_layer_near_star_y[];",
        "#define STATIC_LAYER_FAR_STAR_COUNT %d" % len(far_stars),
        "extern const unsigned char static_layer_far_star_x[];",
        "extern const unsigned char static_layer_far_star_y[];",
        "",
    ])
    header.extend(["#endif", ""])
    OUT_C.write_text("\n".join(output))
    OUT_H.write_text("\n".join(header))


if __name__ == "__main__":
    main()
