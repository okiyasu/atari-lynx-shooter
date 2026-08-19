SHELL := /bin/sh

CC65_VERSION := 2.19
TOOLCHAIN_ROOT := $(CURDIR)/.cache/cc65-$(CC65_VERSION)/install
CL65 := $(TOOLCHAIN_ROOT)/bin/cl65
CC65_HOME := $(TOOLCHAIN_ROOT)/share/cc65
export CC65_HOME
HOST_CC ?= clang
GEN_DIR := build/gen
HOST_CFLAGS := -std=c89 -pedantic -Wall -Wextra -Werror \
	-DGAME_COMBATANT_INSTRUMENT -Iinclude -I$(GEN_DIR)
ROM_CFLAGS := -t lynx -Oirs --standard cc65 -W error -Iinclude -I$(GEN_DIR)
COMPACT_ROM_CFLAGS := -t lynx -O --standard cc65 -W error -Iinclude -I$(GEN_DIR)
ROM := dist/asteroid-patrol.lnx
CADENCE_ROM := dist/asteroid-patrol-cadence.lnx
CADENCE_VARIANT_A_ROM := dist/asteroid-patrol-cadence-v-a.lnx
CADENCE_VARIANT_B_ROM := dist/asteroid-patrol-cadence-v-b.lnx
CADENCE_VARIANT_C_ROM := dist/asteroid-patrol-cadence-v-c.lnx
CADENCE_CFG := cfg/lynx-voice-cadence.cfg
COMMON_ROM_OBJECTS := build/game.o build/sound.o \
	build/title_voice.o \
	build/title_voice_stream.o build/music_data.o build/stage_data.o \
	build/sprite_data.o build/static_layer_data.o \
	build/static_layer_overlay.o build/static_layer_overlay_asset.o \
	build/title_voice_asset.o build/game_timing.o
ROM_OBJECTS := build/cart_directory.o build/main.o build/static_layer.o \
	$(COMMON_ROM_OBJECTS)
CADENCE_OBJECTS := build/cart_directory.o build/main-cadence.o $(COMMON_ROM_OBJECTS) \
	build/static_layer-cadence.o \
	build/cadence_probe.o \
	build/scb_split_probe.o
CADENCE_VARIANT_COMMON_OBJECTS := $(filter-out build/main-cadence.o,$(CADENCE_OBJECTS))
MUSIC_DATA := $(GEN_DIR)/music_data.c
STAGE_INPUT := assets/stages/stages.json
STAGE_GENERATOR := scripts/generate-stage-data.py
STAGE_GOLDEN := tests/golden/stage-data-v034.json
SPRITE_GOLDEN := tests/golden/sprite-data-v050.json
STAGE_STAMP := $(GEN_DIR)/.stage-data.stamp
STAGE_DATA := $(GEN_DIR)/stage_data.c $(GEN_DIR)/stage_data.h \
	$(GEN_DIR)/sprite_data.c $(GEN_DIR)/sprite_data.h
MUSIC_SOURCES := assets/music/stage1.mml assets/music/stage2.mml \
	assets/music/stage3.mml assets/music/stage1_bass.mml \
	assets/music/stage2_bass.mml assets/music/stage3_bass.mml
MUSIC_TRACKS := stage_one=assets/music/stage1.mml \
	stage_two=assets/music/stage2.mml \
	stage_three=assets/music/stage3.mml \
	stage_one_bass=assets/music/stage1_bass.mml \
	stage_two_bass=assets/music/stage2_bass.mml \
	stage_three_bass=assets/music/stage3_bass.mml
PERF_WORKLOAD_FRAMES := 5000000
PERF_PAIR_COUNT := 7

.PHONY: all toolchain rom debug-contract clean test stage-check smoke-host smoke-gearlynx \
	perf-host frame-cadence-gearlynx lint verify inspect voice-generate \
	voice-generate-game-over voice-check static-layer-readback-gearlynx \
	title-game-over-readback-gearlynx \
	frame-cadence-variants-gearlynx phase-2r-gate-a-gearlynx \
	phase-2r-o5-gearlynx phase-2r-audio-diagnostics-gearlynx \
	phase-2r-section-profile-gearlynx phase-2r-logic-profile-gearlynx \
	phase-2r-display-profile-gearlynx \
	phase-2r-display-profile-no-reinject-gearlynx \
	phase-2r-catchup-causality-gearlynx \
	phase-2r-bounded-catchup-gearlynx aps053-diagnostic-rom-gearlynx \
	phase-3r-tick-calibration-gearlynx phase-3r-gate-a-gearlynx

all: verify

toolchain:
	./scripts/install-cc65.sh

rom: $(ROM)

debug-contract: build/static_layer-debug.o

build/static_layer-debug.o: src/static_layer.c include/static_layer.h \
		include/static_layer_data.h include/static_layer_overlay.h \
		include/static_layer_overlay_data.h include/game.h \
		include/title_voice.h | toolchain
	mkdir -p build
	$(CL65) $(COMPACT_ROM_CFLAGS) -DSTATIC_LAYER_DEBUG_ASSERT -c -o $@ src/static_layer.c

$(ROM): $(ROM_OBJECTS) | toolchain
	mkdir -p dist build
	$(CL65) -t lynx -C cfg/lynx-voice.cfg -m build/asteroid-patrol.map \
		-Ln build/asteroid-patrol.lbl -o $@ $(ROM_OBJECTS)

$(CADENCE_ROM): $(CADENCE_OBJECTS) $(CADENCE_CFG) | toolchain
	mkdir -p dist build
	$(CL65) -t lynx -C $(CADENCE_CFG) -m build/asteroid-patrol-cadence.map \
		-Ln build/asteroid-patrol-cadence.lbl -o $@ $(CADENCE_OBJECTS)

build/cart_directory.o: src/cart_directory.s cfg/lynx-voice.cfg | toolchain
	mkdir -p build
	$(CL65) -t lynx -c -o $@ src/cart_directory.s

build/main.o: src/main.c include/game.h include/sound.h include/title_voice.h \
		include/version.h include/game_timing.h \
		include/static_layer.h include/static_layer_data.h \
		$(GEN_DIR)/stage_data.h $(GEN_DIR)/sprite_data.h | toolchain
	mkdir -p build
	$(CL65) $(COMPACT_ROM_CFLAGS) -c -o $@ src/main.c

build/main-cadence.o: src/main.c include/game.h include/sound.h \
		include/title_voice.h include/version.h include/game_timing.h \
		include/static_layer.h include/static_layer_data.h \
		include/cadence_probe.h include/scb_split_probe.h \
		$(GEN_DIR)/stage_data.h $(GEN_DIR)/sprite_data.h | toolchain
	mkdir -p build
	$(CL65) $(COMPACT_ROM_CFLAGS) -DCADENCE_PROBE -c -o $@ src/main.c

build/cadence_probe.o: src/cadence_probe.s | toolchain
	mkdir -p build
	$(CL65) -t lynx -c -o $@ src/cadence_probe.s

build/scb_split_probe.o: src/scb_split_probe.s | toolchain
	mkdir -p build
	$(CL65) -t lynx -c -o $@ src/scb_split_probe.s

build/game_timing.o: src/game_timing.s include/game_timing.h | toolchain
	mkdir -p build
	$(CL65) -t lynx -c -o $@ src/game_timing.s

build/static_layer.o: src/static_layer.c include/static_layer.h \
		include/static_layer_data.h include/static_layer_overlay.h \
		include/static_layer_overlay_data.h include/game.h \
		include/title_voice.h | toolchain
	mkdir -p build
	$(CL65) $(COMPACT_ROM_CFLAGS) -c -o $@ src/static_layer.c

build/static_layer-cadence.o: src/static_layer.c include/static_layer.h \
		include/static_layer_data.h include/static_layer_overlay.h \
		include/static_layer_overlay_data.h include/game.h \
		include/title_voice.h | toolchain
	mkdir -p build
	$(CL65) $(COMPACT_ROM_CFLAGS) -DCADENCE_PROBE -c -o $@ src/static_layer.c

build/static_layer_data.o: src/static_layer_data.c include/static_layer_data.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/static_layer_data.c

build/static_layer_overlay.o: src/static_layer_overlay.c \
		include/static_layer_overlay.h \
		include/static_layer_overlay_data.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/static_layer_overlay.c

build/static_layer_overlay_asset.o: src/static_layer_overlay_asset.s \
		assets/overlay/stage1.bin assets/overlay/stage2.bin \
		assets/overlay/stage3.bin assets/overlay/title.bin | toolchain
	mkdir -p build
	$(CL65) -t lynx -c -o $@ src/static_layer_overlay_asset.s

build/game.o: src/game.c include/game.h include/sound.h \
		$(GEN_DIR)/stage_data.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/game.c

build/sound.o: src/sound.c include/sound.h $(MUSIC_DATA) | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/sound.c

build/ima_adpcm.o: src/ima_adpcm.c include/ima_adpcm.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/ima_adpcm.c

build/pcm_stream.o: src/pcm_stream.s include/pcm_stream.h | toolchain
	mkdir -p build
	$(CL65) -t lynx -c -o $@ src/pcm_stream.s

build/title_voice.o: src/title_voice.c include/title_voice.h \
		include/title_voice_data.h include/game_over_voice_data.h \
		include/title_voice_stream.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/title_voice.c

build/title_voice_stream.o: src/title_voice_stream.s src/title_voice_delta.inc \
		src/title_voice_gain.inc \
		include/title_voice_stream.h | toolchain
	mkdir -p build
	$(CL65) -t lynx -c -o $@ src/title_voice_stream.s

build/title_voice_asset.o: src/title_voice_asset.s \
		assets/voice/title-start.adpcm assets/voice/game-over.adpcm | toolchain
	mkdir -p build
	$(CL65) -t lynx -c -o $@ src/title_voice_asset.s

build/music_data.o: $(MUSIC_DATA) include/sound.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ $(MUSIC_DATA)

build/stage_data.o: $(GEN_DIR)/stage_data.c $(GEN_DIR)/stage_data.h \
		include/game.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ $(GEN_DIR)/stage_data.c

build/sprite_data.o: $(GEN_DIR)/sprite_data.c $(GEN_DIR)/sprite_data.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ $(GEN_DIR)/sprite_data.c

build/mml2c: tools/mml2c.c
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tools/mml2c.c

$(MUSIC_DATA): build/mml2c $(MUSIC_SOURCES) include/sound.h
	mkdir -p $(GEN_DIR)
	./build/mml2c $(GEN_DIR)/music_data $(MUSIC_TRACKS)

$(STAGE_STAMP): $(STAGE_INPUT) $(STAGE_GENERATOR) $(STAGE_GOLDEN) $(SPRITE_GOLDEN)
	mkdir -p $(GEN_DIR)
	./$(STAGE_GENERATOR) generate --input $(STAGE_INPUT) \
		--golden $(STAGE_GOLDEN) --sprite-golden $(SPRITE_GOLDEN) \
		--output-dir $(GEN_DIR)
	touch $@

$(STAGE_DATA): $(STAGE_STAMP)

test: stage-check build/test-game build/test-sound build/test-ima-adpcm \
		build/test-sprite-data
	./build/test-game
	./build/test-sound
	./build/test-ima-adpcm
	./build/test-sprite-data

stage-check:
	./tests/test_stage_data.py

voice-generate:
	./scripts/generate-title-voice.py generate --asset title
	./scripts/generate-title-voice-delta.py
	./scripts/generate-title-voice-gain.py generate

voice-generate-game-over:
	./scripts/generate-title-voice.py generate --asset game-over

voice-check:
	./scripts/generate-title-voice-delta.py
	./scripts/generate-title-voice-gain.py verify
	./scripts/generate-title-voice.py verify

smoke-host: build/test-smoke
	./build/test-smoke

perf-host: build/perf-bench build/perf-bench-legacy build/test-game-legacy
	./build/test-game-legacy
	./build/perf-bench --sync
	./build/perf-bench --unthrottled
	./build/perf-bench-legacy --workload $(PERF_WORKLOAD_FRAMES)
	./build/perf-bench --workload $(PERF_WORKLOAD_FRAMES)
	@results=$$(mktemp "$${TMPDIR:-/tmp}/asteroid-perf.XXXXXX"); \
	trap 'rm -f "$$results"' 0 HUP INT TERM; \
	pair=1; \
	while [ $$pair -le $(PERF_PAIR_COUNT) ]; do \
		if [ $$((pair % 2)) -eq 1 ]; then \
			legacy=$$(./build/perf-bench-legacy --workload $(PERF_WORKLOAD_FRAMES) | sed -n 's/.*elapsed_us=\([0-9][0-9]*\).*/\1/p'); \
			optimized=$$(./build/perf-bench --workload $(PERF_WORKLOAD_FRAMES) | sed -n 's/.*elapsed_us=\([0-9][0-9]*\).*/\1/p'); \
		else \
			optimized=$$(./build/perf-bench --workload $(PERF_WORKLOAD_FRAMES) | sed -n 's/.*elapsed_us=\([0-9][0-9]*\).*/\1/p'); \
			legacy=$$(./build/perf-bench-legacy --workload $(PERF_WORKLOAD_FRAMES) | sed -n 's/.*elapsed_us=\([0-9][0-9]*\).*/\1/p'); \
		fi; \
		delta=$$((legacy - optimized)); \
		printf 'pair=%s legacy_elapsed_us=%s optimized_elapsed_us=%s delta_us=%s\n' "$$pair" "$$legacy" "$$optimized" "$$delta"; \
		printf '%s %s\n' "$$legacy" "$$optimized" >> "$$results"; \
		pair=$$((pair + 1)); \
	done; \
	awk 'function sort(a, n, i, j, value) { for (i = 1; i <= n; ++i) { for (j = i + 1; j <= n; ++j) { if (a[j] < a[i]) { value = a[i]; a[i] = a[j]; a[j] = value; } } } } { legacy[NR] = $$1; optimized[NR] = $$2; delta[NR] = $$1 - $$2; total_delta += delta[NR]; } END { count = NR; sort(legacy, count); sort(optimized, count); sort(delta, count); middle = int((count + 1) / 2); printf "comparison pairs=%d workload_frames=$(PERF_WORKLOAD_FRAMES)\n", count; printf "legacy median_us=%d min_us=%d max_us=%d\n", legacy[middle], legacy[1], legacy[count]; printf "optimized median_us=%d min_us=%d max_us=%d\n", optimized[middle], optimized[1], optimized[count]; printf "paired_delta_us legacy_minus_optimized median=%d min=%d max=%d mean=%.2f\n", delta[middle], delta[1], delta[count], total_delta / count; }' "$$results"

smoke-gearlynx: $(ROM)
	./scripts/smoke-gearlynx.sh $(ROM) build/asteroid-patrol.lbl

frame-cadence-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/verify-frame-pacing-gearlynx.py \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--map build/asteroid-patrol-cadence.map \
		--normal-rom $(ROM) \
		--normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-052/logic-catchup-gearlynx.json

phase-3r-gate-a-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/verify-phase-3r-gate-a-full-fixture-gearlynx.py \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--cadence-map build/asteroid-patrol-cadence.map \
		--release-map build/asteroid-patrol.map \
		--release-rom $(ROM) \
		--output evidence/APS-053/phase-3r-gate-a-full-fixture.json

$(CADENCE_VARIANT_A_ROM): build/main-cadence-v-a.o $(CADENCE_VARIANT_COMMON_OBJECTS) | toolchain
	mkdir -p dist build
	$(CL65) -t lynx -C $(CADENCE_CFG) -m build/asteroid-patrol-cadence-v-a.map \
		-Ln build/asteroid-patrol-cadence-v-a.lbl -o $@ \
		$(CADENCE_VARIANT_COMMON_OBJECTS) build/main-cadence-v-a.o

$(CADENCE_VARIANT_B_ROM): build/main-cadence-v-b.o $(CADENCE_VARIANT_COMMON_OBJECTS) | toolchain
	mkdir -p dist build
	$(CL65) -t lynx -C $(CADENCE_CFG) -m build/asteroid-patrol-cadence-v-b.map \
		-Ln build/asteroid-patrol-cadence-v-b.lbl -o $@ \
		$(CADENCE_VARIANT_COMMON_OBJECTS) build/main-cadence-v-b.o

$(CADENCE_VARIANT_C_ROM): build/main-cadence-v-c.o $(CADENCE_VARIANT_COMMON_OBJECTS) | toolchain
	mkdir -p dist build
	$(CL65) -t lynx -C $(CADENCE_CFG) -m build/asteroid-patrol-cadence-v-c.map \
		-Ln build/asteroid-patrol-cadence-v-c.lbl -o $@ \
		$(CADENCE_VARIANT_COMMON_OBJECTS) build/main-cadence-v-c.o

build/main-cadence-v-a.o: src/main.c include/game.h include/sound.h \
		include/title_voice.h include/version.h include/game_timing.h \
		include/static_layer.h include/static_layer_data.h \
		include/cadence_probe.h $(GEN_DIR)/stage_data.h \
		$(GEN_DIR)/sprite_data.h | toolchain
	mkdir -p build
	$(CL65) $(COMPACT_ROM_CFLAGS) -DCADENCE_PROBE -DCADENCE_VARIANT=1 \
		-c -o $@ src/main.c

build/main-cadence-v-b.o: src/main.c include/game.h include/sound.h \
		include/title_voice.h include/version.h include/game_timing.h \
		include/static_layer.h include/static_layer_data.h \
		include/cadence_probe.h $(GEN_DIR)/stage_data.h \
		$(GEN_DIR)/sprite_data.h | toolchain
	mkdir -p build
	$(CL65) $(COMPACT_ROM_CFLAGS) -DCADENCE_PROBE -DCADENCE_VARIANT=2 \
		-c -o $@ src/main.c

build/main-cadence-v-c.o: src/main.c include/game.h include/sound.h \
		include/title_voice.h include/version.h include/game_timing.h \
		include/static_layer.h include/static_layer_data.h \
		include/cadence_probe.h $(GEN_DIR)/stage_data.h \
		$(GEN_DIR)/sprite_data.h | toolchain
	mkdir -p build
	$(CL65) $(COMPACT_ROM_CFLAGS) -DCADENCE_PROBE -DCADENCE_VARIANT=3 \
		-c -o $@ src/main.c

frame-cadence-variants-gearlynx: $(ROM) $(CADENCE_VARIANT_A_ROM) \
		$(CADENCE_VARIANT_B_ROM) $(CADENCE_VARIANT_C_ROM)
	./scripts/inspect-lnx.sh $(CADENCE_VARIANT_A_ROM)
	./scripts/inspect-lnx.sh $(CADENCE_VARIANT_B_ROM)
	./scripts/inspect-lnx.sh $(CADENCE_VARIANT_C_ROM)
	./scripts/verify-frame-pacing-gearlynx.py --only-zero --variant V-A \
		--rom $(CADENCE_VARIANT_A_ROM) \
		--symbols build/asteroid-patrol-cadence-v-a.lbl \
		--map build/asteroid-patrol-cadence-v-a.map \
		--normal-rom $(ROM) --normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/cadence-v-a.json
	./scripts/verify-frame-pacing-gearlynx.py --only-zero --variant V-B \
		--rom $(CADENCE_VARIANT_B_ROM) \
		--symbols build/asteroid-patrol-cadence-v-b.lbl \
		--map build/asteroid-patrol-cadence-v-b.map \
		--normal-rom $(ROM) --normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/cadence-v-b.json
	./scripts/verify-frame-pacing-gearlynx.py --only-zero --variant V-C \
		--rom $(CADENCE_VARIANT_C_ROM) \
		--symbols build/asteroid-patrol-cadence-v-c.lbl \
		--map build/asteroid-patrol-cadence-v-c.map \
		--normal-rom $(ROM) --normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/cadence-v-c.json

static-layer-readback-gearlynx: $(ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/verify-static-layer-readback-gearlynx.py \
		--rom $(ROM) \
		--symbols build/asteroid-patrol.lbl \
		--output evidence/APS-053/phase-2r-v013.json

title-game-over-readback-gearlynx: $(ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/verify-title-game-over-readback-gearlynx.py \
		--rom $(ROM) \
		--symbols build/asteroid-patrol.lbl \
		--output evidence/APS-053/title-game-over-v027.json

aps053-diagnostic-rom-gearlynx: $(ROM)
	./scripts/inspect-lnx.sh $(ROM)
	python3 scripts/verify-aps053-diagnostic-rom.py \
		--rom $(ROM) \
		--output evidence/APS-053/diagnostic-rom-v027.json
	./scripts/verify-title-game-over-readback-gearlynx.py \
		--rom $(ROM) \
		--symbols build/asteroid-patrol.lbl \
		--output evidence/APS-053/title-game-over-v027.json
	./scripts/verify-static-layer-readback-gearlynx.py \
		--rom $(ROM) \
		--symbols build/asteroid-patrol.lbl \
		--output evidence/APS-053/phase-2r-v027.json

phase-2r-gate-a-gearlynx: $(ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/verify-phase-2r-gate-a-gearlynx.py \
		--rom $(ROM) \
		--symbols build/asteroid-patrol.lbl \
		--output evidence/APS-053/phase-2r-gate-a-v009.json

phase-2r-o5-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/verify-phase-2r-o5-minimal-chain-gearlynx.py \
		--rom $(ROM) \
		--symbols build/asteroid-patrol.lbl \
		--map build/asteroid-patrol.map \
		--cadence-map build/asteroid-patrol-cadence.map \
		--output evidence/APS-053/phase-2r-o5-v013.json

phase-2r-audio-diagnostics-gearlynx: $(ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/verify-audio-gearlynx.py --seconds 8 --channel 0 \
		--diagnostic-output evidence/APS-053/channel-0-diagnostic-v013.json
	-./scripts/verify-audio-gearlynx.py --seconds 8 --channel 1 \
		--diagnostic-output evidence/APS-053/channel-1-diagnostic-v013.json
	./scripts/verify-audio-gearlynx.py --seconds 20 --channel 2 \
		--diagnostic-output evidence/APS-053/channel-2-diagnostic-v013.json

phase-2r-section-profile-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/verify-section-profile-gearlynx.py \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--map build/asteroid-patrol-cadence.map \
		--normal-rom $(ROM) \
		--normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/section-profile-v015.json

phase-2r-logic-profile-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/verify-logic-profile-gearlynx.py \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--map build/asteroid-patrol-cadence.map \
		--normal-rom $(ROM) \
		--normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/logic-profile-v016.json

phase-2r-display-profile-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/verify-display-profile-gearlynx.py \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--map build/asteroid-patrol-cadence.map \
		--normal-rom $(ROM) \
		--normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/display-profile-v019.json

phase-2r-display-profile-no-reinject-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/verify-display-profile-gearlynx.py \
		--no-reinject \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--map build/asteroid-patrol-cadence.map \
		--normal-rom $(ROM) \
		--normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/display-profile-v021.json

phase-2r-catchup-causality-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/verify-display-profile-gearlynx.py \
		--catchup-causality \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--map build/asteroid-patrol-cadence.map \
		--normal-rom $(ROM) \
		--normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/catchup-causality-v022.json

phase-2r-bounded-catchup-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/verify-display-profile-gearlynx.py \
		--bounded-catchup \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--map build/asteroid-patrol-cadence.map \
		--normal-rom $(ROM) \
		--normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--output evidence/APS-053/bounded-catchup-v023.json

phase-3r-tick-calibration-gearlynx: $(ROM) $(CADENCE_ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-lnx.sh $(CADENCE_ROM)
	./scripts/calibrate-cadence-ticks-gearlynx.py \
		--rom $(CADENCE_ROM) \
		--symbols build/asteroid-patrol-cadence.lbl \
		--map build/asteroid-patrol-cadence.map \
		--normal-rom $(ROM) \
		--normal-symbols build/asteroid-patrol.lbl \
		--normal-map build/asteroid-patrol.map \
		--logic-evidence evidence/APS-053/logic-profile-v016.json \
		--output evidence/APS-053/tick-calibration-v024.json

build/test-game: tests/test_game.c src/game.c src/sound.c $(MUSIC_DATA) \
		$(GEN_DIR)/stage_data.c $(GEN_DIR)/stage_data.h include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_game.c src/game.c src/sound.c \
		$(GEN_DIR)/stage_data.c $(MUSIC_DATA)

build/test-game-legacy: tests/test_game.c src/game.c src/sound.c $(MUSIC_DATA) \
		$(GEN_DIR)/stage_data.c $(GEN_DIR)/stage_data.h include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -DGAME_PERF_INSTRUMENT \
		-DGAME_PERF_LEGACY_HIT_RESCAN -o $@ tests/test_game.c src/game.c \
		src/sound.c $(GEN_DIR)/stage_data.c $(MUSIC_DATA)

build/test-sound: tests/test_sound.c src/sound.c $(MUSIC_DATA) include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_sound.c src/sound.c $(MUSIC_DATA)

build/test-ima-adpcm: tests/test_ima_adpcm.c src/ima_adpcm.c \
		include/ima_adpcm.h include/title_voice_data.h \
		include/game_over_voice_data.h assets/voice/title-start.adpcm \
		assets/voice/game-over.adpcm src/title_voice_gain.inc
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_ima_adpcm.c src/ima_adpcm.c

build/test-sprite-data: tests/test_sprite_data.c $(GEN_DIR)/sprite_data.c \
		$(GEN_DIR)/sprite_data.h $(GEN_DIR)/stage_data.c \
		$(GEN_DIR)/stage_data.h include/game.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_sprite_data.c \
		$(GEN_DIR)/sprite_data.c $(GEN_DIR)/stage_data.c

build/test-smoke: tests/test_smoke.c src/game.c src/sound.c $(MUSIC_DATA) \
		$(GEN_DIR)/stage_data.c $(GEN_DIR)/stage_data.h include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_smoke.c src/game.c src/sound.c \
		$(GEN_DIR)/stage_data.c $(MUSIC_DATA)

build/perf-bench: tests/perf_bench.c src/game.c src/sound.c $(MUSIC_DATA) \
		$(GEN_DIR)/stage_data.c $(GEN_DIR)/stage_data.h include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -O2 -DGAME_PERF_INSTRUMENT -o $@ tests/perf_bench.c \
		src/game.c src/sound.c $(GEN_DIR)/stage_data.c $(MUSIC_DATA)

build/perf-bench-legacy: tests/perf_bench.c src/game.c src/sound.c $(MUSIC_DATA) \
		$(GEN_DIR)/stage_data.c $(GEN_DIR)/stage_data.h include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -O2 -DGAME_PERF_INSTRUMENT \
		-DGAME_PERF_LEGACY_HIT_RESCAN -o $@ tests/perf_bench.c src/game.c \
		src/sound.c $(GEN_DIR)/stage_data.c $(MUSIC_DATA)

lint: $(ROM_OBJECTS) voice-check | toolchain
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -fsyntax-only src/game.c src/sound.c \
		src/ima_adpcm.c src/title_voice.c $(MUSIC_DATA) \
		$(GEN_DIR)/stage_data.c $(GEN_DIR)/sprite_data.c tools/mml2c.c \
		tests/test_game.c tests/test_sound.c tests/test_ima_adpcm.c \
		tests/test_sprite_data.c tests/test_smoke.c
	sh -n scripts/*.sh

inspect: $(ROM)
	./scripts/inspect-lnx.sh $(ROM)
	./scripts/inspect-title-voice-cart.py $(ROM)

verify: clean test lint rom inspect

clean:
	rm -rf build dist
	rm -f src/main.o src/game.o src/sound.o
