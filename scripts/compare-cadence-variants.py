#!/usr/bin/env python3
"""Combine APS-053 V-A/V-B/V-C cadence evidence."""

import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cadence(document):
    return document["scenarios"][0]["phase_runs"][0]["contract_g"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", type=Path, required=True)
    parser.add_argument("--v-a", type=Path, required=True)
    parser.add_argument("--v-b", type=Path, required=True)
    parser.add_argument("--v-c", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    documents = {
        "full_0_enemy": load(args.full),
        "V-A_static_suzy": load(args.v_a),
        "V-B_player_tgi": load(args.v_b),
        "V-C_display_sync": load(args.v_c),
    }
    measures = {name: cadence(document)
                for name, document in documents.items()}
    runs = []
    for batch in range(2):
        a = measures["V-A_static_suzy"]["runs"][batch][
            "raw_interval_vblank_counts"]
        b = measures["V-B_player_tgi"]["runs"][batch][
            "raw_interval_vblank_counts"]
        c = measures["V-C_display_sync"]["runs"][batch][
            "raw_interval_vblank_counts"]
        full = measures["full_0_enemy"]["runs"][batch][
            "raw_interval_vblank_counts"]
        estimate = [x + y - z for x, y, z in zip(a, b, c)]
        runs.append({
            "batch": batch + 1,
            "full_0_enemy_raw": full,
            "V-A_raw": a,
            "V-B_raw": b,
            "V-C_raw": c,
            "V-A_plus_V-B_plus_V-C_minus_2V-C_raw": estimate,
            "estimated_median_vblank": sorted(estimate)[len(estimate) // 2],
            "estimated_maximum_vblank": max(estimate),
            "full_median_vblank": measures["full_0_enemy"]["runs"][batch][
                "median_vblank_interval"],
            "full_maximum_vblank": measures["full_0_enemy"]["runs"][batch][
                "maximum_vblank_interval"],
        })

    roms = {}
    for name, document in documents.items():
        rom = document["rom"]
        roms[name] = {
            "path": rom["path"],
            "sha256": rom["sha256"],
            "size_bytes": rom["size_bytes"],
            "layout": rom["layout"],
            "fixture_state_valid": cadence(document)["fixture_state"]["valid"],
        }
    release = documents["full_0_enemy"]["normal_rom"]
    evidence = {
        "aps": "APS-053",
        "phase": "2R-2",
        "method": {
            "fixture": "0 enemy NORMAL, phase/boss/enemy state sampled for all 75 intervals in two independent batches",
            "formula": "V-A + V-B + V-C - 2*V-C = V-A + V-B - V-C",
            "formula_scope": "per-batch raw Timer 2 VBlank interval sample",
            "contract_limit_vblank": 1.05,
        },
        "release_rom": release,
        "variant_roms": roms,
        "runs": runs,
        "all_fixture_states_valid": all(
            item["fixture_state_valid"] for item in roms.values()
        ),
        "release_sha_unchanged_in_variants": all(
            release["sha256"] != rom["sha256"]
            for name, rom in roms.items() if name != "full_0_enemy"
        ),
        "formula_matches_full_median": all(
            run["estimated_median_vblank"] == run["full_median_vblank"]
            for run in runs
        ),
        "formula_matches_full_maximum": all(
            run["estimated_maximum_vblank"] == run["full_maximum_vblank"]
            for run in runs
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    for run in runs:
        print("batch=%d full=%d/%d estimate=%d/%d" % (
            run["batch"], run["full_median_vblank"],
            run["full_maximum_vblank"], run["estimated_median_vblank"],
            run["estimated_maximum_vblank"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
