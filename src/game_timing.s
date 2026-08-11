;
; APS-052 persistent Timer 2 VBlank clock.
;
; This is an interruptor, not an interrupt owner. The cc65 Lynx IRQ stub
; calls every interruptor and clears the pending bits once after the chain,
; so TGI and Timer 3/voice continue to receive the same IRQ.
;
        .export         _game_timing_init
        .export         _game_timing_consume_vblanks
        .export         _game_timing_reset_baseline
        .interruptor    game_timing_irq
        .include        "lynx.inc"
        .include        "zeropage.inc"

        .export         _game_timing_stack_low_water

; The cc65 software stack pointer is a 16-bit zero-page value. Sampling it
; from every IRQ gives a runtime high-water mark without adding a C probe
; call to the voice or gameplay paths. The verifier compares this address
; with the map's reserved stack range and requires 128 bytes between the
; lowest observed SP and the stack start.
        .zeropage
_game_timing_stack_low_water: .res 2

        .bss
game_timing_vblank_total:    .res 4
game_timing_vblank_baseline: .res 4

        .code

; Count every Timer 2 VBlank without clearing or disabling its interrupt.
game_timing_irq:
        lda     sp + 1
        cmp     _game_timing_stack_low_water + 1
        bcc     @record_stack
        bne     @check_vblank
        lda     sp
        cmp     _game_timing_stack_low_water
        bcs     @check_vblank
@record_stack:
        lda     sp
        sta     _game_timing_stack_low_water
        lda     sp + 1
        sta     _game_timing_stack_low_water + 1
@check_vblank:
        lda     INTSET
        and     #VBL_INTERRUPT
        beq     @done
        inc     game_timing_vblank_total
        bne     @done
        inc     game_timing_vblank_total + 1
        bne     @done
        inc     game_timing_vblank_total + 2
        bne     @done
        inc     game_timing_vblank_total + 3
@done:  clc
        rts

; Init and voice completion both discard the pending interval by moving the
; baseline to the current monotonic total.
_game_timing_init:
        php
        sei
        lda     #$ff
        sta     _game_timing_stack_low_water
        sta     _game_timing_stack_low_water + 1
        bra     game_timing_reset_baseline_body

_game_timing_reset_baseline:
        php
        sei
game_timing_reset_baseline_body:
        lda     game_timing_vblank_total
        sta     game_timing_vblank_baseline
        lda     game_timing_vblank_total + 1
        sta     game_timing_vblank_baseline + 1
        lda     game_timing_vblank_total + 2
        sta     game_timing_vblank_baseline + 2
        lda     game_timing_vblank_total + 3
        sta     game_timing_vblank_baseline + 3
        plp
        rts

; Consume a 32-bit monotonic delta atomically and move the baseline. The C
; API returns the low 16 bits in A/X (A=low, X=high), saturating at $ffff if
; the elapsed interval exceeds the 16-bit API range. The monotonic counter
; remains 32-bit so the raw Timer 2 clock can run for long periods; logic and
; sound apply their own independent work caps in the caller.
_game_timing_consume_vblanks:
        php
        sei
        lda     game_timing_vblank_total
        sec
        sbc     game_timing_vblank_baseline
        pha
        lda     game_timing_vblank_total + 1
        sbc     game_timing_vblank_baseline + 1
        pha
        lda     game_timing_vblank_total + 2
        sbc     game_timing_vblank_baseline + 2
        bne     @saturate
        lda     game_timing_vblank_total + 3
        sbc     game_timing_vblank_baseline + 3
        bne     @saturate
        bra     @update_baseline

@saturate:
        pla
        pla
        lda     game_timing_vblank_total
        sta     game_timing_vblank_baseline
        lda     game_timing_vblank_total + 1
        sta     game_timing_vblank_baseline + 1
        lda     game_timing_vblank_total + 2
        sta     game_timing_vblank_baseline + 2
        lda     game_timing_vblank_total + 3
        sta     game_timing_vblank_baseline + 3
        lda     #$ff
        ldx     #$ff
        plp
        rts

@update_baseline:
        lda     game_timing_vblank_total
        sta     game_timing_vblank_baseline
        lda     game_timing_vblank_total + 1
        sta     game_timing_vblank_baseline + 1
        lda     game_timing_vblank_total + 2
        sta     game_timing_vblank_baseline + 2
        lda     game_timing_vblank_total + 3
        sta     game_timing_vblank_baseline + 3
        pla
        tax
        pla
        plp
        rts
