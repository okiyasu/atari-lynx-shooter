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

static void advance_frames(GameState* game, unsigned int frames)
{
    unsigned int i;

    for (i = 0u; i < frames; ++i) {
        game_update(game, 0u);
    }
}

static void disable_enemies_except(GameState* game, unsigned char slot)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game->enemies[i].active = (unsigned char)(i == slot);
    }
}

static void place_player_bullet_hit(GameState* game, unsigned char bullet,
    unsigned char enemy)
{
    game->bullets[bullet].active = 1u;
    game->bullets[bullet].rect.x =
        (unsigned char)(game->enemies[enemy].rect.x - 4u);
    game->bullets[bullet].rect.y = game->enemies[enemy].rect.y;
}

static unsigned char count_player_bullets(const GameState* game)
{
    unsigned char i;
    unsigned char count;

    count = 0u;
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active != 0u) {
            ++count;
        }
    }
    return count;
}

static void test_initial_state(void)
{
    GameState game;
    static const unsigned char xs[GAME_MAX_ENEMIES] = {
        140u, 170u, 200u, 230u
    };
    static const unsigned char ys[GAME_MAX_ENEMIES] = {
        47u, 23u, 70u, 38u
    };
    unsigned char i;

    game_init(&game);
    expect(game.player.x == 10u && game.player.y == 48u,
        "player starts at the fixed position");
    expect(game.lives == 3u && game.score == 0ul && game.game_over == 0u,
        "score lives and game over start clean");
    expect(GAME_MAX_ENEMIES == 4u && GAME_MAX_ENEMY_BULLETS == 6u &&
        GAME_MAX_PLAYER_BULLETS == 12u,
        "all projectile and enemy arrays have fixed requested capacities");
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        expect(game.enemies[i].active != 0u,
            "all initial enemy slots are active");
        expect(game.enemies[i].rect.x == xs[i] &&
            game.enemies[i].rect.y == ys[i],
            "initial enemy coordinates match formation");
        expect(game.enemies[i].rect.width == GAME_ENEMY_WIDTH &&
            game.enemies[i].rect.height == GAME_ENEMY_HEIGHT,
            "enemy rectangle dimensions are initialized");
        expect(game.enemies[i].type == (i == 3u ?
            GAME_ENEMY_TYPE_DROPPER : (unsigned char)(i % 2u)) &&
            game.enemies[i].pattern == (unsigned char)(i % 3u),
            "enemy type and pattern are distributed by slot");
        expect(game.enemies[i].move_counter == 0u &&
            game.enemies[i].direction == 1u,
            "enemy movement counters are independent and initialized");
        expect(game.enemies[i].fire_counter ==
            (unsigned char)((i * 15u) %
            (game.enemies[i].type == GAME_ENEMY_TYPE_SCOUT ? 90u :
                (game.enemies[i].type == GAME_ENEMY_TYPE_SAUCER ?
                    60u : 75u))),
            "enemy fire counter has the slot phase");
    }
    expect(game.enemies[0].phase == 0u && game.enemies[1].phase == 6u &&
        game.enemies[2].phase == 0u && game.enemies[3].phase == 0u,
        "movement phases match straight wave and dive starts");
    expect(game.weapon_level == GAME_WEAPON_LEVEL_MIN &&
        game.power_item.active == 0u &&
        game.power_item.move_counter == 0u,
        "weapon and power item start at clean values");
    expect(game.power_item.rect.width == GAME_POWER_ITEM_WIDTH &&
        game.power_item.rect.height == GAME_POWER_ITEM_HEIGHT,
        "power item rectangle dimensions are initialized");
    expect(game.planet_offset == 0u && game.planet_counter == 0u &&
        game.far_star_offset == 0u && game.far_star_counter == 0u &&
        game.near_star_offset == 0u && game.near_star_counter == 0u,
        "all three background layers start at zero");
    expect(GAME_PLANET_SCROLL_INTERVAL == 8u &&
        GAME_PLANET_SCROLL_PERIOD == 192u,
        "planet scrolling constants expose the fixed cadence and period");
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        expect(game.bullets[i].active == 0u &&
            game.bullets[i].rect.width == GAME_PLAYER_BULLET_WIDTH &&
            game.bullets[i].rect.height == GAME_PLAYER_BULLET_HEIGHT,
            "all player bullets start inactive with fixed dimensions");
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        expect(game.enemy_bullets[i].active == 0u &&
            game.enemy_bullets[i].rect.width == 2u &&
            game.enemy_bullets[i].rect.height == 2u,
            "all enemy bullets start inactive with fixed dimensions");
    }
}

static void test_background_animation_and_player(void)
{
    GameState game;
    unsigned int i;

    game_init(&game);
    game_update(&game, 0u);
    expect(game.near_star_offset == 0u && game.far_star_offset == 0u,
        "background waits for its interval");
    game_update(&game, 0u);
    expect(game.near_star_offset == 1u && game.far_star_offset == 0u,
        "near background moves after two updates");
    advance_frames(&game, 2u);
    expect(game.near_star_offset == 2u && game.far_star_offset == 1u,
        "far background moves after four updates");

    game_init(&game);
    advance_frames(&game, 7u);
    expect(game.planet_offset == 0u && game.planet_counter == 7u,
        "planet waits through seven normal updates");
    game_update(&game, 0u);
    expect(game.planet_offset == 1u && game.planet_counter == 0u &&
        game.far_star_offset == 2u && game.near_star_offset == 4u,
        "update eight produces distinct planet far and near speeds");
    game.planet_offset = 190u;
    game.planet_counter = 7u;
    game_update(&game, 0u);
    expect(game.planet_offset == 191u && game.planet_counter == 0u,
        "planet advances safely from offset one hundred ninety");
    advance_frames(&game, 7u);
    expect(game.planet_offset == 191u && game.planet_counter == 7u,
        "planet holds offset one hundred ninety-one for seven updates");
    game_update(&game, 0u);
    expect(game.planet_offset == 0u && game.planet_counter == 0u,
        "planet wraps explicitly after offset one hundred ninety-one");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.planet_counter = 7u;
    game.enemies[3].rect.x = 100u;
    game.enemies[3].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 3u);
    game_update(&game, 0u);
    expect(game.planet_offset == 1u && game.planet_counter == 0u &&
        game.power_item.active != 0u && game.score == 100ul,
        "Dropper hit update advances planet exactly once");

    game_init(&game);
    game.near_star_offset = 159u;
    game.near_star_counter = 1u;
    game.far_star_offset = 159u;
    game.far_star_counter = 3u;
    game_update(&game, 0u);
    expect(game.near_star_offset == 0u && game.far_star_offset == 0u,
        "both background layers wrap deterministically");

    game_init(&game);
    advance_frames(&game, 7u);
    expect(game.animation_frame == 0u && game.animation_counter == 7u,
        "animation holds for seven updates");
    game_update(&game, 0u);
    expect(game.animation_frame == 1u && game.animation_counter == 0u,
        "animation changes on update eight");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game_update(&game, GAME_INPUT_RIGHT | GAME_INPUT_DOWN);
    expect(game.player.x == 12u && game.player.y == 50u,
        "diagonal input moves the player");
    for (i = 0u; i < 80u; ++i) {
        game.enemies[3].rect.x = 230u;
        game_update(&game, GAME_INPUT_LEFT | GAME_INPUT_UP);
    }
    expect(game.player.x == 0u && game.player.y == GAME_HUD_HEIGHT,
        "left and HUD boundaries clamp the player");
    for (i = 0u; i < 80u; ++i) {
        game.enemies[3].rect.x = 230u;
        game_update(&game, GAME_INPUT_RIGHT | GAME_INPUT_DOWN);
    }
    expect(game.player.x == GAME_SCREEN_WIDTH - GAME_PLAYER_WIDTH &&
        game.player.y == GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT,
        "right and bottom boundaries clamp the player");
}

static void test_enemy_entry_and_patterns(void)
{
    GameState game;

    game_init(&game);
    game_update(&game, 0u);
    expect(game.enemies[0].rect.x == 139u,
        "onscreen straight enemy moves immediately");
    expect(game.enemies[1].rect.x == 169u &&
        game.enemies[1].rect.y == 23u &&
        game.enemies[1].move_counter == 0u &&
        game.enemies[1].fire_counter == 15u,
        "offscreen enemy only moves left");
    advance_frames(&game, 9u);
    expect(game.enemies[1].rect.x == 160u &&
        game.enemies[1].move_counter == 0u,
        "offscreen enemy remains inert at x 160");
    game_update(&game, 0u);
    expect(game.enemies[1].rect.x == 159u &&
        game.enemies[1].move_counter == 0u &&
        game.enemies[1].fire_counter == 15u,
        "entry update only crosses to x 159");
    expect(game.enemies[0].rect.x == 129u &&
        game.enemies[2].rect.x == 189u &&
        game.enemies[3].rect.x == 219u,
        "initial x spacing produces deterministic staggered entry");
    game_update(&game, 0u);
    expect(game.enemies[1].rect.x == 158u &&
        game.enemies[1].move_counter == 1u &&
        game.enemies[1].fire_counter == 16u,
        "normal movement starts on the update after entry");

    game_init(&game);
    disable_enemies_except(&game, 1u);
    game.enemies[1].rect.x = 140u;
    advance_frames(&game, 3u);
    expect(game.enemies[1].rect.x == 137u &&
        game.enemies[1].rect.y == 24u,
        "wave moves left and changes y every third update");
    advance_frames(&game, 15u);
    expect(game.enemies[1].rect.y == 29u &&
        game.enemies[1].phase == 12u,
        "wave reaches its lower turning phase");
    advance_frames(&game, 36u);
    expect(game.enemies[1].rect.y == 17u &&
        game.enemies[1].phase == 0u,
        "wave traverses twelve pixels back to its upper phase");

    game_init(&game);
    disable_enemies_except(&game, 2u);
    game.enemies[2].rect.x = 140u;
    game_update(&game, 0u);
    expect(game.enemies[2].rect.y == 70u,
        "dive holds y on its first update");
    game_update(&game, 0u);
    expect(game.enemies[2].rect.y == 71u,
        "dive descends on its second update");
    advance_frames(&game, 22u);
    expect(game.enemies[2].rect.y == 82u &&
        game.enemies[2].phase == 12u,
        "dive reaches twelve pixels below base");
    advance_frames(&game, 24u);
    expect(game.enemies[2].rect.y == 70u &&
        game.enemies[2].phase == 0u,
        "dive returns to base");

    game_init(&game);
    disable_enemies_except(&game, 1u);
    game.enemies[1].rect.x = 140u;
    game.enemies[1].base_y = GAME_HUD_HEIGHT;
    game.enemies[1].phase = 1u;
    game.enemies[1].direction = 0u;
    game.enemies[1].move_counter = 2u;
    game_update(&game, 0u);
    expect(game.enemies[1].rect.y == GAME_HUD_HEIGHT,
        "wave clamps to HUD without underflow");
    game.enemies[1].pattern = GAME_ENEMY_PATTERN_DIVE;
    game.enemies[1].base_y = GAME_SCREEN_HEIGHT - GAME_ENEMY_HEIGHT;
    game.enemies[1].phase = 11u;
    game.enemies[1].direction = 1u;
    game.enemies[1].move_counter = 1u;
    game_update(&game, 0u);
    expect(game.enemies[1].rect.y ==
        GAME_SCREEN_HEIGHT - GAME_ENEMY_HEIGHT,
        "dive clamps to screen bottom without overflow");
}

static void test_player_fire_and_aabb(void)
{
    GameState game;
    GameRect a = { 10u, 10u, 5u, 5u };
    GameRect overlap = { 14u, 14u, 4u, 4u };
    GameRect touching = { 15u, 10u, 4u, 4u };
    unsigned int i;
    unsigned char active;

    expect(game_aabb_intersects(&a, &overlap) != 0u,
        "overlapping rectangles collide");
    expect(game_aabb_intersects(&a, &touching) == 0u,
        "touching rectangle edges do not collide");
    game_init(&game);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.bullets[0].active != 0u && game.fire_cooldown == 8u,
        "fire creates a bullet and starts cooldown");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.bullets[1].active == 0u,
        "cooldown blocks immediate repeated fire");
    for (i = 0u; i < 8u; ++i) {
        game_update(&game, GAME_INPUT_FIRE);
    }
    active = (unsigned char)(game.bullets[0].active +
        game.bullets[1].active + game.bullets[2].active);
    expect(active >= 2u, "held fire repeats after eight updates");
}

static void test_weapon_levels_and_atomic_fire(void)
{
    GameState game;
    unsigned char i;

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game_update(&game, GAME_INPUT_FIRE);
    expect(count_player_bullets(&game) == 1u &&
        game.bullets[0].rect.x == game.player.x + GAME_PLAYER_WIDTH + 4u &&
        game.bullets[0].rect.y == game.player.y + 2u,
        "level one fires one centered bullet into the lowest slot");
    expect(game.fire_cooldown == 8u,
        "successful level one fire starts eight update cooldown");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.weapon_level = 2u;
    game.bullets[0].active = 1u;
    game.bullets[0].rect.x = 40u;
    game.bullets[0].rect.y = 90u;
    game_update(&game, GAME_INPUT_FIRE);
    expect(count_player_bullets(&game) == 3u &&
        game.bullets[1].rect.y == game.player.y &&
        game.bullets[2].rect.y == game.player.y + 4u,
        "level two atomically fills the next two slots at exact y values");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.weapon_level = 3u;
    game.bullets[1].active = 1u;
    game.bullets[1].rect.x = 40u;
    game.bullets[1].rect.y = 90u;
    game_update(&game, GAME_INPUT_FIRE);
    expect(count_player_bullets(&game) == 4u &&
        game.bullets[0].rect.y == game.player.y &&
        game.bullets[2].rect.y == game.player.y + 2u &&
        game.bullets[3].rect.y == game.player.y + 4u,
        "level three uses ascending free slots and exact parallel rows");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.weapon_level = 3u;
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (i != 4u && i != 9u) {
            game.bullets[i].active = 1u;
            game.bullets[i].rect.x = 40u;
            game.bullets[i].rect.y = 90u;
        }
    }
    game_update(&game, GAME_INPUT_FIRE);
    expect(count_player_bullets(&game) == 10u &&
        game.bullets[4].active == 0u && game.bullets[9].active == 0u,
        "level three does not partially fire with only two free slots");
    expect(game.fire_cooldown == 0u,
        "failed atomic fire leaves cooldown ready for immediate retry");
    game.bullets[10].active = 0u;
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.bullets[4].active != 0u &&
        game.bullets[9].active != 0u &&
        game.bullets[10].active != 0u &&
        count_player_bullets(&game) == 12u,
        "restored capacity fires all three bullets into ascending free slots");

    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        game.bullets[i].rect.x = 154u;
        game.bullets[i].rect.y = 90u;
    }
    game_update(&game, 0u);
    expect(count_player_bullets(&game) == 0u,
        "all twelve player bullets use the screen exit rule");
}

static void test_hits_and_respawns(void)
{
    GameState game;
    GameEnemy untouched;

    game_init(&game);
    game.enemies[0].rect.x = 100u;
    game.enemies[1].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    game.enemies[1].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.score == 100ul && game.enemies[0].rect.x == 180u,
        "one bullet hits the lowest overlapping enemy slot");
    expect(game.enemies[1].rect.x == 99u,
        "one bullet cannot hit the second overlapping enemy");
    expect(game.enemies[0].rect.x == 180u &&
        game.enemies[0].move_counter == 0u,
        "respawned enemy does not move in its hit update");

    game_init(&game);
    game.enemies[0].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    place_player_bullet_hit(&game, 1u, 0u);
    game_update(&game, 0u);
    expect(game.score == 100ul && game.bullets[1].active != 0u,
        "a respawned slot cannot be hit twice in one update");

    game_init(&game);
    game.enemies[0].rect.x = 100u;
    game.enemies[1].rect.x = 110u;
    game.enemies[0].rect.y = 30u;
    game.enemies[1].rect.y = 60u;
    place_player_bullet_hit(&game, 0u, 0u);
    place_player_bullet_hit(&game, 1u, 1u);
    game_update(&game, 0u);
    expect(game.score == 200ul && game.respawn_sequence == 2u,
        "separate bullets can destroy two enemies in one update");
    expect(game.enemies[0].rect.x == 180u &&
        game.enemies[1].rect.x == 196u,
        "each destroyed slot uses its own respawn x");
    expect(game.enemies[0].type == 1u &&
        game.enemies[0].pattern == GAME_ENEMY_PATTERN_WAVE &&
        game.enemies[0].base_y == 30u,
        "first respawn uses incremented global sequence formula");
    expect(game.enemies[1].type == 1u &&
        game.enemies[1].pattern == GAME_ENEMY_PATTERN_STRAIGHT &&
        game.enemies[1].base_y == 64u,
        "second respawn uses sequence plus slot formula");
    expect(game.enemies[0].fire_counter == 0u &&
        game.enemies[1].fire_counter == 15u,
        "respawns restore slot fire phases for the new types");

    game_init(&game);
    untouched = game.enemies[2];
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.enemies[2].rect.x == (unsigned char)(untouched.rect.x - 1u) &&
        game.enemies[2].base_y == untouched.base_y &&
        game.enemies[2].fire_counter == untouched.fire_counter,
        "destroying one slot leaves offscreen sibling fields unchanged except x");

    game_init(&game);
    game.respawn_sequence = 255u;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.respawn_sequence == 0u && game.enemies[0].type == 0u &&
        game.enemies[0].pattern == 0u && game.enemies[0].base_y == 13u,
        "respawn sequence wraps without underflow or out of range indexing");
}

static void test_enemy_fire(void)
{
    GameState game;
    unsigned char i;

    game_init(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.y = 80u;
    game.enemies[0].base_y = 80u;
    advance_frames(&game, 89u);
    expect(game.enemy_bullets[0].active == 0u &&
        game.enemies[0].fire_counter == 89u,
        "Scout waits through update 89");
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].active != 0u &&
        game.enemies[0].fire_counter == 0u,
        "Scout fires exactly on update 90");
    expect(game.enemy_bullets[0].rect.x == game.enemies[0].rect.x,
        "new enemy bullet does not move on generation update");
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].rect.x ==
        (unsigned char)(game.enemies[0].rect.x - 1u),
        "existing enemy bullet moves two while enemy moves one");

    game_init(&game);
    disable_enemies_except(&game, 1u);
    game.enemies[1].rect.x = 159u;
    game.enemies[1].rect.y = 80u;
    game.enemies[1].base_y = 80u;
    game.enemies[1].fire_counter = 59u;
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].active != 0u &&
        game.enemy_bullets[0].rect.x == 158u &&
        game.enemies[1].fire_counter == 0u,
        "Saucer fires at 60 and generated x is screen safe");

    game_init(&game);
    expect(game.enemies[0].fire_counter == 0u &&
        game.enemies[1].fire_counter == 15u &&
        game.enemies[2].fire_counter == 30u &&
        game.enemies[3].fire_counter == 45u,
        "four enemies have independent fifteen update fire phases");
    advance_frames(&game, 10u);
    expect(game.enemies[1].fire_counter == 15u &&
        game.enemies[2].fire_counter == 30u &&
        game.enemies[3].fire_counter == 45u,
        "offscreen enemies do not advance fire counters");

    game_init(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.y = 80u;
    game.enemies[0].base_y = 80u;
    game.enemies[0].fire_counter = 89u;
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game.enemy_bullets[i].active = 1u;
        game.enemy_bullets[i].rect.x = 100u;
        game.enemy_bullets[i].rect.y = 90u;
    }
    game_update(&game, 0u);
    expect(game.enemies[0].fire_counter == 0u,
        "full enemy bullet pool still resets fire counter");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        expect(game.enemy_bullets[i].rect.x == 98u,
            "existing bullets move before a full-pool fire attempt");
    }
    game_update(&game, 0u);
    expect(game.enemies[0].fire_counter == 1u,
        "full-pool failure does not retry on every update");

    game_init(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.y = 80u;
    game.enemies[0].base_y = 80u;
    game.enemies[0].fire_counter = 89u;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 100u;
    game.enemy_bullets[0].rect.y = 90u;
    game_update(&game, 0u);
    expect(game.enemy_bullets[1].active != 0u &&
        game.enemy_bullets[2].active == 0u,
        "enemy fire chooses the lowest available bullet slot");

    game_init(&game);
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game.enemies[i].active = 0u;
    }
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 4u;
    game.enemy_bullets[0].rect.y = 90u;
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].rect.x == 2u &&
        game.enemy_bullets[0].active != 0u,
        "enemy bullet reaches x two while active");
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].rect.x == 0u &&
        game.enemy_bullets[0].active != 0u,
        "enemy bullet reaches x zero without underflow");
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].active == 0u,
        "enemy bullet disappears before moving left of zero");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.enemies[3].rect.x = 140u;
    game.enemies[3].rect.y = 80u;
    game.enemies[3].base_y = 80u;
    expect(game.enemies[3].type == GAME_ENEMY_TYPE_DROPPER &&
        game.enemies[3].fire_counter == 45u,
        "Dropper starts with its fixed type and forty-five update phase");
    advance_frames(&game, 29u);
    expect(game.enemy_bullets[0].active == 0u &&
        game.enemies[3].fire_counter == 74u,
        "Dropper waits through its seventy-fourth onscreen update");
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].active != 0u &&
        game.enemies[3].fire_counter == 0u,
        "Dropper fires at the seventy-five update boundary");
}

static void test_dropper_and_power_item(void)
{
    GameState game;

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.enemies[3].rect.x = 154u;
    game.enemies[3].rect.y = 40u;
    game.enemies[3].base_y = 40u;
    place_player_bullet_hit(&game, 0u, 3u);
    game_update(&game, 0u);
    expect(game.score == 100ul && game.power_item.active != 0u &&
        game.power_item.rect.x == 156u && game.power_item.rect.y == 42u,
        "Dropper hit creates a screen-clipped item from pre-respawn position");
    expect(game.power_item.move_counter == 0u &&
        game.enemies[3].type == GAME_ENEMY_TYPE_DROPPER &&
        game.enemies[3].rect.x == 228u &&
        game.enemies[3].pattern == GAME_ENEMY_PATTERN_WAVE &&
        game.enemies[3].base_y == 81u,
        "new item does not move and respawned slot remains Dropper");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.enemies[3].rect.x = 14u;
    game.enemies[3].rect.y = (unsigned char)(game.player.y - 2u);
    game.enemies[3].base_y = game.enemies[3].rect.y;
    place_player_bullet_hit(&game, 0u, 3u);
    game_update(&game, 0u);
    expect(game.power_item.active != 0u &&
        game.power_item.rect.x == 16u &&
        game.power_item.move_counter == 0u && game.weapon_level == 1u,
        "newly generated overlapping item waits until the next update");
    game_update(&game, 0u);
    expect(game.power_item.active == 0u && game.weapon_level == 2u,
        "generated item becomes collectible on the following update");

    game_init(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.power_item.active == 0u,
        "Scout and Saucer hits never create a power item");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.power_item.active = 1u;
    game.power_item.rect.x = 80u;
    game.power_item.rect.y = 80u;
    game.power_item.move_counter = 0u;
    game.enemies[3].rect.x = 100u;
    game.enemies[3].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 3u);
    game_update(&game, 0u);
    expect(game.power_item.active != 0u &&
        game.power_item.rect.x == 80u && game.power_item.rect.y == 80u &&
        game.power_item.move_counter == 1u,
        "active item is not replaced and continues its normal move cadence");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.power_item.active = 1u;
    game.power_item.rect.x = 20u;
    game.power_item.rect.y = 80u;
    game_update(&game, 0u);
    expect(game.power_item.rect.x == 20u &&
        game.power_item.move_counter == 1u,
        "power item waits on the first movement update");
    game_update(&game, 0u);
    expect(game.power_item.rect.x == 19u &&
        game.power_item.move_counter == 0u,
        "power item moves left one pixel on the second update");
    game.power_item.rect.x = 0u;
    game.power_item.move_counter = 1u;
    game_update(&game, 0u);
    expect(game.power_item.active == 0u &&
        game.power_item.rect.x == 0u &&
        game.power_item.move_counter == 0u,
        "power item at zero disappears without unsigned underflow");

    game_init(&game);
    disable_enemies_except(&game, 3u);
    game.power_item.active = 1u;
    game.power_item.rect.x =
        (unsigned char)(game.player.x + game.player.width);
    game.power_item.rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.power_item.active != 0u && game.weapon_level == 1u,
        "exclusive AABB does not collect an edge-touching item");
    game.power_item.rect.x =
        (unsigned char)(game.player.x + game.player.width - 1u);
    game_update(&game, 0u);
    expect(game.power_item.active == 0u && game.weapon_level == 2u,
        "overlapping item raises weapon level one to two and is consumed");
    game.power_item.active = 1u;
    game.power_item.rect.x = game.player.x;
    game.power_item.rect.y = game.player.y;
    game.power_item.move_counter = 0u;
    game_update(&game, 0u);
    expect(game.weapon_level == 3u && game.power_item.active == 0u,
        "second collection raises weapon level two to three");
    game.power_item.active = 1u;
    game.power_item.rect.x = game.player.x;
    game.power_item.rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.weapon_level == 3u && game.power_item.active == 0u,
        "level three collection is consumed without exceeding the cap");
}

static int frozen_state_matches(const GameState* game,
    const GameState* frozen)
{
    unsigned char i;

    if (game->player.x != frozen->player.x ||
        game->player.y != frozen->player.y ||
        game->score != frozen->score ||
        game->fire_cooldown != frozen->fire_cooldown ||
        game->respawn_sequence != frozen->respawn_sequence ||
        game->planet_offset != frozen->planet_offset ||
        game->planet_counter != frozen->planet_counter ||
        game->far_star_offset != frozen->far_star_offset ||
        game->near_star_offset != frozen->near_star_offset ||
        game->far_star_counter != frozen->far_star_counter ||
        game->near_star_counter != frozen->near_star_counter ||
        game->animation_counter != frozen->animation_counter ||
        game->animation_frame != frozen->animation_frame ||
        game->weapon_level != frozen->weapon_level ||
        game->power_item.active != frozen->power_item.active ||
        game->power_item.rect.x != frozen->power_item.rect.x ||
        game->power_item.rect.y != frozen->power_item.rect.y ||
        game->power_item.move_counter != frozen->power_item.move_counter) {
        return 0;
    }
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        const GameEnemy* a;
        const GameEnemy* b;

        a = &game->enemies[i];
        b = &frozen->enemies[i];
        if (a->rect.x != b->rect.x || a->rect.y != b->rect.y ||
            a->active != b->active || a->type != b->type ||
            a->pattern != b->pattern || a->base_y != b->base_y ||
            a->move_counter != b->move_counter || a->phase != b->phase ||
            a->direction != b->direction ||
            a->fire_counter != b->fire_counter) {
            return 0;
        }
    }
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active != frozen->bullets[i].active ||
            game->bullets[i].rect.x != frozen->bullets[i].rect.x ||
            game->bullets[i].rect.y != frozen->bullets[i].rect.y) {
            return 0;
        }
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active !=
                frozen->enemy_bullets[i].active ||
            game->enemy_bullets[i].rect.x !=
                frozen->enemy_bullets[i].rect.x ||
            game->enemy_bullets[i].rect.y !=
                frozen->enemy_bullets[i].rect.y) {
            return 0;
        }
    }
    return 1;
}

static void test_damage_and_priority(void)
{
    GameState game;
    unsigned char i;

    game_init(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = 1u;
    game.enemies[0].rect.y = 80u;
    game.enemies[0].base_y = 80u;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 1u && game.dying != 0u,
        "left edge alone starts one death");

    game_init(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.enemies[0].rect.y = game.player.y;
    game.enemies[0].base_y = game.player.y;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 1u && game.dying != 0u,
        "enemy body contact alone starts one death");

    game_init(&game);
    game.enemies[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.enemies[0].rect.y = game.player.y;
    game.enemies[1].rect.x = 1u;
    game.enemies[1].rect.y = game.player.y;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game.enemy_bullets[1].active = 1u;
    game.enemy_bullets[1].rect.x = (unsigned char)(game.player.x + 3u);
    game.enemy_bullets[1].rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 1u && game.dying != 0u,
        "simultaneous body edge and bullet damage costs one life");
    expect(game.enemy_bullets[0].active == 0u &&
        game.enemy_bullets[1].active == 0u,
        "all overlapping enemy bullets are consumed");

    game_init(&game);
    game.enemies[0].rect.x = 20u;
    game.enemies[0].rect.y = game.player.y;
    place_player_bullet_hit(&game, 0u, 0u);
    game.enemies[1].rect.x = (unsigned char)(game.player.x + 1u);
    game.enemies[1].rect.y = game.player.y;
    game.enemies[1].base_y = game.player.y;
    game.enemies[1].pattern = GAME_ENEMY_PATTERN_STRAIGHT;
    game_update(&game, 0u);
    expect(game.score == 100ul && game.enemies[0].rect.x == 180u,
        "player bullet respawns its target before damage checks");
    expect(game.lives == GAME_INITIAL_LIVES - 1u && game.dying != 0u,
        "an unrelated enemy remains a same-update damage source");

    game_init(&game);
    game.enemies[0].rect.x = 20u;
    game.enemies[0].rect.y = game.player.y;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.score == 100ul && game.lives == GAME_INITIAL_LIVES &&
        game.dying == 0u,
        "hit target cannot damage after same-update respawn");

    game_init(&game);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 1u,
        "enemy bullet AABB alone starts death");
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        expect(game.bullets[i].active == 0u,
            "death clears every player bullet");
    }

    game_init(&game);
    disable_enemies_except(&game, 0u);
    game.weapon_level = 1u;
    game.power_item.active = 1u;
    game.power_item.rect.x = game.player.x;
    game.power_item.rect.y = game.player.y;
    game.enemies[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.enemies[0].rect.y = game.player.y;
    game.enemies[0].base_y = game.player.y;
    game_update(&game, 0u);
    expect(game.weapon_level == 2u && game.dying != 0u,
        "same-update item collection is committed before player damage");
}

static void test_explosion_respawn_and_invincibility(void)
{
    GameState game;
    GameState frozen;
    unsigned int i;
    unsigned char lives;
    int all_frozen;
    int stages_correct;

    game_init(&game);
    game.score = 700ul;
    game.fire_cooldown = 5u;
    game.weapon_level = 3u;
    game.power_item.active = 1u;
    game.power_item.rect.x = 100u;
    game.power_item.rect.y = 90u;
    game.power_item.move_counter = 1u;
    game.planet_offset = 42u;
    game.planet_counter = 7u;
    game.far_star_offset = 23u;
    game.near_star_offset = 51u;
    game.player.x = 44u;
    game.player.y = 70u;
    game.enemies[0].rect.x = 45u;
    game.enemies[0].rect.y = 70u;
    game.enemies[0].base_y = 70u;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 90u;
    game.enemy_bullets[0].rect.y = 80u;
    game_update(&game, 0u);
    expect(game.dying != 0u && game.explosion_timer == 0u &&
        game.lives == 2u && game.score == 700ul &&
        game.planet_offset == 43u && game.planet_counter == 0u,
        "damage begins stage zero and preserves score");
    frozen = game;
    all_frozen = 1;
    stages_correct = 1;
    for (i = 1u; i < GAME_EXPLOSION_FRAMES; ++i) {
        game_update(&game, GAME_INPUT_RIGHT | GAME_INPUT_FIRE);
        if (!frozen_state_matches(&game, &frozen)) {
            all_frozen = 0;
        }
        if (game.explosion_timer / GAME_EXPLOSION_STAGE_FRAMES !=
            (unsigned char)(i / GAME_EXPLOSION_STAGE_FRAMES)) {
            stages_correct = 0;
        }
    }
    expect(all_frozen,
        "explosion freezes enemies bullets counters input and background");
    expect(stages_correct && game.explosion_timer == 31u,
        "four explosion stages use exact eight update boundaries");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.dying == 0u && game.player.x == 10u &&
        game.player.y == 48u && game.invincibility_timer == 60u,
        "update 32 respawns player with sixty protected updates");
    expect(game.score == 700ul && game.planet_offset == 43u &&
        game.planet_counter == 0u && game.far_star_offset == 23u &&
        game.near_star_offset == 51u,
        "respawn preserves score and all background offsets");
    expect(game.weapon_level == 3u && game.power_item.active == 0u &&
        game.power_item.move_counter == 0u,
        "respawn preserves weapon level but clears the power item");
    expect(game.respawn_sequence == 0u &&
        game.enemies[0].rect.x == 140u &&
        game.enemies[1].rect.x == 170u &&
        game.enemies[2].rect.x == 200u &&
        game.enemies[3].rect.x == 230u,
        "respawn restores the complete four enemy formation");
    expect(game.enemies[3].type == GAME_ENEMY_TYPE_DROPPER,
        "death respawn restores slot three as Dropper");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        expect(game.enemy_bullets[i].active == 0u,
            "respawn clears every enemy bullet");
    }
    expect(game.fire_cooldown == 0u,
        "respawn clears player fire cooldown");
    game_update(&game, 0u);
    expect(game.planet_offset == 43u && game.planet_counter == 1u,
        "first normal respawn update resumes planet scrolling");
    expect(game_player_is_visible(&game) != 0u,
        "invincibility starts visible");
    game.invincibility_timer = 57u;
    expect(game_player_is_visible(&game) != 0u,
        "visibility lasts four timer states");
    game.invincibility_timer = 56u;
    expect(game_player_is_visible(&game) == 0u,
        "visibility toggles at four updates");
    game.invincibility_timer = 60u;
    game.weapon_level = 2u;
    game.power_item.active = 1u;
    game.power_item.rect.x = 100u;
    game.power_item.rect.y = 90u;
    game.power_item.move_counter = 0u;
    game.planet_offset = 50u;
    game.planet_counter = 0u;
    lives = game.lives;
    for (i = 0u; i < 60u; ++i) {
        game.enemies[0].rect.x = (unsigned char)(game.player.x + 1u);
        game.enemies[0].rect.y = game.player.y;
        game.enemy_bullets[0].active = 1u;
        game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
        game.enemy_bullets[0].rect.y = game.player.y;
        game_update(&game, 0u);
    }
    expect(game.lives == lives && game.dying == 0u &&
        game.invincibility_timer == 0u,
        "all first sixty normal updates remain protected");
    expect(game.enemies[0].rect.x == 140u &&
        game.enemies[1].fire_counter == 15u &&
        game.enemy_bullets[0].active == 0u,
        "invincible damage resets formation counters and enemy bullets");
    expect(game.weapon_level == 2u && game.power_item.active != 0u &&
        game.enemies[3].type == GAME_ENEMY_TYPE_DROPPER,
        "invincible damage preserves power state and restores Dropper type");
    expect(game.planet_offset == 57u && game.planet_counter == 4u,
        "sixty invincible updates advance planet through formation resets");
    game.enemies[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.enemies[0].rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.lives == (unsigned char)(lives - 1u) && game.dying != 0u,
        "update 61 can start a new death");
}

static void test_game_over_and_restart(void)
{
    GameState game;
    GameState frozen;
    unsigned int i;

    game_init(&game);
    game.lives = 1u;
    game.score = 500ul;
    game.weapon_level = 3u;
    game.power_item.active = 1u;
    game.power_item.rect.x = 100u;
    game.power_item.rect.y = 90u;
    game.power_item.move_counter = 1u;
    game.planet_offset = 90u;
    game.planet_counter = 7u;
    game.enemies[0].rect.x = 1u;
    game.enemies[0].rect.y = 80u;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 80u;
    game.enemy_bullets[0].rect.y = 80u;
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.lives == 0u && game.dying != 0u && game.game_over == 0u,
        "final damage starts explosion before game over");
    expect(game.planet_offset == 91u && game.planet_counter == 0u,
        "final damage update advances planet before freezing it");
    frozen = game;
    advance_frames(&game, 31u);
    expect(game.dying != 0u && game.explosion_timer == 31u &&
        frozen_state_matches(&game, &frozen),
        "final explosion freezes complete normal state for 31 updates");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.dying == 0u && game.game_over != 0u,
        "game over begins after death update 32");
    frozen = game;
    for (i = 0u; i < 4u; ++i) {
        game_update(&game, GAME_INPUT_RIGHT | GAME_INPUT_FIRE);
    }
    expect(game.game_over != 0u && frozen_state_matches(&game, &frozen),
        "held fire leaves all game over state frozen");
    game_update(&game, GAME_INPUT_RIGHT);
    expect(game.restart_armed != 0u && game.game_over != 0u,
        "release arms restart without changing gameplay");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.game_over == 0u && game.lives == 3u && game.score == 0ul,
        "fresh fire press performs complete restart");
    expect(game.player.x == 10u && game.player.y == 48u &&
        game.respawn_sequence == 0u && game.fire_cooldown == 0u,
        "restart restores player sequence and cooldown");
    expect(game.weapon_level == GAME_WEAPON_LEVEL_MIN &&
        game.power_item.active == 0u &&
        game.power_item.move_counter == 0u,
        "restart restores level one and clears the power item");
    expect(game.enemies[0].rect.x == 140u &&
        game.enemies[1].rect.x == 170u &&
        game.enemies[2].rect.x == 200u &&
        game.enemies[3].rect.x == 230u,
        "restart restores all four enemies");
    expect(game.enemies[0].fire_counter == 0u &&
        game.enemies[1].fire_counter == 15u &&
        game.enemies[2].fire_counter == 30u &&
        game.enemies[3].fire_counter == 45u,
        "restart restores all enemy fire phases");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        expect(game.enemy_bullets[i].active == 0u,
            "restart clears all enemy bullets");
    }
    expect(game.dying == 0u && game.explosion_timer == 0u &&
        game.invincibility_timer == 0u && game.restart_armed == 0u,
        "restart clears death invincibility and restart state");
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        expect(game.bullets[i].active == 0u,
            "restart frame clears every player bullet and does not fire");
    }
    expect(game.planet_offset == 0u && game.planet_counter == 0u &&
        game.far_star_offset == 0u && game.near_star_offset == 0u &&
        game.animation_frame == 0u,
        "restart resets all scrolling and animation");
}

int main(void)
{
    test_initial_state();
    test_background_animation_and_player();
    test_enemy_entry_and_patterns();
    test_player_fire_and_aabb();
    test_weapon_levels_and_atomic_fire();
    test_hits_and_respawns();
    test_enemy_fire();
    test_dropper_and_power_item();
    test_damage_and_priority();
    test_explosion_respawn_and_invincibility();
    test_game_over_and_restart();
    printf("PASS: %u game logic checks\n", checks);
    return EXIT_SUCCESS;
}
