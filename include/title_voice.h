#ifndef TITLE_VOICE_H
#define TITLE_VOICE_H

/* Cartridge-backed voice player shared by the title and GAME OVER clips.
 * Compressed assets stay in separate Lynx directory entries; five small
 * ADPCM buffers and one Timer 3/channel D decoder are shared at runtime. */
void title_voice_init(void);
unsigned char title_voice_start(void);
unsigned char game_over_voice_start(void);
void title_voice_pump(void);
void title_voice_stop(void);
unsigned char title_voice_is_playing(void);
unsigned char title_voice_had_underrun(void);

#endif
