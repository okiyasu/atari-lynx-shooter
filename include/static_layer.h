#ifndef STATIC_LAYER_H
#define STATIC_LAYER_H

#include "game.h"

/* The static layer uses the first 539 bytes of title_voice_scratch_buffer
 * for SCBs/HUD data. The voice player owns that prefix while title or GAME
 * OVER voice is active; the two users are never concurrent. Release builds
 * return without drawing, while STATIC_LAYER_DEBUG_ASSERT builds fail fast
 * at the same boundary to expose a contract violation. */
void static_layer_draw(const GameState* game, unsigned char theme_id);
void static_layer_title_text(int x, int y, unsigned char id,
    unsigned char color);
void static_layer_text(int x, int y, const char* text, unsigned char color);
void static_layer_credit_suffix(int x, int y, unsigned char color);
void static_layer_text_flush(void);

#endif
