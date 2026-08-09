#include <stdio.h>
#include <stdlib.h>

#include "game.h"
#include "sprite_data.h"

static unsigned int checks;

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
        return (1u << 7) | (1u << 8) | (1u << 9);
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

static int frames_differ(const GameSpriteFrame* first,
    const GameSpriteFrame* second)
{
    unsigned char i;

    if (first->run_count != second->run_count) {
        return 1;
    }
    for (i = 0u; i < first->run_count; ++i) {
        const GameSpriteRun* a;
        const GameSpriteRun* b;

        a = &game_sprite_runs[first->run_offset + i];
        b = &game_sprite_runs[second->run_offset + i];
        if (a->y != b->y || a->x0 != b->x0 || a->x1 != b->x1 ||
            a->color != b->color) {
            return 1;
        }
    }
    return 0;
}

int main(void)
{
    static const unsigned int fixed_roles[10] = {
        0xf2cu, 0x9feu, 0xf64u, 0x348u, 0xe93u,
        0x842u, 0xfd5u, 0x84du, 0x3cbu, 0xfffu
    };
    static const unsigned char expected_run_counts[26] = {
        7u, 7u, 10u, 10u, 9u, 9u, 12u, 12u, 9u, 9u,
        10u, 10u, 10u, 10u, 9u, 9u, 8u, 8u, 8u, 8u,
        15u, 15u, 14u, 14u, 20u, 20u
    };
    unsigned int next_offset;
    unsigned char sprite_id;
    unsigned char stage;

    expect(GAME_SPRITE_COUNT == 13u, "all player enemy and boss sprites exist");
    expect(game_sprite_definitions[GAME_SPRITE_PLAYER].width == 8u &&
        game_sprite_definitions[GAME_SPRITE_PLAYER].height == 6u,
        "player sprite preserves the 8x6 collision rectangle");
    next_offset = 0u;
    for (sprite_id = 0u; sprite_id < GAME_SPRITE_COUNT; ++sprite_id) {
        const GameSpriteDefinition* sprite;
        unsigned char frame_index;

        sprite = &game_sprite_definitions[sprite_id];
        if (sprite_id >= GAME_SPRITE_SCOUT &&
            sprite_id <= GAME_SPRITE_MINING_DRONE) {
            expect(sprite->width == 8u && sprite->height == 8u,
                "enemy sprite preserves its 8x8 collision rectangle");
        }
        for (frame_index = 0u; frame_index < 2u; ++frame_index) {
            const GameSpriteFrame* frame;
            unsigned int colors;
            unsigned int allowed;
            unsigned char run_index;

            frame = &sprite->frames[frame_index];
            expect(frame->run_offset == next_offset,
                "sprite runs have deterministic dense offsets");
            expect(frame->run_count != 0u &&
                frame->run_count <= GAME_SPRITE_MAX_RUNS_PER_FRAME,
                "every sprite frame has one through twenty runs");
            expect(frame->run_count ==
                expected_run_counts[(unsigned int)sprite_id * 2u + frame_index],
                "v0.40.0 detailed sprite frame preserves its authored run count");
            colors = 0u;
            allowed = allowed_roles(sprite_id);
            for (run_index = 0u; run_index < frame->run_count; ++run_index) {
                const GameSpriteRun* run;

                run = &game_sprite_runs[frame->run_offset + run_index];
                expect(run->x0 <= run->x1 && run->x1 < sprite->width &&
                    run->y < sprite->height,
                    "sprite run remains inside its collision rectangle");
                expect((allowed & (1u << run->color)) != 0u,
                    "sprite run uses only its fixed palette roles");
                colors |= 1u << run->color;
            }
            expect(bit_count(colors) >= 3u && bit_count(colors) <= 4u,
                "sprite frame uses three or four colors");
            next_offset += frame->run_count;
        }
        expect(frames_differ(&sprite->frames[0], &sprite->frames[1]),
            "sprite has two distinct animation frames");
    }
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
            game_sprite_definitions[boss_sprite].width == boss->width &&
            game_sprite_definitions[boss_sprite].height == boss->height,
            "boss colored sprite preserves its configured collision rectangle");
    }

    printf("PASS: %u sprite data checks\n", checks);
    return 0;
}
