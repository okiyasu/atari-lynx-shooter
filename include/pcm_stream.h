#ifndef PCM_STREAM_H
#define PCM_STREAM_H

#if !defined(__CC65__) && !defined(__fastcall__)
#define __fastcall__
#endif

/* APS-031 hardware feasibility backend. Samples are signed 8-bit two's
 * complement bytes at 8 kHz. The source must remain resident until playback
 * completes. One next buffer can be queued for seamless double-buffered
 * playback. A start while active and a queue while occupied are ignored;
 * completion/stop consumes both sources. This driver owns MIKEY timer 3 and
 * channel D only. */
void __fastcall__ pcm_stream_set_source(const unsigned char* source);
void __fastcall__ pcm_stream_set_queue_source(const unsigned char* source);
void __fastcall__ pcm_stream_start(unsigned length);
unsigned char __fastcall__ pcm_stream_queue(unsigned length);
void pcm_stream_stop(void);
unsigned char pcm_stream_is_playing(void);
unsigned char pcm_stream_can_queue(void);

#endif
