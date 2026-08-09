;
; APS-035/036/038 shared approximately 7.94 kHz IMA ADPCM stream for MIKEY
; channel D (title and GAME OVER clips are mutually exclusive).
; One nibble is decoded inside each Timer 3 IRQ. Mainline code reads
; compressed 128-byte chunks from cartridge into five resident buffers;
; three queued slots preserve the underrun-safe APS-033 stream path.
;

        .export         _title_voice_stream_set_source
        .export         _title_voice_stream_set_queue_source
        .export         _title_voice_stream_start
        .export         _title_voice_stream_queue
        .export         _title_voice_stream_stop
        .export         _title_voice_stream_is_playing
        .export         _title_voice_stream_can_queue

        .import         callirq

        .include        "lynx.inc"

VOICE_OUTPUT           = AUD3OUT
VOICE_CHANNEL_CONTROL  = AUD3CTLA
; Timer 3 uses the 1 us clock and borrows after backup + 1 ticks.
; 125 therefore gives 126 us/sample = 7,936.508 Hz, exactly half the
; APS-033 backup 62 rate (63 us/sample = 15,873.016 Hz).
VOICE_TIMER_RELOAD     = 125
VOICE_TIMER_CONTROL    = $D8

        .zeropage
stream_cursor:         .res 2
stream_queue_cursor:   .res 2
stream_second_queue_cursor: .res 2
stream_third_queue_cursor: .res 2
stream_remaining:      .res 2
stream_queue_remaining: .res 2
stream_second_queue_remaining: .res 2
stream_third_queue_remaining: .res 2
stream_playing:        .res 1
stream_source_set:     .res 1
stream_queue_set:      .res 1
stream_queue_pending:  .res 1
stream_second_queue_set: .res 1
stream_second_queue_pending: .res 1
stream_third_queue_set: .res 1
stream_third_queue_pending: .res 1
stream_high_nibble:    .res 1
stream_packed:         .res 1
decode_predictor:      .res 2
decode_step_index:     .res 1

        .bss
stream_previous_irq:   .res 2
stream_fast_irq_set:   .res 1

        .rodata
        .include "title_voice_delta.inc"
        .include "title_voice_gain.inc"
next_index_minus_one:
        .repeat 89, index
                .if index = 0
                        .byte 0
                .else
                        .byte index - 1
                .endif
        .endrepeat
next_index_plus_two:
        .repeat 89, index
                .if index > 86
                        .byte 88
                .else
                        .byte index + 2
                .endif
        .endrepeat
next_index_plus_four:
        .repeat 89, index
                .if index > 84
                        .byte 88
                .else
                        .byte index + 4
                .endif
        .endrepeat
next_index_plus_six:
        .repeat 89, index
                .if index > 82
                        .byte 88
                .else
                        .byte index + 6
                .endif
        .endrepeat
next_index_plus_eight:
        .repeat 89, index
                .if index > 80
                        .byte 88
                .else
                        .byte index + 8
                .endif
        .endrepeat
decode_jump_table:
        .addr decode_add0, decode_add1, decode_add2, decode_add3
        .addr decode_add4, decode_add5, decode_add6, decode_add7
        .addr decode_subtract0, decode_subtract1
        .addr decode_subtract2, decode_subtract3
        .addr decode_subtract4, decode_subtract5
        .addr decode_subtract6, decode_subtract7

        .code

_title_voice_stream_set_source:
        php
        sei
        pha
        stz     TIM3CTLA
        jsr     restore_irq_vector
        stz     stream_playing
        stz     stream_queue_pending
        stz     stream_queue_set
        stz     stream_second_queue_pending
        stz     stream_second_queue_set
        stz     stream_third_queue_pending
        stz     stream_third_queue_set
        stz     VOICE_CHANNEL_CONTROL
        stz     VOICE_OUTPUT
        pla
        sta     stream_cursor
        stx     stream_cursor + 1
        stz     stream_source_set
        txa
        ora     stream_cursor
        beq     @done
        lda     #$ff
        sta     stream_source_set
@done:  plp
        rts

_title_voice_stream_set_queue_source:
        php
        sei
        pha
        lda     stream_queue_pending
        beq     @set_primary
        lda     stream_second_queue_pending
        beq     @set_second
        lda     stream_third_queue_pending
        beq     @set_third
        pla
        plp
        rts
@set_primary:
        pla
        sta     stream_queue_cursor
        stx     stream_queue_cursor + 1
        stz     stream_queue_set
        txa
        ora     stream_queue_cursor
        beq     @done
        lda     #$ff
        sta     stream_queue_set
@done:  plp
        rts
@set_second:
        pla
        sta     stream_second_queue_cursor
        stx     stream_second_queue_cursor + 1
        stz     stream_second_queue_set
        txa
        ora     stream_second_queue_cursor
        beq     @done
        lda     #$ff
        sta     stream_second_queue_set
        bra     @done
@set_third:
        pla
        sta     stream_third_queue_cursor
        stx     stream_third_queue_cursor + 1
        stz     stream_third_queue_set
        txa
        ora     stream_third_queue_cursor
        beq     @done
        lda     #$ff
        sta     stream_third_queue_set
        bra     @done

_title_voice_stream_start:
        php
        sei
        pha
        lda     stream_playing
        beq     @begin
        pla
        plp
        rts
@begin: pla
        stz     TIM3CTLA
        stz     stream_playing
        stz     VOICE_CHANNEL_CONTROL
        stz     VOICE_OUTPUT
        sta     stream_remaining
        stx     stream_remaining + 1
        txa
        ora     stream_remaining
        beq     @invalid
        lda     stream_source_set
        beq     @invalid
        stz     stream_high_nibble
        stz     decode_predictor
        stz     decode_predictor + 1
        stz     decode_step_index
        lda     #$ff
        sta     stream_playing
        lda     INTVECTL
        sta     stream_previous_irq
        lda     INTVECTH
        sta     stream_previous_irq + 1
        lda     #<title_voice_stream_irq
        sta     INTVECTL
        lda     #>title_voice_stream_irq
        sta     INTVECTH
        lda     #$ff
        sta     stream_fast_irq_set
        lda     #VOICE_TIMER_RELOAD
        sta     TIM3BKUP
        sta     TIM3CNT
        lda     #VOICE_TIMER_CONTROL
        sta     TIM3CTLA
@done:  plp
        rts
@invalid:
        stz     stream_source_set
        stz     stream_queue_pending
        stz     stream_queue_set
        stz     stream_second_queue_pending
        stz     stream_second_queue_set
        stz     stream_third_queue_pending
        stz     stream_third_queue_set
        bra     @done

_title_voice_stream_queue:
        php
        sei
        pha
        lda     stream_queue_pending
        bne     @queue_second
        lda     stream_queue_set
        beq     @reject
        pla
        sta     stream_queue_remaining
        stx     stream_queue_remaining + 1
        txa
        ora     stream_queue_remaining
        beq     @empty
        lda     #$ff
        sta     stream_queue_pending
        plp
        lda     #$01
        ldx     #$00
        rts
@queue_second:
        lda     stream_second_queue_pending
        bne     @queue_third
        lda     stream_second_queue_set
        beq     @reject
        pla
        sta     stream_second_queue_remaining
        stx     stream_second_queue_remaining + 1
        txa
        ora     stream_second_queue_remaining
        beq     @empty
        lda     #$ff
        sta     stream_second_queue_pending
        plp
        lda     #$01
        ldx     #$00
        rts
@queue_third:
        lda     stream_third_queue_pending
        bne     @reject
        lda     stream_third_queue_set
        beq     @reject
        pla
        sta     stream_third_queue_remaining
        stx     stream_third_queue_remaining + 1
        txa
        ora     stream_third_queue_remaining
        beq     @empty
        lda     #$ff
        sta     stream_third_queue_pending
        plp
        lda     #$01
        ldx     #$00
        rts
@reject:
        pla
@empty: plp
        lda     #$00
        ldx     #$00
        rts

_title_voice_stream_stop:
        php
        sei
        stz     TIM3CTLA
        jsr     restore_irq_vector
        stz     stream_playing
        stz     stream_source_set
        stz     stream_queue_pending
        stz     stream_queue_set
        stz     stream_second_queue_pending
        stz     stream_second_queue_set
        stz     stream_third_queue_pending
        stz     stream_third_queue_set
        stz     VOICE_CHANNEL_CONTROL
        stz     VOICE_OUTPUT
        plp
        rts

_title_voice_stream_is_playing:
        lda     stream_playing
        ldx     #$00
        rts

_title_voice_stream_can_queue:
        lda     stream_third_queue_pending
        eor     #$ff
        ldx     #$00
        rts

; Timer 3 runs too quickly for cc65's generic interruptor walk plus exact IMA
; decode. While voice is active, use a private vector. A simultaneous nonvoice
; source is delegated through callirq, but only its bits are acknowledged; a
; Timer 3 borrow that occurs during that work is decoded before this RTI.
title_voice_stream_irq:
        phy
        phx
        pha
        lda     INTSET
        and     #TIMER3_INTERRUPT
        bne     :+
        jsr     callirq
        lda     INTSET
        and     #($ff - TIMER3_INTERRUPT)
        sta     INTRST
        lda     INTSET
        and     #TIMER3_INTERRUPT
        bne     :+
        pla
        plx
        ply
        rti
:
        lda     #TIMER3_INTERRUPT
        sta     INTRST
        lda     stream_high_nibble
        bne     @high
        ldy     #$00
        lda     (stream_cursor),y
        sta     stream_packed
        inc     stream_cursor
        bne     :+
        inc     stream_cursor + 1
:
        lda     #$ff
        sta     stream_high_nibble
        lda     stream_packed
        and     #$0f
        bra     @decode
@high:  stz     stream_high_nibble
        lda     stream_packed
        lsr
        lsr
        lsr
        lsr
@decode:
        jmp     decode_nibble
decode_complete:
        ; AUD3OUT is a direct signed 8-bit DAC path: AUD3VOL only supplies
        ; the polynomial generator and cannot amplify CPU writes here.
        ; Apply center-preserving floor(|sample| * 5 / 4), restore the sign,
        ; and saturate to -128..127 through this constant-time table.
        ldx     decode_predictor + 1
        lda     voice_gain_table,x
        sta     VOICE_OUTPUT

        lda     stream_remaining
        bne     :+
        dec     stream_remaining + 1
:
        dec     stream_remaining
        bne     @not_ours
        lda     stream_remaining + 1
        bne     @not_ours
        lda     stream_queue_pending
        beq     @finish
        lda     stream_queue_cursor
        sta     stream_cursor
        lda     stream_queue_cursor + 1
        sta     stream_cursor + 1
        lda     stream_queue_remaining
        sta     stream_remaining
        lda     stream_queue_remaining + 1
        sta     stream_remaining + 1
        lda     stream_second_queue_pending
        beq     @queue_drained
        lda     stream_second_queue_cursor
        sta     stream_queue_cursor
        lda     stream_second_queue_cursor + 1
        sta     stream_queue_cursor + 1
        lda     stream_second_queue_remaining
        sta     stream_queue_remaining
        lda     stream_second_queue_remaining + 1
        sta     stream_queue_remaining + 1
        lda     stream_third_queue_pending
        beq     @second_queue_drained
        lda     stream_third_queue_cursor
        sta     stream_second_queue_cursor
        lda     stream_third_queue_cursor + 1
        sta     stream_second_queue_cursor + 1
        lda     stream_third_queue_remaining
        sta     stream_second_queue_remaining
        lda     stream_third_queue_remaining + 1
        sta     stream_second_queue_remaining + 1
        stz     stream_third_queue_pending
        stz     stream_third_queue_set
        bra     @queue_advanced
@second_queue_drained:
        stz     stream_second_queue_pending
        stz     stream_second_queue_set
        bra     @queue_advanced
@queue_drained:
        stz     stream_queue_pending
        stz     stream_queue_set
@queue_advanced:
        stz     stream_high_nibble
        bra     @not_ours
@finish:
        stz     TIM3CTLA
        stz     stream_playing
        stz     stream_source_set
        stz     stream_queue_set
        stz     stream_queue_pending
        stz     stream_second_queue_set
        stz     stream_second_queue_pending
        stz     stream_third_queue_set
        stz     stream_third_queue_pending
        stz     VOICE_CHANNEL_CONTROL
        stz     VOICE_OUTPUT
        jsr     restore_irq_vector
@not_ours:
        pla
        plx
        ply
        rti

restore_irq_vector:
        lda     stream_fast_irq_set
        beq     @done
        lda     stream_previous_irq
        sta     INTVECTL
        lda     stream_previous_irq + 1
        sta     INTVECTH
        stz     stream_fast_irq_set
@done:  rts

.macro add_difference difference_low, difference_high, next_index
        .local  store_add
        clc
        lda     decode_predictor
        adc     difference_low,y
        sta     decode_predictor
        lda     decode_predictor + 1
        adc     difference_high,y
        bvc     store_add
        lda     #$ff
        sta     decode_predictor
        lda     #$7f
store_add:
        sta     decode_predictor + 1
        lda     next_index,y
        sta     decode_step_index
        jmp     decode_complete
.endmacro

.macro subtract_difference difference_low, difference_high, next_index
        .local  store_subtract
        sec
        lda     decode_predictor
        sbc     difference_low,y
        sta     decode_predictor
        lda     decode_predictor + 1
        sbc     difference_high,y
        bvc     store_subtract
        stz     decode_predictor
        lda     #$80
store_subtract:
        sta     decode_predictor + 1
        lda     next_index,y
        sta     decode_step_index
        jmp     decode_complete
.endmacro

decode_nibble:
        and     #$0f
        asl
        tax
        ldy     decode_step_index
        jmp     (decode_jump_table,x)

decode_add0:
        add_difference difference_0_low, difference_0_high, next_index_minus_one
decode_add1:
        add_difference difference_1_low, difference_1_high, next_index_minus_one
decode_add2:
        add_difference difference_2_low, difference_2_high, next_index_minus_one
decode_add3:
        add_difference difference_3_low, difference_3_high, next_index_minus_one
decode_add4:
        add_difference difference_4_low, difference_4_high, next_index_plus_two
decode_add5:
        add_difference difference_5_low, difference_5_high, next_index_plus_four
decode_add6:
        add_difference difference_6_low, difference_6_high, next_index_plus_six
decode_add7:
        add_difference difference_7_low, difference_7_high, next_index_plus_eight
decode_subtract0:
        subtract_difference difference_0_low, difference_0_high, next_index_minus_one
decode_subtract1:
        subtract_difference difference_1_low, difference_1_high, next_index_minus_one
decode_subtract2:
        subtract_difference difference_2_low, difference_2_high, next_index_minus_one
decode_subtract3:
        subtract_difference difference_3_low, difference_3_high, next_index_minus_one
decode_subtract4:
        subtract_difference difference_4_low, difference_4_high, next_index_plus_two
decode_subtract5:
        subtract_difference difference_5_low, difference_5_high, next_index_plus_four
decode_subtract6:
        subtract_difference difference_6_low, difference_6_high, next_index_plus_six
decode_subtract7:
        subtract_difference difference_7_low, difference_7_high, next_index_plus_eight
