# APS-045 runtime sprite evidence

- ROM: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`
- LNX: 60,217 bytes; SHA-256 `c0fae56ce368e17a162695045f50a1f6415c59e2c2e4523ddcfa3ed3dc71cd39`
- Version: `0.45.0`
- Sprite source: `assets/stages/stages.json`; canonical `tests/golden/sprite-data-v045.json`; snapshot SHA-256 `0656310e1b41f06c1b6a3ec22d1f07a98cf20bac4da2deed50030ec937963481`
- Runtime contract: 13 IDs, 26 distinct frames, player `12x10 / 8x6`, normal enemy `12x12 / 8x8`, boss visual/collision unchanged, fixed hardware roles, exact 282 horizontal runs
- Capacity: `sprite_data.o` RODATA `0x4DD` = 1,245 bytes; BSS `0x4ED` = 1,261 bytes at `0xB340..0xB82C`; MAIN final used `0xB82D`, limit `0xB837`; C stack `0xB838`; 11 bytes remain
- Baseline delta: LNX `60,217 -> 60,217` (0), sprite RODATA `1,245 -> 1,245` (0), runs `282 -> 282` (0), BSS/MAIN/stack unchanged

## Gearlynx visual verification

`python3 scripts/verify-stage-visuals-gearlynx.py --output-dir evidence/APS-045` and the `--gui --output-dir evidence/APS-045/gui` variant each passed two consecutive final runs. Both modes verified Stage 1-3 NORMAL/CAST/BOSS, generated 32-byte hardware palettes, active boss and collision readback, and every non-empty runtime sprite pixel against the authoring grid. The corresponding 22 headless/GUI PNG files are byte-identical.

An initial GUI run exposed a stale front-buffer capture (`stage1-normal.png` lacked the valid in-memory player/enemies). The verifier now synchronizes two complete post-logic/pre-draw sound-to-next-logic handoffs before capture. After this capture-only fix, both final headless runs and both final GUI runs produced identical hashes.

### Individual sprite SHA-256

| Sprite | SHA-256 |
|---|---|
| player | `ab30d24708570d919b3ea25d1c96b0ea235ebcd7cd95ee51b5c878ba496d6363` |
| scout | `ddd7f67f3a6b8c7b6a32400931e31bc03f77be1df912544e5dc62c7f79e9b25d` |
| saucer | `7e07769f6014196dca6544a81ec06a0674c56e7a70735ba01f1e6d2695164b71` |
| dropper | `a16be4bf4a97542cad54ee0dd605d570ec184f198bb64aacc196ddc111b9be35` |
| fighter | `11b18ce9e5313a57aade0f68b38d0cf32ebab990241bd28307ad43b7f1b1e949` |
| bomber | `f598d99987656f17bf8a4b5826e93e8c55c209d6a834556afa43145fb74cec17` |
| supply | `7d414f466d9def8c753084d96d5da2cc4fd408093c715c8d07c69996601725eb` |
| cave_bat | `13014dfc56f7c06fa75cfc6f2a1877ec26ec2ec2134b87da587b86870e72956f` |
| rock_worm | `df64a55a0e6fde5431d35f273a7fcd65529785d7fef1894a112d2b5694332424` |
| mining_drone | `bd2bd59ba601887b74a6b35222de6a31bd301bf2fd714fd09d0a32cf375ff340` |
| coral_bastion | `7bbc393ae901c63df90b47e45c15371c9267f08ae98b9e21497ced5b3baacd1f` |
| amber_carrier | `a4fb0719d1cf4672bf0a384ebaac1cce5b260fb22b5a6f3afe18dd8622cd8d27` |
| violet_geode | `951d818ae4f6a09b26bfe05cae9ec91ed69e4390d0d42c2657aebc4341e5f26f` |

### Full-screen SHA-256

| Capture | SHA-256 |
|---|---|
| stage1-normal | `1a4faf57d821638612019fff2f5aa01995f0f8d52ca807afb152e9b5929c3d27` |
| stage1-cast | `6dfa85e3c72b103b75172f82ffcfeb79fb5a4168f74f218074cfa9fd4f87f552` |
| stage1-boss | `26e6c8b816717f7fd9754aabfeed9d756f9b38459ba17c32bd57061629cb94d7` |
| stage2-normal | `2a67d68fa9c12ab86c48a3cb606dee9294bfd306cb26b108d738324039c50155` |
| stage2-cast | `8a1ee1fd9ce3b7a125df302443236c418b4e0252269b6c5c72b747b411e44196` |
| stage2-boss | `a3fe3e5295cf0edec9144e4de338d2aee4917ceed0c65ef0dbc0d4d04c65169a` |
| stage3-normal | `33772d30966ba436573e395f043ca85d63ec0e7627ef7394f769baabfe3024f3` |
| stage3-cast | `9b6ba4d928d640e1270dafa37f22416695b6a1680af6b7ebabb383201eaf7605` |
| stage3-boss | `bc1c8e495d89928748335f3ca582be3a0409b9565881872c76705172b8a6b689` |

## Audio/state regression

- Title: Timer 3 backup `0x7D`, 17,408 IRQ and 17,408 reference-identical DAC samples, underrun 0, stop zero, wait trace `38..0` with exactly 38 transitions, then Stage 1 and channel A BGM start.
- GAME OVER: 11,691 IRQ/reference-identical DAC samples, underrun 0, A/C/B stopped during voice, release-to-arm then press-to-TITLE, held press stable for 8 polls.
- Channel A: 6 pitch changes in 8 seconds; channel C: 3 changes in 20 seconds; channel B: 6 changes in 8 seconds. Every observed logical volume mapped to the expected 75% MIKEY gain.
- Screenshots: `title-voice.png`, `game-over-voice.png`, `game-over-voice-active.png`, `channel-a.png`, `channel-b.png`, `channel-c.png`.

## Host/build verification

- `make clean && ./scripts/verify.sh`: stage 40, game 583, sound 351, IMA 14,949, sprite 770; strict C89, cc65 2.19 warnings-as-errors, shell syntax, voice/gain, LNX/cart checks all passed.
- ASan/UBSan: game 583, sound 351, IMA 14,949, sprite 770, smoke 10 passed.
- `make smoke-host`: 10 passed. `make perf-host`: 75 draw / 300 logic / 75 sound; sync 298.82 Hz; 5,000,000-frame paired medians legacy 1,557,021 us, optimized 1,547,751 us; paired delta median 11,098 us.
- `python3 -m py_compile scripts/generate-stage-data.py scripts/verify-stage-visuals-gearlynx.py` and `git diff --check`: passed.

Unverified: Atari Lynx hardware LCD readability/persistence, Lynx I/II differences, physical-speaker audio, IRQ cycle margin, and long-duration hardware playthrough.
