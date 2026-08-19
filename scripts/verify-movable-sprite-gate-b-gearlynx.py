#!/usr/bin/env python3
"""APS-053 v037 gate(b): real-hardware (Gearlynx) pixel verification for the
Phase 3R movable-object Suzy SCB path (main.c movable_append_sprite /
movable_scb_finish), independent of the software decode_packed() model used
by scripts/verify-static-layer-readback-gearlynx.py.

For each of the 9 "enemy"/"mineral" kind sprites (the bpp2 category the
APS-053 v037 brief flags for the last-pixel-drop bug), this places exactly
one active enemy of that type at a known position with everything else
(player, other enemies, boss, power item, bullets, environment hazards) off
screen or inactive, captures the single-entry SCB chain Suzy actually
submits (via a breakpoint at the real _tgi_ioctl entry -- the same entry
static_layer's tgi_sprite()/tgi_draw_sprite() macro expands to), then
compares a real captured screenshot against the sprite's own preview-grid
authoring source (assets/previews/aps044-enemy-preview.json), not against
any encoder/decoder model. This is the "genuinely rendered pixels match the
authored art" check gate(b) requires.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READBACK_PATH = ROOT / "scripts" / "verify-static-layer-readback-gearlynx.py"
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17772

GAME_OFFSET_PLAYER = 2
GAME_OFFSET_BULLETS = 6
GAME_OFFSET_GAME_OVER = 191
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PLANET_OFFSET = 200
GAME_OFFSET_FAR_STAR_OFFSET = 202
GAME_OFFSET_NEAR_STAR_OFFSET = 203
GAME_OFFSET_PHASE_STAGE_INTRO = 210
GAME_OFFSET_ANIMATION_FRAME = 207
GAME_STATE_PREFIX_END = 213
GAME_ENEMY_BYTES = 8 * 12
GAME_ENEMY_SIZE = 12
GAME_PHASE_STAGE_INTRO = 0

# Movable objects use cc65 _suzy.h's SCB_RENONE/SCB_RENONE_PAL (main.c
# movable_append), NOT the SCB_REHV_PAL the static/background layer uses --
# there is no hsize/vsize field at all (Suzy is fixed at 1x scale project-
# wide, APS-050) and penpal (when present) starts right after vpos:
#   sprctl0(1) sprctl1(1) sprcoll(1) next(2) data(2) hpos(2) vpos(2)
#   [penpal(8) -- SCB_RENONE_PAL only, first_of_group entries]
SCB_SPRCTL0 = 0
SCB_SPRCTL1 = 1
SCB_NEXT = 3
SCB_DATA = 5
SCB_HPOS = 7
SCB_VPOS = 9
SCB_PENPAL = 11
SCB_PAL_SIZE = 19
SCB_NOPAL_SIZE = 11
SCB_SKIP_BIT = 0x04
MAX_CHAIN_WALK = 64

SCREEN_WIDTH = 160
SCREEN_HEIGHT = 102

# (sprite_id, kind, type/appearance index, stage matching the formation
# that actually uses this kind so the palette theme is representative)
CASES = [
    ("player", "player", None, 1),
    ("scout", "enemy", 0, 1),
    ("saucer", "enemy", 1, 1),
    ("dropper", "enemy", 2, 1),
    ("fighter", "enemy", 3, 2),
    ("bomber", "enemy", 4, 2),
    ("supply", "enemy", 5, 2),
    ("cave_bat", "enemy", 6, 3),
    ("rock_worm", "enemy", 7, 3),
    ("mining_drone", "enemy", 8, 3),
    ("coral_bastion", "boss", 1, 1),
    ("amber_carrier", "boss", 2, 2),
    ("violet_geode", "boss", 3, 3),
]

GAME_OFFSET_BOSS = 150
GAME_BOSS_SIZE = 14
BOSS_X = 60
BOSS_Y = 30

ENEMY_X = 60
ENEMY_Y = 40


def load_modules():
    spec = importlib.util.spec_from_file_location("readback", READBACK_PATH)
    readback = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(readback)
    visual = readback.load_visual_module()
    visual.MCP_PORT = MCP_PORT
    readback.MCP_PORT = MCP_PORT
    return readback, visual


def load_stage_gen():
    spec = importlib.util.spec_from_file_location(
        "stage_gen", ROOT / "scripts" / "generate-stage-data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signed_word(data, offset):
    value = int.from_bytes(data[offset:offset + 2], "little")
    return value - 0x10000 if value & 0x8000 else value


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], "little")


def sprite_expected_grid(stage_gen, sprite_id):
    previews, _player_doc, _enemy_doc = stage_gen.load_previews()
    document = stage_gen.load_json(ROOT / "assets" / "stages" / "stages.json")
    sprite = next(s for s in document["sprites"] if s["id"] == sprite_id)
    preview = previews[sprite_id]
    roles = stage_gen.SPRITE_ROLES[sprite["kind"]]
    frame0_rows = [list(r) for r in preview["grid"]]
    frame1_rows = [list(r) for r in stage_gen.apply_anim_delta(
        preview["grid"], preview["anim_delta"], roles,
        "previews.%s.anim_delta" % sprite_id)]
    colors_frame0 = {c for row in frame0_rows for c in row if c != "."}
    colors_frame1 = {c for row in frame1_rows for c in row if c != "."}
    colors_union = sorted(colors_frame0 | colors_frame1)
    local_index = {role: i + 1 for i, role in enumerate(colors_union)}
    real_colors = [int(role, 16) for role in colors_union]
    grids = {
        0: [[0 if c == "." else local_index[c] for c in row]
            for row in frame0_rows],
        1: [[0 if c == "." else local_index[c] for c in row]
            for row in frame1_rows],
    }
    return grids, real_colors


def suzy_pixel_color(penpal, value):
    if value == 0:
        return None
    palette_index = value >> 1
    palette_byte = penpal[palette_index]
    if value & 1:
        return palette_byte & 0x0F
    return (palette_byte >> 4) & 0x0F


def inject_fixture(visual, game_address, enemy_address, stage, kind,
                   type_index, frame, request_id):
    player_x, player_y = (60, 70) if kind == "player" else (250, 250)
    visual.write_bytes(game_address + GAME_OFFSET_PLAYER,
                       [player_x, player_y, 8, 6], request_id)
    request_id += 1
    visual.write_bytes(game_address + GAME_OFFSET_BULLETS,
                       [0] * (GAME_OFFSET_GAME_OVER - GAME_OFFSET_BULLETS),
                       request_id)
    request_id += 1
    state = [0] * (GAME_STATE_PREFIX_END - GAME_OFFSET_GAME_OVER + 1)
    state[GAME_OFFSET_STAGE - GAME_OFFSET_GAME_OVER] = stage
    state[GAME_OFFSET_PHASE_STAGE_INTRO - GAME_OFFSET_GAME_OVER] = (
        GAME_PHASE_STAGE_INTRO
    )
    state[GAME_OFFSET_PLANET_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    state[GAME_OFFSET_FAR_STAR_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    state[GAME_OFFSET_NEAR_STAR_OFFSET - GAME_OFFSET_GAME_OVER] = 0
    state[GAME_OFFSET_ANIMATION_FRAME - GAME_OFFSET_GAME_OVER] = frame
    visual.write_bytes(game_address + GAME_OFFSET_GAME_OVER, state,
                       request_id)
    request_id += 1
    visual.write_bytes(enemy_address, [0] * GAME_ENEMY_BYTES, request_id)
    request_id += 1
    visual.write_bytes(game_address + GAME_OFFSET_BOSS,
                       [0] * GAME_BOSS_SIZE, request_id)
    request_id += 1
    if kind == "enemy":
        # GameEnemy: rect{x,y,w,h}, active, type, pattern, base_y,
        # move_counter, phase, direction, fire_counter (12 bytes, see
        # include/game.h).
        enemy_bytes = [ENEMY_X, ENEMY_Y, 8, 8, 1, type_index, 0, ENEMY_Y,
                       0, 0, 0, 0]
        visual.write_bytes(enemy_address, enemy_bytes, request_id)
        request_id += 1
    elif kind == "boss":
        # GameBoss: rect{x,y,w,h}, active, hp, max_hp, config_id,
        # appearance_id, script_step, attack_timer, move_phase, direction,
        # alternate_cannon (14 bytes, see include/game.h).
        boss_bytes = [BOSS_X, BOSS_Y, 24, 24, 1, 1, 1, 0, type_index,
                     0, 0, 0, 0, 0]
        visual.write_bytes(game_address + GAME_OFFSET_BOSS, boss_bytes,
                           request_id)
        request_id += 1
    return request_id


def run_case(visual, readback, stage_gen, game_address, enemy_address,
            ioctl_address, sync_address, empty_sprite_address, sprite_id,
            kind, type_index, stage, frame, request_id, output_dir):
    # Drain any in-flight draw before injecting, exactly as the static
    # layer verifier does.
    visual.tool("set_breakpoint", {"address": "%04X" % sync_address},
               request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = visual.wait_for_breakpoint(
        request_id + 1, "%s frame%d pre-draw boundary" % (sprite_id, frame))
    visual.tool("remove_breakpoint", {"address": "%04X" % sync_address},
               request_id)
    request_id += 1

    request_id = inject_fixture(
        visual, game_address, enemy_address, stage, kind, type_index, frame,
        request_id)

    # _tgi_ioctl is a single shared entry point for every tgi_ioctl() call
    # in the cc65 Lynx TGI driver, not just tgi_sprite(spr) (== tgi_ioctl(0,
    # spr)): tgi_busy()/tgi_updatedisplay() are tgi_ioctl(4, 0)/(4, 1), and
    # GAME_DISPLAY_READY_WAIT spin-polls tgi_busy() an unbounded number of
    # times per frame. Those pass small integers (0/1) as the fastcall
    # pointer argument, not a real SCB chain address, so filter hits by
    # requiring A|X<<8 to look like a real RAM pointer (movable_scb_pool
    # and the static layer's SCBS array both live in BSS, well above
    # 0x1000). draw_game() calls static_layer_draw() (which submits its
    # own background chain via finish_layer() before returning) first,
    # then builds and submits the movable chain via movable_scb_finish();
    # the fixture here queues no HUD/title text, so
    # static_layer_text_flush()'s own finish_layer() is a no-op and does
    # not add a third submission. So the first real-pointer hit per frame
    # is the static/background chain and the second is the movable chain.
    visual.tool("set_breakpoint", {"address": "%04X" % ioctl_address},
               request_id)
    request_id += 1
    pointer_hits = []
    for _ in range(64):
        visual.tool("debug_continue", request_id=request_id)
        request_id = visual.wait_for_breakpoint(
            request_id + 1, "%s frame%d ioctl hit" % (sprite_id, frame))
        cpu = visual.tool("get_6502_status", request_id=request_id)
        request_id += 1
        candidate = int(cpu["A"], 16) | (int(cpu["X"], 16) << 8)
        if candidate >= 0x1000:
            pointer_hits.append(candidate)
            if len(pointer_hits) == 2:
                break
    if len(pointer_hits) != 2:
        raise RuntimeError(
            "%s frame%d: expected 2 real SCB chain hits, got %d" %
            (sprite_id, frame, len(pointer_hits)))
    # v045 update: the movable chain is now a fixed 45-entry static chain
    # (env header/2 slots, player, enemy header/8 slots, boss, power
    # item, pbullet header/12 slots, ebullet header/16 slots -- see
    # src/main.c movable_scb_*), submitted in full every frame regardless
    # of how many objects are active (inactive slots carry the SKIP bit
    # instead of being omitted from the chain, unlike the pre-v045
    # dynamic-append design this harness was originally written
    # against). So instead of assuming the chain is exactly 1-2 entries
    # long, walk it to the end and keep only entries that are neither a
    # palette-only header (data == movable_scb_empty_sprite) nor
    # SKIPped -- this fixture only ever leaves the player (if visible,
    # see inject_fixture) and/or the one object under test active, so
    # that set is 1 or 2 entries regardless of total chain length.
    entries = []
    address = pointer_hits[1]
    for _ in range(MAX_CHAIN_WALK):
        scb_raw = visual.read_bytes(address, SCB_PAL_SIZE, request_id)
        request_id += 1
        entry = {
            "address": address,
            "sprctl0": scb_raw[SCB_SPRCTL0],
            "sprctl1": scb_raw[SCB_SPRCTL1],
            "next": word(scb_raw, SCB_NEXT),
            "data": word(scb_raw, SCB_DATA),
            "hpos": signed_word(scb_raw, SCB_HPOS),
            "vpos": signed_word(scb_raw, SCB_VPOS),
            "penpal": list(scb_raw[SCB_PENPAL:SCB_PENPAL + 3]),
        }
        entries.append(entry)
        if entry["next"] == 0:
            break
        address = entry["next"]
    active_entries = [
        e for e in entries
        if (e["sprctl1"] & SCB_SKIP_BIT) == 0 and
        e["data"] != empty_sprite_address
    ]
    expected_entries = 1 if kind == "player" else 2
    scb = (active_entries[-1] if active_entries else
        {"address": 0, "sprctl0": 0, "sprctl1": 0, "next": 0, "data": 0,
         "hpos": 0, "vpos": 0, "penpal": [0, 0, 0]})
    chain_ok = (entries[-1]["next"] == 0 and
        len(active_entries) == expected_entries)

    visual.tool("remove_breakpoint", {"address": "%04X" % ioctl_address},
               request_id)
    request_id += 1
    visual.tool("debug_step_out", request_id=request_id)
    request_id += 1
    # Reach the next pre-draw boundary so this frame has definitely been
    # swapped to the front buffer before we screenshot it.
    visual.tool("set_breakpoint", {"address": "%04X" % sync_address},
               request_id)
    request_id += 1
    visual.tool("debug_continue", request_id=request_id)
    request_id = visual.wait_for_breakpoint(
        request_id + 1, "%s frame%d post-swap boundary" % (sprite_id, frame))
    visual.tool("remove_breakpoint", {"address": "%04X" % sync_address},
               request_id)
    request_id += 1

    # Read the two raw physical framebuffer pages directly (like
    # verify-static-layer-readback-gearlynx.py) instead of get_screenshot:
    # get_screenshot's own update timing is not proven synchronous with the
    # tgi_busy()/sync-boundary handshake this harness relies on, while
    # vidbas/dispadr are the actual Suzy-written CPU memory pages.
    vidbas_png, vidbas = readback.read_framebuffer_png(
        visual, "vidbas", request_id)
    request_id += 1
    dispadr_png, dispadr = readback.read_framebuffer_png(
        visual, "dispadr", request_id)
    request_id += 1
    name = "%s-frame%d" % (sprite_id, frame)
    (output_dir / (name + "-vidbas.png")).write_bytes(vidbas_png)
    (output_dir / (name + "-dispadr.png")).write_bytes(dispadr_png)
    buffers_equal = vidbas == dispadr

    grids, real_colors = sprite_expected_grid(stage_gen, sprite_id)
    grid = grids[frame]
    color_map = readback.stage_palette_rgba(visual, stage)

    mismatches = []
    checked = 0
    for row in range(16):
        for col in range(16):
            local_value = grid[row][col]
            sx = scb["hpos"] + col
            sy = scb["vpos"] + row
            if sx < 0 or sx >= SCREEN_WIDTH or sy < 0 or sy >= SCREEN_HEIGHT:
                continue
            checked += 1
            actual_vidbas = tuple(vidbas[sy][sx * 4:sx * 4 + 4])
            actual_dispadr = tuple(dispadr[sy][sx * 4:sx * 4 + 4])
            if local_value == 0:
                expected_rgba = None
            else:
                real_color = real_colors[local_value - 1]
                expected_rgba = color_map.get(real_color)
            if expected_rgba is None:
                # Transparent expected pixel: anything drawn earlier
                # (background) is fine, only non-transparent pixels are
                # under test here.
                continue
            if actual_vidbas != expected_rgba or actual_dispadr != expected_rgba:
                mismatches.append({
                    "row": row, "col": col, "sx": sx, "sy": sy,
                    "expected_rgba": list(expected_rgba),
                    "actual_vidbas_rgba": list(actual_vidbas),
                    "actual_dispadr_rgba": list(actual_dispadr),
                })

    return request_id, {
        "sprite_id": sprite_id,
        "frame": frame,
        "stage": stage,
        "scb": {"hpos": scb["hpos"], "vpos": scb["vpos"],
                "data": "0x%04X" % scb["data"],
                "sprctl0": "0x%02X" % scb["sprctl0"],
                "sprctl1": "0x%02X" % scb["sprctl1"],
                "next": scb["next"]},
        "chain_ok": chain_ok,
        "buffers_equal": buffers_equal,
        "checked_pixels": checked,
        "mismatches": mismatches,
        "passed": chain_ok and buffers_equal and not mismatches,
        "vidbas_png": name + "-vidbas.png",
        "dispadr_png": name + "-dispadr.png",
        "vidbas_sha256": hashlib.sha256(vidbas_png).hexdigest(),
        "dispadr_sha256": hashlib.sha256(dispadr_png).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("dist/asteroid-patrol.lnx"))
    parser.add_argument("--symbols", type=Path, default=Path("build/asteroid-patrol.lbl"))
    parser.add_argument("--output", type=Path,
                        default=Path("evidence/APS-053/movable-sprite-gate-b.json"))
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")

    readback, visual = load_modules()
    stage_gen = load_stage_gen()

    game_address = visual.symbol_address(args.symbols, "_game")
    enemy_address = visual.symbol_address(args.symbols, "_game_enemies")
    ioctl_address = visual.symbol_address(args.symbols, "_tgi_ioctl")
    sync_address = visual.symbol_address(args.symbols,
                                         "_game_display_sync_complete")
    scratch_address = visual.symbol_address(args.symbols,
                                         "_title_voice_scratch_buffer")
    voice_active_address = scratch_address + 640 + 6
    empty_sprite_ptr_address = visual.symbol_address(
        args.symbols, "_movable_scb_empty_sprite_debug_export")

    command = [GEARLYNX]
    if not args.gui:
        command.append("--headless")
    command.extend(["--mcp-http", "--mcp-http-port", str(MCP_PORT),
                    str(args.rom), str(args.symbols)])
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    evidence = {"aps": "APS-053", "brief": "v037", "gate": "b",
                "rom": {"path": str(args.rom),
                        "sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest()},
                "cases": []}
    try:
        for _ in range(30):
            try:
                visual.call("initialize", {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "aps053-movable-gate-b",
                                   "version": "1"},
                })
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Gearlynx MCP server did not start")
        request_id = readback.wait_stable_title(
            visual, game_address, voice_active_address, 3
        )
        # movable_scb_empty_sprite_debug_export is itself a pointer
        # variable (its own address is empty_sprite_ptr_address); read
        # its value to get the address it points to, which is what the
        # SCB chain's `data` field is compared against.
        empty_sprite_bytes = visual.read_bytes(
            empty_sprite_ptr_address, 2, request_id)
        request_id += 1
        empty_sprite_address = int.from_bytes(empty_sprite_bytes, "little")
        for sprite_id, kind, type_index, stage in CASES:
            for frame in (0, 1):
                request_id, result = run_case(
                    visual, readback, stage_gen, game_address, enemy_address,
                    ioctl_address, sync_address, empty_sprite_address,
                    sprite_id, kind, type_index, stage, frame, request_id,
                    args.output.parent,
                )
                evidence["cases"].append(result)
                print("%-14s frame%d stage=%d checked=%3d mismatches=%2d %s" % (
                    sprite_id, frame, stage, result["checked_pixels"],
                    len(result["mismatches"]),
                    "PASS" if result["passed"] else "FAIL"))
        evidence["passed"] = all(c["passed"] for c in evidence["cases"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        return 0 if evidence["passed"] else 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("FAIL: %s" % error, file=sys.stderr)
        sys.exit(1)
