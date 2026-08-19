;
; APS-053 v040 test-only, temporary diagnostic markers.
;
; Three exported no-op landing points used only as stable breakpoint
; addresses for the cadence-build gate(a) breakdown harness
; (scripts/verify-phase-3r-gate-a-breakdown-gearlynx.py). Each is a single
; RTS; callers JSR into it and the debugger reads the emulator's own CPU
; tick counter (get_6502_status.total_ticks) while paused exactly at that
; RTS, before it executes. This does not touch scripts/cadence_probe.s or
; include/cadence_probe.h (protected APS-052 apparatus) and is only linked
; into the cadence diagnostic build (build/main-cadence.o), never the
; release ROM. Not part of Phase 3R's SCB chain construction, draw order,
; or data format -- purely external timing landmarks.
;

        .export         _scb_split_marker_begin
        .export         _scb_split_marker_finish_enter
        .export         _scb_split_marker_finish_exit

        .code

_scb_split_marker_begin:
        rts

_scb_split_marker_finish_enter:
        rts

_scb_split_marker_finish_exit:
        rts
