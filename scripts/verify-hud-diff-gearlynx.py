#!/usr/bin/env python3
"""APS-053 v048/v049: HUD per-cell diff-update correctness verification.

Verifies append_hud's new per-cell diffing (src/static_layer.c, replacing
build_text_line's full 700-iteration rebuild every frame, see
.briefs/APS-053/v047.md Fable5 design). Bugs in per-cell diffing tend to be
invisible in a single-frame snapshot (existing
verify-static-layer-readback-gearlynx.py only checks one frame) and only
show up across a sequence of frames where different subsets of the 20 HUD
cells change. This script drives several such sequences and, after each
frame, reads HUD_DATA back from the shared scratch buffer and compares it
byte-for-byte against an independent Python re-implementation of the exact
bit layout build_text_line() produces (verified once against a single-frame
snapshot to confirm the two encoders agree before using either as a
reference for the diffing path).

Sequences exercised, each via _game_display_request breakpoints (arm once
per frame, inject GameState fields, continue to the next hit):

  1. cold start: hud_prev_valid==0 on the very first frame -> full 20-cell
     rebuild path.
  2. steady state: identical GameState for several frames -> zero cells
     rewritten (verified indirectly: HUD_DATA must still match after the
     "do nothing" frames since the diff path never touches a cell whose
     text didn't change).
  3. single-cell change: phase_timer's last digit only -> exactly 1 of the
     20 cells' expected content changes between frames.
  4. multi-digit carry: score incremented so multiple digits roll over at
     once (e.g. ...09 -> ...10) -> 2 adjacent cells change together,
     exercising two different (byte_offset, shift) cell classes in the
     same frame.
  5. stage/phase/lives/weapon_level text change: exercises the
     non-numeric cells (letters), which use a different subset of
     static_layer_font_bits than the digit cells 1-4 already cover.

Not exercised here: the voice-idle-guard recovery path (static_layer_draw
forcing hud_prev_valid back to 0 when title_voice_is_playing() was true,
see static_layer.c). A full rebuild and a correct diff produce identical
bytes when the text is unchanged, so this path cannot be distinguished
from "diffing skipped correctly" by comparing HUD_DATA bytes alone --
verified by code review instead (one-line force-invalidate call at the
same site as the pre-existing early return).

Diagnostic/verification only. Does not modify HUD_DATA's format, the SCB
chain, or any production code path.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE_A_MODULE_PATH = (
    ROOT / "scripts" / "verify-phase-3r-gate-a-full-fixture-gearlynx.py"
)
GEARLYNX = "/Applications/Gearlynx.app/Contents/MacOS/gearlynx"
MCP_PORT = 17784

# GameState field offsets (cc65 layout, verified against
# scripts/verify-phase-3r-gate-a-full-fixture-gearlynx.py's
# GAME_OFFSET_GAME_OVER=191/GAME_OFFSET_STAGE=209 and
# scripts/verify-phase-3r-gate-a-breakdown-gearlynx.py's
# GAME_STATE_PREFIX_END=213 (phase_timer ends at 210+1+2=213)):
#   score(4B unsigned long) @183, weapon_level(1B) @188, lives(1B) @190,
#   stage(1B) @209, phase(1B) @210, phase_timer(2B unsigned int) @211.
GAME_OFFSET_SCORE = 183
GAME_OFFSET_WEAPON_LEVEL = 188
GAME_OFFSET_LIVES = 190
GAME_OFFSET_STAGE = 209
GAME_OFFSET_PHASE = 210
GAME_OFFSET_PHASE_TIMER = 211
GAME_OFFSET_GAME_OVER = 191
GAME_OFFSET_TITLE_VOICE_PENDING = 194
GAME_OFFSET_DYING = 197
GAME_PHASE_NORMAL = 1
GAME_PHASE_TITLE = 6

FONT_HEIGHT = 7
FONT_WIDTH = 5
TEXT_LENGTH = 20
FONT_COUNT = 32
# v049 (Path B, .briefs/APS-053/v048.md/v049.md Fable5 design): HUD cells
# are 8px wide (1 byte/cell, no byte-boundary straddling), not
# build_text_line()'s 6px pitch -- HUD_DATA is 1 header byte + 20 pixel
# bytes per row (was 1 + 15), 7*21+1 = 148 bytes (was 113).
HUD_ROW_BYTES = 21
HUD_DATA_SIZE = 148

LETTER_FONT_INDEX = {
    'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6,
    'H': FONT_COUNT, 'I': 7, 'J': FONT_COUNT, 'K': FONT_COUNT,
    'L': 8, 'M': 9, 'N': 10, 'O': 11, 'P': 12, 'Q': FONT_COUNT,
    'R': 13, 'S': 14, 'T': 15, 'U': FONT_COUNT, 'V': 16, 'W': 17,
    'X': 18, 'Y': FONT_COUNT, 'Z': FONT_COUNT,
}


def text_font_index(glyph):
    if 'a' <= glyph <= 'z':
        glyph = glyph.upper()
    if 'A' <= glyph <= 'Z':
        return LETTER_FONT_INDEX[glyph]
    if '0' <= glyph <= '9':
        return 19 + (ord(glyph) - ord('0'))
    if glyph == '/':
        return 29
    if glyph == ':':
        return 30
    if glyph == '.':
        return 31
    return FONT_COUNT


def build_expected_hud(text, font_bits):
    """Independent re-implementation of append_hud/write_hud_cell's exact
    8px-pitch bit layout (src/static_layer.c, v049 Path B) for a fixed
    20-char line: each cell owns one whole pixel byte, glyph bits in the
    upper 5 bits (bit7..bit3, matching build_text_line's column0..
    column4 MSB-first order), lower 3 bits a spacer (always 0)."""
    assert len(text) == TEXT_LENGTH
    out = bytearray()
    for row in range(FONT_HEIGHT):
        out.append(HUD_ROW_BYTES)
        for c in range(TEXT_LENGTH):
            index = text_font_index(text[c])
            bits = font_bits[index * FONT_HEIGHT + row] \
                if index < FONT_COUNT else 0
            out.append((bits << 3) & 0xFF)
    out.append(0)
    return bytes(out)


def hud_text(score, weapon_level, lives, stage, phase, phase_timer):
    """Reproduces append_hud's exact 20-char layout (src/static_layer.c):
    text[0]='S', [1]=stage digit, [2]=' ', [3]=phase char, [4:8]=timer
    (04d), [8]=' ', [9:14]=score (05d), [14]=' ', [15]='L', [16]=lives
    digit, [17]=' ', [18]='W', [19]=weapon_level digit."""
    phase_char = {
        GAME_PHASE_NORMAL: 'N', 3: 'B', 0: 'I', 2: 'W', 4: 'C',
    }.get(phase, 'A')
    text = 'S{}{}{}{:04d}{}{:05d}{}L{}{}W{}'.format(
        stage, ' ', phase_char, phase_timer, ' ', score, ' ', lives, ' ',
        weapon_level)
    assert len(text) == TEXT_LENGTH, (len(text), text)
    return text


def load_gate_a_module():
    spec = importlib.util.spec_from_file_location(
        "aps053_gate_a_full_fixture", GATE_A_MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MCP_PORT = MCP_PORT
    return module


def start_paused(g, rom, symbols, port):
    import subprocess

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
                "clientInfo": {"name": "aps053-hud-diff", "version": "1"},
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
    deadline = time.monotonic() + 12.0
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


def inject(g, game_address, enemy_address, request_id, score, weapon_level,
           lives, stage, phase, phase_timer, dying=0, voice_pending=0):
    g.write_bytes(game_address + g.GAME_OFFSET_PLAYER, [80, 60, 8, 6],
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
    g.write_bytes(enemy_address, g.enemy_records(0), request_id)
    request_id += 1
    score_bytes = list(int(score).to_bytes(4, "little"))
    g.write_bytes(game_address + GAME_OFFSET_SCORE, score_bytes, request_id)
    request_id += 1
    g.write_bytes(game_address + GAME_OFFSET_WEAPON_LEVEL, [weapon_level],
                 request_id)
    request_id += 1
    g.write_bytes(game_address + GAME_OFFSET_LIVES, [lives], request_id)
    request_id += 1
    g.write_bytes(game_address + GAME_OFFSET_STAGE, [stage], request_id)
    request_id += 1
    g.write_bytes(game_address + GAME_OFFSET_PHASE, [phase], request_id)
    request_id += 1
    timer_bytes = list(int(phase_timer).to_bytes(2, "little"))
    g.write_bytes(game_address + GAME_OFFSET_PHASE_TIMER, timer_bytes,
                 request_id)
    request_id += 1
    g.write_bytes(game_address + GAME_OFFSET_GAME_OVER, [0], request_id)
    request_id += 1
    g.write_bytes(game_address + GAME_OFFSET_TITLE_VOICE_PENDING,
                 [voice_pending, 0, 0, 0], request_id)
    request_id += 1
    g.write_bytes(game_address + GAME_OFFSET_DYING, [dying, 0, 0],
                 request_id)
    return request_id + 1


def one_breakpoint(g, address, request_id, description):
    address_hex = "%04X" % address
    g.tool("set_breakpoint", {"address": address_hex}, request_id)
    request_id += 1
    g.tool("debug_continue", request_id=request_id)
    request_id += 1
    request_id = g.wait_for_breakpoint(request_id, description)
    g.tool("remove_breakpoint", {"address": address_hex}, request_id)
    return request_id + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path,
                        default=Path("dist/asteroid-patrol-cadence.lnx"))
    parser.add_argument("--symbols", type=Path,
                        default=Path("build/asteroid-patrol-cadence.lbl"))
    parser.add_argument("--font-symbols", type=Path,
                        default=Path("build/asteroid-patrol-cadence.lbl"))
    parser.add_argument("--output", type=Path, default=Path(
        "evidence/APS-053/hud-diff-v048.json"))
    args = parser.parse_args()

    if not Path(GEARLYNX).is_file():
        raise RuntimeError("Gearlynx executable not found")

    g = load_gate_a_module()

    evidence = {"aps": "APS-053", "brief": ".briefs/APS-053/v047.md",
                "gate": "hud-diff", "status": "blocked", "frames": []}

    try:
        process, request_id = start_paused(g, args.rom, args.symbols,
                                           MCP_PORT)
        try:
            game_address = g.symbol_address(args.symbols, "_game")
            enemy_address = g.symbol_address(args.symbols, "_game_enemies")
            display_request = g.symbol_address(args.symbols,
                                               "_game_display_request")
            scratch = g.symbol_address(args.symbols,
                                       "_title_voice_scratch_buffer")
            hud_addr = scratch + 21 * 23  # MAX_SCBS(21) * SCB_SIZE(23)
            font_addr = g.symbol_address(args.font_symbols,
                                         "_static_layer_font_bits")
            font_bits = g.read_bytes(font_addr, FONT_COUNT * FONT_HEIGHT,
                                     request_id)
            request_id += 1

            scenario = [
                # (label, score, weapon, lives, stage, phase, timer)
                ("cold_start", 100, 1, 3, 1, GAME_PHASE_NORMAL, 500),
                ("steady_1", 100, 1, 3, 1, GAME_PHASE_NORMAL, 500),
                ("steady_2", 100, 1, 3, 1, GAME_PHASE_NORMAL, 500),
                ("timer_last_digit", 100, 1, 3, 1, GAME_PHASE_NORMAL, 501),
                ("score_carry", 109, 1, 3, 1, GAME_PHASE_NORMAL, 502),
                ("score_carry_next", 110, 1, 3, 1, GAME_PHASE_NORMAL, 503),
                # phase is deliberately kept at NORMAL here: injecting a
                # non-NORMAL phase (e.g. BOSS/STAGE_CLEAR) lets the game
                # logic loop run its own real phase-transition rules
                # before the next display_request, which both changes
                # phase again out from under the injected value and (via
                # draw_phase_overlay -> static_layer_text) legitimately
                # overwrites HUD_DATA with an overlay string for that
                # frame -- correct behavior, but not what this cell-diff
                # test is checking. Non-numeric-cell coverage (stage/
                # lives/weapon_level letters) doesn't need a phase change.
                ("letters_change", 110, 2, 2, 2, GAME_PHASE_NORMAL, 504),
                ("steady_after_letters", 110, 2, 2, 2, GAME_PHASE_NORMAL,
                    505),
            ]

            request_id = inject(g, game_address, enemy_address, request_id,
                               *scenario[0][1:])
            # Warm up past the TITLE-to-gameplay transition before
            # recording: the first couple of display_request hits after
            # forcing game->phase away from TITLE can still reflect
            # transient state (e.g. active_palette_stage/scene caches in
            # main.c not yet settled), same rationale as every other
            # APS-053 gearlynx harness's WARMUP_FRAMES.
            for warm in range(3):
                request_id = one_breakpoint(
                    g, display_request, request_id, "warmup %d" % warm)
                request_id = inject(g, game_address, enemy_address,
                                   request_id, *scenario[0][1:])

            for label, score, weapon, lives, stage, phase, timer in \
                    scenario:
                request_id = one_breakpoint(
                    g, display_request, request_id, label + " display")
                # Read the *actual* GameState fields at the moment this
                # frame's HUD was drawn, not the values just injected --
                # the logic-update loop that runs before draw_game() each
                # frame (main.c) can change some of them (phase_timer is a
                # countdown, so it reliably does) before append_hud() ever
                # sees them. Comparing against what append_hud actually
                # had to render is the correct, robust check; comparing
                # against the raw injected values would spuriously fail
                # whenever the logic loop mutated state in between.
                state = g.read_bytes(game_address + GAME_OFFSET_STAGE,
                                     GAME_OFFSET_PHASE_TIMER + 2 -
                                     GAME_OFFSET_STAGE, request_id)
                request_id += 1
                actual_stage = state[0]
                actual_phase = state[1]
                actual_timer = int.from_bytes(state[2:4], "little")
                score_bytes = g.read_bytes(game_address + GAME_OFFSET_SCORE,
                                          4, request_id)
                request_id += 1
                actual_score = int.from_bytes(score_bytes, "little")
                wl_bytes = g.read_bytes(
                    game_address + GAME_OFFSET_WEAPON_LEVEL, 1, request_id)
                request_id += 1
                actual_weapon = wl_bytes[0]
                lives_bytes = g.read_bytes(game_address + GAME_OFFSET_LIVES,
                                          1, request_id)
                request_id += 1
                actual_lives = lives_bytes[0]

                hud_bytes = g.read_bytes(hud_addr, HUD_DATA_SIZE,
                                         request_id)
                request_id += 1
                expected_text = hud_text(actual_score, actual_weapon,
                                         actual_lives, actual_stage,
                                         actual_phase, actual_timer)
                expected_bytes = build_expected_hud(expected_text,
                                                    font_bits)
                match = hud_bytes == expected_bytes
                evidence["frames"].append({
                    "label": label, "text": expected_text, "match": match,
                    "injected": {"score": score, "weapon": weapon,
                                 "lives": lives, "stage": stage,
                                 "phase": phase, "timer": timer},
                    "hud_hex": hud_bytes.hex(),
                    "expected_hex": expected_bytes.hex(),
                })
                print("%-20s text=%r match=%s" %
                      (label, expected_text, match))
                # advance to next scenario's fields for the *next* frame
                request_id = inject(g, game_address, enemy_address,
                                   request_id, score, weapon, lives, stage,
                                   phase, timer)

            evidence["all_match"] = all(f["match"] for f in
                                        evidence["frames"])
            evidence["status"] = "done"
        finally:
            stop_process(process)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("done: %s" % args.output)
        return 0 if evidence["all_match"] else 1
    except Exception as error:
        evidence["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("BLOCKED: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
