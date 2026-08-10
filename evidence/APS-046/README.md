# APS-046 frame pacing / combatant evidence

- ROM: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`
- Version: `0.46.0`
- LNX: 59,532 bytes; SHA-256 `6d5c2a5e67da94fa4eba9b2164a2859ceee7a33d212e6d0f9c19eec0bf91c721`
- Capacity: normal enemy 8; normal+boss combatant 8; existing Stage initial/respawn 4; 9 rejected
- RAM: BSS `0xB093..0xB57F` = `0x4ED`; MAIN final used `0xB580`; C stack `0xB838`; 696 bytes remain
- Segments: CODE `0x93A7`; RODATA `0x1923`; DATA `0x131`; sprite RODATA `0x4DD` unchanged

## Frame pacing

`frame-pacing-gearlynx.json` records 0/4/8 injected active combatants for 75 consecutive completed hardware frames each. Every stop is `_game_frame_end_complete`, immediately after `GAME_FRAME_END_WAIT(tgi_busy())`. Observed combatant count stayed exactly 0/4/8. The verifier rejected 8 normal + 1 boss before memory injection.

Timer 0 HBLANK was enabled/reloading at 1 MHz (`backup=0x7E`, `control_a=0x18`). Timer 2 VBLANK was enabled/reloading, linked to Timer 0 and interrupting (`backup=0x68`, `control_a=0x9F`). These hardware completions are the correctness criterion. MCP debugger read/write and breakpoint round trips made wall samples 75.646–309.146 ms with medians 210.860/250.288/295.043 ms, so they are explicitly advisory and not treated as 12–15 ms real-time samples.

Host instrumentation passed 0/4/8 frame-end wait reachability, under-budget wait, overrun immediate completion, and 75 draw / 300 logic / 75 sound. Activity/count tests cover 0/1/4/8 normal, boss, 7+boss, 9 rejection, screen-off pre-spawn exclusion, collision, respawn, drop, score, fire, phase clearing, and input.

## Gearlynx visual verification

Headless and GUI Stage 1–3 NORMAL/CAST/BOSS verification each passed twice. Corresponding PNG files are byte-identical and retain APS-045 hashes.

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

Individual sprite hashes also match APS-045: player `ab30d247...`, scout `ddd7f67f...`, saucer `7e07769f...`, dropper `a16be4bf...`, fighter `11b18ce9...`, bomber `f598d999...`, supply `7d414f46...`, cave bat `13014dfc...`, rock worm `df64a55a...`, mining drone `bd2bd59b...`, coral bastion `7bbc393a...`, amber carrier `a4fb0719...`, violet geode `951d818a...`.

## Audio/state regression

- Title: 17,408 Timer 3 IRQ and reference-identical DAC samples, underrun 0, stop zero, 38 post-voice ticks, then Stage 1/channel A.
- GAME OVER: 11,691 IRQ/reference-identical DAC samples, underrun 0, input gate and release/press TITLE return.
- Channel A: 6 pitch changes/8 s; channel C: 3/20 s; channel B: 6/8 s. All observed logical volumes matched 75% MIKEY gain.
- Screenshot SHA-256: title `60bb376c1e73b45744afb79dd0de1b1226aa3d4c35ddbc34ffdfb7112d9424ab`; GAME OVER `c64d9bfeed8f686e177bb454d36eec938ebe7585e8e0dc39faf7c812a509e0d7`; active GAME OVER `52d57f5ba7286562b9765e020c060c087838dbf1534a0186e397d3147926fc8a`; A `87f4b069f1a99f9120a4d17fc531373a8d7c9079009c0ff81c766ac14352bb73`; C `87f4b069f1a99f9120a4d17fc531373a8d7c9079009c0ff81c766ac14352bb73`; B `f570eb2b6cfd691b059c2024b182fc4d39e2ff15efb2ba65b2c9701548baa354`.

## Host/build verification

- `make clean && ./scripts/verify.sh`: stage 44, game 609, sound 351, IMA 14,949, sprite 770; strict C89, cc65 warnings-as-errors, voice/gain/cart/LNX passed.
- ASan/UBSan: game 609, sound 351, IMA 14,949, sprite 770, smoke 19 passed.
- `make smoke-host`: 19 passed. `make perf-host`: passed; sync 75 draw / 300 logic / 75 sound, 299.64 Hz, game speed x1.00.
- Five Python verifiers compiled; `git diff --check` passed.

Unverified: Atari Lynx hardware 13.333 ms pacing and 8-combatant overrun margin, LCD persistence/readability, Lynx I/II differences, physical-speaker audio, IRQ cycle margin, and long-duration hardware playthrough.
