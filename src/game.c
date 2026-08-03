#include "game.h"

#define PLAYER_SPEED 2u
#define BULLET_SPEED 4u
#define FIRE_COOLDOWN_FRAMES 8u
#define ENEMY_MIN_Y (GAME_HUD_HEIGHT + 3u)
#define ENEMY_Y_RANGE 78u
#define FAR_STAR_INTERVAL 4u
#define NEAR_STAR_INTERVAL 2u
#define ANIMATION_INTERVAL 8u
#define ENEMY_DIRECTION_UP 0u
#define ENEMY_DIRECTION_DOWN 1u
#define ENEMY_SCOUT_FIRE_INTERVAL 90u
#define ENEMY_SAUCER_FIRE_INTERVAL 60u
#define ENEMY_DROPPER_FIRE_INTERVAL 75u
#define ENEMY_FIGHTER_FIRE_INTERVAL 72u
#define ENEMY_BOMBER_FIRE_INTERVAL 96u
#define ENEMY_SUPPLY_FIRE_INTERVAL 84u
#define ENEMY_CAVE_BAT_FIRE_INTERVAL 66u
#define ENEMY_ROCK_WORM_FIRE_INTERVAL 84u
#define ENEMY_MINING_DRONE_FIRE_INTERVAL 78u
#define POWER_ITEM_MOVE_INTERVAL 2u
#define BOSS_MOVE_INTERVAL 2u
#define ENVIRONMENT_NO_NEW_SLOT 0xffu
#define ASTEROID_START_X 152u
#define ASTEROID_SCORE 250ul
#define ROCK_START_Y 10u
#define ROCK_LANDING_Y 94u

typedef struct EnemyMovementConfig {
    unsigned char horizontal_speed;
    unsigned char vertical_interval;
    unsigned char vertical_amplitude;
    unsigned char behavior;
} EnemyMovementConfig;

typedef struct GameEnemyFormationConfig {
    const GameEnemyFormationSlot* slots;
    unsigned char respawn_x;
    unsigned char respawn_spacing;
    unsigned char respawn_min_y;
    unsigned char respawn_y_range;
    unsigned char respawn_y_multiplier;
    unsigned char respawn_type_a;
    unsigned char respawn_type_b;
    unsigned char fixed_type;
    unsigned char fire_phase_spacing;
} GameEnemyFormationConfig;

static const EnemyMovementConfig enemy_movements[3] = {
    { 1u, 0u, 0u, GAME_ENEMY_PATTERN_STRAIGHT },
    { 1u, 3u, 6u, GAME_ENEMY_PATTERN_WAVE },
    { 1u, 2u, 12u, GAME_ENEMY_PATTERN_DIVE }
};

static const GameEnemyFormationSlot space_formation_slots[
    GAME_MAX_ENEMIES] = {
    { 140u, 47u, GAME_ENEMY_TYPE_SCOUT, GAME_ENEMY_PATTERN_STRAIGHT,
        ENEMY_SCOUT_FIRE_INTERVAL, 0u },
    { 170u, 23u, GAME_ENEMY_TYPE_SAUCER, GAME_ENEMY_PATTERN_WAVE,
        ENEMY_SAUCER_FIRE_INTERVAL, 15u },
    { 200u, 70u, GAME_ENEMY_TYPE_SCOUT, GAME_ENEMY_PATTERN_DIVE,
        ENEMY_SCOUT_FIRE_INTERVAL, 30u },
    { 230u, 38u, GAME_ENEMY_TYPE_DROPPER, GAME_ENEMY_PATTERN_STRAIGHT,
        ENEMY_DROPPER_FIRE_INTERVAL, 45u }
};

static const GameEnemyFormationSlot air_formation_slots[
    GAME_MAX_ENEMIES] = {
    { 144u, 24u, GAME_ENEMY_TYPE_FIGHTER, GAME_ENEMY_PATTERN_STRAIGHT,
        ENEMY_FIGHTER_FIRE_INTERVAL, 0u },
    { 180u, 64u, GAME_ENEMY_TYPE_BOMBER, GAME_ENEMY_PATTERN_WAVE,
        ENEMY_BOMBER_FIRE_INTERVAL, 18u },
    { 212u, 42u, GAME_ENEMY_TYPE_FIGHTER, GAME_ENEMY_PATTERN_DIVE,
        ENEMY_FIGHTER_FIRE_INTERVAL, 36u },
    { 244u, 78u, GAME_ENEMY_TYPE_SUPPLY, GAME_ENEMY_PATTERN_WAVE,
        ENEMY_SUPPLY_FIRE_INTERVAL, 54u }
};

static const GameEnemyFormationSlot cave_formation_slots[
    GAME_MAX_ENEMIES] = {
    { 148u, 22u, GAME_ENEMY_TYPE_CAVE_BAT, GAME_ENEMY_PATTERN_WAVE,
        ENEMY_CAVE_BAT_FIRE_INTERVAL, 0u },
    { 184u, 72u, GAME_ENEMY_TYPE_ROCK_WORM, GAME_ENEMY_PATTERN_DIVE,
        ENEMY_ROCK_WORM_FIRE_INTERVAL, 16u },
    { 216u, 44u, GAME_ENEMY_TYPE_CAVE_BAT, GAME_ENEMY_PATTERN_STRAIGHT,
        ENEMY_CAVE_BAT_FIRE_INTERVAL, 32u },
    { 248u, 82u, GAME_ENEMY_TYPE_MINING_DRONE, GAME_ENEMY_PATTERN_WAVE,
        ENEMY_MINING_DRONE_FIRE_INTERVAL, 48u }
};

static const GameEnemyFormationConfig enemy_formation_configs[
    GAME_ENEMY_FORMATION_COUNT] = {
    { space_formation_slots, 180u, 16u, ENEMY_MIN_Y, ENEMY_Y_RANGE,
        17u, GAME_ENEMY_TYPE_SCOUT, GAME_ENEMY_TYPE_SAUCER,
        GAME_ENEMY_TYPE_DROPPER, 15u },
    { air_formation_slots, 184u, 18u, 14u, 76u,
        19u, GAME_ENEMY_TYPE_FIGHTER, GAME_ENEMY_TYPE_BOMBER,
        GAME_ENEMY_TYPE_SUPPLY, 18u },
    { cave_formation_slots, 188u, 18u, 16u, 74u,
        23u, GAME_ENEMY_TYPE_CAVE_BAT, GAME_ENEMY_TYPE_ROCK_WORM,
        GAME_ENEMY_TYPE_MINING_DRONE, 16u }
};

static const GameBossStep boss_steps[7] = {
    { GAME_BOSS_SHOT_STRAIGHT, 120u, 20u, GAME_BOSS_MOVE_STILL },
    { GAME_BOSS_SHOT_FAN, 120u, 60u, GAME_BOSS_MOVE_STILL },
    { GAME_BOSS_SHOT_CANNON_CYCLE, 120u, 20u, GAME_BOSS_MOVE_VERTICAL },
    { GAME_BOSS_SHOT_CANNON_CYCLE, 120u, 15u, GAME_BOSS_MOVE_VERTICAL },
    { GAME_BOSS_SHOT_BURST, 90u, 10u, GAME_BOSS_MOVE_STILL },
    { GAME_BOSS_SHOT_PINCER, 120u, 40u, GAME_BOSS_MOVE_STILL },
    { GAME_BOSS_SHOT_PINCER, 120u, 60u, GAME_BOSS_MOVE_WIDE }
};

static const GameBossConfig boss_configs[GAME_STAGE_COUNT] = {
    { 24u, 16u, 132u, 43u, 60u, 2000u,
        GAME_BOSS_MOVE_STILL, 0u, 2u },
    { 28u, 14u, 128u, 44u, 90u, 3000u,
        GAME_BOSS_MOVE_VERTICAL, 2u, 2u },
    { 24u, 24u, 132u, 39u, 120u, 5000u,
        GAME_BOSS_MOVE_WIDE, 4u, 3u }
};

static const GameStageConfig stage_configs[GAME_STAGE_COUNT] = {
    { GAME_BACKGROUND_THEME_SPACE, GAME_ENEMY_FORMATION_SPACE, 0u,
        GAME_BOSS_APPEARANCE_SPACE_FORTRESS, GAME_ENVIRONMENT_ASTEROIDS },
    { GAME_BACKGROUND_THEME_SKY, GAME_ENEMY_FORMATION_AIR, 1u,
        GAME_BOSS_APPEARANCE_AIR_CARRIER, GAME_ENVIRONMENT_WIND },
    { GAME_BACKGROUND_THEME_CAVE, GAME_ENEMY_FORMATION_CAVE, 2u,
        GAME_BOSS_APPEARANCE_ROCK_GUARDIAN, GAME_ENVIRONMENT_ROCKFALL }
};

static const unsigned int asteroid_event_frames[GAME_ASTEROID_EVENT_COUNT] = {
    60u, 240u, 420u, 600u, 780u, 960u
};

static const unsigned char asteroid_event_y[GAME_ASTEROID_EVENT_COUNT] = {
    22u, 70u, 44u, 84u, 30u, 60u
};

static const unsigned int wind_event_frames[GAME_WIND_EVENT_COUNT] = {
    150u, 510u, 870u
};

static const unsigned char wind_event_y[GAME_WIND_EVENT_COUNT] = {
    18u, 58u, 36u
};

static const unsigned char wind_event_direction[GAME_WIND_EVENT_COUNT] = {
    GAME_WIND_DIRECTION_UP, GAME_WIND_DIRECTION_DOWN,
    GAME_WIND_DIRECTION_UP
};

static const unsigned int rock_event_frames[GAME_ROCKFALL_EVENT_COUNT] = {
    90u, 240u, 390u, 540u, 690u, 840u, 990u
};

static const unsigned char rock_event_x[GAME_ROCKFALL_EVENT_COUNT] = {
    24u, 72u, 120u, 48u, 136u, 96u, 16u
};

static void enter_phase(GameState* game, unsigned char phase);

const GameStageConfig* game_get_stage_config(unsigned char stage)
{
    if (stage < 1u || stage > GAME_STAGE_COUNT) {
        return (const GameStageConfig*)0;
    }
    return &stage_configs[stage - 1u];
}

const GameEnemyFormationSlot* game_get_enemy_formation_slot(
    unsigned char formation_id, unsigned char slot)
{
    if (formation_id >= GAME_ENEMY_FORMATION_COUNT ||
        slot >= GAME_MAX_ENEMIES) {
        return (const GameEnemyFormationSlot*)0;
    }
    return &enemy_formation_configs[formation_id].slots[slot];
}

const GameBossConfig* game_get_boss_config(unsigned char stage)
{
    if (stage < 1u || stage > GAME_STAGE_COUNT) {
        return (const GameBossConfig*)0;
    }
    return &boss_configs[stage_configs[stage - 1u].boss_config_id];
}

const GameBossStep* game_get_boss_step(unsigned char index)
{
    if (index >= 7u) {
        return (const GameBossStep*)0;
    }
    return &boss_steps[index];
}

static void clear_player_bullets(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        game->bullets[i].active = 0u;
    }
}

static void clear_power_item(GameState* game)
{
    game->power_item.active = 0u;
    game->power_item.move_counter = 0u;
}

static void clear_enemy_bullets(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game->enemy_bullets[i].active = 0u;
    }
}

static void clear_enemies(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game->enemies[i].active = 0u;
    }
}

static void clear_boss(GameState* game)
{
    game->boss.active = 0u;
    game->boss.hp = 0u;
    game->boss.max_hp = 0u;
    game->boss.config_id = 0u;
    game->boss.appearance_id = GAME_BOSS_APPEARANCE_COMMON;
    game->boss.script_step = 0u;
    game->boss.attack_timer = 0u;
    game->boss.move_phase = 0u;
    game->boss.direction = ENEMY_DIRECTION_DOWN;
    game->boss.alternate_cannon = 0u;
}

static void reset_environment(GameState* game)
{
    unsigned char i;

    game->environment_event_cursor = 0u;
    game->wind.state = GAME_WIND_STATE_INACTIVE;
    game->wind.y = 0u;
    game->wind.direction = GAME_WIND_DIRECTION_UP;
    game->wind.timer = 0u;
    game->wind.push_counter = 0u;
    for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
        game->asteroids[i].active = 0u;
        game->asteroids[i].rect.x = 0u;
        game->asteroids[i].rect.y = 0u;
        game->falling_rocks[i].state = GAME_ROCK_STATE_INACTIVE;
        game->falling_rocks[i].timer = 0u;
        game->falling_rocks[i].rect.x = 0u;
        game->falling_rocks[i].rect.y = 0u;
    }
}

static void clear_combat_objects(GameState* game)
{
    clear_enemies(game);
    clear_player_bullets(game);
    clear_enemy_bullets(game);
    clear_power_item(game);
    game->fire_cooldown = 0u;
}

static unsigned char enemy_fire_interval(unsigned char type)
{
    if (type == GAME_ENEMY_TYPE_SCOUT) {
        return ENEMY_SCOUT_FIRE_INTERVAL;
    }
    if (type == GAME_ENEMY_TYPE_SAUCER) {
        return ENEMY_SAUCER_FIRE_INTERVAL;
    }
    if (type == GAME_ENEMY_TYPE_DROPPER) {
        return ENEMY_DROPPER_FIRE_INTERVAL;
    }
    if (type == GAME_ENEMY_TYPE_FIGHTER) {
        return ENEMY_FIGHTER_FIRE_INTERVAL;
    }
    if (type == GAME_ENEMY_TYPE_BOMBER) {
        return ENEMY_BOMBER_FIRE_INTERVAL;
    }
    if (type == GAME_ENEMY_TYPE_SUPPLY) {
        return ENEMY_SUPPLY_FIRE_INTERVAL;
    }
    if (type == GAME_ENEMY_TYPE_CAVE_BAT) {
        return ENEMY_CAVE_BAT_FIRE_INTERVAL;
    }
    if (type == GAME_ENEMY_TYPE_ROCK_WORM) {
        return ENEMY_ROCK_WORM_FIRE_INTERVAL;
    }
    return ENEMY_MINING_DRONE_FIRE_INTERVAL;
}

static unsigned char enemy_drops_power(unsigned char type)
{
    return (unsigned char)(type == GAME_ENEMY_TYPE_DROPPER ||
        type == GAME_ENEMY_TYPE_SUPPLY ||
        type == GAME_ENEMY_TYPE_MINING_DRONE);
}

static unsigned char clamp_enemy_y(int y)
{
    int maximum;

    maximum = (int)(GAME_SCREEN_HEIGHT - GAME_ENEMY_HEIGHT);
    if (y < (int)GAME_HUD_HEIGHT) {
        return GAME_HUD_HEIGHT;
    }
    if (y > maximum) {
        return (unsigned char)maximum;
    }
    return (unsigned char)y;
}

static void configure_enemy(GameEnemy* enemy, unsigned char type,
    unsigned char pattern, unsigned char base_y,
    unsigned char fire_interval, unsigned char fire_phase)
{
    const EnemyMovementConfig* movement;

    enemy->active = 1u;
    enemy->type = type;
    enemy->pattern = pattern;
    enemy->base_y = base_y;
    enemy->move_counter = 0u;
    enemy->direction = ENEMY_DIRECTION_DOWN;
    movement = &enemy_movements[pattern];
    if (movement->behavior == GAME_ENEMY_PATTERN_WAVE) {
        enemy->phase = movement->vertical_amplitude;
    } else {
        enemy->phase = 0u;
    }
    enemy->rect.y = clamp_enemy_y(base_y);
    enemy->fire_interval = fire_interval;
    enemy->fire_counter = (unsigned char)(fire_phase % fire_interval);
    enemy->drops_power = enemy_drops_power(type);
}

static void reset_enemy_formation(GameState* game)
{
    const GameStageConfig* stage_config;
    const GameEnemyFormationConfig* formation;
    unsigned char i;

    stage_config = &stage_configs[game->stage - 1u];
    formation = &enemy_formation_configs[stage_config->enemy_formation_id];
    game->respawn_sequence = 0u;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        const GameEnemyFormationSlot* slot_config;

        slot_config = &formation->slots[i];
        game->enemies[i].rect.x = slot_config->x;
        configure_enemy(&game->enemies[i], slot_config->type,
            slot_config->pattern, slot_config->y,
            slot_config->fire_interval, slot_config->fire_phase);
    }
}

static void respawn_enemy(GameState* game, unsigned char slot)
{
    const GameStageConfig* stage_config;
    const GameEnemyFormationConfig* formation;
    unsigned int seed;
    GameEnemy* enemy;
    unsigned char type;

    stage_config = &stage_configs[game->stage - 1u];
    formation = &enemy_formation_configs[stage_config->enemy_formation_id];
    game->respawn_sequence = (unsigned char)(game->respawn_sequence + 1u);
    seed = (unsigned int)game->respawn_sequence + slot;
    enemy = &game->enemies[slot];
    enemy->rect.x = (unsigned char)(formation->respawn_x +
        (unsigned int)slot * formation->respawn_spacing);
    type = slot == 3u ? formation->fixed_type :
        ((seed % 2u) == 0u ? formation->respawn_type_a :
            formation->respawn_type_b);
    configure_enemy(enemy, type,
        (unsigned char)(seed % 3u),
        (unsigned char)(formation->respawn_min_y +
            (seed * formation->respawn_y_multiplier) %
                formation->respawn_y_range),
        enemy_fire_interval(type),
        (unsigned char)((unsigned int)slot *
            formation->fire_phase_spacing));
}

static void reset_background_scroll(GameState* game)
{
    game->planet_offset = 0u;
    game->planet_counter = 0u;
    game->far_star_offset = 0u;
    game->near_star_offset = 0u;
    game->far_star_counter = 0u;
    game->near_star_counter = 0u;
}

static void update_scrolling(GameState* game)
{
    ++game->planet_counter;
    if (game->planet_counter == GAME_PLANET_SCROLL_INTERVAL) {
        game->planet_counter = 0u;
        if (game->planet_offset == GAME_PLANET_SCROLL_PERIOD - 1u) {
            game->planet_offset = 0u;
        } else {
            ++game->planet_offset;
        }
    }

    ++game->far_star_counter;
    if (game->far_star_counter == FAR_STAR_INTERVAL) {
        game->far_star_counter = 0u;
        if (game->far_star_offset == GAME_SCREEN_WIDTH - 1u) {
            game->far_star_offset = 0u;
        } else {
            ++game->far_star_offset;
        }
    }

    ++game->near_star_counter;
    if (game->near_star_counter == NEAR_STAR_INTERVAL) {
        game->near_star_counter = 0u;
        if (game->near_star_offset == GAME_SCREEN_WIDTH - 1u) {
            game->near_star_offset = 0u;
        } else {
            ++game->near_star_offset;
        }
    }

    ++game->animation_counter;
    if (game->animation_counter == ANIMATION_INTERVAL) {
        game->animation_counter = 0u;
        game->animation_frame = (unsigned char)(1u - game->animation_frame);
    }
}

static void move_player(GameState* game, unsigned char input)
{
    if ((input & GAME_INPUT_LEFT) != 0u) {
        if (game->player.x >= PLAYER_SPEED) {
            game->player.x = (unsigned char)(game->player.x - PLAYER_SPEED);
        } else {
            game->player.x = 0u;
        }
    }
    if ((input & GAME_INPUT_RIGHT) != 0u &&
        game->player.x < GAME_SCREEN_WIDTH - GAME_PLAYER_WIDTH) {
        game->player.x = (unsigned char)(game->player.x + PLAYER_SPEED);
        if (game->player.x > GAME_SCREEN_WIDTH - GAME_PLAYER_WIDTH) {
            game->player.x = GAME_SCREEN_WIDTH - GAME_PLAYER_WIDTH;
        }
    }
    if ((input & GAME_INPUT_UP) != 0u) {
        if (game->player.y >= GAME_HUD_HEIGHT + PLAYER_SPEED) {
            game->player.y = (unsigned char)(game->player.y - PLAYER_SPEED);
        } else {
            game->player.y = GAME_HUD_HEIGHT;
        }
    }
    if ((input & GAME_INPUT_DOWN) != 0u &&
        game->player.y < GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT) {
        game->player.y = (unsigned char)(game->player.y + PLAYER_SPEED);
        if (game->player.y > GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT) {
            game->player.y = GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT;
        }
    }
}

static void update_enemy_movement(GameEnemy* enemy)
{
    const EnemyMovementConfig* movement;
    int vertical_offset;
    unsigned char phase_limit;

    movement = &enemy_movements[enemy->pattern];
    if (enemy->rect.x >= movement->horizontal_speed) {
        enemy->rect.x = (unsigned char)(enemy->rect.x - movement->horizontal_speed);
    } else {
        enemy->rect.x = 0u;
    }

    if (movement->vertical_interval == 0u) {
        enemy->rect.y = clamp_enemy_y(enemy->base_y);
        return;
    }
    if (movement->behavior == GAME_ENEMY_PATTERN_WAVE) {
        phase_limit = (unsigned char)(movement->vertical_amplitude * 2u);
    } else {
        phase_limit = movement->vertical_amplitude;
    }

    ++enemy->move_counter;
    if (enemy->move_counter == movement->vertical_interval) {
        enemy->move_counter = 0u;
        if (enemy->direction == ENEMY_DIRECTION_DOWN) {
            if (enemy->phase < phase_limit) {
                ++enemy->phase;
            } else {
                enemy->direction = ENEMY_DIRECTION_UP;
                --enemy->phase;
            }
        } else if (enemy->phase != 0u) {
            --enemy->phase;
        } else {
            enemy->direction = ENEMY_DIRECTION_DOWN;
            ++enemy->phase;
        }
    }

    if (movement->behavior == GAME_ENEMY_PATTERN_WAVE) {
        vertical_offset = (int)enemy->phase -
            (int)movement->vertical_amplitude;
    } else {
        vertical_offset = (int)enemy->phase;
    }
    enemy->rect.y = clamp_enemy_y((int)enemy->base_y + vertical_offset);
}

static unsigned char fire_player_bullets(GameState* game)
{
    unsigned char i;
    unsigned char required;
    unsigned char available;
    unsigned char created;

    required = game->weapon_level;
    available = 0u;
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            ++available;
        }
    }
    if (available < required) {
        return 0u;
    }

    created = 0u;
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            game->bullets[i].active = 1u;
            game->bullets[i].rect.x =
                (unsigned char)(game->player.x + GAME_PLAYER_WIDTH);
            if (game->weapon_level == GAME_WEAPON_LEVEL_MIN) {
                game->bullets[i].rect.y =
                    (unsigned char)(game->player.y + 2u);
            } else {
                game->bullets[i].rect.y =
                    (unsigned char)(game->player.y + created * 2u);
                if (game->weapon_level == 2u && created != 0u) {
                    game->bullets[i].rect.y =
                        (unsigned char)(game->player.y + 4u);
                }
            }
            ++created;
            if (created == required) {
                return 1u;
            }
        }
    }
    return 0u;
}

static unsigned char spawn_power_item(GameState* game,
    const GameEnemy* enemy)
{
    unsigned int x;

    if (game->power_item.active != 0u) {
        return 0u;
    }
    x = (unsigned int)enemy->rect.x + 2u;
    if (x > GAME_SCREEN_WIDTH - GAME_POWER_ITEM_WIDTH) {
        x = GAME_SCREEN_WIDTH - GAME_POWER_ITEM_WIDTH;
    }
    game->power_item.rect.x = (unsigned char)x;
    game->power_item.rect.y = (unsigned char)(enemy->rect.y + 2u);
    game->power_item.active = 1u;
    game->power_item.move_counter = 0u;
    return 1u;
}

static unsigned char update_power_item(GameState* game)
{
    if (game->power_item.active == 0u) {
        return 0u;
    }
    ++game->power_item.move_counter;
    if (game->power_item.move_counter == POWER_ITEM_MOVE_INTERVAL) {
        game->power_item.move_counter = 0u;
        if (game->power_item.rect.x == 0u) {
            game->power_item.active = 0u;
            return 0u;
        }
        --game->power_item.rect.x;
    }
    if (game_aabb_intersects(&game->player,
        &game->power_item.rect) != 0u) {
        if (game->weapon_level < GAME_WEAPON_LEVEL_MAX) {
            ++game->weapon_level;
        }
        clear_power_item(game);
        return 1u;
    }
    return 0u;
}

static unsigned char spawn_enemy_bullet(GameState* game, int x, int y,
    signed char velocity_x, signed char velocity_y)
{
    unsigned char i;

    if (x < 0 || x >= (int)GAME_SCREEN_WIDTH ||
        y < 0 || y >= (int)GAME_SCREEN_HEIGHT) {
        return 0u;
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active == 0u) {
            game->enemy_bullets[i].active = 1u;
            game->enemy_bullets[i].rect.x = (unsigned char)x;
            game->enemy_bullets[i].rect.y = (unsigned char)y;
            game->enemy_bullets[i].velocity_x = velocity_x;
            game->enemy_bullets[i].velocity_y = velocity_y;
            return 1u;
        }
    }
    return 0u;
}

static void fire_enemy_bullet(GameState* game, const GameEnemy* enemy)
{
    int x;

    x = enemy->rect.x;
    if (x > (int)(GAME_SCREEN_WIDTH - GAME_ENEMY_BULLET_WIDTH)) {
        x = (int)(GAME_SCREEN_WIDTH - GAME_ENEMY_BULLET_WIDTH);
    }
    (void)spawn_enemy_bullet(game, x, (int)enemy->rect.y + 3,
        (signed char)-2, (signed char)0);
}

static void update_enemy_bullets(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        int x;
        int y;

        if (game->enemy_bullets[i].active == 0u) {
            continue;
        }
        x = (int)game->enemy_bullets[i].rect.x +
            (int)game->enemy_bullets[i].velocity_x;
        y = (int)game->enemy_bullets[i].rect.y +
            (int)game->enemy_bullets[i].velocity_y;
        if (x < 0 || x >= (int)GAME_SCREEN_WIDTH ||
            y < 0 || y >= (int)GAME_SCREEN_HEIGHT) {
            game->enemy_bullets[i].active = 0u;
        } else {
            game->enemy_bullets[i].rect.x = (unsigned char)x;
            game->enemy_bullets[i].rect.y = (unsigned char)y;
        }
    }
}

static void reset_boss_runtime(GameState* game, unsigned char preserve_hp)
{
    const GameBossConfig* config;
    unsigned char hp;

    config = &boss_configs[game->boss.config_id];
    hp = game->boss.hp;
    game->boss.active = 1u;
    game->boss.rect.x = config->stop_x;
    game->boss.rect.y = config->start_y;
    game->boss.rect.width = config->width;
    game->boss.rect.height = config->height;
    game->boss.max_hp = config->max_hp;
    game->boss.hp = preserve_hp != 0u ? hp : config->max_hp;
    game->boss.script_step = 0u;
    game->boss.attack_timer = 0u;
    game->boss.move_phase = 0u;
    game->boss.direction = ENEMY_DIRECTION_DOWN;
    game->boss.alternate_cannon = 0u;
}

static void initialize_boss(GameState* game)
{
    game->boss.config_id = stage_configs[game->stage - 1u].boss_config_id;
    game->boss.appearance_id =
        stage_configs[game->stage - 1u].boss_appearance_id;
    reset_boss_runtime(game, 0u);
}

static void move_boss(GameState* game, unsigned char movement)
{
    const GameBossConfig* config;
    unsigned char amplitude;
    unsigned char minimum_y;
    unsigned char maximum_y;

    if (movement == GAME_BOSS_MOVE_STILL) {
        return;
    }
    ++game->boss.move_phase;
    if (game->boss.move_phase != BOSS_MOVE_INTERVAL) {
        return;
    }
    game->boss.move_phase = 0u;
    config = &boss_configs[game->boss.config_id];
    amplitude = movement == GAME_BOSS_MOVE_WIDE ? 18u : 12u;
    minimum_y = (unsigned char)(config->start_y - amplitude);
    maximum_y = (unsigned char)(config->start_y + amplitude);
    if (game->boss.direction == ENEMY_DIRECTION_DOWN) {
        if (game->boss.rect.y < maximum_y) {
            ++game->boss.rect.y;
        } else {
            game->boss.direction = ENEMY_DIRECTION_UP;
            --game->boss.rect.y;
        }
    } else if (game->boss.rect.y > minimum_y) {
        --game->boss.rect.y;
    } else {
        game->boss.direction = ENEMY_DIRECTION_DOWN;
        ++game->boss.rect.y;
    }
    if (movement == GAME_BOSS_MOVE_WIDE) {
        if (game->boss.direction == ENEMY_DIRECTION_DOWN) {
            game->boss.rect.x = (unsigned char)(config->stop_x - 4u);
        } else {
            game->boss.rect.x = config->stop_x;
        }
    }
}

static void fire_boss_shot(GameState* game, unsigned char shot_type)
{
    int x;
    int center;
    int top;
    int bottom;

    x = (int)game->boss.rect.x - (int)GAME_ENEMY_BULLET_WIDTH;
    center = (int)game->boss.rect.y + (int)game->boss.rect.height / 2;
    top = (int)game->boss.rect.y + 2;
    bottom = (int)game->boss.rect.y + (int)game->boss.rect.height - 4;
    if (shot_type == GAME_BOSS_SHOT_STRAIGHT ||
        shot_type == GAME_BOSS_SHOT_BURST) {
        (void)spawn_enemy_bullet(game, x,
            shot_type == GAME_BOSS_SHOT_STRAIGHT ?
                (int)game->boss.rect.y + 4 : center,
            (signed char)-2, (signed char)0);
    } else if (shot_type == GAME_BOSS_SHOT_FAN) {
        (void)spawn_enemy_bullet(game, x, center,
            (signed char)-2, (signed char)-1);
        (void)spawn_enemy_bullet(game, x, center,
            (signed char)-2, (signed char)0);
        (void)spawn_enemy_bullet(game, x, center,
            (signed char)-2, (signed char)1);
    } else if (shot_type == GAME_BOSS_SHOT_ALTERNATE) {
        (void)spawn_enemy_bullet(game, x,
            game->boss.alternate_cannon == 0u ? top : bottom,
            (signed char)-2, (signed char)0);
        game->boss.alternate_cannon =
            (unsigned char)(1u - game->boss.alternate_cannon);
    } else if (shot_type == GAME_BOSS_SHOT_CANNON_CYCLE) {
        int cannon_y;

        cannon_y = game->boss.alternate_cannon == 0u ? top :
            (game->boss.alternate_cannon == 1u ? center : bottom);
        (void)spawn_enemy_bullet(game, x, cannon_y,
            (signed char)-2, (signed char)0);
        ++game->boss.alternate_cannon;
        if (game->boss.alternate_cannon == 3u) {
            game->boss.alternate_cannon = 0u;
        }
    } else {
        (void)spawn_enemy_bullet(game, x, top,
            (signed char)-2, (signed char)1);
        (void)spawn_enemy_bullet(game, x, bottom,
            (signed char)-2, (signed char)-1);
    }
}

static void update_boss_attack(GameState* game)
{
    const GameBossConfig* config;
    const GameBossStep* step;
    unsigned char step_index;

    config = &boss_configs[game->boss.config_id];
    step_index = (unsigned char)(config->script_offset +
        game->boss.script_step);
    step = &boss_steps[step_index];
    ++game->boss.attack_timer;
    if ((unsigned char)(game->boss.attack_timer % step->fire_interval) == 0u) {
        fire_boss_shot(game, step->shot_type);
    }
    move_boss(game, step->movement);
    if (game->boss.attack_timer == step->duration) {
        game->boss.attack_timer = 0u;
        ++game->boss.script_step;
        if (game->boss.script_step == config->script_count) {
            game->boss.script_step = 0u;
        }
    }
}

static void begin_player_death(GameState* game)
{
    if (game->lives != 0u) {
        --game->lives;
    }
    clear_player_bullets(game);
    game->dying = 1u;
    game->explosion_timer = 0u;
    game->invincibility_timer = 0u;
    sound_request_sfx(&game->sound, SOUND_SFX_PLAYER_EXPLOSION);
}

static void update_player_death(GameState* game)
{
    ++game->explosion_timer;
    if (game->explosion_timer != GAME_EXPLOSION_FRAMES) {
        return;
    }

    game->dying = 0u;
    game->explosion_timer = 0u;
    if (game->lives == 0u) {
        game->game_over = 1u;
        game->restart_armed = 0u;
        reset_environment(game);
        sound_stop_all(&game->sound);
        return;
    }

    game->player.x = 10u;
    game->player.y = 48u;
    clear_player_bullets(game);
    clear_enemy_bullets(game);
    clear_power_item(game);
    game->fire_cooldown = 0u;
    if (game->phase == GAME_PHASE_BOSS) {
        reset_boss_runtime(game, 1u);
        clear_enemies(game);
    } else {
        reset_enemy_formation(game);
        clear_boss(game);
    }
    game->invincibility_timer = GAME_INVINCIBILITY_FRAMES;
    if (game->phase == GAME_PHASE_NORMAL &&
        game->phase_timer == GAME_NORMAL_FRAMES) {
        enter_phase(game, GAME_PHASE_WARNING);
    }
}

static void enter_phase(GameState* game, unsigned char phase)
{
    game->phase = phase;
    game->phase_timer = 0u;
    clear_combat_objects(game);
    clear_boss(game);
    reset_environment(game);
    if (phase == GAME_PHASE_NORMAL) {
        reset_enemy_formation(game);
    } else if (phase == GAME_PHASE_BOSS) {
        initialize_boss(game);
    } else if (phase == GAME_PHASE_WARNING) {
        sound_request_sfx(&game->sound, SOUND_SFX_WARNING);
    } else if (phase == GAME_PHASE_STAGE_CLEAR) {
        sound_request_sfx(&game->sound, SOUND_SFX_STAGE_CLEAR);
    } else if (phase == GAME_PHASE_ALL_CLEAR) {
        game->restart_armed = 0u;
        sound_stop_all(&game->sound);
    }
}

void game_init(GameState* game)
{
    unsigned char i;

    game->player.x = 10u;
    game->player.y = 48u;
    game->player.width = GAME_PLAYER_WIDTH;
    game->player.height = GAME_PLAYER_HEIGHT;
    game->score = 0ul;
    game->fire_cooldown = 0u;
    game->weapon_level = GAME_WEAPON_LEVEL_MIN;
    game->respawn_sequence = 0u;
    game->lives = GAME_INITIAL_LIVES;
    game->game_over = 0u;
    game->restart_armed = 0u;
    game->dying = 0u;
    game->explosion_timer = 0u;
    game->invincibility_timer = 0u;
    game->planet_offset = 0u;
    game->planet_counter = 0u;
    game->far_star_offset = 0u;
    game->near_star_offset = 0u;
    game->far_star_counter = 0u;
    game->near_star_counter = 0u;
    game->animation_counter = 0u;
    game->animation_frame = 0u;
    game->stage = 1u;
    game->phase = GAME_PHASE_STAGE_INTRO;
    game->phase_timer = 0u;
    sound_init(&game->sound);

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game->enemies[i].rect.width = GAME_ENEMY_WIDTH;
        game->enemies[i].rect.height = GAME_ENEMY_HEIGHT;
    }
    reset_enemy_formation(game);
    clear_enemies(game);
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        game->bullets[i].active = 0u;
        game->bullets[i].rect.x = 0u;
        game->bullets[i].rect.y = 0u;
        game->bullets[i].rect.width = GAME_PLAYER_BULLET_WIDTH;
        game->bullets[i].rect.height = GAME_PLAYER_BULLET_HEIGHT;
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game->enemy_bullets[i].active = 0u;
        game->enemy_bullets[i].rect.x = 0u;
        game->enemy_bullets[i].rect.y = 0u;
        game->enemy_bullets[i].rect.width = GAME_ENEMY_BULLET_WIDTH;
        game->enemy_bullets[i].rect.height = GAME_ENEMY_BULLET_HEIGHT;
        game->enemy_bullets[i].velocity_x = (signed char)-2;
        game->enemy_bullets[i].velocity_y = (signed char)0;
    }
    game->power_item.rect.x = 0u;
    game->power_item.rect.y = 0u;
    game->power_item.rect.width = GAME_POWER_ITEM_WIDTH;
    game->power_item.rect.height = GAME_POWER_ITEM_HEIGHT;
    clear_power_item(game);
    game->boss.rect.x = 0u;
    game->boss.rect.y = 0u;
    game->boss.rect.width = 0u;
    game->boss.rect.height = 0u;
    clear_boss(game);
    for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
        game->asteroids[i].rect.width = GAME_ENVIRONMENT_OBJECT_WIDTH;
        game->asteroids[i].rect.height = GAME_ENVIRONMENT_OBJECT_HEIGHT;
        game->falling_rocks[i].rect.width = GAME_ENVIRONMENT_OBJECT_WIDTH;
        game->falling_rocks[i].rect.height = GAME_ENVIRONMENT_OBJECT_HEIGHT;
    }
    reset_environment(game);
}

unsigned char game_aabb_intersects(const GameRect* a, const GameRect* b)
{
    return (unsigned char)(
        (unsigned int)a->x < (unsigned int)b->x + b->width &&
        (unsigned int)a->x + a->width > (unsigned int)b->x &&
        (unsigned int)a->y < (unsigned int)b->y + b->height &&
        (unsigned int)a->y + a->height > (unsigned int)b->y);
}

unsigned char game_player_is_visible(const GameState* game)
{
    unsigned char elapsed;

    if (game->invincibility_timer == 0u) {
        return 1u;
    }
    elapsed = (unsigned char)(GAME_INVINCIBILITY_FRAMES -
        game->invincibility_timer);
    return (unsigned char)(((elapsed / 4u) % 2u) == 0u);
}

static unsigned char update_player_bullets_normal(GameState* game,
    unsigned char* hit_enemies)
{
    unsigned char i;
    unsigned char j;
    unsigned char power_item_created;

    power_item_created = 0u;
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            continue;
        }
        if (game->bullets[i].rect.x >
            GAME_SCREEN_WIDTH - GAME_PLAYER_BULLET_WIDTH - BULLET_SPEED) {
            game->bullets[i].active = 0u;
            continue;
        }
        game->bullets[i].rect.x =
            (unsigned char)(game->bullets[i].rect.x + BULLET_SPEED);
        for (j = 0u; j < GAME_MAX_ENEMIES; ++j) {
            if (game->enemies[j].active != 0u &&
                game->enemies[j].rect.x < GAME_SCREEN_WIDTH &&
                hit_enemies[j] == 0u &&
                game_aabb_intersects(&game->bullets[i].rect,
                    &game->enemies[j].rect) != 0u) {
                game->bullets[i].active = 0u;
                game->score += 100ul;
                if (game->enemies[j].drops_power != 0u) {
                    power_item_created = spawn_power_item(game,
                        &game->enemies[j]);
                }
                respawn_enemy(game, j);
                hit_enemies[j] = 1u;
                break;
            }
        }
    }
    return power_item_created;
}

static void apply_damage(GameState* game, unsigned char damage,
    unsigned char was_invincible)
{
    if (damage == 0u) {
        return;
    }
    if (was_invincible != 0u) {
        if (game->phase == GAME_PHASE_NORMAL) {
            reset_enemy_formation(game);
        } else if (game->phase == GAME_PHASE_BOSS) {
            reset_boss_runtime(game, 1u);
        }
        clear_enemy_bullets(game);
    } else {
        begin_player_death(game);
    }
}

static unsigned char find_free_asteroid(const GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
        if (game->asteroids[i].active == 0u) {
            return i;
        }
    }
    return ENVIRONMENT_NO_NEW_SLOT;
}

static unsigned char find_free_rock(const GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
        if (game->falling_rocks[i].state == GAME_ROCK_STATE_INACTIVE) {
            return i;
        }
    }
    return ENVIRONMENT_NO_NEW_SLOT;
}

static unsigned char start_environment_event(GameState* game)
{
    const GameStageConfig* config;
    unsigned int elapsed;
    unsigned char cursor;
    unsigned char slot;

    config = &stage_configs[game->stage - 1u];
    elapsed = game->phase_timer + 1u;
    cursor = game->environment_event_cursor;
    slot = ENVIRONMENT_NO_NEW_SLOT;
    if (config->environment_id == GAME_ENVIRONMENT_ASTEROIDS &&
        cursor < GAME_ASTEROID_EVENT_COUNT &&
        elapsed == asteroid_event_frames[cursor]) {
        slot = find_free_asteroid(game);
        if (slot != ENVIRONMENT_NO_NEW_SLOT) {
            game->asteroids[slot].active = 1u;
            game->asteroids[slot].rect.x = ASTEROID_START_X;
            game->asteroids[slot].rect.y = asteroid_event_y[cursor];
        }
        ++game->environment_event_cursor;
    } else if (config->environment_id == GAME_ENVIRONMENT_WIND &&
        cursor < GAME_WIND_EVENT_COUNT &&
        elapsed == wind_event_frames[cursor]) {
        game->wind.state = GAME_WIND_STATE_WARNING;
        game->wind.y = wind_event_y[cursor];
        game->wind.direction = wind_event_direction[cursor];
        game->wind.timer = GAME_WIND_WARNING_FRAMES;
        game->wind.push_counter = 0u;
        ++game->environment_event_cursor;
        slot = 0u;
    } else if (config->environment_id == GAME_ENVIRONMENT_ROCKFALL &&
        cursor < GAME_ROCKFALL_EVENT_COUNT &&
        elapsed == rock_event_frames[cursor]) {
        slot = find_free_rock(game);
        if (slot != ENVIRONMENT_NO_NEW_SLOT) {
            game->falling_rocks[slot].state = GAME_ROCK_STATE_WARNING;
            game->falling_rocks[slot].timer = GAME_ROCK_WARNING_FRAMES;
            game->falling_rocks[slot].rect.x = rock_event_x[cursor];
            game->falling_rocks[slot].rect.y = ROCK_LANDING_Y;
        }
        ++game->environment_event_cursor;
    }
    return slot;
}

static void update_wind(GameState* game, unsigned char event_started)
{
    unsigned int player_bottom;
    unsigned int band_bottom;

    if (game->wind.state == GAME_WIND_STATE_INACTIVE ||
        event_started != 0u) {
        return;
    }
    if (game->wind.state == GAME_WIND_STATE_WARNING) {
        --game->wind.timer;
        if (game->wind.timer == 0u) {
            game->wind.state = GAME_WIND_STATE_ACTIVE;
            game->wind.timer = GAME_WIND_ACTIVE_FRAMES;
            game->wind.push_counter = 0u;
        }
        return;
    }

    ++game->wind.push_counter;
    if (game->wind.push_counter == 2u) {
        game->wind.push_counter = 0u;
        player_bottom = (unsigned int)game->player.y + game->player.height;
        band_bottom = (unsigned int)game->wind.y + GAME_WIND_BAND_HEIGHT;
        if ((unsigned int)game->player.y < band_bottom &&
            player_bottom > game->wind.y) {
            if (game->wind.direction == GAME_WIND_DIRECTION_UP) {
                if (game->player.y > GAME_HUD_HEIGHT) {
                    --game->player.y;
                }
            } else if (game->player.y <
                GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT) {
                ++game->player.y;
            }
        }
    }
    --game->wind.timer;
    if (game->wind.timer == 0u) {
        game->wind.state = GAME_WIND_STATE_INACTIVE;
        game->wind.push_counter = 0u;
    }
}

static unsigned char hit_asteroids_with_player_bullets(GameState* game,
    unsigned char new_slot)
{
    unsigned char i;
    unsigned char j;
    unsigned char destroyed;

    destroyed = 0u;

    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            continue;
        }
        for (j = 0u; j < GAME_MAX_ENVIRONMENT_OBJECTS; ++j) {
            if (j != new_slot && game->asteroids[j].active != 0u &&
                game_aabb_intersects(&game->bullets[i].rect,
                    &game->asteroids[j].rect) != 0u) {
                game->bullets[i].active = 0u;
                game->asteroids[j].active = 0u;
                game->score += ASTEROID_SCORE;
                destroyed = 1u;
                break;
            }
        }
    }
    return destroyed;
}

static void update_asteroids(GameState* game, unsigned char new_slot,
    unsigned char* damage)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
        if (game->asteroids[i].active == 0u || i == new_slot) {
            continue;
        }
        if (game->asteroids[i].rect.x == 0u) {
            game->asteroids[i].active = 0u;
            continue;
        }
        --game->asteroids[i].rect.x;
        if (game_aabb_intersects(&game->player,
            &game->asteroids[i].rect) != 0u) {
            game->asteroids[i].active = 0u;
            *damage = 1u;
        }
    }
}

static void update_falling_rocks(GameState* game, unsigned char new_slot,
    unsigned char* damage)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
        GameFallingRock* rock;

        rock = &game->falling_rocks[i];
        if (rock->state == GAME_ROCK_STATE_INACTIVE || i == new_slot) {
            continue;
        }
        if (rock->state == GAME_ROCK_STATE_WARNING) {
            --rock->timer;
            if (rock->timer == 0u) {
                rock->state = GAME_ROCK_STATE_FALLING;
                rock->rect.y = ROCK_START_Y;
            }
        } else if (rock->state == GAME_ROCK_STATE_FALLING) {
            if (rock->rect.y < ROCK_LANDING_Y) {
                unsigned int next_y;

                next_y = (unsigned int)rock->rect.y + 2u;
                rock->rect.y = next_y > ROCK_LANDING_Y ?
                    ROCK_LANDING_Y : (unsigned char)next_y;
            }
            if (game_aabb_intersects(&game->player, &rock->rect) != 0u) {
                *damage = 1u;
                rock->state = GAME_ROCK_STATE_IMPACT;
                rock->timer = GAME_ROCK_IMPACT_FRAMES;
            } else if (rock->rect.y == ROCK_LANDING_Y) {
                rock->state = GAME_ROCK_STATE_IMPACT;
                rock->timer = GAME_ROCK_IMPACT_FRAMES;
            }
        } else {
            --rock->timer;
            if (rock->timer == 0u) {
                rock->state = GAME_ROCK_STATE_INACTIVE;
            }
        }
    }
}

static void update_normal(GameState* game, unsigned char input,
    unsigned char was_invincible)
{
    unsigned char i;
    unsigned char hit_enemies[GAME_MAX_ENEMIES];
    unsigned char power_item_created;
    unsigned char damage;
    unsigned char new_environment_slot;
    unsigned char enemy_destroyed;
    unsigned char power_item_collected;
    const GameStageConfig* stage_config;

    move_player(game, input);
    stage_config = &stage_configs[game->stage - 1u];
    new_environment_slot = start_environment_event(game);
    if (stage_config->environment_id == GAME_ENVIRONMENT_WIND) {
        update_wind(game,
            (unsigned char)(new_environment_slot != ENVIRONMENT_NO_NEW_SLOT));
    }
    if (game->fire_cooldown != 0u) {
        --game->fire_cooldown;
    }
    if ((input & GAME_INPUT_FIRE) != 0u && game->fire_cooldown == 0u &&
        fire_player_bullets(game) != 0u) {
        game->fire_cooldown = FIRE_COOLDOWN_FRAMES;
        sound_request_sfx(&game->sound, SOUND_SFX_SHOT);
    }
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        hit_enemies[i] = 0u;
    }
    power_item_created = update_player_bullets_normal(game, hit_enemies);
    enemy_destroyed = 0u;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        if (hit_enemies[i] != 0u) {
            enemy_destroyed = 1u;
        }
    }
    if (stage_config->environment_id == GAME_ENVIRONMENT_ASTEROIDS) {
        if (hit_asteroids_with_player_bullets(game,
            new_environment_slot) != 0u) {
            enemy_destroyed = 1u;
        }
    }
    if (enemy_destroyed != 0u) {
        sound_request_sfx(&game->sound, SOUND_SFX_ENEMY_DEFEAT);
    }
    update_enemy_bullets(game);

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        GameEnemy* enemy;
        unsigned char interval;

        enemy = &game->enemies[i];
        if (enemy->active == 0u || hit_enemies[i] != 0u) {
            continue;
        }
        if (enemy->rect.x >= GAME_SCREEN_WIDTH) {
            --enemy->rect.x;
            continue;
        }
        update_enemy_movement(enemy);
        interval = enemy->fire_interval;
        ++enemy->fire_counter;
        if (enemy->fire_counter == interval) {
            enemy->fire_counter = 0u;
            fire_enemy_bullet(game, enemy);
        }
    }
    if (power_item_created == 0u) {
        power_item_collected = update_power_item(game);
        if (power_item_collected != 0u) {
            sound_request_sfx(&game->sound, SOUND_SFX_POWER_UP);
        }
    }

    damage = 0u;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        if (game->enemies[i].active != 0u && hit_enemies[i] == 0u &&
            game->enemies[i].rect.x < GAME_SCREEN_WIDTH &&
            (game->enemies[i].rect.x == 0u ||
            game_aabb_intersects(&game->player,
                &game->enemies[i].rect) != 0u)) {
            damage = 1u;
        }
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active != 0u &&
            game_aabb_intersects(&game->player,
                &game->enemy_bullets[i].rect) != 0u) {
            game->enemy_bullets[i].active = 0u;
            damage = 1u;
        }
    }
    if (stage_config->environment_id == GAME_ENVIRONMENT_ASTEROIDS) {
        update_asteroids(game, new_environment_slot, &damage);
    } else if (stage_config->environment_id == GAME_ENVIRONMENT_ROCKFALL) {
        update_falling_rocks(game, new_environment_slot, &damage);
    }
    apply_damage(game, damage, was_invincible);
    ++game->phase_timer;
    if (game->dying == 0u && game->phase_timer == GAME_NORMAL_FRAMES) {
        enter_phase(game, GAME_PHASE_WARNING);
    }
}

static unsigned char update_player_bullets_boss(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            continue;
        }
        if (game->bullets[i].rect.x >
            GAME_SCREEN_WIDTH - GAME_PLAYER_BULLET_WIDTH - BULLET_SPEED) {
            game->bullets[i].active = 0u;
            continue;
        }
        game->bullets[i].rect.x =
            (unsigned char)(game->bullets[i].rect.x + BULLET_SPEED);
        if (game->boss.active != 0u &&
            game_aabb_intersects(&game->bullets[i].rect,
                &game->boss.rect) != 0u) {
            game->bullets[i].active = 0u;
            if (game->boss.hp != 0u) {
                --game->boss.hp;
            }
        }
    }
    return (unsigned char)(game->boss.hp == 0u);
}

static void defeat_boss(GameState* game)
{
    const GameBossConfig* config;

    config = &boss_configs[game->boss.config_id];
    game->score += config->defeat_score;
    sound_request_sfx(&game->sound, SOUND_SFX_BOSS_DEFEAT);
    enter_phase(game, GAME_PHASE_STAGE_CLEAR);
}

static void update_boss(GameState* game, unsigned char input,
    unsigned char was_invincible)
{
    unsigned char i;
    unsigned char damage;

    move_player(game, input);
    if (game->fire_cooldown != 0u) {
        --game->fire_cooldown;
    }
    if ((input & GAME_INPUT_FIRE) != 0u && game->fire_cooldown == 0u &&
        fire_player_bullets(game) != 0u) {
        game->fire_cooldown = FIRE_COOLDOWN_FRAMES;
        sound_request_sfx(&game->sound, SOUND_SFX_SHOT);
    }
    if (update_player_bullets_boss(game) != 0u) {
        defeat_boss(game);
        return;
    }
    update_enemy_bullets(game);
    update_boss_attack(game);

    damage = (unsigned char)(game->boss.active != 0u &&
        game_aabb_intersects(&game->player, &game->boss.rect) != 0u);
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active != 0u &&
            game_aabb_intersects(&game->player,
                &game->enemy_bullets[i].rect) != 0u) {
            game->enemy_bullets[i].active = 0u;
            damage = 1u;
        }
    }
    apply_damage(game, damage, was_invincible);
    ++game->phase_timer;
}

static void game_update_logic(GameState* game, unsigned char input)
{
    unsigned char was_invincible;

    if (game->game_over != 0u || game->phase == GAME_PHASE_ALL_CLEAR) {
        if ((input & GAME_INPUT_FIRE) == 0u) {
            game->restart_armed = 1u;
        } else if (game->restart_armed != 0u) {
            game_init(game);
        }
        return;
    }
    if (game->dying != 0u) {
        update_player_death(game);
        return;
    }

    if (game->phase == GAME_PHASE_STAGE_INTRO) {
        update_scrolling(game);
        ++game->phase_timer;
        if (game->phase_timer == GAME_STAGE_INTRO_FRAMES) {
            enter_phase(game, GAME_PHASE_NORMAL);
        }
        return;
    }
    if (game->phase == GAME_PHASE_WARNING) {
        update_scrolling(game);
        move_player(game, input);
        ++game->phase_timer;
        if (game->phase_timer == GAME_WARNING_FRAMES) {
            enter_phase(game, GAME_PHASE_BOSS);
        }
        return;
    }
    if (game->phase == GAME_PHASE_STAGE_CLEAR) {
        update_scrolling(game);
        ++game->phase_timer;
        if (game->phase_timer == GAME_STAGE_CLEAR_FRAMES) {
            if (game->stage == GAME_STAGE_COUNT) {
                enter_phase(game, GAME_PHASE_ALL_CLEAR);
            } else {
                ++game->stage;
                reset_background_scroll(game);
                sound_set_stage(&game->sound, game->stage);
                enter_phase(game, GAME_PHASE_STAGE_INTRO);
            }
        }
        return;
    }

    was_invincible = (unsigned char)(game->invincibility_timer != 0u);
    if (was_invincible != 0u) {
        --game->invincibility_timer;
    }
    update_scrolling(game);
    if (game->phase == GAME_PHASE_NORMAL) {
        update_normal(game, input, was_invincible);
    } else {
        update_boss(game, input, was_invincible);
    }
}

void game_update(GameState* game, unsigned char input)
{
    unsigned char freeze_bgm;

    freeze_bgm = game->dying;
    game_update_logic(game, input);
    sound_tick(&game->sound, freeze_bgm);
}
