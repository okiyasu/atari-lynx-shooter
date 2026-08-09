;
; Cartridge-only data. The custom linker configuration keeps both segments out
; of resident RAM and exposes them as Lynx directory entries 1 and 2.
;

        .segment        "TITLEVOICE"
        .incbin         "assets/voice/title-start.adpcm"

        .segment        "GAMEVOICE"
        .incbin         "assets/voice/game-over.adpcm"
