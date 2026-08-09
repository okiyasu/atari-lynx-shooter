;
; APS-031 minimal MIKEY direct-PCM feasibility backend.
;
; A timer-3 interrupt writes one resident signed 8-bit sample to channel D's
; direct-output register every 125 us (8 kHz). The normal BGM/SFX backend owns
; channels A/C/B; this module never writes those channels, timers 0/2/7, or
; display registers. No sample is bundled and game flow does not call this
; prototype yet.
;

        .export         _pcm_stream_set_source
        .export         _pcm_stream_set_queue_source
        .export         _pcm_stream_start
        .export         _pcm_stream_queue
        .export         _pcm_stream_stop
        .export         _pcm_stream_is_playing
        .export         _pcm_stream_can_queue
        .interruptor    pcm_stream_irq

        .include        "lynx.inc"

PCM_OUTPUT             = AUD3OUT
PCM_CHANNEL_CONTROL    = AUD3CTLA
PCM_TIMER_RELOAD       = 125
PCM_TIMER_CONTROL      = $D8

        .zeropage
pcm_stream_cursor:     .res 2
pcm_stream_queue_cursor: .res 2

        .bss
pcm_stream_remaining:  .res 2
pcm_stream_playing:    .res 1
pcm_stream_source_set: .res 1
pcm_stream_queue_remaining: .res 2
pcm_stream_queue_set:  .res 1
pcm_stream_queue_pending: .res 1

        .code

; void __fastcall__ pcm_stream_set_source(const unsigned char* source);
; AX = resident source pointer. Replacing a source stops any active stream.
_pcm_stream_set_source:
        php
        sei
        stz     TIM3CTLA
        stz     pcm_stream_playing
        stz     pcm_stream_queue_pending
        stz     pcm_stream_queue_set
        stz     PCM_CHANNEL_CONTROL
        stz     PCM_OUTPUT
        sta     pcm_stream_cursor
        stx     pcm_stream_cursor + 1
        stz     pcm_stream_source_set
        txa
        ora     pcm_stream_cursor
        beq     @done
        lda     #$ff
        sta     pcm_stream_source_set
@done:  plp
        rts

; void __fastcall__ pcm_stream_start(unsigned length);
; AX = byte length. Source must have been supplied by set_source.
_pcm_stream_start:
        php
        sei
        pha
        lda     pcm_stream_playing
        beq     @begin
        pla
        plp
        rts

@begin: pla
        stz     TIM3CTLA
        stz     pcm_stream_playing
        stz     PCM_CHANNEL_CONTROL
        stz     PCM_OUTPUT
        sta     pcm_stream_remaining
        stx     pcm_stream_remaining + 1
        txa
        ora     pcm_stream_remaining
        beq     @invalid
        lda     pcm_stream_source_set
        beq     @invalid
        lda     #$ff
        sta     pcm_stream_playing
        lda     #PCM_TIMER_RELOAD
        sta     TIM3BKUP
        sta     TIM3CNT
        lda     #PCM_TIMER_CONTROL
        sta     TIM3CTLA
@done:  plp
        rts
@invalid:
        stz     pcm_stream_source_set
        stz     pcm_stream_queue_pending
        stz     pcm_stream_queue_set
        bra     @done

; void __fastcall__ pcm_stream_set_queue_source(const unsigned char* source);
; AX = resident queued source pointer. Ignored while a queued buffer exists.
_pcm_stream_set_queue_source:
        php
        sei
        pha
        lda     pcm_stream_queue_pending
        beq     @queue_source
        pla
        plp
        rts
@queue_source:
        pla
        sta     pcm_stream_queue_cursor
        stx     pcm_stream_queue_cursor + 1
        stz     pcm_stream_queue_set
        txa
        ora     pcm_stream_queue_cursor
        beq     @queue_source_done
        lda     #$ff
        sta     pcm_stream_queue_set
@queue_source_done:
        plp
        rts

; unsigned char __fastcall__ pcm_stream_queue(unsigned length);
; AX = byte length. Returns non-zero when the next buffer was accepted.
_pcm_stream_queue:
        php
        sei
        pha
        lda     pcm_stream_queue_pending
        bne     @queue_reject
        lda     pcm_stream_queue_set
        beq     @queue_reject
        pla
        sta     pcm_stream_queue_remaining
        stx     pcm_stream_queue_remaining + 1
        txa
        ora     pcm_stream_queue_remaining
        beq     @queue_empty
        lda     #$ff
        sta     pcm_stream_queue_pending
        plp
        lda     #$01
        ldx     #$00
        rts
@queue_reject:
        pla
@queue_empty:
        plp
        lda     #$00
        ldx     #$00
        rts

; void pcm_stream_stop(void);
_pcm_stream_stop:
        php
        sei
        stz     TIM3CTLA
        stz     pcm_stream_playing
        stz     pcm_stream_source_set
        stz     pcm_stream_queue_pending
        stz     pcm_stream_queue_set
        stz     PCM_CHANNEL_CONTROL
        stz     PCM_OUTPUT
        plp
        rts

; unsigned char pcm_stream_is_playing(void);
_pcm_stream_is_playing:
        lda     pcm_stream_playing
        ldx     #0
        rts

; unsigned char pcm_stream_can_queue(void);
_pcm_stream_can_queue:
        lda     pcm_stream_queue_pending
        eor     #$ff
        ldx     #0
        rts

; Feed channel D when timer 3 is pending. Carry remains clear so cc65's IRQ
; chain can service the TGI VBL handler during the same IRQ pass.
pcm_stream_irq:
        lda     pcm_stream_playing
        beq     @not_ours
        lda     INTSET
        and     #TIMER3_INTERRUPT
        beq     @not_ours
        lda     (pcm_stream_cursor)
        sta     PCM_OUTPUT
        inc     pcm_stream_cursor
        bne     @decrement
        inc     pcm_stream_cursor + 1
@decrement:
        lda     pcm_stream_remaining
        bne     @low
        dec     pcm_stream_remaining + 1
@low:   dec     pcm_stream_remaining
        lda     pcm_stream_remaining
        ora     pcm_stream_remaining + 1
        bne     @not_ours
        lda     pcm_stream_queue_pending
        beq     @finish
        lda     pcm_stream_queue_cursor
        sta     pcm_stream_cursor
        lda     pcm_stream_queue_cursor + 1
        sta     pcm_stream_cursor + 1
        lda     pcm_stream_queue_remaining
        sta     pcm_stream_remaining
        lda     pcm_stream_queue_remaining + 1
        sta     pcm_stream_remaining + 1
        stz     pcm_stream_queue_pending
        stz     pcm_stream_queue_set
        bra     @not_ours
@finish:
        stz     TIM3CTLA
        stz     pcm_stream_playing
        stz     pcm_stream_source_set
        stz     pcm_stream_queue_set
        stz     PCM_CHANNEL_CONTROL
        stz     PCM_OUTPUT
@not_ours:
        clc
        rts
