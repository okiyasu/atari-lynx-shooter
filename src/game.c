#include "game.h"

#define PLAYER_SPEED 2u /* pixels per 75Hz draw frame */
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
#define PLAYER_BULLET_RESULT_POWER_ITEM 0x01u
#define PLAYER_BULLET_RESULT_ENEMY_DESTROYED 0x02u

#if defined(GAME_PERF_LEGACY_HIT_RESCAN) && !defined(GAME_PERF_INSTRUMENT)
#error GAME_PERF_LEGACY_HIT_RESCAN requires GAME_PERF_INSTRUMENT
#endif

#ifdef GAME_PERF_INSTRUMENT
static GamePerfCounters game_perf_counters;

#define GAME_PERF_COUNT(field) ++game_perf_counters.field
#else
#define GAME_PERF_COUNT(field) ((void)0)
#endif

#ifdef GAME_APS055_DIAGNOSTIC
static GameAps055Trace aps055_trace;
static unsigned char aps055_current_event;

static void aps055_copy_bullets(unsigned char* active, unsigned char* x,
    unsigned char* y, const GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        active[i] = game->enemy_bullets[i].active;
        x[i] = game->enemy_bullets[i].rect.x;
        y[i] = game->enemy_bullets[i].rect.y;
    }
}

void game_aps055_trace_reset(void)
{
    unsigned char* bytes;
    unsigned int i;

    bytes = (unsigned char*)&aps055_trace;
    for (i = 0u; i < sizeof(aps055_trace); ++i) {
        bytes[i] = 0u;
    }
    aps055_current_event = 0u;
}

const GameAps055Trace* game_aps055_trace_get(void)
{
    return &aps055_trace;
}

static void aps055_begin(const GameState* game)
{
    GameAps055TraceEvent* event;

    if (aps055_trace.event_count >= GAME_APS055_TRACE_MAX_UPDATES) {
        return;
    }
    aps055_current_event = aps055_trace.event_count;
    ++aps055_trace.event_count;
    event = &aps055_trace.events[aps055_current_event];
    event->player_x_before = game->player.x;
    event->player_y_before = game->player.y;
    aps055_copy_bullets(event->before_active, event->before_x,
        event->before_y, game);
}

static GameAps055TraceEvent* aps055_event(void)
{
    if (aps055_current_event >= aps055_trace.event_count) {
        return (GameAps055TraceEvent*)0;
    }
    return &aps055_trace.events[aps055_current_event];
}

static void aps055_after_move(const GameState* game)
{
    GameAps055TraceEvent* event;

    event = aps055_event();
    if (event != (GameAps055TraceEvent*)0) {
        aps055_copy_bullets(event->after_move_active, event->after_move_x,
            event->after_move_y, game);
    }
}

static void aps055_after_collision(const GameState* game)
{
    GameAps055TraceEvent* event;

    event = aps055_event();
    if (event != (GameAps055TraceEvent*)0) {
        aps055_copy_bullets(event->after_collision_active,
            event->after_collision_x, event->after_collision_y, game);
    }
}

static void aps055_finish(const GameState* game)
{
    GameAps055TraceEvent* event;

    event = aps055_event();
    if (event != (GameAps055TraceEvent*)0) {
        aps055_copy_bullets(event->final_active, event->final_x,
            event->final_y, game);
        event->player_x_after = game->player.x;
        event->player_y_after = game->player.y;
        event->dying_after = game->dying;
        event->lives_after = game->lives;
    }
}

static void aps055_mark_body(void)
{
    GameAps055TraceEvent* event;
    event = aps055_event();
    if (event != (GameAps055TraceEvent*)0) {
        event->enemy_body_damage = 1u;
    }
}

static void aps055_mark_enemy_bullet(void)
{
    GameAps055TraceEvent* event;
    event = aps055_event();
    if (event != (GameAps055TraceEvent*)0) {
        event->enemy_bullet_damage = 1u;
    }
}

static void aps055_mark_asteroid(void)
{
    GameAps055TraceEvent* event;
    event = aps055_event();
    if (event != (GameAps055TraceEvent*)0) {
        event->asteroid_damage = 1u;
    }
}

static void aps055_mark_rock(void)
{
    GameAps055TraceEvent* event;
    event = aps055_event();
    if (event != (GameAps055TraceEvent*)0) {
        event->rock_damage = 1u;
    }
}
#endif

#ifdef APS056_DIAGNOSTIC
GameAps056ScbTrace aps056_scb_trace;

void game_aps056_scb_trace_reset(void)
{
    unsigned char* bytes;
    unsigned int i;

    bytes = (unsigned char*)&aps056_scb_trace;
    for (i = 0u; i < sizeof(aps056_scb_trace); ++i) {
        bytes[i] = 0u;
    }
}

const GameAps056ScbTrace* game_aps056_scb_trace_get(void)
{
    return &aps056_scb_trace;
}

unsigned char game_aps056_scb_trace_is_latched(void)
{
    return aps056_scb_trace.latched;
}

void game_aps056_scb_trace_begin(unsigned char active_count,
    unsigned char visible_count, unsigned char header_penpal0)
{
    if (aps056_scb_trace.latched != 0u) {
        return;
    }
    aps056_scb_trace.latched = 1u;
    aps056_scb_trace.active_count = active_count;
    aps056_scb_trace.visible_count = visible_count;
    aps056_scb_trace.header_penpal0 = header_penpal0;
}

void game_aps056_scb_trace_capture_slot(unsigned char slot_index,
    const unsigned char* scb)
{
    GameAps056ScbTraceSlot* slot;

    if (aps056_scb_trace.latched == 0u ||
        slot_index >= GAME_MAX_ENEMY_BULLETS) {
        return;
    }
    slot = &aps056_scb_trace.slots[slot_index];
    slot->slot_index = slot_index;
    slot->sprctl0 = scb[0];
    slot->sprctl1 = scb[1];
    slot->hpos[0] = scb[7];
    slot->hpos[1] = scb[8];
    slot->vpos[0] = scb[9];
    slot->vpos[1] = scb[10];
    slot->data[0] = scb[5];
    slot->data[1] = scb[6];
    slot->next[0] = scb[3];
    slot->next[1] = scb[4];
    if (aps056_scb_trace.slot_count <= slot_index) {
        aps056_scb_trace.slot_count = (unsigned char)(slot_index + 1u);
    }
}

void game_aps056_scb_trace_submit_before(void)
{
    if (aps056_scb_trace.latched != 0u) {
        aps056_scb_trace.submit_before = GAME_APS056_TRACE_BEFORE_MARKER;
    }
}

void game_aps056_scb_trace_submit_after(void)
{
    if (aps056_scb_trace.latched != 0u &&
        aps056_scb_trace.submit_after == 0u) {
        aps056_scb_trace.submit_after = GAME_APS056_TRACE_AFTER_MARKER;
        aps056_scb_trace.submit_count = 1u;
    }
}
#endif

typedef struct EnemyMovementConfig {
    unsigned char horizontal_speed;
    unsigned char vertical_interval;
    unsigned char vertical_amplitude;
    unsigned char behavior;
} EnemyMovementConfig;

static const EnemyMovementConfig enemy_movements[3] = {
    { 1u, 0u, 0u, GAME_ENEMY_PATTERN_STRAIGHT },
    { 1u, 3u, 6u, GAME_ENEMY_PATTERN_WAVE },
    { 1u, 2u, 12u, GAME_ENEMY_PATTERN_DIVE }
};

#ifdef GAME_PERF_INSTRUMENT
void game_perf_reset(void)
{
    unsigned char* bytes;
    unsigned int i;

    bytes = (unsigned char*)&game_perf_counters;
    for (i = 0u; i < sizeof(game_perf_counters); ++i) {
        bytes[i] = 0u;
    }
}

const GamePerfCounters* game_perf_get(void)
{
    return &game_perf_counters;
}
#endif

static void enter_phase(GameState* game, unsigned char phase);
static void return_to_title(GameState* game);

static void clear_game_state(GameState* game)
{
    unsigned char* bytes;
    unsigned int i;

#ifdef __CC65__
    bytes = (unsigned char*)&game->player;
    for (i = 0u; i < sizeof(*game) - sizeof(game->enemies); ++i) {
        bytes[i] = 0u;
    }
#else
    bytes = (unsigned char*)game;
    for (i = 0u; i < sizeof(*game); ++i) {
        bytes[i] = 0u;
    }
#endif
#ifdef APS056_DIAGNOSTIC
    game->diagnostic_controls = 0u;
    game->diagnostic_damage_source = GAME_DIAGNOSTIC_DAMAGE_NONE;
#endif
}

const GameStageConfig* game_get_stage_config(unsigned char stage)
{
    if (stage < 1u || stage > GAME_STAGE_COUNT) {
        return (const GameStageConfig*)0;
    }
    return &game_stage_configs[stage - 1u];
}

const GameEnemyFormationSlot* game_get_enemy_formation_slot(
    unsigned char formation_id, unsigned char slot)
{
    if (formation_id >= GAME_ENEMY_FORMATION_COUNT ||
        slot >= GAME_STAGE_ACTIVE_ENEMIES) {
        return (const GameEnemyFormationSlot*)0;
    }
    return &game_enemy_formation_configs[formation_id].slots[slot];
}

const GameBossConfig* game_get_boss_config(unsigned char stage)
{
    if (stage < 1u || stage > GAME_STAGE_COUNT) {
        return (const GameBossConfig*)0;
    }
    return &game_boss_configs[game_stage_configs[stage - 1u].boss_config_id];
}

const GameBossStep* game_get_boss_step(unsigned char index)
{
    if (index >= GAME_BOSS_STEP_COUNT) {
        return (const GameBossStep*)0;
    }
    return &game_boss_steps[index];
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

    game->enemy_bullet_move_phase = 0u;
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game->enemy_bullets[i].active = 0u;
    }
}

static void clear_enemies(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game_enemy_at(game, i)->active = 0u;
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

static void reset_player_motion_credit(GameState* game)
{
    game->player_x_credit = 0;
    game->player_y_credit = 0;
}

/* Fire interval per enemy type (APS-021): replaces a nine-branch if
 * chain with a table indexed by the contiguous GAME_ENEMY_TYPE_* ids.
 * Out-of-range types keep the previous fall-through value. */
static const unsigned char enemy_fire_intervals[GAME_ENEMY_TYPE_COUNT] = {
    ENEMY_SCOUT_FIRE_INTERVAL, ENEMY_SAUCER_FIRE_INTERVAL,
    ENEMY_DROPPER_FIRE_INTERVAL, ENEMY_FIGHTER_FIRE_INTERVAL,
    ENEMY_BOMBER_FIRE_INTERVAL, ENEMY_SUPPLY_FIRE_INTERVAL,
    ENEMY_CAVE_BAT_FIRE_INTERVAL, ENEMY_ROCK_WORM_FIRE_INTERVAL,
    ENEMY_MINING_DRONE_FIRE_INTERVAL
};

unsigned char game_enemy_fire_interval(unsigned char type)
{
    if (type >= GAME_ENEMY_TYPE_COUNT) {
        return ENEMY_MINING_DRONE_FIRE_INTERVAL;
    }
    return enemy_fire_intervals[type];
}

unsigned char game_enemy_drops_power(unsigned char type)
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
    enemy->fire_counter = (unsigned char)(fire_phase % fire_interval);
}

static void reset_enemy_formation(GameState* game)
{
    const GameStageConfig* stage_config;
    const GameEnemyFormationConfig* formation;
    unsigned char i;

    stage_config = &game_stage_configs[game->stage - 1u];
    formation = &game_enemy_formation_configs[stage_config->enemy_formation_id];
    game->respawn_sequence = 0u;
    for (i = 0u; i < GAME_STAGE_ACTIVE_ENEMIES; ++i) {
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

    stage_config = &game_stage_configs[game->stage - 1u];
    formation = &game_enemy_formation_configs[stage_config->enemy_formation_id];
    if (slot >= GAME_STAGE_ACTIVE_ENEMIES) {
        game_enemy_at(game, slot)->active = 0u;
        return;
    }
    game->respawn_sequence = (unsigned char)(game->respawn_sequence + 1u);
    seed = (unsigned int)game->respawn_sequence + slot;
    enemy = game_enemy_at(game, slot);
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
        game_enemy_fire_interval(type),
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

/* One background scroll layer: advance its divider counter and wrap
 * the pixel offset inside its period (APS-021): update_scrolling
 * previously repeated this block for all three layers. */
static void advance_scroll_layer(unsigned char* counter,
    unsigned char interval, unsigned char* offset, unsigned char period)
{
    ++*counter;
    if (*counter == interval) {
        *counter = 0u;
        if (*offset == (unsigned char)(period - 1u)) {
            *offset = 0u;
        } else {
            ++*offset;
        }
    }
}

static void update_scrolling(GameState* game)
{
    advance_scroll_layer(&game->planet_counter,
        GAME_PLANET_SCROLL_INTERVAL, &game->planet_offset,
        GAME_PLANET_SCROLL_PERIOD);
    advance_scroll_layer(&game->far_star_counter, FAR_STAR_INTERVAL,
        &game->far_star_offset, GAME_SCREEN_WIDTH);
    advance_scroll_layer(&game->near_star_counter, NEAR_STAR_INTERVAL,
        &game->near_star_offset, GAME_SCREEN_WIDTH);

    ++game->animation_counter;
    if (game->animation_counter == ANIMATION_INTERVAL) {
        game->animation_counter = 0u;
        game->animation_frame = (unsigned char)(1u - game->animation_frame);
    }
}

static void move_player_axis(unsigned char* coordinate,
    signed char* credit,
    unsigned char input, unsigned char negative, unsigned char positive,
    unsigned char minimum, unsigned char maximum)
{
    if ((input & negative) != 0u) {
        if ((input & positive) != 0u || *coordinate == minimum) {
            *credit = 0;
            return;
        }
        *credit = (signed char)(*credit - (signed char)PLAYER_SPEED);
        if (*credit == (signed char)-4) {
            --*coordinate;
            *credit = 0;
        }
        return;
    }
    if ((input & positive) == 0u || *coordinate == maximum) {
        *credit = 0;
    } else {
        *credit = (signed char)(*credit + (signed char)PLAYER_SPEED);
        if (*credit == (signed char)4) {
            ++*coordinate;
            *credit = 0;
        }
    }
}

static void move_player(GameState* game, unsigned char input)
{
    move_player_axis(&game->player.x, &game->player_x_credit,
        input, GAME_INPUT_LEFT, GAME_INPUT_RIGHT,
        0u, GAME_SCREEN_WIDTH - GAME_PLAYER_WIDTH);
    move_player_axis(&game->player.y, &game->player_y_credit,
        input, GAME_INPUT_UP, GAME_INPUT_DOWN,
        GAME_HUD_HEIGHT, GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT);
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

static unsigned char rect_intersects_position(const GameRect* rect,
    const GamePosition* position, unsigned char width, unsigned char height)
{
    return (unsigned char)(
        (unsigned int)rect->x < (unsigned int)position->x + width &&
        (unsigned int)rect->x + rect->width > (unsigned int)position->x &&
        (unsigned int)rect->y < (unsigned int)position->y + height &&
        (unsigned int)rect->y + rect->height > (unsigned int)position->y);
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
    if (rect_intersects_position(&game->player, &game->power_item.rect,
        GAME_POWER_ITEM_WIDTH, GAME_POWER_ITEM_HEIGHT) != 0u) {
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

    if (game->enemy_bullet_move_phase != 0u) {
        if (game->enemy_bullet_move_phase == 3u) {
            game->enemy_bullet_move_phase = 0u;
        } else {
            ++game->enemy_bullet_move_phase;
        }
        return;
    }
    game->enemy_bullet_move_phase = 1u;
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        int x;
        int y;

        GAME_PERF_COUNT(enemy_bullet_slots);
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

    config = &game_boss_configs[game->boss.config_id];
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
    game->boss.config_id = game_stage_configs[game->stage - 1u].boss_config_id;
    game->boss.appearance_id =
        game_stage_configs[game->stage - 1u].boss_appearance_id;
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
    config = &game_boss_configs[game->boss.config_id];
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

    config = &game_boss_configs[game->boss.config_id];
    step_index = (unsigned char)(config->script_offset +
        game->boss.script_step);
    step = &game_boss_steps[step_index];
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
    reset_player_motion_credit(game);
    game->dying = 1u;
    game->explosion_timer = 0u;
    game->invincibility_timer = 0u;
    sound_stop_bgm(&game->sound);
    sound_request_sfx(&game->sound, SOUND_SFX_PLAYER_EXPLOSION);
}

static void update_player_death(GameState* game)
{
    if (sound_sfx_is_active(&game->sound,
        SOUND_SFX_PLAYER_EXPLOSION) != 0u) {
        if (game->explosion_timer < GAME_EXPLOSION_FRAMES - 1u) {
            ++game->explosion_timer;
        }
        return;
    }

    game->dying = 0u;
    game->explosion_timer = 0u;
    if (game->lives == 0u) {
        game->game_over = 1u;
        game->restart_armed = 0u;
        game->game_over_voice_pending = 1u;
        game->game_over_voice_complete = 0u;
        reset_environment(game);
        sound_stop_all(&game->sound);
        return;
    }

    game->player.x = 10u;
    game->player.y = 48u;
    reset_player_motion_credit(game);
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
    sound_set_stage(&game->sound, game->stage);
    if (game->phase == GAME_PHASE_NORMAL &&
        game->phase_timer == GAME_NORMAL_FRAMES) {
        enter_phase(game, GAME_PHASE_WARNING);
    }
}

static void enter_phase(GameState* game, unsigned char phase)
{
    game->phase = phase;
    game->phase_timer = 0u;
    if (phase == GAME_PHASE_STAGE_INTRO ||
        phase == GAME_PHASE_STAGE_CLEAR ||
        phase == GAME_PHASE_ALL_CLEAR ||
        phase == GAME_PHASE_TITLE) {
        reset_player_motion_credit(game);
    }
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

    clear_game_state(game);
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
    game->title_start_armed = 0u;
    game->title_voice_pending = 0u;
    game->game_over_voice_pending = 0u;
    game->game_over_voice_complete = 0u;
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
    game->phase = GAME_PHASE_TITLE;
    game->phase_timer = 0u;
    sound_init(&game->sound);

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game_enemy_at(game, i)->rect.width = GAME_ENEMY_WIDTH;
        game_enemy_at(game, i)->rect.height = GAME_ENEMY_HEIGHT;
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
        game->enemy_bullets[i].velocity_x = (signed char)-2;
        game->enemy_bullets[i].velocity_y = (signed char)0;
    }
    game->power_item.rect.x = 0u;
    game->power_item.rect.y = 0u;
    clear_power_item(game);
    game->boss.rect.x = 0u;
    game->boss.rect.y = 0u;
    game->boss.rect.width = 0u;
    game->boss.rect.height = 0u;
    clear_boss(game);
    reset_environment(game);
    sound_stop_all(&game->sound);
}

void game_start(GameState* game)
{
    game_init(game);
    game->phase = GAME_PHASE_STAGE_INTRO;
    sound_init(&game->sound);
}

void game_title_voice_complete(GameState* game)
{
    if (game->phase == GAME_PHASE_TITLE &&
        game->title_voice_pending == GAME_TITLE_VOICE_PENDING) {
        game->title_voice_pending = GAME_TITLE_POST_VOICE_WAITING;
        game->title_start_armed = GAME_TITLE_POST_VOICE_WAIT_TICKS;
    }
}

void game_game_over_voice_complete(GameState* game)
{
    if (game->game_over != 0u &&
        game->game_over_voice_pending != 0u) {
        game->game_over_voice_pending = 0u;
        game->game_over_voice_complete = 1u;
        game->restart_armed = 0u;
    }
}

static void return_to_title(GameState* game)
{
    game_init(game);
}

unsigned char game_aabb_intersects(const GameRect* a, const GameRect* b)
{
    return (unsigned char)(
        (unsigned int)a->x < (unsigned int)b->x + b->width &&
        (unsigned int)a->x + a->width > (unsigned int)b->x &&
        (unsigned int)a->y < (unsigned int)b->y + b->height &&
        (unsigned int)a->y + a->height > (unsigned int)b->y);
}

#ifdef GAME_COMBATANT_INSTRUMENT
unsigned char game_active_combatant_count(const GameState* game)
{
    unsigned char count;
    unsigned char i;

    count = (unsigned char)(game->boss.active != 0u ?
        GAME_BOSS_COMBATANT_WEIGHT : 0u);
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        const GameEnemy* enemy;

        enemy = game_enemy_at(game, i);
        if (enemy->active != 0u && enemy->rect.x < GAME_SCREEN_WIDTH) {
            count = (unsigned char)(count + GAME_NORMAL_COMBATANT_WEIGHT);
        }
    }
    return count;
}
#endif

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

#ifdef APS056_DIAGNOSTIC
void game_diagnostic_update_controls(GameState* game, unsigned char input)
{
    unsigned char controls;

    controls = game->diagnostic_controls;
    if ((input & GAME_INPUT_DIAGNOSTIC_OPT1) != 0u) {
        controls |= GAME_DIAGNOSTIC_CONTROL_LOGIC_FROZEN;
    } else {
        controls &= (unsigned char)~GAME_DIAGNOSTIC_CONTROL_LOGIC_FROZEN;
    }
    if ((input & GAME_INPUT_DIAGNOSTIC_OPT2) != 0u) {
        if ((controls & GAME_DIAGNOSTIC_CONTROL_OPT2_HELD) == 0u) {
            controls ^= GAME_DIAGNOSTIC_CONTROL_BULLET_WHITE;
        }
        controls |= GAME_DIAGNOSTIC_CONTROL_OPT2_HELD;
    } else {
        controls &= (unsigned char)~GAME_DIAGNOSTIC_CONTROL_OPT2_HELD;
    }
    game->diagnostic_controls = controls;
}

#ifndef __CC65__
unsigned char game_enemy_bullet_active_count(const GameState* game)
{
    unsigned char count;
    unsigned char i;

    count = 0u;
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active != 0u) {
            ++count;
        }
    }
    return count;
}
#endif
#endif

/* Moves one active player bullet one step to the right, deactivating it
 * at the screen edge (APS-021): shared by the normal and boss bullet
 * updates, which previously repeated this advance verbatim. Returns 0
 * when the bullet left the screen. */
static unsigned char advance_player_bullet(GameBullet* bullet)
{
    if (bullet->rect.x >
        GAME_SCREEN_WIDTH - GAME_PLAYER_BULLET_WIDTH - BULLET_SPEED) {
        bullet->active = 0u;
        return 0u;
    }
    bullet->rect.x = (unsigned char)(bullet->rect.x + BULLET_SPEED);
    return 1u;
}

static unsigned char update_player_bullets_normal(GameState* game,
    unsigned char* hit_enemies)
{
    unsigned char i;
    unsigned char j;
#ifdef GAME_PERF_LEGACY_HIT_RESCAN
    unsigned char power_item_created;
#else
    unsigned char result;
#endif

#ifdef GAME_PERF_LEGACY_HIT_RESCAN
    power_item_created = 0u;
#else
    result = 0u;
#endif
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        GAME_PERF_COUNT(player_bullet_slots);
        if (game->bullets[i].active == 0u) {
            continue;
        }
        if (advance_player_bullet(&game->bullets[i]) == 0u) {
            continue;
        }
        for (j = 0u; j < GAME_MAX_ENEMIES; ++j) {
            GameEnemy* enemy;

            GAME_PERF_COUNT(enemy_collision_slots);
            enemy = game_enemy_at(game, j);
            if (enemy->active != 0u &&
                enemy->rect.x < GAME_SCREEN_WIDTH &&
                hit_enemies[j] == 0u &&
                game_aabb_intersects(&game->bullets[i].rect,
                    &enemy->rect) != 0u) {
                game->bullets[i].active = 0u;
                game->score += 100ul;
                if (game_enemy_drops_power(enemy->type) != 0u) {
#ifdef GAME_PERF_LEGACY_HIT_RESCAN
                    power_item_created = spawn_power_item(game, enemy);
#else
                    if (spawn_power_item(game, enemy) != 0u) {
                        result |= PLAYER_BULLET_RESULT_POWER_ITEM;
                    } else {
                        result = (unsigned char)(result &
                            (unsigned char)~PLAYER_BULLET_RESULT_POWER_ITEM);
                    }
#endif
                }
                respawn_enemy(game, j);
                hit_enemies[j] = 1u;
#ifndef GAME_PERF_LEGACY_HIT_RESCAN
                result |= PLAYER_BULLET_RESULT_ENEMY_DESTROYED;
#endif
                break;
            }
        }
    }
#ifdef GAME_PERF_LEGACY_HIT_RESCAN
    return power_item_created;
#else
    return result;
#endif
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
    const GameStageConfig* stage_config;
    const GameEnvironmentConfig* environment;
    const GameEnvironmentEvent* event;
    unsigned int elapsed;
    unsigned char cursor;
    unsigned char slot;

    stage_config = &game_stage_configs[game->stage - 1u];
    environment = &game_environment_configs[stage_config->environment_id];
    elapsed = game->phase_timer + 1u;
    cursor = game->environment_event_cursor;
    slot = ENVIRONMENT_NO_NEW_SLOT;
    if (cursor >= environment->event_count) {
        return slot;
    }
    event = &game_environment_events[environment->event_offset + cursor];
    if (elapsed != event->frame) {
        return slot;
    }
    if (environment->kind == GAME_ENVIRONMENT_ASTEROIDS) {
        slot = find_free_asteroid(game);
        if (slot != ENVIRONMENT_NO_NEW_SLOT) {
            game->asteroids[slot].active = 1u;
            game->asteroids[slot].rect.x = ASTEROID_START_X;
            game->asteroids[slot].rect.y = event->position;
        }
        ++game->environment_event_cursor;
    } else if (environment->kind == GAME_ENVIRONMENT_WIND) {
        game->wind.state = GAME_WIND_STATE_WARNING;
        game->wind.y = event->position;
        game->wind.direction = event->direction;
        game->wind.timer = GAME_WIND_WARNING_FRAMES;
        game->wind.push_counter = 0u;
        ++game->environment_event_cursor;
        slot = 0u;
    } else {
        slot = find_free_rock(game);
        if (slot != ENVIRONMENT_NO_NEW_SLOT) {
            game->falling_rocks[slot].state = GAME_ROCK_STATE_WARNING;
            game->falling_rocks[slot].timer = GAME_ROCK_WARNING_FRAMES;
            game->falling_rocks[slot].rect.x = event->position;
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
                rect_intersects_position(&game->bullets[i].rect,
                    &game->asteroids[j].rect,
                    GAME_ENVIRONMENT_OBJECT_WIDTH,
                    GAME_ENVIRONMENT_OBJECT_HEIGHT) != 0u) {
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
        if (rect_intersects_position(&game->player,
            &game->asteroids[i].rect,
            GAME_ENVIRONMENT_OBJECT_WIDTH,
            GAME_ENVIRONMENT_OBJECT_HEIGHT) != 0u) {
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
            if (rect_intersects_position(&game->player, &rock->rect,
                GAME_ENVIRONMENT_OBJECT_WIDTH,
                GAME_ENVIRONMENT_OBJECT_HEIGHT) != 0u) {
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
    unsigned char player_bullet_result;
    unsigned char damage;
    unsigned char new_environment_slot;
    unsigned char enemy_destroyed;
    unsigned char power_item_collected;
#if defined(GAME_APS055_DIAGNOSTIC) || defined(APS056_DIAGNOSTIC)
    unsigned char damage_before_environment;
#endif
#ifdef APS056_DIAGNOSTIC
    unsigned char diagnostic_source;
#endif
    const GameStageConfig* stage_config;

    GAME_PERF_COUNT(normal_updates);
#ifdef GAME_APS055_DIAGNOSTIC
    aps055_begin(game);
#endif
    move_player(game, input);
    stage_config = &game_stage_configs[game->stage - 1u];
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
        GAME_PERF_COUNT(normal_hit_flag_slots);
        hit_enemies[i] = 0u;
    }
    player_bullet_result = update_player_bullets_normal(game, hit_enemies);
#ifdef GAME_PERF_LEGACY_HIT_RESCAN
    /* Host-only baseline: preserve the pre-APS-019 second flag scan. */
    power_item_created = (unsigned char)(player_bullet_result &
        PLAYER_BULLET_RESULT_POWER_ITEM);
    enemy_destroyed = 0u;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        GAME_PERF_COUNT(normal_hit_flag_slots);
        if (hit_enemies[i] != 0u) {
            enemy_destroyed = 1u;
        }
    }
#else
    power_item_created = (unsigned char)(player_bullet_result &
        PLAYER_BULLET_RESULT_POWER_ITEM);
    enemy_destroyed = (unsigned char)(player_bullet_result &
        PLAYER_BULLET_RESULT_ENEMY_DESTROYED);
#endif
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
#ifdef GAME_APS055_DIAGNOSTIC
    aps055_after_move(game);
#endif

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        GameEnemy* enemy;
        unsigned char interval;

        enemy = game_enemy_at(game, i);
        if (enemy->active == 0u || hit_enemies[i] != 0u) {
            continue;
        }
        if (enemy->rect.x >= GAME_SCREEN_WIDTH) {
            --enemy->rect.x;
            continue;
        }
        update_enemy_movement(enemy);
        interval = game_enemy_fire_interval(enemy->type);
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
#ifdef APS056_DIAGNOSTIC
    diagnostic_source = GAME_DIAGNOSTIC_DAMAGE_NONE;
#endif
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        GameEnemy* enemy;

        enemy = game_enemy_at(game, i);
        if (enemy->active != 0u && hit_enemies[i] == 0u &&
            enemy->rect.x < GAME_SCREEN_WIDTH &&
            game_aabb_intersects(&game->player,
                &enemy->rect) != 0u) {
            damage = 1u;
#ifdef APS056_DIAGNOSTIC
            diagnostic_source = GAME_DIAGNOSTIC_DAMAGE_ENEMY_BODY;
#endif
#ifdef GAME_APS055_DIAGNOSTIC
            aps055_mark_body();
#endif
        }
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        GAME_PERF_COUNT(enemy_bullet_slots);
        if (game->enemy_bullets[i].active != 0u &&
            game->enemy_bullets[i].rect.y >= GAME_HUD_HEIGHT &&
            rect_intersects_position(&game->player,
                &game->enemy_bullets[i].rect,
                GAME_ENEMY_BULLET_WIDTH,
                GAME_ENEMY_BULLET_HEIGHT) != 0u) {
            game->enemy_bullets[i].active = 0u;
            damage = 1u;
#ifdef APS056_DIAGNOSTIC
            diagnostic_source = GAME_DIAGNOSTIC_DAMAGE_ENEMY_BULLET;
#endif
#ifdef GAME_APS055_DIAGNOSTIC
            aps055_mark_enemy_bullet();
#endif
        }
    }
    if (stage_config->environment_id == GAME_ENVIRONMENT_ASTEROIDS) {
#if defined(GAME_APS055_DIAGNOSTIC) || defined(APS056_DIAGNOSTIC)
        damage_before_environment = damage;
#endif
        update_asteroids(game, new_environment_slot, &damage);
#ifdef APS056_DIAGNOSTIC
        if (damage_before_environment == 0u && damage != 0u) {
            diagnostic_source = GAME_DIAGNOSTIC_DAMAGE_ASTEROID;
        }
#endif
#ifdef GAME_APS055_DIAGNOSTIC
        if (damage_before_environment == 0u && damage != 0u) {
            aps055_mark_asteroid();
        }
#endif
    } else if (stage_config->environment_id == GAME_ENVIRONMENT_ROCKFALL) {
#if defined(GAME_APS055_DIAGNOSTIC) || defined(APS056_DIAGNOSTIC)
        damage_before_environment = damage;
#endif
        update_falling_rocks(game, new_environment_slot, &damage);
#ifdef APS056_DIAGNOSTIC
        if (damage_before_environment == 0u && damage != 0u) {
            diagnostic_source = GAME_DIAGNOSTIC_DAMAGE_FALLING_ROCK;
        }
#endif
#ifdef GAME_APS055_DIAGNOSTIC
        if (damage_before_environment == 0u && damage != 0u) {
            aps055_mark_rock();
        }
#endif
    }
#ifdef GAME_APS055_DIAGNOSTIC
    aps055_after_collision(game);
#endif
#ifdef APS056_DIAGNOSTIC
    game->diagnostic_damage_source = diagnostic_source;
#endif
    apply_damage(game, damage, was_invincible);
#ifdef GAME_APS055_DIAGNOSTIC
    aps055_finish(game);
#endif
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
        if (advance_player_bullet(&game->bullets[i]) == 0u) {
            continue;
        }
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

    config = &game_boss_configs[game->boss.config_id];
    game->score += config->defeat_score;
    sound_request_sfx(&game->sound, SOUND_SFX_BOSS_DEFEAT);
    enter_phase(game, GAME_PHASE_STAGE_CLEAR);
}

static void update_boss(GameState* game, unsigned char input,
    unsigned char was_invincible)
{
    unsigned char i;
    unsigned char damage;
#ifdef APS056_DIAGNOSTIC
    unsigned char diagnostic_source;
#endif

#ifdef GAME_APS055_DIAGNOSTIC
    aps055_begin(game);
#endif
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
#ifdef GAME_APS055_DIAGNOSTIC
    aps055_after_move(game);
#endif
    update_boss_attack(game);

    damage = (unsigned char)(game->boss.active != 0u &&
        game_aabb_intersects(&game->player, &game->boss.rect) != 0u);
#ifdef APS056_DIAGNOSTIC
    diagnostic_source = GAME_DIAGNOSTIC_DAMAGE_NONE;
    if (damage != 0u) {
        diagnostic_source = GAME_DIAGNOSTIC_DAMAGE_ENEMY_BODY;
    }
#endif
#ifdef GAME_APS055_DIAGNOSTIC
    if (damage != 0u) {
        aps055_mark_body();
    }
#endif
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active != 0u &&
            rect_intersects_position(&game->player,
                &game->enemy_bullets[i].rect,
                GAME_ENEMY_BULLET_WIDTH,
                GAME_ENEMY_BULLET_HEIGHT) != 0u) {
            game->enemy_bullets[i].active = 0u;
            damage = 1u;
#ifdef APS056_DIAGNOSTIC
            diagnostic_source = GAME_DIAGNOSTIC_DAMAGE_ENEMY_BULLET;
#endif
#ifdef GAME_APS055_DIAGNOSTIC
            aps055_mark_enemy_bullet();
#endif
        }
    }
#ifdef GAME_APS055_DIAGNOSTIC
    aps055_after_collision(game);
#endif
#ifdef APS056_DIAGNOSTIC
    game->diagnostic_damage_source = diagnostic_source;
#endif
    apply_damage(game, damage, was_invincible);
#ifdef GAME_APS055_DIAGNOSTIC
    aps055_finish(game);
#endif
    ++game->phase_timer;
}

unsigned char game_logic_updates_for_draw_frame(unsigned int elapsed_vblanks,
    signed char remainder)
{
#ifdef __CC65__
    /* The Lynx production scheduler has denominator 1, so its remainder is
     * permanently zero. A bounded fixed-step loop deliberately discards
     * excess credit instead of carrying it into a later outer loop. */
    (void)remainder;
    if (elapsed_vblanks >= GAME_LOGIC_UPDATES_MAX /
        GAME_LOGIC_UPDATES_NUMERATOR) {
        return GAME_LOGIC_UPDATES_MAX;
    }
    return (unsigned char)(elapsed_vblanks *
        GAME_LOGIC_UPDATES_NUMERATOR);
#else
    unsigned char base;

    if (elapsed_vblanks > GAME_LOGIC_UPDATES_MAX /
        GAME_LOGIC_UPDATES_NUMERATOR) {
        return GAME_LOGIC_UPDATES_MAX;
    }
    base = (unsigned char)(elapsed_vblanks * GAME_LOGIC_UPDATES_NUMERATOR);
    if (remainder < 0) {
        if (base <= (unsigned char)(-remainder)) {
            return 0u;
        }
        return (unsigned char)(base - (unsigned char)(-remainder));
    }
    if ((unsigned char)remainder >=
        (unsigned char)(GAME_LOGIC_UPDATES_MAX - base)) {
        return GAME_LOGIC_UPDATES_MAX;
    }
    return (unsigned char)(base + (unsigned char)remainder);
#endif
}

void game_update_logic(GameState* game, unsigned char input)
{
    unsigned char was_invincible;

    GAME_PERF_COUNT(logic_updates);
#ifdef APS056_DIAGNOSTIC
    game_diagnostic_update_controls(game, input);
    if ((game->diagnostic_controls & GAME_DIAGNOSTIC_CONTROL_LOGIC_FROZEN) !=
        0u) {
        return;
    }
#endif
    if (game->phase == GAME_PHASE_TITLE) {
        if (game->title_voice_pending != 0u) {
            return;
        }
        if ((input & GAME_INPUT_FIRE) == 0u) {
            game->title_start_armed = 1u;
        } else if (game->title_start_armed != 0u) {
            game->title_start_armed = 0u;
            game->title_voice_pending = GAME_TITLE_VOICE_PENDING;
        }
        return;
    }
    if (game->game_over != 0u) {
        if (game->game_over_voice_complete == 0u) {
            game->restart_armed = 0u;
            return;
        }
        if ((input & GAME_INPUT_FIRE) == 0u) {
            game->restart_armed = 1u;
        } else if (game->restart_armed != 0u) {
            return_to_title(game);
        }
        return;
    }
    if (game->phase == GAME_PHASE_ALL_CLEAR) {
        if ((input & GAME_INPUT_FIRE) == 0u) {
            game->restart_armed = 1u;
        } else if (game->restart_armed != 0u) {
            game_start(game);
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

void game_sound_tick(GameState* game)
{
    unsigned char freeze_bgm;

    if (game->title_voice_pending == GAME_TITLE_POST_VOICE_WAITING &&
        --game->title_start_armed == 0u) {
        game_start(game);
    }
    freeze_bgm = game->dying;
    sound_tick(&game->sound, freeze_bgm);
}

void game_update(GameState* game, unsigned char input)
{
    game_update_logic(game, input);
    game_sound_tick(game);
}
