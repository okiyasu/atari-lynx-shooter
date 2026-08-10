#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/time.h>

#include "game.h"

#define BENCH_DURATION_US 1000000ul
#define BENCH_DRAW_RATE 75ul
#define BENCH_REPREPARE_LOGIC_UPDATES 20ul

typedef struct BenchResult {
    unsigned long elapsed_us;
    unsigned long draw_frames;
    unsigned long logic_updates;
    unsigned long sound_ticks;
} BenchResult;

static unsigned long elapsed_us(const struct timeval* start,
    const struct timeval* end)
{
    long seconds;
    long microseconds;

    seconds = end->tv_sec - start->tv_sec;
    microseconds = end->tv_usec - start->tv_usec;
    if (microseconds < 0) {
        --seconds;
        microseconds += 1000000l;
    }
    return (unsigned long)seconds * 1000000ul +
        (unsigned long)microseconds;
}

static void sleep_until(const struct timeval* start, unsigned long target_us)
{
    struct timeval now;
    struct timeval timeout;
    unsigned long now_us;

    (void)gettimeofday(&now, (void*)0);
    now_us = elapsed_us(start, &now);
    if (now_us >= target_us) {
        return;
    }
    target_us -= now_us;
    timeout.tv_sec = (long)(target_us / 1000000ul);
    timeout.tv_usec = (long)(target_us % 1000000ul);
    (void)select(0, (void*)0, (void*)0, (void*)0, &timeout);
}

static void prepare_combat(GameState* game)
{
    unsigned char i;

    game_init(game);
    game_start(game);
    game->phase = GAME_PHASE_NORMAL;
    game->phase_timer = 0u;
    game->environment_event_cursor = GAME_ASTEROID_EVENT_COUNT;
    for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
        game_enemy_at(game, i)->active = 1u;
        game_enemy_at(game, i)->rect.x = (unsigned char)(120u + i * 4u);
        game_enemy_at(game, i)->rect.y = (unsigned char)(60u + i * 4u);
    }
    for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
        game->bullets[i].active = 1u;
        game->bullets[i].rect.x = 12u;
        game->bullets[i].rect.y = GAME_HUD_HEIGHT;
    }
    for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
        game->enemy_bullets[i].active = 1u;
        game->enemy_bullets[i].rect.x = (unsigned char)(130u + i);
        game->enemy_bullets[i].rect.y = 90u;
        game->enemy_bullets[i].velocity_x = (signed char)-2;
        game->enemy_bullets[i].velocity_y = 0;
    }
}

static void run_draw_frame(GameState* game, unsigned char* remainder,
    unsigned long* logic_since_prepare, BenchResult* result)
{
    unsigned char update;
    unsigned char updates;

    updates = game_logic_updates_for_draw_frame(remainder);
    for (update = 0u; update < updates; ++update) {
        if (*logic_since_prepare == BENCH_REPREPARE_LOGIC_UPDATES) {
            prepare_combat(game);
            *logic_since_prepare = 0ul;
        }
        game_update_logic(game, 0u);
        ++*logic_since_prepare;
        ++result->logic_updates;
    }
    game_sound_tick(game);
    ++result->sound_ticks;
    ++result->draw_frames;
}

static BenchResult run_timed(unsigned char synchronized)
{
    GameState game;
    BenchResult result;
    struct timeval start;
    struct timeval now;
    unsigned char remainder;
    unsigned long logic_since_prepare;

    result.elapsed_us = 0ul;
    result.draw_frames = 0ul;
    result.logic_updates = 0ul;
    result.sound_ticks = 0ul;
    remainder = 0u;
    logic_since_prepare = 0ul;
    prepare_combat(&game);
    game_perf_reset();
    (void)gettimeofday(&start, (void*)0);
    do {
        if (synchronized != 0u) {
            sleep_until(&start, (result.draw_frames + 1ul) *
                1000000ul / BENCH_DRAW_RATE);
        }
        run_draw_frame(&game, &remainder, &logic_since_prepare, &result);
        (void)gettimeofday(&now, (void*)0);
        result.elapsed_us = elapsed_us(&start, &now);
    } while (result.elapsed_us < BENCH_DURATION_US);
    return result;
}

static BenchResult run_workload(unsigned long frames)
{
    GameState game;
    BenchResult result;
    struct timeval start;
    struct timeval end;
    unsigned char remainder;
    unsigned long logic_since_prepare;

    result.elapsed_us = 0ul;
    result.draw_frames = 0ul;
    result.logic_updates = 0ul;
    result.sound_ticks = 0ul;
    remainder = 0u;
    logic_since_prepare = 0ul;
    prepare_combat(&game);
    game_perf_reset();
    (void)gettimeofday(&start, (void*)0);
    while (result.draw_frames < frames) {
        run_draw_frame(&game, &remainder, &logic_since_prepare, &result);
    }
    (void)gettimeofday(&end, (void*)0);
    result.elapsed_us = elapsed_us(&start, &end);
    return result;
}

static void print_result(const char* mode, const BenchResult* result)
{
    const GamePerfCounters* counters;
    double elapsed_seconds;
    double game_speed;

    counters = game_perf_get();
    elapsed_seconds = (double)result->elapsed_us / 1000000.0;
    game_speed = (double)result->logic_updates /
        (elapsed_seconds * (double)BENCH_DRAW_RATE *
            (double)GAME_LOGIC_UPDATES_NUMERATOR /
            (double)GAME_LOGIC_UPDATES_DENOMINATOR);
    printf("mode=%s elapsed_us=%lu draw_frames=%lu logic_updates=%lu ",
        mode, result->elapsed_us, result->draw_frames, result->logic_updates);
    printf("sound_ticks=%lu logic_hz=%.2f game_speed_x=%.2f\n",
        result->sound_ticks, (double)result->logic_updates / elapsed_seconds,
        game_speed);
    printf("hotpath normal_updates=%lu player_bullet_slots=%lu ",
        counters->normal_updates, counters->player_bullet_slots);
    printf("enemy_collision_slots=%lu enemy_bullet_slots=%lu ",
        counters->enemy_collision_slots, counters->enemy_bullet_slots);
    printf("normal_hit_flag_slots=%lu\n", counters->normal_hit_flag_slots);
}

int main(int argc, char** argv)
{
    BenchResult result;
    unsigned long frames;

    if (argc == 2 && strcmp(argv[1], "--sync") == 0) {
        result = run_timed(1u);
        print_result("sync", &result);
        return EXIT_SUCCESS;
    }
    if (argc == 2 && strcmp(argv[1], "--unthrottled") == 0) {
        result = run_timed(0u);
        print_result("unthrottled", &result);
        return EXIT_SUCCESS;
    }
    if (argc == 3 && strcmp(argv[1], "--workload") == 0) {
        frames = strtoul(argv[2], (char**)0, 10);
        if (frames == 0ul) {
            return EXIT_FAILURE;
        }
        result = run_workload(frames);
        print_result("workload", &result);
        return EXIT_SUCCESS;
    }
    fprintf(stderr, "usage: %s --sync|--unthrottled|--workload frames\n",
        argv[0]);
    return EXIT_FAILURE;
}
