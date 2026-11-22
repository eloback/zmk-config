#!/usr/bin/env bash
# Draw the keymap of config/adv360pro.keymap with keymap-drawer.
#
#   img/overview.svg  base layer, nav/fn/num/sys legends in the key corners
#   img/keymap.svg    every layer, plus the combos
#   img/<game>.svg    a game's binds on the keyboard (games/<game>/, game.py)
#   site/index.html   interactive viewer (layer and game tabs, search), see site.py
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

# Game pages (games/*/labels.yaml): what each key does in the game. game.py
# needs ZMK keycodes (TAB, LSHFT), so parse again without display renames.
cat >"$tmp/raw-config.yaml" <<EOF
parse_config:
  zmk_additional_includes: ["$tmp/helpers/include"]
  zmk_keycode_map: {}
  raw_binding_map: {}
  trans_legend: {t: "", type: trans}
EOF
keymap -c "$tmp/raw-config.yaml" parse -z config/adv360pro.keymap >"$tmp/raw.yaml"
games=()
for dir in games/*/; do
    [ -f "$dir/labels.yaml" ] || continue
    name=$(basename "$dir")
    python3 draw/game.py "$tmp/raw.yaml" "$dir" "$tmp"
    draw "$tmp/$name.yaml" >"img/$name.svg"
    i=0
    while IFS= read -r layer; do
        draw "$tmp/$name.yaml" -s "$layer" >"site/layers/$name-$i.svg"
        i=$((i + 1))
    done < <(python3 -c 'import json, sys; print("\n".join(json.load(open(sys.argv[1]))["layers"]))' "$tmp/$name.json")
    games+=("$tmp/$name.json")
done

python3 draw/site.py "$tmp/combos.json" "$tmp/layers.txt" site "${games[@]}"

cp "$tmp/keymap.yaml" draw/keymap.yaml
echo "wrote img/overview.svg, img/keymap.svg, img/<game>.svg, draw/keymap.yaml and site/"
