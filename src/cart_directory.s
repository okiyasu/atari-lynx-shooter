;
; Three-entry Lynx cartridge directory: resident executable plus cartridge-only
; title and GAME OVER voices. Entries 1/2 use the cc65 raw-cart file API.
;

        .include        "lynx.inc"
        .import         __STARTOFDIRECTORY__
        .import         __MAIN_START__
        .import         __CODE_SIZE__, __DATA_SIZE__, __RODATA_SIZE__
        .import         __STARTUP_SIZE__, __ONCE_SIZE__, __LOWCODE_SIZE__
        .import         __TITLEVOICE_SIZE__, __GAMEVOICE_SIZE__
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
__DIRECTORY_END__:
