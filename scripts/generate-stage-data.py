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
    "format_version", "themes", "sprites", "enemy_types", "formations",
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
    "player": set("789"),
    "enemy": set("ABC"),
    "mineral": set("BDE"),
    "boss": set("ABCF"),
    "mineral_boss": set("BDEF"),
}
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


def validate(document):
    object_keys(document, ROOT_KEYS, (), "root")
    integer(document["format_version"], "format_version", 1, 1)

    themes = indexed(document["themes"], "themes", {"id", "colors"})
    if len(themes) != 3:
        fail("themes", "exactly three stage themes required")
    for theme_id, theme in themes.items():
        colors = array(theme["colors"], "themes.%s.colors" % theme_id, 6)
        for index, color in enumerate(colors):
            if not isinstance(color, str) or COLOR_RE.fullmatch(color) is None:
                fail("themes.%s.colors[%d]" % (theme_id, index),
                     "three uppercase hexadecimal digits required")

    sprites = indexed(
        document["sprites"], "sprites",
        {"id", "kind", "width", "height", "frames"},
    )
    for sprite_id, sprite in sprites.items():
        kind = string(sprite["kind"], "sprites.%s.kind" % sprite_id,
                      SPRITE_ROLES)
        width = integer(sprite["width"], "sprites.%s.width" % sprite_id, 1, 32)
        height = integer(sprite["height"], "sprites.%s.height" % sprite_id, 1, 32)
        frames = array(sprite["frames"], "sprites.%s.frames" % sprite_id, 2)
        if frames[0] == frames[1]:
            fail("sprites.%s.frames" % sprite_id, "two distinct frames required")
        for frame_index, rows in enumerate(frames):
            frame_path = "sprites.%s.frames[%d]" % (sprite_id, frame_index)
            array(rows, frame_path, height)
            colors = set()
            for row_index, row in enumerate(rows):
                if not isinstance(row, str) or len(row) != width:
                    fail("%s[%d]" % (frame_path, row_index),
                         "grid row width must equal %d" % width)
                for cell in row:
                    if cell != "." and cell not in SPRITE_ROLES[kind]:
                        fail("%s[%d]" % (frame_path, row_index),
                             "invalid palette role %r for %s" % (cell, kind))
                    if cell != ".":
                        colors.add(cell)
            if len(colors) < 3 or len(colors) > 4:
                fail(frame_path, "each frame must use three or four colors")
            runs = count_runs(rows)
            if runs > 20:
                fail(frame_path, "horizontal run count %d exceeds 20" % runs)

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
                      "formations.%s.slots" % formation_id, 4)
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
        if respawn_x + 3 * spacing > 255:
            fail(respawn_path, "slot 3 respawn x would wrap unsigned char")
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
            if sprite_id in sprites and (
                sprites[sprite_id]["width"] != width or
                sprites[sprite_id]["height"] != height
            ):
                fail(boss_path + ".appearance",
                     "appearance sprite dimensions must equal boss collision box")

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
        object_keys(stage, {"id", "theme", "formation", "environment", "boss"},
                    (), stage_path)
        stage_ids.append(integer(stage["id"], stage_path + ".id", 1, 3))
        used_themes.add(identifier(stage["theme"], stage_path + ".theme"))
        used_formations.add(identifier(stage["formation"], stage_path + ".formation"))
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
        lines.append("static const GameEnemyFormationSlot formation_%s_slots[4] = {" %
                     formation["id"])
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


def render_sprite_header(document):
    lines = [
        "#ifndef SPRITE_DATA_H", "#define SPRITE_DATA_H", "",
        "/* Generated by scripts/generate-stage-data.py. Do not edit. */",
        "#define GAME_SPRITE_MAX_RUNS_PER_FRAME 20u",
    ]
    for index, sprite in enumerate(document["sprites"]):
        lines.append("#define GAME_SPRITE_%s %du" % (macro(sprite["id"]), index))
    lines.extend([
        "#define GAME_SPRITE_COUNT %du" % len(document["sprites"]),
        "#define GAME_SPRITE_INVALID 0xffu", "",
        "typedef struct GameSpriteRun {",
        "    unsigned char y;", "    unsigned char x0;",
        "    unsigned char x1;", "    unsigned char color;",
        "} GameSpriteRun;", "",
        "typedef struct GameSpriteFrame {",
        "    unsigned int run_offset;", "    unsigned char run_count;",
        "} GameSpriteFrame;", "",
        "typedef struct GameSpriteDefinition {",
        "    unsigned char width;", "    unsigned char height;",
        "    GameSpriteFrame frames[2];", "} GameSpriteDefinition;", "",
        "extern const GameSpriteRun game_sprite_runs[];",
        "extern const GameSpriteDefinition game_sprite_definitions[GAME_SPRITE_COUNT];",
        "extern const unsigned char game_enemy_sprite_ids[9];",
        "extern const unsigned char game_boss_sprite_ids[4];",
        "", "#endif", "",
    ])
    return "\n".join(lines)


def render_sprite_source(document):
    sprite_ids = ordered_index(document["sprites"])
    enemy_by_engine = sorted(document["enemy_types"],
                             key=lambda item: ENGINE_TYPES.index(item["engine_type"]))
    appearance_ids = {item["id"]: index for index, item in
                      enumerate(document["boss_appearances"], 1)}
    boss_sprite_ids = [255] * (len(document["boss_appearances"]) + 1)
    for appearance in document["boss_appearances"]:
        boss_sprite_ids[appearance_ids[appearance["id"]]] = sprite_ids[appearance["sprite"]]

    frame_meta = []
    all_runs = []
    for sprite in document["sprites"]:
        frames = []
        for rows in sprite["frames"]:
            runs = sprite_runs(rows)
            frames.append((len(all_runs), len(runs)))
            all_runs.extend(runs)
        frame_meta.append(frames)
    if len(all_runs) > 65535:
        fail("sprites", "flattened sprite run offset exceeds unsigned int")

    lines = [
        '#include "sprite_data.h"', "",
        "/* Generated by scripts/generate-stage-data.py. Do not edit. */", "",
        "const GameSpriteRun game_sprite_runs[] = {",
    ]
    for y, x0, x1, color in all_runs:
        lines.append("    { %s, %s, %s, %s }," %
                     (c_u8(y), c_u8(x0), c_u8(x1), c_u8(color)))
    lines.extend(["};", ""])
    lines.append("const GameSpriteDefinition game_sprite_definitions[GAME_SPRITE_COUNT] = {")
    for sprite, frames in zip(document["sprites"], frame_meta):
        lines.append("    { %s, %s, { { %s, %s }, { %s, %s } } }," % (
            c_u8(sprite["width"]), c_u8(sprite["height"]),
            c_u8(frames[0][0]), c_u8(frames[0][1]),
            c_u8(frames[1][0]), c_u8(frames[1][1]),
        ))
    lines.extend(["};", ""])
    lines.append("const unsigned char game_enemy_sprite_ids[9] = {")
    lines.append("    " + ", ".join(c_u8(sprite_ids[item["sprite"]])
                                    for item in enemy_by_engine))
    lines.extend(["};", ""])
    lines.append("const unsigned char game_boss_sprite_ids[4] = {")
    lines.append("    " + ", ".join(c_u8(value) for value in boss_sprite_ids))
    lines.extend(["};", ""])
    return "\n".join(lines)


def golden_snapshot(document):
    keys = ["enemy_types", "formations", "boss_appearances", "boss_scripts",
            "bosses", "environments", "stages"]
    return {key: document[key] for key in keys}


def sprite_authoring_snapshot(document):
    return {"sprites": document["sprites"]}


def generate(document, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "stage_data.h": render_stage_header(document),
        "stage_data.c": render_stage_source(document),
        "sprite_data.h": render_sprite_header(document),
        "sprite_data.c": render_sprite_source(document),
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


def verify_sprite_golden(document, golden_path):
    golden = load_json(golden_path)
    object_keys(golden, {"snapshot_sha256"}, (), "sprite golden")
    expected = string(
        golden["snapshot_sha256"], "sprite golden.snapshot_sha256"
    )
    payload = json.dumps(
        sprite_authoring_snapshot(document), sort_keys=True,
        separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        fail("sprite golden", "sprite authoring data differ from v0.40.0")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "validate", "snapshot"))
    parser.add_argument("--input", type=Path,
                        default=Path("assets/stages/stages.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/gen"))
    parser.add_argument("--golden", type=Path)
    parser.add_argument("--sprite-golden", type=Path)
    args = parser.parse_args()
    try:
        document = load_json(args.input)
        validate(document)
        if args.golden is not None:
            verify_golden(document, args.golden)
        if args.sprite_golden is not None:
            verify_sprite_golden(document, args.sprite_golden)
        if args.command == "generate":
            generate(document, args.output_dir)
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
