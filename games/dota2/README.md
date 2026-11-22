# Dota 2

My Dota 2 hotkeys, laid out for the keyboard's Dota mode. Browse them on the
[keymap viewer](https://eloback.github.io/zmk-config/#dota-2) (search works:
try "courier").

![Dota 2 binds](../../img/dota2.svg)

## Keyboard

Dota mode is a variant of the game layer (`dota` in
[config/base.keymap](../../config/base.keymap)):

- **Game mode** on and off: the `Game` toggle key. It comes back in whichever
  game variant was used last.
- **Dota mode** on and off: hold `Fn` (bottom small left-thumb key) and press
  the number row's far-left key. Off means the Deadlock layout. `&to 0` and
  rebooting the keyboard reset it to Deadlock.
- What changes from the Deadlock layout: `Y` / `H` / `N` move into the pinky
  column, so abilities and items start one column further left, `Shift` (the
  queue modifier, which Dota can't rebind) moves to the small left-thumb key,
  and `F1` (hero select) takes the outer top key.

## Binds

[dotakeys_personal.lst](dotakeys_personal.lst) is a verbatim copy of the
game's hotkey file, and the single source of truth. Dota rewrites the file
itself, adds new actions to it after patches and migrates old versions, so it
is copied, never generated.

- **Rebind**: in the in-game Hotkeys menu, then `dota-sync pull`, commit and
  push. CI redraws the board and the viewer.
- **New PC**: open Dota once, close it, then `dota-sync push` (it refuses
  while Dota is running and backs up the file it replaces). If Steam reports a
  cloud sync conflict on the next launch, keep the files on this computer.
- `dota-sync diff` shows what differs between the repo and Steam.

`dota-sync` is a command in the devshell (`nix develop`, or direnv). Without
it, run the script itself: `games/dota2/sync.sh pull`.

[labels.yaml](labels.yaml) only names and colors the actions on the page. An
action without a label still shows, under its raw name, so a game update never
breaks the page: add a label when a new one appears (the draw step prints
them).

The page also lists binds the keyboard can't type in game mode, e.g. a key
Dota bound by itself. Rebind those in game.

## Things to check in game

Dota keeps a second, older bind file, `user_keys.vcfg` (console binds), which
still binds `1`-`6` to items, `G` to voice chat and `Y` to camera grip. If
pressing `3` uses an item as well as selecting the control group, those old
binds are live and should be removed.
