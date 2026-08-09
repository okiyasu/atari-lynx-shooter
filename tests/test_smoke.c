#include <stdio.h>
#include <stdlib.h>

#include "game.h"

static unsigned int checks;

static void expect(int condition, const char* message)
{
    ++checks;
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", message);
        exit(EXIT_FAILURE);
    }
}

static void advance_intro(GameState* game)
{
    unsigned int frame;

    for (frame = 0u; frame < GAME_STAGE_INTRO_FRAMES; ++frame) {
        game_update(game, 0u);
    }
}

int main(void)
{
    GameState game;
    unsigned char start_x;
    unsigned char bullet;

    game_init(&game);
    expect(game.stage == 1u && game.phase == GAME_PHASE_TITLE &&
        game.game_over == 0u,
        "boot starts title without GAME OVER");

    game_update(&game, GAME_INPUT_FIRE);
    expect(game.phase == GAME_PHASE_TITLE && game.title_start_armed == 0u &&
        game.game_over == 0u,
        "held boot fire cannot bypass the title");

    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_TITLE && game.title_start_armed != 0u &&
        game.game_over == 0u,
        "releasing fire arms the title start");

    game_update(&game, GAME_INPUT_FIRE);
    expect(game.phase == GAME_PHASE_TITLE &&
        game.title_voice_pending != 0u && game.phase_timer == 0u &&
        game.game_over == 0u,
        "fresh title fire queues voice without GAME OVER");
    game_title_voice_complete(&game);
    expect(game.phase == GAME_PHASE_STAGE_INTRO && game.phase_timer == 0u &&
        game.title_voice_pending == 0u && game.game_over == 0u,
        "voice completion starts Stage 1 INTRO without GAME OVER");

    advance_intro(&game);
    expect(game.phase == GAME_PHASE_NORMAL && game.game_over == 0u,
        "Stage 1 reaches NORMAL after exactly 90 updates without GAME OVER");

    start_x = game.player.x;
    game_update(&game, GAME_INPUT_RIGHT);
    expect(game.player.x > start_x && game.game_over == 0u,
        "right input moves the player without GAME OVER");

    game_update(&game, GAME_INPUT_FIRE);
    bullet = 0u;
    while (bullet < GAME_MAX_PLAYER_BULLETS &&
        game.bullets[bullet].active == 0u) {
        ++bullet;
    }
    expect(bullet < GAME_MAX_PLAYER_BULLETS && game.game_over == 0u,
        "fire input activates a player bullet without GAME OVER");

    printf("PASS: %u startup control smoke checks\n", checks);
    return EXIT_SUCCESS;
}
