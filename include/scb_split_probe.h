#ifndef SCB_SPLIT_PROBE_H
#define SCB_SPLIT_PROBE_H

/* APS-053 v040 test-only diagnostic markers, cadence build only (see
 * src/scb_split_probe.s). Not part of Phase 3R's SCB chain construction,
 * draw order, or data format -- external timing landmarks only. */
void scb_split_marker_begin(void);
void scb_split_marker_finish_enter(void);
void scb_split_marker_finish_exit(void);

#endif
