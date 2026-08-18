;
; Seven-entry Lynx cartridge directory: resident executable, cartridge-only
; title and GAME OVER voices, and four scene-exclusive static layer overlay
; groups (APS-053 T2, docs/plan/2026-08-17-ram-reclamation.md §4). Entries
; 1-6 use the cc65 raw-cart file API.
;

        .include        "lynx.inc"
        .import         __STARTOFDIRECTORY__
        .import         __MAIN_START__
        .import         __CODE_SIZE__, __DATA_SIZE__, __RODATA_SIZE__
        .import         __STARTUP_SIZE__, __ONCE_SIZE__, __LOWCODE_SIZE__
        .import         __TITLEVOICE_SIZE__, __GAMEVOICE_SIZE__
        .import         __OVERLAYSTAGE1_SIZE__, __OVERLAYSTAGE2_SIZE__
        .import         __OVERLAYSTAGE3_SIZE__, __OVERLAYTITLE_SIZE__
        .import         __BANK0BLOCKSIZE__
        .export         __DEFDIR__: absolute = 1

        .segment        "DIRECTORY"

__DIRECTORY_START__:
off0 = __STARTOFDIRECTORY__ + (__DIRECTORY_END__ - __DIRECTORY_START__)
len0 = __STARTUP_SIZE__ + __ONCE_SIZE__ + __CODE_SIZE__ + __DATA_SIZE__ + __RODATA_SIZE__ + __LOWCODE_SIZE__
block0 = off0 / __BANK0BLOCKSIZE__
        .byte   <block0
        .word   off0 & (__BANK0BLOCKSIZE__ - 1)
        .byte   $88
        .word   __MAIN_START__
        .word   len0

off1 = off0 + len0
block1 = off1 / __BANK0BLOCKSIZE__
        .byte   <block1
        .word   off1 & (__BANK0BLOCKSIZE__ - 1)
        .byte   $00
        .word   $0000
        .word   __TITLEVOICE_SIZE__

off2 = off1 + __TITLEVOICE_SIZE__
block2 = off2 / __BANK0BLOCKSIZE__
        .byte   <block2
        .word   off2 & (__BANK0BLOCKSIZE__ - 1)
        .byte   $00
        .word   $0000
        .word   __GAMEVOICE_SIZE__

off3 = off2 + __GAMEVOICE_SIZE__
block3 = off3 / __BANK0BLOCKSIZE__
        .byte   <block3
        .word   off3 & (__BANK0BLOCKSIZE__ - 1)
        .byte   $00
        .word   $0000
        .word   __OVERLAYSTAGE1_SIZE__

off4 = off3 + __OVERLAYSTAGE1_SIZE__
block4 = off4 / __BANK0BLOCKSIZE__
        .byte   <block4
        .word   off4 & (__BANK0BLOCKSIZE__ - 1)
        .byte   $00
        .word   $0000
        .word   __OVERLAYSTAGE2_SIZE__

off5 = off4 + __OVERLAYSTAGE2_SIZE__
block5 = off5 / __BANK0BLOCKSIZE__
        .byte   <block5
        .word   off5 & (__BANK0BLOCKSIZE__ - 1)
        .byte   $00
        .word   $0000
        .word   __OVERLAYSTAGE3_SIZE__

off6 = off5 + __OVERLAYSTAGE3_SIZE__
block6 = off6 / __BANK0BLOCKSIZE__
        .byte   <block6
        .word   off6 & (__BANK0BLOCKSIZE__ - 1)
        .byte   $00
        .word   $0000
        .word   __OVERLAYTITLE_SIZE__
__DIRECTORY_END__:
