SHELL := /bin/sh

CC65_VERSION := 2.19
TOOLCHAIN_ROOT := $(CURDIR)/.cache/cc65-$(CC65_VERSION)/install
CL65 := $(TOOLCHAIN_ROOT)/bin/cl65
CC65_HOME := $(TOOLCHAIN_ROOT)/share/cc65
export CC65_HOME
HOST_CC ?= clang
GEN_DIR := build/gen
HOST_CFLAGS := -std=c89 -pedantic -Wall -Wextra -Werror -Iinclude -I$(GEN_DIR)
ROM_CFLAGS := -t lynx -Oirs --standard cc65 -W error -Iinclude -I$(GEN_DIR)
ROM := dist/asteroid-patrol.lnx
ROM_OBJECTS := build/main.o build/game.o build/sound.o build/music_data.o
MUSIC_DATA := $(GEN_DIR)/music_data.c
MUSIC_SOURCES := assets/music/stage1.mml assets/music/stage2.mml \
	assets/music/stage3.mml
MUSIC_TRACKS := stage_one=assets/music/stage1.mml \
	stage_two=assets/music/stage2.mml \
	stage_three=assets/music/stage3.mml
PERF_WORKLOAD_FRAMES := 5000000
PERF_PAIR_COUNT := 7

.PHONY: all toolchain rom clean test smoke-host smoke-gearlynx perf-host lint verify inspect

all: verify

toolchain:
	./scripts/install-cc65.sh

rom: $(ROM)

$(ROM): $(ROM_OBJECTS) | toolchain
	mkdir -p dist build
	$(CL65) -t lynx -m build/asteroid-patrol.map -Ln build/asteroid-patrol.lbl -o $@ $(ROM_OBJECTS)

build/main.o: src/main.c include/game.h include/sound.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/main.c

build/game.o: src/game.c include/game.h include/sound.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/game.c

build/sound.o: src/sound.c include/sound.h $(MUSIC_DATA) | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/sound.c

build/music_data.o: $(MUSIC_DATA) include/sound.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ $(MUSIC_DATA)

build/mml2c: tools/mml2c.c
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tools/mml2c.c

$(MUSIC_DATA): build/mml2c $(MUSIC_SOURCES) include/sound.h
	mkdir -p $(GEN_DIR)
	./build/mml2c $(GEN_DIR)/music_data $(MUSIC_TRACKS)

test: build/test-game build/test-sound
	./build/test-game
	./build/test-sound

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

build/test-game: tests/test_game.c src/game.c src/sound.c $(MUSIC_DATA) \
		include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_game.c src/game.c src/sound.c \
		$(MUSIC_DATA)

build/test-game-legacy: tests/test_game.c src/game.c src/sound.c $(MUSIC_DATA) \
		include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -DGAME_PERF_INSTRUMENT \
		-DGAME_PERF_LEGACY_HIT_RESCAN -o $@ tests/test_game.c src/game.c \
		src/sound.c $(MUSIC_DATA)

build/test-sound: tests/test_sound.c src/sound.c $(MUSIC_DATA) include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_sound.c src/sound.c $(MUSIC_DATA)

build/test-smoke: tests/test_smoke.c src/game.c src/sound.c $(MUSIC_DATA) \
		include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_smoke.c src/game.c src/sound.c \
		$(MUSIC_DATA)

build/perf-bench: tests/perf_bench.c src/game.c src/sound.c $(MUSIC_DATA) \
		include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -O2 -DGAME_PERF_INSTRUMENT -o $@ tests/perf_bench.c \
		src/game.c src/sound.c $(MUSIC_DATA)

build/perf-bench-legacy: tests/perf_bench.c src/game.c src/sound.c $(MUSIC_DATA) \
		include/game.h include/sound.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -O2 -DGAME_PERF_INSTRUMENT \
		-DGAME_PERF_LEGACY_HIT_RESCAN -o $@ tests/perf_bench.c src/game.c \
		src/sound.c $(MUSIC_DATA)

lint: $(ROM_OBJECTS) | toolchain
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -fsyntax-only src/game.c src/sound.c \
		$(MUSIC_DATA) tools/mml2c.c \
		tests/test_game.c tests/test_sound.c tests/test_smoke.c
	sh -n scripts/*.sh

inspect: $(ROM)
	./scripts/inspect-lnx.sh $(ROM)

verify: clean test lint rom inspect

clean:
	rm -rf build dist
	rm -f src/main.o src/game.o src/sound.o
