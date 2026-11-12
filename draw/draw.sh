#!/usr/bin/env bash
# Redraw img/keymap.svg from config/adv360pro.keymap with keymap-drawer.
# Usage: `nix run .#draw` (CI runs it on every keymap change, see
# .github/workflows/draw.yml).
set -euo pipefail

root=$(git rev-parse --show-toplevel)
cd "$root"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# zmk-helpers provides ZMK_LAYER etc. Use the revision pinned in west.yml.
rev=$(grep -A2 'name: zmk-helpers' config/west.yml | sed -n 's/.*revision: *\([0-9a-f]\{40\}\).*/\1/p')
git init -q "$tmp/helpers"
git -C "$tmp/helpers" fetch -q --depth 1 https://github.com/urob/zmk-helpers "$rev"
git -C "$tmp/helpers" checkout -q FETCH_HEAD

# The 360 keymap re-orders keys (urob order), so the stock adv360pro layout
# does not fit. Reuse the &physical_layout0 override from the keymap.
{
    echo '/ { layout: layout { compatible = "zmk,physical-layout"; display-name = "urob";'
    sed -n '/^&physical_layout0 {/,/^};/p' config/adv360pro.keymap | sed '1d;$d' | grep -v display-name
    echo '}; };'
} >"$tmp/layout.dtsi"

# Add the include path to the config.
sed "s|^parse_config:|parse_config:\n  zmk_additional_includes: [\"$tmp/helpers/include\"]|" draw/config.yaml >"$tmp/config.yaml"

# Draw combos on a separate "Combos" panel so they do not clutter every layer.
keymap -c "$tmp/config.yaml" parse -z config/adv360pro.keymap --virtual-layers Combos >"$tmp/keymap.yaml"
yq -i '.combos[].l = ["Combos"]' "$tmp/keymap.yaml"
mkdir -p img
keymap -c "$tmp/config.yaml" draw "$tmp/keymap.yaml" --dts-layout "$tmp/layout.dtsi" >img/keymap.svg
cp "$tmp/keymap.yaml" draw/keymap.yaml
echo "wrote img/keymap.svg and draw/keymap.yaml"
