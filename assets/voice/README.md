# Voice assets

`title-start.adpcm` and `game-over.adpcm` are generated locally from their
matching `.txt` files by `scripts/generate-title-voice.py`. The checked-in
artifacts are mono 8 kHz 4-bit IMA ADPCM, low nibble first, with predictor 0
and step index 0. Only the final ADPCM is linked into the ROM.

## Voice and synthesis

- Provider: VOICEVOX Nemo
- Official website label: `男性2` (CV かちょゴリラ)
- Engine speaker: `男声2`, UUID `7ecc7a17-1465-4b22-a3b5-842a110ff55e`
- Style: `ノーマル`, ID `10000`
- Settings: speed `0.9`, pitch `-0.08`, intonation `0.9`, volume `1.0`
- Output WAV: 8 kHz mono signed 16-bit PCM
- Inputs: title `わしは宇宙の帝王ザカリテ`; GAME OVER `お前は弱かった`
- Fixed credit: `VOICEVOX:Nemo（男性2）`

`make voice-generate` regenerates the title artifact and
`make voice-generate-game-over` regenerates the GAME OVER artifact while the
local Nemo engine is running. `make voice-check` performs an offline strict
check of both metadata/header/payload sets and pins both ADPCM SHA-256 values.
The metadata pins the synthesis-query hash, versions, installer provenance,
exact commands, platform architecture, and license review. The WAV and
normalized PCM SHA-256 values record the bytes produced by that generation run;
they are validated as SHA-256 provenance but are not required to match across
runs. VOICEVOX can vary raw PCM while the lossy IMA encoder still produces the
same checked-in ADPCM.
The generator deterministically replaces the engine's 0.1-second
post-phoneme tail with exactly 800 zero PCM samples before IMA encoding; this
keeps the natural engine output length. Cross-run reproducibility is required
at the ROM boundary: sample count, final ADPCM SHA-256, generated header, and
cartridge payload. `make voice-check` includes a host regression proving that
different PCM hashes can legitimately converge to identical ADPCM/sample-count/
header output.

## Local official distribution

- VOICEVOX editor: `0.25.2`, official macOS arm64 DMG SHA-256
  `4d532a84470c6d0cf713d2c5c6e6e5f8d2c36b18821055fd2c73386fcdfd6b91`
- VOICEVOX Nemo Engine: `0.24.0`, official macOS arm64 VVPP SHA-256
  `d67cbe5c8e23c0ee41a398e12e20b98de039a0eada944a3938bc6c3e39fc8f4f`
- Installed engine:
  `/Users/mammycloud-m4/Library/Application Support/voicevox/vvpp-engines/208cf94d-43d2-4cf5-abc0-9783cac36d29/0.24.0/run`
- Execution: arm64 native; Rosetta not used
- Synthesis transport: loopback HTTP at `127.0.0.1:50121` only; no external API

Exact download URLs, acquisition times, hashes, engine/generator commands, and
per-asset WAV/ADPCM details are recorded in `title-start.json` and
`game-over.json`.

## License

The VOICEVOX Nemo terms and VOICEVOX software terms were checked on
2026-08-09. Nemo-generated audio may be used commercially or non-commercially
when the required credit is shown. This project uses the fixed, more specific
credit `VOICEVOX:Nemo（男性2）` in the ROM and documentation. Restrictions and
source URLs are fixed in `LICENSE.md` and both asset metadata files.
