#!/usr/bin/env python3
"""APS-053 Phase 3R pre-implementation gate: bpp-pack every sprite frame with
the *real* Suzy packed-bitmap encoder (reused from generate-static-layer.py,
already proven on Gearlynx for the static layer) and report the actual byte
counts for all 13 sprites x 2 frames (26 frames total).

This script is verification/estimation only. It does not touch the shipped
ROM pipeline (generate-stage-data.py's own CLI/output is untouched, Makefile
is untouched) and does not implement any Suzy draw code. See
.briefs/APS-053/v032.md.

Usage: python3 scripts/verify-phase-3r-sprite-bpp-gate.py [--json]
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage_gen = _load_module("stage_gen", ROOT / "scripts" / "generate-stage-data.py")
static_layer_gen = _load_module(
    "static_layer_gen", ROOT / "scripts" / "generate-static-layer.py")

CANDIDATE_BPP = (1, 2, 4)  # 3bpp intentionally excluded per v032 scope


def grid_to_rows(grid):
    return [list(row) for row in grid]


def minimal_bpp(distinct_role_count):
    """Smallest bpp in CANDIDATE_BPP that can hold distinct_role_count
    non-transparent colors plus pixel value 0 (transparent)."""
    needed_values = distinct_role_count + 1  # + transparent
    for bpp in CANDIDATE_BPP:
        if (1 << bpp) >= needed_values:
            return bpp
    raise SystemExit("no candidate bpp covers %d colors" % distinct_role_count)


def numeric_image(rows, local_index):
    image = []
    for row in rows:
        image.append([0 if cell == "." else local_index[cell] for cell in row])
    return image


def literal_bytes(rows, local_index, bpp):
    """Unpacked/literal reference size: ceil(16*bpp/8) bytes per scanline,
    byte-aligned, no RLE -- reported for context only."""
    per_row = (stage_gen.PREVIEW_CANVAS * bpp + 7) // 8
    return per_row * len(rows)


def build_sprite_report(sprite, previews):
    sprite_id = sprite["id"]
    kind = sprite["kind"]
    preview = previews[sprite_id]
    roles = stage_gen.SPRITE_ROLES[kind]
    frame0_rows = grid_to_rows(preview["grid"])
    frame1_rows = stage_gen.apply_anim_delta(
        preview["grid"], preview["anim_delta"], roles,
        "previews.%s.anim_delta" % sprite_id)
    frame1_rows = grid_to_rows(frame1_rows)

    colors_frame0 = sorted({c for row in frame0_rows for c in row if c != "."})
    colors_frame1 = sorted({c for row in frame1_rows for c in row if c != "."})
    colors_union = sorted(set(colors_frame0) | set(colors_frame1))
    # Shared local pixel-index assignment across both frames of one sprite,
    # so both frames of a sprite can share one SCB penpal table (APS-053
    # v032 design doc Phase 3R step 2).
    local_index = {role: index + 1 for index, role in enumerate(colors_union)}

    bpp = minimal_bpp(len(colors_union))

    frame_reports = []
    total_packed = 0
    total_literal = 0
    for name, rows in (("frame0", frame0_rows), ("frame1", frame1_rows)):
        image = numeric_image(rows, local_index)
        packed = static_layer_gen.encode_packed(image, bpp)
        packed_size = len(packed)
        literal_size = literal_bytes(rows, local_index, bpp)
        total_packed += packed_size
        total_literal += literal_size
        frame_reports.append({
            "frame": name,
            "colors_used": (colors_frame0 if name == "frame0" else colors_frame1),
            "packed_bytes": packed_size,
            "literal_bytes": literal_size,
        })

    return {
        "sprite_id": sprite_id,
        "kind": kind,
        "colors_union": colors_union,
        "bpp": bpp,
        "frames": frame_reports,
        "packed_bytes_total": total_packed,
        "literal_bytes_total": total_literal,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                         help="emit machine-readable JSON instead of a table")
    args = parser.parse_args()

    document = stage_gen.load_json(stage_gen.Path("assets/stages/stages.json"))
    previews, _player_doc, _enemy_doc = stage_gen.load_previews()
    # Reuse the pipeline's own validator so this gate always reflects data
    # that passes the same rules the real generator enforces (3-4 colors,
    # anim_delta legality, etc.) rather than assumptions made here.
    stage_gen.validate(document, previews)

    reports = [build_sprite_report(sprite, previews)
               for sprite in document["sprites"]]

    grand_packed = sum(r["packed_bytes_total"] for r in reports)
    grand_literal = sum(r["literal_bytes_total"] for r in reports)
    by_bpp = {}
    for r in reports:
        by_bpp.setdefault(r["bpp"], []).append(r["sprite_id"])

    summary = {
        "sprite_count": len(reports),
        "frame_count": len(reports) * 2,
        "packed_bytes_total": grand_packed,
        "literal_bytes_total": grand_literal,
        "sprites_by_bpp": {str(k): v for k, v in sorted(by_bpp.items())},
        "sprites": reports,
    }

    if args.json:
        json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return

    print("APS-053 Phase 3R bpp gate -- %d sprites / %d frames" %
          (summary["sprite_count"], summary["frame_count"]))
    print("%-16s %-8s %-4s %6s %6s %6s %6s" % (
        "sprite", "kind", "bpp", "f0", "f1", "packed", "literal"))
    for r in reports:
        f0 = r["frames"][0]["packed_bytes"]
        f1 = r["frames"][1]["packed_bytes"]
        print("%-16s %-8s %-4d %6d %6d %6d %6d" % (
            r["sprite_id"], r["kind"], r["bpp"], f0, f1,
            r["packed_bytes_total"], r["literal_bytes_total"]))
    print("-" * 62)
    print("TOTAL packed=%d literal=%d" % (grand_packed, grand_literal))
    print("by bpp:", summary["sprites_by_bpp"])


if __name__ == "__main__":
    main()
