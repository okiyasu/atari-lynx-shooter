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

static void test_movement_and_boundaries(void)
{
    GameState game;
    unsigned int i;

    game_init(&game);
    game_update(&game, GAME_INPUT_RIGHT | GAME_INPUT_DOWN);
    expect(game.player.x == 12u && game.player.y == 50u,
        "direction input moves the player diagonally");

    for (i = 0u; i < 200u; ++i) {
        game_update(&game, GAME_INPUT_LEFT | GAME_INPUT_UP);
    }
    expect(game.player.x == 0u, "left boundary is clamped");
    expect(game.player.y == GAME_HUD_HEIGHT, "top boundary preserves HUD");

    for (i = 0u; i < 200u; ++i) {
        game_update(&game, GAME_INPUT_RIGHT | GAME_INPUT_DOWN);
    }
    expect(game.player.x == GAME_SCREEN_WIDTH - GAME_PLAYER_WIDTH,
        "right boundary is clamped");
    expect(game.player.y == GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT,
        "bottom boundary is clamped");
}

static void test_fire_and_cooldown(void)
{
    GameState game;
    unsigned int i;
    unsigned char active;

    game_init(&game);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.bullets[0].active != 0u, "A or B input fires a bullet");
    expect(game.fire_cooldown != 0u, "firing starts cooldown");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.bullets[1].active == 0u, "cooldown blocks immediate repeat fire");

    for (i = 0u; i < 8u; ++i) {
        game_update(&game, GAME_INPUT_FIRE);
    }
    active = (unsigned char)(game.bullets[0].active + game.bullets[1].active +
        game.bullets[2].active);
    expect(active >= 2u, "held fire repeats after cooldown");
}

static void test_aabb_edges(void)
{
    GameRect a = { 10u, 10u, 5u, 5u };
    GameRect overlap = { 14u, 14u, 4u, 4u };
    GameRect touching = { 15u, 10u, 4u, 4u };

    expect(game_aabb_intersects(&a, &overlap) != 0u,
        "overlapping rectangles collide");
    expect(game_aabb_intersects(&a, &touching) == 0u,
        "touching edges do not collide");
}

static void test_hit_score_and_respawn(void)
{
    GameState game;
    unsigned char old_y;

    game_init(&game);
    game.bullets[0].active = 1u;
    game.bullets[0].rect.x = (unsigned char)(game.enemy.x - 3u);
    game.bullets[0].rect.y = game.enemy.y;
    old_y = game.enemy.y;
    game_update(&game, 0u);

    expect(game.bullets[0].active == 0u, "hit consumes the bullet");
    expect(game.score == 100ul, "hit adds 100 points");
    expect(game.enemy.x == 140u && game.enemy.y != old_y,
        "hit respawns enemy at a deterministic new position");
}

int main(void)
{
    test_movement_and_boundaries();
    test_fire_and_cooldown();
    test_aabb_edges();
    test_hit_score_and_respawn();
    printf("PASS: %u game logic checks\n", checks);
    return EXIT_SUCCESS;
}

