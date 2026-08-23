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

static void disable_enemies(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game_enemy_at(game, i)->active = 0u;
    }
}

static void init_normal(GameState* game)
{
    unsigned char i;

    game_start(game);
    game->phase = GAME_PHASE_NORMAL;
    game->phase_timer = 0u;
    game->invincibility_timer = 0u;
    disable_enemies(game);
    for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
        game->asteroids[i].active = 0u;
        game->falling_rocks[i].state = GAME_ROCK_STATE_INACTIVE;
    }
    game->player.x = 40u;
    game->player.y = 40u;
}

static unsigned char scb_skipped(unsigned char active, unsigned char y)
{
    /* Exact production predicate in movable_scb_update(): an enemy bullet
     * is submitted only when active and below the HUD. */
    return (unsigned char)(active == 0u || y < GAME_HUD_HEIGHT);
}

static const GameAps055TraceEvent* only_event(void)
{
    const GameAps055Trace* trace;

    trace = game_aps055_trace_get();
    expect(trace->event_count == 1u,
        "one normal logic update produces one APS-055 trace event");
    return &trace->events[0];
}

static void test_collision_consumes_before_draw(void)
{
    GameState game;
    const GameAps055TraceEvent* event;

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game.enemy_bullets[0].velocity_x = (signed char)-2;
    game.enemy_bullets[0].velocity_y = 0;
    game_aps055_trace_reset();
    game_update_logic(&game, 0u);
    event = only_event();

    expect(event->before_active[0] != 0u && event->before_x[0] == 42u &&
        event->before_y[0] == 40u && scb_skipped(event->before_active[0],
            event->before_y[0]) == 0u,
        "enemy bullet is active and SCB-visible at draw input state");
    expect(event->after_move_active[0] != 0u &&
        event->after_move_x[0] == 40u && event->after_move_y[0] == 40u,
        "enemy bullet moves into the player before collision evaluation");
    expect(event->enemy_bullet_damage != 0u &&
        event->enemy_body_damage == 0u && event->asteroid_damage == 0u &&
        event->rock_damage == 0u,
        "damage source is enemy bullet only");
    expect(event->after_collision_active[0] == 0u &&
        scb_skipped(event->after_collision_active[0],
            event->after_collision_y[0]) != 0u,
        "collision consumes enemy bullet before draw SCB update");
    expect(event->final_active[0] == 0u && event->dying_after != 0u &&
        event->lives_after == GAME_INITIAL_LIVES - 1u,
        "same logic update starts player death after bullet consumption");
    printf("TRACE collision: before active/x/y=%u/%u/%u, after_move=%u/%u/%u, "
        "after_collision active/x/y=%u/%u/%u, source=enemy_bullet, "
        "draw=SKIP\n",
        event->before_active[0], event->before_x[0], event->before_y[0],
        event->after_move_active[0], event->after_move_x[0],
        event->after_move_y[0], event->after_collision_active[0],
        event->after_collision_x[0], event->after_collision_y[0]);
}

static void test_active_scb_predicate(void)
{
    GameState game;
    const GameAps055TraceEvent* event;

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 100u;
    game.enemy_bullets[0].rect.y = 8u;
    game_aps055_trace_reset();
    game_update_logic(&game, 0u);
    event = only_event();
    expect(event->final_active[0] != 0u && event->final_x[0] == 98u &&
        event->final_y[0] == 8u &&
        scb_skipped(event->final_active[0], event->final_y[0]) != 0u,
        "active enemy bullet above HUD is deliberately SCB-skipped");

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 100u;
    game.enemy_bullets[0].rect.y = 40u;
    game_aps055_trace_reset();
    game_update_logic(&game, 0u);
    event = only_event();
    expect(event->final_active[0] != 0u && event->final_x[0] == 98u &&
        event->final_y[0] == 40u &&
        scb_skipped(event->final_active[0], event->final_y[0]) == 0u,
        "active enemy bullet below HUD remains SCB-visible at rect x/y");
    printf("TRACE draw predicate: active/y=1/8 -> SKIP; active/x/y=1/98/40 "
        "-> visible\n");
}

static void test_catchup_and_aps054_boundary(void)
{
    GameState game;
    const GameAps055Trace* trace;
    unsigned char updates;

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game_aps055_trace_reset();
    updates = game_logic_updates_for_draw_frame(1u, 0);
    while (updates != 0u && game.dying == 0u) {
        game_update_logic(&game, 0u);
        --updates;
    }
    trace = game_aps055_trace_get();
    expect(trace->event_count == 1u && game.dying != 0u,
        "one elapsed VBlank catch-up invokes collision before the draw");
    printf("TRACE catch-up: elapsed=1 requests four logic updates; "
        "enemy bullet consumed in first logic update; draw slot=SKIP\n");

    init_normal(&game);
    game_aps055_trace_reset();
    game_update_logic(&game, GAME_INPUT_RIGHT);
    trace = game_aps055_trace_get();
    expect(trace->event_count == 1u && game.player.x == 40u &&
        game.player_x_credit == 2,
        "APS-054 changes player position only after accumulated motion credit");
    printf("TRACE APS-054: one logic update with RIGHT player x=40 credit=2; "
        "enemy bullet update/collision path unchanged\n");
}

static void test_enemy_bullet_75hz_normalization(void)
{
    GameState game;
    unsigned char i;

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 100u;
    game.enemy_bullets[0].rect.y = 40u;
    game.enemy_bullets[0].velocity_x = (signed char)-2;
    game.enemy_bullets[0].velocity_y = (signed char)1;
    game_aps055_trace_reset();
    for (i = 0u; i < 4u; ++i) {
        game_update_logic(&game, 0u);
    }
    expect(game.enemy_bullets[0].active != 0u &&
        game.enemy_bullets[0].rect.x == 98u &&
        game.enemy_bullets[0].rect.y == 41u,
        "elapsed=1 equivalent four logic updates move enemy bullet by velocity");

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 100u;
    game.enemy_bullets[0].rect.y = 40u;
    game.enemy_bullets[0].velocity_x = (signed char)-2;
    game.enemy_bullets[0].velocity_y = (signed char)1;
    game_aps055_trace_reset();
    for (i = 0u; i < 12u; ++i) {
        game_update_logic(&game, 0u);
    }
    expect(game.enemy_bullets[0].active != 0u &&
        game.enemy_bullets[0].rect.x == 94u &&
        game.enemy_bullets[0].rect.y == 43u,
        "elapsed=3 equivalent twelve logic updates move enemy bullet three times");
    printf("TRACE normalized: 4 logic updates delta=(-2,+1); "
        "12 logic updates delta=(-6,+3)\n");
}

int main(void)
{
    test_collision_consumes_before_draw();
    test_active_scb_predicate();
    test_catchup_and_aps054_boundary();
    test_enemy_bullet_75hz_normalization();
    printf("PASS: %u APS-055 diagnostic checks\n", checks);
    return EXIT_SUCCESS;
}
