#include <lynx.h>
#ifdef STATIC_LAYER_DEBUG_ASSERT
#include <assert.h>
#endif
#include <string.h>
#include <tgi.h>

#include "game.h"
#include "static_layer.h"
#include "static_layer_data.h"
#include "static_layer_overlay.h"
#include "static_layer_overlay_data.h"
#include "title_voice.h"
#ifdef CADENCE_PROBE
#include "static_layer_split_probe.h"
#endif

#define BLACK 0u
#define WHITE 15u
#define PLANET 1u
#define PLANET_DETAIL 3u
#define FAR_STAR 3u
#define NEAR_STAR 4u
#define MOUNTAIN 1u
#define MID_CLOUD 3u
#define NEAR_CLOUD 4u
#define CAVE_SHADOW 1u
#define CAVE_ROCK 3u
#define CAVE_NEAR 4u
#define SPACE 0u
#define SKY 1u
#define CAVE 2u
#define MAX_SCBS 21u
#define SCB_SIZE 23u
#define TEXT_DATA_SIZE 113u
#define STATIC_LAYER_TEXT_ADVANCE 5

static unsigned char scb_count;
static unsigned char text_layer_started;
static unsigned char title_text_queue;
static unsigned char overlay_loaded = STATIC_LAYER_OVERLAY_NONE;
#ifndef CADENCE_PROBE
static unsigned char text_layer_buffer_index;
#endif
#define SCBS ((SCB_REHV_PAL*)title_voice_scratch_buffer)
#define HUD_DATA ((unsigned char*)title_voice_scratch_buffer + MAX_SCBS * SCB_SIZE)
#ifndef CADENCE_PROBE
/* TITLE currently submits ten SCBs.  Keep a second queued text bitmap in
 * the first unused title-only SCB slot so the cadence probe's fixture region
 * at scratch+539 remains untouched.  Game/background layers never queue
 * text and can still use all 21 SCB slots. */
#define HUD_DATA_SECOND ((unsigned char*)title_voice_scratch_buffer + \
    10u * SCB_SIZE)
#endif

#ifdef STATIC_LAYER_DEBUG_ASSERT
#define STATIC_LAYER_REQUIRE_VOICE_IDLE() \
    assert(title_voice_is_playing() == 0u)
#else
#define STATIC_LAYER_REQUIRE_VOICE_IDLE() ((void)0)
#endif

/* Loads the cart overlay group needed for the scene about to be drawn,
 * skipping the read when it is already resident. Callers must only reach
 * this after confirming the voice player is idle (see
 * STATIC_LAYER_REQUIRE_VOICE_IDLE): the overlay loader and the voice
 * streamer share a single cart-wide read cursor and must never run
 * concurrently. */
static void ensure_overlay(unsigned char which)
{
    if (overlay_loaded == which) return;
    static_layer_overlay_load(which);
    overlay_loaded = which;
}

static void reset_scb(SCB_REHV_PAL* scb, const unsigned char* data,
    int x, int y, unsigned char color, unsigned char detail)
{
    memset(scb, 0, sizeof(*scb));
    scb->sprctl0 = (unsigned char)(BPP_1 | TYPE_NONCOLL);
    scb->sprctl1 = (unsigned char)(PACKED | REHV);
    scb->sprcoll = NO_COLLIDE;
    scb->data = (unsigned char*)data;
    scb->hpos = (signed int)x;
    scb->vpos = (signed int)y;
    /* HSIZE/VSIZE are 8.8 scale factors, not source dimensions. All normal
     * static sprites are 1x; static_layer_draw restores the clear sprite's
     * special full-screen scale after this helper returns. */
    scb->hsize = 0x0100u;
    scb->vsize = 0x0100u;
    /* Suzy selects penpal[value >> 1], then takes the low nibble for odd
     * values and the high nibble for even values. Pixel 1 is therefore the
     * low nibble of penpal[0], while the 2bpp planet's pixel 2 is the high
     * nibble of penpal[1]. */
    scb->penpal[0] = (unsigned char)(color & 0x0Fu);
    scb->penpal[1] = (unsigned char)((detail & 0x0Fu) << 4);
}

static void begin_layer(void)
{
    scb_count = 0u;
#ifndef CADENCE_PROBE
    text_layer_buffer_index = 0u;
#endif
}

static void append_scb(const unsigned char* data, int x, int y,
    unsigned char color)
{
    SCB_REHV_PAL* scb;

    if (scb_count >= MAX_SCBS) return;
    scb = &SCBS[scb_count];
    reset_scb(scb, data, x, y, color, color);
    if (scb_count != 0u) SCBS[scb_count - 1u].next = (char*)scb;
    ++scb_count;
}

static void append_repeat(const unsigned char* data, int x, int y,
    unsigned char color, int period)
{
    append_scb(data, x, y, color);
    append_scb(data, x + period, y, color);
}

static void finish_layer(void)
{
#ifdef CADENCE_PROBE
    static_layer_split_marker_pre_finish();
#endif
    if (scb_count != 0u) tgi_sprite(SCBS);
}

static void append_space(const GameState* game)
{
    int x;
    unsigned char i;
    const unsigned char* far_star_x =
        static_layer_overlay_buffer + STATIC_LAYER_OVERLAY_FAR_STAR_X_OFFSET;
    const unsigned char* far_star_y =
        static_layer_overlay_buffer + STATIC_LAYER_OVERLAY_FAR_STAR_Y_OFFSET;
    const unsigned char* near_star_x =
        static_layer_overlay_buffer + STATIC_LAYER_OVERLAY_NEAR_STAR_X_OFFSET;
    const unsigned char* near_star_y =
        static_layer_overlay_buffer + STATIC_LAYER_OVERLAY_NEAR_STAR_Y_OFFSET;

    x = (int)GAME_PLANET_BASE_X - (int)game->planet_offset;
    if (x < -(int)GAME_PLANET_WIDTH) x += (int)GAME_PLANET_SCROLL_PERIOD;
    append_scb(static_layer_overlay_buffer + STATIC_LAYER_OVERLAY_PLANET_OFFSET,
        x, GAME_PLANET_BASE_Y, PLANET);
    SCBS[scb_count - 1u].sprctl0 = (unsigned char)(BPP_2 | TYPE_NONCOLL);
    SCBS[scb_count - 1u].penpal[1] =
        (unsigned char)(PLANET_DETAIL << 4);
    for (i = 0u; i < STATIC_LAYER_FAR_STAR_COUNT; ++i) {
        x = (int)far_star_x[i] - (int)game->far_star_offset;
        if (x < 0) x += GAME_SCREEN_WIDTH;
        append_scb(static_layer_overlay_buffer +
            STATIC_LAYER_OVERLAY_SPACE_FAR_STAR_OFFSET, x, far_star_y[i],
            FAR_STAR);
    }
    for (i = 0u; i < STATIC_LAYER_NEAR_STAR_COUNT; ++i) {
        x = (int)near_star_x[i] - (int)game->near_star_offset;
        if (x < 0) x += GAME_SCREEN_WIDTH;
        append_scb(static_layer_overlay_buffer +
            STATIC_LAYER_OVERLAY_NEAR_STAR_OFFSET, x, near_star_y[i],
            NEAR_STAR);
    }
}

typedef struct StaticScrollLayer {
    unsigned int overlay_offset;
    unsigned char y;
    unsigned char color;
    unsigned char offset_kind;
    unsigned int period;
} StaticScrollLayer;

static const StaticScrollLayer sky_layers[3] = {
    { STATIC_LAYER_OVERLAY_MOUNTAIN_OFFSET, STATIC_LAYER_MOUNTAIN_Y_OFFSET,
        MOUNTAIN, 0u, GAME_PLANET_SCROLL_PERIOD },
    { STATIC_LAYER_OVERLAY_MID_CLOUD_OFFSET, STATIC_LAYER_MID_CLOUD_Y_OFFSET,
        MID_CLOUD, 1u, GAME_SCREEN_WIDTH },
    { STATIC_LAYER_OVERLAY_NEAR_CLOUD_OFFSET, STATIC_LAYER_NEAR_CLOUD_Y_OFFSET,
        NEAR_CLOUD, 2u, GAME_SCREEN_WIDTH }
};

static const StaticScrollLayer cave_layers[3] = {
    { STATIC_LAYER_OVERLAY_CAVE_WALL_OFFSET, STATIC_LAYER_CAVE_WALL_Y_OFFSET,
        CAVE_SHADOW, 0u, GAME_PLANET_SCROLL_PERIOD },
    { STATIC_LAYER_OVERLAY_CAVE_ROCK_OFFSET, STATIC_LAYER_CAVE_ROCK_Y_OFFSET,
        CAVE_ROCK, 1u, GAME_SCREEN_WIDTH },
    { STATIC_LAYER_OVERLAY_CAVE_NEAR_OFFSET, STATIC_LAYER_CAVE_NEAR_Y_OFFSET,
        CAVE_NEAR, 2u, GAME_SCREEN_WIDTH }
};

static void append_scroll_layers(const GameState* game,
    const StaticScrollLayer* layers)
{
    unsigned char i;
    unsigned char offset;

    for (i = 0u; i < 3u; ++i) {
        offset = layers[i].offset_kind == 0u ? game->planet_offset :
            layers[i].offset_kind == 1u ? game->far_star_offset :
            game->near_star_offset;
        append_repeat(static_layer_overlay_buffer + layers[i].overlay_offset,
            -(int)offset, layers[i].y, layers[i].color, layers[i].period);
    }
}

/* Maps 'A'-'Z' to its compact index in static_layer_font_bits.
 * H/J/K/Q/U/Y/Z are unused across every rendered string in the ROM and were
 * dropped from font_glyphs (scripts/generate-static-layer.py), so the
 * indices are no longer a plain `glyph - 'A'` range; this presence table
 * absorbs the gaps. STATIC_LAYER_FONT_COUNT marks a removed letter. */
static const unsigned char letter_font_index[26] = {
    0u, 1u, 2u, 3u, 4u, 5u, 6u,             /* A-G */
    STATIC_LAYER_FONT_COUNT,                /* H */
    7u,                                     /* I */
    STATIC_LAYER_FONT_COUNT,                /* J */
    STATIC_LAYER_FONT_COUNT,                /* K */
    8u, 9u, 10u, 11u, 12u,                  /* L-P */
    STATIC_LAYER_FONT_COUNT,                /* Q */
    13u, 14u, 15u,                          /* R-T */
    STATIC_LAYER_FONT_COUNT,                /* U */
    16u, 17u, 18u,                          /* V-X */
    STATIC_LAYER_FONT_COUNT,                /* Y */
    STATIC_LAYER_FONT_COUNT                 /* Z */
};

static unsigned char text_font_index(char glyph)
{
    if (glyph >= 'a' && glyph <= 'z') glyph = (char)(glyph - 'a' + 'A');
    if (glyph >= 'A' && glyph <= 'Z') return letter_font_index[glyph - 'A'];
    if (glyph >= '0' && glyph <= '9') return (unsigned char)(19 + glyph - '0');
    if (glyph == '/') return 29u;
    if (glyph == ':') return 30u;
    if (glyph == '.') return 31u;
    return STATIC_LAYER_FONT_COUNT;
}

#ifndef CADENCE_PROBE
static void build_text_line(unsigned char* output, const char* text)
#define TEXT_OUTPUT output
#else
static void build_text_line(const char* text)
#define TEXT_OUTPUT HUD_DATA
#endif
{
    unsigned char row;
    unsigned char c;
    unsigned char column;
    unsigned char bits;
    unsigned char byte;
    unsigned char pixel;
    unsigned char index;
    unsigned char length;
    unsigned char pixel_bytes;

    length = 0u;
    while (length < 20u && text[length] != '\0') ++length;
    /* Each glyph occupies STATIC_LAYER_FONT_WIDTH pixel columns plus 1
     * transparent spacer column (kerning). */
    pixel_bytes = (unsigned char)
        (((unsigned int)length * (STATIC_LAYER_FONT_WIDTH + 1u) + 7u) / 8u);

    byte = 0u;
    for (row = 0u; row < STATIC_LAYER_FONT_HEIGHT; ++row) {
        TEXT_OUTPUT[byte++] = (unsigned char)(pixel_bytes + 1u);
        for (pixel = 0u; pixel < pixel_bytes; ++pixel) {
            TEXT_OUTPUT[byte + pixel] = 0u;
        }
        pixel = 0u;
        for (c = 0u; c < length; ++c) {
            index = text_font_index(text[c]);
            bits = index < STATIC_LAYER_FONT_COUNT ?
                static_layer_font_bits[index *
                    STATIC_LAYER_FONT_HEIGHT + row] : 0u;
            for (column = 0u; column < STATIC_LAYER_FONT_WIDTH; ++column) {
                if ((bits & (unsigned char)(16u >> column)) != 0u) {
                    TEXT_OUTPUT[byte + pixel / 8u] |=
                        (unsigned char)(0x80u >> (pixel & 7u));
                }
                ++pixel;
            }
            ++pixel;
        }
        byte = (unsigned char)(byte + pixel_bytes);
    }
    TEXT_OUTPUT[byte] = 0u;
}
#undef TEXT_OUTPUT

/* v048 (see .briefs/APS-053/v047.md, Fable5 design review): append_hud's
 * text is always a fixed 20-character line, so build_text_line's full
 * 700-iteration (7 rows x 20 chars x 5 columns) rebuild -- gate(a)'s
 * largest single measured cost at 7.28VBlank/72% of the frame -- redrew
 * every glyph every frame regardless of whether it changed. This block
 * replaces that path (for HUD only) with per-cell diffing against the
 * previous frame's text: only glyphs that actually changed are
 * re-blitted (typically 0-2 cells/frame, e.g. the countdown timer's last
 * digit). build_text_line itself is untouched and still used by
 * static_layer_text() (WARNING/GAME OVER/etc., variable-length, not a
 * per-frame hot path).
 *
 * Cell layout, Path B (see .briefs/APS-053/v048.md, Fable5 design
 * review): a first cut at 6px/cell (build_text_line's own pitch) put 2
 * of every 4 cells straddling a byte boundary, needing a 4-way switch of
 * read-modify-write bit ops per cell -- +776B of CODE, mostly that
 * switch (measured, not the diffing approach itself). Re-laid the HUD
 * out at 8px/cell instead: 20 cells x 8px = 160px = the full screen
 * width, so every cell owns one whole byte -- no straddling, no RMW, no
 * per-cell offset table. Each cell's glyph occupies the byte's upper 5
 * bits (bit7..bit3, matching build_text_line's column0..column4
 * MSB-first order) with the lower 3 bits as a wider spacer. Row stride
 * is HUD_ROW_BYTES = 1 header + 20 pixel bytes = 21; the full buffer is
 * 7*21+1 = 148 bytes (was 113 at 6px/cell), still inside
 * title_voice_scratch_buffer's HUD_DATA span (scratch+483..631 of 640
 * available -- see HUD_DATA's definition above).
 *
 * Visual change (user-approved, .briefs/APS-053/v048.md): character
 * spacing widens from 1px to 3px and the HUD line now spans the full
 * screen width (append_hud's append_scb call below moved from x=2 to
 * x=0 accordingly) instead of 120px starting at x=2. */
#define HUD_TEXT_LENGTH 20u
#define HUD_ROW_BYTES 21u  /* 1 header byte + 20 pixel bytes (8px/cell) */

/* v049 (Fable5 design review): static instead of a stack-local `char
 * text[21]` inside append_hud, for three compounding reasons verified by
 * function-size measurement: (1) the 7 constant cells baked in below
 * ('S'/' '/'L'/'W'/etc.) never need rewriting every frame -- 8 removed
 * assignments; (2) every hud_text[i] access compiles to absolute
 * addressing instead of stack-relative, shrinking each digit-loop store
 * and the function's stack frame; (3) the unscored-frame restore-copy
 * that used to pull hud_prev_text[9..13] back into a fresh local buffer
 * is gone entirely -- hud_text already still holds last frame's score
 * digits because nothing local resets it. The initializer's layout must
 * match append_hud's field assignments exactly (see that function). */
static char hud_text[HUD_TEXT_LENGTH + 1u] = "S0 N0000 00000 L0 W0";
static char hud_prev_text[HUD_TEXT_LENGTH + 1u];
/* 0 forces a full rebuild on the next append_hud call: startup, and any
 * frame where static_layer_draw's voice-idle guard skipped drawing (the
 * shared scratch buffer HUD_DATA aliases may have been reused for voice
 * playback in the meantime -- see static_layer_draw). */
static unsigned char hud_prev_valid;
static unsigned long hud_prev_score;

static void hud_rebuild_skeleton(void)
{
    unsigned char row;
    unsigned char* p = HUD_DATA;

    memset(p, 0, (unsigned int)HUD_ROW_BYTES * STATIC_LAYER_FONT_HEIGHT +
        1u);
    for (row = 0u; row < STATIC_LAYER_FONT_HEIGHT; ++row) {
        *p = (unsigned char)HUD_ROW_BYTES;
        p += HUD_ROW_BYTES;
    }
}

static void write_hud_cell(unsigned char cell, char glyph)
{
    unsigned char row;
    unsigned char index;
    unsigned char* dst;

    index = text_font_index(glyph);
    dst = HUD_DATA + 1u + cell;
    for (row = 0u; row < STATIC_LAYER_FONT_HEIGHT; ++row) {
        *dst = index < STATIC_LAYER_FONT_COUNT ?
            (unsigned char)(static_layer_font_bits[index *
                STATIC_LAYER_FONT_HEIGHT + row] << 3) : 0u;
        dst += HUD_ROW_BYTES;
    }
}

/* v049 (see .briefs/APS-053/v049.md, Fable5 design review): indexed by
 * GAME_PHASE_* (0..6, contiguous), replacing a 5-branch ternary chain
 * that reloaded and compared game->phase at every step (~96B measured)
 * with a single load + table lookup + store (~15B) at the one call site
 * that needs it. GAME_PHASE_TITLE (6) never reaches append_hud (draw_game
 * returns before calling static_layer_draw(game, ...) when
 * game->phase == GAME_PHASE_TITLE), but the table still covers all 7
 * values so an out-of-range read is structurally impossible rather than
 * relying on that invariant. */
static const char hud_phase_char[7] = { 'I', 'N', 'W', 'B', 'C', 'A', 'A' };

static void append_hud(const GameState* game)
{
    unsigned char i;
    unsigned int timer_value;

    /* Score's decimal digits require an unsigned long (32-bit) division/
     * modulo chain (5 iterations); v047 Fable5 review measured this at
     * ~4-5% of append_hud's pre-optimization cost -- worth skipping when
     * the score hasn't changed since last frame (it changes on kills/
     * pickups, not every frame). hud_text being static (see its
     * declaration) means the digits from the last time the score did
     * change are simply still sitting there; no restore-copy needed. */
    if (game->score != hud_prev_score) {
        unsigned long score_value = game->score;

        for (i = 5u; i != 0u; --i) {
            hud_text[8u + i] = (char)('0' + score_value % 10ul);
            score_value /= 10ul;
        }
        hud_prev_score = game->score;
    }
    timer_value = game->phase_timer;
    for (i = 4u; i != 0u; --i) {
        hud_text[3u + i] = (char)('0' + timer_value % 10u);
        timer_value /= 10u;
    }
    /* hud_text[0]='S', [2]=' ', [8]=' ', [14]=' ', [15]='L', [17]=' ',
     * [18]='W' are baked into hud_text's static initializer below and
     * never need rewriting -- they can't change. */
    hud_text[1] = (char)('0' + game->stage);
    hud_text[3] = hud_phase_char[game->phase];
    hud_text[16] = (char)('0' + game->lives);
    hud_text[19] = (char)('0' + game->weapon_level);

    if (hud_prev_valid == 0u) {
        hud_rebuild_skeleton();
        for (i = 0u; i < HUD_TEXT_LENGTH; ++i) {
            write_hud_cell(i, hud_text[i]);
        }
        hud_prev_valid = 1u;
    } else {
        for (i = 0u; i < HUD_TEXT_LENGTH; ++i) {
            if (hud_text[i] != hud_prev_text[i]) {
                write_hud_cell(i, hud_text[i]);
            }
        }
    }
    memcpy(hud_prev_text, hud_text, HUD_TEXT_LENGTH + 1u);

    append_scb(HUD_DATA, 0, 2, WHITE);
    SCBS[scb_count - 1u].sprctl1 = (unsigned char)(LITERAL | REHV);
    append_scb(static_layer_clear_data, 0, GAME_HUD_HEIGHT - 1u, NEAR_STAR);
}

static const unsigned char* title_text_data(unsigned char id)
{
    switch (id) {
    case 0u:
        return static_layer_overlay_buffer +
            STATIC_LAYER_OVERLAY_TEXT_ASTEROID_PATROL_OFFSET;
    case 1u:
        return static_layer_overlay_buffer +
            STATIC_LAYER_OVERLAY_TEXT_AB_TO_START_OFFSET;
    case 2u:
        return static_layer_overlay_buffer +
            STATIC_LAYER_OVERLAY_TEXT_ARROWS_MOVE_OFFSET;
    case 3u:
        return static_layer_overlay_buffer +
            STATIC_LAYER_OVERLAY_TEXT_AB_FIRE_OFFSET;
    default:
        return static_layer_overlay_buffer +
            STATIC_LAYER_OVERLAY_TEXT_VOICEVOX_NEMO_OFFSET;
    }
}

static void append_text_data(const unsigned char* data, int x, int y,
    unsigned char color)
{
    append_scb(data, x, y, color);
    SCBS[scb_count - 1u].sprctl1 = (unsigned char)(LITERAL | REHV);
}

void static_layer_title_text(int x, int y, unsigned char id,
    unsigned char color)
{
    STATIC_LAYER_REQUIRE_VOICE_IDLE();
    if (title_voice_is_playing() != 0u) return;
    append_text_data(title_text_data(id), x, y, color);
}

void static_layer_text(int x, int y, const char* text, unsigned char color)
{
    /* The first 539 bytes of title_voice_scratch_buffer are SCB/HUD storage.
     * The main loop never draws while a voice stream is pumping; keep a
     * runtime guard so a future caller cannot race the shared storage. */
    STATIC_LAYER_REQUIRE_VOICE_IDLE();
    if (title_voice_is_playing() != 0u) return;
#ifndef CADENCE_PROBE
    if (title_text_queue != 0u && text_layer_buffer_index >= 2u) return;
    /* v048: static_layer_text() reuses HUD_DATA itself whenever this is
     * the first queued string this layer (text_layer_buffer_index==0,
     * always true for in-game overlays like WARNING/STAGE CLEAR since
     * title_text_queue==0 there, see draw_phase_overlay in main.c) --
     * that overwrites whatever append_hud last wrote there. Force the
     * next append_hud call to rebuild every cell instead of diffing
     * against hud_prev_text, which would otherwise believe (correctly,
     * from its own point of view) that nothing changed and leave this
     * overlay's leftover bytes on screen. See append_hud. */
    if (text_layer_buffer_index == 0u) hud_prev_valid = 0u;
    build_text_line(text_layer_buffer_index == 0u ? HUD_DATA :
        HUD_DATA_SECOND, text);
#else
    /* CADENCE_PROBE always reuses HUD_DATA here (no second buffer, see
     * the HUD_DATA_SECOND comment above) -- same reasoning as above. */
    hud_prev_valid = 0u;
    build_text_line(text);
#endif
    if (title_text_queue == 0u) {
        begin_layer();
        append_text_data(HUD_DATA, x, y, color);
        finish_layer();
        return;
    }
    if (text_layer_started == 0u) {
        begin_layer();
        text_layer_started = 1u;
    }
#ifndef CADENCE_PROBE
    append_text_data(text_layer_buffer_index == 0u ? HUD_DATA :
        HUD_DATA_SECOND, x, y, color);
    ++text_layer_buffer_index;
#else
    append_text_data(HUD_DATA, x, y, color);
#endif
}

void static_layer_text_flush(void)
{
    STATIC_LAYER_REQUIRE_VOICE_IDLE();
    if (title_text_queue == 0u || text_layer_started == 0u) return;
    finish_layer();
    text_layer_started = 0u;
}

void static_layer_draw(const GameState* game, unsigned char theme_id)
{
    /* See static_layer.h: voice playback owns the shared scratch buffer. */
    STATIC_LAYER_REQUIRE_VOICE_IDLE();
    if (title_voice_is_playing() != 0u) {
        /* HUD_DATA (part of the shared scratch buffer) may have been
         * reused for voice playback while drawing was skipped; force
         * append_hud's next call to rebuild every cell instead of
         * diffing against stale hud_prev_text (v048, see append_hud). */
        hud_prev_valid = 0u;
        return;
    }
    title_text_queue = game == 0 ? 1u : 0u;
    text_layer_started = 0u;
    if (game == 0) {
        ensure_overlay(STATIC_LAYER_OVERLAY_TITLE);
    } else if (theme_id == SKY) {
        ensure_overlay(STATIC_LAYER_OVERLAY_STAGE2);
    } else if (theme_id == CAVE) {
        ensure_overlay(STATIC_LAYER_OVERLAY_STAGE3);
    } else {
        ensure_overlay(STATIC_LAYER_OVERLAY_STAGE1);
    }
    begin_layer();
    append_scb(static_layer_clear_data, 0, 0, BLACK);
    SCBS[0].sprctl0 = (unsigned char)(BPP_1 | TYPE_BACKNONCOLL);
    SCBS[0].hsize = (unsigned int)(GAME_SCREEN_WIDTH << 8);
    SCBS[0].vsize = (unsigned int)(GAME_SCREEN_HEIGHT << 8);
#ifdef CADENCE_PROBE
    static_layer_split_marker_after_overlay_and_clear();
#endif
    if (game == 0) {
        /* TITLE text is appended to the clear SCB and submitted once at the
         * display boundary, keeping the calibration path to one Suzy list. */
        text_layer_started = 1u;
        return;
    }
    if (theme_id == SKY) append_scroll_layers(game, sky_layers);
    else if (theme_id == CAVE) append_scroll_layers(game, cave_layers);
    else append_space(game);
#ifdef CADENCE_PROBE
    static_layer_split_marker_after_background();
#endif
    append_hud(game);
    finish_layer();
}

void static_layer_credit_suffix(int x, int y, unsigned char color)
{
    const unsigned char* suffix_data = static_layer_overlay_buffer +
        STATIC_LAYER_OVERLAY_TEXT_VOICEVOX_SUFFIX_OFFSET;

    STATIC_LAYER_REQUIRE_VOICE_IDLE();
    if (title_voice_is_playing() != 0u) return;
    if (title_text_queue == 0u) {
        begin_layer();
        append_scb(suffix_data, x, y, color);
        SCBS[scb_count - 1u].sprctl1 = (unsigned char)(LITERAL | REHV);
        finish_layer();
        return;
    }
    append_scb(suffix_data, x, y, color);
    SCBS[scb_count - 1u].sprctl1 = (unsigned char)(LITERAL | REHV);
}
