#include <6502.h>
#include <joystick.h>
#include <lynx.h>
#include <tgi.h>

#include "game.h"

#define GAME_COLOR_BLACK 0u
#define GAME_COLOR_WHITE 15u
#define GAME_COLOR_PLAYER 10u
#define GAME_COLOR_BULLET 14u
#define GAME_COLOR_ENEMY 4u
#define SCORE_DIGITS 5u

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

    tgi_clear();
    tgi_setcolor(GAME_COLOR_WHITE);
    tgi_line(0u, GAME_HUD_HEIGHT - 1u, GAME_SCREEN_WIDTH - 1u,
        GAME_HUD_HEIGHT - 1u);
    format_score(game->score, score_text);
    tgi_outtextxy(2u, 1u, "SCORE");
    tgi_outtextxy(42u, 1u, score_text);

    draw_rect(&game->player, GAME_COLOR_PLAYER);
    draw_rect(&game->enemy, GAME_COLOR_ENEMY);
    for (i = 0u; i < GAME_MAX_BULLETS; ++i) {
        if (game->bullets[i].active != 0u) {
            draw_rect(&game->bullets[i].rect, GAME_COLOR_BULLET);
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
