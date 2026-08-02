#!/bin/sh
set -eu

CC65_VERSION=2.19
CC65_TAG=V2.19
CC65_COMMIT=555282497c3ecf8b313d87d5973093af19c35bd5
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CACHE_ROOT="$PROJECT_ROOT/.cache/cc65-$CC65_VERSION"
SOURCE_DIR="$CACHE_ROOT/source"
INSTALL_DIR="$CACHE_ROOT/install"

if [ -d "$SOURCE_DIR/.git" ]; then
    actual_commit=$(git -C "$SOURCE_DIR" rev-parse HEAD)
    if [ "$actual_commit" != "$CC65_COMMIT" ]; then
        echo "cc65 tag verification failed: expected $CC65_COMMIT, got $actual_commit" >&2
        exit 1
    fi
fi

if [ -x "$INSTALL_DIR/bin/cl65" ] && [ -d "$SOURCE_DIR/.git" ]; then
    actual_version=$($INSTALL_DIR/bin/cl65 --version 2>&1)
    case "$actual_version" in
        *"Git 5552824"*) exit 0 ;;
        *) echo "Unexpected cached cl65: $actual_version" >&2; exit 1 ;;
    esac
fi

mkdir -p "$CACHE_ROOT"
if [ ! -d "$SOURCE_DIR/.git" ]; then
    git clone --branch "$CC65_TAG" --depth 1 https://github.com/cc65/cc65.git "$SOURCE_DIR"
fi

actual_commit=$(git -C "$SOURCE_DIR" rev-parse HEAD)
if [ "$actual_commit" != "$CC65_COMMIT" ]; then
    echo "cc65 tag verification failed: expected $CC65_COMMIT, got $actual_commit" >&2
    exit 1
fi

make -C "$SOURCE_DIR" -j2
make -C "$SOURCE_DIR" PREFIX="$INSTALL_DIR" install
"$INSTALL_DIR/bin/cl65" --version
