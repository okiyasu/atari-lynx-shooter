#ifndef TITLE_VOICE_STREAM_H
#define TITLE_VOICE_STREAM_H

#if !defined(__CC65__) && !defined(__fastcall__)
#define __fastcall__
#endif

/* Approximately 7.94 kHz IMA ADPCM stream for MIKEY channel D. Timer 3 uses
 * backup 125 on its 1 us clock, giving a 126 us period (7,936.508 Hz). The
 * source and as many as three queued compressed buffers must remain resident
 * until consumed. */
void __fastcall__ title_voice_stream_set_source(const unsigned char* source);
void __fastcall__ title_voice_stream_set_queue_source(
    const unsigned char* source);
void __fastcall__ title_voice_stream_start(unsigned sample_count);
unsigned char __fastcall__ title_voice_stream_queue(unsigned sample_count);
void title_voice_stream_stop(void);
unsigned char title_voice_stream_is_playing(void);
unsigned char title_voice_stream_can_queue(void);

#endif
