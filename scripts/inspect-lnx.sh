#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 ROM.lnx" >&2
    exit 2
fi

ROM=$1
test -f "$ROM"
size=$(wc -c < "$ROM" | tr -d ' ')
magic=$(LC_ALL=C od -An -N4 -c "$ROM" | tr -d ' \n')
bank0=$(od -An -j4 -N2 -tu2 "$ROM" | tr -d ' ')
bank1=$(od -An -j6 -N2 -tu2 "$ROM" | tr -d ' ')
version=$(od -An -j8 -N2 -tu2 "$ROM" | tr -d ' ')

if [ "$magic" != "LYNX" ]; then
    echo "invalid LNX magic: $magic" >&2
    exit 1
fi
if [ "$version" != "1" ]; then
    echo "unexpected LNX version: $version" >&2
    exit 1
fi
if [ "$size" -le 64 ]; then
    echo "LNX image has no payload: $size bytes" >&2
    exit 1
fi
case "$bank0" in
    512|1024|2048) ;;
    *) echo "invalid bank 0 page size: $bank0" >&2; exit 1 ;;
esac

printf 'LNX header OK: magic=%s version=%s bank0_page=%s bank1_page=%s size=%s bytes\n' \
    "$magic" "$version" "$bank0" "$bank1" "$size"
