# APS-044 character preview evidence

- Player source (locked v001): `assets/previews/aps044-player-preview.json`
- Enemy/boss source: `assets/previews/aps044-enemy-preview.json`
- Player generator (locked v001): `scripts/generate-aps044-player-preview.py`
- Sheet generator: `scripts/generate-aps044-character-sheets.py`
- Canvas: independent 16x16 fixed grids; sheets use exact 8x nearest-neighbor sprites on `#111122`
- Scope: preview only; no game screen, HUD/UI, runtime sprite, Gearlynx frame, ROM, or LNX

## Locked v001 player PNG SHA-256

| File | SHA-256 |
|---|---|
| `a-dark-8x.png` | `579e14a45713807261e025ae50b11e0008489a14fc61f0cd2a492aae68dcd9e1` |
| `a-dark.png` | `4dea3d93f42883368b6b1e28eaaba1e971906f2e0c669ccd0e4980c221b43926` |
| `a-transparent-8x.png` | `db9f98b72cb92c4622bcf9762d81d487001a84d6e8a9e40367b4d7720f37881d` |
| `a-transparent.png` | `429bd28826eab556f03f5e2e2263a1d3f1f89551169189f63d61ad35a86dbc01` |
| `b-dark-8x.png` | `6d31169b439aa5104655d72adf6608e3d9b39709e06c59ba0defb7f4d0daa613` |
| `b-dark.png` | `d37ca7ad659673ac0faa6469b9c58b28a5c4eceb050a21b8b4ab30db37ace7e5` |
| `b-transparent-8x.png` | `e06db89085ec0656ee065e1e98ae21ebbd4c6aca58f71fc8e1a9002830d7b078` |
| `b-transparent.png` | `89cd83951a3b9428db061a8a9ba740bcb401eec29c734219ccf040a5ff4a3523` |

## Enemy and boss fixed-grid metrics

| ID / grid | Cells | Roles | BBox | Fill | Spans | Runs | Longest role run | Silhouette / features |
|---|---:|---|---|---:|---|---:|---|---|
| `scout` / `aps044_scout_preview` | 73 | A=40, B=30, C=3 | 13x10 | 56.2% | 2/4/7/8/10/12/13 | 29 | A=8, B=3, C=1 | sensor wedge / sensor, shadow, wedge |
| `saucer` / `aps044_saucer_preview` | 65 | A=28, B=27, C=10 | 14x9 | 51.6% | 1/2/4/5/7/9/10/13/14 | 21 | A=9, B=4, C=10 | offset dome and rim / dome, rim, shadow |
| `dropper` / `aps044_dropper_preview` | 65 | A=29, B=33, C=3 | 12x12 | 45.1% | 1/2/4/6/8/9/10/12 | 33 | A=8, B=2, C=3 | claw and cargo pod / claw, pod, sensor |
| `fighter` / `aps044_fighter_preview` | 68 | A=39, B=27, C=2 | 15x10 | 45.3% | 1/2/3/4/5/6/8/10/14/15 | 27 | A=9, B=3, C=2 | banked wing and long nose / bank-wing, nose, nozzle |
| `bomber` / `aps044_bomber_preview` | 92 | A=47, B=41, C=4 | 14x10 | 65.7% | 6/7/8/9/11/12/13/14 | 37 | A=9, B=6, C=4 | armored pod and bomb bay / armor, bay, pod |
| `supply` / `aps044_supply_preview` | 69 | A=32, B=34, C=3 | 13x10 | 53.1% | 2/4/5/6/9/11/13 | 30 | A=9, B=3, C=3 | cargo frame and lock / antenna, cargo, lock |
| `cave_bat` / `aps044_cave_bat_preview` | 53 | B=23, D=22, E=8 | 16x11 | 30.1% | 1/2/4/6/8/10/12/14/16 | 35 | B=2, D=3, E=4 | swept split wing / eye, membrane, wing |
| `rock_worm` / `aps044_rock_worm_preview` | 47 | B=24, D=11, E=12 | 16x10 | 29.4% | 1/2/3/4/6/7/8 | 30 | B=2, D=2, E=2 | segmented mineral drill / drill, seam, segment |
| `mining_drone` / `aps044_mining_drone_preview` | 66 | B=30, D=27, E=9 | 16x10 | 41.2% | 1/2/4/6/9/10/11/12 | 34 | B=3, D=6, E=4 | asymmetric drill chassis / chassis, core, drill |
| `coral_bastion` / `aps044_coral_bastion_preview` | 135 | A=75, B=48, C=8, F=4 | 13x15 | 69.2% | 1/7/9/10/12/13 | 69 | A=9, B=2, C=3, F=2 | coral spires, turret and reactor / reactor, slit, spires, turret |
| `amber_carrier` / `aps044_amber_carrier_preview` | 85 | A=43, B=36, C=4, F=2 | 14x11 | 55.2% | 1/2/6/8/10/13 | 40 | A=9, B=3, C=2, F=2 | bridge, nacelles and engines / bridge, engine, nacelle |
| `violet_geode` / `aps044_violet_geode_preview` | 98 | B=28, D=46, E=16, F=8 | 13x13 | 58.0% | 1/2/4/5/7/8/10/11/12/13 | 51 | B=2, D=5, E=4, F=3 | offset facets, nucleus and fissure / facet, fissure, nucleus |

## Sheet dimensions and SHA-256

| File | Pixels | Contents | SHA-256 |
|---|---:|---|---|
| `normal-enemies-sheet.png` | 432x456 | scout, saucer, dropper, fighter, bomber, supply, cave_bat, rock_worm, mining_drone | `59ebddfaa534a8ea527d0f7a6864ac27da9f7d8758b40c648bf03ffc359dd01c` |
| `bosses-sheet.png` | 432x152 | coral_bastion, amber_carrier, violet_geode | `a5273b14231c43c3b0b239b256e2ec88c57c97b8116649dbfa341e3642fff66d` |
| `all-characters-sheet.png` | 576x608 | player_a, player_b, scout, saucer, dropper, fighter, bomber, supply, cave_bat, rock_worm, mining_drone, coral_bastion, amber_carrier, violet_geode | `c83f80e8b57052816ae7bb46a2a057b4eb9f81acc454845938798ff21326866b` |

## Sheet positions

| Sheet | ID | Cell (row, col) | Sprite box x/y/w/h | Label box x/y/w/h |
|---|---|---:|---|---|
| `normal-enemies-sheet.png` | `scout` | 0,0 | 8/8/128/128 | 53/138/38/10 |
| `normal-enemies-sheet.png` | `saucer` | 0,1 | 152/8/128/128 | 193/138/46/10 |
| `normal-enemies-sheet.png` | `dropper` | 0,2 | 296/8/128/128 | 333/138/54/10 |
| `normal-enemies-sheet.png` | `fighter` | 1,0 | 8/160/128/128 | 45/290/54/10 |
| `normal-enemies-sheet.png` | `bomber` | 1,1 | 152/160/128/128 | 193/290/46/10 |
| `normal-enemies-sheet.png` | `supply` | 1,2 | 296/160/128/128 | 337/290/46/10 |
| `normal-enemies-sheet.png` | `cave_bat` | 2,0 | 8/312/128/128 | 41/442/62/10 |
| `normal-enemies-sheet.png` | `rock_worm` | 2,1 | 152/312/128/128 | 181/442/70/10 |
| `normal-enemies-sheet.png` | `mining_drone` | 2,2 | 296/312/128/128 | 313/442/94/10 |
| `bosses-sheet.png` | `coral_bastion` | 0,0 | 8/8/128/128 | 21/138/102/10 |
| `bosses-sheet.png` | `amber_carrier` | 0,1 | 152/8/128/128 | 165/138/102/10 |
| `bosses-sheet.png` | `violet_geode` | 0,2 | 296/8/128/128 | 313/138/94/10 |
| `all-characters-sheet.png` | `player_a` | 0,0 | 8/8/128/128 | 41/138/62/10 |
| `all-characters-sheet.png` | `player_b` | 0,1 | 152/8/128/128 | 185/138/62/10 |
| `all-characters-sheet.png` | `scout` | 0,2 | 296/8/128/128 | 341/138/38/10 |
| `all-characters-sheet.png` | `saucer` | 0,3 | 440/8/128/128 | 481/138/46/10 |
| `all-characters-sheet.png` | `dropper` | 1,0 | 8/160/128/128 | 45/290/54/10 |
| `all-characters-sheet.png` | `fighter` | 1,1 | 152/160/128/128 | 189/290/54/10 |
| `all-characters-sheet.png` | `bomber` | 1,2 | 296/160/128/128 | 337/290/46/10 |
| `all-characters-sheet.png` | `supply` | 1,3 | 440/160/128/128 | 481/290/46/10 |
| `all-characters-sheet.png` | `cave_bat` | 2,0 | 8/312/128/128 | 41/442/62/10 |
| `all-characters-sheet.png` | `rock_worm` | 2,1 | 152/312/128/128 | 181/442/70/10 |
| `all-characters-sheet.png` | `mining_drone` | 2,2 | 296/312/128/128 | 313/442/94/10 |
| `all-characters-sheet.png` | `coral_bastion` | 2,3 | 440/312/128/128 | 453/442/102/10 |
| `all-characters-sheet.png` | `amber_carrier` | 3,0 | 8/464/128/128 | 21/594/102/10 |
| `all-characters-sheet.png` | `violet_geode` | 3,1 | 152/464/128/128 | 169/594/94/10 |

Regeneration check: the three sheets were independently regenerated in a temporary directory and matched byte-for-byte. The locked v001 source, generator, and eight PNG files were SHA-256 checked and their pixels revalidated without rewriting them.

Unverified: human readability at native 16x16, Atari Lynx LCD persistence, and any later 12x10/runtime adaptation.
