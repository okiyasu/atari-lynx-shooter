#ifndef GAME_H
#define GAME_H

#include "sound.h"

#define GAME_SCREEN_WIDTH 160u
#define GAME_SCREEN_HEIGHT 102u
#define GAME_HUD_HEIGHT 10u

#define GAME_PLAYER_WIDTH 8u
#define GAME_PLAYER_HEIGHT 6u
#define GAME_ENEMY_WIDTH 8u
#define GAME_ENEMY_HEIGHT 8u
#define GAME_PLAYER_BULLET_WIDTH 3u
#define GAME_PLAYER_BULLET_HEIGHT 2u
#define GAME_MAX_PLAYER_BULLETS 12u
#define GAME_ENEMY_BULLET_WIDTH 2u
#define GAME_ENEMY_BULLET_HEIGHT 2u
#define GAME_POWER_ITEM_WIDTH 4u
#define GAME_POWER_ITEM_HEIGHT 4u
#define GAME_MAX_ENEMIES 4u
#define GAME_MAX_ENEMY_BULLETS 16u
#define GAME_WEAPON_LEVEL_MIN 1u
#define GAME_WEAPON_LEVEL_MAX 3u
#define GAME_INITIAL_LIVES 3u
#define GAME_EXPLOSION_FRAMES 32u
#define GAME_EXPLOSION_STAGE_FRAMES 8u
#define GAME_EXPLOSION_STAGES 4u
#define GAME_INVINCIBILITY_FRAMES 60u
#define GAME_PLANET_WIDTH 32u
#define GAME_PLANET_HEIGHT 24u
#define GAME_PLANET_BASE_X 120u
#define GAME_PLANET_BASE_Y 18u
#define GAME_PLANET_SCROLL_INTERVAL 8u
#define GAME_PLANET_SCROLL_PERIOD 192u

#define GAME_STAGE_COUNT 3u
#define GAME_STAGE_INTRO_FRAMES 90u
#define GAME_NORMAL_FRAMES 1125u
#define GAME_WARNING_FRAMES 120u
#define GAME_STAGE_CLEAR_FRAMES 120u
#define GAME_LOGIC_UPDATES_NUMERATOR 5u
#define GAME_LOGIC_UPDATES_DENOMINATOR 4u

#define GAME_PHASE_STAGE_INTRO 0u
#define GAME_PHASE_NORMAL 1u
#define GAME_PHASE_WARNING 2u
#define GAME_PHASE_BOSS 3u
#define GAME_PHASE_STAGE_CLEAR 4u
#define GAME_PHASE_ALL_CLEAR 5u
#define GAME_PHASE_TITLE 6u

#define GAME_BACKGROUND_THEME_SPACE 0u
#define GAME_BACKGROUND_THEME_SKY 1u
#define GAME_BACKGROUND_THEME_CAVE 2u
#define GAME_BACKGROUND_THEME_COUNT 3u

#define GAME_ENVIRONMENT_ASTEROIDS 0u
#define GAME_ENVIRONMENT_WIND 1u
#define GAME_ENVIRONMENT_ROCKFALL 2u
#define GAME_ENVIRONMENT_COUNT 3u

#define GAME_MAX_ENVIRONMENT_OBJECTS 2u
#define GAME_ENVIRONMENT_OBJECT_WIDTH 8u
#define GAME_ENVIRONMENT_OBJECT_HEIGHT 8u
#define GAME_ASTEROID_EVENT_COUNT 6u
#define GAME_ROCKFALL_EVENT_COUNT 7u
#define GAME_WIND_EVENT_COUNT 3u
#define GAME_WIND_WARNING_FRAMES 45u
#define GAME_WIND_ACTIVE_FRAMES 150u
#define GAME_WIND_BAND_HEIGHT 24u
#define GAME_WIND_DIRECTION_UP 0u
#define GAME_WIND_DIRECTION_DOWN 1u
#define GAME_ROCK_WARNING_FRAMES 45u
#define GAME_ROCK_IMPACT_FRAMES 12u
#define GAME_ROCK_STATE_INACTIVE 0u
#define GAME_ROCK_STATE_WARNING 1u
#define GAME_ROCK_STATE_FALLING 2u
#define GAME_ROCK_STATE_IMPACT 3u
#define GAME_WIND_STATE_INACTIVE 0u
#define GAME_WIND_STATE_WARNING 1u
#define GAME_WIND_STATE_ACTIVE 2u

#define GAME_ENEMY_FORMATION_SPACE 0u
#define GAME_ENEMY_FORMATION_AIR 1u
#define GAME_ENEMY_FORMATION_CAVE 2u
#define GAME_ENEMY_FORMATION_COUNT 3u

#define GAME_BOSS_APPEARANCE_COMMON 0u
#define GAME_BOSS_APPEARANCE_SPACE_FORTRESS 1u
#define GAME_BOSS_APPEARANCE_AIR_CARRIER 2u
#define GAME_BOSS_APPEARANCE_ROCK_GUARDIAN 3u
#define GAME_BOSS_APPEARANCE_COUNT 4u

#define GAME_BOSS_SHOT_STRAIGHT 0u
#define GAME_BOSS_SHOT_FAN 1u
#define GAME_BOSS_SHOT_ALTERNATE 2u
#define GAME_BOSS_SHOT_PINCER 3u
#define GAME_BOSS_SHOT_BURST 4u
#define GAME_BOSS_SHOT_CANNON_CYCLE 5u

#define GAME_BOSS_MOVE_STILL 0u
#define GAME_BOSS_MOVE_VERTICAL 1u
#define GAME_BOSS_MOVE_WIDE 2u

#define GAME_ENEMY_PATTERN_STRAIGHT 0u
#define GAME_ENEMY_PATTERN_WAVE 1u
#define GAME_ENEMY_PATTERN_DIVE 2u

#define GAME_ENEMY_TYPE_SCOUT 0u
#define GAME_ENEMY_TYPE_SAUCER 1u
#define GAME_ENEMY_TYPE_DROPPER 2u
#define GAME_ENEMY_TYPE_FIGHTER 3u
#define GAME_ENEMY_TYPE_BOMBER 4u
#define GAME_ENEMY_TYPE_SUPPLY 5u
#define GAME_ENEMY_TYPE_CAVE_BAT 6u
#define GAME_ENEMY_TYPE_ROCK_WORM 7u
#define GAME_ENEMY_TYPE_MINING_DRONE 8u
#define GAME_ENEMY_TYPE_COUNT 9u

#define GAME_INPUT_UP 0x01u
#define GAME_INPUT_DOWN 0x02u
#define GAME_INPUT_LEFT 0x04u
#define GAME_INPUT_RIGHT 0x08u
#define GAME_INPUT_FIRE 0x10u

typedef struct GameRect {
    unsigned char x;
    unsigned char y;
    unsigned char width;
    unsigned char height;
} GameRect;

typedef struct GameBullet {
    GameRect rect;
    unsigned char active;
} GameBullet;

typedef struct GameEnemyBullet {
    GameRect rect;
    unsigned char active;
    signed char velocity_x;
    signed char velocity_y;
} GameEnemyBullet;

typedef struct GameEnemy {
    GameRect rect;
    unsigned char active;
    unsigned char type;
    unsigned char pattern;
    unsigned char base_y;
    unsigned char move_counter;
    unsigned char phase;
    unsigned char direction;
    unsigned char fire_interval;
    unsigned char fire_counter;
    unsigned char drops_power;
} GameEnemy;

typedef struct GamePowerItem {
    GameRect rect;
    unsigned char active;
    unsigned char move_counter;
} GamePowerItem;

typedef struct GameBoss {
    GameRect rect;
    unsigned char active;
    unsigned char hp;
    unsigned char max_hp;
    unsigned char config_id;
    unsigned char appearance_id;
    unsigned char script_step;
    unsigned char attack_timer;
    unsigned char move_phase;
    unsigned char direction;
    unsigned char alternate_cannon;
} GameBoss;

typedef struct GameAsteroid {
    GameRect rect;
    unsigned char active;
} GameAsteroid;

typedef struct GameFallingRock {
    GameRect rect;
    unsigned char state;
    unsigned char timer;
} GameFallingRock;

typedef struct GameWindBand {
    unsigned char state;
    unsigned char y;
    unsigned char direction;
    unsigned char timer;
    unsigned char push_counter;
} GameWindBand;

typedef struct GameStageConfig {
    unsigned char background_theme_id;
    unsigned char enemy_formation_id;
    unsigned char boss_config_id;
    unsigned char boss_appearance_id;
    unsigned char environment_id;
} GameStageConfig;

typedef struct GameEnemyFormationSlot {
    unsigned char x;
    unsigned char y;
    unsigned char type;
    unsigned char pattern;
    unsigned char fire_interval;
    unsigned char fire_phase;
} GameEnemyFormationSlot;

typedef struct GameBossConfig {
    unsigned char width;
    unsigned char height;
    unsigned char stop_x;
    unsigned char start_y;
    unsigned char max_hp;
    unsigned int defeat_score;
    unsigned char movement;
    unsigned char script_offset;
    unsigned char script_count;
} GameBossConfig;

typedef struct GameBossStep {
    unsigned char shot_type;
    unsigned char duration;
    unsigned char fire_interval;
    unsigned char movement;
} GameBossStep;

typedef struct GameState {
    GameRect player;
    GameEnemy enemies[GAME_MAX_ENEMIES];
    GameBullet bullets[GAME_MAX_PLAYER_BULLETS];
    GameEnemyBullet enemy_bullets[GAME_MAX_ENEMY_BULLETS];
    GamePowerItem power_item;
    GameBoss boss;
    GameAsteroid asteroids[GAME_MAX_ENVIRONMENT_OBJECTS];
    GameFallingRock falling_rocks[GAME_MAX_ENVIRONMENT_OBJECTS];
    GameWindBand wind;
    unsigned long score;
    unsigned char fire_cooldown;
    unsigned char weapon_level;
    unsigned char respawn_sequence;
    unsigned char lives;
    unsigned char game_over;
    unsigned char restart_armed;
    unsigned char title_start_armed;
    unsigned char dying;
    unsigned char explosion_timer;
    unsigned char invincibility_timer;
    unsigned char planet_offset;
    unsigned char planet_counter;
    unsigned char far_star_offset;
    unsigned char near_star_offset;
    unsigned char far_star_counter;
    unsigned char near_star_counter;
    unsigned char animation_counter;
    unsigned char animation_frame;
    unsigned char environment_event_cursor;
    unsigned char stage;
    unsigned char phase;
    unsigned int phase_timer;
    SoundState sound;
} GameState;

#ifdef GAME_PERF_INSTRUMENT
/* Host-only counters. Normal ROM builds do not include these or their state. */
typedef struct GamePerfCounters {
    unsigned long logic_updates;
    unsigned long normal_updates;
    unsigned long player_bullet_slots;
    unsigned long enemy_collision_slots;
    unsigned long enemy_bullet_slots;
    unsigned long normal_hit_flag_slots;
} GamePerfCounters;

void game_perf_reset(void);
const GamePerfCounters* game_perf_get(void);
#endif

void game_init(GameState* game);
void game_start(GameState* game);
unsigned char game_logic_updates_for_draw_frame(unsigned char* remainder);
void game_update_logic(GameState* game, unsigned char input);
void game_sound_tick(GameState* game);
void game_update(GameState* game, unsigned char input);
unsigned char game_aabb_intersects(const GameRect* a, const GameRect* b);
unsigned char game_player_is_visible(const GameState* game);
const GameStageConfig* game_get_stage_config(unsigned char stage);
const GameEnemyFormationSlot* game_get_enemy_formation_slot(
    unsigned char formation_id, unsigned char slot);
const GameBossConfig* game_get_boss_config(unsigned char stage);
const GameBossStep* game_get_boss_step(unsigned char index);

#endif
