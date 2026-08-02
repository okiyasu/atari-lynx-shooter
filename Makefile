SHELL := /bin/sh

CC65_VERSION := 2.19
TOOLCHAIN_ROOT := $(CURDIR)/.cache/cc65-$(CC65_VERSION)/install
CL65 := $(TOOLCHAIN_ROOT)/bin/cl65
CC65_HOME := $(TOOLCHAIN_ROOT)/share/cc65
export CC65_HOME
HOST_CC ?= clang
HOST_CFLAGS := -std=c89 -pedantic -Wall -Wextra -Werror -Iinclude
ROM_CFLAGS := -t lynx -Oirs --standard cc65 -W error -Iinclude
ROM := dist/asteroid-patrol.lnx
ROM_OBJECTS := build/main.o build/game.o

.PHONY: all toolchain rom clean test lint verify inspect

all: verify

toolchain:
	./scripts/install-cc65.sh

rom: $(ROM)

$(ROM): $(ROM_OBJECTS) | toolchain
	mkdir -p dist build
	$(CL65) -t lynx -m build/asteroid-patrol.map -Ln build/asteroid-patrol.lbl -o $@ $(ROM_OBJECTS)

build/main.o: src/main.c include/game.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/main.c

build/game.o: src/game.c include/game.h | toolchain
	mkdir -p build
	$(CL65) $(ROM_CFLAGS) -c -o $@ src/game.c

test: build/test-game
	./build/test-game

build/test-game: tests/test_game.c src/game.c include/game.h
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ tests/test_game.c src/game.c

lint: $(ROM_OBJECTS) | toolchain
	mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -fsyntax-only src/game.c tests/test_game.c
	sh -n scripts/*.sh

inspect: $(ROM)
	./scripts/inspect-lnx.sh $(ROM)

verify: clean test lint rom inspect

clean:
	rm -rf build dist
	rm -f src/main.o src/game.o
