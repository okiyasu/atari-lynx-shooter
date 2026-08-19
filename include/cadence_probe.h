#ifndef CADENCE_PROBE_H
#define CADENCE_PROBE_H

/* APS-052 test-only cadence hook. It records Timer 2 VBlank counts between
 * display requests; the verifier arms it through the exported RAM symbols. */
void cadence_probe_display(void);
void cadence_probe_logic_update(void);
void cadence_probe_elapsed_vblanks(unsigned int elapsed_vblanks);
void cadence_probe_sound_tick(void);
void cadence_probe_capture_state(void);
void cadence_probe_hold_fixture(void);

#define CADENCE_FIXTURE_SAMPLE_COUNT 75u

#endif
