#!/usr/bin/env python3
"""Post-process keymap-drawer's parse output (see draw.sh).

Usage: process.py PARSED_YAML OUT_DIR

Writes OUT_DIR/keymap.yaml (all layers) and OUT_DIR/overview.yaml (base with
the nav/fn/num/sys legends in its corners, the way urob draws his keymap).

- hides flag layers that only exist for firmware logic (dota_sel)
- gives layers display names (nav -> Nav) on headers and on the keys that
  activate them
- blanks keys that do the same as on the layer below. The 360's extra keys are
  repeated on every layer (X_LT etc. in adv360pro.keymap), which drowns out
  what a layer actually changes
- tags layer keys with an `act-<layer>` class and held keys with
  `on-<layer>`, so the stylesheet in config.yaml can color them per layer
- puts combos that fire on base on a separate "Combos" panel, and leaves
  layer-specific combos on their layer
"""

import json
import re
import sys
from pathlib import Path

import yaml

HIDDEN = {"dota_sel"}

NAMES = {
    "base": "Base",
    "nav": "Nav",
    "fn": "Fn",
    "num": "Num",
    "sys": "Sys",
    "macro": "Macro",
    "goto": "Goto",
    "game": "Game",
    "mouse": "Mouse",
    "dota": "Dota",
    "game_fn": "Game Fn",
}

# The layer a layer sits on top of. Keys equal to the parent's are blanked.
PARENT = {"dota": "game", "game_fn": "game"}

# Overview corners: layer -> legend position on the base key.
CORNERS = {"nav": "tr", "fn": "tl", "num": "bl", "sys": "br"}

COMBOS = "Combos"
LEGEND_FIELDS = ("t", "h", "s", "tl", "tr", "bl", "br", "left", "right")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def as_dict(key) -> dict:
    if key is None:
        return {}
    if isinstance(key, dict):
        return dict(key)
    return {"t": str(key)}


def add_type(key: dict, cls: str) -> dict:
    types = key.get("type", "").split()
    if cls not in types:
        types.append(cls)
    key["type"] = " ".join(types)
    return key


def is_passthrough(key: dict) -> bool:
    """Transparent, or the held key that activated the layer."""
    types = key.get("type", "").split()
    return "trans" in types or "held" in types


def same(a: dict, b: dict) -> bool:
    strip = lambda k: {f: k.get(f) for f in LEGEND_FIELDS if k.get(f)}  # noqa: E731
    return strip(a) == strip(b)


def rename(key: dict, names: dict[str, str]) -> dict:
    for f in LEGEND_FIELDS:
        if isinstance(key.get(f), str) and key[f] in names:
            key[f] = names[key[f]]
    return key


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    km = yaml.safe_load(src.read_text())
    raw = {n: [as_dict(k) for k in keys] for n, keys in km["layers"].items()}

    # Blank keys repeated from the parent layer. Compare against the parent's
    # *original* keys, before the parent itself is blanked.
    layers: dict[str, list[dict]] = {}
    for name, keys in raw.items():
        if name in HIDDEN:
            continue
        parent = PARENT.get(name, "base")
        if name not in (parent, COMBOS) and parent in raw:
            keys = [
                {"type": "trans"} if not is_passthrough(k) and same(k, p) else k
                for k, p in zip(keys, raw[parent])
            ]
        layers[name] = keys

    names = {n: NAMES.get(n, n) for n in layers}

    # Color hooks: keys that switch to a layer, and the keys held on a layer.
    for name, keys in layers.items():
        for key in keys:
            rename(key, names)
            for f in ("t", "h"):
                if key.get(f) in names.values() and key[f] != names[name]:
                    add_type(key, f"act-{f}-{slug(key[f])}")
            if "held" in key.get("type", "").split():
                add_type(key, "on-" + slug(names[name]))

    # Combos: base ones on the Combos panel, the rest stay on their layers.
    # A layer combo on the same keys as a base combo (nav's < > { }) goes on
    # the base combo's top legend instead, so it does not cover nav's keys.
    combos, base_combos = [], {}
    for combo in km.get("combos", []):
        combo["k"] = rename(as_dict(combo["k"]), names)
        on = [names[l] for l in combo.get("l", []) if l in names]
        combo["l"] = on if on and names["base"] not in on else [COMBOS]
        if combo["l"] == [COMBOS]:
            base_combos[tuple(sorted(combo["p"]))] = combo
        combos.append(combo)
    for combo in list(combos):
        twin = base_combos.get(tuple(sorted(combo["p"])))
        if twin is None or twin is combo:
            continue
        legend = combo["k"].get("t")
        if twin["k"].get("s") in (None, legend):
            twin["k"]["s"] = legend
            combos.remove(combo)

    # On the Combos panel, mark the keys combos use with their base letter
    # (top left, where no combo box sits), so "Esc" reads as W + E.
    def letter(i: int) -> str:
        t = layers["base"][i].get("t", "")
        return t if t and not t.startswith("$$") else ""

    used = {i for c in combos if c["l"] == [COMBOS] for i in c["p"]}
    layers[COMBOS] = [
        {"tl": letter(i), "type": "combo-key"} if i in used and letter(i) else {"type": "trans"}
        for i in range(len(layers[COMBOS]))
    ]

    # Combo list for the viewer: what each combo does and which keys make it.
    (out / "combos.json").write_text(
        json.dumps(
            [
                {
                    "layer": c["l"][0],
                    "p": c["p"],
                    "t": c["k"].get("t", ""),
                    "h": c["k"].get("h", ""),
                    "s": c["k"].get("s", ""),
                    "keys": [letter(i) or f"#{i}" for i in c["p"]],
                }
                for c in combos
            ],
            ensure_ascii=False,
        )
    )

    full = {
        "layout": km["layout"],
        "layers": {names[n]: keys for n, keys in layers.items()},
        "combos": combos,
    }

    # Overview: base, with the other layers' legends in the corners.
    base = []
    for i, key in enumerate(layers["base"]):
        key = dict(key)
        for layer, corner in CORNERS.items():
            other = layers[layer][i]
            if is_passthrough(other) or not other.get("t"):
                continue
            if corner in ("tl", "tr") and key.get("s"):
                continue  # would cover the shifted legend
            key[corner] = other["t"]
        base.append(key)
    overview = {
        "layout": km["layout"],
        "layers": {"Base": base, COMBOS: layers[COMBOS]},
        "combos": [c for c in combos if c["l"] == [COMBOS]],
    }

    dump = lambda d: yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=120)  # noqa: E731
    (out / "keymap.yaml").write_text(dump(full))
    (out / "overview.yaml").write_text(dump(overview))
    (out / "layers.txt").write_text("\n".join(names[n] for n in layers) + "\n")


if __name__ == "__main__":
    main()
