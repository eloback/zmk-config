#!/usr/bin/env python3
"""Draw a game's binds on the keyboard (see draw.sh and games/*/labels.yaml).

Usage: game.py RAW_PARSED_YAML GAME_DIR OUT_DIR

RAW_PARSED_YAML is the keymap parsed by keymap-drawer with no display renames,
so keys read as ZMK keycodes (TAB, LSHFT, F1). GAME_DIR holds labels.yaml and
the game's own bind file. Writes, with NAME the game folder's name:

  OUT_DIR/NAME.yaml  keymap-drawer layers "<title>" and "<title> Fn": what each
                     key does in the game, in the keyboard's game mode
  OUT_DIR/NAME.json  the bind list, unreachable binds and menu-only binds, for
                     the viewer (site.py)

The game's file is the source of truth. labels.yaml only names and colors the
actions, and an action without a label is shown under its raw name. Only Dota
2's file format (dotakeys_personal.lst) is supported for now.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

# ZMK keycode (as keymap-drawer prints it) -> Dota key name.
ZMK_TO_GAME = {
    "ESC": "ESCAPE", "RET": "ENTER", "BSPC": "BACKSPACE", "DEL": "DELETE",
    "LEFT": "LEFTARROW", "RIGHT": "RIGHTARROW", "UP": "UPARROW", "DOWN": "DOWNARROW",
    "PG UP": "PGUP", "PG DN": "PGDN", "GRAVE": "`", "MINUS": "-", "EQUAL": "=",
    "SEMICOLON": ";", "COMMA": ",", "DOT": ".", "FSLH": "/", "BSLH": "\\",
    "LBKT": "[", "RBKT": "]", "SQT": "'",
    "LSHFT": "SHIFT", "RSHFT": "SHIFT", "LCTRL": "CTRL", "RCTRL": "CTRL",
    "LALT": "ALT", "RALT": "ALT",
}
MODIFIERS = {"SHIFT", "CTRL", "ALT"}

# How a key name reads on the board.
PRETTY = {
    "ESCAPE": "Esc", "ENTER": "Enter", "BACKSPACE": "Bksp", "TAB": "Tab", "SPACE": "Space",
    "LEFTARROW": "←", "RIGHTARROW": "→", "UPARROW": "↑", "DOWNARROW": "↓",
    "SHIFT": "Shift", "CTRL": "Ctrl", "ALT": "Alt", "PGUP": "PgUp", "PGDN": "PgDn",
    # keys no game binds, as keymap-drawer prints them
    "PSCRN": "PrtSc", "MUTE": "Mute", "PP": "Play", "VOL DN": "Vol −", "VOL UP": "Vol +",
    "RGUI": "Gui", "LGUI": "Gui",
}

# Keyboard behaviors that are not keys.
SPECIAL = {
    "&swapper": {"t": "Alt-Tab"},
    "&bootloader": {"t": "Boot"},
    "&studio_unlock": {"t": "Studio"},
}

MOUSE = re.compile(r"^(MOUSE\d|MWHEEL(UP|DOWN))$")
KEYPAD = re.compile(r"^KP_")


def kv_parse(text: str) -> dict:
    """Valve KeyValues: "key" "value" pairs and "key" { ... } blocks."""
    tokens = re.findall(r'"([^"]*)"|([{}])', text)
    pos = 0

    def block() -> dict:
        nonlocal pos
        out: dict = {}
        while pos < len(tokens):
            key, brace = tokens[pos]
            pos += 1
            if brace == "}":
                return out
            value, brace = tokens[pos]
            pos += 1
            out[key] = block() if brace == "{" else value
        return out

    return block()


def game_binds(path: Path) -> list[dict]:
    """Top-level binds of a dotakeys_personal.lst: action, key, modifier."""
    keys = kv_parse(path.read_text())["KeyBindings"]["Keys"]
    binds = []
    for action, spec in keys.items():
        if isinstance(spec, dict) and spec.get("Key"):
            binds.append({
                "action": action,
                "key": spec["Key"].upper(),
                "mod": spec.get("Modifier", "").upper(),
            })
    return binds


def keycode(key) -> str | None:
    """The game key a keyboard key sends, or None for non-key behaviors."""
    if not isinstance(key, str) or key.startswith("&") or key == "":
        return None
    return ZMK_TO_GAME.get(key, key)


def stack(layers: list[list]) -> list:
    """Top layer first; transparent keys fall through to the next layer."""
    out = []
    for keys in zip(*layers):
        pick = keys[-1]
        for key in keys:
            if not (isinstance(key, dict) and key.get("type") == "trans"):
                pick = key
                break
        out.append(pick)
    return out


def main() -> None:
    raw_path, game_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    name = game_dir.name
    cfg = yaml.safe_load((game_dir / "labels.yaml").read_text())
    labels = cfg.get("actions", {})
    groups = cfg.get("groups", {})
    context = tuple(cfg.get("context", []))
    title = cfg["title"]
    # Group names for the list on the page, in labels.yaml's order.
    groups.setdefault("other", "Other")

    km = yaml.safe_load(raw_path.read_text())
    layer_keys = [km["layers"][l] for l in cfg["layers"]]
    board = stack(layer_keys)
    fn_board = stack([km["layers"][cfg["fn"]]] + layer_keys)

    def label(action: str) -> dict:
        if action in labels:
            return labels[action]
        # "Inventory1AutoCast" is Item 1's autocast: no label of its own needed.
        base = action.removesuffix("AutoCast")
        if base != action and base in labels:
            return {**labels[base], "name": labels[base]["name"] + " (autocast)"}
        return {"t": action, "name": action, "group": "other"}

    binds = game_binds(game_dir / cfg["binds"])
    for b in binds:
        b.update({k: v for k, v in label(b["action"]).items() if k in ("t", "name", "group")})
        b["context"] = b["action"].startswith(context)
    play = [b for b in binds if not b["context"]]
    by_key: dict[str, list[dict]] = defaultdict(list)
    for b in play:
        by_key[b["key"]].append(b)

    # Keys the keyboard can send in game mode, and how to reach each one.
    reach: dict[str, str] = {}
    for keys, how in ((board, ""), (fn_board, "Fn + ")):
        for key in keys:
            code = keycode(key)
            if code and code not in reach:
                reach[code] = how

    def legend(key) -> dict:
        if isinstance(key, dict):
            if key.get("type") == "held":
                return {"t": "Fn", "type": "held on-game-fn"}
            target, hold = key.get("t", ""), key.get("h", "")
            if hold == "toggle":
                return {"t": {"game": "Game", "base": "Base", "dota_sel": "Dota mode"}.get(target, target), "s": "toggle"}
            return {"t": target}
        if key == cfg["fn"]:
            return {"t": "Fn", "h": "hold", "type": "act-h-game-fn"}
        if key in SPECIAL:
            return dict(SPECIAL[key])
        code = keycode(key)
        if code is None:
            return {}
        pretty = PRETTY.get(code, code)
        if code in MODIFIERS:
            return {"t": pretty, "s": "modifier", "type": "mod"}
        plain = [b for b in by_key.get(code, []) if not b["mod"]]
        if not plain:
            return {"s": pretty, "type": "unbound"}
        out = {"s": pretty, "t": " / ".join(dict.fromkeys(b["t"] for b in plain))}
        out["type"] = "grp-" + plain[0]["group"]
        # Modifier binds other than autocast (that is noted once, in the list).
        extra = [
            b for b in by_key.get(code, [])
            if b["mod"] and not b["action"].endswith("AutoCast")
        ]
        if extra:
            out["h"] = " / ".join(f"{PRETTY[b['mod']]}: {b['t']}" for b in extra)
        return out

    drawn = {
        "layout": km["layout"],
        "layers": {
            title: [legend(k) for k in board],
            # On the Fn board, only draw what Fn changes.
            f"{title} Fn": [{"type": "trans"} if f == b else legend(f) for f, b in zip(fn_board, board)],
        },
    }
    (out / f"{name}.yaml").write_text(yaml.safe_dump(drawn, sort_keys=False, allow_unicode=True, width=120))

    def where(b: dict) -> str | None:
        """How to press a bind in game mode, or None if the keyboard can't."""
        if MOUSE.match(b["key"]):
            return PRETTY.get(b["key"], b["key"].title().replace("Mwheel", "Wheel "))
        how = reach.get(b["key"])
        if how is None or (b["mod"] and b["mod"] not in reach):
            return None
        key = how + PRETTY.get(b["key"], b["key"])
        return f"{PRETTY[b['mod']]} + {key}" if b["mod"] else key

    rows, unreachable, menus = [], [], []
    for b in binds:
        row = {"action": b["action"], "t": b["t"], "name": b.get("name", b["action"]),
               "group": b["group"], "keys": where(b)}
        if b["context"]:
            row["keys"] = row["keys"] or PRETTY.get(b["key"], b["key"])
            menus.append(row)
        elif b["action"].endswith("AutoCast") and b["mod"] == "ALT" and row["keys"]:
            continue  # "Alt + the ability's key", one note on the page covers them

        elif row["keys"] is None:
            row["key"] = (PRETTY.get(b["mod"], b["mod"]) + " + " if b["mod"] else "") + PRETTY.get(b["key"], b["key"])
            # The keyboard has no keypad; a keypad duplicate is not a problem.
            if not KEYPAD.match(b["key"]):
                unreachable.append(row)
        else:
            rows.append(row)
    unlabeled = sorted({b["action"] for b in play if b["group"] == "other"})

    info = {
        "title": title,
        "slug": name,
        "layers": list(drawn["layers"]),  # drawn to site/layers/NAME-<i>.svg
        "groups": groups,
        "binds": rows,
        "unreachable": unreachable,
        "menus": menus,
        "unlabeled": unlabeled,
        "autocast": any(b["action"].endswith("AutoCast") and b["mod"] == "ALT" for b in play),
    }
    (out / f"{name}.json").write_text(json.dumps(info, ensure_ascii=False))

    for r in unreachable:
        print(f"{title}: {r['name']} is bound to {r['key']}, which game mode can't type", file=sys.stderr)
    if unlabeled:
        print(f"{title}: no label in labels.yaml for {', '.join(unlabeled)}", file=sys.stderr)


if __name__ == "__main__":
    main()
