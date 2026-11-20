#!/usr/bin/env bash
# Draw the keymap of config/adv360pro.keymap with keymap-drawer.
#
#   img/overview.svg  base layer, nav/fn/num/sys legends in the key corners
#   img/keymap.svg    every layer, plus the combos
#   site/index.html   interactive viewer (layer tabs, search), see site.py
#
# Usage: `nix run .#draw`. CI runs it on every keymap change, commits the
# SVGs and publishes the site to GitHub Pages (.github/workflows/draw.yml).
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

keymap -c "$tmp/config.yaml" parse -z config/adv360pro.keymap --virtual-layers Combos >"$tmp/parsed.yaml"
python3 draw/process.py "$tmp/parsed.yaml" "$tmp"

draw() { keymap -c "$tmp/config.yaml" draw --dts-layout "$tmp/layout.dtsi" "$@"; }

mkdir -p img site/layers
draw "$tmp/keymap.yaml" >img/keymap.svg
draw "$tmp/overview.yaml" >img/overview.svg
# The overview is one picture, its "Base" / "Combos" headers are noise.
sed -i '/<text[^>]*class="label"/d' img/overview.svg

# One SVG per layer for the interactive viewer.
rm -f site/layers/*.svg
i=0
while IFS= read -r layer; do
    draw "$tmp/keymap.yaml" -s "$layer" >"site/layers/$i.svg"
    i=$((i + 1))
done <"$tmp/layers.txt"
cp img/overview.svg site/layers/overview.svg
python3 draw/site.py "$tmp/combos.json" "$tmp/layers.txt" site

cp "$tmp/keymap.yaml" draw/keymap.yaml
echo "wrote img/overview.svg, img/keymap.svg, draw/keymap.yaml and site/"
