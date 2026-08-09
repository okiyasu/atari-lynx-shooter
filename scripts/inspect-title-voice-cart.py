#!/usr/bin/env python3
"""Validate both cartridge-only voice entries and payloads."""

import argparse
import hashlib
import struct
from pathlib import Path

LNX_HEADER_SIZE = 64
DIRECTORY_OFFSET = 0x00CB
BLOCK_SIZE = 0x0400


def entry(data, index):
    offset = LNX_HEADER_SIZE + DIRECTORY_OFFSET + index * 8
    block, block_offset, flags, destination, length = struct.unpack_from(
        "<BHBHH", data, offset
    )
    cartridge_offset = block * BLOCK_SIZE + block_offset
    return {
        "block": block,
        "block_offset": block_offset,
        "flags": flags,
        "destination": destination,
        "length": length,
        "cartridge_offset": cartridge_offset,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rom")
    parser.add_argument("--title-voice", default="assets/voice/title-start.adpcm")
    parser.add_argument("--game-over-voice", default="assets/voice/game-over.adpcm")
    args = parser.parse_args()
    rom = Path(args.rom).read_bytes()
    title_voice = Path(args.title_voice).read_bytes()
    game_over_voice = Path(args.game_over_voice).read_bytes()
    main_entry = entry(rom, 0)
    title_entry = entry(rom, 1)
    game_over_entry = entry(rom, 2)
    title_start = LNX_HEADER_SIZE + title_entry["cartridge_offset"]
    title_payload = rom[title_start : title_start + title_entry["length"]]
    game_over_start = LNX_HEADER_SIZE + game_over_entry["cartridge_offset"]
    game_over_payload = rom[
        game_over_start : game_over_start + game_over_entry["length"]
    ]

    if main_entry["flags"] != 0x88 or main_entry["destination"] != 0x0200:
        raise SystemExit("invalid executable directory entry")
    if title_entry["flags"] != 0 or title_entry["destination"] != 0:
        raise SystemExit("invalid title voice directory entry")
    if game_over_entry["flags"] != 0 or game_over_entry["destination"] != 0:
        raise SystemExit("invalid GAME OVER voice directory entry")
    if title_entry["cartridge_offset"] != (
        main_entry["cartridge_offset"] + main_entry["length"]
    ):
        raise SystemExit("title voice is not contiguous after resident executable")
    if game_over_entry["cartridge_offset"] != (
        title_entry["cartridge_offset"] + title_entry["length"]
    ):
        raise SystemExit("GAME OVER voice is not contiguous after title voice")
    if title_entry["length"] != len(title_voice) or title_payload != title_voice:
        raise SystemExit("title voice payload does not match checked-in ADPCM")
    if (game_over_entry["length"] != len(game_over_voice) or
            game_over_payload != game_over_voice):
        raise SystemExit("GAME OVER voice payload does not match checked-in ADPCM")
    if game_over_start + len(game_over_payload) != len(rom):
        raise SystemExit("unexpected bytes follow the GAME OVER voice payload")

    for name, directory_entry, payload in (
        ("title", title_entry, title_payload),
        ("game-over", game_over_entry, game_over_payload),
    ):
        print(
            "{} voice cart entry OK: block={} offset={} cart_offset={} length={} "
            "sha256={}".format(
                name,
                directory_entry["block"],
                directory_entry["block_offset"],
                directory_entry["cartridge_offset"],
                directory_entry["length"],
                hashlib.sha256(payload).hexdigest(),
            )
        )


if __name__ == "__main__":
    main()
