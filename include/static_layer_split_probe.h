#ifndef STATIC_LAYER_SPLIT_PROBE_H
#define STATIC_LAYER_SPLIT_PROBE_H

/* APS-053 v047/v048 test-only diagnostic markers. See
 * src/static_layer_split_probe.s. */
void static_layer_split_marker_after_overlay_and_clear(void);
void static_layer_split_marker_after_background(void);
void static_layer_split_marker_pre_finish(void);

#endif
