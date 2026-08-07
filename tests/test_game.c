#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

static void init_normal(GameState* game)
{
    unsigned char i;

    game_start(game);
    game->phase = GAME_PHASE_NORMAL;
    game->phase_timer = 0u;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game->enemies[i].active = 1u;
    }
}

static void init_normal_stage(GameState* game, unsigned char stage)
{
    game_start(game);
    game->stage = stage;
    game->phase = GAME_PHASE_STAGE_INTRO;
    game->phase_timer = GAME_STAGE_INTRO_FRAMES - 1u;
    game_update(game, 0u);
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

static unsigned char count_enemy_bullets(const GameState* game)
{
    unsigned char i;
    unsigned char count;

    count = 0u;
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active != 0u) {
            ++count;
        }
    }
    return count;
}

static void enter_boss(GameState* game, unsigned char stage)
{
    game_start(game);
    game->stage = stage;
    game->phase = GAME_PHASE_WARNING;
    game->phase_timer = GAME_WARNING_FRAMES - 1u;
    game_update(game, 0u);
}

static void test_stage_one_configuration(void)
{
    const GameStageConfig* stage_config;
    const GameEnemyFormationSlot* slot;
    static const unsigned char xs[GAME_MAX_ENEMIES] = {
        140u, 170u, 200u, 230u
    };
    static const unsigned char ys[GAME_MAX_ENEMIES] = {
        47u, 23u, 70u, 38u
    };
    static const unsigned char types[GAME_MAX_ENEMIES] = {
        GAME_ENEMY_TYPE_SCOUT, GAME_ENEMY_TYPE_SAUCER,
        GAME_ENEMY_TYPE_SCOUT, GAME_ENEMY_TYPE_DROPPER
    };
    static const unsigned char patterns[GAME_MAX_ENEMIES] = {
        GAME_ENEMY_PATTERN_STRAIGHT, GAME_ENEMY_PATTERN_WAVE,
        GAME_ENEMY_PATTERN_DIVE, GAME_ENEMY_PATTERN_STRAIGHT
    };
    static const unsigned char intervals[GAME_MAX_ENEMIES] = {
        90u, 60u, 90u, 75u
    };
    unsigned char i;

    stage_config = game_get_stage_config(1u);
    expect(stage_config != (const GameStageConfig*)0 &&
        stage_config->background_theme_id == GAME_BACKGROUND_THEME_SPACE &&
        stage_config->enemy_formation_id == GAME_ENEMY_FORMATION_SPACE &&
        stage_config->boss_config_id == 0u &&
        stage_config->boss_appearance_id ==
            GAME_BOSS_APPEARANCE_SPACE_FORTRESS &&
        stage_config->environment_id == GAME_ENVIRONMENT_ASTEROIDS,
        "stage one selects SPACE formation and SPACE_FORTRESS IDs");
    expect(game_get_stage_config(0u) == (const GameStageConfig*)0 &&
        game_get_stage_config(4u) == (const GameStageConfig*)0,
        "stage configuration rejects values outside one through three");
    stage_config = game_get_stage_config(2u);
    expect(stage_config->background_theme_id == GAME_BACKGROUND_THEME_SKY &&
        stage_config->enemy_formation_id == GAME_ENEMY_FORMATION_AIR &&
        stage_config->boss_config_id == 1u &&
        stage_config->boss_appearance_id ==
            GAME_BOSS_APPEARANCE_AIR_CARRIER &&
        stage_config->environment_id == GAME_ENVIRONMENT_WIND,
        "stage two selects SKY AIR and AIR_CARRIER IDs");
    stage_config = game_get_stage_config(3u);
    expect(stage_config->background_theme_id == GAME_BACKGROUND_THEME_CAVE &&
        stage_config->enemy_formation_id == GAME_ENEMY_FORMATION_CAVE &&
        stage_config->boss_config_id == 2u &&
        stage_config->boss_appearance_id ==
            GAME_BOSS_APPEARANCE_ROCK_GUARDIAN &&
        stage_config->environment_id == GAME_ENVIRONMENT_ROCKFALL,
        "stage three selects CAVE formation and ROCK_GUARDIAN IDs");

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        slot = game_get_enemy_formation_slot(GAME_ENEMY_FORMATION_SPACE, i);
        expect(slot != (const GameEnemyFormationSlot*)0 &&
            slot->x == xs[i] && slot->y == ys[i] &&
            slot->type == types[i] && slot->pattern == patterns[i] &&
            slot->fire_interval == intervals[i] &&
            slot->fire_phase == (unsigned char)(i * 15u),
            "SPACE formation slot exposes coordinates type movement and fire");
    }
    expect(game_get_enemy_formation_slot(GAME_ENEMY_FORMATION_COUNT, 0u) ==
            (const GameEnemyFormationSlot*)0 &&
        game_get_enemy_formation_slot(GAME_ENEMY_FORMATION_SPACE,
            GAME_MAX_ENEMIES) == (const GameEnemyFormationSlot*)0,
        "formation lookup rejects invalid formation and slot IDs");
}

static void test_stage_three_configuration_and_cave_formation(void)
{
    GameState game;
    const GameEnemyFormationSlot* slot;
    static const unsigned char xs[GAME_MAX_ENEMIES] = {
        148u, 184u, 216u, 248u
    };
    static const unsigned char ys[GAME_MAX_ENEMIES] = {
        22u, 72u, 44u, 82u
    };
    static const unsigned char types[GAME_MAX_ENEMIES] = {
        GAME_ENEMY_TYPE_CAVE_BAT, GAME_ENEMY_TYPE_ROCK_WORM,
        GAME_ENEMY_TYPE_CAVE_BAT, GAME_ENEMY_TYPE_MINING_DRONE
    };
    static const unsigned char patterns[GAME_MAX_ENEMIES] = {
        GAME_ENEMY_PATTERN_WAVE, GAME_ENEMY_PATTERN_DIVE,
        GAME_ENEMY_PATTERN_STRAIGHT, GAME_ENEMY_PATTERN_WAVE
    };
    static const unsigned char intervals[GAME_MAX_ENEMIES] = {
        66u, 84u, 66u, 78u
    };
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        slot = game_get_enemy_formation_slot(GAME_ENEMY_FORMATION_CAVE, i);
        expect(slot != (const GameEnemyFormationSlot*)0 &&
            slot->x == xs[i] && slot->y == ys[i] &&
            slot->type == types[i] && slot->pattern == patterns[i] &&
            slot->fire_interval == intervals[i] &&
            slot->fire_phase == (unsigned char)(i * 16u),
            "CAVE formation exposes every fixed slot field");
    }

    init_normal_stage(&game, 3u);
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        expect(game.enemies[i].rect.x == xs[i] &&
            game.enemies[i].rect.y == ys[i] &&
            game.enemies[i].type == types[i] &&
            game.enemies[i].pattern == patterns[i] &&
            game.enemies[i].fire_interval == intervals[i] &&
            game.enemies[i].fire_counter == (unsigned char)(i * 16u),
            "stage three normal entry initializes the CAVE formation");
    }
    expect(game.enemies[0].drops_power == 0u &&
        game.enemies[1].drops_power == 0u &&
        game.enemies[2].drops_power == 0u &&
        game.enemies[3].drops_power != 0u,
        "only the initial MINING_DRONE carries power-drop capability");
    game_update(&game, 0u);
    expect(game.enemies[0].rect.x == 147u &&
        game.enemies[1].rect.x == 183u &&
        game.enemies[1].fire_counter == 16u,
        "CAVE enemies preserve staggered offscreen entry behavior");
}

static void test_stage_three_background_scroll(void)
{
    GameState game;
    GameState frozen;

    game_start(&game);
    game.stage = 3u;
    game.phase = GAME_PHASE_STAGE_INTRO;
    advance_frames(&game, 8u);
    expect(game.planet_offset == 1u && game.planet_counter == 0u &&
        game.far_star_offset == 2u && game.far_star_counter == 0u &&
        game.near_star_offset == 4u && game.near_star_counter == 0u,
        "CAVE wall rock and formation layers advance at exact 8 4 2 rates");
    game.planet_offset = 191u;
    game.planet_counter = 7u;
    game.far_star_offset = 159u;
    game.far_star_counter = 3u;
    game.near_star_offset = 159u;
    game.near_star_counter = 1u;
    game_update(&game, 0u);
    expect(game.planet_offset == 0u && game.planet_counter == 0u &&
        game.far_star_offset == 0u && game.far_star_counter == 0u &&
        game.near_star_offset == 0u && game.near_star_counter == 0u,
        "CAVE layers wrap at exact 192 160 and 160 periods");
    game.dying = 1u;
    frozen = game;
    game_update(&game, 0u);
    expect(game.planet_offset == frozen.planet_offset &&
        game.planet_counter == frozen.planet_counter &&
        game.far_star_offset == frozen.far_star_offset &&
        game.near_star_offset == frozen.near_star_offset,
        "stage three explosion freezes all CAVE scroll state");
}

static void test_stage_two_configuration_and_air_formation(void)
{
    GameState game;
    const GameEnemyFormationSlot* slot;
    static const unsigned char xs[GAME_MAX_ENEMIES] = {
        144u, 180u, 212u, 244u
    };
    static const unsigned char ys[GAME_MAX_ENEMIES] = {
        24u, 64u, 42u, 78u
    };
    static const unsigned char types[GAME_MAX_ENEMIES] = {
        GAME_ENEMY_TYPE_FIGHTER, GAME_ENEMY_TYPE_BOMBER,
        GAME_ENEMY_TYPE_FIGHTER, GAME_ENEMY_TYPE_SUPPLY
    };
    static const unsigned char patterns[GAME_MAX_ENEMIES] = {
        GAME_ENEMY_PATTERN_STRAIGHT, GAME_ENEMY_PATTERN_WAVE,
        GAME_ENEMY_PATTERN_DIVE, GAME_ENEMY_PATTERN_WAVE
    };
    static const unsigned char intervals[GAME_MAX_ENEMIES] = {
        72u, 96u, 72u, 84u
    };
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        slot = game_get_enemy_formation_slot(GAME_ENEMY_FORMATION_AIR, i);
        expect(slot != (const GameEnemyFormationSlot*)0 &&
            slot->x == xs[i] && slot->y == ys[i] &&
            slot->type == types[i] && slot->pattern == patterns[i] &&
            slot->fire_interval == intervals[i] &&
            slot->fire_phase == (unsigned char)(i * 18u),
            "AIR formation exposes every fixed slot field");
    }

    init_normal_stage(&game, 2u);
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        expect(game.enemies[i].rect.x == xs[i] &&
            game.enemies[i].rect.y == ys[i] &&
            game.enemies[i].type == types[i] &&
            game.enemies[i].pattern == patterns[i] &&
            game.enemies[i].fire_interval == intervals[i] &&
            game.enemies[i].fire_counter == (unsigned char)(i * 18u),
            "stage two normal entry initializes the AIR formation");
    }
    expect(game.enemies[0].drops_power == 0u &&
        game.enemies[1].drops_power == 0u &&
        game.enemies[2].drops_power == 0u &&
        game.enemies[3].drops_power != 0u,
        "only the initial SUPPLY slot carries power-drop capability");

    game_update(&game, 0u);
    expect(game.enemies[0].rect.x == 143u &&
        game.enemies[1].rect.x == 179u &&
        game.enemies[1].move_counter == 0u &&
        game.enemies[1].fire_counter == 18u,
        "AIR enemies preserve staggered offscreen entry behavior");
}

static void test_stage_two_background_scroll(void)
{
    GameState game;
    GameState frozen;
    unsigned char i;

    game_start(&game);
    game.stage = 2u;
    game.phase = GAME_PHASE_STAGE_INTRO;
    advance_frames(&game, 1u);
    expect(game.planet_counter == 1u && game.planet_offset == 0u &&
        game.far_star_counter == 1u && game.far_star_offset == 0u &&
        game.near_star_counter == 1u && game.near_star_offset == 0u,
        "SKY far mid and near layers wait on their first update");
    advance_frames(&game, 7u);
    expect(game.planet_counter == 0u && game.planet_offset == 1u &&
        game.far_star_counter == 0u && game.far_star_offset == 2u &&
        game.near_star_counter == 0u && game.near_star_offset == 4u,
        "SKY layers advance at exact 8 4 and 2 update boundaries");
    game.planet_offset = 191u;
    game.planet_counter = 7u;
    game.far_star_offset = 159u;
    game.far_star_counter = 3u;
    game.near_star_offset = 159u;
    game.near_star_counter = 1u;
    game_update(&game, 0u);
    expect(game.planet_offset == 0u && game.planet_counter == 0u &&
        game.far_star_offset == 0u && game.far_star_counter == 0u &&
        game.near_star_offset == 0u && game.near_star_counter == 0u,
        "SKY layers wrap at 192 160 and 160 without underflow");

    game.dying = 1u;
    game.explosion_timer = 0u;
    frozen = game;
    game_update(&game, 0u);
    expect(game.planet_offset == frozen.planet_offset &&
        game.planet_counter == frozen.planet_counter &&
        game.far_star_offset == frozen.far_star_offset &&
        game.near_star_offset == frozen.near_star_offset,
        "stage two explosion freezes all SKY scroll state");

    init_normal_stage(&game, 2u);
    game.planet_offset = 33u;
    game.planet_counter = 5u;
    game.far_star_offset = 44u;
    game.far_star_counter = 2u;
    game.near_star_offset = 55u;
    game.near_star_counter = 1u;
    for (i = 1u; i < GAME_MAX_ENEMIES; ++i) {
        game.enemies[i].active = 0u;
    }
    game.enemies[0].rect.x = game.player.x;
    game.enemies[0].rect.y = game.player.y;
    game.enemies[0].base_y = game.player.y;
    game_update(&game, 0u);
    frozen = game;
    advance_frames(&game, GAME_EXPLOSION_FRAMES);
    expect(game.dying == 0u && game.invincibility_timer == 60u,
        "stage two non-final death completes the normal respawn");
    expect(game.planet_offset == frozen.planet_offset &&
        game.planet_counter == frozen.planet_counter &&
        game.far_star_offset == frozen.far_star_offset &&
        game.far_star_counter == frozen.far_star_counter &&
        game.near_star_offset == frozen.near_star_offset &&
        game.near_star_counter == frozen.near_star_counter,
        "stage two non-final respawn preserves all SKY scroll state");
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

    init_normal(&game);
    expect(game.player.x == 10u && game.player.y == 48u,
        "player starts at the fixed position");
    expect(game.lives == 3u && game.score == 0ul && game.game_over == 0u,
        "score lives and game over start clean");
    expect(GAME_MAX_ENEMIES == 4u && GAME_MAX_ENEMY_BULLETS == 16u &&
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
        expect(game.enemies[i].fire_interval ==
            (game.enemies[i].type == GAME_ENEMY_TYPE_SCOUT ? 90u :
                (game.enemies[i].type == GAME_ENEMY_TYPE_SAUCER ?
                    60u : 75u)),
            "enemy stores its SPACE formation fire interval");
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

static void test_boot_initialization_and_intro_input(void)
{
    GameState first;
    GameState second;

    memset(&first, 0x00, sizeof(first));
    memset(&second, 0xff, sizeof(second));
    game_init(&first);
    game_init(&second);
    expect(memcmp(&first, &second, sizeof(first)) == 0,
        "game init fully determines every GameState byte");
    expect(first.stage == 1u && first.phase == GAME_PHASE_TITLE &&
        first.phase_timer == 0u && first.lives == GAME_INITIAL_LIVES &&
        first.game_over == 0u && first.dying == 0u &&
        first.restart_armed == 0u && first.title_start_armed == 0u &&
        first.sound.bgm_active == 0u &&
        first.sound.output_bgm.active == 0u &&
        first.sound.output_sfx.active == 0u,
        "boot starts at the clean silent title with start input disarmed");
    game_update(&first, GAME_INPUT_FIRE | GAME_INPUT_RIGHT);
    expect(first.phase == GAME_PHASE_TITLE && first.title_start_armed == 0u &&
        first.player.x == 10u && first.player.y == 48u &&
        count_player_bullets(&first) == 0u,
        "held boot fire cannot skip the title or fire a shot");
    game_update(&first, GAME_INPUT_RIGHT);
    expect(first.phase == GAME_PHASE_TITLE && first.title_start_armed != 0u &&
        first.player.x == 10u && first.player.y == 48u,
        "releasing fire arms a later title start without movement");
    game_update(&first, GAME_INPUT_FIRE | GAME_INPUT_RIGHT);
    expect(first.phase == GAME_PHASE_STAGE_INTRO && first.phase_timer == 0u &&
        first.player.x == 10u && first.player.y == 48u &&
        count_player_bullets(&first) == 0u,
        "fresh title fire starts intro without moving or firing");
    game_update(&first, GAME_INPUT_FIRE | GAME_INPUT_RIGHT);
    expect(first.phase == GAME_PHASE_STAGE_INTRO && first.phase_timer == 1u &&
        first.player.x == 10u && first.player.y == 48u &&
        count_player_bullets(&first) == 0u,
        "intro ignores held A B and direction input without firing or moving");
    advance_frames(&first, GAME_STAGE_INTRO_FRAMES - 1u);
    expect(first.phase == GAME_PHASE_NORMAL && first.phase_timer == 0u,
        "stage one intro advances to normal after exactly ninety updates");
    game_update(&first, GAME_INPUT_RIGHT | GAME_INPUT_FIRE);
    expect(first.player.x == 12u && count_player_bullets(&first) == 1u,
        "normal phase accepts movement and A B fire input");
}

static void test_background_animation_and_player(void)
{
    GameState game;
    unsigned int i;

    init_normal(&game);
    game_update(&game, 0u);
    expect(game.near_star_offset == 0u && game.far_star_offset == 0u,
        "background waits for its interval");
    game_update(&game, 0u);
    expect(game.near_star_offset == 1u && game.far_star_offset == 0u,
        "near background moves after two updates");
    advance_frames(&game, 2u);
    expect(game.near_star_offset == 2u && game.far_star_offset == 1u,
        "far background moves after four updates");

    init_normal(&game);
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

    init_normal(&game);
    disable_enemies_except(&game, 3u);
    game.planet_counter = 7u;
    game.enemies[3].rect.x = 100u;
    game.enemies[3].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 3u);
    game_update(&game, 0u);
    expect(game.planet_offset == 1u && game.planet_counter == 0u &&
        game.power_item.active != 0u && game.score == 100ul,
        "Dropper hit update advances planet exactly once");

    init_normal(&game);
    game.near_star_offset = 159u;
    game.near_star_counter = 1u;
    game.far_star_offset = 159u;
    game.far_star_counter = 3u;
    game_update(&game, 0u);
    expect(game.near_star_offset == 0u && game.far_star_offset == 0u,
        "both background layers wrap deterministically");

    init_normal(&game);
    advance_frames(&game, 7u);
    expect(game.animation_frame == 0u && game.animation_counter == 7u,
        "animation holds for seven updates");
    game_update(&game, 0u);
    expect(game.animation_frame == 1u && game.animation_counter == 0u,
        "animation changes on update eight");

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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
    init_normal(&game);
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

    init_normal(&game);
    disable_enemies_except(&game, 3u);
    game_update(&game, GAME_INPUT_FIRE);
    expect(count_player_bullets(&game) == 1u &&
        game.bullets[0].rect.x == game.player.x + GAME_PLAYER_WIDTH + 4u &&
        game.bullets[0].rect.y == game.player.y + 2u,
        "level one fires one centered bullet into the lowest slot");
    expect(game.fire_cooldown == 8u,
        "successful level one fire starts eight update cooldown");

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
    game.enemies[0].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    place_player_bullet_hit(&game, 1u, 0u);
    game_update(&game, 0u);
    expect(game.score == 100ul && game.bullets[1].active != 0u,
        "a respawned slot cannot be hit twice in one update");

    init_normal(&game);
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

    init_normal(&game);
    untouched = game.enemies[2];
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.enemies[2].rect.x == (unsigned char)(untouched.rect.x - 1u) &&
        game.enemies[2].base_y == untouched.base_y &&
        game.enemies[2].fire_counter == untouched.fire_counter,
        "destroying one slot leaves offscreen sibling fields unchanged except x");

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.power_item.active == 0u,
        "Scout and Saucer hits never create a power item");

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

static void test_air_respawn_and_supply_drop(void)
{
    GameState game;

    init_normal_stage(&game, 2u);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.score == 100ul && game.power_item.active == 0u &&
        game.enemies[0].rect.x == 184u &&
        game.enemies[0].base_y == 33u &&
        game.enemies[0].type == GAME_ENEMY_TYPE_BOMBER &&
        game.enemies[0].pattern == GAME_ENEMY_PATTERN_WAVE &&
        game.enemies[0].fire_interval == 96u &&
        game.enemies[0].drops_power == 0u,
        "AIR slot zero uses its x y type movement and no-drop respawn formula");

    game.enemies[0].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.enemies[0].rect.x == 184u &&
        game.enemies[0].base_y == 52u &&
        game.enemies[0].type == GAME_ENEMY_TYPE_FIGHTER &&
        game.enemies[0].pattern == GAME_ENEMY_PATTERN_DIVE &&
        game.enemies[0].fire_interval == 72u,
        "AIR ordinary slots cycle FIGHTER BOMBER and three movements");

    init_normal_stage(&game, 2u);
    disable_enemies_except(&game, 3u);
    game.enemies[3].rect.x = 154u;
    game.enemies[3].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 3u);
    game_update(&game, 0u);
    expect(game.power_item.active != 0u &&
        game.power_item.rect.x == 156u && game.power_item.rect.y == 42u &&
        game.enemies[3].rect.x == 238u &&
        game.enemies[3].type == GAME_ENEMY_TYPE_SUPPLY &&
        game.enemies[3].base_y == 14u &&
        game.enemies[3].pattern == GAME_ENEMY_PATTERN_WAVE &&
        game.enemies[3].fire_interval == 84u &&
        game.enemies[3].fire_counter == 54u &&
        game.enemies[3].drops_power != 0u,
        "AIR slot three remains SUPPLY and alone creates the power item");

    init_normal(&game);
    expect(game.enemies[3].type == GAME_ENEMY_TYPE_DROPPER &&
        game.enemies[3].drops_power != 0u,
        "stage one Dropper retains data-driven power-drop capability");
}

static void test_cave_respawn_and_drone_drop(void)
{
    GameState game;

    init_normal_stage(&game, 3u);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.score == 100ul && game.power_item.active == 0u &&
        game.enemies[0].rect.x == 188u &&
        game.enemies[0].base_y == 39u &&
        game.enemies[0].type == GAME_ENEMY_TYPE_ROCK_WORM &&
        game.enemies[0].pattern == GAME_ENEMY_PATTERN_WAVE &&
        game.enemies[0].fire_interval == 84u &&
        game.enemies[0].drops_power == 0u,
        "CAVE slot zero uses its first deterministic respawn formula");

    game.enemies[0].rect.x = 100u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.enemies[0].rect.x == 188u &&
        game.enemies[0].base_y == 62u &&
        game.enemies[0].type == GAME_ENEMY_TYPE_CAVE_BAT &&
        game.enemies[0].pattern == GAME_ENEMY_PATTERN_DIVE &&
        game.enemies[0].fire_interval == 66u,
        "CAVE ordinary slots cycle BAT WORM and three movements");

    init_normal_stage(&game, 3u);
    disable_enemies_except(&game, 3u);
    game.enemies[3].rect.x = 154u;
    game.enemies[3].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 3u);
    game_update(&game, 0u);
    expect(game.power_item.active != 0u &&
        game.power_item.rect.x == 156u && game.power_item.rect.y == 42u,
        "MINING_DRONE creates a power item at its pre-respawn center");
    expect(game.enemies[3].rect.x == 242u &&
        game.enemies[3].type == GAME_ENEMY_TYPE_MINING_DRONE,
        "CAVE slot three keeps fixed MINING_DRONE type and x");
    expect(game.enemies[3].base_y == 34u &&
        game.enemies[3].pattern == GAME_ENEMY_PATTERN_WAVE,
        "CAVE slot three uses deterministic y and movement");
    expect(game.enemies[3].fire_interval == 78u &&
        game.enemies[3].fire_counter == 48u &&
        game.enemies[3].drops_power != 0u,
        "respawned MINING_DRONE keeps fire phase and drop capability");

    init_normal(&game);
    expect(game.enemies[3].type == GAME_ENEMY_TYPE_DROPPER &&
        game.enemies[3].drops_power != 0u,
        "CAVE integration preserves stage one Dropper power drops");
    init_normal_stage(&game, 2u);
    expect(game.enemies[3].type == GAME_ENEMY_TYPE_SUPPLY &&
        game.enemies[3].drops_power != 0u,
        "CAVE integration preserves stage two SUPPLY power drops");
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
        game->stage != frozen->stage ||
        game->phase != frozen->phase ||
        game->phase_timer != frozen->phase_timer ||
        game->weapon_level != frozen->weapon_level ||
        game->power_item.active != frozen->power_item.active ||
        game->power_item.rect.x != frozen->power_item.rect.x ||
        game->power_item.rect.y != frozen->power_item.rect.y ||
        game->power_item.move_counter != frozen->power_item.move_counter ||
        game->boss.active != frozen->boss.active ||
        game->boss.rect.x != frozen->boss.rect.x ||
        game->boss.rect.y != frozen->boss.rect.y ||
        game->boss.hp != frozen->boss.hp ||
        game->boss.max_hp != frozen->boss.max_hp ||
        game->boss.config_id != frozen->boss.config_id ||
        game->boss.appearance_id != frozen->boss.appearance_id ||
        game->boss.script_step != frozen->boss.script_step ||
        game->boss.attack_timer != frozen->boss.attack_timer ||
        game->boss.move_phase != frozen->boss.move_phase ||
        game->boss.direction != frozen->boss.direction ||
        game->boss.alternate_cannon != frozen->boss.alternate_cannon) {
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
            a->fire_interval != b->fire_interval ||
            a->fire_counter != b->fire_counter ||
            a->drops_power != b->drops_power) {
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
                frozen->enemy_bullets[i].rect.y ||
            game->enemy_bullets[i].velocity_x !=
                frozen->enemy_bullets[i].velocity_x ||
            game->enemy_bullets[i].velocity_y !=
                frozen->enemy_bullets[i].velocity_y) {
            return 0;
        }
    }
    return 1;
}

static void test_damage_and_priority(void)
{
    GameState game;
    unsigned char i;

    init_normal(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = 1u;
    game.enemies[0].rect.y = 80u;
    game.enemies[0].base_y = 80u;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 1u && game.dying != 0u,
        "left edge alone starts one death");

    init_normal(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.enemies[0].rect.y = game.player.y;
    game.enemies[0].base_y = game.player.y;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 1u && game.dying != 0u,
        "enemy body contact alone starts one death");

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
    game.enemies[0].rect.x = 20u;
    game.enemies[0].rect.y = game.player.y;
    place_player_bullet_hit(&game, 0u, 0u);
    game_update(&game, 0u);
    expect(game.score == 100ul && game.lives == GAME_INITIAL_LIVES &&
        game.dying == 0u,
        "hit target cannot damage after same-update respawn");

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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

    init_normal(&game);
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
        "release arms title return without changing gameplay");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.phase == GAME_PHASE_TITLE && game.game_over == 0u &&
        game.lives == 3u && game.score == 0ul &&
        game.sound.bgm_active == 0u &&
        game.sound.output_bgm.active == 0u &&
        game.sound.output_sfx.active == 0u &&
        game.title_start_armed == 0u,
        "fresh fire press returns game over to a silent clean title");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.phase == GAME_PHASE_TITLE && game.title_start_armed == 0u,
        "the game-over return press cannot also start from title");
    game_update(&game, 0u);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.phase == GAME_PHASE_STAGE_INTRO && game.game_over == 0u &&
        game.lives == 3u && game.score == 0ul,
        "a title fire press performs complete restart");
    expect(game.player.x == 10u && game.player.y == 48u &&
        game.respawn_sequence == 0u && game.fire_cooldown == 0u,
        "title restart restores player sequence and cooldown");
    expect(game.weapon_level == GAME_WEAPON_LEVEL_MIN &&
        game.power_item.active == 0u &&
        game.power_item.move_counter == 0u,
        "title restart restores level one and clears the power item");
    expect(game.enemies[0].rect.x == 140u &&
        game.enemies[1].rect.x == 170u &&
        game.enemies[2].rect.x == 200u &&
        game.enemies[3].rect.x == 230u,
        "title restart restores all four enemies");
    expect(game.enemies[0].fire_counter == 0u &&
        game.enemies[1].fire_counter == 15u &&
        game.enemies[2].fire_counter == 30u &&
        game.enemies[3].fire_counter == 45u,
        "title restart restores all enemy fire phases");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        expect(game.enemy_bullets[i].active == 0u,
            "title restart clears all enemy bullets");
    }
    expect(game.dying == 0u && game.explosion_timer == 0u &&
        game.invincibility_timer == 0u && game.restart_armed == 0u,
        "title restart clears death invincibility and restart state");
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        expect(game.bullets[i].active == 0u,
            "title start clears every player bullet and does not fire");
    }
    expect(game.planet_offset == 0u && game.planet_counter == 0u &&
        game.far_star_offset == 0u && game.near_star_offset == 0u &&
        game.animation_frame == 0u,
        "title restart resets all scrolling and animation");
}

static void test_stage_phase_machine(void)
{
    GameState game;
    unsigned char i;

    game_start(&game);
    expect(game.stage == 1u && game.phase == GAME_PHASE_STAGE_INTRO &&
        game.phase_timer == 0u,
        "game starts at stage one intro with a zero elapsed timer");
    expect(game.score == 0ul && game.lives == GAME_INITIAL_LIVES &&
        game.weapon_level == GAME_WEAPON_LEVEL_MIN,
        "new campaign starts with base score lives and weapon level");
    advance_frames(&game, GAME_STAGE_INTRO_FRAMES - 1u);
    expect(game.phase == GAME_PHASE_STAGE_INTRO &&
        game.phase_timer == GAME_STAGE_INTRO_FRAMES - 1u,
        "intro remains active immediately before update ninety");
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        expect(game.enemies[i].active == 0u,
            "intro keeps every normal enemy inactive");
    }
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.phase == GAME_PHASE_NORMAL && game.phase_timer == 0u,
        "intro update ninety enters normal with a reset timer");
    expect(count_player_bullets(&game) == 0u,
        "intro transition fire input does not create a player bullet");
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        expect(game.enemies[i].active != 0u,
            "normal entry initializes every enemy slot");
    }

    game.phase_timer = GAME_NORMAL_FRAMES - 2u;
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_NORMAL &&
        game.phase_timer == GAME_NORMAL_FRAMES - 1u,
        "normal remains active immediately before update 1125");
    game.bullets[0].active = 1u;
    game.enemy_bullets[0].active = 1u;
    game.power_item.active = 1u;
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_WARNING && game.phase_timer == 0u,
        "normal update 1125 enters warning with a reset timer");
    expect(count_player_bullets(&game) == 0u &&
        count_enemy_bullets(&game) == 0u &&
        game.power_item.active == 0u && game.boss.active == 0u,
        "normal boundary clears bullets item and boss state");
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        expect(game.enemies[i].active == 0u,
            "warning entry clears every normal enemy");
    }

    game.player.x = 10u;
    game.phase_timer = GAME_WARNING_FRAMES - 2u;
    game_update(&game, GAME_INPUT_RIGHT | GAME_INPUT_FIRE);
    expect(game.phase == GAME_PHASE_WARNING &&
        game.phase_timer == GAME_WARNING_FRAMES - 1u &&
        game.player.x == 12u && count_player_bullets(&game) == 0u,
        "warning update 119 permits movement but suppresses firing");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.phase == GAME_PHASE_BOSS && game.phase_timer == 0u &&
        game.boss.active != 0u && count_player_bullets(&game) == 0u,
        "warning update 120 initializes the boss without firing");

    game.score = 4321ul;
    game.lives = 2u;
    game.weapon_level = 3u;
    game.planet_offset = 91u;
    game.planet_counter = 6u;
    game.far_star_offset = 73u;
    game.far_star_counter = 2u;
    game.near_star_offset = 51u;
    game.near_star_counter = 1u;
    game.phase = GAME_PHASE_STAGE_CLEAR;
    game.phase_timer = GAME_STAGE_CLEAR_FRAMES - 2u;
    game.boss.active = 0u;
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_STAGE_CLEAR &&
        game.phase_timer == GAME_STAGE_CLEAR_FRAMES - 1u,
        "stage clear remains active immediately before update 120");
    game_update(&game, 0u);
    expect(game.stage == 2u && game.phase == GAME_PHASE_STAGE_INTRO &&
        game.phase_timer == 0u,
        "stage one clear update 120 enters stage two intro");
    expect(game.score == 4321ul && game.lives == 2u &&
        game.weapon_level == 3u,
        "stage transition preserves score lives and weapon level");
    expect(game.planet_offset == 0u && game.planet_counter == 0u &&
        game.far_star_offset == 0u && game.far_star_counter == 0u &&
        game.near_star_offset == 0u && game.near_star_counter == 0u,
        "stage two intro alone resets every background offset and counter");
    game.planet_offset = 17u;
    game.planet_counter = 3u;
    game.far_star_offset = 29u;
    game.far_star_counter = 1u;
    game.near_star_offset = 41u;
    game.near_star_counter = 0u;
    game.phase = GAME_PHASE_STAGE_CLEAR;
    game.phase_timer = GAME_STAGE_CLEAR_FRAMES - 1u;
    game_update(&game, 0u);
    expect(game.stage == 3u && game.phase == GAME_PHASE_STAGE_INTRO,
        "stage two clear advances to stage three intro");
    expect(game.planet_offset == 0u && game.planet_counter == 0u &&
        game.far_star_offset == 0u && game.far_star_counter == 0u &&
        game.near_star_offset == 0u && game.near_star_counter == 0u,
        "stage three intro resets every background offset and counter");
    game.phase = GAME_PHASE_STAGE_CLEAR;
    game.phase_timer = GAME_STAGE_CLEAR_FRAMES - 1u;
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.stage == 3u && game.phase == GAME_PHASE_ALL_CLEAR &&
        game.restart_armed == 0u,
        "stage three clear enters all clear and disarms held restart");

    init_normal(&game);
    game.phase_timer = GAME_NORMAL_FRAMES - 1u;
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = game.player.x;
    game.enemies[0].rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.dying != 0u && game.phase == GAME_PHASE_NORMAL &&
        game.phase_timer == GAME_NORMAL_FRAMES,
        "damage on the normal boundary counts once and defers transition");
    advance_frames(&game, GAME_EXPLOSION_FRAMES - 1u);
    game_update(&game, 0u);
    expect(game.dying == 0u && game.phase == GAME_PHASE_WARNING &&
        game.phase_timer == 0u,
        "boundary death enters warning only after the frozen explosion");
}

static void test_boss_configuration_and_scripts(void)
{
    GameState game;
    const GameBossConfig* config;
    const GameBossStep* step;
    unsigned char i;
    unsigned char lower_y;

    config = game_get_boss_config(1u);
    expect(config != (const GameBossConfig*)0 && config->max_hp == 60u &&
        config->width == 24u && config->height == 16u &&
        config->stop_x == 132u && config->defeat_score == 2000u,
        "stage one boss table exposes fixed HP AABB stop and score");
    config = game_get_boss_config(2u);
    expect(config != (const GameBossConfig*)0 && config->max_hp == 90u &&
        config->width == 28u && config->height == 14u &&
        config->stop_x == 128u && config->defeat_score == 3000u &&
        config->movement == GAME_BOSS_MOVE_VERTICAL,
        "stage two boss table exposes fixed HP AABB stop and score");
    config = game_get_boss_config(3u);
    expect(config != (const GameBossConfig*)0 && config->max_hp == 120u &&
        config->width == 24u && config->height == 24u &&
        config->stop_x == 132u && config->defeat_score == 5000u,
        "stage three boss table exposes fixed HP AABB stop and score");
    expect(game_get_boss_config(0u) == (const GameBossConfig*)0 &&
        game_get_boss_config(4u) == (const GameBossConfig*)0,
        "boss table rejects stages outside one through three");

    step = game_get_boss_step(0u);
    expect(step != (const GameBossStep*)0 &&
        step->shot_type == GAME_BOSS_SHOT_STRAIGHT,
        "stage one script begins with straight shots");
    step = game_get_boss_step(1u);
    expect(step->shot_type == GAME_BOSS_SHOT_FAN,
        "stage one script includes the three-way fan");
    step = game_get_boss_step(2u);
    expect(step->shot_type == GAME_BOSS_SHOT_CANNON_CYCLE &&
        step->movement == GAME_BOSS_MOVE_VERTICAL,
        "stage two script combines three-cannon cycling and vertical motion");
    step = game_get_boss_step(4u);
    expect(step->shot_type == GAME_BOSS_SHOT_BURST &&
        step->duration == 90u && step->fire_interval == 10u &&
        step->movement == GAME_BOSS_MOVE_STILL,
        "stage three script begins with a stationary burst step");
    step = game_get_boss_step(5u);
    expect(step->shot_type == GAME_BOSS_SHOT_PINCER &&
        step->duration == 120u && step->fire_interval == 40u &&
        step->movement == GAME_BOSS_MOVE_STILL,
        "stage three script includes stationary forty-update pincers");
    step = game_get_boss_step(6u);
    expect(step->shot_type == GAME_BOSS_SHOT_PINCER &&
        step->duration == 120u && step->fire_interval == 60u &&
        step->movement == GAME_BOSS_MOVE_WIDE,
        "stage three script ends with moving sixty-update pincers");
    expect(game_get_boss_step(7u) == (const GameBossStep*)0,
        "boss script lookup rejects an out-of-range step");

    enter_boss(&game, 1u);
    expect(game.boss.config_id == 0u && game.boss.hp == 60u &&
        game.boss.max_hp == 60u && game.boss.rect.x == 132u &&
        game.boss.rect.y == 43u && game.boss.rect.width == 24u &&
        game.boss.rect.height == 16u &&
        game.boss.appearance_id == GAME_BOSS_APPEARANCE_SPACE_FORTRESS,
        "stage one boss initializes entirely from configuration");
    game.boss.attack_timer = 19u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 1u &&
        game.enemy_bullets[0].rect.x == 130u &&
        game.enemy_bullets[0].rect.y == 47u &&
        game.enemy_bullets[0].velocity_x == (signed char)-2 &&
        game.enemy_bullets[0].velocity_y == (signed char)0,
        "straight attack uses the forward turret at x130 y47");
    game.enemy_bullets[0].active = 0u;
    game.boss.script_step = 1u;
    game.boss.attack_timer = 59u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 3u &&
        game.enemy_bullets[0].rect.x == 130u &&
        game.enemy_bullets[0].rect.y == 51u &&
        game.enemy_bullets[0].velocity_y == (signed char)-1 &&
        game.enemy_bullets[1].velocity_y == (signed char)0 &&
        game.enemy_bullets[2].velocity_y == (signed char)1,
        "fan attack emits three signed vertical trajectories");

    enter_boss(&game, 1u);
    game.boss.attack_timer = 18u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 0u &&
        game.boss.attack_timer == 19u && game.boss.script_step == 0u,
        "stage one straight step stays silent immediately before twenty");
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 1u &&
        game.boss.attack_timer == 20u && game.boss.script_step == 0u,
        "stage one straight step fires exactly on update twenty");
    game.boss.attack_timer = 119u;
    game_update(&game, 0u);
    expect(game.boss.script_step == 1u && game.boss.attack_timer == 0u,
        "stage one switches from straight to fan at update one hundred twenty");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game.enemy_bullets[i].active = 0u;
    }
    game.boss.attack_timer = 58u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 0u &&
        game.boss.attack_timer == 59u,
        "stage one fan step stays silent immediately before sixty");
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 3u &&
        game.boss.attack_timer == 60u,
        "stage one fan step fires exactly on update sixty");
    game.boss.attack_timer = 119u;
    game_update(&game, 0u);
    expect(game.boss.script_step == 0u && game.boss.attack_timer == 0u,
        "stage one attack script wraps after two hundred forty updates");

    enter_boss(&game, 2u);
    expect(game.boss.config_id == 1u && game.boss.hp == 90u &&
        game.boss.max_hp == 90u && game.boss.rect.x == 128u &&
        game.boss.rect.y == 44u && game.boss.rect.width == 28u &&
        game.boss.rect.height == 14u &&
        game.boss.appearance_id == GAME_BOSS_APPEARANCE_AIR_CARRIER,
        "stage two initializes the complete AIR_CARRIER boss state");
    game.boss.attack_timer = 19u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 1u &&
        game.enemy_bullets[0].rect.y == game.boss.rect.y + 2u &&
        game.boss.alternate_cannon == 1u,
        "air carrier cannon cycle begins at the upper gun");
    game.enemy_bullets[0].active = 0u;
    game.boss.attack_timer = 19u;
    lower_y = (unsigned char)(game.boss.rect.y +
        game.boss.rect.height / 2u);
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 1u &&
        game.enemy_bullets[0].rect.y == lower_y &&
        game.boss.alternate_cannon == 2u &&
        game.boss.rect.y == 45u,
        "air carrier cannon cycle advances to the middle gun");
    game.enemy_bullets[0].active = 0u;
    game.boss.attack_timer = 19u;
    lower_y = (unsigned char)(game.boss.rect.y +
        game.boss.rect.height - 4u);
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 1u &&
        game.enemy_bullets[0].rect.y == lower_y &&
        game.boss.alternate_cannon == 0u && game.boss.rect.x == 128u,
        "air carrier cannon cycle fires lower then wraps while x stays fixed");

    enter_boss(&game, 2u);
    advance_frames(&game, 23u);
    expect(game.boss.rect.y == 55u && game.boss.move_phase == 1u,
        "air carrier remains below its lower boundary before update twenty four");
    game_update(&game, 0u);
    expect(game.boss.rect.y == 56u && game.boss.rect.x == 128u,
        "air carrier reaches y56 on the exact two-update movement boundary");
    game_update(&game, 0u);
    game_update(&game, 0u);
    expect(game.boss.rect.y == 55u && game.boss.direction == 0u &&
        game.boss.rect.x == 128u,
        "air carrier reverses upward after holding the y56 endpoint");

    enter_boss(&game, 2u);
    game.boss.attack_timer = 18u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 0u &&
        game.boss.attack_timer == 19u,
        "air carrier first step stays silent immediately before twenty");
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 1u &&
        game.boss.attack_timer == 20u,
        "air carrier first step fires exactly on update twenty");
    game.boss.attack_timer = 119u;
    game_update(&game, 0u);
    expect(game.boss.script_step == 1u && game.boss.attack_timer == 0u,
        "air carrier switches cadence at update one hundred twenty");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game.enemy_bullets[i].active = 0u;
    }
    game.boss.attack_timer = 13u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 0u &&
        game.boss.attack_timer == 14u,
        "air carrier second step stays silent immediately before fifteen");
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 1u &&
        game.boss.attack_timer == 15u,
        "air carrier second step fires exactly on update fifteen");
    game.boss.attack_timer = 119u;
    game_update(&game, 0u);
    expect(game.boss.script_step == 0u && game.boss.attack_timer == 0u,
        "air carrier attack cycle wraps after two hundred forty updates");

    enter_boss(&game, 3u);
    expect(game.boss.config_id == 2u && game.boss.hp == 120u &&
        game.boss.max_hp == 120u && game.boss.rect.x == 132u &&
        game.boss.rect.y == 39u && game.boss.rect.width == 24u &&
        game.boss.rect.height == 24u &&
        game.boss.appearance_id == GAME_BOSS_APPEARANCE_ROCK_GUARDIAN,
        "stage three initializes the complete ROCK_GUARDIAN state");
    game.boss.attack_timer = 8u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 0u &&
        game.boss.attack_timer == 9u && game.boss.rect.x == 132u &&
        game.boss.rect.y == 39u,
        "rock guardian remains still and silent immediately before ten");
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 1u &&
        game.enemy_bullets[0].rect.x == 130u &&
        game.enemy_bullets[0].rect.y == 51u &&
        game.enemy_bullets[0].velocity_x == (signed char)-2 &&
        game.enemy_bullets[0].velocity_y == (signed char)0,
        "rock guardian burst fires from the central core at update ten");

    enter_boss(&game, 3u);
    game.boss.attack_timer = 89u;
    game_update(&game, 0u);
    expect(game.boss.script_step == 1u && game.boss.attack_timer == 0u &&
        game.boss.rect.x == 132u && game.boss.rect.y == 39u,
        "rock guardian switches after ninety stationary burst updates");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game.enemy_bullets[i].active = 0u;
    }
    game.boss.attack_timer = 38u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 0u &&
        game.boss.attack_timer == 39u && game.boss.rect.x == 132u,
        "stationary pincer waits immediately before forty");
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 2u &&
        game.enemy_bullets[0].velocity_y == (signed char)1 &&
        game.enemy_bullets[1].velocity_y == (signed char)-1 &&
        game.boss.rect.x == 132u && game.boss.rect.y == 39u,
        "stationary pincer emits inward shots at update forty");
    game.boss.attack_timer = 119u;
    game_update(&game, 0u);
    expect(game.boss.script_step == 2u && game.boss.attack_timer == 0u,
        "rock guardian switches to wide movement after step two");
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game.enemy_bullets[i].active = 0u;
    }
    game.boss.attack_timer = 58u;
    game.boss.move_phase = 1u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 0u &&
        game.boss.attack_timer == 59u && game.boss.rect.y == 40u &&
        game.boss.rect.x == 128u,
        "wide step moves every two updates and waits before sixty");
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == 2u &&
        game.boss.attack_timer == 60u,
        "wide step pincer fires exactly on update sixty");
    game.boss.attack_timer = 119u;
    game_update(&game, 0u);
    expect(game.boss.script_step == 0u && game.boss.attack_timer == 0u,
        "rock guardian wraps its complete 330-update script");

    enter_boss(&game, 3u);
    game.boss.script_step = 2u;
    advance_frames(&game, 35u);
    expect(game.boss.rect.y == 56u && game.boss.move_phase == 1u,
        "rock guardian approaches its lower wide-movement endpoint");
    game_update(&game, 0u);
    expect(game.boss.rect.y == 57u && game.boss.rect.x == 128u,
        "rock guardian reaches y57 with downward x128");
    game_update(&game, 0u);
    game_update(&game, 0u);
    expect(game.boss.rect.y == 56u && game.boss.direction == 0u &&
        game.boss.rect.x == 132u,
        "rock guardian reverses upward with x132 after y57");
    game.boss.rect.y = 22u;
    game.boss.direction = 0u;
    game.boss.move_phase = 0u;
    game_update(&game, 0u);
    game_update(&game, 0u);
    expect(game.boss.rect.y == 21u && game.boss.rect.x == 132u,
        "rock guardian reaches y21 with upward x132");
    game_update(&game, 0u);
    game_update(&game, 0u);
    expect(game.boss.rect.y == 22u && game.boss.direction == 1u &&
        game.boss.rect.x == 128u,
        "rock guardian reverses downward with x128 after y21");
}

static void test_enemy_bullet_capacity_and_signed_motion(void)
{
    GameState game;
    unsigned char i;

    enter_boss(&game, 2u);
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game.enemy_bullets[i].active = 1u;
        game.enemy_bullets[i].rect.x = 80u;
        game.enemy_bullets[i].rect.y = 80u;
        game.enemy_bullets[i].velocity_x = 0;
        game.enemy_bullets[i].velocity_y = 0;
    }
    game.boss.attack_timer = 119u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == GAME_MAX_ENEMY_BULLETS &&
        game.boss.attack_timer == 0u && game.boss.script_step == 1u &&
        game.boss.alternate_cannon == 1u,
        "full sixteen-slot pool advances AIR_CARRIER script and cannon phase");
    game.enemy_bullets[0].active = 0u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == GAME_MAX_ENEMY_BULLETS - 1u &&
        game.boss.attack_timer == 1u && game.boss.script_step == 1u,
        "freeing a slot after a missed cadence does not accumulate a shot");

    enter_boss(&game, 3u);
    game.boss.script_step = 2u;
    game.boss.attack_timer = 59u;
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game.enemy_bullets[i].active = 1u;
        game.enemy_bullets[i].rect.x = 80u;
        game.enemy_bullets[i].rect.y = 80u;
        game.enemy_bullets[i].velocity_x = 0;
        game.enemy_bullets[i].velocity_y = 0;
    }
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == GAME_MAX_ENEMY_BULLETS &&
        game.boss.attack_timer == 60u && game.boss.script_step == 2u,
        "full pool consumes the rock guardian moving pincer cadence");
    game.enemy_bullets[0].active = 0u;
    game_update(&game, 0u);
    expect(count_enemy_bullets(&game) == GAME_MAX_ENEMY_BULLETS - 1u &&
        game.boss.attack_timer == 61u,
        "rock guardian does not accumulate a full-pool pincer shot");

    enter_boss(&game, 1u);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = 30u;
    game.enemy_bullets[0].rect.y = 30u;
    game.enemy_bullets[0].velocity_x = (signed char)-2;
    game.enemy_bullets[0].velocity_y = (signed char)-1;
    game.enemy_bullets[1].active = 1u;
    game.enemy_bullets[1].rect.x = 30u;
    game.enemy_bullets[1].rect.y = 30u;
    game.enemy_bullets[1].velocity_x = (signed char)-2;
    game.enemy_bullets[1].velocity_y = (signed char)1;
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].rect.x == 28u &&
        game.enemy_bullets[0].rect.y == 29u &&
        game.enemy_bullets[1].rect.x == 28u &&
        game.enemy_bullets[1].rect.y == 31u,
        "signed bullet velocity updates both upward and downward paths");
    game.enemy_bullets[0].rect.x = 0u;
    game.enemy_bullets[0].rect.y = 20u;
    game.enemy_bullets[0].velocity_x = (signed char)-1;
    game.enemy_bullets[0].velocity_y = 0;
    game.enemy_bullets[1].rect.x = 159u;
    game.enemy_bullets[1].rect.y = 20u;
    game.enemy_bullets[1].velocity_x = 1;
    game.enemy_bullets[1].velocity_y = 0;
    game.enemy_bullets[2].active = 1u;
    game.enemy_bullets[2].rect.x = 20u;
    game.enemy_bullets[2].rect.y = 0u;
    game.enemy_bullets[2].velocity_x = 0;
    game.enemy_bullets[2].velocity_y = (signed char)-1;
    game.enemy_bullets[3].active = 1u;
    game.enemy_bullets[3].rect.x = 20u;
    game.enemy_bullets[3].rect.y = 101u;
    game.enemy_bullets[3].velocity_x = 0;
    game.enemy_bullets[3].velocity_y = 1;
    game_update(&game, 0u);
    expect(game.enemy_bullets[0].active == 0u &&
        game.enemy_bullets[1].active == 0u &&
        game.enemy_bullets[2].active == 0u &&
        game.enemy_bullets[3].active == 0u,
        "signed intermediates remove bullets beyond all four screen edges");
}

static void place_boss_hit(GameState* game, unsigned char bullet)
{
    game->bullets[bullet].active = 1u;
    game->bullets[bullet].rect.x =
        (unsigned char)(game->boss.rect.x - 4u);
    game->bullets[bullet].rect.y = game->boss.rect.y;
}

static void test_boss_hits_death_and_priority(void)
{
    GameState game;
    GameState frozen;
    unsigned int i;
    unsigned int held_timer;

    enter_boss(&game, 1u);
    place_boss_hit(&game, 0u);
    place_boss_hit(&game, 1u);
    place_boss_hit(&game, 2u);
    game_update(&game, 0u);
    expect(game.boss.hp == 57u && count_player_bullets(&game) == 0u,
        "three same-update player bullet hits each remove one boss HP");

    game.boss.hp = 2u;
    game.score = 100ul;
    game.player.x = game.boss.rect.x;
    game.player.y = game.boss.rect.y;
    game.boss.attack_timer = 19u;
    place_boss_hit(&game, 0u);
    place_boss_hit(&game, 1u);
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_STAGE_CLEAR && game.score == 2100ul &&
        game.lives == GAME_INITIAL_LIVES && game.dying == 0u,
        "zero HP prioritizes one score award and clear over contact damage");
    expect(game.boss.active == 0u && count_enemy_bullets(&game) == 0u &&
        count_player_bullets(&game) == 0u,
        "boss defeat suppresses later movement and firing and clears combat");
    game_update(&game, 0u);
    expect(game.score == 2100ul,
        "stage clear cannot award the boss score a second time");

    enter_boss(&game, 2u);
    game.boss.hp = 33u;
    game.boss.script_step = 1u;
    game.boss.attack_timer = 22u;
    game.boss.move_phase = 1u;
    game.boss.rect.x = game.player.x;
    game.boss.rect.y = game.player.y;
    held_timer = game.phase_timer;
    game_update(&game, 0u);
    expect(game.dying != 0u && game.lives == 2u &&
        game.boss.hp == 33u && game.phase == GAME_PHASE_BOSS &&
        game.phase_timer == held_timer + 1u,
        "boss contact counts once then retains HP phase and elapsed time");
    frozen = game;
    advance_frames(&game, GAME_EXPLOSION_FRAMES - 1u);
    expect(game.dying != 0u && game.explosion_timer == 31u &&
        game.phase == frozen.phase && game.phase_timer == frozen.phase_timer &&
        game.boss.hp == frozen.boss.hp &&
        game.planet_offset == frozen.planet_offset,
        "all first 31 explosion updates freeze boss phase and background");
    game_update(&game, 0u);
    expect(game.dying == 0u && game.invincibility_timer == 60u &&
        game.boss.hp == 33u && game.boss.script_step == 0u &&
        game.boss.attack_timer == 0u && game.boss.move_phase == 0u &&
        game.boss.rect.x == 128u && game.boss.rect.y == 44u &&
        game.boss.direction == 1u && game.boss.alternate_cannon == 0u,
        "boss respawn preserves HP but resets position movement guns and script");
    for (i = 0u; i < 60u; ++i) {
        game.boss.rect.x = game.player.x;
        game.boss.rect.y = game.player.y;
        game_update(&game, 0u);
    }
    expect(game.lives == 2u && game.dying == 0u &&
        game.invincibility_timer == 0u && game.boss.hp == 33u,
        "all sixty boss respawn updates remain protected and preserve HP");
    game.boss.rect.x = game.player.x;
    game.boss.rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.lives == 1u && game.dying != 0u,
        "boss respawn update 61 can start a new death");

    enter_boss(&game, 2u);
    game.boss.hp = 1u;
    game.score = 100ul;
    game.lives = 2u;
    game.weapon_level = 3u;
    place_boss_hit(&game, 0u);
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_STAGE_CLEAR && game.score == 3100ul &&
        game.boss.active == 0u && count_enemy_bullets(&game) == 0u,
        "AIR_CARRIER zero HP awards three thousand once and enters clear");
    game.phase_timer = GAME_STAGE_CLEAR_FRAMES - 1u;
    game_update(&game, 0u);
    expect(game.stage == 3u && game.phase == GAME_PHASE_STAGE_INTRO &&
        game.score == 3100ul && game.lives == 2u &&
        game.weapon_level == 3u,
        "stage two clear enters stage three intro with campaign state held");

    enter_boss(&game, 3u);
    game.boss.hp = 33u;
    game.boss.script_step = 2u;
    game.boss.attack_timer = 22u;
    game.boss.move_phase = 0u;
    game.boss.direction = 0u;
    game.boss.rect.x = game.player.x;
    game.boss.rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.dying != 0u && game.boss.hp == 33u,
        "rock guardian contact begins death while preserving HP");
    advance_frames(&game, GAME_EXPLOSION_FRAMES - 1u);
    game_update(&game, 0u);
    expect(game.dying == 0u && game.boss.hp == 33u &&
        game.boss.rect.x == 132u && game.boss.rect.y == 39u &&
        game.boss.direction == 1u && game.boss.move_phase == 0u &&
        game.boss.script_step == 0u && game.boss.attack_timer == 0u,
        "rock guardian death reset preserves HP and resets all runtime state");

    enter_boss(&game, 3u);
    game.boss.hp = 1u;
    game.score = 100ul;
    game.lives = 2u;
    game.weapon_level = 3u;
    place_boss_hit(&game, 0u);
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_STAGE_CLEAR && game.score == 5100ul &&
        game.boss.active == 0u && count_enemy_bullets(&game) == 0u,
        "ROCK_GUARDIAN zero HP awards five thousand exactly once");
    game_update(&game, 0u);
    expect(game.score == 5100ul,
        "stage three clear cannot award the guardian score twice");
    game.phase_timer = GAME_STAGE_CLEAR_FRAMES - 1u;
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.stage == 3u && game.phase == GAME_PHASE_ALL_CLEAR &&
        game.score == 5100ul && game.lives == 2u &&
        game.weapon_level == 3u && game.restart_armed == 0u,
        "rock guardian clear reaches ALL CLEAR with campaign state held");

    enter_boss(&game, 1u);
    game.lives = 1u;
    game.boss.rect.x = game.player.x;
    game.boss.rect.y = game.player.y;
    game_update(&game, 0u);
    expect(game.lives == 0u && game.dying != 0u && game.game_over == 0u,
        "final boss damage starts an explosion before game over");
    advance_frames(&game, GAME_EXPLOSION_FRAMES - 1u);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.dying == 0u && game.game_over != 0u &&
        game.phase == GAME_PHASE_BOSS && game.restart_armed == 0u,
        "final boss explosion enters game over after update 32");
}

static void test_stage_one_asteroids(void)
{
    GameState game;
    static const unsigned int frames[GAME_ASTEROID_EVENT_COUNT] = {
        60u, 240u, 420u, 600u, 780u, 960u
    };
    static const unsigned char ys[GAME_ASTEROID_EVENT_COUNT] = {
        22u, 70u, 44u, 84u, 30u, 60u
    };
    unsigned char i;

    init_normal_stage(&game, 1u);
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    for (i = 0u; i < GAME_ASTEROID_EVENT_COUNT; ++i) {
        game.phase_timer = frames[i] - 1u;
        game.environment_event_cursor = i;
        game.asteroids[0].active = 0u;
        game.asteroids[1].active = 0u;
        game_update(&game, 0u);
        expect(game.asteroids[0].active != 0u &&
            game.asteroids[0].rect.x == 152u &&
            game.asteroids[0].rect.y == ys[i] &&
            game.environment_event_cursor == (unsigned char)(i + 1u),
            "asteroid event spawns exact fixed coordinates and advances cursor");
    }
    game_update(&game, 0u);
    expect(game.asteroids[0].rect.x == 151u,
        "asteroid spawn update skips movement then advances one pixel");

    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = 120u;
    game.asteroids[1].active = 0u;
    game.environment_event_cursor = 1u;
    game.phase_timer = 239u;
    game_update(&game, 0u);
    expect(game.asteroids[1].active != 0u &&
        game.asteroids[1].rect.x == 152u &&
        game.asteroids[1].rect.y == 70u,
        "asteroid allocation selects the lowest free fixed slot");

    game.asteroids[0].active = 1u;
    game.asteroids[1].active = 1u;
    game.asteroids[0].rect.x = 100u;
    game.asteroids[1].rect.x = 110u;
    game.environment_event_cursor = 2u;
    game.phase_timer = 419u;
    game_update(&game, 0u);
    expect(game.environment_event_cursor == 3u &&
        game.asteroids[0].rect.x == 99u &&
        game.asteroids[1].rect.x == 109u,
        "full asteroid pool discards event without deferred retry");

    game.phase_timer = 1u;
    game.environment_event_cursor = GAME_ASTEROID_EVENT_COUNT;
    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = 50u;
    game.asteroids[0].rect.y = 40u;
    game.asteroids[1].active = 0u;
    game.bullets[0].active = 1u;
    game.bullets[0].rect.x = 46u;
    game.bullets[0].rect.y = 40u;
    game.score = 10ul;
    game_update(&game, 0u);
    expect(game.asteroids[0].active == 0u &&
        game.bullets[0].active == 0u && game.score == 260ul,
        "one player bullet destroys one asteroid for 250 points once");
    game_update(&game, 0u);
    expect(game.score == 260ul,
        "destroyed asteroid cannot award its score twice");

    game.enemies[0].active = 1u;
    game.enemies[0].rect.x = 50u;
    game.enemies[0].rect.y = 40u;
    game.enemies[0].drops_power = 0u;
    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = 50u;
    game.asteroids[0].rect.y = 40u;
    game.bullets[0].active = 1u;
    game.bullets[0].rect.x = 46u;
    game.bullets[0].rect.y = 40u;
    game_update(&game, 0u);
    expect(game.score == 360ul && game.asteroids[0].active != 0u &&
        game.bullets[0].active == 0u,
        "normal enemy hit has priority over an overlapping asteroid");

    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = 0u;
    game_update(&game, 0u);
    expect(game.asteroids[0].active == 0u && game.score == 360ul,
        "asteroid leaving the left edge disappears without score");

    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.asteroids[0].rect.y = game.player.y;
    game.invincibility_timer = 3u;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES &&
        game.asteroids[0].active == 0u && game.dying == 0u,
        "invincible asteroid contact consumes rock without life loss or score");

    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game.invincibility_timer = 0u;
    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.asteroids[0].rect.y = game.player.y;
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game.enemy_bullets[0].velocity_x = (signed char)-2;
    game.enemy_bullets[0].velocity_y = 0;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 1u && game.dying != 0u,
        "asteroid and enemy bullet damage aggregate to one life loss");
}

static void test_stage_two_wind(void)
{
    GameState game;

    init_normal_stage(&game, 2u);
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    advance_frames(&game, 149u);
    expect(game.wind.state == GAME_WIND_STATE_INACTIVE &&
        game.environment_event_cursor == 0u,
        "wind remains inactive before the exact first event update");
    game_update(&game, 0u);
    expect(game.wind.state == GAME_WIND_STATE_WARNING &&
        game.wind.y == 18u &&
        game.wind.direction == GAME_WIND_DIRECTION_UP &&
        game.wind.timer == GAME_WIND_WARNING_FRAMES &&
        game.environment_event_cursor == 1u,
        "first wind event starts a 45-update upward warning band");
    advance_frames(&game, GAME_WIND_WARNING_FRAMES - 1u);
    expect(game.wind.state == GAME_WIND_STATE_WARNING &&
        game.wind.timer == 1u,
        "wind warning remains harmless through update 44");
    game_update(&game, 0u);
    expect(game.wind.state == GAME_WIND_STATE_ACTIVE &&
        game.wind.timer == GAME_WIND_ACTIVE_FRAMES &&
        game.wind.push_counter == 0u,
        "wind warning transitions deterministically to 150 active updates");

    game.player.y = 24u;
    game_update(&game, GAME_INPUT_DOWN);
    expect(game.player.y == 26u && game.wind.push_counter == 1u,
        "first active wind update waits while normal input moves first");
    game_update(&game, GAME_INPUT_DOWN);
    expect(game.player.y == 27u && game.wind.push_counter == 0u,
        "second active update applies one-pixel wind after two-pixel input");
    game.player.y = 80u;
    game_update(&game, 0u);
    game_update(&game, 0u);
    expect(game.player.y == 80u,
        "wind leaves a player outside its AABB band unchanged");

    game.wind.state = GAME_WIND_STATE_ACTIVE;
    game.wind.y = GAME_HUD_HEIGHT;
    game.wind.direction = GAME_WIND_DIRECTION_UP;
    game.wind.timer = 10u;
    game.wind.push_counter = 1u;
    game.player.y = GAME_HUD_HEIGHT;
    game_update(&game, 0u);
    expect(game.player.y == GAME_HUD_HEIGHT,
        "upward wind clamps player at HUD lower boundary");
    game.wind.y = 78u;
    game.wind.direction = GAME_WIND_DIRECTION_DOWN;
    game.wind.push_counter = 1u;
    game.player.y = GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT;
    game_update(&game, 0u);
    expect(game.player.y == GAME_SCREEN_HEIGHT - GAME_PLAYER_HEIGHT,
        "downward wind clamps player at playfield bottom");
    game.wind.state = GAME_WIND_STATE_ACTIVE;
    game.wind.timer = 1u;
    game.wind.push_counter = 0u;
    game_update(&game, 0u);
    expect(game.wind.state == GAME_WIND_STATE_INACTIVE &&
        game.wind.push_counter == 0u,
        "wind becomes inactive immediately after its 150th active update");

    game.wind.state = GAME_WIND_STATE_INACTIVE;
    game.environment_event_cursor = 1u;
    game.phase_timer = 509u;
    game_update(&game, 0u);
    expect(game.wind.state == GAME_WIND_STATE_WARNING &&
        game.wind.y == 58u &&
        game.wind.direction == GAME_WIND_DIRECTION_DOWN,
        "second wind event uses fixed lower band and downward direction");
    game.wind.state = GAME_WIND_STATE_INACTIVE;
    game.environment_event_cursor = 2u;
    game.phase_timer = 869u;
    game_update(&game, 0u);
    expect(game.wind.state == GAME_WIND_STATE_WARNING &&
        game.wind.y == 36u &&
        game.wind.direction == GAME_WIND_DIRECTION_UP &&
        game.environment_event_cursor == GAME_WIND_EVENT_COUNT,
        "third wind event uses fixed middle band and exhausts cursor");

    game.wind.timer = 20u;
    game.wind.push_counter = 1u;
    game.dying = 1u;
    game.explosion_timer = 0u;
    game.lives = 2u;
    advance_frames(&game, GAME_EXPLOSION_FRAMES);
    expect(game.wind.state == GAME_WIND_STATE_WARNING &&
        game.wind.timer == 20u && game.wind.push_counter == 1u,
        "all 32 death updates freeze wind schedule timer and push phase");
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game_update(&game, 0u);
    expect(game.wind.timer == 19u,
        "non-final respawn resumes wind from its exact frozen phase");
}

static void test_stage_three_rockfall(void)
{
    GameState game;
    static const unsigned int frames[GAME_ROCKFALL_EVENT_COUNT] = {
        90u, 240u, 390u, 540u, 690u, 840u, 990u
    };
    static const unsigned char xs[GAME_ROCKFALL_EVENT_COUNT] = {
        24u, 72u, 120u, 48u, 136u, 96u, 16u
    };
    unsigned char i;

    init_normal_stage(&game, 3u);
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    for (i = 0u; i < GAME_ROCKFALL_EVENT_COUNT; ++i) {
        game.phase_timer = frames[i] - 1u;
        game.environment_event_cursor = i;
        game.falling_rocks[0].state = GAME_ROCK_STATE_INACTIVE;
        game.falling_rocks[1].state = GAME_ROCK_STATE_INACTIVE;
        game_update(&game, 0u);
        expect(game.falling_rocks[0].state == GAME_ROCK_STATE_WARNING &&
            game.falling_rocks[0].rect.x == xs[i] &&
            game.falling_rocks[0].rect.y == 94u &&
            game.falling_rocks[0].timer == GAME_ROCK_WARNING_FRAMES,
            "rockfall event starts exact landing marker without collision");
    }
    advance_frames(&game, GAME_ROCK_WARNING_FRAMES - 1u);
    expect(game.falling_rocks[0].state == GAME_ROCK_STATE_WARNING &&
        game.falling_rocks[0].timer == 1u,
        "rock warning remains nonphysical through update 44");
    game_update(&game, 0u);
    expect(game.falling_rocks[0].state == GAME_ROCK_STATE_FALLING &&
        game.falling_rocks[0].rect.y == 10u,
        "warning transition spawns falling rock without moving it");
    game_update(&game, 0u);
    expect(game.falling_rocks[0].rect.y == 12u,
        "falling rock moves down exactly two pixels on its next update");

    game.falling_rocks[0].state = GAME_ROCK_STATE_WARNING;
    game.falling_rocks[1].state = GAME_ROCK_STATE_WARNING;
    game.falling_rocks[0].timer = 10u;
    game.falling_rocks[1].timer = 10u;
    game.environment_event_cursor = 1u;
    game.phase_timer = 239u;
    game_update(&game, 0u);
    expect(game.environment_event_cursor == 2u &&
        game.falling_rocks[0].timer == 9u &&
        game.falling_rocks[1].timer == 9u,
        "full rock pool discards event and advances without deferred spawn");

    game.falling_rocks[0].state = GAME_ROCK_STATE_WARNING;
    game.falling_rocks[0].timer = 10u;
    game.falling_rocks[1].state = GAME_ROCK_STATE_INACTIVE;
    game.environment_event_cursor = 2u;
    game.phase_timer = 389u;
    game_update(&game, 0u);
    expect(game.falling_rocks[1].state == GAME_ROCK_STATE_WARNING &&
        game.falling_rocks[1].rect.x == 120u &&
        game.falling_rocks[1].timer == GAME_ROCK_WARNING_FRAMES,
        "rockfall allocation selects the lowest free fixed slot");

    game.environment_event_cursor = GAME_ROCKFALL_EVENT_COUNT;
    game.phase_timer = 1u;
    game.falling_rocks[0].state = GAME_ROCK_STATE_FALLING;
    game.falling_rocks[0].rect.x = 50u;
    game.falling_rocks[0].rect.y = 40u;
    game.falling_rocks[1].state = GAME_ROCK_STATE_INACTIVE;
    game.bullets[0].active = 1u;
    game.bullets[0].rect.x = 46u;
    game.bullets[0].rect.y = 40u;
    game.score = 20ul;
    game_update(&game, 0u);
    expect(game.falling_rocks[0].state == GAME_ROCK_STATE_FALLING &&
        game.falling_rocks[0].rect.y == 42u &&
        game.bullets[0].active != 0u && game.score == 20ul,
        "falling rock is indestructible and never awards score");

    game.player.x = 50u;
    game.player.y = 94u;
    game.falling_rocks[0].state = GAME_ROCK_STATE_FALLING;
    game.falling_rocks[0].rect.x = 50u;
    game.falling_rocks[0].rect.y = 92u;
    game_update(&game, 0u);
    expect(game.falling_rocks[0].rect.y == 94u &&
        game.falling_rocks[0].state == GAME_ROCK_STATE_IMPACT &&
        game.falling_rocks[0].timer == GAME_ROCK_IMPACT_FRAMES &&
        game.lives == GAME_INITIAL_LIVES - 1u && game.dying != 0u,
        "landing position checks player AABB before entering impact display");
    advance_frames(&game, GAME_EXPLOSION_FRAMES);
    expect(game.falling_rocks[0].state == GAME_ROCK_STATE_IMPACT &&
        game.falling_rocks[0].timer == GAME_ROCK_IMPACT_FRAMES,
        "death explosion freezes rock impact state and timer");

    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game.player.x = 10u;
    game.player.y = 48u;
    advance_frames(&game, GAME_ROCK_IMPACT_FRAMES - 1u);
    expect(game.falling_rocks[0].state == GAME_ROCK_STATE_IMPACT &&
        game.falling_rocks[0].timer == 1u,
        "impact marker remains active for its first eleven resumed updates");
    game_update(&game, 0u);
    expect(game.falling_rocks[0].state == GAME_ROCK_STATE_INACTIVE,
        "impact marker releases its slot after exactly twelve updates");

    game.invincibility_timer = 3u;
    game.falling_rocks[0].state = GAME_ROCK_STATE_FALLING;
    game.falling_rocks[0].rect.x = game.player.x;
    game.falling_rocks[0].rect.y = (unsigned char)(game.player.y - 2u);
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 1u &&
        game.dying == 0u &&
        game.falling_rocks[0].state == GAME_ROCK_STATE_IMPACT,
        "invincible rock contact consumes fall into impact without damage");

    game.invincibility_timer = 0u;
    game.falling_rocks[0].state = GAME_ROCK_STATE_FALLING;
    game.falling_rocks[1].state = GAME_ROCK_STATE_FALLING;
    game.falling_rocks[0].rect.x = game.player.x;
    game.falling_rocks[1].rect.x = game.player.x;
    game.falling_rocks[0].rect.y = (unsigned char)(game.player.y - 2u);
    game.falling_rocks[1].rect.y = (unsigned char)(game.player.y - 2u);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x = (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game.enemy_bullets[0].velocity_x = (signed char)-2;
    game.enemy_bullets[0].velocity_y = 0;
    game_update(&game, 0u);
    expect(game.lives == GAME_INITIAL_LIVES - 2u && game.dying != 0u &&
        game.falling_rocks[0].state == GAME_ROCK_STATE_IMPACT &&
        game.falling_rocks[1].state == GAME_ROCK_STATE_IMPACT,
        "two rocks and enemy bullet still aggregate to one life loss");
}

static void test_environment_phase_boundaries_and_restart(void)
{
    GameState game;
    unsigned char i;

    init_normal_stage(&game, 1u);
    game.asteroids[0].active = 1u;
    game.environment_event_cursor = 4u;
    game.phase_timer = GAME_NORMAL_FRAMES - 1u;
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_WARNING &&
        game.environment_event_cursor == 0u &&
        game.asteroids[0].active == 0u &&
        game.wind.state == GAME_WIND_STATE_INACTIVE,
        "normal exit clears every environment object and schedule cursor");

    game_start(&game);
    for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
        expect(game.asteroids[i].active == 0u &&
            game.falling_rocks[i].state == GAME_ROCK_STATE_INACTIVE &&
            game.asteroids[i].rect.width == GAME_ENVIRONMENT_OBJECT_WIDTH &&
            game.falling_rocks[i].rect.height ==
                GAME_ENVIRONMENT_OBJECT_HEIGHT,
            "game init clears dedicated bounded slots and preserves dimensions");
    }
    expect(game.environment_event_cursor == 0u &&
        game.wind.state == GAME_WIND_STATE_INACTIVE,
        "game init resets environment cursor and wind state");

    game.phase = GAME_PHASE_ALL_CLEAR;
    game.stage = 3u;
    game.falling_rocks[0].state = GAME_ROCK_STATE_IMPACT;
    game.falling_rocks[0].timer = 7u;
    game_update(&game, 0u);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.stage == 1u && game.phase == GAME_PHASE_STAGE_INTRO &&
        game.falling_rocks[0].state == GAME_ROCK_STATE_INACTIVE &&
        game.environment_event_cursor == 0u,
        "ALL CLEAR release and repress fully resets environment state");

    init_normal_stage(&game, 1u);
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game.lives = 1u;
    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = (unsigned char)(game.player.x + 1u);
    game.asteroids[0].rect.y = game.player.y;
    game_update(&game, 0u);
    advance_frames(&game, GAME_EXPLOSION_FRAMES);
    expect(game.game_over != 0u &&
        game.asteroids[0].active == 0u &&
        game.environment_event_cursor == 0u,
        "final explosion clears environment before GAME OVER becomes visible");
}

static void test_all_clear_restart(void)
{
    GameState game;
    GameState frozen;
    unsigned char i;

    game_start(&game);
    game.phase = GAME_PHASE_ALL_CLEAR;
    game.stage = 3u;
    game.score = 9999ul;
    game.lives = 1u;
    game.weapon_level = 3u;
    game.planet_offset = 50u;
    game.restart_armed = 0u;
    game.enemies[0].active = 1u;
    game.enemy_bullets[0].active = 1u;
    game.boss.active = 1u;
    game.boss.hp = 17u;
    frozen = game;
    for (i = 0u; i < 4u; ++i) {
        game_update(&game, GAME_INPUT_FIRE | GAME_INPUT_RIGHT);
    }
    expect(frozen_state_matches(&game, &frozen) != 0 &&
        game.lives == 1u && game.restart_armed == 0u,
        "held fire freezes every ALL CLEAR state and cannot restart it");
    game_update(&game, GAME_INPUT_RIGHT);
    expect(game.phase == GAME_PHASE_ALL_CLEAR && game.restart_armed != 0u,
        "all clear release arms restart without changing state");
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.stage == 1u && game.phase == GAME_PHASE_STAGE_INTRO &&
        game.phase_timer == 0u && game.score == 0ul &&
        game.lives == GAME_INITIAL_LIVES &&
        game.weapon_level == GAME_WEAPON_LEVEL_MIN,
        "fresh all clear press fully restarts at stage one intro");
    expect(game.planet_offset == 0u && count_player_bullets(&game) == 0u &&
        count_enemy_bullets(&game) == 0u && game.boss.active == 0u,
        "all clear restart resets background bullets and boss without firing");
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        expect(game.enemies[i].active == 0u,
            "all clear restart keeps normal enemies clear during intro");
    }
}

static void reset_game_sound(GameState* game)
{
    sound_set_stage(&game->sound, game->stage);
}

static void test_draw_frame_logic_scheduler(void)
{
    GameState game;
    unsigned char remainder;
    unsigned char frame;
    unsigned char update;
    unsigned char updates;
    unsigned int total_updates;

    remainder = 0u;
    total_updates = 0u;
    for (frame = 0u; frame < GAME_LOGIC_UPDATES_DENOMINATOR; ++frame) {
        updates = game_logic_updates_for_draw_frame(&remainder);
        expect(updates == (frame == GAME_LOGIC_UPDATES_DENOMINATOR - 1u ?
            2u : 1u),
            "5/4 scheduler performs its extra deterministic update on frame four");
        total_updates += updates;
    }
    expect(total_updates == GAME_LOGIC_UPDATES_NUMERATOR && remainder == 0u,
        "four 75Hz draw frames always contain exactly five logic updates");

    game_start(&game);
    remainder = 0u;
    for (frame = 0u; frame < GAME_LOGIC_UPDATES_DENOMINATOR; ++frame) {
        updates = game_logic_updates_for_draw_frame(&remainder);
        for (update = 0u; update < updates; ++update) {
            game_update_logic(&game, 0u);
        }
        game_sound_tick(&game);
    }
    expect(game.phase_timer == GAME_LOGIC_UPDATES_NUMERATOR &&
        game.sound.bgm_step == 0u &&
        game.sound.bgm_remaining ==
            (unsigned char)(15u - GAME_LOGIC_UPDATES_DENOMINATOR) &&
        game.sound.output_bgm.active != 0u,
        "5/4 advances stage progression while the BGM/SFX tick stays at 75Hz, advancing once per draw frame rather than once per logic update");
}

static void test_sound_initial_phase_and_fire_integration(void)
{
    GameState game;
    unsigned char i;

    game_start(&game);
    expect(game.sound.bgm_active != 0u &&
        game.sound.bgm_id == SOUND_BGM_STAGE_ONE &&
        game.sound.bgm_step == 0u &&
        game.sound.sfx_id == SOUND_SFX_NONE,
        "game start enables stage one BGM at its head with no active SFX");
    expect(game.sound.output_bgm_bass.active != 0u,
        "game start also enables the stage one bassline through the full game update path");
    advance_frames(&game, 20u);
    game.phase_timer = GAME_STAGE_INTRO_FRAMES - 1u;
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_NORMAL &&
        game.sound.bgm_id == SOUND_BGM_STAGE_ONE &&
        game.sound.bgm_active != 0u && game.sound.output_bgm.active != 0u,
        "intro to normal keeps the same stage BGM running");

    game.phase_timer = GAME_NORMAL_FRAMES - 1u;
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_WARNING &&
        game.sound.bgm_id == SOUND_BGM_STAGE_ONE &&
        game.sound.bgm_active != 0u && game.sound.output_bgm.active != 0u,
        "normal to warning keeps BGM running independently of the WARNING SFX");
    game.phase_timer = GAME_WARNING_FRAMES - 1u;
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_BOSS &&
        game.sound.bgm_id == SOUND_BGM_STAGE_ONE &&
        game.sound.bgm_active != 0u,
        "warning to boss keeps BGM running");

    game.phase = GAME_PHASE_NORMAL;
    game.phase_timer = 0u;
    reset_game_sound(&game);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.sound.sfx_id == SOUND_SFX_SHOT &&
        game.sound.sfx_step == 0u && game.sound.sfx_remaining == 3u,
        "one successful normal volley fires one shot SFX from its head");
    sound_set_stage(&game.sound, game.stage);
    game.fire_cooldown = 2u;
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.sound.sfx_id == SOUND_SFX_NONE,
        "cooldown-blocked normal fire remains silent");
    game.fire_cooldown = 0u;
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        game.bullets[i].active = 1u;
    }
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.sound.sfx_id == SOUND_SFX_NONE,
        "capacity-blocked normal volley remains silent");

    game_start(&game);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.sound.sfx_id == SOUND_SFX_NONE,
        "fire input during stage intro never requests shot SFX");
    enter_boss(&game, 1u);
    reset_game_sound(&game);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.sound.sfx_id == SOUND_SFX_SHOT,
        "one successful boss volley fires the same shot SFX");
}

static void test_sound_enemy_asteroid_and_power_integration(void)
{
    GameState game;
    unsigned char level;

    init_normal(&game);
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game.enemies[0].active = 1u;
    game.enemies[1].active = 1u;
    game.enemies[0].rect.x = 70u;
    game.enemies[0].rect.y = 30u;
    game.enemies[1].rect.x = 70u;
    game.enemies[1].rect.y = 60u;
    place_player_bullet_hit(&game, 0u, 0u);
    place_player_bullet_hit(&game, 1u, 1u);
    reset_game_sound(&game);
    game_update(&game, 0u);
    expect(game.sound.sfx_id == SOUND_SFX_ENEMY_DEFEAT &&
        game.sound.sfx_step == 0u && game.sound.sfx_remaining == 3u &&
        game.score == 200ul,
        "two enemies defeated in one update aggregate to one defeat SFX");

    init_normal_stage(&game, 1u);
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game.environment_event_cursor = GAME_ASTEROID_EVENT_COUNT;
    game.asteroids[0].active = 1u;
    game.asteroids[0].rect.x = 50u;
    game.asteroids[0].rect.y = 40u;
    game.bullets[0].active = 1u;
    game.bullets[0].rect.x = 46u;
    game.bullets[0].rect.y = 40u;
    reset_game_sound(&game);
    game_update(&game, 0u);
    expect(game.asteroids[0].active == 0u &&
        game.sound.sfx_id == SOUND_SFX_ENEMY_DEFEAT &&
        game.score == 250ul,
        "asteroid destruction uses the shared enemy-defeat SFX once");

    for (level = GAME_WEAPON_LEVEL_MIN;
        level <= GAME_WEAPON_LEVEL_MAX; ++level) {
        init_normal(&game);
        disable_enemies_except(&game, GAME_MAX_ENEMIES);
        game.weapon_level = level;
        game.power_item.active = 1u;
        game.power_item.rect.x = game.player.x;
        game.power_item.rect.y = game.player.y;
        reset_game_sound(&game);
        game_update(&game, 0u);
        expect(game.power_item.active == 0u &&
            game.sound.sfx_id == SOUND_SFX_POWER_UP &&
            game.weapon_level == (level == GAME_WEAPON_LEVEL_MAX ?
                GAME_WEAPON_LEVEL_MAX : (unsigned char)(level + 1u)),
            "actual item consumption at every weapon level fires power-up SFX");
    }

    init_normal(&game);
    disable_enemies_except(&game, 3u);
    game.enemies[3].rect.x = 70u;
    game.enemies[3].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 3u);
    reset_game_sound(&game);
    game_update(&game, 0u);
    expect(game.power_item.active != 0u &&
        game.sound.sfx_id == SOUND_SFX_ENEMY_DEFEAT,
        "power item generation is silent apart from the actual enemy defeat");
}

static void test_sound_damage_freeze_and_warning_integration(void)
{
    GameState game;
    unsigned char lives;

    init_normal(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = game.player.x;
    game.enemies[0].rect.y = game.player.y;
    reset_game_sound(&game);
    game_update(&game, 0u);
    expect(game.dying != 0u &&
        game.sound.sfx_id == SOUND_SFX_PLAYER_EXPLOSION &&
        game.sound.sfx_remaining == 7u,
        "real damage begins one player-explosion SFX");
    advance_frames(&game, GAME_EXPLOSION_FRAMES);
    expect(game.dying == 0u && game.sound.bgm_active != 0u &&
        game.sound.sfx_id == SOUND_SFX_NONE &&
        game.sound.output_bgm.active != 0u,
        "all 32 death updates freeze the BGM cursor while explosion SFX plays, and BGM keeps running once it completes");
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game_update(&game, 0u);
    expect(game.sound.output_bgm.active != 0u,
        "first post-respawn update keeps BGM sounding");

    init_normal(&game);
    game.invincibility_timer = 2u;
    lives = game.lives;
    game.enemies[0].rect.x = game.player.x;
    game.enemies[0].rect.y = game.player.y;
    reset_game_sound(&game);
    game_update(&game, 0u);
    expect(game.lives == lives && game.dying == 0u &&
        game.sound.sfx_id == SOUND_SFX_NONE,
        "invincible collision resets gameplay objects without explosion SFX");

    init_normal(&game);
    disable_enemies_except(&game, GAME_MAX_ENEMIES);
    game.phase_timer = GAME_NORMAL_FRAMES - 1u;
    reset_game_sound(&game);
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_WARNING &&
        game.sound.sfx_id == SOUND_SFX_WARNING &&
        game.sound.sfx_remaining == 7u,
        "normal boundary enters warning through its single SFX trigger point");

    init_normal(&game);
    disable_enemies_except(&game, 0u);
    game.phase_timer = GAME_NORMAL_FRAMES - 1u;
    game.enemies[0].rect.x = game.player.x;
    game.enemies[0].rect.y = game.player.y;
    reset_game_sound(&game);
    game_update(&game, 0u);
    expect(game.dying != 0u && game.phase == GAME_PHASE_NORMAL &&
        game.phase_timer == GAME_NORMAL_FRAMES &&
        game.sound.sfx_id == SOUND_SFX_PLAYER_EXPLOSION,
        "boundary damage defers warning and starts only explosion SFX");
    advance_frames(&game, GAME_EXPLOSION_FRAMES);
    expect(game.dying == 0u && game.phase == GAME_PHASE_WARNING &&
        game.sound.sfx_id == SOUND_SFX_WARNING,
        "death completion reaches the same warning SFX trigger point once");
}

static void test_sound_boss_chain_stage_terminal_and_restart(void)
{
    GameState game;
    unsigned int chain_length;

    enter_boss(&game, 1u);
    reset_game_sound(&game);
    game.boss.hp = 1u;
    game.bullets[0].active = 1u;
    game.bullets[0].rect.x =
        (unsigned char)(game.boss.rect.x - 4u);
    game.bullets[0].rect.y = game.boss.rect.y;
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_STAGE_CLEAR &&
        game.sound.sfx_id == SOUND_SFX_BOSS_DEFEAT &&
        game.sound.pending_stage_clear != 0u,
        "boss HP zero starts boss SFX and defers stage-clear SFX once");
    chain_length = sound_get_sfx_length(SOUND_SFX_BOSS_DEFEAT) +
        sound_get_sfx_length(SOUND_SFX_STAGE_CLEAR);
    advance_frames(&game, chain_length - 1u);
    expect(game.phase == GAME_PHASE_STAGE_CLEAR &&
        game.phase_timer == chain_length - 1u &&
        game.sound.sfx_id == SOUND_SFX_NONE &&
        game.sound.pending_stage_clear == 0u,
        "boss-clear chain finishes intact before the 120-update stage switch");

    sound_request_sfx(&game.sound, SOUND_SFX_WARNING);
    game.sound.pending_stage_clear = 1u;
    game.phase_timer = GAME_STAGE_CLEAR_FRAMES - 1u;
    game_update(&game, 0u);
    expect(game.stage == 2u && game.phase == GAME_PHASE_STAGE_INTRO &&
        game.sound.bgm_id == SOUND_BGM_STAGE_TWO &&
        game.sound.bgm_active != 0u && game.sound.bgm_step == 0u && game.sound.sfx_id == SOUND_SFX_NONE &&
        game.sound.pending_stage_clear == 0u,
        "stage switch restarts BGM at the next song head and discards active and pending SFX");

    game.phase = GAME_PHASE_STAGE_CLEAR;
    game.phase_timer = GAME_STAGE_CLEAR_FRAMES - 1u;
    sound_request_sfx(&game.sound, SOUND_SFX_SHOT);
    game_update(&game, 0u);
    expect(game.stage == 3u && game.phase == GAME_PHASE_STAGE_INTRO &&
        game.sound.bgm_id == SOUND_BGM_STAGE_THREE &&
        game.sound.bgm_active != 0u && game.sound.bgm_step == 0u && game.sound.sfx_id == SOUND_SFX_NONE,
        "stage two switch starts stage three cave BGM at its exact head");

    game.phase = GAME_PHASE_STAGE_CLEAR;
    game.phase_timer = GAME_STAGE_CLEAR_FRAMES - 1u;
    sound_set_stage(&game.sound, 3u);
    sound_request_sfx(&game.sound, SOUND_SFX_BOSS_DEFEAT);
    game.sound.pending_stage_clear = 1u;
    game_update(&game, 0u);
    expect(game.phase == GAME_PHASE_ALL_CLEAR &&
        game.sound.bgm_active == 0u &&
        game.sound.sfx_id == SOUND_SFX_NONE &&
        game.sound.pending_stage_clear == 0u &&
        game.sound.output_bgm.active == 0u &&
        game.sound.output_sfx.active == 0u,
        "ALL CLEAR stops BGM and clears active and pending SFX on both channels");
    game_update(&game, 0u);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.stage == 1u && game.phase == GAME_PHASE_STAGE_INTRO &&
        game.sound.bgm_active != 0u &&
        game.sound.bgm_id == SOUND_BGM_STAGE_ONE &&
        game.sound.bgm_step == 0u && game.sound.sfx_id == SOUND_SFX_NONE,
        "ALL CLEAR release and repress restarts gameplay with BGM running from stage one head");

    init_normal(&game);
    disable_enemies_except(&game, 0u);
    game.lives = 1u;
    game.enemies[0].rect.x = game.player.x;
    game.enemies[0].rect.y = game.player.y;
    game_update(&game, 0u);
    advance_frames(&game, GAME_EXPLOSION_FRAMES);
    expect(game.game_over != 0u && game.sound.bgm_active == 0u &&
        game.sound.sfx_id == SOUND_SFX_NONE &&
        game.sound.output_bgm.active == 0u &&
        game.sound.output_sfx.active == 0u,
        "GAME OVER stops all sound on both channels after final explosion completion");
    game_update(&game, 0u);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.game_over == 0u &&
        game.sound.bgm_id == SOUND_BGM_STAGE_ONE &&
        game.sound.bgm_step == 0u && game.sound.sfx_id == SOUND_SFX_NONE,
        "GAME OVER release and repress returns to stage one with BGM disabled");
}

static void test_sound_simultaneous_priority_integration(void)
{
    GameState game;

    init_normal(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = 70u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game.fire_cooldown = 0u;
    reset_game_sound(&game);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.sound.sfx_id == SOUND_SFX_ENEMY_DEFEAT,
        "same-update enemy defeat replaces lower-priority shot SFX");

    init_normal(&game);
    disable_enemies_except(&game, 0u);
    game.enemies[0].rect.x = 70u;
    game.enemies[0].rect.y = 40u;
    place_player_bullet_hit(&game, 0u, 0u);
    game.enemy_bullets[0].active = 1u;
    game.enemy_bullets[0].rect.x =
        (unsigned char)(game.player.x + 2u);
    game.enemy_bullets[0].rect.y = game.player.y;
    game.enemy_bullets[0].velocity_x = (signed char)-2;
    game.enemy_bullets[0].velocity_y = 0;
    reset_game_sound(&game);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.dying != 0u &&
        game.sound.sfx_id == SOUND_SFX_PLAYER_EXPLOSION,
        "same-update real damage replaces shot and enemy-defeat SFX");

    enter_boss(&game, 1u);
    game.boss.hp = 1u;
    game.bullets[0].active = 1u;
    game.bullets[0].rect.x =
        (unsigned char)(game.boss.rect.x - 4u);
    game.bullets[0].rect.y = game.boss.rect.y;
    reset_game_sound(&game);
    game_update(&game, GAME_INPUT_FIRE);
    expect(game.sound.sfx_id == SOUND_SFX_BOSS_DEFEAT &&
        game.sound.pending_stage_clear != 0u,
        "boss defeat overrides same-update shot and retains clear follow-up");
}

int main(void)
{
    test_stage_one_configuration();
    test_stage_two_configuration_and_air_formation();
    test_stage_three_configuration_and_cave_formation();
    test_initial_state();
    test_boot_initialization_and_intro_input();
    test_background_animation_and_player();
    test_stage_two_background_scroll();
    test_stage_three_background_scroll();
    test_enemy_entry_and_patterns();
    test_player_fire_and_aabb();
    test_weapon_levels_and_atomic_fire();
    test_hits_and_respawns();
    test_enemy_fire();
    test_dropper_and_power_item();
    test_air_respawn_and_supply_drop();
    test_cave_respawn_and_drone_drop();
    test_damage_and_priority();
    test_explosion_respawn_and_invincibility();
    test_game_over_and_restart();
    test_stage_phase_machine();
    test_boss_configuration_and_scripts();
    test_enemy_bullet_capacity_and_signed_motion();
    test_boss_hits_death_and_priority();
    test_stage_one_asteroids();
    test_stage_two_wind();
    test_stage_three_rockfall();
    test_environment_phase_boundaries_and_restart();
    test_all_clear_restart();
    test_draw_frame_logic_scheduler();
    test_sound_initial_phase_and_fire_integration();
    test_sound_enemy_asteroid_and_power_integration();
    test_sound_damage_freeze_and_warning_integration();
    test_sound_boss_chain_stage_terminal_and_restart();
    test_sound_simultaneous_priority_integration();
    printf("PASS: %u game logic checks\n", checks);
    return EXIT_SUCCESS;
}
