#include <6502.h>
#include <joystick.h>
#include <lynx.h>
#include <tgi.h>

#include "game.h"

#define GAME_COLOR_BLACK 0u
#define GAME_COLOR_WHITE 15u
#define GAME_COLOR_PLANET_BODY 1u
#define GAME_COLOR_PLANET_DETAIL 3u
#define GAME_COLOR_FAR_STAR 2u
#define GAME_COLOR_NEAR_STAR 7u
#define GAME_COLOR_PLAYER 10u
#define GAME_COLOR_BULLET 14u
#define GAME_COLOR_ENEMY_BULLET 6u
#define GAME_COLOR_SCOUT 4u
#define GAME_COLOR_SAUCER 12u
#define GAME_COLOR_DROPPER 9u
#define GAME_COLOR_POWER_ITEM 11u
#define GAME_COLOR_EXPLOSION 14u
#define SCORE_DIGITS 5u

typedef struct Star {
    unsigned char x;
    unsigned char y;
} Star;

typedef struct PlanetRun {
    unsigned char y;
    unsigned char x0;
    unsigned char x1;
    unsigned char color;
} PlanetRun;

static const PlanetRun planet_runs[32] = {
    { 0u, 11u, 20u, GAME_COLOR_PLANET_BODY },
    { 1u, 7u, 24u, GAME_COLOR_PLANET_BODY },
    { 2u, 5u, 26u, GAME_COLOR_PLANET_BODY },
    { 3u, 3u, 28u, GAME_COLOR_PLANET_BODY },
    { 4u, 2u, 29u, GAME_COLOR_PLANET_BODY },
    { 5u, 1u, 30u, GAME_COLOR_PLANET_BODY },
    { 6u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 7u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 8u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 9u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 10u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 11u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 12u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 13u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 14u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 15u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 16u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 17u, 0u, 31u, GAME_COLOR_PLANET_BODY },
    { 18u, 1u, 30u, GAME_COLOR_PLANET_BODY },
    { 19u, 2u, 29u, GAME_COLOR_PLANET_BODY },
    { 20u, 3u, 28u, GAME_COLOR_PLANET_BODY },
    { 21u, 5u, 26u, GAME_COLOR_PLANET_BODY },
    { 22u, 7u, 24u, GAME_COLOR_PLANET_BODY },
    { 23u, 11u, 20u, GAME_COLOR_PLANET_BODY },
    { 5u, 9u, 13u, GAME_COLOR_PLANET_DETAIL },
    { 6u, 7u, 15u, GAME_COLOR_PLANET_DETAIL },
    { 7u, 7u, 15u, GAME_COLOR_PLANET_DETAIL },
    { 8u, 9u, 13u, GAME_COLOR_PLANET_DETAIL },
    { 14u, 20u, 24u, GAME_COLOR_PLANET_DETAIL },
    { 15u, 18u, 25u, GAME_COLOR_PLANET_DETAIL },
    { 16u, 19u, 25u, GAME_COLOR_PLANET_DETAIL },
    { 17u, 21u, 23u, GAME_COLOR_PLANET_DETAIL }
};

static const Star far_stars[10] = {
    { 4u, 17u }, { 19u, 72u }, { 37u, 31u }, { 55u, 90u },
    { 74u, 52u }, { 91u, 14u }, { 108u, 81u }, { 127u, 39u },
    { 143u, 65u }, { 155u, 24u }
};

static const Star near_stars[7] = {
    { 11u, 42u }, { 33u, 84u }, { 58u, 20u }, { 82u, 62u },
    { 106u, 95u }, { 132u, 29u }, { 151u, 74u }
};

static const unsigned char player_masks[2][GAME_PLAYER_HEIGHT] = {
    { 0x18u, 0x3cu, 0xfeu, 0xffu, 0xfeu, 0x24u },
    { 0x18u, 0x7cu, 0xfeu, 0xffu, 0xfeu, 0x42u }
};

static const unsigned char enemy_masks[3][2][GAME_ENEMY_HEIGHT] = {
    {
        { 0x18u, 0x3cu, 0x7eu, 0xdbu, 0xffu, 0x24u, 0x42u, 0x81u },
        { 0x18u, 0x3cu, 0x7eu, 0xbdu, 0xffu, 0x42u, 0x24u, 0x81u }
    },
    {
        { 0x00u, 0x18u, 0x7eu, 0xffu, 0xbdu, 0x7eu, 0x24u, 0x00u },
        { 0x00u, 0x3cu, 0x7eu, 0xdbu, 0xffu, 0x7eu, 0x42u, 0x00u }
    },
    {
        { 0x24u, 0x7eu, 0x3cu, 0xffu, 0x7eu, 0x18u, 0x3cu, 0x24u },
        { 0x42u, 0x7eu, 0x3cu, 0xffu, 0x7eu, 0x18u, 0x24u, 0x18u }
    }
};

static const unsigned char power_item_mask[GAME_POWER_ITEM_HEIGHT] = {
    0x60u, 0xf0u, 0xf0u, 0x60u
};

static const unsigned char explosion_masks[GAME_EXPLOSION_STAGES][8] = {
    { 0x00u, 0x00u, 0x18u, 0x3cu, 0x3cu, 0x18u, 0x00u, 0x00u },
    { 0x00u, 0x24u, 0x18u, 0x7eu, 0x7eu, 0x18u, 0x24u, 0x00u },
    { 0x81u, 0x24u, 0x5au, 0x3cu, 0x3cu, 0x5au, 0x24u, 0x81u },
    { 0x42u, 0x81u, 0x24u, 0x00u, 0x00u, 0x24u, 0x81u, 0x42u }
};

static unsigned char read_input(void)
{
    unsigned char joy;
    unsigned char input;

    joy = joy_read(JOY_1);
    input = 0u;
    if ((joy & JOY_UP_MASK) != 0u) {
        input |= GAME_INPUT_UP;
    }
    if ((joy & JOY_DOWN_MASK) != 0u) {
        input |= GAME_INPUT_DOWN;
    }
    if ((joy & JOY_LEFT_MASK) != 0u) {
        input |= GAME_INPUT_LEFT;
    }
    if ((joy & JOY_RIGHT_MASK) != 0u) {
        input |= GAME_INPUT_RIGHT;
    }
    if ((joy & (JOY_BTN_1_MASK | JOY_BTN_2_MASK)) != 0u) {
        input |= GAME_INPUT_FIRE;
    }
    return input;
}

static void draw_rect(const GameRect* rect, unsigned char color)
{
    tgi_setcolor(color);
    tgi_bar(rect->x, rect->y,
        (unsigned int)rect->x + rect->width - 1u,
        (unsigned int)rect->y + rect->height - 1u);
}

static unsigned char scroll_x(unsigned char x, unsigned char offset)
{
    if (x >= offset) {
        return (unsigned char)(x - offset);
    }
    return (unsigned char)(GAME_SCREEN_WIDTH - (offset - x));
}

static void draw_planet(const GameState* game)
{
    unsigned char i;
    int draw_x;
    int draw_y;
    int x0;
    int x1;

    draw_x = (int)GAME_PLANET_BASE_X - (int)game->planet_offset;
    if (draw_x < -(int)GAME_PLANET_WIDTH) {
        draw_x += (int)GAME_PLANET_SCROLL_PERIOD;
    }
    for (i = 0u; i < 32u; ++i) {
        draw_y = (int)GAME_PLANET_BASE_Y + (int)planet_runs[i].y;
        if (draw_y < 0 || draw_y >= (int)GAME_SCREEN_HEIGHT) {
            continue;
        }
        x0 = draw_x + (int)planet_runs[i].x0;
        x1 = draw_x + (int)planet_runs[i].x1;
        if (x1 < 0 || x0 >= (int)GAME_SCREEN_WIDTH) {
            continue;
        }
        if (x0 < 0) {
            x0 = 0;
        }
        if (x1 >= (int)GAME_SCREEN_WIDTH) {
            x1 = (int)GAME_SCREEN_WIDTH - 1;
        }
        tgi_setcolor(planet_runs[i].color);
        tgi_bar((unsigned int)x0, (unsigned int)draw_y,
            (unsigned int)x1, (unsigned int)draw_y);
    }
}

static void draw_background(const GameState* game)
{
    unsigned char i;
    unsigned char x;
    unsigned int x1;

    tgi_setcolor(GAME_COLOR_FAR_STAR);
    for (i = 0u; i < 10u; ++i) {
        x = scroll_x(far_stars[i].x, game->far_star_offset);
        tgi_bar(x, far_stars[i].y, x, far_stars[i].y);
    }

    tgi_setcolor(GAME_COLOR_NEAR_STAR);
    for (i = 0u; i < 7u; ++i) {
        x = scroll_x(near_stars[i].x, game->near_star_offset);
        x1 = (unsigned int)x + 1u;
        if (x1 >= GAME_SCREEN_WIDTH) {
            x1 = GAME_SCREEN_WIDTH - 1u;
        }
        tgi_bar(x, near_stars[i].y, x1, near_stars[i].y);
    }
}

static void draw_mask(int x, int y,
    unsigned char width, unsigned char height,
    const unsigned char* rows, unsigned char color)
{
    unsigned char row;
    unsigned char column;
    unsigned char run_start;
    unsigned char mask;
    int draw_y;
    int x0;
    int x1;

    tgi_setcolor(color);
    for (row = 0u; row < height; ++row) {
        draw_y = y + row;
        if (draw_y < 0 || draw_y >= (int)GAME_SCREEN_HEIGHT) {
            continue;
        }
        column = 0u;
        while (column < width) {
            mask = (unsigned char)(0x80u >> column);
            if ((rows[row] & mask) == 0u) {
                ++column;
                continue;
            }
            run_start = column;
            do {
                ++column;
                if (column == width) {
                    break;
                }
                mask = (unsigned char)(0x80u >> column);
            } while ((rows[row] & mask) != 0u);

            x0 = x + run_start;
            x1 = x + column - 1u;
            if (x1 >= 0 && x0 < (int)GAME_SCREEN_WIDTH) {
                if (x0 < 0) {
                    x0 = 0;
                }
                if (x1 >= (int)GAME_SCREEN_WIDTH) {
                    x1 = (int)GAME_SCREEN_WIDTH - 1;
                }
                tgi_bar((unsigned int)x0, (unsigned int)draw_y,
                    (unsigned int)x1, (unsigned int)draw_y);
            }
        }
    }
}

static void format_score(unsigned long score, char* text)
{
    unsigned char i;

    text[SCORE_DIGITS] = '\0';
    for (i = SCORE_DIGITS; i != 0u; --i) {
        text[i - 1u] = (char)('0' + (score % 10ul));
        score /= 10ul;
    }
}

static void draw_game(const GameState* game)
{
    unsigned char i;
    char score_text[SCORE_DIGITS + 1u];
    char lives_text[2u];
    char power_text[2u];

    tgi_clear();
    draw_planet(game);
    draw_background(game);
    tgi_setcolor(GAME_COLOR_WHITE);
    tgi_line(0u, GAME_HUD_HEIGHT - 1u, GAME_SCREEN_WIDTH - 1u,
        GAME_HUD_HEIGHT - 1u);
    format_score(game->score, score_text);
    tgi_outtextxy(2u, 1u, "SCORE");
    tgi_outtextxy(42u, 1u, score_text);
    lives_text[0] = (char)('0' + game->lives);
    lives_text[1] = '\0';
    tgi_outtextxy(112u, 1u, "LIVES");
    tgi_outtextxy(152u, 1u, lives_text);
    power_text[0] = (char)('0' + game->weapon_level);
    power_text[1] = '\0';
    tgi_outtextxy(72u, 1u, "PWR");
    tgi_outtextxy(96u, 1u, power_text);

    if (game->game_over != 0u) {
        tgi_outtextxy(48u, 40u, "GAME OVER");
        tgi_outtextxy(36u, 58u, "A/B TO RESTART");
    } else {
        if (game->dying != 0u) {
            draw_mask((int)game->player.x,
                (int)game->player.y - 1, 8u, 8u,
                explosion_masks[game->explosion_timer /
                    GAME_EXPLOSION_STAGE_FRAMES],
                GAME_COLOR_EXPLOSION);
        } else if (game_player_is_visible(game) != 0u) {
            draw_mask(game->player.x, game->player.y, GAME_PLAYER_WIDTH,
                GAME_PLAYER_HEIGHT, player_masks[game->animation_frame],
                GAME_COLOR_PLAYER);
        }
        for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
            if (game->enemies[i].active != 0u &&
                game->enemies[i].rect.x < GAME_SCREEN_WIDTH) {
                draw_mask(game->enemies[i].rect.x,
                    game->enemies[i].rect.y, GAME_ENEMY_WIDTH,
                    GAME_ENEMY_HEIGHT,
                    enemy_masks[game->enemies[i].type]
                        [game->animation_frame],
                    game->enemies[i].type == GAME_ENEMY_TYPE_SCOUT ?
                        GAME_COLOR_SCOUT :
                        (game->enemies[i].type == GAME_ENEMY_TYPE_SAUCER ?
                            GAME_COLOR_SAUCER : GAME_COLOR_DROPPER));
            }
        }
        if (game->power_item.active != 0u) {
            draw_mask(game->power_item.rect.x, game->power_item.rect.y,
                GAME_POWER_ITEM_WIDTH, GAME_POWER_ITEM_HEIGHT,
                power_item_mask, GAME_COLOR_POWER_ITEM);
        }
        for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
            if (game->bullets[i].active != 0u) {
                draw_rect(&game->bullets[i].rect, GAME_COLOR_BULLET);
            }
        }
        for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
            if (game->enemy_bullets[i].active != 0u) {
                draw_rect(&game->enemy_bullets[i].rect,
                    GAME_COLOR_ENEMY_BULLET);
            }
        }
    }
    tgi_updatedisplay();
}

void main(void)
{
    GameState game;

    tgi_install(tgi_static_stddrv);
    tgi_init();
    joy_install(joy_static_stddrv);
    CLI();
    while (tgi_busy() != 0u) {
    }
    tgi_setbgcolor(GAME_COLOR_BLACK);
    tgi_setframerate(75u);
    game_init(&game);

    for (;;) {
        while (tgi_busy() != 0u) {
        }
        game_update(&game, read_input());
        draw_game(&game);
    }
}
