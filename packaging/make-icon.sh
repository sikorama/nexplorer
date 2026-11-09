#!/usr/bin/env bash
# Regenerates icon.png and icon.ico from an embedded SVG. Needs rsvg-convert and
# ImageMagick. The committed icons are used as is by the build scripts; to change
# the icon, replace icon.png and icon.ico (or rerun this script with another SVG).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
src="${1:-$here/../nexplorer/ui/svg/cassette-tape.svg}"

glyph="$(sed -e 's/currentColor/#ffffff/g' -e 's/width="24" height="24"/width="256" height="256"/' "$src")"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
printf '%s' "$glyph" > "$tmp/glyph.svg"
# Glyph in the middle 70% of a dark rounded square.
rsvg-convert -w 358 -h 358 "$tmp/glyph.svg" -o "$tmp/glyph.png"
convert -size 512x512 xc:none -fill '#1f2937' -draw 'roundrectangle 0,0 511,511 96,96' \
    "$tmp/glyph.png" -gravity center -composite "$here/icon.png"
convert "$here/icon.png" -define icon:auto-resize=256,128,64,48,32,16 "$here/icon.ico"
