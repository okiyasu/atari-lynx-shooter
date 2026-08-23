#include <stdio.h>
#include <stdlib.h>

#include "game.h"

static unsigned int checks;

typedef struct HostScbEntry {
    unsigned char source_active;
    unsigned char source_x;
    unsigned char source_y;
    unsigned char sprctl1;
    signed int hpos;
    signed int vpos;
    unsigned char slot;
    unsigned char next_slot;
    unsigned char data_present;
} HostScbEntry;

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
    game->player.x = 20u;
    game->player.y = 70u;
}

/* Host projection of the exact production enemy-bullet branch in
 * movable_scb_update(). CADENCE captures the real SCB values from main.c;
 * this projection keeps the host checks independent of Gearlynx timing. */
static HostScbEntry project_slot(const GameEnemyBullet* source,
    unsigned char slot)
{
    HostScbEntry result;

    result.source_active = source->active;
    result.source_x = source->rect.x;
    result.source_y = source->rect.y;
    result.hpos = (signed int)source->rect.x;
    result.vpos = (signed int)source->rect.y;
    result.slot = slot;
    result.next_slot = (unsigned char)(slot + 1u < GAME_MAX_ENEMY_BULLETS ?
        slot + 1u : 0u);
    result.data_present = 1u;
    result.sprctl1 = (unsigned char)(0x08u |
        (source->active != 0u && source->rect.y >= GAME_HUD_HEIGHT ?
            0u : 0x04u));
    return result;
}

static void test_active_slot_values(void)
{
    GameState game;
    HostScbEntry entry;

    init_normal(&game);
    game.enemy_bullets[3].active = 1u;
    game.enemy_bullets[3].rect.x = 100u;
    game.enemy_bullets[3].rect.y = 40u;
    game.enemy_bullets[3].velocity_x = 0;
    game.enemy_bullets[3].velocity_y = 0;
    game_update_logic(&game, 0u);
    entry = project_slot(&game.enemy_bullets[3], 3u);

    expect(entry.source_active != 0u && entry.source_x == 100u &&
        entry.source_y == 40u, "active source state reaches draw boundary");
    expect(entry.sprctl1 == 0x08u && entry.hpos == 100 &&
        entry.vpos == 40, "active in-play bullet writes non-SKIP hpos/vpos");
    expect(entry.slot == 3u && entry.next_slot == 4u &&
        entry.data_present != 0u, "slot mapping and data pointer remain valid");
}

static void test_collision_slot_is_skipped_after_consumption(void)
{
    GameState game;
    HostScbEntry entry;

    init_normal(&game);
    game.player.x = 100u;
    game.player.y = 40u;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 102u;
    game.enemy_bullets[0].rect.y = 40u;
    game.enemy_bullets[0].velocity_x = (signed char)-2;
    game.enemy_bullets[0].velocity_y = 0;
    game_update_logic(&game, 0u);
    entry = project_slot(&game.enemy_bullets[0], 0u);

    expect(game.enemy_bullets[0].active == 0u && game.dying != 0u,
        "collision consumes bullet before draw boundary");
    expect(entry.sprctl1 == 0x0Cu && entry.data_present != 0u,
        "consumed source maps to same slot with SKIP and intact data");
}

static void test_hud_boundary_and_catchup(void)
{
    GameState game;
    HostScbEntry entry;
    unsigned char i;

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 159u;
    game.enemy_bullets[0].rect.y = GAME_HUD_HEIGHT;
    game.enemy_bullets[0].velocity_x = 0;
    game.enemy_bullets[0].velocity_y = 0;
    for (i = 0u; i < 4u; ++i) {
        game_update_logic(&game, 0u);
    }
    entry = project_slot(&game.enemy_bullets[0], 0u);
    expect(entry.sprctl1 == 0x08u && entry.hpos == 159 &&
        entry.vpos == GAME_HUD_HEIGHT,
        "catch-up keeps in-play boundary bullet visible at y=HUD height");

    game.enemy_bullets[0].rect.y = (unsigned char)(GAME_HUD_HEIGHT - 1u);
    entry = project_slot(&game.enemy_bullets[0], 0u);
    expect(entry.sprctl1 == 0x0Cu,
        "active bullet above HUD is the only predicate-driven SKIP case");
}

static void test_collision_boundaries_and_hidden_bullets(void)
{
    GameState game;

    init_normal(&game);
    game.player.y = GAME_HUD_HEIGHT;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = (unsigned char)(GAME_HUD_HEIGHT - 2u);
    game.enemy_bullets[0].velocity_x = 0;
    game.enemy_bullets[0].velocity_y = 0;
    game_update_logic(&game, 0u);
    expect(game.enemy_bullets[0].active != 0u && game.dying == 0u,
        "enemy bullet at y=8 is hidden and excluded from damage");

    init_normal(&game);
    game.player.y = GAME_HUD_HEIGHT;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = (unsigned char)(GAME_HUD_HEIGHT - 1u);
    game.enemy_bullets[0].velocity_x = 0;
    game.enemy_bullets[0].velocity_y = 0;
    game_update_logic(&game, 0u);
    expect(game.enemy_bullets[0].active != 0u && game.dying == 0u,
        "enemy bullet at y=9 is hidden and excluded from damage");

    init_normal(&game);
    game.player.y = GAME_HUD_HEIGHT;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = GAME_HUD_HEIGHT;
    game.enemy_bullets[0].velocity_x = 0;
    game.enemy_bullets[0].velocity_y = 0;
    game_update_logic(&game, 0u);
    expect(game.enemy_bullets[0].active == 0u && game.dying != 0u,
        "enemy bullet at y=10 retains in-play damage");

    init_normal(&game);
    game_enemy_at(&game, 0u)->active = 1u;
    game_enemy_at(&game, 0u)->rect.x = 0u;
    game_enemy_at(&game, 0u)->rect.y = 20u;
    game_enemy_at(&game, 0u)->base_y = 20u;
    game_enemy_at(&game, 0u)->pattern = GAME_ENEMY_PATTERN_STRAIGHT;
    game_update_logic(&game, 0u);
    expect(game.dying == 0u,
        "non-contact enemy body at x=0 does not cause damage");

    init_normal(&game);
    game.player.x = 0u;
    game_enemy_at(&game, 0u)->active = 1u;
    game_enemy_at(&game, 0u)->rect.x = 0u;
    game_enemy_at(&game, 0u)->rect.y = game.player.y;
    game_enemy_at(&game, 0u)->base_y = game.player.y;
    game_enemy_at(&game, 0u)->pattern = GAME_ENEMY_PATTERN_STRAIGHT;
    game_update_logic(&game, 0u);
    expect(game.dying != 0u,
        "contacting enemy body at x=0 retains damage");

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x +
        GAME_PLAYER_WIDTH);
    game.enemy_bullets[0].rect.y = game.player.y;
    game.enemy_bullets[0].velocity_x = 0;
    game.enemy_bullets[0].velocity_y = 0;
    game_update_logic(&game, 0u);
    expect(game.enemy_bullets[0].active != 0u && game.dying == 0u,
        "enemy bullet at x right boundary remains non-contact");

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x +
        GAME_PLAYER_WIDTH - 1u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game.enemy_bullets[0].velocity_x = 0;
    game.enemy_bullets[0].velocity_y = 0;
    game_update_logic(&game, 0u);
    expect(game.enemy_bullets[0].active == 0u && game.dying != 0u,
        "enemy bullet at x right overlap boundary retains damage");
}

#ifdef APS056_DIAGNOSTIC
static void test_controls_active_count_and_damage_sources(void)
{
    GameState game;
    unsigned char i;
    unsigned int frozen_timer;

    init_normal(&game);
    expect(game_enemy_bullet_active_count(&game) == 0u,
        "diagnostic active count starts at zero");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game.enemy_bullets[i].active = 1u;
    }
    expect(game_enemy_bullet_active_count(&game) == GAME_MAX_ENEMY_BULLETS,
        "diagnostic active count reaches the 16-slot upper boundary");

    frozen_timer = game.phase_timer;
    game_update_logic(&game, GAME_INPUT_DIAGNOSTIC_OPT1);
    expect((game.diagnostic_controls & GAME_DIAGNOSTIC_CONTROL_LOGIC_FROZEN) !=
        0u &&
        game.phase_timer == frozen_timer,
        "OPT1 freezes logic without advancing the phase timer");
    game_update_logic(&game, 0u);
    expect((game.diagnostic_controls & GAME_DIAGNOSTIC_CONTROL_LOGIC_FROZEN) ==
        0u,
        "releasing OPT1 resumes diagnostic control state");

    expect((game.diagnostic_controls &
        GAME_DIAGNOSTIC_CONTROL_BULLET_WHITE) == 0u,
        "enemy bullet starts in danger color mode");
    game_diagnostic_update_controls(&game, GAME_INPUT_DIAGNOSTIC_OPT2);
    expect((game.diagnostic_controls &
        GAME_DIAGNOSTIC_CONTROL_BULLET_WHITE) != 0u,
        "OPT2 rising edge switches enemy bullets to white");
    game_diagnostic_update_controls(&game, GAME_INPUT_DIAGNOSTIC_OPT2);
    expect((game.diagnostic_controls &
        GAME_DIAGNOSTIC_CONTROL_BULLET_WHITE) != 0u,
        "held OPT2 does not repeatedly toggle the penpal");
    game_diagnostic_update_controls(&game, 0u);
    game_diagnostic_update_controls(&game, GAME_INPUT_DIAGNOSTIC_OPT2);
    expect((game.diagnostic_controls &
        GAME_DIAGNOSTIC_CONTROL_BULLET_WHITE) == 0u,
        "second OPT2 press restores danger color mode");

    init_normal(&game);
    game_enemy_at(&game, 0u)->active = 1u;
    game_enemy_at(&game, 0u)->rect.x = game.player.x;
    game_enemy_at(&game, 0u)->rect.y = game.player.y;
    game_enemy_at(&game, 0u)->base_y = game.player.y;
    game_update_logic(&game, 0u);
    expect(game.diagnostic_damage_source ==
        GAME_DIAGNOSTIC_DAMAGE_ENEMY_BODY,
        "enemy body collision records damage source 1");

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game_update_logic(&game, 0u);
    expect(game.diagnostic_damage_source ==
        GAME_DIAGNOSTIC_DAMAGE_ENEMY_BULLET,
        "enemy bullet collision records damage source 2");

    init_normal(&game);
    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.asteroids[0].rect.y = game.player.y;
    game_update_logic(&game, 0u);
    expect(game.diagnostic_damage_source == GAME_DIAGNOSTIC_DAMAGE_ASTEROID,
        "asteroid collision records damage source 3");

    init_normal(&game);
    game.stage = 3u;
    game.falling_rocks[0].state = GAME_ROCK_STATE_FALLING;
    game.falling_rocks[0].rect.x = game.player.x;
    game.falling_rocks[0].rect.y = game.player.y;
    game_update_logic(&game, 0u);
    expect(game.diagnostic_damage_source ==
        GAME_DIAGNOSTIC_DAMAGE_FALLING_ROCK,
        "falling rock collision records damage source 4");
}

static unsigned int trace_word(const unsigned char value[2])
{
    return (unsigned int)value[0] | ((unsigned int)value[1] << 8);
}

static void capture_host_slot(unsigned char slot, unsigned char sprctl1,
    signed int hpos, signed int vpos, unsigned int data, unsigned int next)
{
    unsigned char scb[11];

    scb[0] = 0x05u;
    scb[1] = sprctl1;
    scb[2] = 0x20u;
    scb[3] = (unsigned char)next;
    scb[4] = (unsigned char)(next >> 8);
    scb[5] = (unsigned char)data;
    scb[6] = (unsigned char)(data >> 8);
    scb[7] = (unsigned char)hpos;
    scb[8] = (unsigned char)(hpos >> 8);
    scb[9] = (unsigned char)vpos;
    scb[10] = (unsigned char)(vpos >> 8);
    game_aps056_scb_trace_capture_slot(slot, scb);
}

static void capture_host_trace(const GameState* game,
    unsigned char header_penpal0)
{
    unsigned char active_count;
    unsigned char visible_count;
    unsigned char i;

    active_count = 0u;
    visible_count = 0u;
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        const GameEnemyBullet* bullet = &game->enemy_bullets[i];

        if (bullet->active != 0u) {
            ++active_count;
            if (bullet->rect.y >= GAME_HUD_HEIGHT) {
                ++visible_count;
            }
        }
    }
    game_aps056_scb_trace_begin(active_count, visible_count,
        header_penpal0);
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        const GameEnemyBullet* bullet = &game->enemy_bullets[i];
        unsigned char sprctl1;
        unsigned int next;

        sprctl1 = (unsigned char)(0x08u |
            (bullet->active != 0u && bullet->rect.y >= GAME_HUD_HEIGHT ?
                0u : 0x04u));
        next = (i + 1u < GAME_MAX_ENEMY_BULLETS) ?
            (unsigned int)(0x4100u + i) : 0u;
        capture_host_slot(i, sprctl1, (signed int)bullet->rect.x,
            (signed int)bullet->rect.y, (unsigned int)(0x4000u + i), next);
    }
}

static void test_one_shot_scb_trace(void)
{
    GameState game;
    const GameAps056ScbTrace* trace;
    unsigned int frozen_timer;

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 100u;
    game.enemy_bullets[0].rect.y = 40u;
    game.enemy_bullets[3].active = 1u;
    game.enemy_bullets[3].rect.x = 80u;
    game.enemy_bullets[3].rect.y = 9u;
    game_aps056_scb_trace_reset();
    capture_host_trace(&game, 6u);
    game_aps056_scb_trace_submit_before();
    game_aps056_scb_trace_submit_after();
    game_aps056_scb_trace_submit_after();
    trace = game_aps056_scb_trace_get();
    expect(trace->latched != 0u && trace->active_count == 2u &&
        trace->visible_count == 1u && trace->header_penpal0 == 6u,
        "SCB trace stores active/predicate counts and danger penpal");
    expect(trace->slot_count == GAME_MAX_ENEMY_BULLETS &&
        trace->slots[0].slot_index == 0u &&
        trace->slots[15].slot_index == 15u,
        "SCB trace scans all 16 slots with bounded indices");
    expect(trace->slots[0].sprctl0 == 0x05u &&
        trace->slots[0].sprctl1 == 0x08u &&
        trace_word(trace->slots[0].hpos) == 100u &&
        trace_word(trace->slots[0].vpos) == 40u &&
        trace_word(trace->slots[0].data) == 0x4000u &&
        trace_word(trace->slots[0].next) == 0x4100u,
        "SCB trace stores control/coordinates/data/next for active slot");
    expect(trace->slots[3].sprctl1 == 0x0Cu &&
        trace_word(trace->slots[3].hpos) == 80u &&
        trace_word(trace->slots[3].vpos) == 9u &&
        trace_word(trace->slots[15].next) == 0u,
        "SCB trace preserves HUD predicate skip and terminal next");
    expect(trace->submit_before == GAME_APS056_TRACE_BEFORE_MARKER &&
        trace->submit_after == GAME_APS056_TRACE_AFTER_MARKER &&
        trace->submit_count == 1u,
        "SCB trace has one-shot submit markers and count");

    game_aps056_scb_trace_begin(16u, 16u, 15u);
    trace = game_aps056_scb_trace_get();
    expect(trace->active_count == 2u && trace->visible_count == 1u &&
        trace->header_penpal0 == 6u && trace->submit_count == 1u,
        "SCB trace latch rejects a second frame capture");

    init_normal(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 100u;
    game.enemy_bullets[0].rect.y = 40u;
    frozen_timer = game.phase_timer;
    game_aps056_scb_trace_reset();
    game_update_logic(&game, GAME_INPUT_DIAGNOSTIC_OPT1);
    game_aps056_scb_trace_begin(1u, 1u, 6u);
    trace = game_aps056_scb_trace_get();
    expect(game.phase_timer == frozen_timer && trace->latched != 0u,
        "OPT1 logic freeze leaves draw-side trace available");
}

static void test_trace_penpal_follows_opt2(void)
{
    GameState game;
    const GameAps056ScbTrace* trace;

    init_normal(&game);
    game_diagnostic_update_controls(&game, GAME_INPUT_DIAGNOSTIC_OPT2);
    game_aps056_scb_trace_reset();
    game_aps056_scb_trace_begin(0u, 0u,
        (game.diagnostic_controls & GAME_DIAGNOSTIC_CONTROL_BULLET_WHITE) !=
        0u ? 15u : 6u);
    trace = game_aps056_scb_trace_get();
    expect(trace->header_penpal0 == 15u,
        "OPT2 rising edge is reflected as white trace penpal");
    game_diagnostic_update_controls(&game, 0u);
    game_diagnostic_update_controls(&game, GAME_INPUT_DIAGNOSTIC_OPT2);
    game_aps056_scb_trace_reset();
    game_aps056_scb_trace_begin(0u, 0u,
        (game.diagnostic_controls & GAME_DIAGNOSTIC_CONTROL_BULLET_WHITE) !=
        0u ? 15u : 6u);
    trace = game_aps056_scb_trace_get();
    expect(trace->header_penpal0 == 6u,
        "second OPT2 rising edge restores danger trace penpal");
}
#endif

int main(void)
{
    test_active_slot_values();
    test_collision_slot_is_skipped_after_consumption();
    test_hud_boundary_and_catchup();
    test_collision_boundaries_and_hidden_bullets();
#ifdef APS056_DIAGNOSTIC
    test_controls_active_count_and_damage_sources();
    test_one_shot_scb_trace();
    test_trace_penpal_follows_opt2();
#endif
    printf("PASS: %u APS-056 diagnostic checks\n", checks);
    return EXIT_SUCCESS;
}
