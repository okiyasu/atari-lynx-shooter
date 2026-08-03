#ifndef GAME_H
#define GAME_H

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
#define GAME_MAX_ENEMY_BULLETS 6u
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

#define GAME_ENEMY_PATTERN_STRAIGHT 0u
#define GAME_ENEMY_PATTERN_WAVE 1u
#define GAME_ENEMY_PATTERN_DIVE 2u

#define GAME_ENEMY_TYPE_SCOUT 0u
#define GAME_ENEMY_TYPE_SAUCER 1u
#define GAME_ENEMY_TYPE_DROPPER 2u

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

typedef struct GameEnemy {
    GameRect rect;
    unsigned char active;
    unsigned char type;
    unsigned char pattern;
    unsigned char base_y;
    unsigned char move_counter;
    unsigned char phase;
    unsigned char direction;
    unsigned char fire_counter;
} GameEnemy;

typedef struct GamePowerItem {
    GameRect rect;
    unsigned char active;
    unsigned char move_counter;
} GamePowerItem;

typedef struct GameState {
    GameRect player;
    GameEnemy enemies[GAME_MAX_ENEMIES];
    GameBullet bullets[GAME_MAX_PLAYER_BULLETS];
    GameBullet enemy_bullets[GAME_MAX_ENEMY_BULLETS];
    GamePowerItem power_item;
    unsigned long score;
    unsigned char fire_cooldown;
    unsigned char weapon_level;
    unsigned char respawn_sequence;
    unsigned char lives;
    unsigned char game_over;
    unsigned char restart_armed;
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
} GameState;

void game_init(GameState* game);
void game_update(GameState* game, unsigned char input);
unsigned char game_aabb_intersects(const GameRect* a, const GameRect* b);
unsigned char game_player_is_visible(const GameState* game);

#endif
