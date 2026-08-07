#include <6502.h>
#include <joystick.h>
#include <lynx.h>
#include <tgi.h>

#include "game.h"

#define GAME_COLOR_BLACK 0u
#define GAME_COLOR_WHITE 15u
#define GAME_COLOR_PLANET_BODY 1u
#define GAME_COLOR_PLANET_DETAIL 3u
#define GAME_COLOR_FAR_STAR 2u
#define GAME_COLOR_NEAR_STAR 7u
#define GAME_COLOR_PLAYER 10u
#define GAME_COLOR_BULLET 14u
#define GAME_COLOR_ENEMY_BULLET 15u
#define GAME_COLOR_SCOUT 4u
#define GAME_COLOR_SAUCER 12u
#define GAME_COLOR_DROPPER 9u
#define GAME_COLOR_POWER_ITEM 11u
#define GAME_COLOR_EXPLOSION 14u
#define GAME_COLOR_BOSS 13u
#define GAME_COLOR_BOSS_DETAIL 5u
#define GAME_COLOR_SKY 8u
#define GAME_COLOR_MOUNTAIN 4u
#define GAME_COLOR_MID_CLOUD 7u
#define GAME_COLOR_NEAR_CLOUD 15u
#define GAME_COLOR_FIGHTER 14u
#define GAME_COLOR_BOMBER 6u
#define GAME_COLOR_SUPPLY 11u
#define GAME_COLOR_CAVE_WALL 1u
#define GAME_COLOR_CAVE_SHADOW 3u
#define GAME_COLOR_CAVE_ROCK 5u
#define GAME_COLOR_CAVE_NEAR 13u
#define GAME_COLOR_CAVE_BAT 12u
#define GAME_COLOR_ROCK_WORM 9u
#define GAME_COLOR_MINING_DRONE 14u
#define GAME_COLOR_ENVIRONMENT_BODY 5u
#define GAME_COLOR_ENVIRONMENT_DETAIL 13u
#define GAME_COLOR_WIND_WARNING 6u
#define GAME_COLOR_WIND_ACTIVE 14u
#define SCORE_DIGITS 5u

/* MIKEY audio channel register blocks (include/_mikey.h layout): eight
 * registers per channel starting at 0xFD20 (channel A) and 0xFD28
 * (channel B). Both channels share the same in-block offsets, so the
 * backend addresses them as base pointer plus offset (APS-021). */
#define SOUND_CHANNEL_A ((volatile unsigned char*)0xfd20u)
#define SOUND_CHANNEL_B ((volatile unsigned char*)0xfd28u)
#define SOUND_REG_VOL 0u
#define SOUND_REG_FEEDBACK 1u
#define SOUND_REG_SHIFT_LOW 3u
#define SOUND_REG_RELOAD 4u
#define SOUND_REG_CONTROL_A 5u
#define SOUND_REG_CONTROL_B 7u
#define SOUND_MASTER_STEREO (*(volatile unsigned char*)0xfd50u)
#define SOUND_TIMER_ENABLE 0x18u

typedef struct Star {
    unsigned char x;
    unsigned char y;
} Star;

typedef struct PlanetRun {
    unsigned char y;
    unsigned char x0;
    unsigned char x1;
    unsigned char palette_index;
} PlanetRun;

typedef struct BackgroundTheme {
    unsigned char background_color;
    unsigned char planet_colors[2];
    unsigned char far_star_color;
    unsigned char near_star_color;
} BackgroundTheme;

typedef struct BossRun {
    unsigned char y;
    unsigned char x0;
    unsigned char x1;
    unsigned char palette_index;
} BossRun;

typedef struct SkyRun {
    unsigned char y;
    unsigned char x0;
    unsigned char x1;
} SkyRun;

typedef struct CloudGroup {
    unsigned char x;
    unsigned char y;
} CloudGroup;

typedef struct SoundPitchRegister {
    unsigned char reload;
    unsigned char prescaler;
} SoundPitchRegister;

typedef struct SoundWaveRegister {
    unsigned char feedback;
    unsigned char shift_low;
    unsigned char control_b;
} SoundWaveRegister;

typedef struct SoundHardwareState {
    unsigned char active;
    unsigned char note;
    unsigned char volume;
    unsigned char wave;
} SoundHardwareState;

static const SoundPitchRegister sound_pitch_registers[SOUND_NOTE_COUNT] = {
    { 0xfau, 3u }, { 0xe7u, 3u }, { 0xd6u, 3u }, { 0xc6u, 3u },
    { 0xb8u, 3u }, { 0xacu, 3u }, { 0xa1u, 3u }, { 0x96u, 3u },
    { 0x8du, 3u }, { 0x84u, 3u }, { 0xfau, 2u }, { 0xebu, 2u },
    { 0xdeu, 2u }, { 0xd2u, 2u }, { 0xc7u, 2u }, { 0xbcu, 2u }
};

static const SoundWaveRegister sound_wave_registers[SOUND_WAVE_COUNT] = {
    { 0x3fu, 0xacu, 0u },
    { 0x36u, 0x5au, 0u },
    { 0x1fu, 0x7fu, 0u },
    { 0x24u, 0xb4u, 0u }
};

static SoundHardwareState sound_hardware_bgm;
static SoundHardwareState sound_hardware_sfx;
static GameState game;

static const BackgroundTheme background_themes[
    GAME_BACKGROUND_THEME_COUNT] = {
    { GAME_COLOR_BLACK,
        { GAME_COLOR_PLANET_BODY, GAME_COLOR_PLANET_DETAIL },
        GAME_COLOR_FAR_STAR, GAME_COLOR_NEAR_STAR },
    { GAME_COLOR_SKY,
        { GAME_COLOR_MOUNTAIN, GAME_COLOR_MOUNTAIN },
        GAME_COLOR_MID_CLOUD, GAME_COLOR_NEAR_CLOUD },
    { GAME_COLOR_CAVE_WALL,
        { GAME_COLOR_CAVE_SHADOW, GAME_COLOR_CAVE_SHADOW },
        GAME_COLOR_CAVE_ROCK, GAME_COLOR_CAVE_NEAR }
};

static const PlanetRun planet_runs[32] = {
    { 0u, 11u, 20u, 0u }, { 1u, 7u, 24u, 0u },
    { 2u, 5u, 26u, 0u }, { 3u, 3u, 28u, 0u },
    { 4u, 2u, 29u, 0u }, { 5u, 1u, 30u, 0u },
    { 6u, 0u, 31u, 0u }, { 7u, 0u, 31u, 0u },
    { 8u, 0u, 31u, 0u }, { 9u, 0u, 31u, 0u },
    { 10u, 0u, 31u, 0u }, { 11u, 0u, 31u, 0u },
    { 12u, 0u, 31u, 0u }, { 13u, 0u, 31u, 0u },
    { 14u, 0u, 31u, 0u }, { 15u, 0u, 31u, 0u },
    { 16u, 0u, 31u, 0u }, { 17u, 0u, 31u, 0u },
    { 18u, 1u, 30u, 0u }, { 19u, 2u, 29u, 0u },
    { 20u, 3u, 28u, 0u }, { 21u, 5u, 26u, 0u },
    { 22u, 7u, 24u, 0u }, { 23u, 11u, 20u, 0u },
    { 5u, 9u, 13u, 1u }, { 6u, 7u, 15u, 1u },
    { 7u, 7u, 15u, 1u }, { 8u, 9u, 13u, 1u },
    { 14u, 20u, 24u, 1u }, { 15u, 18u, 25u, 1u },
    { 16u, 19u, 25u, 1u }, { 17u, 21u, 23u, 1u }
};

#define SPACE_FORTRESS_RUN_COUNT 26u

static const BossRun space_fortress_runs[2][SPACE_FORTRESS_RUN_COUNT] = {
    {
        /* 24x16 hull: the left edge is the forward twin turret. */
        { 0u, 10u, 17u, 0u }, { 1u, 7u, 20u, 0u },
        { 2u, 5u, 22u, 0u }, { 3u, 4u, 23u, 0u },
        { 4u, 0u, 6u, 0u }, { 4u, 3u, 23u, 0u },
        { 5u, 2u, 21u, 0u }, { 6u, 3u, 23u, 0u },
        { 7u, 0u, 23u, 0u }, { 8u, 0u, 23u, 0u },
        { 9u, 3u, 23u, 0u }, { 10u, 2u, 21u, 0u },
        { 11u, 0u, 6u, 0u }, { 11u, 3u, 23u, 0u },
        { 12u, 4u, 23u, 0u }, { 13u, 5u, 22u, 0u },
        { 14u, 7u, 20u, 0u }, { 15u, 10u, 17u, 0u },
        /* Armor/core is central; the rightmost runs are rear engines. */
        { 3u, 16u, 20u, 1u }, { 6u, 10u, 14u, 1u },
        { 7u, 9u, 15u, 1u }, { 8u, 9u, 15u, 1u },
        { 9u, 10u, 14u, 1u }, { 12u, 16u, 20u, 1u },
        { 5u, 22u, 23u, 1u }, { 10u, 22u, 23u, 1u }
    },
    {
        /* Frame two keeps the hull and pulses core/engine detail. */
        { 0u, 10u, 17u, 0u }, { 1u, 7u, 20u, 0u },
        { 2u, 5u, 22u, 0u }, { 3u, 4u, 23u, 0u },
        { 4u, 0u, 6u, 0u }, { 4u, 3u, 23u, 0u },
        { 5u, 2u, 21u, 0u }, { 6u, 3u, 23u, 0u },
        { 7u, 0u, 23u, 0u }, { 8u, 0u, 23u, 0u },
        { 9u, 3u, 23u, 0u }, { 10u, 2u, 21u, 0u },
        { 11u, 0u, 6u, 0u }, { 11u, 3u, 23u, 0u },
        { 12u, 4u, 23u, 0u }, { 13u, 5u, 22u, 0u },
        { 14u, 7u, 20u, 0u }, { 15u, 10u, 17u, 0u },
        { 3u, 16u, 20u, 1u }, { 6u, 11u, 13u, 1u },
        { 7u, 10u, 14u, 1u }, { 8u, 10u, 14u, 1u },
        { 9u, 11u, 13u, 1u }, { 12u, 16u, 20u, 1u },
        { 6u, 22u, 23u, 1u }, { 9u, 22u, 23u, 1u }
    }
};

#define AIR_CARRIER_RUN_COUNT 27u

static const BossRun air_carrier_runs[2][AIR_CARRIER_RUN_COUNT] = {
    {
        /* Flat deck and left-facing bow with upper/middle/lower guns. */
        { 0u, 8u, 23u, 0u }, { 1u, 5u, 26u, 0u },
        { 2u, 0u, 7u, 1u }, { 2u, 3u, 27u, 0u },
        { 3u, 4u, 26u, 0u }, { 4u, 6u, 25u, 0u },
        { 5u, 5u, 26u, 0u }, { 6u, 0u, 7u, 1u },
        { 6u, 3u, 27u, 0u }, { 7u, 0u, 7u, 1u },
        { 7u, 2u, 27u, 0u }, { 8u, 4u, 27u, 0u },
        { 9u, 5u, 26u, 0u }, { 10u, 0u, 7u, 1u },
        { 10u, 3u, 27u, 0u }, { 11u, 6u, 25u, 0u },
        { 12u, 8u, 23u, 0u }, { 13u, 11u, 20u, 0u },
        /* Central hull windows and twin rear engines. */
        { 3u, 12u, 18u, 1u }, { 5u, 10u, 12u, 1u },
        { 5u, 16u, 18u, 1u }, { 8u, 10u, 18u, 1u },
        { 11u, 12u, 18u, 1u }, { 3u, 25u, 27u, 1u },
        { 5u, 26u, 27u, 1u }, { 9u, 26u, 27u, 1u },
        { 11u, 25u, 27u, 1u }
    },
    {
        { 0u, 8u, 23u, 0u }, { 1u, 5u, 26u, 0u },
        { 2u, 0u, 7u, 1u }, { 2u, 3u, 27u, 0u },
        { 3u, 4u, 26u, 0u }, { 4u, 6u, 25u, 0u },
        { 5u, 5u, 26u, 0u }, { 6u, 0u, 7u, 1u },
        { 6u, 3u, 27u, 0u }, { 7u, 0u, 7u, 1u },
        { 7u, 2u, 27u, 0u }, { 8u, 4u, 27u, 0u },
        { 9u, 5u, 26u, 0u }, { 10u, 0u, 7u, 1u },
        { 10u, 3u, 27u, 0u }, { 11u, 6u, 25u, 0u },
        { 12u, 8u, 23u, 0u }, { 13u, 11u, 20u, 0u },
        { 3u, 13u, 17u, 1u }, { 5u, 11u, 13u, 1u },
        { 5u, 15u, 17u, 1u }, { 8u, 11u, 17u, 1u },
        { 11u, 13u, 17u, 1u }, { 4u, 25u, 27u, 1u },
        { 6u, 26u, 27u, 1u }, { 8u, 26u, 27u, 1u },
        { 10u, 25u, 27u, 1u }
    }
};

#define ROCK_GUARDIAN_RUN_COUNT 36u

static const BossRun rock_guardian_runs[2][ROCK_GUARDIAN_RUN_COUNT] = {
    {
        /* Jagged 24x24 shell with upper/lower fangs around the muzzle. */
        { 0u, 9u, 14u, 0u }, { 1u, 6u, 17u, 0u },
        { 2u, 4u, 19u, 0u }, { 3u, 2u, 21u, 0u },
        { 4u, 3u, 22u, 0u }, { 5u, 1u, 23u, 0u },
        { 6u, 0u, 22u, 0u }, { 7u, 2u, 23u, 0u },
        { 8u, 1u, 23u, 0u }, { 9u, 0u, 23u, 0u },
        { 10u, 2u, 23u, 0u }, { 11u, 0u, 23u, 0u },
        { 12u, 0u, 23u, 0u }, { 13u, 2u, 23u, 0u },
        { 14u, 0u, 23u, 0u }, { 15u, 1u, 23u, 0u },
        { 16u, 2u, 23u, 0u }, { 17u, 0u, 22u, 0u },
        { 18u, 1u, 23u, 0u }, { 19u, 3u, 22u, 0u },
        { 20u, 2u, 21u, 0u }, { 21u, 4u, 19u, 0u },
        { 22u, 6u, 17u, 0u }, { 23u, 9u, 14u, 0u },
        { 3u, 0u, 2u, 1u }, { 4u, 0u, 1u, 1u },
        { 19u, 0u, 1u, 1u }, { 20u, 0u, 2u, 1u },
        { 7u, 7u, 16u, 1u }, { 8u, 6u, 17u, 1u },
        { 9u, 5u, 18u, 1u }, { 10u, 5u, 18u, 1u },
        { 11u, 4u, 19u, 1u }, { 12u, 4u, 19u, 1u },
        { 13u, 5u, 18u, 1u }, { 14u, 6u, 17u, 1u }
    },
    {
        { 0u, 9u, 14u, 0u }, { 1u, 6u, 17u, 0u },
        { 2u, 4u, 19u, 0u }, { 3u, 2u, 21u, 0u },
        { 4u, 3u, 22u, 0u }, { 5u, 1u, 23u, 0u },
        { 6u, 0u, 22u, 0u }, { 7u, 2u, 23u, 0u },
        { 8u, 1u, 23u, 0u }, { 9u, 0u, 23u, 0u },
        { 10u, 2u, 23u, 0u }, { 11u, 0u, 23u, 0u },
        { 12u, 0u, 23u, 0u }, { 13u, 2u, 23u, 0u },
        { 14u, 0u, 23u, 0u }, { 15u, 1u, 23u, 0u },
        { 16u, 2u, 23u, 0u }, { 17u, 0u, 22u, 0u },
        { 18u, 1u, 23u, 0u }, { 19u, 3u, 22u, 0u },
        { 20u, 2u, 21u, 0u }, { 21u, 4u, 19u, 0u },
        { 22u, 6u, 17u, 0u }, { 23u, 9u, 14u, 0u },
        { 2u, 0u, 3u, 1u }, { 3u, 0u, 1u, 1u },
        { 20u, 0u, 1u, 1u }, { 21u, 0u, 3u, 1u },
        { 8u, 8u, 15u, 1u }, { 9u, 7u, 16u, 1u },
        { 10u, 6u, 17u, 1u }, { 11u, 5u, 18u, 1u },
        { 12u, 5u, 18u, 1u }, { 13u, 6u, 17u, 1u },
        { 14u, 7u, 16u, 1u }, { 15u, 8u, 15u, 1u }
    }
};

/* SKY far layer: fixed 192-pixel mountain/horizon horizontal runs. */
static const SkyRun mountain_runs[31] = {
    { 58u, 14u, 18u }, { 59u, 13u, 19u }, { 60u, 12u, 20u },
    { 61u, 11u, 21u }, { 62u, 10u, 23u }, { 63u, 9u, 25u },
    { 64u, 8u, 27u }, { 65u, 7u, 29u }, { 66u, 6u, 31u },
    { 63u, 63u, 67u }, { 64u, 61u, 69u }, { 65u, 59u, 71u },
    { 66u, 57u, 73u }, { 67u, 54u, 76u }, { 68u, 50u, 80u },
    { 60u, 118u, 122u }, { 61u, 116u, 124u },
    { 62u, 114u, 126u }, { 63u, 112u, 128u },
    { 64u, 109u, 131u }, { 65u, 106u, 134u },
    { 66u, 102u, 138u },
    { 70u, 0u, 191u }, { 71u, 0u, 191u },
    { 72u, 0u, 191u }, { 73u, 0u, 191u },
    { 74u, 0u, 191u }, { 75u, 0u, 191u },
    { 76u, 0u, 191u }, { 77u, 0u, 191u },
    { 78u, 0u, 191u }
};

static const CloudGroup mid_clouds[8] = {
    { 4u, 22u }, { 25u, 47u }, { 47u, 31u }, { 68u, 57u },
    { 89u, 18u }, { 109u, 42u }, { 130u, 28u }, { 150u, 53u }
};

static const CloudGroup near_clouds[5] = {
    { 8u, 72u }, { 41u, 82u }, { 75u, 68u },
    { 108u, 87u }, { 141u, 76u }
};

static const SkyRun mid_cloud_shape[5] = {
    { 0u, 3u, 7u }, { 1u, 1u, 10u }, { 2u, 0u, 12u },
    { 3u, 2u, 11u }, { 4u, 4u, 9u }
};

static const SkyRun near_cloud_shape[7] = {
    { 0u, 5u, 12u }, { 1u, 2u, 15u }, { 2u, 0u, 18u },
    { 3u, 0u, 20u }, { 4u, 1u, 19u }, { 5u, 3u, 17u },
    { 6u, 6u, 14u }
};

/* CAVE layers: 192px wall cracks, 160px rock skin and near formations. */
static const SkyRun cave_wall_runs[18] = {
    { 24u, 8u, 20u }, { 25u, 17u, 22u }, { 26u, 21u, 24u },
    { 47u, 52u, 65u }, { 48u, 50u, 55u }, { 49u, 48u, 52u },
    { 68u, 92u, 108u }, { 69u, 105u, 111u }, { 70u, 109u, 114u },
    { 31u, 137u, 151u }, { 32u, 134u, 140u },
    { 33u, 132u, 136u }, { 82u, 166u, 184u },
    { 83u, 163u, 170u }, { 84u, 160u, 165u },
    { 57u, 116u, 121u }, { 58u, 118u, 125u },
    { 59u, 123u, 129u }
};

static const SkyRun cave_rock_runs[22] = {
    { 10u, 0u, 159u }, { 11u, 0u, 159u }, { 12u, 0u, 159u },
    { 13u, 0u, 28u }, { 13u, 36u, 75u }, { 13u, 84u, 121u },
    { 13u, 130u, 159u }, { 14u, 0u, 18u }, { 14u, 45u, 64u },
    { 14u, 94u, 111u }, { 14u, 141u, 159u },
    { 98u, 0u, 159u }, { 97u, 0u, 159u }, { 96u, 0u, 159u },
    { 95u, 0u, 24u }, { 95u, 34u, 70u }, { 95u, 79u, 116u },
    { 95u, 126u, 159u }, { 94u, 0u, 14u }, { 94u, 43u, 61u },
    { 94u, 89u, 107u }, { 94u, 137u, 159u }
};

static const SkyRun cave_near_runs[26] = {
    { 15u, 11u, 22u }, { 16u, 13u, 20u }, { 17u, 15u, 19u },
    { 18u, 16u, 18u }, { 19u, 17u, 17u },
    { 15u, 59u, 71u }, { 16u, 61u, 69u }, { 17u, 63u, 68u },
    { 18u, 65u, 67u }, { 19u, 66u, 66u },
    { 15u, 120u, 133u }, { 16u, 122u, 131u },
    { 17u, 124u, 129u }, { 18u, 126u, 128u },
    { 19u, 127u, 127u }, { 93u, 30u, 42u },
    { 92u, 32u, 40u }, { 91u, 34u, 38u }, { 90u, 35u, 37u },
    { 89u, 36u, 36u }, { 93u, 84u, 97u }, { 92u, 86u, 95u },
    { 91u, 88u, 93u }, { 90u, 90u, 92u }, { 89u, 91u, 91u },
    { 93u, 145u, 159u }
};

static const Star far_stars[10] = {
    { 4u, 17u }, { 19u, 72u }, { 37u, 31u }, { 55u, 90u },
    { 74u, 52u }, { 91u, 14u }, { 108u, 81u }, { 127u, 39u },
    { 143u, 65u }, { 155u, 24u }
};

static const Star near_stars[7] = {
    { 11u, 42u }, { 33u, 84u }, { 58u, 20u }, { 82u, 62u },
    { 106u, 95u }, { 132u, 29u }, { 151u, 74u }
};

static const unsigned char player_masks[2][GAME_PLAYER_HEIGHT] = {
    { 0x18u, 0x3cu, 0xfeu, 0xffu, 0xfeu, 0x24u },
    { 0x18u, 0x7cu, 0xfeu, 0xffu, 0xfeu, 0x42u }
};

static const unsigned char enemy_masks[GAME_ENEMY_TYPE_COUNT][2]
    [GAME_ENEMY_HEIGHT] = {
    {
        /* SCOUT: pointed interceptor with a blinking tail fin. */
        { 0x10u, 0x38u, 0x7cu, 0xfeu, 0xffu, 0x7cu, 0x24u, 0x42u },
        { 0x08u, 0x1cu, 0x7eu, 0xffu, 0xfeu, 0x3eu, 0x24u, 0x81u }
    },
    {
        /* SAUCER: flat rim, dome and alternating landing lights. */
        { 0x18u, 0x3cu, 0x7eu, 0xffu, 0xffu, 0x7eu, 0x42u, 0x00u },
        { 0x18u, 0x7eu, 0xffu, 0xffu, 0x7eu, 0x3cu, 0x81u, 0x00u }
    },
    {
        /* DROPPER: cargo pod with opening lower hatch. */
        { 0x3cu, 0x7eu, 0xffu, 0xdbu, 0xdbu, 0xffu, 0x3cu, 0x18u },
        { 0x3cu, 0x7eu, 0xffu, 0xbdu, 0xffu, 0x5au, 0x3cu, 0x24u }
    },
    {
        /* FIGHTER: narrow nose and swept wings. */
        { 0x80u, 0xc0u, 0xf0u, 0xfeu, 0xffu, 0x7cu, 0x18u, 0x10u },
        { 0x80u, 0xe0u, 0xf8u, 0xffu, 0xfeu, 0x38u, 0x18u, 0x08u }
    },
    {
        /* BOMBER: broad twin-engine wing. */
        { 0x24u, 0x66u, 0x7eu, 0xffu, 0xffu, 0x7eu, 0x66u, 0x24u },
        { 0x42u, 0x66u, 0xffu, 0xffu, 0x7eu, 0x7eu, 0x66u, 0x42u }
    },
    {
        /* SUPPLY: box fuselage and straight transport wing. */
        { 0x3cu, 0x3cu, 0xffu, 0xffu, 0x7eu, 0x3cu, 0x24u, 0x24u },
        { 0x3cu, 0x7eu, 0xffu, 0xffu, 0x3cu, 0x3cu, 0x42u, 0x42u }
    },
    {
        /* CAVE_BAT: broad flapping wings around a narrow body. */
        { 0x81u, 0xc3u, 0x7eu, 0x3cu, 0x18u, 0x3cu, 0x24u, 0x42u },
        { 0x18u, 0x5au, 0xffu, 0x7eu, 0x18u, 0x3cu, 0x42u, 0x81u }
    },
    {
        /* ROCK_WORM: offset armored segments and a distinct head. */
        { 0xc0u, 0xf0u, 0x7cu, 0x3eu, 0x1fu, 0x0eu, 0x1cu, 0x38u },
        { 0x60u, 0xf8u, 0x7cu, 0x3eu, 0x1fu, 0x0eu, 0x1cu, 0x70u }
    },
    {
        /* MINING_DRONE: box chassis, lamp and animated drill. */
        { 0x18u, 0x7eu, 0xffu, 0xdbu, 0xffu, 0x7eu, 0x18u, 0x24u },
        { 0x18u, 0x7eu, 0xffu, 0xdbu, 0xffu, 0x7eu, 0x24u, 0x18u }
    }
};

static const unsigned char power_item_mask[GAME_POWER_ITEM_HEIGHT] = {
    0x60u, 0xf0u, 0xf0u, 0x60u
};

static const unsigned char explosion_masks[GAME_EXPLOSION_STAGES][8] = {
    { 0x00u, 0x00u, 0x18u, 0x3cu, 0x3cu, 0x18u, 0x00u, 0x00u },
    { 0x00u, 0x24u, 0x18u, 0x7eu, 0x7eu, 0x18u, 0x24u, 0x00u },
    { 0x81u, 0x24u, 0x5au, 0x3cu, 0x3cu, 0x5au, 0x24u, 0x81u },
    { 0x42u, 0x81u, 0x24u, 0x00u, 0x00u, 0x24u, 0x81u, 0x42u }
};

static const unsigned char asteroid_masks[2][8] = {
    { 0x18u, 0x7cu, 0xfeu, 0xdbu, 0xffu, 0x7eu, 0x3cu, 0x18u },
    { 0x1cu, 0x7eu, 0xffu, 0xbdu, 0x7fu, 0x3eu, 0x1cu, 0x08u }
};

static const unsigned char falling_rock_masks[2][8] = {
    { 0x18u, 0x3cu, 0x7eu, 0xffu, 0xdbu, 0x7eu, 0x3cu, 0x18u },
    { 0x0cu, 0x3eu, 0x7fu, 0xffu, 0xbdu, 0x7eu, 0x38u, 0x10u }
};

static void sound_backend_silence_channel(volatile unsigned char* channel,
    SoundHardwareState* hardware, unsigned char write_registers)
{
    if (write_registers != 0u) {
        channel[SOUND_REG_VOL] = 0u;
        channel[SOUND_REG_CONTROL_A] = 0u;
    }
    hardware->active = 0u;
    hardware->note = SOUND_NOTE_REST;
    hardware->volume = 0u;
    hardware->wave = SOUND_WAVE_TONE;
}

static void sound_backend_init(void)
{
    SOUND_MASTER_STEREO = 0u;
    sound_backend_silence_channel(SOUND_CHANNEL_A, &sound_hardware_bgm, 1u);
    sound_backend_silence_channel(SOUND_CHANNEL_B, &sound_hardware_sfx, 1u);
}

/* Applies one logical channel output to one MIKEY channel. Shared by
 * BGM (channel A) and SFX (channel B) since APS-021: the previous
 * per-channel duplicates used the same register offsets and the same
 * APS-013 write ordering (control=0, shift-low, control-B, feedback,
 * volume, reload, control=prescaler|enable; volume-only rewrite when
 * just the volume changes), which this helper preserves verbatim. */
static void sound_backend_apply(volatile unsigned char* channel,
    SoundHardwareState* hardware, const SoundOutput* output)
{
    const SoundPitchRegister* pitch;
    const SoundWaveRegister* wave;

    if (output->active == 0u || output->note == SOUND_NOTE_REST ||
        output->note > SOUND_NOTE_COUNT ||
        output->wave >= SOUND_WAVE_COUNT) {
        sound_backend_silence_channel(channel, hardware, hardware->active);
        return;
    }

    pitch = &sound_pitch_registers[output->note - 1u];
    wave = &sound_wave_registers[output->wave];
    if (hardware->active == 0u ||
        output->note != hardware->note ||
        output->wave != hardware->wave) {
        channel[SOUND_REG_CONTROL_A] = 0u;
        channel[SOUND_REG_SHIFT_LOW] = wave->shift_low;
        channel[SOUND_REG_CONTROL_B] = wave->control_b;
        channel[SOUND_REG_FEEDBACK] = wave->feedback;
        channel[SOUND_REG_VOL] = output->volume;
        channel[SOUND_REG_RELOAD] = pitch->reload;
        channel[SOUND_REG_CONTROL_A] =
            (unsigned char)(pitch->prescaler | SOUND_TIMER_ENABLE);
    } else if (output->volume != hardware->volume) {
        channel[SOUND_REG_VOL] = output->volume;
    }
    hardware->active = 1u;
    hardware->note = output->note;
    hardware->volume = output->volume;
    hardware->wave = output->wave;
}

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
    unsigned int y0;
    unsigned int y1;

    y0 = rect->y;
    y1 = (unsigned int)rect->y + rect->height - 1u;
    if (y1 < GAME_HUD_HEIGHT) {
        return;
    }
    if (y0 < GAME_HUD_HEIGHT) {
        y0 = GAME_HUD_HEIGHT;
    }
    if (y0 >= GAME_SCREEN_HEIGHT) {
        return;
    }
    tgi_setcolor(color);
    tgi_bar(rect->x, y0,
        (unsigned int)rect->x + rect->width - 1u,
        y1);
}

static unsigned char scroll_x(unsigned char x, unsigned char offset)
{
    if (x >= offset) {
        return (unsigned char)(x - offset);
    }
    return (unsigned char)(GAME_SCREEN_WIDTH - (offset - x));
}

/* Screen-clipped one-pixel-high horizontal run. Shared clipping core
 * for planet, sky/cave and boss run drawing (APS-021): those callers
 * previously repeated the same clamp-and-bar sequence. */
static void draw_clipped_hline(int x0, int x1, int y, unsigned char color)
{
    if (y < 0 || y >= (int)GAME_SCREEN_HEIGHT || x1 < 0 ||
        x0 >= (int)GAME_SCREEN_WIDTH) {
        return;
    }
    if (x0 < 0) {
        x0 = 0;
    }
    if (x1 >= (int)GAME_SCREEN_WIDTH) {
        x1 = (int)GAME_SCREEN_WIDTH - 1;
    }
    tgi_setcolor(color);
    tgi_bar((unsigned int)x0, (unsigned int)y,
        (unsigned int)x1, (unsigned int)y);
}

static void draw_planet(const GameState* game,
    const BackgroundTheme* theme)
{
    unsigned char i;
    int draw_x;
    int draw_y;

    draw_x = (int)GAME_PLANET_BASE_X - (int)game->planet_offset;
    if (draw_x < -(int)GAME_PLANET_WIDTH) {
        draw_x += (int)GAME_PLANET_SCROLL_PERIOD;
    }
    for (i = 0u; i < 32u; ++i) {
        draw_y = (int)GAME_PLANET_BASE_Y + (int)planet_runs[i].y;
        if (draw_y < (int)GAME_HUD_HEIGHT) {
            continue;
        }
        draw_clipped_hline(draw_x + (int)planet_runs[i].x0,
            draw_x + (int)planet_runs[i].x1, draw_y,
            theme->planet_colors[planet_runs[i].palette_index]);
    }
}

static void draw_background(const GameState* game,
    const BackgroundTheme* theme)
{
    unsigned char i;
    unsigned char x;
    unsigned int x1;

    tgi_setcolor(theme->far_star_color);
    for (i = 0u; i < 10u; ++i) {
        x = scroll_x(far_stars[i].x, game->far_star_offset);
        tgi_bar(x, far_stars[i].y, x, far_stars[i].y);
    }

    tgi_setcolor(theme->near_star_color);
    for (i = 0u; i < 7u; ++i) {
        x = scroll_x(near_stars[i].x, game->near_star_offset);
        x1 = (unsigned int)x + 1u;
        if (x1 >= GAME_SCREEN_WIDTH) {
            x1 = GAME_SCREEN_WIDTH - 1u;
        }
        tgi_bar(x, near_stars[i].y, x1, near_stars[i].y);
    }
}

static void draw_sky_run(int base_x, int base_y, const SkyRun* run,
    unsigned char color)
{
    draw_clipped_hline(base_x + (int)run->x0, base_x + (int)run->x1,
        base_y + (int)run->y, color);
}

static void draw_mountains(const GameState* game,
    const BackgroundTheme* theme)
{
    unsigned char i;
    int base_x;

    base_x = -(int)game->planet_offset;
    for (i = 0u; i < 31u; ++i) {
        draw_sky_run(base_x, 0, &mountain_runs[i],
            theme->planet_colors[0]);
        draw_sky_run(base_x + (int)GAME_PLANET_SCROLL_PERIOD, 0,
            &mountain_runs[i], theme->planet_colors[0]);
    }
}

static void draw_cloud_groups(const CloudGroup* groups,
    unsigned char group_count, const SkyRun* shape,
    unsigned char run_count, unsigned char offset, unsigned char color)
{
    unsigned char group;
    unsigned char run;
    int base_x;
    int base_y;

    for (group = 0u; group < group_count; ++group) {
        base_x = (int)scroll_x(groups[group].x, offset);
        base_y = groups[group].y;
        for (run = 0u; run < run_count; ++run) {
            draw_sky_run(base_x, base_y, &shape[run], color);
            draw_sky_run(base_x - (int)GAME_SCREEN_WIDTH, base_y,
                &shape[run], color);
        }
    }
}

static void draw_sky_background(const GameState* game,
    const BackgroundTheme* theme)
{
    draw_mountains(game, theme);
    draw_cloud_groups(mid_clouds, 8u, mid_cloud_shape, 5u,
        game->far_star_offset, theme->far_star_color);
    draw_cloud_groups(near_clouds, 5u, near_cloud_shape, 7u,
        game->near_star_offset, theme->near_star_color);
}

static void draw_periodic_runs(const SkyRun* runs,
    unsigned char run_count, unsigned int period, unsigned char offset,
    unsigned char color)
{
    unsigned char i;
    int base_x;

    base_x = -(int)offset;
    for (i = 0u; i < run_count; ++i) {
        draw_sky_run(base_x, 0, &runs[i], color);
        draw_sky_run(base_x + (int)period, 0, &runs[i], color);
    }
}

static void draw_cave_background(const GameState* game,
    const BackgroundTheme* theme)
{
    draw_periodic_runs(cave_wall_runs, 18u,
        GAME_PLANET_SCROLL_PERIOD, game->planet_offset,
        theme->planet_colors[0]);
    draw_periodic_runs(cave_rock_runs, 22u, GAME_SCREEN_WIDTH,
        game->far_star_offset, theme->far_star_color);
    draw_periodic_runs(cave_near_runs, 26u, GAME_SCREEN_WIDTH,
        game->near_star_offset, theme->near_star_color);
}

static void draw_mask(int x, int y,
    unsigned char width, unsigned char height,
    const unsigned char* rows, unsigned char color)
{
    unsigned char row;
    unsigned char column;
    unsigned char run_start;
    unsigned char mask;
    int draw_y;
    int x0;
    int x1;

    tgi_setcolor(color);
    for (row = 0u; row < height; ++row) {
        draw_y = y + row;
        if (draw_y < 0 || draw_y >= (int)GAME_SCREEN_HEIGHT) {
            continue;
        }
        column = 0u;
        while (column < width) {
            mask = (unsigned char)(0x80u >> column);
            if ((rows[row] & mask) == 0u) {
                ++column;
                continue;
            }
            run_start = column;
            do {
                ++column;
                if (column == width) {
                    break;
                }
                mask = (unsigned char)(0x80u >> column);
            } while ((rows[row] & mask) != 0u);

            x0 = x + run_start;
            x1 = x + column - 1u;
            if (x1 >= 0 && x0 < (int)GAME_SCREEN_WIDTH) {
                if (x0 < 0) {
                    x0 = 0;
                }
                if (x1 >= (int)GAME_SCREEN_WIDTH) {
                    x1 = (int)GAME_SCREEN_WIDTH - 1;
                }
                tgi_bar((unsigned int)x0, (unsigned int)draw_y,
                    (unsigned int)x1, (unsigned int)draw_y);
            }
        }
    }
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

static void draw_clipped_boss_run(const GameBoss* boss,
    const BossRun* run)
{
    draw_clipped_hline((int)boss->rect.x + (int)run->x0,
        (int)boss->rect.x + (int)run->x1,
        (int)boss->rect.y + (int)run->y,
        run->palette_index == 0u ?
            GAME_COLOR_BOSS : GAME_COLOR_BOSS_DETAIL);
}

static void draw_common_boss(const GameBoss* boss)
{
    unsigned int x0;
    unsigned int x1;
    unsigned int y0;
    unsigned int y1;

    x0 = boss->rect.x;
    x1 = (unsigned int)boss->rect.x + boss->rect.width - 1u;
    y0 = boss->rect.y;
    y1 = (unsigned int)boss->rect.y + boss->rect.height - 1u;
    tgi_setcolor(GAME_COLOR_BOSS);
    tgi_bar(x0 + 4u, y0, x1 - 4u, y0 + 2u);
    tgi_bar(x0 + 2u, y0 + 3u, x1 - 2u, y1 - 3u);
    tgi_bar(x0 + 4u, y1 - 2u, x1 - 4u, y1);
    tgi_setcolor(GAME_COLOR_BOSS_DETAIL);
    tgi_bar(x0, y0 + 5u, x0 + 5u, y0 + 7u);
    tgi_bar(x0 + 7u, y0 + 5u, x1 - 5u, y0 + 7u);
    tgi_bar(x1 - 3u, y0 + 2u, x1, y1 - 2u);
}

/* Two-frame run-sprite table for the named boss appearances (APS-021):
 * replaces one identical draw function per appearance. Index is
 * appearance_id - 1 (COMMON has no run sprite). */
typedef struct BossSprite {
    const BossRun* frames[2];
    unsigned char run_count;
} BossSprite;

static const BossSprite boss_sprites[GAME_BOSS_APPEARANCE_COUNT - 1u] = {
    { { space_fortress_runs[0], space_fortress_runs[1] },
        SPACE_FORTRESS_RUN_COUNT },
    { { air_carrier_runs[0], air_carrier_runs[1] },
        AIR_CARRIER_RUN_COUNT },
    { { rock_guardian_runs[0], rock_guardian_runs[1] },
        ROCK_GUARDIAN_RUN_COUNT }
};

static void draw_boss(const GameBoss* boss, unsigned char animation_frame)
{
    const BossSprite* sprite;
    const BossRun* runs;
    unsigned char i;

    if (boss->appearance_id == GAME_BOSS_APPEARANCE_COMMON ||
        boss->appearance_id >= GAME_BOSS_APPEARANCE_COUNT) {
        draw_common_boss(boss);
        return;
    }
    sprite = &boss_sprites[boss->appearance_id - 1u];
    runs = sprite->frames[animation_frame];
    for (i = 0u; i < sprite->run_count; ++i) {
        draw_clipped_boss_run(boss, &runs[i]);
    }
}

static unsigned char enemy_color(unsigned char type)
{
    static const unsigned char colors[GAME_ENEMY_TYPE_COUNT] = {
        GAME_COLOR_SCOUT, GAME_COLOR_SAUCER, GAME_COLOR_DROPPER,
        GAME_COLOR_FIGHTER, GAME_COLOR_BOMBER, GAME_COLOR_SUPPLY,
        GAME_COLOR_CAVE_BAT, GAME_COLOR_ROCK_WORM,
        GAME_COLOR_MINING_DRONE
    };

    return colors[type];
}

static unsigned char tiny_glyph_row(char glyph, unsigned char row)
{
    static const unsigned char digits[10][5] = {
        { 7u, 5u, 5u, 5u, 7u }, { 2u, 6u, 2u, 2u, 7u },
        { 7u, 1u, 7u, 4u, 7u }, { 7u, 1u, 7u, 1u, 7u },
        { 5u, 5u, 7u, 1u, 1u }, { 7u, 4u, 7u, 1u, 7u },
        { 7u, 4u, 7u, 5u, 7u }, { 7u, 1u, 2u, 2u, 2u },
        { 7u, 5u, 7u, 5u, 7u }, { 7u, 5u, 7u, 1u, 7u }
    };
    static const unsigned char letters[8][5] = {
        { 7u, 4u, 7u, 1u, 7u }, /* S */
        { 7u, 2u, 2u, 2u, 7u }, /* I */
        { 5u, 7u, 7u, 7u, 5u }, /* N */
        { 5u, 5u, 5u, 7u, 2u }, /* W */
        { 6u, 5u, 6u, 5u, 6u }, /* B */
        { 7u, 4u, 4u, 4u, 7u }, /* C */
        { 2u, 5u, 7u, 5u, 5u }, /* A */
        { 4u, 4u, 4u, 4u, 7u }  /* L */
    };

    if (glyph >= '0' && glyph <= '9') {
        return digits[(unsigned char)(glyph - '0')][row];
    }
    if (glyph == 'S') return letters[0][row];
    if (glyph == 'I') return letters[1][row];
    if (glyph == 'N') return letters[2][row];
    if (glyph == 'W') return letters[3][row];
    if (glyph == 'B') return letters[4][row];
    if (glyph == 'C') return letters[5][row];
    if (glyph == 'A') return letters[6][row];
    if (glyph == 'L') return letters[7][row];
    return 0u;
}

static void draw_tiny_text(unsigned char x, unsigned char y,
    const char* text, unsigned char color)
{
    unsigned char column;
    unsigned char row;
    unsigned char bits;

    tgi_setcolor(color);
    while (*text != '\0') {
        for (row = 0u; row < 5u; ++row) {
            bits = tiny_glyph_row(*text, row);
            for (column = 0u; column < 3u; ++column) {
                if ((bits & (unsigned char)(4u >> column)) != 0u) {
                    tgi_bar(x + column, y + row, x + column, y + row);
                }
            }
        }
        x = (unsigned char)(x + 4u);
        ++text;
    }
}

static char phase_symbol(const GameState* game)
{
    if (game->phase == GAME_PHASE_STAGE_INTRO) return 'I';
    if (game->phase == GAME_PHASE_NORMAL) return 'N';
    if (game->phase == GAME_PHASE_WARNING) return 'W';
    if (game->phase == GAME_PHASE_BOSS) return 'B';
    if (game->phase == GAME_PHASE_STAGE_CLEAR) return 'C';
    return 'A';
}

static void format_counter(unsigned int value, char* text)
{
    unsigned char i;

    text[4u] = '\0';
    for (i = 4u; i != 0u; --i) {
        text[i - 1u] = (char)('0' + (value % 10u));
        value /= 10u;
    }
}

static void draw_hud(const GameState* game)
{
    char score_text[SCORE_DIGITS + 1u];
    char timer_text[5u];
    char hud_text[21u];

    format_score(game->score, score_text);
    format_counter(game->phase_timer, timer_text);
    hud_text[0] = 'S';
    hud_text[1] = (char)('0' + game->stage);
    hud_text[2] = ' ';
    hud_text[3] = phase_symbol(game);
    hud_text[4] = timer_text[0];
    hud_text[5] = timer_text[1];
    hud_text[6] = timer_text[2];
    hud_text[7] = timer_text[3];
    hud_text[8] = ' ';
    hud_text[9] = score_text[0];
    hud_text[10] = score_text[1];
    hud_text[11] = score_text[2];
    hud_text[12] = score_text[3];
    hud_text[13] = score_text[4];
    hud_text[14] = ' ';
    hud_text[15] = 'L';
    hud_text[16] = (char)('0' + game->lives);
    hud_text[17] = ' ';
    hud_text[18] = 'W';
    hud_text[19] = (char)('0' + game->weapon_level);
    hud_text[20] = '\0';
    tgi_setcolor(GAME_COLOR_BLACK);
    tgi_bar(0u, 0u, GAME_SCREEN_WIDTH - 1u, GAME_HUD_HEIGHT - 1u);
    draw_tiny_text(2u, 2u, hud_text, GAME_COLOR_WHITE);
    tgi_setcolor(GAME_COLOR_NEAR_STAR);
    tgi_line(0u, GAME_HUD_HEIGHT - 1u, GAME_SCREEN_WIDTH - 1u,
        GAME_HUD_HEIGHT - 1u);
}

static void draw_phase_overlay(const GameState* game)
{
    if (game->phase == GAME_PHASE_WARNING) {
        tgi_outtextxy(52u, 45u, "WARNING");
    } else if (game->phase == GAME_PHASE_STAGE_CLEAR) {
        tgi_outtextxy(36u, 45u, "STAGE CLEAR");
    } else if (game->phase == GAME_PHASE_ALL_CLEAR) {
        tgi_outtextxy(44u, 40u, "ALL CLEAR");
        tgi_outtextxy(36u, 58u, "A/B TO RESTART");
    }
}

static void draw_wind_band(const GameWindBand* wind)
{
    unsigned char x;
    unsigned char y;
    unsigned char bottom;

    bottom = (unsigned char)(wind->y + GAME_WIND_BAND_HEIGHT - 1u);
    if (wind->state == GAME_WIND_STATE_WARNING) {
        tgi_setcolor(GAME_COLOR_WIND_WARNING);
        for (x = 0u; x < GAME_SCREEN_WIDTH; x = (unsigned char)(x + 12u)) {
            unsigned int x1;

            x1 = (unsigned int)x + 4u;
            if (x1 >= GAME_SCREEN_WIDTH) {
                x1 = GAME_SCREEN_WIDTH - 1u;
            }
            tgi_bar(x, wind->y, x1, wind->y);
            tgi_bar(x, bottom, x1, bottom);
        }
    } else {
        tgi_setcolor(GAME_COLOR_WIND_ACTIVE);
        for (y = (unsigned char)(wind->y + 5u); y < bottom;
            y = (unsigned char)(y + 7u)) {
            tgi_line(8u, y, 151u, y);
        }
    }
    for (x = 20u; x < GAME_SCREEN_WIDTH; x = (unsigned char)(x + 40u)) {
        unsigned char center_y;

        center_y = (unsigned char)(wind->y + GAME_WIND_BAND_HEIGHT / 2u);
        if (wind->direction == GAME_WIND_DIRECTION_UP) {
            tgi_line(x, (unsigned int)center_y + 4u, x, center_y - 4u);
            tgi_line(x, center_y - 4u, x - 2u, center_y - 1u);
            tgi_line(x, center_y - 4u, x + 2u, center_y - 1u);
        } else {
            tgi_line(x, center_y - 4u, x, (unsigned int)center_y + 4u);
            tgi_line(x, (unsigned int)center_y + 4u,
                x - 2u, (unsigned int)center_y + 1u);
            tgi_line(x, (unsigned int)center_y + 4u,
                x + 2u, (unsigned int)center_y + 1u);
        }
    }
}

static void draw_environment(const GameState* game,
    const GameStageConfig* stage_config)
{
    unsigned char i;

    if (game->phase != GAME_PHASE_NORMAL) {
        return;
    }
    if (stage_config->environment_id == GAME_ENVIRONMENT_ASTEROIDS) {
        for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
            if (game->asteroids[i].active != 0u) {
                draw_mask(game->asteroids[i].rect.x,
                    game->asteroids[i].rect.y,
                    GAME_ENVIRONMENT_OBJECT_WIDTH,
                    GAME_ENVIRONMENT_OBJECT_HEIGHT,
                    asteroid_masks[game->animation_frame],
                    GAME_COLOR_ENVIRONMENT_BODY);
            }
        }
    } else if (stage_config->environment_id == GAME_ENVIRONMENT_WIND) {
        if (game->wind.state != GAME_WIND_STATE_INACTIVE) {
            draw_wind_band(&game->wind);
        }
    } else {
        for (i = 0u; i < GAME_MAX_ENVIRONMENT_OBJECTS; ++i) {
            const GameFallingRock* rock;
            unsigned char y;

            rock = &game->falling_rocks[i];
            if (rock->state == GAME_ROCK_STATE_WARNING) {
                tgi_setcolor(GAME_COLOR_WIND_ACTIVE);
                for (y = 14u; y < 91u; y = (unsigned char)(y + 12u)) {
                    tgi_bar(rock->rect.x + 3u, y,
                        rock->rect.x + 4u, y + 2u);
                }
                tgi_line(rock->rect.x, 94u,
                    rock->rect.x + GAME_ENVIRONMENT_OBJECT_WIDTH - 1u, 94u);
                tgi_line(rock->rect.x, 94u, rock->rect.x + 2u, 91u);
                tgi_line(rock->rect.x + 7u, 94u,
                    rock->rect.x + 5u, 91u);
            } else if (rock->state == GAME_ROCK_STATE_FALLING) {
                draw_mask(rock->rect.x, rock->rect.y,
                    GAME_ENVIRONMENT_OBJECT_WIDTH,
                    GAME_ENVIRONMENT_OBJECT_HEIGHT,
                    falling_rock_masks[game->animation_frame],
                    GAME_COLOR_ENVIRONMENT_BODY);
            } else if (rock->state == GAME_ROCK_STATE_IMPACT) {
                tgi_setcolor(GAME_COLOR_ENVIRONMENT_DETAIL);
                tgi_line(rock->rect.x, 98u, rock->rect.x + 7u, 98u);
                tgi_line(rock->rect.x + 2u, 96u,
                    rock->rect.x + 5u, 96u);
            }
        }
    }
}

static void draw_game(const GameState* game)
{
    const GameStageConfig* stage_config;
    const BackgroundTheme* theme;
    unsigned char i;

    if (game->phase == GAME_PHASE_TITLE) {
        tgi_setbgcolor(GAME_COLOR_BLACK);
        tgi_clear();
        tgi_setcolor(GAME_COLOR_WHITE);
        tgi_outtextxy(24u, 18u, "ASTEROID PATROL");
        tgi_outtextxy(32u, 42u, "A/B TO START");
        tgi_outtextxy(28u, 62u, "ARROWS: MOVE");
        tgi_outtextxy(36u, 74u, "A/B: FIRE");
        tgi_updatedisplay();
        return;
    }

    stage_config = game_get_stage_config(game->stage);
    theme = &background_themes[stage_config->background_theme_id];
    tgi_setbgcolor(theme->background_color);
    tgi_clear();
    if (stage_config->background_theme_id == GAME_BACKGROUND_THEME_SKY) {
        draw_sky_background(game, theme);
    } else if (stage_config->background_theme_id ==
        GAME_BACKGROUND_THEME_CAVE) {
        draw_cave_background(game, theme);
    } else {
        draw_planet(game, theme);
        draw_background(game, theme);
    }
    draw_hud(game);
    tgi_setcolor(GAME_COLOR_WHITE);
    draw_phase_overlay(game);
    draw_environment(game, stage_config);

    if (game->phase != GAME_PHASE_ALL_CLEAR) {
        if (game->dying != 0u) {
            draw_mask((int)game->player.x,
                (int)game->player.y - 1, 8u, 8u,
                explosion_masks[game->explosion_timer /
                    GAME_EXPLOSION_STAGE_FRAMES],
                GAME_COLOR_EXPLOSION);
        } else if (game_player_is_visible(game) != 0u) {
            draw_mask(game->player.x, game->player.y, GAME_PLAYER_WIDTH,
                GAME_PLAYER_HEIGHT, player_masks[game->animation_frame],
                GAME_COLOR_PLAYER);
        }
        for (i = 0u; i < GAME_MAX_ENEMIES; ++i) {
            if (game->enemies[i].active != 0u &&
                game->enemies[i].rect.x < GAME_SCREEN_WIDTH) {
                draw_mask(game->enemies[i].rect.x,
                    game->enemies[i].rect.y, GAME_ENEMY_WIDTH,
                    GAME_ENEMY_HEIGHT,
                    enemy_masks[game->enemies[i].type]
                        [game->animation_frame],
                    enemy_color(game->enemies[i].type));
            }
        }
        if (game->boss.active != 0u) {
            draw_boss(&game->boss, game->animation_frame);
        }
        if (game->power_item.active != 0u) {
            draw_mask(game->power_item.rect.x, game->power_item.rect.y,
                GAME_POWER_ITEM_WIDTH, GAME_POWER_ITEM_HEIGHT,
                power_item_mask, GAME_COLOR_POWER_ITEM);
        }
        for (i = 0u; i < GAME_MAX_PLAYER_BULLETS; ++i) {
            if (game->bullets[i].active != 0u) {
                draw_rect(&game->bullets[i].rect, GAME_COLOR_BULLET);
            }
        }
        for (i = 0u; i < GAME_MAX_ENEMY_BULLETS; ++i) {
            if (game->enemy_bullets[i].active != 0u) {
                unsigned int x1;
                unsigned int y1;

                x1 = (unsigned int)game->enemy_bullets[i].rect.x + 2u;
                y1 = (unsigned int)game->enemy_bullets[i].rect.y + 1u;
                if (game->enemy_bullets[i].rect.y >= GAME_HUD_HEIGHT) {
                    if (x1 >= GAME_SCREEN_WIDTH) {
                        x1 = GAME_SCREEN_WIDTH - 1u;
                    }
                    if (y1 >= GAME_SCREEN_HEIGHT) {
                        y1 = GAME_SCREEN_HEIGHT - 1u;
                    }
                    tgi_setcolor(GAME_COLOR_ENEMY_BULLET);
                    tgi_bar(game->enemy_bullets[i].rect.x,
                        game->enemy_bullets[i].rect.y, x1,
                        game->enemy_bullets[i].rect.y);
                    tgi_bar((unsigned int)game->enemy_bullets[i].rect.x + 1u,
                        y1, (unsigned int)game->enemy_bullets[i].rect.x + 1u,
                        y1);
                }
            }
        }
    }
    if (game->game_over != 0u) {
        tgi_outtextxy(48u, 40u, "GAME OVER");
        tgi_outtextxy(40u, 58u, "A/B TO TITLE");
    }
    tgi_updatedisplay();
}

void main(void)
{
    unsigned char logic_remainder;
    unsigned char logic_updates;
    unsigned char update;
    unsigned char input;

    tgi_install(tgi_static_stddrv);
    tgi_init();
    joy_install(joy_static_stddrv);
    CLI();
    while (tgi_busy() != 0u) {
    }
    tgi_setbgcolor(GAME_COLOR_BLACK);
    tgi_setframerate(75u);
    sound_backend_init();
    game_init(&game);
    logic_remainder = 0u;

    for (;;) {
        while (tgi_busy() != 0u) {
        }
        input = read_input();
        logic_updates = game_logic_updates_for_draw_frame(&logic_remainder);
        for (update = 0u; update < logic_updates; ++update) {
            game_update_logic(&game, input);
        }
        game_sound_tick(&game);
        sound_backend_apply(SOUND_CHANNEL_A, &sound_hardware_bgm,
            &game.sound.output_bgm);
        sound_backend_apply(SOUND_CHANNEL_B, &sound_hardware_sfx,
            &game.sound.output_sfx);
        draw_game(&game);
    }
}
