#!/usr/bin/env bash
# Copy Dota 2's hotkey file between Steam and this repo. In the devshell it is
# the `dota-sync` command (flake.nix), run from anywhere in the repo.
set -euo pipefail

usage() {
    cat <<'EOF'
Copy Dota 2's hotkey file between Steam and this repo.

  dota-sync pull   Steam -> repo, after rebinding in game
  dota-sync push   repo -> Steam, e.g. on a new PC (Dota closed)
  dota-sync diff   what differs between the two

The game's file is the source of truth: rebind in the in-game Hotkeys menu,
then pull, commit and push. CI redraws the page (img/dota2.svg, the site).

Steam is found under ~/.local/share/Steam. Set STEAM_DIR to use another
install, and STEAM_ID when more than one Steam account has played Dota.
EOF
}

# Packaged by the flake, this script runs from the Nix store: find the repo
# through git, from the current directory.
root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "run this inside the zmk-config repo" >&2
    exit 1
}
repo="$root/games/dota2/dotakeys_personal.lst"
steam=${STEAM_DIR:-$HOME/.local/share/Steam}

if [ -n "${STEAM_ID:-}" ]; then
    dirs=("$steam/userdata/$STEAM_ID/570")
else
    shopt -s nullglob
    dirs=("$steam"/userdata/*/570)
fi
case ${#dirs[@]} in
    0) echo "no Dota 2 config under $steam/userdata (set STEAM_DIR?)" >&2; exit 1 ;;
    1) ;;
    *) echo "several Steam accounts have played Dota, set STEAM_ID to one of:" >&2
       for d in "${dirs[@]}"; do basename "$(dirname "$d")" >&2; done
       exit 1 ;;
esac
live="${dirs[0]}/remote/cfg/dotakeys_personal.lst"

case ${1:-} in
    pull)
        [ -f "$live" ] || { echo "$live does not exist: open Dota once" >&2; exit 1; }
        cp "$live" "$repo"
        echo "copied $live -> $repo"
        git -C "$root" diff --stat -- games/dota2/dotakeys_personal.lst
        ;;
    push)
        # Dota rewrites the file while running and when it closes.
        if pgrep -x dota2 >/dev/null; then
            echo "Dota 2 is running: close it first" >&2
            exit 1
        fi
        mkdir -p "$(dirname "$live")"
        if [ -f "$live" ]; then
            backup="$live.bak-$(date +%Y%m%d-%H%M%S)"
            cp -p "$live" "$backup"
            echo "backed up the current file to $backup"
        fi
        cp "$repo" "$live"
        echo "copied $repo -> $live"
        echo "If Steam reports a cloud sync conflict on launch, keep the files on this computer."
        ;;
    diff)
        diff -u "$repo" "$live" && echo "no differences"
        ;;
    -h | --help) usage ;;
    *)
        usage >&2
        exit 2
        ;;
esac
