#!/usr/bin/env python3
"""Generate and verify the asset-isolated APS-044 player previews."""

import argparse
import hashlib
import json
import struct
import tempfile
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "assets/previews/aps044-player-preview.json"
DEFAULT_OUTPUT = ROOT / "evidence/APS-044"
EXPECTED_PALETTE = {
    "9": "#334488",
    "8": "#FF6644",
    "7": "#99FFEE",
    "C": "#FFDD55",
}
EXPECTED_VARIANTS = {"a": "delta-wing", "b": "twin-boom-heavy"}
TRANSPARENT = (0, 0, 0, 0)


class ValidationError(ValueError):
    pass


def fail(path, message):
    raise ValidationError("%s: %s" % (path, message))


def reject_constant(value):
    raise ValidationError("JSON constant is not permitted: %s" % value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(
                stream,
                object_pairs_hook=unique_object,
                parse_constant=reject_constant,
            )
    except json.JSONDecodeError as error:
        raise ValidationError("%s:%d:%d: %s" % (
            path, error.lineno, error.colno, error.msg
        )) from error


def require_keys(value, expected, path):
    if not isinstance(value, dict):
        fail(path, "object required")
    missing = set(expected) - set(value)
    unknown = set(value) - set(expected)
    if missing:
        fail(path, "missing keys: %s" % ", ".join(sorted(missing)))
    if unknown:
        fail(path, "unknown keys: %s" % ", ".join(sorted(unknown)))


def parse_hex_color(value, path):
    if (not isinstance(value, str) or len(value) != 7 or
            value[0] != "#"):
        fail(path, "#RRGGBB color required")
    try:
        rgb = tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
    except ValueError as error:
        raise ValidationError("%s: invalid color %r" % (path, value)) from error
    return rgb + (255,)


def horizontal_runs(grid):
    runs = []
    for y, row in enumerate(grid):
        x = 0
        while x < len(row):
            role = row[x]
            if role == ".":
                x += 1
                continue
            start = x
            x += 1
            while x < len(row) and row[x] == role:
                x += 1
            runs.append((role, start, x - 1, y))
    return runs


def components(grid, role=None):
    positions = {
        (x, y)
        for y, row in enumerate(grid)
        for x, cell in enumerate(row)
        if cell != "." and (role is None or cell == role)
    }
    result = []
    while positions:
        pending = [positions.pop()]
        component = set(pending)
        while pending:
            x, y = pending.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    point = (x + dx, y + dy)
                    if point in positions:
                        positions.remove(point)
                        component.add(point)
                        pending.append(point)
        result.append(component)
    return result


def bounding_box(points):
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def count_row_segments(row):
    count = 0
    inside = False
    for cell in row:
        if cell == ".":
            inside = False
        elif not inside:
            count += 1
            inside = True
    return count


def validate_variant(variant, width, height, path):
    require_keys(variant, {"id", "name", "grid"}, path)
    variant_id = variant["id"]
    if variant_id not in EXPECTED_VARIANTS:
        fail(path + ".id", "variant id must be a or b")
    if variant["name"] != EXPECTED_VARIANTS[variant_id]:
        fail(path + ".name", "fixed design name mismatch")
    grid = variant["grid"]
    if not isinstance(grid, list) or len(grid) != height:
        fail(path + ".grid", "exactly %d rows required" % height)
    for y, row in enumerate(grid):
        if not isinstance(row, str) or len(row) != width:
            fail("%s.grid[%d]" % (path, y),
                 "exactly %d characters required" % width)
        invalid = set(row) - set(".987C")
        if invalid:
            fail("%s.grid[%d]" % (path, y),
                 "invalid cells: %s" % ", ".join(sorted(invalid)))

    points = {
        (x, y)
        for y, row in enumerate(grid)
        for x, cell in enumerate(row)
        if cell != "."
    }
    if not points:
        fail(path + ".grid", "empty design")
    min_x, min_y, max_x, max_y = bounding_box(points)
    box_width = max_x - min_x + 1
    box_height = max_y - min_y + 1
    if not 14 <= box_width <= 16:
        fail(path + ".grid", "occupied width must be 14..16")
    if not 9 <= box_height <= 12:
        fail(path + ".grid", "occupied height must be 9..12")
    if not 1 <= min_y <= 3 or not 1 <= height - max_y - 1 <= 3:
        fail(path + ".grid", "top and bottom margins must each be 1..3 pixels")
    if min_x != 0 or max_x != width - 1:
        fail(path + ".grid", "tail and nose must reach the left/right edges")

    roles = {grid[y][x] for x, y in points}
    if roles != set(EXPECTED_PALETTE):
        fail(path + ".grid", "all four fixed hardware roles are required")
    role_counts = {
        role: sum(row.count(role) for row in grid)
        for role in sorted(roles)
    }
    runs = horizontal_runs(grid)
    longest_runs = {}
    for role, start, end, _y in runs:
        length = end - start + 1
        longest_runs[role] = max(longest_runs.get(role, 0), length)
        if length >= 12:
            fail(path + ".grid", "12-pixel role run is forbidden")
        if role == "8" and length > 6:
            fail(path + ".grid", "hull run exceeds 6 pixels")
    for y in range(height - 1):
        for x in range(width - 1):
            if (grid[y][x:x + 2] == "99" and
                    grid[y + 1][x:x + 2] == "99"):
                fail(path + ".grid", "outline contains a 2-pixel-thick band")

    filled_ratio = len(points) / float(box_width * box_height)
    if filled_ratio > 0.85:
        fail(path + ".grid", "bounding box fill exceeds 85 percent")
    spans = {
        max(x for x, point_y in points if point_y == y) -
        min(x for x, point_y in points if point_y == y) + 1
        for y in range(min_y, max_y + 1)
        if any(point_y == y for _x, point_y in points)
    }
    if len(spans) < 3:
        fail(path + ".grid", "at least three colored row spans required")
    if all(count_row_segments(grid[y]) == 1 for y in range(min_y, max_y + 1)):
        fail(path + ".grid", "primitive solid silhouette is forbidden")
    cropped = [grid[y][min_x:max_x + 1] for y in range(min_y, max_y + 1)]
    if cropped == list(reversed(cropped)):
        fail(path + ".grid", "vertical symmetry is forbidden")
    if len(components(grid)) != 1:
        fail(path + ".grid", "ship pixels must form one 8-connected silhouette")

    engine_components = components(grid, "C")
    if len(engine_components) != 1:
        fail(path + ".grid", "one engine flare component required")
    engine = engine_components[0]
    engine_box = bounding_box(engine)
    engine_width = engine_box[2] - engine_box[0] + 1
    engine_height = engine_box[3] - engine_box[1] + 1
    if (engine_box[0] != 0 or engine_width not in (1, 2) or
            engine_height != 2 or len(engine) not in (2, 4)):
        fail(path + ".grid", "engine must be a left-edge 1x2 or 2x2 flare")

    canopy_components = components(grid, "7")
    if len(canopy_components) != 1:
        fail(path + ".grid", "exactly one canopy/highlight component required")
    canopy = canopy_components[0]
    canopy_box = bounding_box(canopy)
    canopy_width = canopy_box[2] - canopy_box[0] + 1
    canopy_height = canopy_box[3] - canopy_box[1] + 1
    if (canopy_width, canopy_height, len(canopy)) not in ((2, 2, 4), (3, 2, 6)):
        fail(path + ".grid", "canopy must be a solid 2x2 or 3x2 block")
    if canopy_box[0] < 8 or canopy_box[1] > (min_y + max_y) // 2:
        fail(path + ".grid", "canopy must sit on the forward upper surface")

    tip_counts = [sum(row[x] != "." for row in grid)
                  for x in range(width - 3, width)]
    if not (tip_counts[0] > tip_counts[1] > tip_counts[2] and
            1 <= tip_counts[2] <= 2):
        fail(path + ".grid", "rightmost three columns must taper to 1..2 pixels")
    tip_cells = [grid[y][width - 1] for y in range(height)
                 if grid[y][width - 1] != "."]
    if not tip_cells or any(cell != "9" for cell in tip_cells):
        fail(path + ".grid", "nose tip must use the deep outline role")

    tail_notch = any(
        grid[y][0] == "." and (grid[y][1] != "." or grid[y][2] != ".")
        for y in range(min_y, max_y + 1)
    )
    if not tail_notch:
        fail(path + ".grid", "one-pixel tail notch required")

    outlined_columns = 0
    occupied_columns = 0
    for x in range(1, width):
        occupied = [y for y in range(height) if grid[y][x] != "."]
        if occupied:
            occupied_columns += 1
            if grid[min(occupied)][x] == "9":
                outlined_columns += 1
    if outlined_columns * 4 < occupied_columns * 3:
        fail(path + ".grid", "upper edge is not predominantly one-pixel outline")

    part_checks = {
        "engine": len(engine) in (2, 4),
        "canopy": len(canopy) in (4, 6),
        "nose": len(tip_cells) in (1, 2),
        "main-wing": any(span >= 10 for span in spans),
        "nozzle-notch": tail_notch,
    }
    if sum(part_checks.values()) < 3:
        fail(path + ".grid", "fewer than three machine-identifiable parts")

    return {
        "id": variant_id,
        "name": variant["name"],
        "cells": len(points),
        "role_counts": role_counts,
        "bbox": (box_width, box_height),
        "fill_ratio": filled_ratio,
        "row_spans": sorted(spans),
        "run_count": len(runs),
        "longest_runs": longest_runs,
        "tip_counts": tip_counts,
        "parts": sorted(name for name, passed in part_checks.items() if passed),
    }


def validate_document(document):
    require_keys(document, {
        "format_version", "width", "height", "scale", "background",
        "palette", "variants",
    }, "root")
    if document["format_version"] != 1:
        fail("format_version", "must be 1")
    if document["width"] != 16 or document["height"] != 16:
        fail("root", "preview canvas must be 16x16")
    if document["scale"] != 8:
        fail("scale", "nearest-neighbor scale must be 8")
    if document["background"] != "#111122":
        fail("background", "dark background must be #111122")
    require_keys(document["palette"], set(EXPECTED_PALETTE), "palette")
    if document["palette"] != EXPECTED_PALETTE:
        fail("palette", "fixed hardware palette mismatch")
    for role, value in document["palette"].items():
        parse_hex_color(value, "palette.%s" % role)
    variants = document["variants"]
    if not isinstance(variants, list) or len(variants) != 2:
        fail("variants", "exactly two variants required")
    metrics = [
        validate_variant(
            variant, document["width"], document["height"],
            "variants[%d]" % index,
        )
        for index, variant in enumerate(variants)
    ]
    if {metric["id"] for metric in metrics} != set(EXPECTED_VARIANTS):
        fail("variants", "variants a and b required exactly once")
    return metrics


def png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload +
            struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def encode_png_rgba(pixels, width, height):
    raw = b"".join(
        b"\x00" + b"".join(bytes(pixel) for pixel in row)
        for row in pixels
    )
    return (b"\x89PNG\r\n\x1a\n" +
            png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height,
                                             8, 6, 0, 0, 0)) +
            png_chunk(b"IDAT", zlib.compress(raw, 9)) +
            png_chunk(b"IEND", b""))


def decode_png_rgba(data, path):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(path, "PNG signature mismatch")
    offset = 8
    compressed = bytearray()
    width = height = None
    saw_end = False
    while offset < len(data):
        if offset + 12 > len(data):
            fail(path, "truncated PNG chunk")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        crc_end = payload_end + 4
        if crc_end > len(data):
            fail(path, "truncated PNG payload")
        payload = data[payload_start:payload_end]
        actual_crc = struct.unpack(">I", data[payload_end:crc_end])[0]
        expected_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            fail(path, "PNG chunk CRC mismatch")
        if kind == b"IHDR":
            if len(payload) != 13:
                fail(path, "invalid IHDR length")
            width, height, depth, color, compression, filtering, interlace = \
                struct.unpack(">IIBBBBB", payload)
            if (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0):
                fail(path, "PNG must be non-interlaced 8-bit RGBA")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            saw_end = True
            offset = crc_end
            break
        offset = crc_end
    if not saw_end or offset != len(data) or width is None or height is None:
        fail(path, "incomplete PNG structure")
    try:
        raw = zlib.decompress(bytes(compressed))
    except zlib.error as error:
        raise ValidationError("%s: invalid PNG deflate stream" % path) from error
    stride = width * 4
    if len(raw) != (stride + 1) * height:
        fail(path, "unexpected decompressed PNG length")
    pixels = []
    for y in range(height):
        start = y * (stride + 1)
        if raw[start] != 0:
            fail(path, "only deterministic PNG filter 0 is permitted")
        row = raw[start + 1:start + 1 + stride]
        pixels.append([
            tuple(row[x:x + 4]) for x in range(0, stride, 4)
        ])
    return width, height, pixels


def rasterize(grid, palette, background):
    return [
        [background if cell == "." else palette[cell] for cell in row]
        for row in grid
    ]


def nearest_neighbor(pixels, scale):
    output = []
    for row in pixels:
        expanded = [pixel for pixel in row for _index in range(scale)]
        for _index in range(scale):
            output.append(list(expanded))
    return output


def artifact_bytes(document):
    palette = {
        role: parse_hex_color(value, "palette.%s" % role)
        for role, value in document["palette"].items()
    }
    dark = parse_hex_color(document["background"], "background")
    result = {}
    for variant in document["variants"]:
        for background_name, background in (
                ("transparent", TRANSPARENT), ("dark", dark)):
            pixels = rasterize(variant["grid"], palette, background)
            base_name = "%s-%s.png" % (variant["id"], background_name)
            result[base_name] = encode_png_rgba(pixels, 16, 16)
            scaled = nearest_neighbor(pixels, document["scale"])
            scaled_name = "%s-%s-8x.png" % (
                variant["id"], background_name
            )
            result[scaled_name] = encode_png_rgba(scaled, 128, 128)
    return result


def verify_artifacts(document, artifacts, output_dir):
    expected = artifact_bytes(document)
    if set(artifacts) != set(expected):
        fail(str(output_dir), "artifact filename set mismatch")
    palette = {
        role: parse_hex_color(value, "palette.%s" % role)
        for role, value in document["palette"].items()
    }
    dark = parse_hex_color(document["background"], "background")
    grids = {variant["id"]: variant["grid"] for variant in document["variants"]}
    for name, data in artifacts.items():
        if data != expected[name]:
            fail(str(output_dir / name), "byte mismatch after regeneration")
        variant_id, background_name = name.split("-", 1)
        scaled = background_name.endswith("-8x.png")
        background_key = background_name[:-7] if scaled else background_name[:-4]
        background = TRANSPARENT if background_key == "transparent" else dark
        base_pixels = rasterize(grids[variant_id], palette, background)
        expected_pixels = nearest_neighbor(base_pixels, 8) if scaled else base_pixels
        expected_size = 128 if scaled else 16
        width, height, actual_pixels = decode_png_rgba(
            data, str(output_dir / name)
        )
        if (width, height) != (expected_size, expected_size):
            fail(str(output_dir / name), "PNG dimensions mismatch")
        if actual_pixels != expected_pixels:
            fail(str(output_dir / name), "PNG pixel mismatch")
        if scaled:
            for y in range(16):
                for x in range(16):
                    expected_pixel = base_pixels[y][x]
                    for yy in range(y * 8, y * 8 + 8):
                        for xx in range(x * 8, x * 8 + 8):
                            if actual_pixels[yy][xx] != expected_pixel:
                                fail(str(output_dir / name),
                                     "non-nearest-neighbor scaled pixel")
    return {
        name: hashlib.sha256(data).hexdigest()
        for name, data in sorted(artifacts.items())
    }


def read_artifacts(output_dir, names):
    result = {}
    for name in names:
        path = output_dir / name
        if not path.is_file():
            fail(str(path), "missing generated artifact")
        result[name] = path.read_bytes()
    return result


def write_artifacts(output_dir, artifacts):
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        (output_dir / name).write_bytes(data)


def readme_text(source, metrics, hashes):
    lines = [
        "# APS-044 player A/B preview evidence",
        "",
        "- Source: `%s`" % source.relative_to(ROOT),
        "- Generator: `scripts/generate-aps044-player-preview.py`",
        "- Canvas: 16x16 RGBA; transparent or `#111122`; 8x nearest-neighbor 128x128",
        "- Scope: preview-only player pixels; game assets, ROM, Gearlynx output, UI, text, and frames excluded",
        "",
        "## Metrics",
        "",
        "| Variant | Cells | Roles | BBox | Fill | Row spans | Runs | Tip columns | Parts |",
        "|---|---:|---|---|---:|---|---:|---|---|",
    ]
    for metric in metrics:
        roles = ", ".join(
            "%s=%d" % (role, metric["role_counts"][role])
            for role in ("9", "8", "7", "C")
        )
        lines.append(
            "| %s | %d | %s | %dx%d | %.1f%% | %s | %d | %s | %s |" % (
                metric["id"].upper(), metric["cells"], roles,
                metric["bbox"][0], metric["bbox"][1],
                metric["fill_ratio"] * 100.0,
                "/".join(str(span) for span in metric["row_spans"]),
                metric["run_count"],
                "/".join(str(count) for count in metric["tip_counts"]),
                ", ".join(metric["parts"]),
            )
        )
    lines.extend([
        "",
        "## PNG SHA-256",
        "",
        "| File | SHA-256 |",
        "|---|---|",
    ])
    for name, digest in sorted(hashes.items()):
        lines.append("| `%s` | `%s` |" % (name, digest))
    lines.extend([
        "",
        "Regeneration check: all eight PNG files were generated again in an independent temporary directory and matched byte-for-byte.",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check", action="store_true",
        help="verify checked-in output without rewriting it",
    )
    args = parser.parse_args()
    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    document = load_json(source)
    metrics = validate_document(document)
    expected = artifact_bytes(document)
    if not args.check:
        write_artifacts(output_dir, expected)
    actual = read_artifacts(output_dir, expected)
    hashes = verify_artifacts(document, actual, output_dir)

    with tempfile.TemporaryDirectory(prefix="aps044-preview-") as temp_name:
        temp_dir = Path(temp_name)
        write_artifacts(temp_dir, artifact_bytes(document))
        regenerated = read_artifacts(temp_dir, expected)
        verify_artifacts(document, regenerated, temp_dir)
        for name in expected:
            if regenerated[name] != actual[name]:
                fail(name, "independent regeneration is not byte-identical")

    readme = readme_text(source, metrics, hashes)
    readme_path = output_dir / "README.md"
    if not args.check:
        readme_path.write_text(readme, encoding="utf-8")

    for metric in metrics:
        print(
            "APS-044 %s: cells=%d roles=%s bbox=%dx%d runs=%d taper=%s" % (
                metric["id"].upper(), metric["cells"],
                "/".join("%s:%d" % (role, metric["role_counts"][role])
                         for role in ("9", "8", "7", "C")),
                metric["bbox"][0], metric["bbox"][1],
                metric["run_count"],
                "/".join(str(count) for count in metric["tip_counts"]),
            )
        )
    print("APS-044 preview verification OK: 8 PNGs, deterministic byte match")


if __name__ == "__main__":
    main()
