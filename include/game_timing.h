#ifndef GAME_TIMING_H
#define GAME_TIMING_H

/* Timer 2 VBlank clock used by the outer game loop. */
void game_timing_init(void);
unsigned int game_timing_consume_vblanks(void);
void game_timing_reset_baseline(void);

#endif
