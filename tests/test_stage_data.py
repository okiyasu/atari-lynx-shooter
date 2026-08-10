#!/usr/bin/env python3
"""Negative and determinism tests for APS-034/APS-049 stage+sprite authoring."""

import copy
import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage_generator", ROOT / "scripts" / "generate-stage-data.py"
)
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)
CHECKS = 0


def expect(condition, message):
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def expect_invalid(document, previews, message):
    try:
        GENERATOR.validate(document, previews)
    except GENERATOR.ValidationError:
        expect(True, message)
        return
    expect(False, message)


def mutated(base, change):
    document = copy.deepcopy(base)
    change(document)
    return document


def grid_from_runs(runs, canvas=16):
    hexchars = "0123456789ABCDEF"
    grid = [["." for _ in range(canvas)] for _ in range(canvas)]
    for y, x0, x1, color in runs:
        for x in range(x0, x1 + 1):
            grid[y][x] = hexchars[color]
    return ["".join(row) for row in grid]


def main():
    input_path = ROOT / "assets" / "stages" / "stages.json"
    golden_path = ROOT / "tests" / "golden" / "stage-data-v034.json"
    sprite_golden_path = ROOT / "tests" / "golden" / "sprite-data-v050.json"
    document = GENERATOR.load_json(input_path)
    previews, player_doc, enemy_doc = GENERATOR.load_previews()
    GENERATOR.validate(document, previews)
    GENERATOR.verify_golden(document, golden_path)
    GENERATOR.verify_sprite_golden(document, sprite_golden_path, previews)
    expect(True, "valid authoring data and stage/sprite goldens must pass")
    expect(GENERATOR.weighted_combatant_count(4, 1) == 8,
           "four normal enemies plus one boss must fill weighted limit eight")
    try:
        GENERATOR.validate_combatant_mix(5, 1, "test")
    except GENERATOR.ValidationError:
        expect(True, "five normal enemies plus one boss must reject weighted nine")
    else:
        expect(False, "five normal enemies plus one boss must reject weighted nine")
    GENERATOR.validate_combatant_mix(8, 0, "test")
    expect(True, "eight normal enemies must fill weighted limit eight")

    # APS-049 contract a: the preview JSON (single visual source) is pinned
    # by the sprite golden hash. A grid mutation must be detected.
    changed_previews = copy.deepcopy(previews)
    changed_previews["player"]["grid"][2] = "................"
    try:
        GENERATOR.verify_sprite_golden(document, sprite_golden_path,
                                       changed_previews)
    except GENERATOR.ValidationError:
        expect(True, "v0.50.0 sprite golden must detect preview grid changes")
    else:
        expect(False, "v0.50.0 sprite golden must detect preview grid changes")

    mapping_mutation = copy.deepcopy(document)
    mapping_mutation["enemy_types"][0]["sprite"] = "saucer"
    mapping_mutation["enemy_types"][1]["sprite"] = "scout"
    try:
        GENERATOR.verify_golden(mapping_mutation, golden_path)
    except GENERATOR.ValidationError:
        expect(True, "enemy type to sprite mapping mutation must be rejected")
    else:
        expect(False, "enemy type to sprite mapping mutation must be rejected")

    raw_invalid = ROOT / "tests" / "fixtures" / "stages"
    for fixture in sorted(raw_invalid.glob("*.json")):
        try:
            value = GENERATOR.load_json(fixture)
            GENERATOR.validate(value, previews)
        except GENERATOR.ValidationError:
            expect(True, "%s must fail" % fixture.name)
        else:
            expect(False, "%s must fail" % fixture.name)

    cases = [
        ("unknown key", lambda d: d.update({"extra": 1})),
        ("missing key", lambda d: d.pop("formations")),
        ("float number", lambda d: d["stages"][0].update({"id": 1.0})),
        ("null number", lambda d: d["formations"][0]["slots"][0].update({"x": None})),
        ("string number", lambda d: d["formations"][0]["slots"][0].update({"x": "140"})),
        ("wrong stage count", lambda d: d["stages"].pop()),
        ("wrong stage id", lambda d: d["stages"][1].update({"id": 3})),
        ("wrong slot count", lambda d: d["formations"][0]["slots"].pop()),
        ("normal combatant weight two", lambda d: d.update({"normal_combatant_weight": 2})),
        ("boss combatant weight one", lambda d: d.update({"boss_combatant_weight": 1})),
        ("combatant limit nine", lambda d: d.update({"combatant_limit": 9})),
        ("boss coexistence type", lambda d: d["stages"][0].update({
            "boss_coexists_with_normal_enemies": 1
        })),
        ("nine active slots", lambda d: d["formations"][0]["slots"].extend(
            copy.deepcopy(d["formations"][0]["slots"][:1]) * 5
        )),
        ("wrong theme color count", lambda d: d["themes"][0]["colors"].pop()),
        ("unknown stage reference", lambda d: d["stages"][0].update({"theme": "missing"})),
        ("unknown sprite reference", lambda d: d["enemy_types"][0].update({"sprite": "missing"})),
        ("respawn uchar wrap", lambda d: d["formations"][0]["respawn"].update({"x": 250})),
        ("spawn x range", lambda d: d["formations"][0]["slots"][0].update({"x": 249})),
        ("spawn y range", lambda d: d["formations"][0]["slots"][0].update({"y": 10})),
        ("fire phase range", lambda d: d["formations"][0]["slots"][0].update({"fire_phase": 90})),
        ("boss screen boundary", lambda d: d["bosses"][0].update({"stop_x": 150})),
        ("boss collision contract", lambda d: d["bosses"][0].update({"width": 23})),
        ("boss score C range", lambda d: d["bosses"][0].update({"defeat_score": 65536})),
        ("boss script boundary", lambda d: d["boss_scripts"][0]["steps"][0].update({"fire_interval": 121})),
        ("environment event order", lambda d: d["environments"][0]["events"][1].update({"frame": 60})),
        ("environment event range", lambda d: d["environments"][2]["events"][0].update({"position": 153})),
        ("environment direction", lambda d: d["environments"][1]["events"][0].update({"direction": None})),
        ("sprite collision width", lambda d: d["sprites"][0].update({"width": 9})),
        ("sprite collision height", lambda d: d["sprites"][1].update({"height": 9})),
        ("sprite unknown key", lambda d: d["sprites"][0].update({"frames": []})),
        ("duplicate definition id", lambda d: d["themes"][1].update({"id": "space"})),
    ]
    for name, change in cases:
        expect_invalid(mutated(document, change), previews, name)

    # APS-049 preview-side negative cases (contract a/b guardrails).
    def mutated_preview(change):
        clone = copy.deepcopy(previews)
        change(clone)
        return clone

    preview_cases = [
        ("preview grid character",
         lambda p: p["player"]["grid"].__setitem__(2, ".....XXX........")),
        ("preview grid width",
         lambda p: p["player"]["grid"].__setitem__(2, ".....999")),
        ("preview role outside kind",
         lambda p: p["scout"]["grid"].__setitem__(2, "......DD........")),
        ("preview too few colors",
         lambda p: p["scout"].update({"grid": [
             row.replace("C", "B") for row in p["scout"]["grid"]]})),
        ("anim_delta duplicate cell",
         lambda p: p["scout"].update({"anim_delta": [[0, 7, "C"], [0, 7, "C"]]})),
        ("anim_delta unknown role",
         lambda p: p["scout"].update({"anim_delta": [[0, 7, "Z"]]})),
        ("anim_delta no-op recolor",
         lambda p: p["scout"].update({"anim_delta": [[5, 3, "B"]]})),
        ("anim_delta too many cells",
         lambda p: p["scout"].update({"anim_delta": [[x, 0, "C"] for x in range(7)]})),
        ("anim_delta empty",
         lambda p: p["scout"].update({"anim_delta": []})),
        ("feature coordinate on transparent cell",
         lambda p: p["scout"].update({"features": {"sensor": [[0, 0], [12, 6]]}})),
    ]
    for name, change in preview_cases:
        try:
            GENERATOR.validate(document, mutated_preview(change))
        except GENERATOR.ValidationError:
            expect(True, name)
        else:
            expect(False, name)

    # APS-049 contract b: generated frame-0 runs round-trip to the preview
    # grid verbatim for all thirteen sprites, and frame-1 reconstructs as
    # frame 0 plus the declared anim_delta overlay (no other change).
    for sprite_id, preview in previews.items():
        frame0 = preview["grid"]
        runs0 = GENERATOR.sprite_runs(frame0)
        reconstructed0 = grid_from_runs(runs0)
        expect(reconstructed0 == list(frame0),
               "contract b: %s frame 0 runs reconstruct the preview grid "
               "verbatim" % sprite_id)
        expected_frame1 = GENERATOR.apply_anim_delta(
            frame0, preview["anim_delta"], set(preview["roles"]),
            "contract-b.%s" % sprite_id)
        reconstructed1 = [list(row) for row in reconstructed0]
        for x, y, role in preview["anim_delta"]:
            reconstructed1[y][x] = role
        reconstructed1 = ["".join(row) for row in reconstructed1]
        expect(reconstructed1 == expected_frame1,
               "contract b: %s frame 1 is frame 0 plus its anim_delta "
               "overlay, nothing else" % sprite_id)
        for feature, points in preview["features"].items():
            for fx, fy in points:
                expect(frame0[fy][fx] != ".",
                       "contract b: %s feature %s coordinate stays on a "
                       "colored cell" % (sprite_id, feature))

    with tempfile.TemporaryDirectory(prefix="aps034-stage-") as first_dir, \
            tempfile.TemporaryDirectory(prefix="aps034-stage-") as second_dir:
        first = Path(first_dir)
        second = Path(second_dir)
        GENERATOR.generate(document, first, previews)
        GENERATOR.generate(document, second, previews)
        names = ["stage_data.c", "stage_data.h", "sprite_data.c", "sprite_data.h"]
        for name in names:
            expect((first / name).read_bytes() == (second / name).read_bytes(),
                   "%s generation must be deterministic" % name)
        header = (first / "stage_data.h").read_text(encoding="utf-8")
        expect("GAME_STAGE_COUNT 3u" in header and
               "GAME_STAGE_NORMAL_COMBATANT_WEIGHT 1u" in header and
               "GAME_STAGE_BOSS_COMBATANT_WEIGHT 4u" in header and
               "GAME_STAGE_COMBATANT_LIMIT 8u" in header and
               "GAME_BOSS_STEP_COUNT 7u" in header,
               "generated dense counts must be fixed")
        source = (first / "stage_data.c").read_text(encoding="utf-8")
        expect(source.count("slots[4]") == 3,
               "generated formations expose four authored slots within cap eight")
        sprite_header = (first / "sprite_data.h").read_text(encoding="utf-8")
        expect("GAME_SPRITE_CANVAS 16u" in sprite_header and
               "GAME_SPRITE_COUNT 13u" in sprite_header,
               "generated sprite contract exposes the shared 16x16 preview canvas")

    print("PASS: %d stage data validator/generator checks" % CHECKS)


if __name__ == "__main__":
    main()
