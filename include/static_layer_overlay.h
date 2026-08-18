#ifndef STATIC_LAYER_OVERLAY_H
#define STATIC_LAYER_OVERLAY_H

/* Cartridge-backed overlay for background/title RODATA that is exclusive to
 * a single scene (APS-053 T2, docs/plan/2026-08-17-ram-reclamation.md §4).
 * static_layer_draw() loads the group for the scene it is about to draw
 * into static_layer_overlay_buffer (declared in the generated
 * static_layer_overlay_data.h) before referencing any offset within it, and
 * skips the reload when the same group is already resident.
 *
 * Loading reuses title_voice.c's cartridge file API (open()/read() with a
 * single cart-wide read cursor that ignores the fd argument). That cursor is
 * shared with title/GAME OVER voice streaming: callers must not load an
 * overlay while a voice stream is active. static_layer_draw() enforces this
 * by returning early while title_voice_is_playing() is true, before it ever
 * reaches static_layer_overlay_load(). */
#define STATIC_LAYER_OVERLAY_STAGE1 0u
#define STATIC_LAYER_OVERLAY_STAGE2 1u
#define STATIC_LAYER_OVERLAY_STAGE3 2u
#define STATIC_LAYER_OVERLAY_TITLE 3u
#define STATIC_LAYER_OVERLAY_NONE 0xFFu

void static_layer_overlay_load(unsigned char which);

#endif
