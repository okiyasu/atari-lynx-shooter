#include <stdio.h>
#include <stdlib.h>

#include "game.h"
#include "sprite_data.h"

/* _suzy.h SPRCTL0 bpp bits, duplicated here (host build has no lynx.h)
 * to decode game_sprite_definitions[].sprctl0 for the checks below. Must
 * stay in sync with scripts/generate-stage-data.py SPRITE_SPRCTL0_BY_BPP. */
#define BPP_4 0xC0u
#define BPP_3 0x80u
#define BPP_2 0x40u
#define BPP_1 0x00u
#define TYPE_NONCOLL 0x05u

static unsigned int checks;

static void expect(int condition, const char* message)
{
    ++checks;
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", message);
        exit(1);
    }
}

static unsigned char sprctl0_bpp(unsigned char sprctl0)
{
    switch (sprctl0 & 0xC0u) {
    case BPP_4: return 4u;
    case BPP_2: return 2u;
    case BPP_1: return 1u;
    default: return 0u;
    }
}

/* APS-053 Phase 3R: pixel value v (1-based) selects penpal[v>>1], the low
 * nibble if v is odd, the high nibble if even (src/static_layer.c reset_scb
 * comment; scripts/generate-stage-data.py pack_sprite_penpal). Decodes the
 * up to 4 real colors a sprite's packed bitmap can reference back out of
 * its 3-byte penpal table, stopping at the first unused (zero) slot -- 0 is
 * always transparent/pixel-value-0 and never itself an authored color
 * (see allowed_roles: no sprite kind's role set includes '0'). */
static unsigned char decode_penpal(const unsigned char* penpal,
    unsigned char* colors)
{
    unsigned char v;
    unsigned char count;
    unsigned char color;

    count = 0u;
    for (v = 1u; v <= 4u; ++v) {
        color = (v & 1u) ? (unsigned char)(penpal[v >> 1] & 0x0Fu) :
            (unsigned char)((penpal[v >> 1] >> 4) & 0x0Fu);
        if (color == 0u) {
            break;
        }
        colors[count++] = color;
    }
    return count;
}

/* Walks one Suzy PACKED-bitmap byte stream far enough to confirm it is
 * well-formed and self-terminating (scripts/generate-static-layer.py
 * encode_packed: each row is prefixed by its own byte length + 1, and the
 * stream ends with a single 0 row-length byte), without decoding pixels --
 * doing that would require re-deriving the source preview grid in C, which
 * duplicates the golden-hash-protected Python authoring data for no extra
 * safety here. Returns the number of bytes consumed (including the final
 * terminator), or 0 if the stream runs past `limit` bytes without
 * terminating. */
static unsigned int packed_stream_length(const unsigned char* data,
    unsigned int limit)
{
    unsigned int offset;
    unsigned char row_length;

    offset = 0u;
    for (;;) {
        if (offset >= limit) {
            return 0u;
        }
        row_length = data[offset];
        if (row_length == 0u) {
            return offset + 1u;
        }
        offset = (unsigned int)(offset + row_length);
    }
}

static unsigned int palette_color(unsigned char stage, unsigned char index)
{
    return (unsigned int)((unsigned int)game_stage_palettes[stage][index] << 8) |
        game_stage_palettes[stage][16u + index];
}

static unsigned int allowed_roles(unsigned char sprite_id)
{
    if (sprite_id == GAME_SPRITE_PLAYER) {
        return (1u << 7) | (1u << 8) | (1u << 9) | (1u << 12);
    }
    if (sprite_id >= GAME_SPRITE_SCOUT && sprite_id <= GAME_SPRITE_SUPPLY) {
        return (1u << 10) | (1u << 11) | (1u << 12);
    }
    if (sprite_id >= GAME_SPRITE_CAVE_BAT &&
        sprite_id <= GAME_SPRITE_MINING_DRONE) {
        return (1u << 11) | (1u << 13) | (1u << 14);
    }
    if (sprite_id == GAME_SPRITE_VIOLET_GEODE) {
        return (1u << 11) | (1u << 13) | (1u << 14) | (1u << 15);
    }
    return (1u << 10) | (1u << 11) | (1u << 12) | (1u << 15);
}

int main(void)
{
    /* boss collision rectangles are unchanged since APS-042/047 even though
     * the visual canvas is now the shared 16x16 preview grid. */
    static const unsigned char expected_boss_collision_widths[3] = {
        24u, 28u, 24u
    };
    static const unsigned char expected_boss_collision_heights[3] = {
        16u, 14u, 24u
    };
    /* Expected bpp per sprite, pinned by
     * verify-phase-3r-sprite-bpp-gate.py's confirmed Phase 3R gate numbers
     * (all previews use 3-4 authored colors, never enough for 1bpp; see
     * .briefs/APS-053/v036.md item 1: 2bpp x 9, 4bpp x 4, 1bpp x 0). */
    static const unsigned char expected_bpp[13] = {
        4u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 2u, 4u, 4u, 4u
    };
    static const unsigned int fixed_roles[10] = {
        0xf2cu, 0x9feu, 0xf64u, 0x348u, 0xe93u,
        0x842u, 0xfd5u, 0x84du, 0x3cbu, 0xfffu
    };
    unsigned char sprite_id;
    unsigned char stage;
    unsigned int next_offset;

    expect(GAME_SPRITE_COUNT == 13u, "all player enemy and boss sprites exist");
    expect(GAME_PLAYER_WIDTH == 8u && GAME_PLAYER_HEIGHT == 6u,
        "player collision box remains 8x6");
    expect(GAME_ENEMY_WIDTH == 8u && GAME_ENEMY_HEIGHT == 8u,
        "normal enemy collision box remains 8x8");

    next_offset = 0u;
    for (sprite_id = 0u; sprite_id < GAME_SPRITE_COUNT; ++sprite_id) {
        const GameSpriteDefinition* sprite;
        unsigned char colors[4];
        unsigned char color_count;
        unsigned char i;
        unsigned int allowed;
        unsigned int frame0_length;
        unsigned int frame1_length;
        signed char dx;
        signed char dy;

        sprite = &game_sprite_definitions[sprite_id];

        dx = (signed char)((sprite->anchor >> 4) & 0x0Fu) - 8;
        dy = (signed char)(sprite->anchor & 0x0Fu) - 8;
        expect(dx >= -8 && dx <= 7 && dy >= -8 && dy <= 7,
            "sprite anchor decodes within its packed biased 4-bit range");

        expect((sprite->sprctl0 & TYPE_NONCOLL) == TYPE_NONCOLL,
            "sprite sprctl0 always requests non-colliding sprite type");
        expect(sprctl0_bpp(sprite->sprctl0) == expected_bpp[sprite_id],
            "sprite bpp matches the confirmed Phase 3R gate assignment");

        color_count = decode_penpal(sprite->penpal, colors);
        expect(color_count >= 3u && color_count <= 4u,
            "sprite penpal decodes three or four non-transparent colors");
        allowed = allowed_roles(sprite_id);
        for (i = 0u; i < color_count; ++i) {
            expect((allowed & (1u << colors[i])) != 0u,
                "sprite penpal uses only its fixed palette roles");
        }

        expect(sprite->frame0_offset == next_offset,
            "sprite frame 0 starts immediately after the previous sprite's data");
        frame0_length = packed_stream_length(
            game_sprite_packed_data + sprite->frame0_offset,
            GAME_SPRITE_PACKED_DATA_LENGTH - sprite->frame0_offset);
        expect(frame0_length != 0u,
            "sprite frame 0 packed bitmap is well-formed and self-terminating");
        expect(sprite->frame1_offset == sprite->frame0_offset + frame0_length,
            "sprite frame 1 starts immediately after frame 0's packed bytes");
        frame1_length = packed_stream_length(
            game_sprite_packed_data + sprite->frame1_offset,
            GAME_SPRITE_PACKED_DATA_LENGTH - sprite->frame1_offset);
        expect(frame1_length != 0u,
            "sprite frame 1 packed bitmap is well-formed and self-terminating");

        next_offset = sprite->frame1_offset + frame1_length;
    }
    expect(next_offset == GAME_SPRITE_PACKED_DATA_LENGTH,
        "every packed byte belongs to exactly one sprite frame, none stray");

    for (sprite_id = 0u; sprite_id < 9u; ++sprite_id) {
        expect(game_enemy_sprite_ids[sprite_id] == sprite_id + 1u,
            "engine enemy type maps to its generated sprite id");
    }
    expect(game_boss_sprite_ids[0] == GAME_SPRITE_INVALID &&
        game_boss_sprite_ids[1] == GAME_SPRITE_CORAL_BASTION &&
        game_boss_sprite_ids[2] == GAME_SPRITE_AMBER_CARRIER &&
        game_boss_sprite_ids[3] == GAME_SPRITE_VIOLET_GEODE,
        "boss appearance ids map to generated colored sprites");

    for (stage = 0u; stage < GAME_STAGE_COUNT; ++stage) {
        const GameBossConfig* boss;
        unsigned char appearance;
        unsigned char boss_sprite;

        boss = &game_boss_configs[game_stage_configs[stage].boss_config_id];
        appearance = game_stage_configs[stage].boss_appearance_id;
        boss_sprite = game_boss_sprite_ids[appearance];
        expect(boss_sprite != GAME_SPRITE_INVALID &&
            boss->width ==
                expected_boss_collision_widths[boss_sprite - GAME_SPRITE_CORAL_BASTION] &&
            boss->height ==
                expected_boss_collision_heights[boss_sprite - GAME_SPRITE_CORAL_BASTION],
            "boss collision box is unchanged since APS-042/047");
    }

    for (stage = 0u; stage < GAME_STAGE_COUNT; ++stage) {
        unsigned char role;

        for (role = 0u; role < 10u; ++role) {
            expect(palette_color(stage, (unsigned char)(role + 6u)) ==
                fixed_roles[role],
                "all stages preserve the fixed gameplay palette roles");
        }
        expect(palette_color(stage, 0u) != palette_color(stage, 1u) &&
            palette_color(stage, 1u) != palette_color(stage, 2u),
            "stage theme provides six authored background colors");
    }

    printf("PASS: %u sprite data checks\n", checks);
    return 0;
}
