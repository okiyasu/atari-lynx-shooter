#!/usr/bin/env python3
"""APS-049 contract e: fix game_sprite_run_data/definitions bytes with a
SHA-256, confirm that exact byte sequence is present in the final .lnx
ROM image, and record the ROM's own SHA-256 as evidence."""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage_generator", ROOT / "scripts" / "generate-stage-data.py"
)
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


def sprite_run_and_definition_bytes(document, previews):
    """Rebuild the exact byte sequence generate-stage-data.py emits into
    game_sprite_run_data[] / game_sprite_definitions[] (see
    render_sprite_source()), independent of the .c text rendering, so the
    comparison is against the same bytes the ROM linker consumes."""
    payload = bytearray()
    sprite_ids = GENERATOR.ordered_index(document["sprites"])
    all_runs = []
    frame_meta = []
    anchors = []
    for sprite in document["sprites"]:
        sprite_id = sprite["id"]
        preview = previews[sprite_id]
        _kind, collision_w, collision_h, scale = \
            GENERATOR.SPRITE_CONTRACTS[sprite_id]
        frame0 = preview["grid"]
        frame0_runs = GENERATOR.sprite_runs(frame0)
        delta_runs = [(y, x, x, int(role, 16))
                     for x, y, role in preview["anim_delta"]]
        frames = []
        for runs in (frame0_runs, delta_runs):
            frames.append((len(all_runs), len(runs)))
            all_runs.extend(runs)
        frame_meta.append(frames)
        anchors.append(GENERATOR.sprite_anchor(
            frame0, collision_w, collision_h, scale))
    for run in all_runs:
        packed = GENERATOR.pack_sprite_run(run)
        payload.extend(packed)
    for frames, anchor in zip(frame_meta, anchors):
        dx, dy = anchor
        payload.append(GENERATOR.pack_sprite_anchor(dx, dy))
        payload.append(frames[0][0] & 0xFF)
        payload.append((frames[0][0] >> 8) & 0xFF)
        payload.append(frames[0][1])
        payload.append(frames[1][1])
    del sprite_ids
    return bytes(payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=ROOT / "assets" / "stages" / "stages.json")
    parser.add_argument("--rom", type=Path,
                        default=ROOT / "dist" / "asteroid-patrol.lnx")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "evidence" / "APS-049" /
                        "sprite-rom-bytes.json")
    args = parser.parse_args()

    document = GENERATOR.load_json(args.input)
    previews, _, _ = GENERATOR.load_previews()
    GENERATOR.validate(document, previews)

    payload = sprite_run_and_definition_bytes(document, previews)
    payload_sha256 = hashlib.sha256(payload).hexdigest()

    if not args.rom.is_file():
        print("FAIL: ROM not found at %s (run `make rom` first)" % args.rom,
              file=sys.stderr)
        return 1
    rom_bytes = args.rom.read_bytes()
    rom_sha256 = hashlib.sha256(rom_bytes).hexdigest()
    offset = rom_bytes.find(payload)
    if offset < 0:
        print("FAIL: sprite run/definition byte sequence (sha256=%s, "
              "%d bytes) not found verbatim in %s" %
              (payload_sha256, len(payload), args.rom), file=sys.stderr)
        return 1

    evidence = {
        "aps": "APS-049",
        "contract": "e",
        "sprite_payload_bytes": len(payload),
        "sprite_payload_sha256": payload_sha256,
        "sprite_payload_offset_in_rom": offset,
        "rom_path": str(args.rom),
        "rom_size_bytes": len(rom_bytes),
        "rom_sha256": rom_sha256,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("PASS: sprite run/definition bytes (sha256=%s) present at ROM "
          "offset %d; ROM sha256=%s" %
          (payload_sha256, offset, rom_sha256))
    return 0


if __name__ == "__main__":
    sys.exit(main())
