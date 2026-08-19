#!/usr/bin/env python3
"""APS-053 Phase 2R-2 Gate A: O2/O3/O4 boundary diagnostics.

This script is diagnostic-only.  It does not modify the release ROM source or
the linked production objects.  O2 follows the real _tgi_ioctl call from its
entry to debug_step_out return and samples Suzy/Mikey registers.  O3 fills
both physical framebuffer pages with 0xAA and reads those CPU addresses back
directly.  O4 repeats the same raw-memory flow with the old TGI player path.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUAL_PATH = ROOT / "scripts" / "verify-stage-visuals-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17775
PAGE_SIZE = 160 * 102 // 2
PAGE_C038 = 0xC038
PAGE_E018 = 0xE018
SENTINEL = 0xAA
SCB_SIZE = 23
MAX_SCBS = 21
SCRATCH_SCBS = MAX_SCBS * SCB_SIZE
RAW_CHUNK = 512
GAME_PHASE_STAGE_INTRO = 0
GAME_OFFSET_PLAYER = 2
GAME_OFFSET_BULLETS = 6
GAME_OFFSET_GAME_OVER = 191
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PLANET_OFFSET = 200
GAME_OFFSET_FAR_STAR_OFFSET = 202
GAME_OFFSET_NEAR_STAR_OFFSET = 203
GAME_OFFSET_PHASE_STAGE_INTRO = 210
GAME_STATE_PREFIX_END = 213
GAME_ENEMY_BYTES = 8 * 12
ROI = (72, 52, 96, 76)


def load_visual_module():
    spec = importlib.util.spec_from_file_location("visual_verifier", VISUAL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    return module


def parse_int(value):
    if isinstance(value, int):
        return value
    return int(str(value), 16)


def register_map(payload):
    return {
        row[0]: {"address": row[1], "value": row[2],
                 "int": parse_int(row[2])}
        for row in payload["registers"]
    }


def register_snapshot(visual, request_id):
    suzy_payload = visual.tool("get_suzy_registers", request_id=request_id)
    request_id += 1
    mikey_payload = visual.tool("get_mikey_registers", request_id=request_id)
    request_id += 1
    suzy = register_map(suzy_payload)
    mikey = register_map(mikey_payload)
    names = {
        "SCBNEXT": suzy.get("SCBNEXT"),
        "SPRGO": suzy.get("SPRGO"),
        "SPRSYS": suzy.get("SPRSYS"),
        "VIDBAS": suzy.get("VIDBAS"),
        "DISPADR": mikey.get("DISPADR"),
    }
    return request_id, {
        "readback_available": all(value is not None for value in names.values()),
        "suzy_registers": suzy,
        "mikey_registers": mikey,
        "selected": names,
        "selected_readback": names,
    }


def read_chunks(visual, address, size, request_id):
    parts = []
    offset = 0
    while offset < size:
        count = min(RAW_CHUNK, size - offset)
        parts.append(visual.read_bytes(address + offset, count, request_id))
        request_id += 1
        offset += count
    return request_id, b"".join(parts)


def write_chunks(visual, address, size, value, request_id):
    payload = [value] * RAW_CHUNK
    offset = 0
    while offset < size:
        count = min(RAW_CHUNK, size - offset)
        visual.write_bytes(address + offset, payload[:count], request_id)
        request_id += 1
        offset += count
    return request_id


def raw_page_record(raw, expected_pixels, clear_color, path):
    path.write_bytes(raw)
    changed = sum(byte != SENTINEL for byte in raw)
    unchanged = len(raw) - changed
    high = unpack_pixels(raw, True)
    low = unpack_pixels(raw, False)
    expected = flatten(expected_pixels)
    expected_high = pack_pixels(expected, True)
    expected_low = pack_pixels(expected, False)
    return {
        "cpu_address": "0x%04X" % (PAGE_C038 if "C038" in path.name else PAGE_E018),
        "bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_file": path.name,
        "sentinel": "0x%02X" % SENTINEL,
        "changed_byte_count": changed,
        "unchanged_sentinel_byte_count": unchanged,
        "all_sentinel": changed == 0,
        "clear_color": clear_color,
        "expected_static_pixel_count": sum(value != clear_color for value in expected),
        "high_nibble_first": pixel_metrics(raw, high, expected, clear_color),
        "low_nibble_first": pixel_metrics(raw, low, expected, clear_color),
        "exact_expected_packed_match": {
            "high_nibble_first": raw == expected_high,
            "low_nibble_first": raw == expected_low,
        },
    }


def unpack_pixels(raw, high_first):
    pixels = []
    for byte in raw:
        if high_first:
            pixels.extend([(byte >> 4) & 0x0F, byte & 0x0F])
        else:
            pixels.extend([byte & 0x0F, (byte >> 4) & 0x0F])
    return pixels[:160 * 102]


def pack_pixels(pixels, high_first):
    result = bytearray()
    for index in range(0, len(pixels), 2):
        first = pixels[index]
        second = pixels[index + 1]
        result.append((first << 4 | second) if high_first else
                      (second << 4 | first))
    return bytes(result)


def flatten(rows):
    return [value for row in rows for value in row]


def pixel_metrics(raw, pixels, expected, clear_color):
    nonclear = sum(value != clear_color for value in pixels)
    nonzero = sum(value != 0 for value in pixels)
    changed = sum(value != (SENTINEL & 0x0F) for value in pixels)
    changed_nonclear = sum(
        value != (SENTINEL & 0x0F) and value != clear_color
        for value in pixels
    )
    exact = sum(actual == want for actual, want in zip(pixels, expected))
    return {
        "changed_from_0xAA_pixel_count": changed,
        "changed_non_clear_pixel_count": changed_nonclear,
        "non_clear_pixel_count": nonclear,
        "nonzero_pixel_count": nonzero,
        "exact_pixel_match_count": exact,
        "exact_pixel_match": exact == len(expected),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def roi_metrics(raw, clear_color):
    result = {}
    for label, high_first in (("high_nibble_first", True),
                              ("low_nibble_first", False)):
        pixels = unpack_pixels(raw, high_first)
        x0, y0, x1, y1 = ROI
        values = [pixels[y * 160 + x] for y in range(y0, y1 + 1)
                  for x in range(x0, x1 + 1)]
        result[label] = {
            "changed_from_0xAA_pixel_count": sum(
                value != (SENTINEL & 0x0F) for value in values
            ),
            "non_background_pixel_count": sum(value != clear_color for value in values),
            "nonzero_pixel_count": sum(value != 0 for value in values),
            "sample_pixel_count": len(values),
        }
    return result


def state_injection(visual, game_address, enemy_address, player_x, player_y,
                    request_id):
    visual.write_bytes(game_address + GAME_OFFSET_PLAYER,
                       [player_x, player_y, 8, 6], request_id)
    request_id += 1
    visual.write_bytes(game_address + GAME_OFFSET_BULLETS,
                       [0] * (GAME_OFFSET_GAME_OVER - GAME_OFFSET_BULLETS),
                       request_id)
    request_id += 1
    state = [0] * (GAME_STATE_PREFIX_END - GAME_OFFSET_GAME_OVER + 1)
    state[GAME_OFFSET_STAGE - GAME_OFFSET_GAME_OVER] = 1
    state[GAME_OFFSET_PHASE_STAGE_INTRO - GAME_OFFSET_GAME_OVER] = (
        GAME_PHASE_STAGE_INTRO
    )
    # Keep these explicit in the evidence flow: stage 1, zero scroll, no
    # active environment/object state, and a stable non-dying player.
    state[GAME_OFFSET_PLANET_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    state[GAME_OFFSET_FAR_STAR_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    state[GAME_OFFSET_NEAR_STAR_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    visual.write_bytes(game_address + GAME_OFFSET_GAME_OVER, state, request_id)
    request_id += 1
    visual.write_bytes(enemy_address, [0] * GAME_ENEMY_BYTES, request_id)
    return request_id + 1


def fill_pages(visual, request_id):
    request_id = write_chunks(visual, PAGE_C038, PAGE_SIZE, SENTINEL, request_id)
    request_id = write_chunks(visual, PAGE_E018, PAGE_SIZE, SENTINEL, request_id)
    request_id, c038 = read_chunks(visual, PAGE_C038, PAGE_SIZE, request_id)
    request_id, e018 = read_chunks(visual, PAGE_E018, PAGE_SIZE, request_id)
    return request_id, {
        "value": "0x%02X" % SENTINEL,
        "page_c038_all_sentinel": all(byte == SENTINEL for byte in c038),
        "page_e018_all_sentinel": all(byte == SENTINEL for byte in e018),
        "page_c038_sha256": hashlib.sha256(c038).hexdigest(),
        "page_e018_sha256": hashlib.sha256(e018).hexdigest(),
    }


def read_pages(visual, request_id):
    request_id, c038 = read_chunks(visual, PAGE_C038, PAGE_SIZE, request_id)
    request_id, e018 = read_chunks(visual, PAGE_E018, PAGE_SIZE, request_id)
    return request_id, {"0xC038": c038, "0xE018": e018}


def wait_breakpoint(visual, request_id, description):
    return visual.wait_for_breakpoint(request_id, description)


def cadence_consistency():
    phase_path = ROOT / "evidence" / "APS-053" / "phase-2r-v008.json"
    cadence_path = ROOT / "evidence" / "APS-053" / "cadence-zero-v008.json"
    phase = json.loads(phase_path.read_text(encoding="utf-8"))
    cadence = json.loads(cadence_path.read_text(encoding="utf-8"))
    contract = cadence["scenarios"][0]["phase_runs"][0]["contract_g"]
    rows = []
    for index, run in enumerate(phase["runs"]):
        phase_raw = run["full_0_enemy_raw"]
        cadence_raw = contract["runs"][index]["raw_interval_vblank_counts"]
        rows.append({
            "batch": index + 1,
            "phase_key": "runs[%d].full_0_enemy_raw" % index,
            "cadence_key": "scenarios[0].phase_runs[0].contract_g.runs[%d].raw_interval_vblank_counts" % index,
            "sample_count": len(phase_raw),
            "raw_equal": phase_raw == cadence_raw,
            "computed_median_vblank": statistics.median(phase_raw),
            "computed_maximum_vblank": max(phase_raw),
            "reported_median_vblank": contract["run_medians_vblank"][index],
            "reported_maximum_vblank": contract["run_maxima_vblank"][index],
            "reported_summary_consistent": (
                statistics.median(phase_raw) == contract["run_medians_vblank"][index]
                and max(phase_raw) == contract["run_maxima_vblank"][index]
            ),
        })
    return {
        "source_files": [str(phase_path), str(cadence_path)],
        "measurement_scope": "0-enemy NORMAL, two independent 75-sample batches",
        "rows": rows,
        "raw_and_summary_consistent": all(
            row["raw_equal"] and row["reported_summary_consistent"]
            for row in rows
        ),
        "formula_fields_not_used_as_cadence_summary": [
            "runs[].V-A_plus_V-B_plus_V-C_minus_2V-C_raw",
            "runs[].estimated_median_vblank",
            "runs[].estimated_maximum_vblank",
        ],
    }


def register_evidence(entry, entry_readback, return_readback,
                      chain_head, page_bases):
    entry_selected = entry_readback["selected"]
    return_selected = return_readback["selected"]
    expected = {
        "SCBNEXT": {
            "value": chain_head,
            "semantics": "SCB head pointer at _tgi_ioctl entry",
        },
        "SPRGO": {
            "value": 0,
            "semantics": "not busy after _tgi_ioctl return; write trigger itself is not inferred from readback",
        },
        "SPRSYS": {
            "value": 0,
            "semantics": "sprite engine idle after _tgi_ioctl return",
        },
        "VIDBAS": {
            "value": page_bases,
            "semantics": "one of the two physical framebuffer bases",
        },
        "DISPADR": {
            "value": page_bases,
            "semantics": "one of the two physical framebuffer bases",
        },
    }
    for name, record in expected.items():
        entry_actual = entry_selected.get(name)
        return_actual = return_selected.get(name)
        record["entry_actual"] = None if entry_actual is None else entry_actual["value"]
        record["return_actual"] = None if return_actual is None else return_actual["value"]
        record["readback_available"] = entry_actual is not None and return_actual is not None
        if isinstance(record["value"], list):
            record["entry_expected_match"] = (record["entry_actual"] in record["value"])
            record["return_expected_match"] = (record["return_actual"] in record["value"])
        else:
            record["entry_expected_match"] = (record["entry_actual"] == record["value"])
            record["return_expected_match"] = (record["return_actual"] == record["value"])
    entry["register_contract"] = expected
    entry["readback_available"] = (
        entry_readback["readback_available"]
        and return_readback["readback_available"]
    )
    entry["selected_readback"] = {
        "entry": entry_selected,
        "return": return_selected,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path, default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-053/phase-2r-gate-a-v009.json"))
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")
    visual = load_visual_module()
    game_address = visual.symbol_address(args.symbols, "_game")
    enemy_address = visual.symbol_address(args.symbols, "_game_enemies")
    ioctl_address = visual.symbol_address(args.symbols, "_tgi_ioctl")
    tgi_bar_address = visual.symbol_address(args.symbols, "_tgi_bar")
    sync_address = visual.symbol_address(args.symbols, "_game_display_sync_complete")
    request_address = visual.symbol_address(args.symbols, "_game_display_request")
    scratch_address = visual.symbol_address(args.symbols,
                                            "_title_voice_scratch_buffer")
    assets = visual.load_static_assets() if hasattr(visual, "load_static_assets") else None
    # load_static_assets belongs to the existing static readback verifier, so
    # import it explicitly while keeping this script's MCP flow independent.
    static_spec = importlib.util.spec_from_file_location(
        "static_readback", ROOT / "scripts" / "verify-static-layer-readback-gearlynx.py"
    )
    static_module = importlib.util.module_from_spec(static_spec)
    static_spec.loader.exec_module(static_module)
    assets = static_module.load_static_assets()
    for symbol, entry in assets.items():
        entry["symbol"] = "_" + symbol
        entry["address"] = visual.symbol_address(args.symbols, entry["symbol"])

    process = subprocess.Popen(
        [GEARLYNX] + ([] if args.gui else ["--headless"]) + [
            "--mcp-http", "--mcp-http-port", str(MCP_PORT),
            str(args.rom), str(args.symbols),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    output_dir = args.output.parent
    evidence = {
        "aps": "APS-053",
        "phase": "2R-2",
        "gate": "A",
        "version": "0.53.2",
        "status": "blocked",
        "rom": {"path": str(args.rom),
                "size_bytes": args.rom.stat().st_size,
                "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest()},
        "physical_framebuffers": {
            "page_c038": {"cpu_address": "0xC038", "bytes": PAGE_SIZE},
            "page_e018": {"cpu_address": "0xE018", "bytes": PAGE_SIZE},
        },
        "cadence_consistency": cadence_consistency(),
        "o2_tgi_ioctl": {},
        "o3_raw_memory_sentinel": {},
        "o4_old_tgi_positive_control": {},
    }
    request_id = 1
    try:
        for _ in range(30):
            try:
                visual.call("initialize", {
                    "protocolVersion": "2025-11-25", "capabilities": {},
                    "clientInfo": {"name": "aps053-gate-a", "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")

        request_id = static_module.wait_stable_title(
            visual, game_address, scratch_address + 640 + 6, 3
        )
        # O2/O3 static-only frame: stop at the real pre-draw boundary, inject
        # stage intro with the player off-screen, then sentinel both pages.
        visual.tool("set_breakpoint", {"address": "%04X" % sync_address}, request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_breakpoint(
            visual, request_id + 1, "O2/O3 pre-draw boundary"
        )
        visual.tool("remove_breakpoint", {"address": "%04X" % sync_address}, request_id)
        request_id += 1
        request_id = state_injection(visual, game_address, enemy_address, 250, 250,
                                     request_id)
        request_id, sentinel = fill_pages(visual, request_id)
        evidence["o3_raw_memory_sentinel"]["sentinel_prefill"] = sentinel

        visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_breakpoint(
            visual, request_id + 1, "O2 _tgi_ioctl entry"
        )
        entry_cpu = visual.tool("get_6502_status", request_id=request_id)
        request_id += 1
        request_id, entry_registers = register_snapshot(visual, request_id)
        scratch_raw = visual.read_bytes(scratch_address, SCRATCH_SCBS + 56, request_id)
        request_id += 1
        scbs = static_module.parse_scb_chain(
            scratch_raw[:SCRATCH_SCBS], scratch_address
        )
        expected = static_module.render_scb_chain(
            scbs, assets, scratch_address, scratch_raw[SCRATCH_SCBS:SCRATCH_SCBS + 56]
        )
        chain_head = "0x%04X" % scratch_address
        entry_cpu["chain_identity"] = {
            "scratch_address": chain_head,
            "scb_count": len(scbs),
            "scb_chain_terminated": scbs[-1]["next"] == 0,
            "fastcall_candidates": {
                "AX_little_endian": "0x%04X" % (int(entry_cpu["A"], 16) |
                                                   (int(entry_cpu["X"], 16) << 8)),
                "XA_little_endian": "0x%04X" % (int(entry_cpu["X"], 16) |
                                                   (int(entry_cpu["A"], 16) << 8)),
            },
            "pointer_match_to_scratch": False,
        }
        entry_cpu["chain_identity"]["pointer_match_to_scratch"] = any(
            value == chain_head
            for value in entry_cpu["chain_identity"]["fastcall_candidates"].values()
        )
        visual.tool("debug_step_out", request_id=request_id)
        request_id += 1
        visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address}, request_id)
        request_id += 1
        return_cpu = visual.tool("get_6502_status", request_id=request_id)
        request_id += 1
        request_id, return_registers = register_snapshot(visual, request_id)
        request_id, immediate_pages = read_pages(visual, request_id)
        o2 = {
            "entry_breakpoint": "0x%04X" % ioctl_address,
            "entry_cpu": entry_cpu,
            "return_cpu": return_cpu,
            "entry_pc": entry_cpu["PC"],
            "return_pc": return_cpu["PC"],
            "entry_to_return_method": "debug_step_out (RTS/return boundary)",
            "scb_chain": scbs,
            "register_readback_at_entry": entry_registers,
            "register_readback_at_return": return_registers,
        }
        register_evidence(o2, entry_registers, return_registers, chain_head,
                          ["0xC038", "0xE018"])
        evidence["o2_tgi_ioctl"] = o2

        immediate_records = {}
        for page_name, raw in immediate_pages.items():
            path = output_dir / ("phase-2r-v009-o3-immediate-%s.bin" % page_name[2:])
            immediate_records[page_name] = raw_page_record(
                raw, expected, scbs[0]["penpal"][1], path
            )
        evidence["o3_raw_memory_sentinel"]["after_ioctl_return"] = immediate_records

        # The next sync boundary is after the production tgi_busy wait.  This
        # separates an asynchronous Suzy completion from the immediate return
        # readback without using screenshot/framebuffer APIs.
        visual.tool("set_breakpoint", {"address": "%04X" % sync_address}, request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_breakpoint(
            visual, request_id + 1, "O3 post-tgi_busy sync boundary"
        )
        request_id += 1
        request_id, settled_pages = read_pages(visual, request_id)
        settled_records = {}
        for page_name, raw in settled_pages.items():
            path = output_dir / ("phase-2r-v009-o3-settled-%s.bin" % page_name[2:])
            settled_records[page_name] = raw_page_record(
                raw, expected, scbs[0]["penpal"][1], path
            )
        evidence["o3_raw_memory_sentinel"]["after_tgi_busy_sync"] = settled_records
        evidence["o3_raw_memory_sentinel"]["scb_context"] = {
            "clear_color": scbs[0]["penpal"][1],
            "scb_count": len(scbs),
            "expected_static_pixel_count": sum(
                value != scbs[0]["penpal"][1] for value in flatten(expected)
            ),
            "expected_static_index_sha256": hashlib.sha256(
                bytes(flatten(expected))
            ).hexdigest(),
            "physical_page_mapping": {
                "VIDBAS_or_raw_page": "both CPU addresses read directly; register value recorded in O2",
                "C038": "raw CPU read at 0xC038",
                "E018": "raw CPU read at 0xE018",
            },
        }
        visual.tool("remove_breakpoint", {"address": "%04X" % sync_address}, request_id)
        request_id += 1

        # O4: same stage-intro/static setup, but player at (80,60).  No
        # environment objects are active, so the first _tgi_bar is the old
        # TGI player path.  The raw read is taken at display-request entry,
        # after all player bars have returned and before the display swap.
        request_id = state_injection(visual, game_address, enemy_address, 80, 60,
                                     request_id)
        request_id, o4_sentinel = fill_pages(visual, request_id)
        visual.tool("set_breakpoint", {"address": "%04X" % tgi_bar_address}, request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_breakpoint(
            visual, request_id + 1, "O4 old TGI _tgi_bar entry"
        )
        old_tgi_cpu = visual.tool("get_6502_status", request_id=request_id)
        request_id += 1
        request_id, old_tgi_registers = register_snapshot(visual, request_id)
        request_id, old_tgi_stack = (request_id,
                                     visual.tool("get_call_stack", request_id=request_id))
        request_id += 1
        visual.tool("debug_step_out", request_id=request_id)
        request_id += 1
        visual.tool("remove_breakpoint", {"address": "%04X" % tgi_bar_address}, request_id)
        request_id += 1
        visual.tool("set_breakpoint", {"address": "%04X" % request_address}, request_id)
        request_id += 1
        visual.tool("debug_continue", request_id=request_id)
        request_id = wait_breakpoint(
            visual, request_id + 1, "O4 display-request after old TGI player"
        )
        request_id += 1
        request_id, o4_pages = read_pages(visual, request_id)
        o4_records = {}
        for page_name, raw in o4_pages.items():
            path = output_dir / ("phase-2r-v009-o4-%s.bin" % page_name[2:])
            record = raw_page_record(raw, expected, scbs[0]["penpal"][1], path)
            record["player_roi"] = roi_metrics(raw, scbs[0]["penpal"][1])
            record["sentinel_prefill"] = o4_sentinel
            o4_records[page_name] = record
        evidence["o4_old_tgi_positive_control"] = {
            "old_tgi_entry_breakpoint": "0x%04X" % tgi_bar_address,
            "old_tgi_entry_cpu": old_tgi_cpu,
            "old_tgi_entry_registers": old_tgi_registers,
            "old_tgi_call_stack": old_tgi_stack,
            "display_request_boundary": "0x%04X" % request_address,
            "fixture": {
                "stage": 1,
                "phase": "GAME_PHASE_STAGE_INTRO",
                "player_rect": [80, 60, 8, 6],
                "environment_objects": "inactive",
                "roi": {"x0": ROI[0], "y0": ROI[1], "x1": ROI[2], "y1": ROI[3]},
            },
            "pages": o4_records,
            "positive_control": any(
                record["player_roi"]["high_nibble_first"]["changed_from_0xAA_pixel_count"] > 0
                or record["player_roi"]["low_nibble_first"]["changed_from_0xAA_pixel_count"] > 0
                for record in o4_records.values()
            ),
        }
        settled_changed = [
            record["changed_byte_count"]
            for record in settled_records.values()
        ]
        settled_static_pixels = [
            max(
                record["high_nibble_first"]["changed_non_clear_pixel_count"],
                record["low_nibble_first"]["changed_non_clear_pixel_count"],
            )
            for record in settled_records.values()
        ]
        static_missing = max(settled_static_pixels) == 0
        clear_observed = max(settled_changed) > 0
        evidence["diagnosis"] = {
            "o2_suzy_boundary": {
                "ioctl_entry_reached": True,
                "fastcall_pointer_matches_scb_head": (
                    entry_cpu["chain_identity"]["pointer_match_to_scratch"]
                ),
                "scb_chain_count": len(scbs),
                "scb_chain_terminated": scbs[-1]["next"] == 0,
                "return_register_readback_available": (
                    return_registers["readback_available"]
                ),
            },
            "o3_raw_memory": {
                "clear_write_observed": clear_observed,
                "static_pixel_write_observed": not static_missing,
                "settled_changed_byte_counts": settled_changed,
                "settled_changed_non_clear_pixel_counts": settled_static_pixels,
                "expected_static_pixel_count": sum(
                    value != scbs[0]["penpal"][1] for value in flatten(expected)
                ),
            },
            "o4_raw_memory": {
                "old_tgi_entry_reached": (
                    old_tgi_cpu["PC"].upper() == "%04X" % tgi_bar_address
                ),
                "positive_control": evidence[
                    "o4_old_tgi_positive_control"
                ]["positive_control"],
            },
            "cause_classification": (
                "O3 clear-only/static-nonrender: generated packed data or "
                "SCB chain continuation/format candidate; O4 raw-memory "
                "positive control passes, so debugger/raw physical-page "
                "observation is not the primary blocker"
                if clear_observed and static_missing and
                evidence["o4_old_tgi_positive_control"]["positive_control"]
                else "O2-O4 did not uniquely isolate a cause"
            ),
            "unresolved_boundary": (
                "SCB non-clear asset data interpretation versus chain traversal "
                "is not separated by O2-O4; O5 minimal chain/Fable5 review required"
            ),
        }
        evidence["gate_a_acceptance"] = {
            "accepted": False,
            "reason": "O3 observed clear-only output and v008 full 0-enemy cadence remained 115-117 VBlank, above the 3-VBlank Gate A budget",
            "cadence_vblank_summary": {
                "median": [116, 115],
                "maximum": [117, 117],
                "within_gate_budget": False,
            },
        }
        # The diagnostic itself completed; Gate A acceptance remains false by
        # design until the unresolved Suzy non-clear path is resolved.
        evidence["status"] = "done"
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print("%s: %s" % (evidence["status"].upper(), args.output))
        return 0 if evidence["status"] == "done" else 1
    except Exception as error:
        evidence["error"] = str(error)
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print("BLOCKED: %s" % error, file=sys.stderr)
        return 2
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    sys.exit(main())
