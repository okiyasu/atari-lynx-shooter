;
; APS-053 v047 test-only, temporary diagnostic marker.
;
; Single exported no-op landing point used only as a stable breakpoint
; address for the gate(a) frame-breakdown harness
; (scripts/verify-phase-3r-frame-breakdown-gearlynx.py). Marks the point
; in static_layer.c's finish_layer(), right before tgi_sprite(SCBS) is
; called, separating "background/HUD SCB construction" from "background
; Suzy submit" within section E of the frame breakdown (see that script's
; module docstring). Callers JSR into it and the debugger reads the
; emulator's own CPU tick counter (get_6502_status.total_ticks) while
; paused exactly at this RTS, before it executes. Does not touch
; src/cadence_probe.s or src/scb_split_probe.s (both unmodified) and is
; only linked into the cadence diagnostic build
; (build/static_layer-cadence.o), never the release ROM. Not part of any
; production code path, SCB chain construction, draw order, or data
; format -- purely an external timing landmark.
;

        .export         _static_layer_split_marker_pre_finish

        .code

_static_layer_split_marker_pre_finish:
        rts
