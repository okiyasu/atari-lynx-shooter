#!/usr/bin/env python3
"""Validate APS-034 stage authoring JSON and emit C89 ROM tables."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


FIXED_PALETTE_ROLES = [
    "F2C", "9FE", "F64", "348", "E93",
    "842", "FD5", "84D", "3CB", "FFF",
]
ROOT_KEYS = {
    "format_version", "normal_combatant_weight", "boss_combatant_weight",
    "combatant_limit", "themes", "sprites",
    "enemy_types", "formations",
    "boss_appearances", "boss_scripts", "bosses", "environments", "stages",
}
ENGINE_TYPES = [
    "SCOUT", "SAUCER", "DROPPER", "FIGHTER", "BOMBER", "SUPPLY",
    "CAVE_BAT", "ROCK_WORM", "MINING_DRONE",
]
MOVEMENTS = {"straight": 0, "wave": 1, "dive": 2}
BOSS_MOVEMENTS = {"still": 0, "vertical": 1, "wide": 2}
SHOTS = {
    "straight": 0, "fan": 1, "alternate": 2, "pincer": 3,
    "burst": 4, "cannon_cycle": 5,
}
ENVIRONMENT_KINDS = {"asteroids": 0, "wind": 1, "rockfall": 2}
SPRITE_ROLES = {
    "player": set("789C"),
    "enemy": set("ABC"),
    "mineral": set("BDE"),
    "boss": set("ABCF"),
    "mineral_boss": set("BDEF"),
}
# sprite_id -> (kind, collision_width, collision_height, boss_visual_scale)
# APS-049: visual canvas is now the 16x16 preview grid for every sprite
# (assets/previews/aps044-*-preview.json is the single visual source).
# Collision rectangles are unchanged from APS-042/047. boss_visual_scale
# is the integer factor applied when drawing each sprite (1..2); it does not
# affect collision, RODATA size, or run authoring, only the on-screen draw
# call.
SPRITE_CONTRACTS = {
    "player": ("player", 8, 6, 1),
    "scout": ("enemy", 8, 8, 1),
    "saucer": ("enemy", 8, 8, 1),
    "dropper": ("enemy", 8, 8, 1),
    "fighter": ("enemy", 8, 8, 1),
    "bomber": ("enemy", 8, 8, 1),
    "supply": ("enemy", 8, 8, 1),
    "cave_bat": ("mineral", 8, 8, 1),
    "rock_worm": ("mineral", 8, 8, 1),
    "mining_drone": ("mineral", 8, 8, 1),
    # APS-050: all bosses unified to 1x draw to restore collision-center
    # alignment and avoid screen-edge clipping at configured stop_x.
    "coral_bastion": ("boss", 24, 16, 1),
    "amber_carrier": ("boss", 28, 14, 1),
    "violet_geode": ("mineral_boss", 24, 24, 1),
}
PREVIEW_CANVAS = 16
PLAYER_PREVIEW_PATH = Path("assets/previews/aps044-player-preview.json")
ENEMY_PREVIEW_PATH = Path("assets/previews/aps044-enemy-preview.json")
PLAYER_VARIANT_ID = "a"
# 2-bytes/run encoding budget: every sprite canvas is fixed at 16x16, so a
# generous ceiling on frame-0 run count keeps RODATA/BSS bounded; the real
# gate is the linked RAM residual checked by tests/test_stage_data.py and
# reported in evidence/APS-049 (APS-046 baseline requires >=11 bytes free).
SPRITE_FRAME0_RUN_BUDGET_TOTAL = 620
SPRITE_FRAME1_DELTA_BUDGET_PER_SPRITE = 6
COMBATANT_LIMIT = 8
NORMAL_COMBATANT_WEIGHT = 1
BOSS_COMBATANT_WEIGHT = 4
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
COLOR_RE = re.compile(r"^[0-9A-F]{3}$")


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
                stream, object_pairs_hook=unique_object,
                parse_constant=reject_constant,
            )
    except json.JSONDecodeError as error:
        raise ValidationError("%s:%d:%d: %s" % (
            path, error.lineno, error.colno, error.msg
        )) from error


def object_keys(value, required, optional, path):
    if not isinstance(value, dict):
        fail(path, "object required")
    keys = set(value)
    missing = set(required) - keys
    unknown = keys - set(required) - set(optional)
    if missing:
        fail(path, "missing keys: %s" % ", ".join(sorted(missing)))
    if unknown:
        fail(path, "unknown keys: %s" % ", ".join(sorted(unknown)))


def array(value, path, length=None, nonempty=False):
    if not isinstance(value, list):
        fail(path, "array required")
    if length is not None and len(value) != length:
        fail(path, "exactly %d entries required" % length)
    if nonempty and not value:
        fail(path, "non-empty array required")
    return value


def integer(value, path, minimum=0, maximum=255):
    if isinstance(value, bool) or not isinstance(value, int):
        fail(path, "integer required (float/null/string are invalid)")
    if value < minimum or value > maximum:
        fail(path, "must be in range %d..%d" % (minimum, maximum))
    return value


def string(value, path, choices=None):
    if not isinstance(value, str):
        fail(path, "string required")
    if choices is not None and value not in choices:
        fail(path, "unknown value %r" % value)
    return value


def identifier(value, path):
    value = string(value, path)
    if IDENTIFIER_RE.fullmatch(value) is None:
        fail(path, "lower snake-case identifier required")
    return value


def indexed(items, path, required, optional=()):
    result = {}
    for index, item in enumerate(array(items, path, nonempty=True)):
        item_path = "%s[%d]" % (path, index)
        object_keys(item, required, optional, item_path)
        item_id = identifier(item["id"], item_path + ".id")
        if item_id in result:
            fail(item_path + ".id", "duplicate id %r" % item_id)
        result[item_id] = item
    return result


def require_references(definitions, used, path):
    unknown = used - set(definitions)
    unused = set(definitions) - used
    if unknown:
        fail(path, "unknown references: %s" % ", ".join(sorted(unknown)))
    if unused:
        fail(path, "unreferenced definitions: %s" % ", ".join(sorted(unused)))


def count_runs(rows):
    count = 0
    for row in rows:
        previous = "."
        for cell in row:
            if cell != "." and cell != previous:
                count += 1
            previous = cell
    return count


def maximum_role_run(rows):
    maximum = 0
    for row in rows:
        start = 0
        while start < len(row):
            if row[start] == ".":
                start += 1
                continue
            end = start + 1
            while end < len(row) and row[end] == row[start]:
                end += 1
            maximum = max(maximum, end - start)
            start = end
    return maximum


def complex_row_count(rows):
    count = 0
    for row in rows:
        if count_runs([row]) >= 3:
            count += 1
    return count


def sprite_runs(rows):
    runs = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == ".":
                x += 1
                continue
            start = x
            color = row[x]
            x += 1
            while x < len(row) and row[x] == color:
                x += 1
            runs.append((y, start, x - 1, int(color, 16)))
    return runs


def pack_sprite_run(run):
    """APS-049 2-bytes/run encoding: every sprite canvas is a fixed 16x16
    preview grid, so y, x0, run length and color role all fit in 4 bits
    each (byte0 = y<<4|x0, byte1 = length<<4|color). This halves the
    previous 3-bytes/run cost, which is required to keep the larger
    16x16-authored run counts inside the linked RAM residual budget."""
    y, x0, x1, color = run
    length = x1 - x0
    if not (0 <= y <= 15 and 0 <= x0 <= 15 and 0 <= length <= 15 and
            0 <= color <= 15):
        fail("sprite runs",
             "run %r exceeds the 16x16 2-byte encoding range" % (run,))
    return ((y << 4) | x0, (length << 4) | color)


def preview_bbox(grid, canvas=PREVIEW_CANVAS):
    xs = [x for y in range(canvas) for x in range(canvas)
          if grid[y][x] != "."]
    ys = [y for y in range(canvas) for x in range(canvas)
          if grid[y][x] != "."]
    if not xs:
        fail("preview grid", "grid has no colored cells")
    return min(xs), max(xs), min(ys), max(ys)


def sprite_anchor(grid, collision_width, collision_height, scale,
                  canvas=PREVIEW_CANVAS):
    """(dx, dy) = collision rect center - visual bbox center, decided
    deterministically from the preview grid's colored bounding box so the
    generator (not hand authoring) owns the runtime draw offset."""
    min_x, max_x, min_y, max_y = preview_bbox(grid, canvas)
    bbox_center_x = (min_x + max_x + 1) / 2.0 * scale
    bbox_center_y = (min_y + max_y + 1) / 2.0 * scale
    dx = round(collision_width / 2.0 - bbox_center_x)
    dy = round(collision_height / 2.0 - bbox_center_y)
    if not (-8 <= dx <= 7 and -8 <= dy <= 7):
        fail("sprite anchor",
             "anchor (%d,%d) exceeds the packed 4-bit signed range" %
             (dx, dy))
    return dx, dy


def pack_sprite_anchor(dx, dy):
    """Bias dx/dy by +8 into 0..15 so the C decoder is a plain subtract
    (no branch/sign-extend), trimming CODE size on the 6502 target."""
    return (((dx + 8) & 0x0F) << 4) | ((dy + 8) & 0x0F)


def load_previews(player_path=PLAYER_PREVIEW_PATH,
                  enemy_path=ENEMY_PREVIEW_PATH,
                  player_variant=PLAYER_VARIANT_ID):
    player_doc = load_json(player_path)
    enemy_doc = load_json(enemy_path)
    object_keys(player_doc, {"format_version", "width", "height", "scale",
                             "background", "palette", "variants"}, (),
               "player preview")
    variants = {variant["id"]: variant for variant in player_doc["variants"]}
    if player_variant not in variants:
        fail("player preview", "unknown player variant %r" % player_variant)
    variant = variants[player_variant]
    previews = {
        "player": {
            "grid": variant["grid"],
            "anim_delta": variant.get("anim_delta", []),
            "features": {},
            "roles": "".join(sorted(SPRITE_ROLES["player"])),
        },
    }
    object_keys(enemy_doc, {"format_version", "width", "height", "scale",
                            "background", "palette", "characters"}, (),
               "enemy preview")
    for character in enemy_doc["characters"]:
        previews[character["id"]] = {
            "grid": character["grid"],
            "anim_delta": character.get("anim_delta", []),
            "features": character.get("features", {}),
            "roles": character["roles"],
        }
    return previews, player_doc, enemy_doc


def apply_anim_delta(grid, delta, roles, path, canvas=PREVIEW_CANVAS):
    grid_rows = [list(row) for row in grid]
    if len(delta) < 1 or len(delta) > 6:
        fail(path, "anim_delta must declare 1..6 cells, got %d" % len(delta))
    seen = set()
    for index, entry in enumerate(delta):
        entry_path = "%s[%d]" % (path, index)
        if (not isinstance(entry, list) or len(entry) != 3):
            fail(entry_path, "must be a [x, y, role] triple")
        x, y, role = entry
        x = integer(x, entry_path + "[0]", 0, canvas - 1)
        y = integer(y, entry_path + "[1]", 0, canvas - 1)
        if (x, y) in seen:
            fail(entry_path, "duplicate delta cell (%d,%d)" % (x, y))
        seen.add((x, y))
        if not isinstance(role, str) or role not in roles:
            fail(entry_path, "role %r is not authored for this sprite" % role)
        if grid_rows[y][x] == role:
            fail(entry_path,
                 "delta must add or recolor, not repeat the frame 0 role")
        grid_rows[y][x] = role
    return ["".join(row) for row in grid_rows]


def weighted_combatant_count(normal_enemies, boss_count):
    return (normal_enemies * NORMAL_COMBATANT_WEIGHT +
            boss_count * BOSS_COMBATANT_WEIGHT)


def validate_combatant_mix(normal_enemies, boss_count, path):
    if normal_enemies < 0 or normal_enemies > COMBATANT_LIMIT:
        fail(path, "normal enemy count must be in range 0..8")
    if boss_count < 0 or boss_count > 1:
        fail(path, "boss count must be zero or one")
    weighted = weighted_combatant_count(normal_enemies, boss_count)
    if weighted > COMBATANT_LIMIT:
        fail(path, "weighted combatants %d exceed limit %d" %
             (weighted, COMBATANT_LIMIT))
    return weighted


def validate(document, previews=None):
    object_keys(document, ROOT_KEYS, (), "root")
    integer(document["format_version"], "format_version", 1, 1)
    normal_weight = integer(document["normal_combatant_weight"],
                            "normal_combatant_weight", 1, COMBATANT_LIMIT)
    boss_weight = integer(document["boss_combatant_weight"],
                          "boss_combatant_weight", 1, COMBATANT_LIMIT)
    if normal_weight != NORMAL_COMBATANT_WEIGHT:
        fail("normal_combatant_weight",
             "APS-047 requires normal combatant weight one")
    if boss_weight != BOSS_COMBATANT_WEIGHT:
        fail("boss_combatant_weight",
             "APS-047 requires boss combatant weight four")
    combatant_limit = integer(
        document["combatant_limit"], "combatant_limit", 1, COMBATANT_LIMIT
    )
    if combatant_limit != COMBATANT_LIMIT:
        fail("combatant_limit", "APS-047 requires exactly eight weighted combatants")

    themes = indexed(document["themes"], "themes", {"id", "colors"})
    if len(themes) != 3:
        fail("themes", "exactly three stage themes required")
    for theme_id, theme in themes.items():
        colors = array(theme["colors"], "themes.%s.colors" % theme_id, 6)
        for index, color in enumerate(colors):
            if not isinstance(color, str) or COLOR_RE.fullmatch(color) is None:
                fail("themes.%s.colors[%d]" % (theme_id, index),
                     "three uppercase hexadecimal digits required")

    # APS-049: stages.json only owns the sprite id/kind/collision contract.
    # The single visual source of truth is the 16x16 preview authoring in
    # assets/previews/aps044-*-preview.json (see load_previews()); frame 0
    # must match the preview grid verbatim and frame 1 is preview frame 0
    # plus the preview's declared anim_delta overlay cells.
    sprites = indexed(
        document["sprites"], "sprites", {"id", "kind", "width", "height"},
    )
    if set(sprites) != set(SPRITE_CONTRACTS):
        fail("sprites", "APS-049 requires the fixed thirteen sprite ids")
    if previews is None:
        previews, _, _ = load_previews()
    total_frame0_runs = 0
    for sprite_id, sprite in sprites.items():
        kind = string(sprite["kind"], "sprites.%s.kind" % sprite_id,
                      SPRITE_ROLES)
        width = integer(sprite["width"], "sprites.%s.width" % sprite_id, 1, 32)
        height = integer(sprite["height"], "sprites.%s.height" % sprite_id, 1, 32)
        contract_kind, collision_width, collision_height, _boss_scale = \
            SPRITE_CONTRACTS[sprite_id]
        if kind != contract_kind:
            fail("sprites.%s.kind" % sprite_id,
                 "kind must remain %s" % contract_kind)
        if (width, height) != (collision_width, collision_height):
            fail("sprites.%s" % sprite_id,
                 "APS-049 collision rectangle must be %dx%d" %
                 (collision_width, collision_height))
        if sprite_id not in previews:
            fail("previews", "sprite %r has no preview authoring" % sprite_id)
        preview = previews[sprite_id]
        roles = SPRITE_ROLES[kind]
        preview_roles = set(preview["roles"])
        if not preview_roles <= roles:
            fail("previews.%s.roles" % sprite_id,
                 "preview roles %r exceed the %s role set" %
                 (preview["roles"], kind))
        frame0 = array(preview["grid"], "previews.%s.grid" % sprite_id,
                       PREVIEW_CANVAS)
        colors_used = set()
        for row_index, row in enumerate(frame0):
            row_path = "previews.%s.grid[%d]" % (sprite_id, row_index)
            if not isinstance(row, str) or len(row) != PREVIEW_CANVAS:
                fail(row_path, "preview grid row width must be 16")
            for cell in row:
                if cell != "." and cell not in roles:
                    fail(row_path,
                         "invalid palette role %r for %s" % (cell, kind))
                if cell != ".":
                    colors_used.add(cell)
        if len(colors_used) < 3 or len(colors_used) > 4:
            fail("previews.%s.grid" % sprite_id,
                 "each sprite must use three or four colors")
        apply_anim_delta(frame0, preview["anim_delta"], roles,
                         "previews.%s.anim_delta" % sprite_id)
        for feature, points in preview["features"].items():
            for point_index, point in enumerate(points):
                feature_path = "previews.%s.features.%s[%d]" % (
                    sprite_id, feature, point_index)
                if not isinstance(point, list) or len(point) != 2:
                    fail(feature_path, "feature point must be [x, y]")
                fx = integer(point[0], feature_path + "[0]", 0,
                            PREVIEW_CANVAS - 1)
                fy = integer(point[1], feature_path + "[1]", 0,
                            PREVIEW_CANVAS - 1)
                if frame0[fy][fx] == ".":
                    fail(feature_path,
                         "feature coordinate (%d,%d) must be colored" %
                         (fx, fy))
        total_frame0_runs += len(sprite_runs(frame0))
    if total_frame0_runs > SPRITE_FRAME0_RUN_BUDGET_TOTAL:
        fail("sprites",
             "frame-0 run total %d exceeds the RAM-linked budget %d" %
             (total_frame0_runs, SPRITE_FRAME0_RUN_BUDGET_TOTAL))

    enemy_types = indexed(
        document["enemy_types"], "enemy_types",
        {"id", "engine_type", "sprite"},
    )
    if len(enemy_types) != len(ENGINE_TYPES):
        fail("enemy_types", "exactly nine engine enemy types required")
    seen_engine_types = set()
    enemy_sprite_refs = set()
    for enemy_id, enemy in enemy_types.items():
        engine_type = string(enemy["engine_type"],
                             "enemy_types.%s.engine_type" % enemy_id,
                             ENGINE_TYPES)
        if engine_type in seen_engine_types:
            fail("enemy_types.%s.engine_type" % enemy_id,
                 "duplicate engine type")
        seen_engine_types.add(engine_type)
        enemy_sprite_refs.add(identifier(
            enemy["sprite"], "enemy_types.%s.sprite" % enemy_id
        ))
    if seen_engine_types != set(ENGINE_TYPES):
        fail("enemy_types", "every engine enemy type must be mapped once")

    formations = indexed(
        document["formations"], "formations", {"id", "slots", "respawn"}
    )
    if len(formations) != 3:
        fail("formations", "exactly three formations required")
    used_enemy_types = set()
    for formation_id, formation in formations.items():
        slots = array(formation["slots"],
                      "formations.%s.slots" % formation_id, nonempty=True)
        if len(slots) > combatant_limit:
            fail("formations.%s.slots" % formation_id,
                 "active normal enemies exceed combatant_limit")
        if len(slots) != 4:
            fail("formations.%s.slots" % formation_id,
                 "existing stage difficulty requires exactly four active slots")
        for slot_index, slot in enumerate(slots):
            slot_path = "formations.%s.slots[%d]" % (formation_id, slot_index)
            object_keys(slot, {"x", "y", "enemy", "movement",
                               "fire_interval", "fire_phase"}, (), slot_path)
            integer(slot["x"], slot_path + ".x", 0, 248)
            integer(slot["y"], slot_path + ".y", 11, 94)
            enemy_id = identifier(slot["enemy"], slot_path + ".enemy")
            used_enemy_types.add(enemy_id)
            string(slot["movement"], slot_path + ".movement", MOVEMENTS)
            interval = integer(slot["fire_interval"],
                               slot_path + ".fire_interval", 1, 255)
            phase = integer(slot["fire_phase"], slot_path + ".fire_phase",
                            0, 254)
            if phase >= interval:
                fail(slot_path + ".fire_phase", "must be less than fire_interval")
        respawn = formation["respawn"]
        respawn_path = "formations.%s.respawn" % formation_id
        object_keys(respawn, {"x", "spacing", "min_y", "y_range",
                              "y_multiplier", "type_a", "type_b",
                              "fixed_type", "fire_phase_spacing"}, (), respawn_path)
        respawn_x = integer(respawn["x"], respawn_path + ".x", 0, 255)
        spacing = integer(respawn["spacing"], respawn_path + ".spacing", 0, 255)
        if respawn_x + (len(slots) - 1) * spacing > 255:
            fail(respawn_path, "last active slot respawn x would wrap unsigned char")
        min_y = integer(respawn["min_y"], respawn_path + ".min_y", 11, 94)
        y_range = integer(respawn["y_range"], respawn_path + ".y_range", 1, 255)
        if min_y + y_range - 1 > 94:
            fail(respawn_path, "respawn y range leaves the permitted playfield")
        integer(respawn["y_multiplier"], respawn_path + ".y_multiplier", 1, 255)
        integer(respawn["fire_phase_spacing"],
                respawn_path + ".fire_phase_spacing", 0, 85)
        for key in ("type_a", "type_b", "fixed_type"):
            used_enemy_types.add(identifier(respawn[key], respawn_path + "." + key))

    appearances = indexed(
        document["boss_appearances"], "boss_appearances", {"id", "sprite"}
    )
    if len(appearances) != 3:
        fail("boss_appearances", "exactly three boss appearances required")
    appearance_sprite_refs = set()
    for appearance_id, appearance in appearances.items():
        appearance_sprite_refs.add(identifier(
            appearance["sprite"], "boss_appearances.%s.sprite" % appearance_id
        ))

    scripts = indexed(
        document["boss_scripts"], "boss_scripts", {"id", "steps"}
    )
    if len(scripts) != 3:
        fail("boss_scripts", "exactly three boss scripts required")
    total_steps = 0
    for script_id, script in scripts.items():
        steps = array(script["steps"], "boss_scripts.%s.steps" % script_id,
                      nonempty=True)
        total_steps += len(steps)
        if total_steps > 255:
            fail("boss_scripts", "flattened step offset exceeds unsigned char")
        for step_index, step in enumerate(steps):
            step_path = "boss_scripts.%s.steps[%d]" % (script_id, step_index)
            object_keys(step, {"shot", "duration", "fire_interval", "movement"},
                        (), step_path)
            string(step["shot"], step_path + ".shot", SHOTS)
            duration = integer(step["duration"], step_path + ".duration", 1, 255)
            interval = integer(step["fire_interval"],
                               step_path + ".fire_interval", 1, 255)
            if interval > duration:
                fail(step_path + ".fire_interval", "must not exceed duration")
            string(step["movement"], step_path + ".movement", BOSS_MOVEMENTS)

    bosses = indexed(
        document["bosses"], "bosses",
        {"id", "width", "height", "stop_x", "start_y", "max_hp",
         "defeat_score", "movement", "appearance", "script"},
    )
    if len(bosses) != 3:
        fail("bosses", "exactly three bosses required")
    used_appearances = set()
    used_scripts = set()
    for boss_id, boss in bosses.items():
        boss_path = "bosses.%s" % boss_id
        width = integer(boss["width"], boss_path + ".width", 1, 160)
        height = integer(boss["height"], boss_path + ".height", 1, 92)
        stop_x = integer(boss["stop_x"], boss_path + ".stop_x", 0, 159)
        start_y = integer(boss["start_y"], boss_path + ".start_y", 10, 101)
        if stop_x + width > 160 or start_y + height > 102:
            fail(boss_path, "boss collision rectangle leaves the screen")
        integer(boss["max_hp"], boss_path + ".max_hp", 1, 255)
        integer(boss["defeat_score"], boss_path + ".defeat_score", 0, 65535)
        string(boss["movement"], boss_path + ".movement", BOSS_MOVEMENTS)
        appearance_id = identifier(boss["appearance"], boss_path + ".appearance")
        script_id = identifier(boss["script"], boss_path + ".script")
        used_appearances.add(appearance_id)
        used_scripts.add(script_id)
        if appearance_id in appearances:
            sprite_id = appearances[appearance_id]["sprite"]
            if sprite_id in SPRITE_CONTRACTS and (
                SPRITE_CONTRACTS[sprite_id][1] != width or
                SPRITE_CONTRACTS[sprite_id][2] != height
            ):
                fail(boss_path + ".appearance",
                     "boss collision box differs from its sprite contract")

    environments = indexed(
        document["environments"], "environments", {"id", "kind", "events"}
    )
    if len(environments) != 3:
        fail("environments", "exactly three environments required")
    seen_environment_kinds = set()
    for environment_id, environment in environments.items():
        environment_path = "environments.%s" % environment_id
        kind = string(environment["kind"], environment_path + ".kind",
                      ENVIRONMENT_KINDS)
        if kind in seen_environment_kinds:
            fail(environment_path + ".kind", "duplicate environment kind")
        seen_environment_kinds.add(kind)
        previous_frame = 0
        for event_index, event in enumerate(array(
            environment["events"], environment_path + ".events", nonempty=True
        )):
            event_path = "%s.events[%d]" % (environment_path, event_index)
            object_keys(event, {"frame", "position", "direction"}, (), event_path)
            frame = integer(event["frame"], event_path + ".frame", 1, 1125)
            if frame <= previous_frame:
                fail(event_path + ".frame", "event frames must be strictly increasing")
            previous_frame = frame
            if kind == "asteroids":
                integer(event["position"], event_path + ".position", 11, 94)
            elif kind == "wind":
                integer(event["position"], event_path + ".position", 11, 78)
            else:
                integer(event["position"], event_path + ".position", 0, 152)
            direction = event["direction"]
            if kind == "wind":
                string(direction, event_path + ".direction", {"up", "down"})
            elif direction is not None:
                fail(event_path + ".direction", "must be null outside wind events")

    stages = array(document["stages"], "stages", 3)
    stage_ids = []
    used_themes = set()
    used_formations = set()
    used_environments = set()
    used_bosses = set()
    for index, stage in enumerate(stages):
        stage_path = "stages[%d]" % index
        object_keys(stage, {"id", "theme", "formation", "environment", "boss",
                            "boss_coexists_with_normal_enemies"},
                    (), stage_path)
        coexist = stage["boss_coexists_with_normal_enemies"]
        if not isinstance(coexist, bool):
            fail(stage_path + ".boss_coexists_with_normal_enemies",
                 "boolean required")
        formation_id = identifier(stage["formation"],
                                  stage_path + ".formation")
        if coexist and formation_id in formations:
            validate_combatant_mix(len(formations[formation_id]["slots"]), 1,
                                   stage_path +
                                   ".boss_coexists_with_normal_enemies")
        stage_ids.append(integer(stage["id"], stage_path + ".id", 1, 3))
        used_themes.add(identifier(stage["theme"], stage_path + ".theme"))
        used_formations.add(formation_id)
        used_environments.add(identifier(stage["environment"], stage_path + ".environment"))
        used_bosses.add(identifier(stage["boss"], stage_path + ".boss"))
    if stage_ids != [1, 2, 3]:
        fail("stages", "stage ids must be exactly 1, 2, 3 in order")

    require_references(themes, used_themes, "stages.theme")
    require_references(formations, used_formations, "stages.formation")
    require_references(environments, used_environments, "stages.environment")
    require_references(bosses, used_bosses, "stages.boss")
    require_references(appearances, used_appearances, "bosses.appearance")
    require_references(scripts, used_scripts, "bosses.script")
    require_references(enemy_types, used_enemy_types, "formations.enemy")
    require_references(sprites, {"player"} | enemy_sprite_refs |
                       appearance_sprite_refs, "sprite references")
    if (len(sprites) != 13 or len(enemy_sprite_refs) != 9 or
            len(appearance_sprite_refs) != 3):
        fail("sprites", "distinct player, nine enemy, and three boss sprites required")
    for sprite_id in enemy_sprite_refs:
        if sprite_id in sprites and sprites[sprite_id]["kind"] not in {"enemy", "mineral"}:
            fail("enemy_types", "enemy sprite %r has a non-enemy kind" % sprite_id)
    for sprite_id in appearance_sprite_refs:
        if sprite_id in sprites and sprites[sprite_id]["kind"] not in {"boss", "mineral_boss"}:
            fail("boss_appearances", "boss sprite %r has a non-boss kind" % sprite_id)
    if "player" not in sprites or sprites["player"]["kind"] != "player":
        fail("sprites", "a player sprite with id 'player' is required")


def macro(value):
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def ordered_index(items):
    return {item["id"]: index for index, item in enumerate(items)}


def c_u8(value):
    return "%du" % value


def render_stage_header(document):
    lines = [
        "#ifndef STAGE_DATA_H", "#define STAGE_DATA_H", "",
        "/* Generated by scripts/generate-stage-data.py. Do not edit. */",
        "#define GAME_STAGE_COUNT 3u",
        "#define GAME_STAGE_NORMAL_COMBATANT_WEIGHT %du" %
        document["normal_combatant_weight"],
        "#define GAME_STAGE_BOSS_COMBATANT_WEIGHT %du" %
        document["boss_combatant_weight"],
        "#define GAME_STAGE_COMBATANT_LIMIT %du" % document["combatant_limit"],
    ]
    groups = [
        ("GAME_BACKGROUND_THEME_", document["themes"], 0),
        ("GAME_ENEMY_FORMATION_", document["formations"], 0),
        ("GAME_ENVIRONMENT_", document["environments"], 0),
    ]
    for prefix, items, start in groups:
        for index, item in enumerate(items, start):
            lines.append("#define %s%s %du" % (prefix, macro(item["id"]), index))
        lines.append("#define %sCOUNT %du" % (prefix, len(items)))
    event_macro_names = {
        "asteroids": "ASTEROID", "wind": "WIND", "rockfall": "ROCKFALL",
    }
    for environment in document["environments"]:
        lines.append("#define GAME_%s_EVENT_COUNT %du" % (
            event_macro_names[environment["kind"]], len(environment["events"])
        ))
    lines.append("#define GAME_BOSS_APPEARANCE_COMMON 0u")
    for index, item in enumerate(document["boss_appearances"], 1):
        lines.append("#define GAME_BOSS_APPEARANCE_%s %du" %
                     (macro(item["id"]), index))
    lines.append("#define GAME_BOSS_APPEARANCE_COUNT %du" %
                 (len(document["boss_appearances"]) + 1))
    step_count = sum(len(item["steps"]) for item in document["boss_scripts"])
    lines.extend([
        "#define GAME_BOSS_STEP_COUNT %du" % step_count,
        "", "extern const GameStageConfig game_stage_configs[GAME_STAGE_COUNT];",
        "extern const GameEnemyFormationConfig",
        "    game_enemy_formation_configs[GAME_ENEMY_FORMATION_COUNT];",
        "extern const GameBossConfig game_boss_configs[GAME_STAGE_COUNT];",
        "extern const GameBossStep game_boss_steps[GAME_BOSS_STEP_COUNT];",
        "extern const GameEnvironmentConfig",
        "    game_environment_configs[GAME_ENVIRONMENT_COUNT];",
        "extern const GameEnvironmentEvent game_environment_events[];",
        "extern const unsigned char game_stage_palettes[GAME_STAGE_COUNT][32];",
        "", "#endif", "",
    ])
    return "\n".join(lines)


def palette_bytes(colors):
    values = [int(value, 16) for value in colors + FIXED_PALETTE_ROLES]
    return [(value >> 8) & 0x0F for value in values] + [value & 0xFF for value in values]


def render_stage_source(document):
    theme_ids = ordered_index(document["themes"])
    formation_ids = ordered_index(document["formations"])
    environment_ids = ordered_index(document["environments"])
    boss_ids = ordered_index(document["bosses"])
    appearance_ids = {item["id"]: index for index, item in
                      enumerate(document["boss_appearances"], 1)}
    enemy_ids = {item["id"]: ENGINE_TYPES.index(item["engine_type"])
                 for item in document["enemy_types"]}
    script_offsets = {}
    offset = 0
    for script in document["boss_scripts"]:
        script_offsets[script["id"]] = (offset, len(script["steps"]))
        offset += len(script["steps"])

    lines = [
        '#include "game.h"', "",
        "/* Generated by scripts/generate-stage-data.py. Do not edit. */", "",
    ]
    for formation in document["formations"]:
        lines.append("static const GameEnemyFormationSlot formation_%s_slots[%d] = {" %
                     (formation["id"], len(formation["slots"])))
        for slot in formation["slots"]:
            lines.append("    { %s, %s, %s, %s, %s, %s }," % (
                c_u8(slot["x"]), c_u8(slot["y"]), c_u8(enemy_ids[slot["enemy"]]),
                c_u8(MOVEMENTS[slot["movement"]]), c_u8(slot["fire_interval"]),
                c_u8(slot["fire_phase"]),
            ))
        lines.extend(["};", ""])

    lines.append("const GameEnemyFormationConfig game_enemy_formation_configs[GAME_ENEMY_FORMATION_COUNT] = {")
    for formation in document["formations"]:
        respawn = formation["respawn"]
        lines.append("    { formation_%s_slots, %s, %s, %s, %s, %s, %s, %s, %s, %s }," % (
            formation["id"], c_u8(respawn["x"]), c_u8(respawn["spacing"]),
            c_u8(respawn["min_y"]), c_u8(respawn["y_range"]),
            c_u8(respawn["y_multiplier"]), c_u8(enemy_ids[respawn["type_a"]]),
            c_u8(enemy_ids[respawn["type_b"]]), c_u8(enemy_ids[respawn["fixed_type"]]),
            c_u8(respawn["fire_phase_spacing"]),
        ))
    lines.extend(["};", ""])

    lines.append("const GameBossStep game_boss_steps[GAME_BOSS_STEP_COUNT] = {")
    for script in document["boss_scripts"]:
        for step in script["steps"]:
            lines.append("    { %s, %s, %s, %s }," % (
                c_u8(SHOTS[step["shot"]]), c_u8(step["duration"]),
                c_u8(step["fire_interval"]), c_u8(BOSS_MOVEMENTS[step["movement"]]),
            ))
    lines.extend(["};", ""])

    lines.append("const GameBossConfig game_boss_configs[GAME_STAGE_COUNT] = {")
    for boss in document["bosses"]:
        script_offset, script_count = script_offsets[boss["script"]]
        lines.append("    { %s, %s, %s, %s, %s, %du, %s, %s, %s }," % (
            c_u8(boss["width"]), c_u8(boss["height"]), c_u8(boss["stop_x"]),
            c_u8(boss["start_y"]), c_u8(boss["max_hp"]), boss["defeat_score"],
            c_u8(BOSS_MOVEMENTS[boss["movement"]]), c_u8(script_offset),
            c_u8(script_count),
        ))
    lines.extend(["};", ""])

    event_offset = 0
    lines.append("const GameEnvironmentEvent game_environment_events[] = {")
    for environment in document["environments"]:
        for event in environment["events"]:
            direction = 0
            if event["direction"] == "down":
                direction = 1
            lines.append("    { %du, %s, %s }," % (
                event["frame"], c_u8(event["position"]), c_u8(direction)
            ))
    lines.extend(["};", ""])
    lines.append("const GameEnvironmentConfig game_environment_configs[GAME_ENVIRONMENT_COUNT] = {")
    for environment in document["environments"]:
        count = len(environment["events"])
        lines.append("    { %s, %s, %s }," % (
            c_u8(ENVIRONMENT_KINDS[environment["kind"]]),
            c_u8(event_offset), c_u8(count),
        ))
        event_offset += count
    lines.extend(["};", ""])

    lines.append("const GameStageConfig game_stage_configs[GAME_STAGE_COUNT] = {")
    for stage in document["stages"]:
        boss = document["bosses"][boss_ids[stage["boss"]]]
        lines.append("    { %s, %s, %s, %s, %s }," % (
            c_u8(theme_ids[stage["theme"]]), c_u8(formation_ids[stage["formation"]]),
            c_u8(boss_ids[stage["boss"]]), c_u8(appearance_ids[boss["appearance"]]),
            c_u8(environment_ids[stage["environment"]]),
        ))
    lines.extend(["};", ""])

    lines.append("const unsigned char game_stage_palettes[GAME_STAGE_COUNT][32] = {")
    for stage in document["stages"]:
        theme = document["themes"][theme_ids[stage["theme"]]]
        values = palette_bytes(theme["colors"])
        lines.append("    {")
        lines.append("        " + ", ".join("0x%02xu" % value for value in values[:16]) + ",")
        lines.append("        " + ", ".join("0x%02xu" % value for value in values[16:]))
        lines.append("    },")
    lines.extend(["};", ""])
    return "\n".join(lines)


def render_sprite_header(document, previews):
    lines = [
        "#ifndef SPRITE_DATA_H", "#define SPRITE_DATA_H", "",
        "/* Generated by scripts/generate-stage-data.py. Do not edit. */",
        "#define GAME_SPRITE_CANVAS 16u",
        "#define GAME_SPRITE_FRAME0_RUN_BUDGET %du" %
            SPRITE_FRAME0_RUN_BUDGET_TOTAL,
    ]
    for index, sprite in enumerate(document["sprites"]):
        lines.append("#define GAME_SPRITE_%s %du" % (macro(sprite["id"]), index))
    lines.extend([
        "#define GAME_SPRITE_COUNT %du" % len(document["sprites"]),
        "#define GAME_SPRITE_INVALID 0xffu", "",
        "/* APS-050: single-source preview authoring. Frame 0 is the",
        " * assets/previews/aps044-*-preview.json grid verbatim (16x16,",
        " * 2 bytes/run: byte0 = y<<4|x0, byte1 = length<<4|color). Frame 1",
        " * is an *overlay delta* of 1..6 runs stored immediately after",
        " * frame 0's runs and applied on top of frame 0 by the caller (see",
        " * game_sprite_visit_runs callers in main.c), not a second full",
        " * frame -- this keeps RODATA/RAM within budget, as does folding",
        " * frame_offset/frame_count into one definition (frame 1 has no",
        " * offset field: it starts right after frame 0's run_count runs).",
        " * Visual canvas is always 16x16 (GAME_SPRITE_CANVAS) so",
        " * width/height are not stored per sprite; anchor is packed into",
        " * one byte ((dx+8) in the high nibble, (dy+8) in the low nibble,",
        " * range -8..7) and boss draw scale is derived from SPRITE_CONTRACTS",
        " * at runtime (all bosses are 1x in APS-050) rather than stored,",
        " * to keep the linked RAM budget. */",
        "typedef struct GameSpriteDefinition {",
        "    unsigned char anchor;",
        "    unsigned int frame0_offset;",
        "    unsigned char frame0_count;",
        "    unsigned char frame1_count;",
        "} GameSpriteDefinition;", "",
        "typedef void (*GameSpriteRunVisitor)(int x0, int x1, int y,",
        "    unsigned char color, void* context);", "",
        "extern const unsigned char game_sprite_run_data[];",
        "extern const GameSpriteDefinition game_sprite_definitions[GAME_SPRITE_COUNT];",
        "extern const unsigned char game_enemy_sprite_ids[9];",
        "extern const unsigned char game_boss_sprite_ids[4];",
        "unsigned char game_sprite_visit_runs(int x, int y,",
        "    unsigned char sprite_id, unsigned char animation_frame,",
        "    GameSpriteRunVisitor visitor, void* context);",
        "", "#endif", "",
    ])
    return "\n".join(lines)


def render_sprite_source(document, previews):
    sprite_ids = ordered_index(document["sprites"])
    enemy_by_engine = sorted(document["enemy_types"],
                             key=lambda item: ENGINE_TYPES.index(item["engine_type"]))
    appearance_ids = {item["id"]: index for index, item in
                      enumerate(document["boss_appearances"], 1)}
    boss_sprite_ids = [255] * (len(document["boss_appearances"]) + 1)
    for appearance in document["boss_appearances"]:
        boss_sprite_ids[appearance_ids[appearance["id"]]] = sprite_ids[appearance["sprite"]]

    frame_meta = []
    anchors = []
    all_runs = []
    for sprite in document["sprites"]:
        sprite_id = sprite["id"]
        preview = previews[sprite_id]
        _kind, collision_w, collision_h, scale = SPRITE_CONTRACTS[sprite_id]
        frame0 = preview["grid"]
        frame0_runs = sprite_runs(frame0)
        delta_runs = [(y, x, x, int(role, 16))
                     for x, y, role in preview["anim_delta"]]
        frames = []
        for runs in (frame0_runs, delta_runs):
            frames.append((len(all_runs), len(runs)))
            all_runs.extend(runs)
        frame_meta.append(frames)
        anchors.append(sprite_anchor(frame0, collision_w, collision_h, scale))
    if len(all_runs) > 65535:
        fail("sprites", "flattened sprite run offset exceeds unsigned int")

    lines = [
        '#include "sprite_data.h"', "",
        "/* Generated by scripts/generate-stage-data.py. Do not edit. */", "",
        "const unsigned char game_sprite_run_data[] = {",
    ]
    for run in all_runs:
        packed = pack_sprite_run(run)
        lines.append("    %s, %s," % (c_u8(packed[0]), c_u8(packed[1])))
    lines.extend(["};", ""])
    lines.append("const GameSpriteDefinition game_sprite_definitions[GAME_SPRITE_COUNT] = {")
    for sprite, frames, anchor in zip(document["sprites"], frame_meta, anchors):
        dx, dy = anchor
        assert frames[1][0] == frames[0][0] + frames[0][1], (
            "frame 1 delta runs must immediately follow frame 0's runs")
        lines.append(
            "    { %s, %s, %s, %s }," % (
                c_u8(pack_sprite_anchor(dx, dy)),
                c_u8(frames[0][0]), c_u8(frames[0][1]), c_u8(frames[1][1]),
            ))
    lines.extend(["};", ""])
    lines.append("const unsigned char game_enemy_sprite_ids[9] = {")
    lines.append("    " + ", ".join(c_u8(sprite_ids[item["sprite"]])
                                    for item in enemy_by_engine))
    lines.extend(["};", ""])
    lines.append("const unsigned char game_boss_sprite_ids[4] = {")
    lines.append("    " + ", ".join(c_u8(value) for value in boss_sprite_ids))
    lines.extend(["};", ""])
    lines.extend([
        "unsigned char game_sprite_visit_runs(int x, int y,",
        "    unsigned char sprite_id, unsigned char animation_frame,",
        "    GameSpriteRunVisitor visitor, void* context)",
        "{",
        "    const GameSpriteDefinition* def;",
        "    unsigned int offset;",
        "    unsigned char count;",
        "    unsigned char first;",
        "    unsigned char second;",
        "    unsigned char i;",
        "",
        "    if (sprite_id >= GAME_SPRITE_COUNT || animation_frame > 1u ||",
        "        visitor == (GameSpriteRunVisitor)0) {",
        "        return 0u;",
        "    }",
        "    def = &game_sprite_definitions[sprite_id];",
        "    if (animation_frame == 0u) {",
        "        offset = def->frame0_offset * 2u;",
        "        count = def->frame0_count;",
        "    } else {",
        "        offset = (def->frame0_offset + def->frame0_count) * 2u;",
        "        count = def->frame1_count;",
        "    }",
        "    for (i = 0u; i < count; ++i) {",
        "        first = game_sprite_run_data[offset];",
        "        second = game_sprite_run_data[offset + 1u];",
        "        visitor(x + (int)(first & 0x0fu),",
        "            x + (int)(first & 0x0fu) + (int)(second >> 4),",
        "            y + (int)(first >> 4),",
        "            (unsigned char)(second & 0x0fu),",
        "            context);",
        "        offset += 2u;",
        "    }",
        "    return count;",
        "}", "",
    ])
    return "\n".join(lines)


def golden_snapshot(document):
    keys = ["enemy_types", "formations", "boss_appearances", "boss_scripts",
            "bosses", "environments"]
    snapshot = {key: document[key] for key in keys}
    snapshot["stages"] = [
        {key: value for key, value in stage.items()
         if key != "boss_coexists_with_normal_enemies"}
        for stage in document["stages"]
    ]
    return snapshot


def sprite_authoring_snapshot(document, previews=None):
    """APS-050 contract a: fixes the preview JSON (player variant 'a' plus
    all twelve enemy/boss characters) as the sprite authoring golden,
    alongside the stages.json id/kind/collision contract it must satisfy."""
    if previews is None:
        previews, _, _ = load_previews()
    return {"sprites": document["sprites"], "previews": previews}


def generate(document, output_dir, previews=None):
    if previews is None:
        previews, _, _ = load_previews()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "stage_data.h": render_stage_header(document),
        "stage_data.c": render_stage_source(document),
        "sprite_data.h": render_sprite_header(document, previews),
        "sprite_data.c": render_sprite_source(document, previews),
    }
    for name, content in outputs.items():
        (output_dir / name).write_text(content, encoding="utf-8")


def verify_golden(document, golden_path):
    golden = load_json(golden_path)
    object_keys(golden, {"snapshot_sha256"}, (), "golden")
    expected = string(golden["snapshot_sha256"], "golden.snapshot_sha256")
    payload = json.dumps(
        golden_snapshot(document), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        fail("golden", "generated stage/formation/boss/event tables differ from v0.34.0")


def verify_sprite_golden(document, golden_path, previews=None):
    golden = load_json(golden_path)
    object_keys(golden, {"snapshot_sha256"}, (), "sprite golden")
    expected = string(
        golden["snapshot_sha256"], "sprite golden.snapshot_sha256"
    )
    payload = json.dumps(
        sprite_authoring_snapshot(document, previews), sort_keys=True,
        separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        fail("sprite golden",
             "sprite/preview authoring data differ from v0.49.0")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "validate", "snapshot"))
    parser.add_argument("--input", type=Path,
                        default=Path("assets/stages/stages.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/gen"))
    parser.add_argument("--golden", type=Path)
    parser.add_argument("--sprite-golden", type=Path)
    parser.add_argument("--player-preview", type=Path,
                        default=PLAYER_PREVIEW_PATH)
    parser.add_argument("--enemy-preview", type=Path,
                        default=ENEMY_PREVIEW_PATH)
    args = parser.parse_args()
    try:
        document = load_json(args.input)
        previews, _, _ = load_previews(args.player_preview, args.enemy_preview)
        validate(document, previews)
        if args.golden is not None:
            verify_golden(document, args.golden)
        if args.sprite_golden is not None:
            verify_sprite_golden(document, args.sprite_golden, previews)
        if args.command == "generate":
            generate(document, args.output_dir, previews)
            print("generated stage and sprite C tables: %s" % args.output_dir)
        elif args.command == "snapshot":
            print(json.dumps(golden_snapshot(document), indent=2, ensure_ascii=False))
        else:
            print("stage data valid: stages=3 sprites=%d" % len(document["sprites"]))
    except (OSError, ValidationError) as error:
        print("stage data error: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
