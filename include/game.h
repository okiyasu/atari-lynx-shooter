#ifndef GAME_H
#define GAME_H

#define GAME_SCREEN_WIDTH 160u
#define GAME_SCREEN_HEIGHT 102u
#define GAME_HUD_HEIGHT 10u

#define GAME_PLAYER_WIDTH 8u
#define GAME_PLAYER_HEIGHT 6u
#define GAME_ENEMY_WIDTH 8u
#define GAME_ENEMY_HEIGHT 8u
#define GAME_BULLET_WIDTH 3u
#define GAME_BULLET_HEIGHT 2u
#define GAME_MAX_BULLETS 3u

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

typedef struct GameState {
    GameRect player;
    GameRect enemy;
    GameBullet bullets[GAME_MAX_BULLETS];
    unsigned long score;
    unsigned char fire_cooldown;
    unsigned char respawn_sequence;
} GameState;

void game_init(GameState* game);
void game_update(GameState* game, unsigned char input);
unsigned char game_aabb_intersects(const GameRect* a, const GameRect* b);

#endif

