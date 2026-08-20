;
; APS-053 v047/v048 test-only, temporary diagnostic markers.
;
; Exported no-op landing points used only as stable breakpoint addresses
; for the gate(a) frame-breakdown harness
; (scripts/verify-phase-3r-frame-breakdown-gearlynx.py). Callers JSR into
; each; the debugger reads the emulator's own CPU tick counter
; (get_6502_status.total_ticks) while paused exactly at that RTS, before
; it executes. Does not touch src/cadence_probe.s or src/scb_split_probe.s
; (both unmodified) and is only linked into the cadence diagnostic build
; (build/static_layer-cadence.o), never the release ROM. Not part of any
; production code path, SCB chain construction, draw order, or data
; format -- purely external timing landmarks.
;
;   _static_layer_split_marker_after_overlay_and_clear: static_layer.c
;     static_layer_draw(), right after ensure_overlay()+begin_layer()+the
;     full-screen clear append_scb() call, before append_space()/
;     append_scroll_layers().
;   _static_layer_split_marker_after_background: static_layer.c
;     static_layer_draw(), right after append_space()/
;     append_scroll_layers() returns, before append_hud().
;   _static_layer_split_marker_pre_finish: static_layer.c finish_layer(),
;     right before tgi_sprite(SCBS) is called, separating
;     "background/HUD SCB construction" from "background Suzy submit"
;     within section E of the frame breakdown (see that script's module
;     docstring).
;

        .export         _static_layer_split_marker_after_overlay_and_clear
        .export         _static_layer_split_marker_after_background
        .export         _static_layer_split_marker_pre_finish

        .code

_static_layer_split_marker_after_overlay_and_clear:
        rts

_static_layer_split_marker_after_background:
        rts

_static_layer_split_marker_pre_finish:
        rts
