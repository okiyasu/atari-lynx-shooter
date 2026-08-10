#!/usr/bin/env python3
"""Generate and verify APS-044 isolated 16x16 character sheets."""

import argparse
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "assets/previews/aps044-enemy-preview.json"
PLAYER_SOURCE = ROOT / "assets/previews/aps044-player-preview.json"
PLAYER_GENERATOR = ROOT / "scripts/generate-aps044-player-preview.py"
DEFAULT_OUTPUT = ROOT / "evidence/APS-044"
BACKGROUND = "#111122"
EXPECTED_PALETTE = {
    "A": "#EE9933",
    "B": "#884422",
    "C": "#FFDD55",
    "D": "#8844DD",
    "E": "#33CCBB",
    "F": "#FFFFFF",
}
NORMAL_IDS = [
    "scout", "saucer", "dropper", "fighter", "bomber", "supply",
    "cave_bat", "rock_worm", "mining_drone",
]
BOSS_IDS = ["coral_bastion", "amber_carrier", "violet_geode"]
EXPECTED_ROLES = {
    "scout": "ABC",
    "saucer": "ABC",
    "dropper": "ABC",
    "fighter": "ABC",
    "bomber": "ABC",
    "supply": "ABC",
    "cave_bat": "BDE",
    "rock_worm": "BDE",
    "mining_drone": "BDE",
    "coral_bastion": "ABCF",
    "amber_carrier": "ABCF",
    "violet_geode": "BDEF",
}
EXPECTED_SILHOUETTES = {
    "scout": "sensor wedge",
    "saucer": "offset dome and rim",
    "dropper": "claw and cargo pod",
    "fighter": "banked wing and long nose",
    "bomber": "armored pod and bomb bay",
    "supply": "cargo frame and lock",
    "cave_bat": "swept split wing",
    "rock_worm": "segmented mineral drill",
    "mining_drone": "asymmetric drill chassis",
    "coral_bastion": "coral spires, turret and reactor",
    "amber_carrier": "bridge, nacelles and engines",
    "violet_geode": "offset facets, nucleus and fissure",
}
EXPECTED_FEATURES = {
    "scout": {"sensor", "wedge", "shadow"},
    "saucer": {"dome", "rim", "shadow"},
    "dropper": {"pod", "claw", "sensor"},
    "fighter": {"nose", "bank-wing", "nozzle"},
    "bomber": {"pod", "bay", "armor"},
    "supply": {"cargo", "lock", "antenna"},
    "cave_bat": {"wing", "membrane", "eye"},
    "rock_worm": {"drill", "segment", "seam"},
    "mining_drone": {"chassis", "core", "drill"},
    "coral_bastion": {"spires", "turret", "reactor", "slit"},
    "amber_carrier": {"bridge", "nacelle", "engine"},
    "violet_geode": {"facet", "nucleus", "fissure"},
}
PLAYER_LOCKED_HASHES = {
    "assets/previews/aps044-player-preview.json":
        "6d9365a52d3b255ca1aff9cfbb4d2151600b43864699de7b7ad14ac50352e44f",
    "scripts/generate-aps044-player-preview.py":
        "6209bc1e86e725232613c8b2b6dcb905dc3b5390bc9a437ce40f1e106ecab45b",
    "evidence/APS-044/a-dark-8x.png":
        "579e14a45713807261e025ae50b11e0008489a14fc61f0cd2a492aae68dcd9e1",
    "evidence/APS-044/a-dark.png":
        "4dea3d93f42883368b6b1e28eaaba1e971906f2e0c669ccd0e4980c221b43926",
    "evidence/APS-044/a-transparent-8x.png":
        "db9f98b72cb92c4622bcf9762d81d487001a84d6e8a9e40367b4d7720f37881d",
    "evidence/APS-044/a-transparent.png":
        "429bd28826eab556f03f5e2e2263a1d3f1f89551169189f63d61ad35a86dbc01",
    "evidence/APS-044/b-dark-8x.png":
        "6d31169b439aa5104655d72adf6608e3d9b39709e06c59ba0defb7f4d0daa613",
    "evidence/APS-044/b-dark.png":
        "d37ca7ad659673ac0faa6469b9c58b28a5c4eceb050a21b8b4ab30db37ace7e5",
    "evidence/APS-044/b-transparent-8x.png":
        "e06db89085ec0656ee065e1e98ae21ebbd4c6aca58f71fc8e1a9002830d7b078",
    "evidence/APS-044/b-transparent.png":
        "89cd83951a3b9428db061a8a9ba740bcb401eec29c734219ccf040a5ff4a3523",
}
SHEET_LAYOUTS = {
    "normal-enemies-sheet.png": (3, 3, NORMAL_IDS),
    "bosses-sheet.png": (3, 1, BOSS_IDS),
    "all-characters-sheet.png": (
        4, 4, ["player_a", "player_b"] + NORMAL_IDS + BOSS_IDS
    ),
}
TILE_WIDTH = 144
TILE_HEIGHT = 152
SPRITE_X = 8
SPRITE_Y = 8
SPRITE_SIZE = 128
LABEL_Y = 138
LABEL_SCALE = 2
LABEL_COLOR = (255, 255, 255, 255)

# Compact 3x5 bitmap font. Labels are rendered as uppercase preview metadata.
FONT = {
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "111", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "_": ("000", "000", "000", "000", "111"),
    "-": ("000", "000", "111", "000", "000"),
}


class ValidationError(ValueError):
    pass


def fail(path, message):
    raise ValidationError("%s: %s" % (path, message))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require_keys(value, expected, path):
    if not isinstance(value, dict):
        fail(path, "object required")
    missing = set(expected) - set(value)
    unknown = set(value) - set(expected)
    if missing:
        fail(path, "missing keys: %s" % ", ".join(sorted(missing)))
    if unknown:
        fail(path, "unknown keys: %s" % ", ".join(sorted(unknown)))


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


def load_player_module():
    spec = importlib.util.spec_from_file_location(
        "aps044_player_preview", PLAYER_GENERATOR
    )
    if spec is None or spec.loader is None:
        fail(str(PLAYER_GENERATOR), "cannot load locked v001 generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_hex_color(value, path):
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        fail(path, "#RRGGBB color required")
    try:
        return tuple(int(value[index:index + 2], 16)
                     for index in (1, 3, 5)) + (255,)
    except ValueError as error:
        raise ValidationError("%s: invalid color %r" % (path, value)) from error


def foreground_points(grid):
    return {
        (x, y) for y, row in enumerate(grid)
        for x, cell in enumerate(row) if cell != "."
    }


def components(grid, role=None):
    remaining = {
        (x, y) for y, row in enumerate(grid)
        for x, cell in enumerate(row)
        if cell != "." and (role is None or cell == role)
    }
    result = []
    while remaining:
        pending = [remaining.pop()]
        component = set(pending)
        while pending:
            x, y = pending.pop()
            for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0),
                           (1, 0), (-1, 1), (0, 1), (1, 1)):
                point = (x + dx, y + dy)
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    pending.append(point)
        result.append(component)
    return result


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


def row_segments(row):
    count = 0
    inside = False
    for cell in row:
        if cell == ".":
            inside = False
        elif not inside:
            count += 1
            inside = True
    return count


def validate_character(character, index):
    path = "characters[%d]" % index
    require_keys(character, {
        "id", "grid_name", "category", "roles", "silhouette",
        "features", "grid",
    }, path)
    character_id = character["id"]
    if character_id not in EXPECTED_ROLES:
        fail(path + ".id", "unknown fixed character id")
    expected_category = "normal" if character_id in NORMAL_IDS else "boss"
    if character["category"] != expected_category:
        fail(path + ".category", "fixed category mismatch")
    if character["grid_name"] != "aps044_%s_preview" % character_id:
        fail(path + ".grid_name", "fixed grid name mismatch")
    if character["roles"] != EXPECTED_ROLES[character_id]:
        fail(path + ".roles", "fixed hardware role set mismatch")
    if character["silhouette"] != EXPECTED_SILHOUETTES[character_id]:
        fail(path + ".silhouette", "fixed silhouette description mismatch")

    grid = character["grid"]
    if not isinstance(grid, list) or len(grid) != 16:
        fail(path + ".grid", "exactly 16 rows required")
    allowed = set(character["roles"])
    for y, row in enumerate(grid):
        if not isinstance(row, str) or len(row) != 16:
            fail("%s.grid[%d]" % (path, y), "exactly 16 cells required")
        invalid = set(row) - allowed - {"."}
        if invalid:
            fail("%s.grid[%d]" % (path, y),
                 "invalid roles: %s" % ", ".join(sorted(invalid)))

    points = foreground_points(grid)
    if not points:
        fail(path + ".grid", "empty fixed grid")
    roles = {grid[y][x] for x, y in points}
    if roles != allowed or not 3 <= len(roles) <= 4:
        fail(path + ".grid", "all three or four fixed roles are required")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    box_width = max_x - min_x + 1
    box_height = max_y - min_y + 1
    fill = len(points) / float(box_width * box_height)
    if fill > 0.85:
        fail(path + ".grid", "bounding box fill exceeds 85 percent")
    if len(components(grid)) != 1:
        fail(path + ".grid", "foreground must be one 8-connected design")

    runs = horizontal_runs(grid)
    longest = {}
    for role, start, end, _y in runs:
        length = end - start + 1
        longest[role] = max(longest.get(role, 0), length)
        if length >= 12:
            fail(path + ".grid", "12-pixel same-role run is forbidden")

    spans = set()
    for y in range(min_y, max_y + 1):
        occupied = [x for x in range(16) if grid[y][x] != "."]
        if occupied:
            spans.add(max(occupied) - min(occupied) + 1)
    if len(spans) < 3:
        fail(path + ".grid", "at least three colored row spans required")
    has_notch = any(row_segments(row) >= 2 for row in grid[min_y:max_y + 1])
    has_taper = len(spans) >= 4 and min(spans) * 2 <= max(spans)
    if not has_notch and not has_taper:
        fail(path + ".grid", "outline taper or cutout required")
    cropped = [row[min_x:max_x + 1] for row in grid[min_y:max_y + 1]]
    if cropped == list(reversed(cropped)):
        fail(path + ".grid", "vertical symmetry is forbidden")

    boundary = set()
    for x, y in points:
        if any((x + dx, y + dy) not in points
               for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
            boundary.add((x, y))
    if boundary and all(grid[y][x] == "B" for x, y in boundary):
        inner_boundary = {
            (x, y) for x, y in points - boundary
            if any((x + dx, y + dy) in boundary
                   for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
        }
        if inner_boundary and all(
                grid[y][x] == "B" for x, y in inner_boundary):
            fail(path + ".grid", "full two-pixel outline is forbidden")
    for role in roles:
        role_components = components(grid, role)
        if len(role_components) > 8:
            fail(path + ".grid", "scattered role noise is forbidden")
        if sum(len(component) == 1 for component in role_components) > 2:
            fail(path + ".grid", "too many isolated role pixels")

    features = character["features"]
    require_keys(features, EXPECTED_FEATURES[character_id], path + ".features")
    feature_points = set()
    for name, cells in features.items():
        if not isinstance(cells, list) or not cells:
            fail("%s.features.%s" % (path, name), "non-empty cells required")
        for cell_index, cell in enumerate(cells):
            cell_path = "%s.features.%s[%d]" % (path, name, cell_index)
            if (not isinstance(cell, list) or len(cell) != 2 or
                    any(type(value) is not int for value in cell)):
                fail(cell_path, "[x, y] integer coordinate required")
            x, y = cell
            if not 0 <= x < 16 or not 0 <= y < 16:
                fail(cell_path, "feature coordinate outside 16x16")
            if grid[y][x] == ".":
                fail(cell_path, "feature coordinate must be colored")
            feature_points.add((x, y))
    if len(feature_points) < len(features) + 1:
        fail(path + ".features", "features require distinct visible cells")

    role_counts = {role: sum(row.count(role) for row in grid)
                   for role in sorted(roles)}
    return {
        "id": character_id,
        "grid_name": character["grid_name"],
        "category": character["category"],
        "roles": character["roles"],
        "silhouette": character["silhouette"],
        "features": sorted(features),
        "cells": len(points),
        "role_counts": role_counts,
        "bbox": (box_width, box_height),
        "fill": fill,
        "spans": sorted(spans),
        "runs": len(runs),
        "longest": longest,
    }


def validate_document(document):
    require_keys(document, {
        "format_version", "width", "height", "scale", "background",
        "palette", "characters",
    }, "root")
    if document["format_version"] != 1:
        fail("format_version", "must be 1")
    if document["width"] != 16 or document["height"] != 16:
        fail("root", "fixed preview grid must be 16x16")
    if document["scale"] != 8:
        fail("scale", "nearest-neighbor scale must be 8")
    if document["background"] != BACKGROUND:
        fail("background", "must be #111122")
    if document["palette"] != EXPECTED_PALETTE:
        fail("palette", "fixed hardware palette mismatch")
    for role, color in document["palette"].items():
        parse_hex_color(color, "palette.%s" % role)
    characters = document["characters"]
    if not isinstance(characters, list) or len(characters) != 12:
        fail("characters", "exactly 12 enemies and bosses required")
    metrics = [validate_character(character, index)
               for index, character in enumerate(characters)]
    actual_ids = [metric["id"] for metric in metrics]
    if actual_ids != NORMAL_IDS + BOSS_IDS:
        fail("characters", "fixed normal/boss id order mismatch")
    grids = [tuple(character["grid"]) for character in characters]
    if len(set(grids)) != len(grids):
        fail("characters", "all fixed grids must be unique")
    return metrics


def locked_player_data(player_module, output_dir):
    for relative, expected_hash in PLAYER_LOCKED_HASHES.items():
        path = ROOT / relative
        if not path.is_file():
            fail(str(path), "locked v001 artifact missing")
        actual_hash = sha256(path.read_bytes())
        if actual_hash != expected_hash:
            fail(str(path), "locked v001 SHA-256 mismatch")
    document = player_module.load_json(PLAYER_SOURCE)
    player_module.validate_document(document)
    expected = player_module.artifact_bytes(document)
    actual = {
        name: (output_dir / name).read_bytes()
        for name in expected
    }
    player_module.verify_artifacts(document, actual, output_dir)
    return document


def blank_pixels(width, height, color):
    return [[color for _x in range(width)] for _y in range(height)]


def blit(target, source, left, top):
    for y, row in enumerate(source):
        target[top + y][left:left + len(row)] = row


def label_pixels(text):
    text = text.upper()
    if any(character not in FONT for character in text):
        fail(text, "label contains unsupported bitmap glyph")
    width = len(text) * 8 - 2
    pixels = [[None for _x in range(width)] for _y in range(10)]
    for index, character in enumerate(text):
        glyph = FONT[character]
        origin_x = index * 8
        for glyph_y, row in enumerate(glyph):
            for glyph_x, value in enumerate(row):
                if value == "1":
                    for yy in range(2):
                        for xx in range(2):
                            pixels[glyph_y * 2 + yy][origin_x + glyph_x * 2 + xx] = \
                                LABEL_COLOR
    return pixels


def draw_label(target, text, tile_left, tile_top, background):
    label = label_pixels(text)
    left = tile_left + (TILE_WIDTH - len(label[0])) // 2
    top = tile_top + LABEL_Y
    if left < tile_left or left + len(label[0]) > tile_left + TILE_WIDTH:
        fail(text, "label does not fit its tile")
    for y, row in enumerate(label):
        for x, pixel in enumerate(row):
            if pixel is not None:
                target[top + y][left + x] = pixel
    return (left, top, len(label[0]), len(label))


def character_sources(enemy_document, player_document):
    sources = {}
    enemy_palette = {
        role: parse_hex_color(color, "palette.%s" % role)
        for role, color in enemy_document["palette"].items()
    }
    for character in enemy_document["characters"]:
        sources[character["id"]] = (
            character["grid"], enemy_palette, character["id"]
        )
    player_palette = {
        role: parse_hex_color(color, "player.palette.%s" % role)
        for role, color in player_document["palette"].items()
    }
    for variant in player_document["variants"]:
        source_id = "player_%s" % variant["id"]
        sources[source_id] = (
            variant["grid"], player_palette, source_id
        )
    return sources


def render_sheet(name, columns, rows, ids, sources, player_module):
    background = parse_hex_color(BACKGROUND, "background")
    width = columns * TILE_WIDTH
    height = rows * TILE_HEIGHT
    sheet = blank_pixels(width, height, background)
    placements = []
    for index, character_id in enumerate(ids):
        row = index // columns
        column = index % columns
        if row >= rows:
            fail(name, "sheet capacity smaller than character count")
        grid, palette, label = sources[character_id]
        base = player_module.rasterize(grid, palette, background)
        scaled = player_module.nearest_neighbor(base, 8)
        tile_left = column * TILE_WIDTH
        tile_top = row * TILE_HEIGHT
        sprite_left = tile_left + SPRITE_X
        sprite_top = tile_top + SPRITE_Y
        blit(sheet, scaled, sprite_left, sprite_top)
        label_box = draw_label(sheet, label, tile_left, tile_top, background)
        placements.append({
            "id": character_id,
            "row": row,
            "column": column,
            "sprite": (sprite_left, sprite_top, SPRITE_SIZE, SPRITE_SIZE),
            "label": label_box,
        })
    return player_module.encode_png_rgba(sheet, width, height), placements


def artifact_bytes(enemy_document, player_document, player_module):
    sources = character_sources(enemy_document, player_document)
    result = {}
    placements = {}
    for name, layout in SHEET_LAYOUTS.items():
        columns, rows, ids = layout
        data, sheet_placements = render_sheet(
            name, columns, rows, ids, sources, player_module
        )
        result[name] = data
        placements[name] = sheet_placements
    return result, placements


def verify_sheet(name, data, placements, sources, player_module):
    columns, rows, expected_ids = SHEET_LAYOUTS[name]
    width, height, pixels = player_module.decode_png_rgba(data, name)
    expected_size = (columns * TILE_WIDTH, rows * TILE_HEIGHT)
    if (width, height) != expected_size:
        fail(name, "sheet dimensions mismatch")
    if [placement["id"] for placement in placements] != expected_ids:
        fail(name, "sheet character order/count mismatch")
    background = parse_hex_color(BACKGROUND, "background")
    for placement in placements:
        character_id = placement["id"]
        grid, palette, label = sources[character_id]
        left, top, sprite_width, sprite_height = placement["sprite"]
        if (sprite_width, sprite_height) != (128, 128):
            fail(name, "sprite box must be 128x128")
        for y in range(16):
            for x in range(16):
                expected = background if grid[y][x] == "." else palette[grid[y][x]]
                for yy in range(top + y * 8, top + y * 8 + 8):
                    for xx in range(left + x * 8, left + x * 8 + 8):
                        if pixels[yy][xx] != expected:
                            fail(name, "%s is not exact 8x nearest-neighbor" % character_id)
        label_left, label_top, label_width, label_height = placement["label"]
        if label_top < top + sprite_height:
            fail(name, "%s label overlaps sprite" % character_id)
        label_region = [
            pixels[y][label_left:label_left + label_width]
            for y in range(label_top, label_top + label_height)
        ]
        expected_label = label_pixels(label)
        for y in range(label_height):
            for x in range(label_width):
                expected = expected_label[y][x]
                actual = label_region[y][x]
                if expected is None:
                    expected = background
                if actual != expected:
                    fail(name, "%s bitmap label mismatch" % character_id)
    return width, height


def verify_artifacts(enemy_document, player_document, artifacts,
                     placements, player_module):
    expected, expected_placements = artifact_bytes(
        enemy_document, player_document, player_module
    )
    if set(artifacts) != set(SHEET_LAYOUTS):
        fail("sheets", "expected exactly three named sheet artifacts")
    sources = character_sources(enemy_document, player_document)
    dimensions = {}
    for name in sorted(artifacts):
        if placements[name] != expected_placements[name]:
            fail(name, "placement metadata mismatch")
        if artifacts[name] != expected[name]:
            fail(name, "byte mismatch after regeneration")
        dimensions[name] = verify_sheet(
            name, artifacts[name], placements[name], sources, player_module
        )
    hashes = {name: sha256(data) for name, data in sorted(artifacts.items())}
    return dimensions, hashes


def write_artifacts(output_dir, artifacts):
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        (output_dir / name).write_bytes(data)


def read_artifacts(output_dir):
    result = {}
    for name in SHEET_LAYOUTS:
        path = output_dir / name
        if not path.is_file():
            fail(str(path), "missing generated sheet")
        result[name] = path.read_bytes()
    return result


def expect_invalid(document, mutate, description):
    candidate = copy.deepcopy(document)
    mutate(candidate)
    try:
        validate_document(candidate)
    except ValidationError:
        return
    fail("negative.%s" % description, "invalid mutation was accepted")


def run_negative_tests(document):
    tests = [
        (lambda value: value["characters"].pop(), "missing-id"),
        (lambda value: value["characters"][0]["grid"].pop(), "height"),
        (lambda value: value["characters"][0]["grid"].__setitem__(2, "X" * 16), "role"),
        (lambda value: value["characters"][0].__setitem__("roles", "AB"), "palette-count"),
        (lambda value: value["characters"][0]["grid"].__setitem__(2, "AAAAAAAAAAAA...."), "long-run"),
        (lambda value: value["characters"][0]["features"]["sensor"].__setitem__(0, [15, 15]), "feature"),
        (lambda value: value["characters"][0].__setitem__("silhouette", "primitive"), "silhouette"),
        (lambda value: value["characters"][1].__setitem__("grid", list(value["characters"][0]["grid"])), "duplicate"),
    ]
    for mutate, description in tests:
        expect_invalid(document, mutate, description)
    return len(tests)


def readme_text(source, metrics, dimensions, hashes, placements):
    lines = [
        "# APS-044 character preview evidence",
        "",
        "- Player source (locked v001): `assets/previews/aps044-player-preview.json`",
        "- Enemy/boss source: `%s`" % source.relative_to(ROOT),
        "- Player generator (locked v001): `scripts/generate-aps044-player-preview.py`",
        "- Sheet generator: `scripts/generate-aps044-character-sheets.py`",
        "- Canvas: independent 16x16 fixed grids; sheets use exact 8x nearest-neighbor sprites on `#111122`",
        "- Scope: preview only; no game screen, HUD/UI, runtime sprite, Gearlynx frame, ROM, or LNX",
        "",
        "## Locked v001 player PNG SHA-256",
        "",
        "| File | SHA-256 |",
        "|---|---|",
    ]
    for relative, digest in sorted(PLAYER_LOCKED_HASHES.items()):
        if relative.endswith(".png"):
            lines.append("| `%s` | `%s` |" % (Path(relative).name, digest))
    lines.extend([
        "",
        "## Enemy and boss fixed-grid metrics",
        "",
        "| ID / grid | Cells | Roles | BBox | Fill | Spans | Runs | Longest role run | Silhouette / features |",
        "|---|---:|---|---|---:|---|---:|---|---|",
    ])
    for metric in metrics:
        roles = ", ".join(
            "%s=%d" % (role, metric["role_counts"][role])
            for role in metric["roles"]
        )
        longest = ", ".join(
            "%s=%d" % (role, metric["longest"][role])
            for role in metric["roles"]
        )
        lines.append(
            "| `%s` / `%s` | %d | %s | %dx%d | %.1f%% | %s | %d | %s | %s / %s |" % (
                metric["id"], metric["grid_name"], metric["cells"], roles,
                metric["bbox"][0], metric["bbox"][1], metric["fill"] * 100.0,
                "/".join(str(span) for span in metric["spans"]), metric["runs"],
                longest, metric["silhouette"], ", ".join(metric["features"]),
            )
        )
    lines.extend([
        "",
        "## Sheet dimensions and SHA-256",
        "",
        "| File | Pixels | Contents | SHA-256 |",
        "|---|---:|---|---|",
    ])
    for name in ("normal-enemies-sheet.png", "bosses-sheet.png", "all-characters-sheet.png"):
        width, height = dimensions[name]
        ids = ", ".join(placement["id"] for placement in placements[name])
        lines.append("| `%s` | %dx%d | %s | `%s` |" % (
            name, width, height, ids, hashes[name]
        ))
    lines.extend([
        "",
        "## Sheet positions",
        "",
        "| Sheet | ID | Cell (row, col) | Sprite box x/y/w/h | Label box x/y/w/h |",
        "|---|---|---:|---|---|",
    ])
    for name in ("normal-enemies-sheet.png", "bosses-sheet.png", "all-characters-sheet.png"):
        for placement in placements[name]:
            lines.append("| `%s` | `%s` | %d,%d | %s | %s |" % (
                name, placement["id"], placement["row"], placement["column"],
                "/".join(str(value) for value in placement["sprite"]),
                "/".join(str(value) for value in placement["label"]),
            ))
    lines.extend([
        "",
        "Regeneration check: the three sheets were independently regenerated in a temporary directory and matched byte-for-byte. The locked v001 source, generator, and eight PNG files were SHA-256 checked and their pixels revalidated without rewriting them.",
        "",
        "Unverified: human readability at native 16x16, Atari Lynx LCD persistence, and any later 12x10/runtime adaptation.",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check", action="store_true",
        help="verify checked-in sheets and manifest without rewriting them",
    )
    args = parser.parse_args()
    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    player_module = load_player_module()
    enemy_document = load_json(source)
    metrics = validate_document(enemy_document)
    negative_count = run_negative_tests(enemy_document)
    player_document = locked_player_data(player_module, output_dir)
    expected, placements = artifact_bytes(
        enemy_document, player_document, player_module
    )
    if not args.check:
        write_artifacts(output_dir, expected)
    actual = read_artifacts(output_dir)
    dimensions, hashes = verify_artifacts(
        enemy_document, player_document, actual, placements, player_module
    )

    with tempfile.TemporaryDirectory(prefix="aps044-sheets-") as temp_name:
        temp_dir = Path(temp_name)
        regenerated, regenerated_placements = artifact_bytes(
            enemy_document, player_document, player_module
        )
        write_artifacts(temp_dir, regenerated)
        reread = {name: (temp_dir / name).read_bytes() for name in SHEET_LAYOUTS}
        verify_artifacts(
            enemy_document, player_document, reread,
            regenerated_placements, player_module,
        )
        for name in expected:
            if reread[name] != actual[name]:
                fail(name, "independent regeneration is not byte-identical")

    readme = readme_text(source, metrics, dimensions, hashes, placements)
    readme_path = output_dir / "README.md"
    if args.check:
        if (not readme_path.is_file() or
                readme_path.read_text(encoding="utf-8") != readme):
            fail(str(readme_path), "evidence manifest mismatch")
    else:
        readme_path.write_text(readme, encoding="utf-8")

    for metric in metrics:
        print("APS-044 %s: cells=%d roles=%s bbox=%dx%d runs=%d" % (
            metric["id"], metric["cells"],
            "/".join("%s:%d" % (role, metric["role_counts"][role])
                     for role in metric["roles"]),
            metric["bbox"][0], metric["bbox"][1], metric["runs"],
        ))
    for name in sorted(hashes):
        print("APS-044 %s: %dx%d sha256=%s" % (
            name, dimensions[name][0], dimensions[name][1], hashes[name]
        ))
    print("APS-044 sheet verification OK: 12 fixed grids, 14 labeled entries, "
          "3 PNGs, %d negative checks, deterministic byte match" % negative_count)


if __name__ == "__main__":
    main()
