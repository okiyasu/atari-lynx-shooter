#include "game.h"

#define PLAYER_SPEED 2u
#define BULLET_SPEED 4u
#define ENEMY_BULLET_SPEED 2u
#define FIRE_COOLDOWN_FRAMES 8u
#define ENEMY_MIN_Y (GAME_HUD_HEIGHT + 3u)
#define ENEMY_Y_RANGE 78u
#define FAR_STAR_INTERVAL 4u
#define NEAR_STAR_INTERVAL 2u
#define ANIMATION_INTERVAL 8u
#define ENEMY_DIRECTION_UP 0u
#define ENEMY_DIRECTION_DOWN 1u
#define ENEMY_SCOUT_FIRE_INTERVAL 90u
#define ENEMY_SAUCER_FIRE_INTERVAL 60u
#define ENEMY_DROPPER_FIRE_INTERVAL 75u
#define POWER_ITEM_MOVE_INTERVAL 2u

typedef struct EnemyMovementConfig {
    unsigned char horizontal_speed;
    unsigned char vertical_interval;
    unsigned char vertical_amplitude;
    unsigned char behavior;
} EnemyMovementConfig;

static const EnemyMovementConfig enemy_movements[3] = {
    { 1u, 0u, 0u, GAME_ENEMY_PATTERN_STRAIGHT },
    { 1u, 3u, 6u, GAME_ENEMY_PATTERN_WAVE },
    { 1u, 2u, 12u, GAME_ENEMY_PATTERN_DIVE }
};

static const unsigned char initial_enemy_x[GAME_MAX_ENEMIES] = {
    140u, 170u, 200u, 230u
};

static const unsigned char initial_enemy_y[GAME_MAX_ENEMIES] = {
    47u, 23u, 70u, 38u
};

static void clear_player_bullets(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        game->bullets[i].active = 0u;
    }
}

static void clear_power_item(GameState* game)
{
    game->power_item.active = 0u;
    game->power_item.move_counter = 0u;
}

static void clear_enemy_bullets(GameState* game)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game->enemy_bullets[i].active = 0u;
    }
}

static unsigned char enemy_fire_interval(unsigned char type)
{
    if (type == GAME_ENEMY_TYPE_SCOUT) {
        return ENEMY_SCOUT_FIRE_INTERVAL;
    }
    if (type == GAME_ENEMY_TYPE_SAUCER) {
        return ENEMY_SAUCER_FIRE_INTERVAL;
    }
    return ENEMY_DROPPER_FIRE_INTERVAL;
}

static unsigned char clamp_enemy_y(int y)
{
    int maximum;

    maximum = (int)(GAME_SCREEN_HEIGHT - GAME_ENEMY_HEIGHT);
    if (y < (int)GAME_HUD_HEIGHT) {
        return GAME_HUD_HEIGHT;
    }
    if (y > maximum) {
        return (unsigned char)maximum;
    }
    return (unsigned char)y;
}

static void configure_enemy(GameEnemy* enemy, unsigned char slot,
    unsigned char type, unsigned char pattern, unsigned char base_y)
{
    const EnemyMovementConfig* movement;
    unsigned char interval;

    enemy->active = 1u;
    enemy->type = type;
    enemy->pattern = pattern;
    enemy->base_y = base_y;
    enemy->move_counter = 0u;
    enemy->direction = ENEMY_DIRECTION_DOWN;
    movement = &enemy_movements[pattern];
    if (movement->behavior == GAME_ENEMY_PATTERN_WAVE) {
        enemy->phase = movement->vertical_amplitude;
    } else {
        enemy->phase = 0u;
    }
    enemy->rect.y = clamp_enemy_y(base_y);
    interval = enemy_fire_interval(type);
    enemy->fire_counter = (unsigned char)(((unsigned int)slot * 15u) % interval);
}

static void reset_enemy_formation(GameState* game)
{
    unsigned char i;

    game->respawn_sequence = 0u;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game->enemies[i].rect.x = initial_enemy_x[i];
        configure_enemy(&game->enemies[i], i,
            i == 3u ? GAME_ENEMY_TYPE_DROPPER :
                (unsigned char)(i % 2u),
            (unsigned char)(i % 3u), initial_enemy_y[i]);
    }
}

static void respawn_enemy(GameState* game, unsigned char slot)
{
    unsigned int seed;
    GameEnemy* enemy;

    game->respawn_sequence = (unsigned char)(game->respawn_sequence + 1u);
    seed = (unsigned int)game->respawn_sequence + slot;
    enemy = &game->enemies[slot];
    enemy->rect.x = (unsigned char)(180u + (unsigned int)slot * 16u);
    configure_enemy(enemy, slot,
        slot == 3u ? GAME_ENEMY_TYPE_DROPPER :
            (unsigned char)(seed % 2u),
        (unsigned char)(seed % 3u),
        (unsigned char)(ENEMY_MIN_Y + (seed * 17u) % ENEMY_Y_RANGE));
}

static void update_scrolling(GameState* game)
{
    ++game->planet_counter;
    if (game->planet_counter == GAME_PLANET_SCROLL_INTERVAL) {
        game->planet_counter = 0u;
        if (game->planet_offset == GAME_PLANET_SCROLL_PERIOD - 1u) {
            game->planet_offset = 0u;
        } else {
            ++game->planet_offset;
        }
    }

    ++game->far_star_counter;
    if (game->far_star_counter == FAR_STAR_INTERVAL) {
        game->far_star_counter = 0u;
        if (game->far_star_offset == GAME_SCREEN_WIDTH - 1u) {
            game->far_star_offset = 0u;
        } else {
            ++game->far_star_offset;
        }
    }

    ++game->near_star_counter;
    if (game->near_star_counter == NEAR_STAR_INTERVAL) {
        game->near_star_counter = 0u;
        if (game->near_star_offset == GAME_SCREEN_WIDTH - 1u) {
            game->near_star_offset = 0u;
        } else {
            ++game->near_star_offset;
        }
    }

    ++game->animation_counter;
    if (game->animation_counter == ANIMATION_INTERVAL) {
        game->animation_counter = 0u;
        game->animation_frame = (unsigned char)(1u - game->animation_frame);
    }
}

static void update_enemy_movement(GameEnemy* enemy)
{
    const EnemyMovementConfig* movement;
    int vertical_offset;
    unsigned char phase_limit;

    movement = &enemy_movements[enemy->pattern];
    if (enemy->rect.x >= movement->horizontal_speed) {
        enemy->rect.x = (unsigned char)(enemy->rect.x - movement->horizontal_speed);
    } else {
        enemy->rect.x = 0u;
    }

    if (movement->vertical_interval == 0u) {
        enemy->rect.y = clamp_enemy_y(enemy->base_y);
        return;
    }
    if (movement->behavior == GAME_ENEMY_PATTERN_WAVE) {
        phase_limit = (unsigned char)(movement->vertical_amplitude * 2u);
    } else {
        phase_limit = movement->vertical_amplitude;
    }

    ++enemy->move_counter;
    if (enemy->move_counter == movement->vertical_interval) {
        enemy->move_counter = 0u;
        if (enemy->direction == ENEMY_DIRECTION_DOWN) {
            if (enemy->phase < phase_limit) {
                ++enemy->phase;
            } else {
                enemy->direction = ENEMY_DIRECTION_UP;
                --enemy->phase;
            }
        } else if (enemy->phase != 0u) {
            --enemy->phase;
        } else {
            enemy->direction = ENEMY_DIRECTION_DOWN;
            ++enemy->phase;
        }
    }

    if (movement->behavior == GAME_ENEMY_PATTERN_WAVE) {
        vertical_offset = (int)enemy->phase -
            (int)movement->vertical_amplitude;
    } else {
        vertical_offset = (int)enemy->phase;
    }
    enemy->rect.y = clamp_enemy_y((int)enemy->base_y + vertical_offset);
}

static unsigned char fire_player_bullets(GameState* game)
{
    unsigned char i;
    unsigned char required;
    unsigned char available;
    unsigned char created;

    required = game->weapon_level;
    available = 0u;
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            ++available;
        }
    }
    if (available < required) {
        return 0u;
    }

    created = 0u;
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            game->bullets[i].active = 1u;
            game->bullets[i].rect.x =
                (unsigned char)(game->player.x + GAME_PLAYER_WIDTH);
            if (game->weapon_level == GAME_WEAPON_LEVEL_MIN) {
                game->bullets[i].rect.y =
                    (unsigned char)(game->player.y + 2u);
            } else {
                game->bullets[i].rect.y =
                    (unsigned char)(game->player.y + created * 2u);
                if (game->weapon_level == 2u && created != 0u) {
                    game->bullets[i].rect.y =
                        (unsigned char)(game->player.y + 4u);
                }
            }
            ++created;
            if (created == required) {
                return 1u;
            }
        }
    }
    return 0u;
}

static unsigned char spawn_power_item(GameState* game,
    const GameEnemy* enemy)
{
    unsigned int x;

    if (game->power_item.active != 0u) {
        return 0u;
    }
    x = (unsigned int)enemy->rect.x + 2u;
    if (x > GAME_SCREEN_WIDTH - GAME_POWER_ITEM_WIDTH) {
        x = GAME_SCREEN_WIDTH - GAME_POWER_ITEM_WIDTH;
    }
    game->power_item.rect.x = (unsigned char)x;
    game->power_item.rect.y = (unsigned char)(enemy->rect.y + 2u);
    game->power_item.active = 1u;
    game->power_item.move_counter = 0u;
    return 1u;
}

static void update_power_item(GameState* game)
{
    if (game->power_item.active == 0u) {
        return;
    }
    ++game->power_item.move_counter;
    if (game->power_item.move_counter == POWER_ITEM_MOVE_INTERVAL) {
        game->power_item.move_counter = 0u;
        if (game->power_item.rect.x == 0u) {
            game->power_item.active = 0u;
            return;
        }
        --game->power_item.rect.x;
    }
    if (game_aabb_intersects(&game->player,
        &game->power_item.rect) != 0u) {
        if (game->weapon_level < GAME_WEAPON_LEVEL_MAX) {
            ++game->weapon_level;
        }
        clear_power_item(game);
    }
}

static void fire_enemy_bullet(GameState* game, const GameEnemy* enemy)
{
    unsigned char i;

    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active == 0u) {
            game->enemy_bullets[i].active = 1u;
            if (enemy->rect.x > GAME_SCREEN_WIDTH - GAME_ENEMY_BULLET_WIDTH) {
                game->enemy_bullets[i].rect.x =
                    GAME_SCREEN_WIDTH - GAME_ENEMY_BULLET_WIDTH;
            } else {
                game->enemy_bullets[i].rect.x = enemy->rect.x;
            }
            game->enemy_bullets[i].rect.y =
                (unsigned char)(enemy->rect.y + 3u);
            return;
        }
    }
}

static void begin_player_death(GameState* game)
{
    if (game->lives != 0u) {
        --game->lives;
    }
    clear_player_bullets(game);
    game->dying = 1u;
    game->explosion_timer = 0u;
    game->invincibility_timer = 0u;
}

static void update_player_death(GameState* game)
{
    ++game->explosion_timer;
    if (game->explosion_timer != GAME_EXPLOSION_FRAMES) {
        return;
    }

    game->dying = 0u;
    game->explosion_timer = 0u;
    if (game->lives == 0u) {
        game->game_over = 1u;
        game->restart_armed = 0u;
        return;
    }

    game->player.x = 10u;
    game->player.y = 48u;
    clear_player_bullets(game);
    clear_enemy_bullets(game);
    clear_power_item(game);
    game->fire_cooldown = 0u;
    reset_enemy_formation(game);
    game->invincibility_timer = GAME_INVINCIBILITY_FRAMES;
}

void game_init(GameState* game)
{
    unsigned char i;

    game->player.x = 10u;
    game->player.y = 48u;
    game->player.width = GAME_PLAYER_WIDTH;
    game->player.height = GAME_PLAYER_HEIGHT;
    game->score = 0ul;
    game->fire_cooldown = 0u;
    game->weapon_level = GAME_WEAPON_LEVEL_MIN;
    game->respawn_sequence = 0u;
    game->lives = GAME_INITIAL_LIVES;
    game->game_over = 0u;
    game->restart_armed = 0u;
    game->dying = 0u;
    game->explosion_timer = 0u;
    game->invincibility_timer = 0u;
    game->planet_offset = 0u;
    game->planet_counter = 0u;
    game->far_star_offset = 0u;
    game->near_star_offset = 0u;
    game->far_star_counter = 0u;
    game->near_star_counter = 0u;
    game->animation_counter = 0u;
    game->animation_frame = 0u;

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game->enemies[i].rect.width = GAME_ENEMY_WIDTH;
        game->enemies[i].rect.height = GAME_ENEMY_HEIGHT;
    }
    reset_enemy_formation(game);
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        game->bullets[i].active = 0u;
        game->bullets[i].rect.x = 0u;
        game->bullets[i].rect.y = 0u;
        game->bullets[i].rect.width = GAME_PLAYER_BULLET_WIDTH;
        game->bullets[i].rect.height = GAME_PLAYER_BULLET_HEIGHT;
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game->enemy_bullets[i].active = 0u;
        game->enemy_bullets[i].rect.x = 0u;
        game->enemy_bullets[i].rect.y = 0u;
        game->enemy_bullets[i].rect.width = GAME_ENEMY_BULLET_WIDTH;
        game->enemy_bullets[i].rect.height = GAME_ENEMY_BULLET_HEIGHT;
    }
    game->power_item.rect.x = 0u;
    game->power_item.rect.y = 0u;
    game->power_item.rect.width = GAME_POWER_ITEM_WIDTH;
    game->power_item.rect.height = GAME_POWER_ITEM_HEIGHT;
    clear_power_item(game);
}

unsigned char game_aabb_intersects(const GameRect* a, const GameRect* b)
{
    return (unsigned char)(
        (unsigned int)a->x < (unsigned int)b->x + b->width &&
        (unsigned int)a->x + a->width > (unsigned int)b->x &&
        (unsigned int)a->y < (unsigned int)b->y + b->height &&
        (unsigned int)a->y + a->height > (unsigned int)b->y);
}

unsigned char game_player_is_visible(const GameState* game)
{
    unsigned char elapsed;

    if (game->invincibility_timer == 0u) {
        return 1u;
    }
    elapsed = (unsigned char)(GAME_INVINCIBILITY_FRAMES -
        game->invincibility_timer);
    return (unsigned char)(((elapsed / 4u) % 2u) == 0u);
}

void game_update(GameState* game, unsigned char input)
{
    unsigned char i;
    unsigned char j;
    unsigned char was_invincible;
    unsigned char damage;
    unsigned char power_item_created;
    unsigned char hit_enemies[GAME_MAX_ENEMIES];

    if (game->game_over != 0u) {
        if ((input & GAME_INPUT_FIRE) == 0u) {
            game->restart_armed = 1u;
        } else if (game->restart_armed != 0u) {
            game_init(game);
        }
        return;
    }
    if (game->dying != 0u) {
        update_player_death(game);
        return;
    }

    was_invincible = (unsigned char)(game->invincibility_timer != 0u);
    if (was_invincible != 0u) {
        --game->invincibility_timer;
    }
    update_scrolling(game);

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
        if (fire_player_bullets(game) != 0u) {
            game->fire_cooldown = FIRE_COOLDOWN_FRAMES;
        }
    }

    power_item_created = 0u;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        hit_enemies[i] = 0u;
    }
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        if (game->bullets[i].active == 0u) {
            continue;
        }
        if (game->bullets[i].rect.x >
            GAME_SCREEN_WIDTH - GAME_PLAYER_BULLET_WIDTH - BULLET_SPEED) {
            game->bullets[i].active = 0u;
            continue;
        }
        game->bullets[i].rect.x =
            (unsigned char)(game->bullets[i].rect.x + BULLET_SPEED);
        for (j = 0u; j < GAME_MAX_ENEMIES; ++j) {
            if (game->enemies[j].active != 0u &&
                game->enemies[j].rect.x < GAME_SCREEN_WIDTH &&
                hit_enemies[j] == 0u &&
                game_aabb_intersects(&game->bullets[i].rect,
                    &game->enemies[j].rect) != 0u) {
                game->bullets[i].active = 0u;
                game->score += 100ul;
                if (game->enemies[j].type == GAME_ENEMY_TYPE_DROPPER) {
                    power_item_created = spawn_power_item(game,
                        &game->enemies[j]);
                }
                respawn_enemy(game, j);
                hit_enemies[j] = 1u;
                break;
            }
        }
    }

    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active != 0u) {
            if (game->enemy_bullets[i].rect.x < ENEMY_BULLET_SPEED) {
                game->enemy_bullets[i].active = 0u;
            } else {
                game->enemy_bullets[i].rect.x = (unsigned char)(
                    game->enemy_bullets[i].rect.x - ENEMY_BULLET_SPEED);
            }
        }
    }

    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        GameEnemy* enemy;
        unsigned char interval;

        enemy = &game->enemies[i];
        if (enemy->active == 0u || hit_enemies[i] != 0u) {
            continue;
        }
        if (enemy->rect.x >= GAME_SCREEN_WIDTH) {
            --enemy->rect.x;
            continue;
        }
        update_enemy_movement(enemy);
        interval = enemy_fire_interval(enemy->type);
        ++enemy->fire_counter;
        if (enemy->fire_counter == interval) {
            enemy->fire_counter = 0u;
            fire_enemy_bullet(game, enemy);
        }
    }

    if (power_item_created == 0u) {
        update_power_item(game);
    }

    damage = 0u;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        if (game->enemies[i].active != 0u && hit_enemies[i] == 0u &&
            game->enemies[i].rect.x < GAME_SCREEN_WIDTH &&
            (game->enemies[i].rect.x == 0u ||
            game_aabb_intersects(&game->player,
                &game->enemies[i].rect) != 0u)) {
            damage = 1u;
        }
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        if (game->enemy_bullets[i].active != 0u &&
            game_aabb_intersects(&game->player,
                &game->enemy_bullets[i].rect) != 0u) {
            game->enemy_bullets[i].active = 0u;
            damage = 1u;
        }
    }
    if (damage != 0u) {
        if (was_invincible != 0u) {
            reset_enemy_formation(game);
            clear_enemy_bullets(game);
        } else {
            begin_player_death(game);
        }
    }
}
