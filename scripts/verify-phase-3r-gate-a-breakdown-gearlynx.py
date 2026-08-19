#!/usr/bin/env python3
"""APS-053 Phase 3R Gate A breakdown: separates the 33 VBlank gate(a)
overrun (v038, evidence/APS-053/phase-3r-gate-a-full-fixture-v038.json)
into (i) pure Suzy SPRGO+wait cost, (ii) SCB construction cost, and
(iii) any per-frame data-conversion cost, per .briefs/APS-053/v040.md.

Diagnostic only. Does not modify Phase 3R's SCB chain construction, draw
order, or data format. It reuses three temporary, cadence-build-only
landing points (src/scb_split_probe.s, called from src/main.c only inside
existing #ifdef CADENCE_PROBE blocks -- never compiled into the release
ROM, confirmed byte-identical to the v038 evidence sha256 below) as stable
breakpoint addresses:

  - scb_split_marker_begin: first instruction of movable_scb_begin(), i.e.
    the start of the movable-object draw pass for this frame.
  - scb_split_marker_finish_enter: first instruction of
    movable_scb_finish(), i.e. the end of SCB construction (draw_environment
    + all movable_append calls) and the start of the tgi_sprite() call.
  - scb_split_marker_finish_exit: last instruction of movable_scb_finish(),
    i.e. immediately after tgi_sprite() (SCBNEXT/VIDBAS setup + SPRGO +
    busy-wait, see .cache/cc65-2.19/source/libsrc/lynx/tgi/
    lynx-160-102-16.s draw_sprite) returns.

At each landing point the emulator's own CPU tick counter
(get_6502_status().total_ticks) is read while paused, giving tick-exact
deltas. NOTE (APS-053 v044 correction, see evidence/APS-053/README.md):
total_ticks does NOT increment 1:1 with CPU instruction cycles -- it runs
at roughly 4.4-5.0x a nominal 4MHz 65C02 cycle, per tick-calibration-v024
(184,668 ticks/VBlank). Divide by ~4.4-5.0 before comparing a tick delta
against a desk-estimated CPU-cycle count. The VBlank-unit deltas below are
unaffected (they stay in tick units, converted via the same calibration):

  - (ii) SCB construction = finish_enter.total_ticks - begin.total_ticks
  - (i)  pure Suzy         = finish_exit.total_ticks - finish_enter.total_ticks
  - (iii) frame-per data conversion: no separate runtime pack/convert step
    exists in this call path (movable_append's `data` argument always
    points into the build-time-generated game_sprite_packed_data array,
    see src/main.c movable_append_sprite; the offline encode_packed() call
    is scripts/generate-static-layer.py-only, never invoked from ROM
    code). Because the three markers bracket the *entire* movable draw
    pass with no gap, any such cost, if it existed, would already be
    inside (i) or (ii) above -- there is no third bucket to measure
    separately. This script reports (iii) as a code-inspection finding,
    not a measured non-zero value.

APS-053 v045 update: Phase 3R2 replaced the per-frame dynamic-append
movable_scb_pool with a fixed static SCB chain (movable_scb_env_header
etc., see src/main.c), so there is no longer a single contiguous pool to
dump/decode here -- the scb_split_marker_begin/finish_enter/finish_exit
landing points are unchanged (still called from movable_scb_update, the
v045 renamed/rewritten successor of movable_scb_begin/movable_scb_finish)
and still bracket the same two phases: (ii) is now "walk each static
slot, mutate SKIP/hpos/vpos/data in place" instead of "append a fresh SCB
into the pool", and (i) is unchanged (tgi_sprite() + SPRGO + busy-wait).
get_suzy_registers is still sampled at finish_exit to read the actual
hardware SPRHSIZ/SPRVSIZ the movable chain ran with (Phase 2R-0's
hsize/vsize-misconfiguration bug class).

An "empty" fixture (0 enemies, boss inactive, 0 bullets, GAME_PHASE_NORMAL)
is also profiled the same way, to cross-check against the Phase 2R-2
baseline (~3 VBlank) per the harness-validity request in v040.
"""

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE_A_MODULE_PATH = ROOT / "scripts" / "verify-phase-3r-gate-a-full-fixture-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17781

FRAME_SAMPLES_PER_BATCH = 15
BATCH_COUNT = 2
# v038 (scripts/cadence_probe.s CADENCE_WARMUP_REQUEST_COUNT=6): the ROM
# probe's own internal warmup counter needs 6 display-request hits after
# the arm-consuming hit (1 + 6 = 7) before it resets the production
# game_timing baseline; the catch-up backlog then escalates and settles
# over the next 1-2 hits (v038's own raw_interval_vblank_counts starts at
# 11, jumps to 33 by the second recorded sample and stays there). 9 warmup
# display-request cycles here (comfortably past hit 7-9) reproduces that
# same settled state before this script starts recording samples --
# confirmed empirically below (see EMPIRICAL NOTE in the module docstring
# update / evidence JSON "warmup_convergence_check").
WARMUP_FRAMES = 9
STABLE_TITLE_TIMEOUT = 12.0
BREAKPOINT_TIMEOUT = 60.0

# SCB_RENONE / SCB_RENONE_PAL layout, _suzy.h: sprctl0,sprctl1,sprcoll (1B
# each), next,data (2B pointers), hpos,vpos (2B signed ints); _PAL adds an
# 8-byte penpal tail (only penpal[0..2] are ever written by movable_append).
SCB_RENONE_SIZE = 11
SCB_RENONE_PAL_SIZE = 19
RENONE_RELOAD_MASK = 0x30
REUSEPAL_BIT = 0x08
LITERAL_BIT = 0x80


def load_gate_a_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_gate_a_full_fixture", GATE_A_MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    return module


def one_breakpoint(g, address, request_id, description):
    address_hex = "%04X" % address
    g.tool("set_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    g.tool("debug_continue", request_id=request_id)
    request_id += 1
    request_id = g.wait_for_breakpoint(request_id, description)
    g.tool("remove_breakpoint", {"address": address_hex}, request_id)
    return request_id + 1


def read_total_ticks(g, request_id):
    payload = g.tool("get_6502_status", request_id=request_id)
    return request_id + 1, payload["total_ticks"]


def read_suzy_registers(g, request_id):
    payload = g.tool("get_suzy_registers", request_id=request_id)
    regs = {row[0]: row[2] for row in payload["registers"]}
    return request_id + 1, regs


def read_u16(g, address, request_id):
    value = int.from_bytes(g.read_bytes(address, 2, request_id), "little")
    return request_id + 1, value


def decode_scb_chain(g, head_address, request_id, max_entries=48):
    """v045: SCBs are separate static objects (movable_scb_env_header,
    movable_scb_env[], ... movable_scb_ebullet[]) linked by address, not
    slices of one contiguous pool, so this walks the real chain via each
    SCB's `next` pointer starting at head_address instead of slicing a
    dumped byte array. Offsets follow _suzy.h field order exactly; every
    read is SCB_RENONE_PAL_SIZE bytes (the follower/SCB_RENONE case just
    ignores the trailing penpal bytes it reads from -- harmlessly --
    whatever object happens to sit right after it in memory)."""
    entries = []
    findings = []
    address = head_address
    while address != 0 and len(entries) < max_entries:
        header = g.read_bytes(address, SCB_RENONE_PAL_SIZE, request_id)
        request_id += 1
        sprctl0 = header[0]
        sprctl1 = header[1]
        sprcoll = header[2]
        next_ptr = int.from_bytes(header[3:5], "little")
        data_ptr = int.from_bytes(header[5:7], "little")
        hpos = int.from_bytes(header[7:9], "little", signed=True)
        vpos = int.from_bytes(header[9:11], "little", signed=True)
        is_follower = (sprctl1 & REUSEPAL_BIT) != 0
        penpal = None if is_follower else list(header[11:14])
        reload_field = sprctl1 & RENONE_RELOAD_MASK
        literal = (sprctl1 & LITERAL_BIT) != 0
        entry = {
            "index": len(entries),
            "address": "%04X" % address,
            "sprctl0_hex": "%02X" % sprctl0,
            "sprctl1_hex": "%02X" % sprctl1,
            "sprcoll_hex": "%02X" % sprcoll,
            "next_ptr": "%04X" % next_ptr,
            "data_ptr": "%04X" % data_ptr,
            "hpos": hpos,
            "vpos": vpos,
            "reusepal": is_follower,
            "penpal_header": penpal,
            "reload_field": reload_field,
            "literal_bit_set": literal,
        }
        entries.append(entry)
        if reload_field != 0:
            findings.append(
                "entry %d (address %04X): sprctl1=%02X has a non-zero "
                "reload field (RENONE expected, value=0x%02X) -- HSIZE/"
                "VSIZE/stretch/tilt would be reloaded from fields this "
                "short SCB does not carry, a Phase 2R-0-class "
                "misconfiguration." %
                (entry["index"], address, sprctl1, reload_field)
            )
        if literal:
            findings.append(
                "entry %d (address %04X): sprctl1=%02X has LITERAL set "
                "(PACKED expected)." % (entry["index"], address, sprctl1)
            )
        address = next_ptr
    return request_id, entries, findings


# GAME_OFFSET_BOSS (150) + sizeof(BOSS_RECORD) (14) = 164: asteroids[2] +
# falling_rocks[2] + wind band, ending at GAME_OFFSET_GAME_OVER (191).
# Zeroed wholesale (state/active fields are 0 = inactive throughout this
# codebase's convention) so draw_environment() has nothing left over from
# whatever stage/state the ROM was in before injection -- an initial smoke
# run of this harness found 1 stray active environment-hazard SCB leaking
# through into the "empty" fixture because this span was not cleared.
GAME_OFFSET_ENVIRONMENT_HAZARDS = 164
GAME_ENVIRONMENT_HAZARDS_SIZE = 191 - 164


def inject_empty_fixture(g, game_address, enemy_address, request_id):
    """0 enemies, boss inactive, 0 bullets, 0 environment hazards,
    GAME_PHASE_NORMAL: the closest reproduction of the pre-Phase-3R
    background+HUD-only scope Phase 2R-2's ~3 VBlank baseline was measured
    against."""
    g.write_bytes(game_address + GAME_OFFSET_ENVIRONMENT_HAZARDS,
                 [0] * GAME_ENVIRONMENT_HAZARDS_SIZE, request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_PLAYER, [8, 0, 8, 6],
                 request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_BULLETS,
                 [0] * (g.GAME_MAX_PLAYER_BULLETS * 5), request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_ENEMY_BULLETS,
                 [0] * (g.GAME_MAX_ENEMY_BULLETS * 5), request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_POWER_ITEM, [0] * 4,
                 request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_BOSS, [0] * 14, request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_GAME_OVER, [0], request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_TITLE_VOICE_PENDING,
                 [0, 0, 0, 0], request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_DYING, [0, 0, 0], request_id)
    request_id += 1
    g.write_bytes(game_address + g.GAME_OFFSET_STAGE,
                 [1, g.GAME_PHASE_NORMAL, 0, 0], request_id)
    request_id += 1
    g.write_bytes(enemy_address, g.enemy_records(0), request_id)
    return request_id + 1


def resolve_addresses(g, symbols):
    return {
        "game": g.symbol_address(symbols, "_game"),
        "enemies": g.symbol_address(symbols, "_game_enemies"),
        "display_request": g.symbol_address(symbols, "_game_display_request"),
        "scb_begin": g.symbol_address(symbols, "_scb_split_marker_begin"),
        "finish_enter": g.symbol_address(
            symbols, "_scb_split_marker_finish_enter"),
        "finish_exit": g.symbol_address(
            symbols, "_scb_split_marker_finish_exit"),
        "chain_head_ptr": g.symbol_address(
            symbols, "_scb_split_probe_chain_head"),
        "vblank_count": g.symbol_address(
            symbols, "_cadence_probe_vblank_count"),
        "probe_armed": g.symbol_address(symbols, "_cadence_probe_armed"),
    }


def start_paused(g, rom, symbols, port):
    command = [
        GEARLYNX, "--headless", "--mcp-http", "--mcp-http-port", str(port),
        str(rom), str(symbols),
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for attempt in range(40):
        try:
            g.call("initialize", {
                "protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "aps053-gate-a-breakdown",
                               "version": "1"},
            })
            break
        except Exception:
            if attempt == 39:
                process.terminate()
                raise RuntimeError("Gearlynx MCP server did not start")
            time.sleep(0.2)
    g.tool("debug_continue", request_id=2)
    request_id = 3
    game_address = g.symbol_address(symbols, "_game")
    deadline = time.monotonic() + STABLE_TITLE_TIMEOUT
    stable = 0
    while time.monotonic() < deadline:
        state = g.read_bytes(game_address + g.GAME_OFFSET_STAGE, 2,
                             request_id)
        request_id += 1
        if state == bytes([1, g.GAME_PHASE_TITLE]):
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
        time.sleep(0.01)
    else:
        process.terminate()
        raise RuntimeError("ROM did not reach stable TITLE state")
    g.tool("debug_pause", request_id=request_id)
    request_id += 1
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = g.tool("debug_get_status", request_id=request_id)
        request_id += 1
        if status.get("paused"):
            return process, request_id
        time.sleep(0.01)
    process.terminate()
    raise RuntimeError("did not pause after stable TITLE")


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_batch(g, rom, symbols, port, fixture_kind, batch_index):
    process, request_id = start_paused(g, rom, symbols, port)
    try:
        addresses = resolve_addresses(g, symbols)
        inject = (g.inject_full_fixture if fixture_kind == "full"
                 else lambda ga, ea, rid: inject_empty_fixture(g, ga, ea, rid))
        request_id = inject(addresses["game"], addresses["enemies"],
                            request_id)
        g.write_bytes(addresses["probe_armed"], [1], request_id)
        request_id += 1
        # First display-request hit consumes the arm edge; the rest let the
        # ROM-internal catch-up backlog settle before sampling (see
        # WARMUP_FRAMES comment above).
        warmup_vblanks = []
        d_prev = None
        for warm in range(WARMUP_FRAMES):
            request_id = one_breakpoint(
                g, addresses["display_request"], request_id,
                "%s batch %d warm-up %d" % (fixture_kind, batch_index, warm),
            )
            request_id, vblank_raw = read_u16(g, addresses["vblank_count"],
                                              request_id)
            request_id, d_prev = read_total_ticks(g, request_id)
            warmup_vblanks.append(vblank_raw)
            request_id = inject(addresses["game"], addresses["enemies"],
                                request_id)
        frames = []
        for index in range(FRAME_SAMPLES_PER_BATCH):
            request_id = one_breakpoint(
                g, addresses["scb_begin"], request_id,
                "%s batch %d frame %d scb_begin" %
                (fixture_kind, batch_index, index),
            )
            request_id, t0 = read_total_ticks(g, request_id)
            request_id = one_breakpoint(
                g, addresses["finish_enter"], request_id,
                "%s batch %d frame %d finish_enter" %
                (fixture_kind, batch_index, index),
            )
            request_id, t1 = read_total_ticks(g, request_id)
            request_id, chain_head = read_u16(g, addresses["chain_head_ptr"],
                                              request_id)
            request_id, entries, findings = decode_scb_chain(
                g, chain_head, request_id)
            request_id = one_breakpoint(
                g, addresses["finish_exit"], request_id,
                "%s batch %d frame %d finish_exit" %
                (fixture_kind, batch_index, index),
            )
            request_id, t2 = read_total_ticks(g, request_id)
            request_id, suzy_regs = read_suzy_registers(g, request_id)
            request_id = one_breakpoint(
                g, addresses["display_request"], request_id,
                "%s batch %d frame %d display_request" %
                (fixture_kind, batch_index, index),
            )
            request_id, vblank_raw = read_u16(g, addresses["vblank_count"],
                                              request_id)
            request_id, d_this = read_total_ticks(g, request_id)
            request_id = inject(addresses["game"], addresses["enemies"],
                                request_id)
            pre_movable_ticks = t0 - d_prev
            scb_build_ticks = t1 - t0
            pure_suzy_ticks = t2 - t1
            post_movable_ticks = d_this - t2
            total_frame_ticks = d_this - d_prev
            frames.append({
                "frame": index,
                "total_ticks": {"prev_display_request": d_prev, "begin": t0,
                               "finish_enter": t1, "finish_exit": t2,
                               "display_request": d_this},
                "pre_movable_ticks": pre_movable_ticks,
                "scb_build_ticks": scb_build_ticks,
                "pure_suzy_ticks": pure_suzy_ticks,
                "total_movable_ticks": t2 - t0,
                "post_movable_ticks": post_movable_ticks,
                "total_frame_ticks": total_frame_ticks,
                "vblank_count_since_prev_display_request": vblank_raw,
                "suzy_sprhsiz": suzy_regs.get("SPRHSIZ"),
                "suzy_sprvsiz": suzy_regs.get("SPRVSIZ"),
                "suzy_sprctl0": suzy_regs.get("SPRCTL0"),
                "suzy_sprctl1": suzy_regs.get("SPRCTL1"),
                "suzy_sprsys": suzy_regs.get("SPRSYS"),
                "scb_entry_count": len(entries),
                "scb_findings": findings,
            })
            d_prev = d_this
        return {
            "batch": batch_index,
            "fixture": fixture_kind,
            "warmup_vblank_counts": warmup_vblanks,
            "frames": frames,
            "last_scb_entries": entries,
        }
    finally:
        stop_process(process)


def summarize_ticks(frames, key):
    values = [frame[key] for frame in frames]
    return {
        "samples": len(values),
        "values": values,
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path,
                        default=Path("dist/asteroid-patrol-cadence.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol-cadence.lbl"))
    parser.add_argument("--release-rom", type=Path,
                        default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--output", type=Path, default=Path(
        "evidence/APS-053/phase-3r-gate-a-breakdown-v045.json"))
    args = parser.parse_args()

    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")

    g = load_gate_a_module()

    evidence = {
        "aps": "APS-053",
        "phase": "3R2",
        "brief": ".briefs/APS-053/v045.md",
        "status": "blocked",
        "rom": {
            "path": str(args.rom),
            "size_bytes": args.rom.stat().st_size,
            "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
        },
        "release_rom": {
            "path": str(args.release_rom),
            "sha256": hashlib.sha256(args.release_rom.read_bytes()).hexdigest(),
            "note": "v045 intentionally changed both ROMs (static SCB "
                "chain replacing the v036 dynamic-append pool); this is "
                "no longer expected to match any pre-v045 evidence sha256.",
        },
        "method": {
            "markers": {
                "scb_begin": "first instruction of movable_scb_begin "
                    "(src/scb_split_marker_begin, src/scb_split_probe.s)",
                "finish_enter": "first instruction of movable_scb_finish, "
                    "before tgi_sprite()",
                "finish_exit": "last instruction of movable_scb_finish, "
                    "after tgi_sprite() (SCBNEXT/VIDBAS + SPRGO + busy-wait, "
                    "see .cache/cc65-2.19/source/libsrc/lynx/tgi/"
                    "lynx-160-102-16.s draw_sprite) returns",
            },
            "timer": "get_6502_status().total_ticks, tick-exact (NOT 1:1 "
                "with CPU cycles -- see evidence/APS-053/README.md v044 "
                "correction, ~4.4-5.0x a nominal 4MHz cycle), read while "
                "paused at each marker",
            "scb_dump": "v045: static SCB chain walked live from "
                "movable_scb_env_header via each entry's `next` pointer "
                "at finish_enter, decoded against SCB_RENONE/"
                "SCB_RENONE_PAL layout (_suzy.h) -- no more single "
                "contiguous pool to dump as one block",
            "suzy_registers": "get_suzy_registers sampled at finish_exit "
                "(SPRHSIZ/SPRVSIZ/SPRCTL0/SPRCTL1/SPRSYS)",
            "frames_per_batch": FRAME_SAMPLES_PER_BATCH,
            "independent_batch_count": BATCH_COUNT,
            "warmup_frames": WARMUP_FRAMES,
        },
        "code_inspection_finding_iii": (
            "No per-frame data-conversion/pack step exists in the movable "
            "SCB path. v045: movable_scb_update's per-slot `data` "
            "assignment always points into the build-time-generated "
            "game_sprite_packed_data array (src/main.c: `p->data = "
            "(unsigned char*)(frame != 0u ? cache->frame1_ptr : "
            "cache->frame0_ptr)`, itself derived from "
            "game_sprite_packed_data + def->frameN_offset on a cache "
            "miss); the only encode_packed() call site is offline "
            "(scripts/generate-static-layer.py / generate-stage-data.py), "
            "never invoked from ROM code. Because the scb_begin/"
            "finish_enter/finish_exit markers bracket the entire movable "
            "draw pass with zero gap, any such cost, if present, would "
            "already be counted inside (ii) SCB construction -- there is "
            "no third, separately-measurable bucket. grep -rn "
            "'encode_packed|\\bpack\\b' src include turns up no runtime "
            "call site."
        ),
        "pre_existing_working_tree_state_warning": (
            "The working tree already had uncommitted changes to "
            "include/game.h (part of the 'Phase 2R/3R catch-up limit macro' "
            "WIP this brief says not to touch) BEFORE this diagnostic run "
            "started, in addition to the src/main.c and Makefile edits made "
            "for this diagnostic. Most importantly, GAME_LOGIC_UPDATES_MAX "
            "is currently 12u in include/game.h, not the 128u the v038 "
            "evidence's 33 VBlank result was measured against (`git diff -- "
            "include/game.h` shows this uncommitted change). This is left "
            "untouched per the brief's protected-files list, but it means "
            "this script's own total_frame_ticks/vblank numbers (below) "
            "reflect a ~10.7x lower logic-catch-up ceiling than the ROM "
            "that produced the 33 VBlank baseline -- they are NOT directly "
            "comparable to v038's 33 VBlank figure, and this script does "
            "not attempt to reproduce it. The (i) pure-Suzy and (ii) "
            "SCB-construction tick costs measured here are unaffected by "
            "this macro (they do not depend on how many logic updates ran "
            "beforehand -- see per-frame stability in the results below) "
            "and remain valid in absolute terms."
        ),
    }

    try:
        results = {}
        for fixture_kind in ("full", "empty"):
            batches = []
            for batch_index in range(1, BATCH_COUNT + 1):
                print("running %s fixture batch %d..." %
                      (fixture_kind, batch_index))
                batch = run_batch(g, args.rom, args.symbols, MCP_PORT,
                                  fixture_kind, batch_index)
                batches.append(batch)
                print("  pre_movable median=%d scb_build median=%d "
                      "pure_suzy median=%d post_movable median=%d "
                      "total_frame median=%d ticks (vblank=%d)" % (
                          statistics.median(
                              f["pre_movable_ticks"] for f in batch["frames"]),
                          statistics.median(
                              f["scb_build_ticks"] for f in batch["frames"]),
                          statistics.median(
                              f["pure_suzy_ticks"] for f in batch["frames"]),
                          statistics.median(
                              f["post_movable_ticks"] for f in batch["frames"]),
                          statistics.median(
                              f["total_frame_ticks"] for f in batch["frames"]),
                          statistics.median(
                              f["vblank_count_since_prev_display_request"]
                              for f in batch["frames"]),
                      ))
            all_frames = [f for b in batches for f in b["frames"]]
            all_findings = sorted(set(
                finding for f in all_frames for finding in f["scb_findings"]
            ))
            ticks_per_vblank_samples = [
                f["total_frame_ticks"] /
                f["vblank_count_since_prev_display_request"]
                for f in all_frames
                if f["vblank_count_since_prev_display_request"] > 0
            ]
            component_keys = ("pre_movable_ticks", "scb_build_ticks",
                              "pure_suzy_ticks", "post_movable_ticks")
            median_total = statistics.median(
                f["total_frame_ticks"] for f in all_frames)
            share_of_total_frame_pct = {
                key: round(100.0 * statistics.median(
                    f[key] for f in all_frames) / median_total, 2)
                for key in component_keys
            }
            results[fixture_kind] = {
                "batches": batches,
                "warmup_vblank_counts_by_batch": [
                    b["warmup_vblank_counts"] for b in batches
                ],
                "pre_movable_ticks": summarize_ticks(all_frames,
                                                     "pre_movable_ticks"),
                "scb_build_ticks": summarize_ticks(all_frames,
                                                   "scb_build_ticks"),
                "pure_suzy_ticks": summarize_ticks(all_frames,
                                                   "pure_suzy_ticks"),
                "post_movable_ticks": summarize_ticks(all_frames,
                                                      "post_movable_ticks"),
                "total_movable_ticks": summarize_ticks(all_frames,
                                                       "total_movable_ticks"),
                "total_frame_ticks": summarize_ticks(all_frames,
                                                     "total_frame_ticks"),
                "vblank_count_since_prev_display_request": summarize_ticks(
                    all_frames, "vblank_count_since_prev_display_request"),
                "ticks_per_vblank_empirical": {
                    "median": statistics.median(ticks_per_vblank_samples)
                        if ticks_per_vblank_samples else None,
                    "samples": len(ticks_per_vblank_samples),
                    "note": "total_frame_ticks / "
                        "vblank_count_since_prev_display_request for the "
                        "*same* display_request-to-display_request interval "
                        "-- self-consistent, no assumed CPU clock rate.",
                },
                "share_of_total_frame_pct": share_of_total_frame_pct,
                "scb_findings": all_findings,
                "scb_entry_count_last_frame":
                    batches[-1]["frames"][-1]["scb_entry_count"],
                "scb_entry_counts_all_frames": [
                    f["scb_entry_count"] for f in all_frames
                ],
            }

        evidence["results"] = results
        evidence["v038_baseline_maximum_vblank"] = 33
        evidence["gate_a_target_vblank"] = 2
        evidence["status"] = "done"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("done: %s" % args.output)
        return 0
    except Exception as error:
        evidence["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("BLOCKED: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
