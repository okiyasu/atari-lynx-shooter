;
; APS-052 test-only, non-invasive cadence probe.
;
; The Timer 2 interrupt increments a counter while a batch is active. The
; display-request hook snapshots and clears that counter, producing one
; VBlank interval per display request without pausing the emulator. The
; verifier arms a batch through the exported BSS bytes and uses one write
; breakpoint on completion only to read the finished batch.
;

        .export         _cadence_probe_display
        .export         _cadence_probe_logic_update
        .export         _cadence_probe_elapsed_vblanks
        .export         _cadence_probe_sound_tick
        .export         _cadence_probe_logic_update_count
        .export         _cadence_probe_elapsed_vblank_count
        .export         _cadence_probe_armed
        .export         _cadence_probe_active
        .export         _cadence_probe_complete
        .export         _cadence_probe_sample_count
        .export         _cadence_probe_vblank_count
        .export         _cadence_probe_warmup_vblank_count
        .export         _cadence_probe_warmup
        .export         _cadence_probe_overflow
        .export         _cadence_probe_intervals
        .export         _cadence_probe_sound_tick_count
        .interruptor    cadence_probe_irq
        .import         _game_timing_reset_baseline
        .include        "lynx.inc"

; APS-052 logic batches use 16 intervals so the real game-update path can
; complete two independent batches before a fixture reaches a phase boundary.
CADENCE_INTERVAL_COUNT = 16
CADENCE_WARMUP_REQUEST_COUNT = 6

        .bss
_cadence_probe_armed:        .res 1
_cadence_probe_active:       .res 1
_cadence_probe_complete:     .res 1
_cadence_probe_sample_count: .res 1
_cadence_probe_vblank_count: .res 2
_cadence_probe_warmup_vblank_count: .res 2
_cadence_probe_warmup:      .res 1
_cadence_probe_overflow:     .res 1
_cadence_probe_logic_update_count: .res 4
_cadence_probe_elapsed_vblank_count: .res 4

        ; Keep actual sound-tick readback in ZP so the cadence probe does not
        ; grow production BSS or move the C stack reservation.
        .zeropage
_cadence_probe_sound_tick_count: .res 4

        .bss

; The interval batch is part of the cadence ROM's BSS. Its linker map is
; checked against the C stack start by the verifier; no stack or MAIN tail
; bytes are borrowed. A high-byte sample sets overflow instead of silently
; truncating the raw VBlank count.
_cadence_probe_intervals:   .res CADENCE_INTERVAL_COUNT

        .code

; Count Timer 2 VBlank IRQs without claiming the interrupt. The shared IRQ
; stub clears the hardware interrupt after all interruptors have run.
cadence_probe_irq:
        lda     _cadence_probe_active
        beq     @done
        lda     INTSET
        and     #VBL_INTERRUPT
        beq     @done
        inc     _cadence_probe_vblank_count
        bne     @done
        inc     _cadence_probe_vblank_count + 1
@done:  clc
        rts

; Called immediately before tgi_updatedisplay(). The interrupt mask protects
; the 16-bit snapshot/reset from a concurrent Timer 2 increment.
_cadence_probe_display:
        php
        sei
        lda     _cadence_probe_armed
        beq     @record
        stz     _cadence_probe_armed
        stz     _cadence_probe_active
        stz     _cadence_probe_sample_count
        stz     _cadence_probe_vblank_count
        stz     _cadence_probe_vblank_count + 1
        stz     _cadence_probe_warmup_vblank_count
        stz     _cadence_probe_warmup_vblank_count + 1
        stz     _cadence_probe_overflow
        stz     _cadence_probe_logic_update_count
        stz     _cadence_probe_logic_update_count + 1
        stz     _cadence_probe_logic_update_count + 2
        stz     _cadence_probe_logic_update_count + 3
        stz     _cadence_probe_elapsed_vblank_count
        stz     _cadence_probe_elapsed_vblank_count + 1
        stz     _cadence_probe_elapsed_vblank_count + 2
        stz     _cadence_probe_elapsed_vblank_count + 3
        stz     _cadence_probe_sound_tick_count
        stz     _cadence_probe_sound_tick_count + 1
        stz     _cadence_probe_sound_tick_count + 2
        stz     _cadence_probe_sound_tick_count + 3
        lda     #1
        sta     _cadence_probe_active
        lda     #CADENCE_WARMUP_REQUEST_COUNT
        sta     _cadence_probe_warmup
        ; Discard VBlanks accumulated while the debugger injected the
        ; fixture. The first interval is still a probe warm-up sample, but
        ; the production timing baseline must start at the same arm edge.
        jsr     _game_timing_reset_baseline
        jmp     @done

@record:
        lda     _cadence_probe_active
        beq     @record_inactive
        lda     _cadence_probe_warmup
        beq     @record_sample
        lda     _cadence_probe_vblank_count
        clc
        adc     _cadence_probe_warmup_vblank_count
        sta     _cadence_probe_warmup_vblank_count
        lda     _cadence_probe_vblank_count + 1
        adc     _cadence_probe_warmup_vblank_count + 1
        sta     _cadence_probe_warmup_vblank_count + 1
        stz     _cadence_probe_vblank_count
        stz     _cadence_probe_vblank_count + 1
        dec     _cadence_probe_warmup
        bne     @done
        stz     _cadence_probe_logic_update_count
        stz     _cadence_probe_logic_update_count + 1
        stz     _cadence_probe_logic_update_count + 2
        stz     _cadence_probe_logic_update_count + 3
        stz     _cadence_probe_elapsed_vblank_count
        stz     _cadence_probe_elapsed_vblank_count + 1
        stz     _cadence_probe_elapsed_vblank_count + 2
        stz     _cadence_probe_elapsed_vblank_count + 3
        stz     _cadence_probe_sound_tick_count
        stz     _cadence_probe_sound_tick_count + 1
        stz     _cadence_probe_sound_tick_count + 2
        stz     _cadence_probe_sound_tick_count + 3
        ; The warm-up interval is deliberately excluded from both the probe
        ; and production catch-up denominator.
        jsr     _game_timing_reset_baseline
        bra     @done

@record_inactive:
        jmp     @done

@record_sample:
        lda     _cadence_probe_sample_count
        cmp     #CADENCE_INTERVAL_COUNT
        bcs     @done
        tax
        lda     _cadence_probe_vblank_count
        pha
        lda     _cadence_probe_vblank_count + 1
        beq     @store
        lda     #1
        sta     _cadence_probe_overflow
@store: pla
        sta     _cadence_probe_intervals,x
        stz     _cadence_probe_vblank_count
        stz     _cadence_probe_vblank_count + 1
        inc     _cadence_probe_sample_count
        lda     _cadence_probe_sample_count
        cmp     #CADENCE_INTERVAL_COUNT
        bne     @done
        stz     _cadence_probe_active
        lda     #1
        sta     _cadence_probe_complete
        bra     @done

; Completion is raised by the final sampled display request. The verifier
; aligns scheduler counters to the intervals whose following main-loop work
; was observed, and records the terminal display interval separately.
@finish:
        stz     _cadence_probe_active
        lda     #1
        sta     _cadence_probe_complete

@done:  plp
        rts

; Called by the cadence-only main loop for every executed logic update.
_cadence_probe_logic_update:
        lda     _cadence_probe_active
        beq     @done
        inc     _cadence_probe_logic_update_count
        bne     @done
        inc     _cadence_probe_logic_update_count + 1
        bne     @done
        inc     _cadence_probe_logic_update_count + 2
        bne     @done
        inc     _cadence_probe_logic_update_count + 3
@done:  rts

; Called once per main-loop consume with the production 16-bit elapsed value.
_cadence_probe_elapsed_vblanks:
        pha
        phx
        lda     _cadence_probe_active
        beq     @elapsed_inactive
        plx
        pla
        clc
        adc     _cadence_probe_elapsed_vblank_count
        sta     _cadence_probe_elapsed_vblank_count
        txa
        adc     _cadence_probe_elapsed_vblank_count + 1
        sta     _cadence_probe_elapsed_vblank_count + 1
        bcc     @elapsed_return
        inc     _cadence_probe_elapsed_vblank_count + 2
        bne     @elapsed_return
        inc     _cadence_probe_elapsed_vblank_count + 3
@elapsed_return:
        rts
@elapsed_inactive:
        plx
        pla
        rts

; Called once, immediately after each real game_sound_tick() returns.
_cadence_probe_sound_tick:
        lda     _cadence_probe_active
        beq     @sound_done
        inc     _cadence_probe_sound_tick_count
        bne     @sound_done
        inc     _cadence_probe_sound_tick_count + 1
        bne     @sound_done
        inc     _cadence_probe_sound_tick_count + 2
        bne     @sound_done
        inc     _cadence_probe_sound_tick_count + 3
@sound_done:
        rts
