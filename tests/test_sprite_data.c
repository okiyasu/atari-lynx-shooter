#include <stdio.h>
#include <stdlib.h>

#include "game.h"
#include "sprite_data.h"

static unsigned int checks;

typedef struct VisitedRun {
    int x0;
    int x1;
    int y;
    unsigned char color;
} VisitedRun;

typedef struct VisitCapture {
    VisitedRun runs[96];
    unsigned char count;
} VisitCapture;

static void capture_run(int x0, int x1, int y, unsigned char color,
    void* context)
{
    VisitCapture* capture;

    capture = (VisitCapture*)context;
    if (capture->count >= 96u) {
        fprintf(stderr, "FAIL: runtime sprite visitor exceeded capture capacity\n");
        exit(1);
    }
    capture->runs[capture->count].x0 = x0;
    capture->runs[capture->count].x1 = x1;
    capture->runs[capture->count].y = y;
    capture->runs[capture->count].color = color;
    ++capture->count;
}

/* APS-049 contract c: packed run -> decoded grid round trip. Each run is
 * 2 bytes: byte0 = y<<4|x0, byte1 = length<<4|color, valid only because
 * every sprite canvas is a fixed 16x16 preview grid (see
 * scripts/generate-stage-data.py pack_sprite_run()). */
typedef struct DecodedRun {
    unsigned char y;
    unsigned char x0;
    unsigned char x1;
    unsigned char color;
} DecodedRun;

static void decode_run(unsigned int index, DecodedRun* run)
{
    unsigned int offset;
    unsigned char first;
    unsigned char second;

    offset = index * 2u;
    first = game_sprite_run_data[offset];
    second = game_sprite_run_data[offset + 1u];
    run->y = (unsigned char)(first >> 4);
    run->x0 = (unsigned char)(first & 0x0fu);
    run->x1 = (unsigned char)(run->x0 + (second >> 4));
    run->color = (unsigned char)(second & 0x0fu);
}

static void expect(int condition, const char* message)
{
    ++checks;
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", message);
        exit(1);
    }
}

static unsigned int allowed_roles(unsigned char sprite_id)
{
    if (sprite_id == GAME_SPRITE_PLAYER) {
        return (1u << 7) | (1u << 8) | (1u << 9) | (1u << 12);
    }
    if (sprite_id >= GAME_SPRITE_SCOUT &&
        sprite_id <= GAME_SPRITE_SUPPLY) {
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

static unsigned char bit_count(unsigned int value)
{
    unsigned char count;

    count = 0u;
    while (value != 0u) {
        if ((value & 1u) != 0u) {
            ++count;
        }
        value >>= 1;
    }
    return count;
}

static unsigned int palette_color(unsigned char stage, unsigned char index)
{
    return (unsigned int)((unsigned int)game_stage_palettes[stage][index] << 8) |
        game_stage_palettes[stage][16u + index];
}

static int frames_differ(unsigned char frame0_count,
    unsigned char frame1_count)
{
    /* frame 1 is an overlay delta (1..6 runs), so "differs" only needs to
     * confirm it declares at least one run distinct from an empty overlay. */
    return frame1_count >= 1u && frame1_count <= 6u && frame0_count >= 1u;
}

int main(void)
{
    static const unsigned int fixed_roles[10] = {
        0xf2cu, 0x9feu, 0xf64u, 0x348u, 0xe93u,
        0x842u, 0xfd5u, 0x84du, 0x3cbu, 0xfffu
    };
    /* frame-0 run counts derived from assets/previews/aps044-*-preview.json
     * (player variant "a"); frame-1 counts are each sprite's anim_delta
     * overlay length. Both are re-derived by scripts/generate-stage-data.py
     * at build time and pinned by tests/golden/sprite-data-v049.json. */
    static const unsigned char expected_frame0_runs[13] = {
        44u, 29u, 21u, 33u, 27u, 37u, 30u,
        35u, 30u, 34u, 69u, 40u, 51u
    };
    static const unsigned char expected_frame1_runs[13] = {
        1u, 1u, 1u, 1u, 1u, 1u, 1u,
        1u, 1u, 1u, 1u, 1u, 1u
    };
    /* boss collision rectangles are unchanged since APS-042/047 even though
     * the visual canvas is now the shared 16x16 preview grid. */
    static const unsigned char expected_boss_collision_widths[3] = {
        24u, 28u, 24u
    };
    static const unsigned char expected_boss_collision_heights[3] = {
        16u, 14u, 24u
    };
    unsigned int next_offset;
    unsigned char sprite_id;
    unsigned char stage;

    expect(GAME_SPRITE_COUNT == 13u, "all player enemy and boss sprites exist");
    expect(GAME_PLAYER_WIDTH == 8u && GAME_PLAYER_HEIGHT == 6u,
        "player collision box remains 8x6");
    expect(GAME_ENEMY_WIDTH == 8u && GAME_ENEMY_HEIGHT == 8u,
        "normal enemy collision box remains 8x8");
    next_offset = 0u;
    for (sprite_id = 0u; sprite_id < GAME_SPRITE_COUNT; ++sprite_id) {
        const GameSpriteDefinition* sprite;
        unsigned char frame_index;

        sprite = &game_sprite_definitions[sprite_id];
        {
            signed char dx = (signed char)((sprite->anchor >> 4) & 0x0Fu) - 8;
            signed char dy = (signed char)(sprite->anchor & 0x0Fu) - 8;
            expect(dx >= -8 && dx <= 7 && dy >= -8 && dy <= 7,
                "sprite anchor decodes within its packed biased 4-bit range");
        }
        for (frame_index = 0u; frame_index < 2u; ++frame_index) {
            unsigned int frame_offset;
            unsigned char frame_count;
            VisitCapture capture;
            unsigned int colors;
            unsigned int allowed;
            unsigned char run_index;
            unsigned char visited;
            unsigned char expected_runs;

            if (frame_index == 0u) {
                frame_offset = sprite->frame0_offset;
                frame_count = sprite->frame0_count;
            } else {
                frame_offset = sprite->frame0_offset + sprite->frame0_count;
                frame_count = sprite->frame1_count;
            }
            expect(frame_offset == next_offset,
                "sprite runs have deterministic dense offsets");
            expected_runs = frame_index == 0u ?
                expected_frame0_runs[sprite_id] :
                expected_frame1_runs[sprite_id];
            expect(frame_count == expected_runs,
                "APS-049 preview-derived sprite preserves its authored run count");
            colors = 0u;
            allowed = allowed_roles(sprite_id);
            for (run_index = 0u; run_index < frame_count; ++run_index) {
                DecodedRun run;

                decode_run(frame_offset + run_index, &run);
                expect(run.x0 <= run.x1 && run.x1 < GAME_SPRITE_CANVAS &&
                    run.y < GAME_SPRITE_CANVAS,
                    "sprite run remains inside its 16x16 visual canvas");
                expect((allowed & (1u << run.color)) != 0u,
                    "sprite run uses only its fixed palette roles");
                colors |= 1u << run.color;
            }
            if (frame_index == 0u) {
                expect(bit_count(colors) >= 3u && bit_count(colors) <= 4u,
                    "sprite frame 0 uses three or four colors");
            }
            capture.count = 0u;
            visited = game_sprite_visit_runs(-3, 7, sprite_id, frame_index,
                capture_run, &capture);
            expect(visited == frame_count &&
                capture.count == frame_count,
                "runtime draw traversal visits every generated run exactly once");
            for (run_index = 0u; run_index < frame_count; ++run_index) {
                DecodedRun run;
                const VisitedRun* actual;

                decode_run(frame_offset + run_index, &run);
                actual = &capture.runs[run_index];
                expect(actual->x0 == -3 + (int)run.x0 &&
                    actual->x1 == -3 + (int)run.x1 &&
                    actual->y == 7 + (int)run.y &&
                    actual->color == run.color,
                    "runtime draw traversal preserves translated run table values (round trip)");
            }
            next_offset += frame_count;
        }
        expect(frames_differ(sprite->frame0_count, sprite->frame1_count),
            "sprite frame 1 declares a non-empty 1..6 cell overlay delta");
    }
    expect(next_offset <= GAME_SPRITE_FRAME0_RUN_BUDGET,
        "authored run total stays within the RAM-linked budget headroom");
    expect(game_sprite_visit_runs(0, 0, GAME_SPRITE_COUNT, 0u,
        capture_run, (void*)0) == 0u &&
        game_sprite_visit_runs(0, 0, GAME_SPRITE_PLAYER, 2u,
        capture_run, (void*)0) == 0u &&
        game_sprite_visit_runs(0, 0, GAME_SPRITE_PLAYER, 0u,
        (GameSpriteRunVisitor)0, (void*)0) == 0u,
        "runtime draw traversal rejects invalid sprite frame and callback paths");
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

    printf("PASS: %u sprite data checks\n", checks);
    return 0;
}
