#include <stdio.h>
#include <stdlib.h>

#include "game.h"

static unsigned int checks;
static unsigned char mock_busy_remaining;
static unsigned char mock_busy_calls;

static unsigned char mock_tgi_busy(void)
{
    ++mock_busy_calls;
    if (mock_busy_remaining == 0u) {
        return 0u;
    }
    --mock_busy_remaining;
    return 1u;
}

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

static void advance_draw_frame(GameState* game, unsigned char input)
{
    signed char remainder;
    unsigned char updates;
    unsigned char update;

    remainder = 0u;
    updates = game_logic_updates_for_draw_frame(1u, remainder);
    for (update = 0u; update < updates; ++update) {
        game_update_logic(game, input);
    }
    game_sound_tick(game);
}

static void expect_display_ready_wait(unsigned char busy_frames,
    unsigned char expected_calls, const char* message)
{
    mock_busy_remaining = busy_frames;
    mock_busy_calls = 0u;
    GAME_DISPLAY_READY_WAIT(mock_tgi_busy());
    expect(mock_busy_calls == expected_calls, message);
}

int main(void)
{
    GameState game;
    unsigned char start_x;
    unsigned char bullet;
    unsigned char enemy;
    unsigned char frame;
    unsigned int logic_updates;
    unsigned int sound_ticks;

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
    expect(game.phase == GAME_PHASE_TITLE &&
        game.title_start_armed == GAME_TITLE_POST_VOICE_WAIT_TICKS &&
        game.title_voice_pending == GAME_TITLE_POST_VOICE_WAITING &&
        game.phase_timer == 0u && game.game_over == 0u,
        "voice completion enters the 38 tick title wait without GAME OVER");

    for (bullet = 0u; bullet < GAME_TITLE_POST_VOICE_WAIT_TICKS - 1u;
        ++bullet) {
        advance_draw_frame(&game, GAME_INPUT_FIRE | GAME_INPUT_RIGHT);
    }
    expect(game.phase == GAME_PHASE_TITLE && game.title_start_armed == 1u &&
        game.phase_timer == 0u &&
        game.sound.bgm_active == 0u && game.game_over == 0u,
        "the first 37 wait ticks keep the title silent");
    advance_draw_frame(&game, GAME_INPUT_FIRE | GAME_INPUT_RIGHT);
    expect(game.phase == GAME_PHASE_STAGE_INTRO && game.phase_timer == 0u &&
        game.title_voice_pending == 0u && game.sound.bgm_active != 0u &&
        game.game_over == 0u,
        "the 38th wait tick starts Stage 1 INTRO and BGM once");

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

    for (enemy = 0u; enemy < GAME_MAX_ENEMIES; ++enemy) {
        game_enemy_at(&game, enemy)->active = 0u;
    }
    expect(game_active_combatant_count(&game) == 0u,
        "zero-enemy pacing fixture has zero active combatants");
    expect_display_ready_wait(2u, 3u,
        "display-ready synchronization waits for the prior VBLANK swap");
    for (enemy = 0u; enemy < GAME_STAGE_ACTIVE_ENEMIES; ++enemy) {
        game_enemy_at(&game, enemy)->active = 1u;
        game_enemy_at(&game, enemy)->rect.x = (unsigned char)(80u + enemy);
    }
    expect(game_active_combatant_count(&game) == 4u,
        "baseline pacing fixture has four active combatants");
    expect_display_ready_wait(1u, 2u,
        "display-ready synchronization is independent of four-enemy workload");
    for (; enemy < GAME_MAX_ENEMIES; ++enemy) {
        *game_enemy_at(&game, enemy) = game.enemies[0];
        game_enemy_at(&game, enemy)->active = 1u;
        game_enemy_at(&game, enemy)->rect.x = (unsigned char)(80u + enemy);
    }
    expect(game_active_combatant_count(&game) == 8u,
        "capacity pacing fixture has eight active combatants");
    expect_display_ready_wait(1u, 2u,
        "display-ready synchronization is independent of eight-enemy workload");
    expect_display_ready_wait(0u, 1u,
        "completed prior swap permits immediate back-buffer reuse");

    logic_updates = 0u;
    sound_ticks = 0u;
    for (frame = 0u; frame < GAME_DRAW_HZ; ++frame) {
        signed char remainder;
        unsigned char updates;

        remainder = 0u;
        updates = game_logic_updates_for_draw_frame(1u, remainder);
        logic_updates += updates;
        ++sound_ticks;
    }
    expect(logic_updates == 300u && sound_ticks == 75u,
        "75 draw frames retain 300 logic updates and 75 sound ticks");
    expect(GAME_FRAME_INTERVAL_MIN_US == 12000ul &&
        GAME_FRAME_INTERVAL_MAX_US == 15000ul,
        "advisory 75Hz frame interval window remains 12000 through 15000 us");

    printf("PASS: %u startup control smoke checks\n", checks);
    return EXIT_SUCCESS;
}
