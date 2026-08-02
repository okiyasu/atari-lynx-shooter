#include "game.h"

#define PLAYER_SPEED 2u
#define BULLET_SPEED 4u
#define FIRE_COOLDOWN_FRAMES 8u
#define ENEMY_X 140u
#define ENEMY_MIN_Y (GAME_HUD_HEIGHT + 3u)
#define ENEMY_Y_RANGE 78u

static void respawn_enemy(GameState* game)
{
    game->respawn_sequence = (unsigned char)(game->respawn_sequence + 1u);
    game->enemy.x = ENEMY_X;
    game->enemy.y = (unsigned char)(ENEMY_MIN_Y +
        ((unsigned int)game->respawn_sequence * 17u) % ENEMY_Y_RANGE);
}

static void fire_bullet(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            game->bullets[i].active = 1u;
            game->bullets[i].rect.x = (unsigned char)(game->player.x + GAME_PLAYER_WIDTH);
            game->bullets[i].rect.y = (unsigned char)(game->player.y + 2u);
            return;
        }
    }
}

void game_init(GameState* game)
{
    unsigned char i;

    game->player.x = 10u;
    game->player.y = 48u;
    game->player.width = GAME_PLAYER_WIDTH;
    game->player.height = GAME_PLAYER_HEIGHT;
    game->enemy.x = ENEMY_X;
    game->enemy.y = 47u;
    game->enemy.width = GAME_ENEMY_WIDTH;
    game->enemy.height = GAME_ENEMY_HEIGHT;
    game->score = 0ul;
    game->fire_cooldown = 0u;
    game->respawn_sequence = 0u;

    for (i = 0u; i < GAME_MAX_BULLETS; ++i) {
        game->bullets[i].active = 0u;
        game->bullets[i].rect.x = 0u;
        game->bullets[i].rect.y = 0u;
        game->bullets[i].rect.width = GAME_BULLET_WIDTH;
        game->bullets[i].rect.height = GAME_BULLET_HEIGHT;
    }
}

unsigned char game_aabb_intersects(const GameRect* a, const GameRect* b)
{
    return (unsigned char)(
        (unsigned int)a->x < (unsigned int)b->x + b->width &&
        (unsigned int)a->x + a->width > (unsigned int)b->x &&
        (unsigned int)a->y < (unsigned int)b->y + b->height &&
        (unsigned int)a->y + a->height > (unsigned int)b->y);
}

void game_update(GameState* game, unsigned char input)
{
    unsigned char i;

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

    if (game->fire_cooldown != 0u) {
        --game->fire_cooldown;
    }
    if ((input & GAME_INPUT_FIRE) != 0u && game->fire_cooldown == 0u) {
        fire_bullet(game);
        game->fire_cooldown = FIRE_COOLDOWN_FRAMES;
    }

    for (i = 0u; i < GAME_MAX_BULLETS; ++i) {
        if (game->bullets[i].active != 0u) {
            if (game->bullets[i].rect.x >
                GAME_SCREEN_WIDTH - GAME_BULLET_WIDTH - BULLET_SPEED) {
                game->bullets[i].active = 0u;
            } else {
                game->bullets[i].rect.x =
                    (unsigned char)(game->bullets[i].rect.x + BULLET_SPEED);
                if (game_aabb_intersects(&game->bullets[i].rect, &game->enemy) != 0u) {
                    game->bullets[i].active = 0u;
                    game->score += 100ul;
                    respawn_enemy(game);
                }
            }
        }
    }
}

