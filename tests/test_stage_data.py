#!/usr/bin/env python3
"""Negative and determinism tests for APS-034 stage authoring."""

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


def expect_invalid(document, message):
    try:
        GENERATOR.validate(document)
    except GENERATOR.ValidationError:
        expect(True, message)
        return
    expect(False, message)


def mutated(base, change):
    document = copy.deepcopy(base)
    change(document)
    return document


def main():
    input_path = ROOT / "assets" / "stages" / "stages.json"
    golden_path = ROOT / "tests" / "golden" / "stage-data-v034.json"
    sprite_golden_path = ROOT / "tests" / "golden" / "sprite-data-v040.json"
    document = GENERATOR.load_json(input_path)
    GENERATOR.validate(document)
    GENERATOR.verify_golden(document, golden_path)
    GENERATOR.verify_sprite_golden(document, sprite_golden_path)
    expect(True, "valid authoring data and stage/sprite goldens must pass")

    changed_sprite = copy.deepcopy(document)
    changed_sprite["sprites"][0]["frames"][0][0] = "..77...."
    try:
        GENERATOR.verify_sprite_golden(changed_sprite, sprite_golden_path)
    except GENERATOR.ValidationError:
        expect(True, "v0.40.0 sprite authoring golden must detect grid changes")
    else:
        expect(False, "v0.40.0 sprite authoring golden must detect grid changes")

    raw_invalid = ROOT / "tests" / "fixtures" / "stages"
    for fixture in sorted(raw_invalid.glob("*.json")):
        try:
            value = GENERATOR.load_json(fixture)
            GENERATOR.validate(value)
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
        ("wrong theme color count", lambda d: d["themes"][0]["colors"].pop()),
        ("unknown stage reference", lambda d: d["stages"][0].update({"theme": "missing"})),
        ("unknown sprite reference", lambda d: d["enemy_types"][0].update({"sprite": "missing"})),
        ("respawn uchar wrap", lambda d: d["formations"][0]["respawn"].update({"x": 250})),
        ("spawn x range", lambda d: d["formations"][0]["slots"][0].update({"x": 249})),
        ("spawn y range", lambda d: d["formations"][0]["slots"][0].update({"y": 10})),
        ("fire phase range", lambda d: d["formations"][0]["slots"][0].update({"fire_phase": 90})),
        ("boss screen boundary", lambda d: d["bosses"][0].update({"stop_x": 150})),
        ("boss score C range", lambda d: d["bosses"][0].update({"defeat_score": 65536})),
        ("boss script boundary", lambda d: d["boss_scripts"][0]["steps"][0].update({"fire_interval": 121})),
        ("environment event order", lambda d: d["environments"][0]["events"][1].update({"frame": 60})),
        ("environment event range", lambda d: d["environments"][2]["events"][0].update({"position": 153})),
        ("environment direction", lambda d: d["environments"][1]["events"][0].update({"direction": None})),
        ("sprite grid character", lambda d: d["sprites"][0]["frames"][0].__setitem__(0, "..X7....")),
        ("sprite grid width", lambda d: d["sprites"][0]["frames"][0].__setitem__(0, "..77...")),
        ("sprite frames equal", lambda d: d["sprites"][0].update({"frames": [d["sprites"][0]["frames"][0], d["sprites"][0]["frames"][0]]})),
        ("sprite run maximum", lambda d: d["sprites"][1]["frames"].__setitem__(0, ["ABABABAB", "BABABABA", "ABABABAB", "BABABABA", "ABABABAB", "BABABABA", "CCCCCCCC", "ABABABAB"])),
        ("duplicate definition id", lambda d: d["themes"][1].update({"id": "space"})),
    ]
    for name, change in cases:
        expect_invalid(mutated(document, change), name)

    with tempfile.TemporaryDirectory(prefix="aps034-stage-") as first_dir, \
            tempfile.TemporaryDirectory(prefix="aps034-stage-") as second_dir:
        first = Path(first_dir)
        second = Path(second_dir)
        GENERATOR.generate(document, first)
        GENERATOR.generate(document, second)
        names = ["stage_data.c", "stage_data.h", "sprite_data.c", "sprite_data.h"]
        for name in names:
            expect((first / name).read_bytes() == (second / name).read_bytes(),
                   "%s generation must be deterministic" % name)
        header = (first / "stage_data.h").read_text(encoding="utf-8")
        expect("GAME_STAGE_COUNT 3u" in header and
               "GAME_BOSS_STEP_COUNT 7u" in header,
               "generated dense counts must be fixed")
        sprite_header = (first / "sprite_data.h").read_text(encoding="utf-8")
        expect("GAME_SPRITE_MAX_RUNS_PER_FRAME 20u" in sprite_header,
               "generated sprite contract must retain the run cap")

    print("PASS: %d stage data validator/generator checks" % CHECKS)


if __name__ == "__main__":
    main()
