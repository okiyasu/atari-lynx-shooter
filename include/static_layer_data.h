#ifndef STATIC_LAYER_DATA_H
#define STATIC_LAYER_DATA_H

#include <stddef.h>

#define STATIC_LAYER_CLEAR_WIDTH 1
#define STATIC_LAYER_CLEAR_HEIGHT 1
#define STATIC_LAYER_CLEAR_Y_OFFSET 0
#define STATIC_LAYER_CLEAR_BPP 1
extern const unsigned char static_layer_clear_data[];

#define STATIC_LAYER_PLANET_WIDTH 32
#define STATIC_LAYER_PLANET_HEIGHT 24
#define STATIC_LAYER_PLANET_Y_OFFSET 0
#define STATIC_LAYER_PLANET_BPP 2
extern const unsigned char static_layer_planet_data[];

#define STATIC_LAYER_MOUNTAIN_WIDTH 192
#define STATIC_LAYER_MOUNTAIN_HEIGHT 21
#define STATIC_LAYER_MOUNTAIN_Y_OFFSET 58
#define STATIC_LAYER_MOUNTAIN_BPP 1
extern const unsigned char static_layer_mountain_data[];

#define STATIC_LAYER_MID_CLOUD_WIDTH 160
#define STATIC_LAYER_MID_CLOUD_HEIGHT 44
#define STATIC_LAYER_MID_CLOUD_Y_OFFSET 18
#define STATIC_LAYER_MID_CLOUD_BPP 1
extern const unsigned char static_layer_mid_cloud_data[];

#define STATIC_LAYER_NEAR_CLOUD_WIDTH 160
#define STATIC_LAYER_NEAR_CLOUD_HEIGHT 26
#define STATIC_LAYER_NEAR_CLOUD_Y_OFFSET 68
#define STATIC_LAYER_NEAR_CLOUD_BPP 1
extern const unsigned char static_layer_near_cloud_data[];

#define STATIC_LAYER_CAVE_WALL_WIDTH 192
#define STATIC_LAYER_CAVE_WALL_HEIGHT 61
#define STATIC_LAYER_CAVE_WALL_Y_OFFSET 24
#define STATIC_LAYER_CAVE_WALL_BPP 1
extern const unsigned char static_layer_cave_wall_data[];

#define STATIC_LAYER_CAVE_ROCK_WIDTH 160
#define STATIC_LAYER_CAVE_ROCK_HEIGHT 89
#define STATIC_LAYER_CAVE_ROCK_Y_OFFSET 10
#define STATIC_LAYER_CAVE_ROCK_BPP 1
extern const unsigned char static_layer_cave_rock_data[];

#define STATIC_LAYER_CAVE_NEAR_WIDTH 160
#define STATIC_LAYER_CAVE_NEAR_HEIGHT 79
#define STATIC_LAYER_CAVE_NEAR_Y_OFFSET 15
#define STATIC_LAYER_CAVE_NEAR_BPP 1
extern const unsigned char static_layer_cave_near_data[];

#define STATIC_LAYER_SPACE_FAR_STAR_WIDTH 1
#define STATIC_LAYER_SPACE_FAR_STAR_HEIGHT 1
#define STATIC_LAYER_SPACE_FAR_STAR_Y_OFFSET 0
#define STATIC_LAYER_SPACE_FAR_STAR_BPP 1
extern const unsigned char static_layer_space_far_star_data[];

#define STATIC_LAYER_NEAR_STAR_WIDTH 2
#define STATIC_LAYER_NEAR_STAR_HEIGHT 1
#define STATIC_LAYER_NEAR_STAR_Y_OFFSET 0
#define STATIC_LAYER_NEAR_STAR_BPP 1
extern const unsigned char static_layer_near_star_data[];

#define STATIC_LAYER_GLYPH_COUNT 18
extern const unsigned char static_layer_glyph_bits[];
#define STATIC_LAYER_FONT_COUNT 39
#define STATIC_LAYER_FONT_WIDTH 5
#define STATIC_LAYER_FONT_HEIGHT 7
extern const unsigned char static_layer_font_bits[];
extern const unsigned char static_layer_text_asteroid_patrol_data[];
extern const unsigned char static_layer_text_ab_to_start_data[];
extern const unsigned char static_layer_text_arrows_move_data[];
extern const unsigned char static_layer_text_ab_fire_data[];
extern const unsigned char static_layer_text_voicevox_nemo_data[];
extern const unsigned char static_layer_text_voicevox_suffix_data[];
#define STATIC_LAYER_NEAR_STAR_COUNT 7
extern const unsigned char static_layer_near_star_x[];
extern const unsigned char static_layer_near_star_y[];
#define STATIC_LAYER_FAR_STAR_COUNT 10
extern const unsigned char static_layer_far_star_x[];
extern const unsigned char static_layer_far_star_y[];

#endif
