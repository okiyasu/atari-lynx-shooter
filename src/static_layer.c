#include <lynx.h>
#ifdef STATIC_LAYER_DEBUG_ASSERT
#include <assert.h>
#endif
#include <string.h>
#include <tgi.h>

#include "game.h"
#include "static_layer.h"
#include "static_layer_data.h"
#include "title_voice.h"

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
    if (scb_count != 0u) tgi_sprite(SCBS);
}

static void append_space(const GameState* game)
{
    int x;
    unsigned char i;

    x = (int)GAME_PLANET_BASE_X - (int)game->planet_offset;
    if (x < -(int)GAME_PLANET_WIDTH) x += (int)GAME_PLANET_SCROLL_PERIOD;
    append_scb(static_layer_planet_data, x, GAME_PLANET_BASE_Y, PLANET);
    SCBS[scb_count - 1u].sprctl0 = (unsigned char)(BPP_2 | TYPE_NONCOLL);
    SCBS[scb_count - 1u].penpal[1] =
        (unsigned char)(PLANET_DETAIL << 4);
    for (i = 0u; i < STATIC_LAYER_FAR_STAR_COUNT; ++i) {
        x = (int)static_layer_far_star_x[i] -
            (int)game->far_star_offset;
        if (x < 0) x += GAME_SCREEN_WIDTH;
        append_scb(static_layer_space_far_star_data, x,
            static_layer_far_star_y[i], FAR_STAR);
    }
    for (i = 0u; i < STATIC_LAYER_NEAR_STAR_COUNT; ++i) {
        x = (int)static_layer_near_star_x[i] -
            (int)game->near_star_offset;
        if (x < 0) x += GAME_SCREEN_WIDTH;
        append_scb(static_layer_near_star_data, x,
            static_layer_near_star_y[i], NEAR_STAR);
    }
}

typedef struct StaticScrollLayer {
    const unsigned char* data;
    unsigned char y;
    unsigned char color;
    unsigned char offset_kind;
    unsigned int period;
} StaticScrollLayer;

static const StaticScrollLayer sky_layers[3] = {
    { static_layer_mountain_data, STATIC_LAYER_MOUNTAIN_Y_OFFSET,
        MOUNTAIN, 0u, GAME_PLANET_SCROLL_PERIOD },
    { static_layer_mid_cloud_data, STATIC_LAYER_MID_CLOUD_Y_OFFSET,
        MID_CLOUD, 1u, GAME_SCREEN_WIDTH },
    { static_layer_near_cloud_data, STATIC_LAYER_NEAR_CLOUD_Y_OFFSET,
        NEAR_CLOUD, 2u, GAME_SCREEN_WIDTH }
};

static const StaticScrollLayer cave_layers[3] = {
    { static_layer_cave_wall_data, STATIC_LAYER_CAVE_WALL_Y_OFFSET,
        CAVE_SHADOW, 0u, GAME_PLANET_SCROLL_PERIOD },
    { static_layer_cave_rock_data, STATIC_LAYER_CAVE_ROCK_Y_OFFSET,
        CAVE_ROCK, 1u, GAME_SCREEN_WIDTH },
    { static_layer_cave_near_data, STATIC_LAYER_CAVE_NEAR_Y_OFFSET,
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
        append_repeat(layers[i].data, -(int)offset, layers[i].y,
            layers[i].color, layers[i].period);
    }
}

static unsigned char glyph_index(char glyph)
{
    if (glyph >= '0' && glyph <= '9') return (unsigned char)(glyph - '0');
    if (glyph == 'S') return 10u;
    if (glyph == 'I') return 11u;
    if (glyph == 'N') return 12u;
    if (glyph == 'W') return 13u;
    if (glyph == 'B') return 14u;
    if (glyph == 'C') return 15u;
    if (glyph == 'A') return 16u;
    return 17u;
}

static void build_hud(const char* text)
{
    unsigned char row;
    unsigned char c;
    unsigned char column;
    unsigned char bits;
    unsigned char byte;
    unsigned char pixel;

    byte = 0u;
    for (row = 0u; row < 5u; ++row) {
        HUD_DATA[byte++] = 11u;
        for (pixel = 0u; pixel < 10u; ++pixel) HUD_DATA[byte + pixel] = 0u;
        pixel = 0u;
        for (c = 0u; c < 20u; ++c) {
            bits = text[c] == ' ' ? 0u :
                static_layer_glyph_bits[glyph_index(text[c]) * 5u + row];
            for (column = 0u; column < 4u; ++column) {
                if (column != 3u &&
                    (bits & (unsigned char)(4u >> column)) != 0u) {
                    HUD_DATA[byte + pixel / 8u] |=
                        (unsigned char)(0x80u >> (pixel & 7u));
                }
                ++pixel;
            }
        }
        byte = (unsigned char)(byte + 10u);
    }
    HUD_DATA[byte] = 0u;
}

static void append_hud(const GameState* game)
{
    char text[21];
    unsigned char i;
    unsigned long score_value;
    unsigned int timer_value;

    score_value = game->score;
    for (i = 5u; i != 0u; --i) {
        text[8u + i] = (char)('0' + score_value % 10ul);
        score_value /= 10ul;
    }
    timer_value = game->phase_timer;
    for (i = 4u; i != 0u; --i) {
        text[3u + i] = (char)('0' + timer_value % 10u);
        timer_value /= 10u;
    }
    text[0] = 'S'; text[1] = (char)('0' + game->stage); text[2] = ' ';
    text[3] = game->phase == GAME_PHASE_NORMAL ? 'N' :
        game->phase == GAME_PHASE_BOSS ? 'B' :
        game->phase == GAME_PHASE_STAGE_INTRO ? 'I' :
        game->phase == GAME_PHASE_WARNING ? 'W' :
        game->phase == GAME_PHASE_STAGE_CLEAR ? 'C' : 'A';
    text[8] = ' ';
    text[14] = ' '; text[15] = 'L';
    text[16] = (char)('0' + game->lives); text[17] = ' '; text[18] = 'W';
    text[19] = (char)('0' + game->weapon_level); text[20] = '\0';
    build_hud(text);
    append_scb(HUD_DATA, 2, 2, WHITE);
    SCBS[scb_count - 1u].sprctl1 = (unsigned char)(LITERAL | REHV);
    append_scb(static_layer_clear_data, 0, GAME_HUD_HEIGHT - 1u, NEAR_STAR);
}

static unsigned char text_font_index(char glyph)
{
    if (glyph >= 'A' && glyph <= 'Z') return (unsigned char)(glyph - 'A');
    if (glyph >= 'a' && glyph <= 'z') return (unsigned char)(glyph - 'a');
    if (glyph >= '0' && glyph <= '9') return (unsigned char)(26 + glyph - '0');
    if (glyph == '/') return 36u;
    if (glyph == ':') return 37u;
    if (glyph == '.') return 38u;
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

static const unsigned char* title_text_data(unsigned char id)
{
    switch (id) {
    case 0u: return static_layer_text_asteroid_patrol_data;
    case 1u: return static_layer_text_ab_to_start_data;
    case 2u: return static_layer_text_arrows_move_data;
    case 3u: return static_layer_text_ab_fire_data;
    default: return static_layer_text_voicevox_nemo_data;
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
    build_text_line(text_layer_buffer_index == 0u ? HUD_DATA :
        HUD_DATA_SECOND, text);
#else
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
    if (title_voice_is_playing() != 0u) return;
    title_text_queue = game == 0 ? 1u : 0u;
    text_layer_started = 0u;
    begin_layer();
    append_scb(static_layer_clear_data, 0, 0, BLACK);
    SCBS[0].sprctl0 = (unsigned char)(BPP_1 | TYPE_BACKNONCOLL);
    SCBS[0].hsize = (unsigned int)(GAME_SCREEN_WIDTH << 8);
    SCBS[0].vsize = (unsigned int)(GAME_SCREEN_HEIGHT << 8);
    if (game == 0) {
        /* TITLE text is appended to the clear SCB and submitted once at the
         * display boundary, keeping the calibration path to one Suzy list. */
        text_layer_started = 1u;
        return;
    }
    if (theme_id == SKY) append_scroll_layers(game, sky_layers);
    else if (theme_id == CAVE) append_scroll_layers(game, cave_layers);
    else append_space(game);
    append_hud(game);
    finish_layer();
}

void static_layer_credit_suffix(int x, int y, unsigned char color)
{
    STATIC_LAYER_REQUIRE_VOICE_IDLE();
    if (title_voice_is_playing() != 0u) return;
    if (title_text_queue == 0u) {
        begin_layer();
        append_scb(static_layer_text_voicevox_suffix_data, x, y, color);
        SCBS[scb_count - 1u].sprctl1 = (unsigned char)(LITERAL | REHV);
        finish_layer();
        return;
    }
    append_scb(static_layer_text_voicevox_suffix_data, x, y, color);
    SCBS[scb_count - 1u].sprctl1 = (unsigned char)(LITERAL | REHV);
}
