#!/usr/bin/env python3
"""Build the interactive keymap viewer (see draw.sh).

Usage: site.py COMBOS_JSON LAYERS_TXT SITE_DIR

Reads SITE_DIR/layers/{overview,0,1,...}.svg (one keymap-drawer SVG per
layer) and writes SITE_DIR/index.html, a single self-contained page:

- one tab per layer (keys 1-9 / arrows), plus the overview
- layer keys are links: click "Nav" on Space to open the nav layer
- search ("/"): highlights matching keys and counts matches per layer, so
  "where is the $ key?" is one keystroke away
- combos: hovering one highlights the keys that make it, and the Combos and
  Overview tabs list every combo with its keys (COMBOS_JSON, from process.py)
"""

import html
import json
import re
import sys
from pathlib import Path

LAYER_COLOR = {
    "Nav": "nav",
    "Fn": "fn",
    "Num": "num",
    "Sys": "sys",
    "Mouse": "mouse",
    "Game": "game",
    "Dota": "game",
    "Game Fn": "game",
}


def clean_svg(svg: str) -> str:
    svg = re.sub(r"<\?xml[^>]*>\s*", "", svg)
    # Tabs name the layer already; drop the header above the drawing.
    svg = re.sub(r'<text[^>]*class="label"[^>]*>.*?</text>\n?', "", svg)
    # Let CSS size the drawing, and crop the band the header sat in.
    svg = re.sub(r'(<svg[^>]*?) width="[^"]*" height="[^"]*"', r"\1", svg, count=1)
    svg = re.sub(
        r'viewBox="0 0 (\d+) (\d+)"',
        lambda m: f'viewBox="0 {CROP} {m[1]} {int(m[2]) - CROP}"',
        svg,
        count=1,
    )
    return svg


CROP = 28  # draw_config.outer_pad_h minus a margin


REPO = "https://github.com/eloback/zmk-config/blob/main"

# Game pages (game.py): bind group -> color token.
GROUP_COLOR = {
    "ability": "nav", "item": "game", "unit": "sys", "camera": "mouse",
    "shop": "fn", "chat": "num", "system": "misc", "other": "misc",
}


def kbds(keys: str) -> str:
    """ "Fn + F7" -> <kbd>Fn</kbd>+<kbd>F7</kbd> """
    return "+".join(f"<kbd>{html.escape(k)}</kbd>" for k in keys.split(" + "))


def bind_item(b: dict) -> str:
    words = html.escape(f"{b['name']} {b['t']} {b['keys']} {b['action']}".lower())
    return (
        f'<li data-words="{words}"><span class="out">{html.escape(b["name"])}</span>'
        f'<span class="keys">{kbds(b["keys"])}</span></li>'
    )


def game_section(g: dict) -> str:
    """The bind list under a game's board."""
    e = html.escape
    out = [f'<section class="game" data-game="{e(g["slug"])}" hidden>', f"<h2>{e(g['title'])}</h2>"]
    out.append(
        "<p>Keyboard in <b>game mode</b>, switched to Dota mode with <b>Fn</b> + the number row's far-left key. "
        f'The binds are drawn from the game\'s own hotkey file, <a href="{REPO}/games/{e(g["slug"])}">games/{e(g["slug"])}</a>, '
        "where the README explains how to install them.</p>"
    )
    if g["unreachable"]:
        items = ", ".join(f"{e(r['name'])} (<kbd>{e(r['key'])}</kbd>)" for r in g["unreachable"])
        out.append(f'<p class="warn"><b>Not reachable in game mode:</b> {items}. Rebind them in game.</p>')
    if g["autocast"]:
        out.append("<p><b>Autocast:</b> Alt + an ability or item key.</p>")
    out.append('<div class="bind-groups">')
    for group, title in g["groups"].items():
        rows = [b for b in g["binds"] if b["group"] == group]
        if not rows:
            continue
        dot = f'<span class="dot" style="background: var(--{GROUP_COLOR.get(group, "misc")})"></span>'
        out.append(f'<div class="bind-group"><h3>{dot}{e(title)}</h3><ul class="binds">')
        out += [bind_item(b) for b in rows]
        out.append("</ul></div>")
    out.append("</div>")
    if g["menus"]:
        out.append(
            f'<details><summary>Menu-only binds ({len(g["menus"])}): shop, talents, spectating</summary>'
            '<ul class="binds menus">' + "".join(bind_item(b) for b in g["menus"]) + "</ul></details>"
        )
    out.append("</section>")
    return "\n".join(out)


def main() -> None:
    combos_json, layers_txt, site = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    games = [json.loads(Path(p).read_text()) for p in sys.argv[4:]]
    names = [l for l in layers_txt.read_text().splitlines() if l]
    # (name, svg file, game slug)
    tabs = [("Overview", "overview", "")] + [(n, str(i), "") for i, n in enumerate(names)]
    for g in games:
        tabs += [(layer, f"{g['slug']}-{i}", g["slug"]) for i, layer in enumerate(g["layers"])]

    panels, buttons = [], []
    for i, (name, file, game) in enumerate(tabs):
        svg = clean_svg((site / "layers" / f"{file}.svg").read_text())
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if game:
            color = "game"
        else:
            color = LAYER_COLOR.get(name, "misc" if name not in ("Overview", "Base") else "")
        dot = f'<span class="dot" style="background: var(--{color})"></span>' if color else ""
        key = f"<kbd>{i}</kbd>" if i < 10 else ""
        if game and not tabs[i - 1][2]:
            buttons.append('<span class="sep" aria-hidden="true">Games</span>')
        buttons.append(
            f'<button role="tab" id="tab-{slug}" data-layer="{slug}" data-game="{game}" aria-controls="panel-{slug}">'
            f'{dot}<span class="name">{html.escape(name)}</span>{key}<span class="count"></span></button>'
        )
        panels.append(f'<section role="tabpanel" id="panel-{slug}" data-layer="{slug}" hidden>{svg}</section>')

    page = TEMPLATE.replace("{{TABS}}", "\n      ".join(buttons)).replace("{{PANELS}}", "\n    ".join(panels))
    page = page.replace("{{GAMES}}", "\n".join(game_section(g) for g in games))
    page = page.replace("{{NAMES}}", json.dumps([n for n, _, _ in tabs]))
    page = page.replace("{{COMBOS}}", combos_json.read_text())
    (site / "index.html").write_text(page)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Advantage 360 keymap</title>
<style>
  :root {
    --bg: #eff1f5; --surface: #e6e9ef; --line: #ccd0da;
    --text: #4c4f69; --sub: #6c6f85; --accent: #1e66f5; --hit: #fe640b;
    --nav: #1e66f5; --fn: #8839ef; --num: #e64553; --sys: #40a02b;
    --game: #df8e1d; --mouse: #179299; --misc: #7287fd;
    color-scheme: light dark;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #11111b; --surface: #181825; --line: #313244;
      --text: #cdd6f4; --sub: #9399b2; --accent: #89b4fa; --hit: #fab387;
      --nav: #89b4fa; --fn: #cba6f7; --num: #f38ba8; --sys: #a6e3a1;
      --game: #fab387; --mouse: #94e2d5; --misc: #b4befe;
    }
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.5 Inter, "SF Pro Text", system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .wrap { max-width: 1240px; margin: 0 auto; padding: 24px 16px 48px; }
  header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 16px; margin-bottom: 16px; }
  h1 { font-size: 22px; margin: 0; letter-spacing: -0.01em; }
  header p { margin: 0; color: var(--sub); font-size: 14px; }
  header a { color: var(--accent); }
  .bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
  [role=tablist] { display: flex; flex-wrap: wrap; gap: 6px; flex: 1 1 auto; }
  [role=tab] {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 10px; border-radius: 8px; border: 1px solid var(--line);
    background: var(--surface); color: var(--text); font: inherit; font-size: 14px; cursor: pointer;
  }
  [role=tab]:hover { border-color: var(--sub); }
  [role=tab][aria-selected=true] { background: var(--text); color: var(--bg); border-color: var(--text); }
  [role=tab] kbd { font: 11px ui-monospace, monospace; opacity: 0.55; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .count:not(:empty) {
    background: var(--hit); color: #fff; border-radius: 99px; padding: 0 6px; font-size: 12px; font-weight: 700;
  }
  [role=tab].nomatch { opacity: 0.4; }
  .search { position: relative; flex: 0 1 260px; }
  .search input {
    width: 100%; padding: 7px 10px 7px 32px; border-radius: 8px; border: 1px solid var(--line);
    background: var(--surface); color: var(--text); font: inherit; font-size: 14px;
  }
  .search input:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
  .search svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); opacity: 0.5; }
  .stage { border-radius: 14px; overflow-x: auto; border: 1px solid var(--line); }
  .stage svg { display: block; width: 100%; min-width: 720px; height: auto; }
  .stage a { cursor: pointer; }
  .stage a:hover text { text-decoration: underline; }
  section.searching g.key, section.searching g.combo { opacity: 0.25; }
  section.searching g.hit { opacity: 1; }
  g.hit > rect { stroke: var(--hit) !important; stroke-width: 3 !important; }
  .legend {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px 24px;
    margin-top: 16px; color: var(--sub); font-size: 14px;
  }
  .legend b { color: var(--text); }
  .legend .c { font-weight: 700; }
  /* combo hover: light up the keys that make the combo */
  section.combo-focus g.combo, section.combo-focus g.key { opacity: 0.3; }
  section.combo-focus g.combo.on, section.combo-focus g.key.src { opacity: 1; }
  g.key.src > rect { stroke: var(--accent) !important; stroke-width: 3 !important; }
  g.combo.on > rect { stroke: var(--accent) !important; stroke-width: 2 !important; }
  g.combo { cursor: default; }
  .combos { margin-top: 20px; }
  .combos h2 { font-size: 17px; margin: 0 0 2px; }
  .combos p { margin: 0 0 10px; color: var(--sub); font-size: 14px; }
  #combo-list {
    list-style: none; margin: 0; padding: 0;
    display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 6px;
  }
  #combo-list li {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface);
  }
  #combo-list li.on { border-color: var(--accent); }
  #combo-list .out { font-weight: 600; }
  #combo-list .out small { color: var(--sub); font-weight: 400; margin-left: 4px; }
  #combo-list .keys { display: flex; gap: 3px; align-items: center; color: var(--sub); font-size: 12px; }
  #combo-list kbd {
    font: 600 12px/1 ui-monospace, monospace; padding: 3px 5px; border-radius: 4px;
    border: 1px solid var(--line); background: var(--bg); color: var(--text);
  }
  .status { min-height: 1.5em; color: var(--sub); font-size: 14px; margin: 0 0 8px; }
  .sep {
    align-self: center; margin-left: 10px; padding-left: 12px; border-left: 1px solid var(--line);
    color: var(--sub); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  }
  /* game pages: the bind list under the board */
  .game { margin-top: 20px; }
  .game h2 { font-size: 17px; margin: 0 0 4px; }
  .game > p { margin: 0 0 10px; color: var(--sub); font-size: 14px; max-width: 80ch; }
  .game a { color: var(--accent); }
  .game .warn { color: var(--text); border-left: 3px solid var(--hit); padding: 4px 10px; background: var(--surface); }
  .bind-groups { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px 24px; margin-top: 12px; }
  .bind-group h3 { display: flex; align-items: center; gap: 6px; font-size: 14px; margin: 0 0 6px; }
  ul.binds { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
  ul.binds li {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 4px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); font-size: 14px;
  }
  ul.binds .keys { display: flex; gap: 3px; align-items: center; color: var(--sub); font-size: 12px; white-space: nowrap; }
  ul.binds kbd, .game kbd {
    font: 600 12px/1 ui-monospace, monospace; padding: 3px 5px; border-radius: 4px;
    border: 1px solid var(--line); background: var(--bg); color: var(--text);
  }
  .game details { margin-top: 16px; }
  .game summary { cursor: pointer; color: var(--sub); font-size: 14px; }
  ul.binds.menus { grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); margin-top: 8px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Advantage 360 Pro keymap</h1>
    <p>Drawn from <a href="https://github.com/eloback/zmk-config/blob/main/config/base.keymap">config/base.keymap</a> by <a href="https://github.com/caksoylar/keymap-drawer">keymap-drawer</a>.</p>
  </header>

  <div class="bar">
    <div role="tablist" aria-label="Layers">
      {{TABS}}
    </div>
    <label class="search">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
      <input id="q" type="search" placeholder="Find a key  ( / )" autocomplete="off" spellcheck="false" aria-label="Find a key">
    </label>
  </div>
  <p class="status" id="status" aria-live="polite"></p>

  <div class="stage">
    {{PANELS}}
  </div>

  <section class="combos" id="combo-section" hidden>
    <h2>Combos</h2>
    <p>Press the keys together. Hover a combo to see its keys on the board.</p>
    <ul id="combo-list"></ul>
  </section>

  {{GAMES}}

  <div class="legend" id="legend">
    <div><b>Center</b> tap &middot; <b>bottom</b> hold &middot; <b>top</b> shifted</div>
    <div><b>Blank key</b>: same as the layer below</div>
    <div><b>Colored key</b>: held to reach this layer. Click a colored layer name to open it.</div>
    <div><b>Overview corners</b>:
      <span class="c" style="color: var(--fn)">Fn</span>,
      <span class="c" style="color: var(--nav)">Nav</span>,
      <span class="c" style="color: var(--num)">Num</span>,
      <span class="c" style="color: var(--sys)">Sys</span>
      (clockwise from top left)</div>
  </div>
</div>

<script>
const NAMES = {{NAMES}};
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const tabs = [...document.querySelectorAll("[role=tab]")];
const panels = [...document.querySelectorAll("[role=tabpanel]")];
const q = document.getElementById("q");
const status = document.getElementById("status");

function show(layer, push = true) {
  if (!tabs.some(t => t.dataset.layer === layer)) layer = "overview";
  for (const t of tabs) t.setAttribute("aria-selected", t.dataset.layer === layer);
  for (const p of panels) p.hidden = p.dataset.layer !== layer;
  if (push && location.hash.slice(1) !== layer) history.replaceState(null, "", "#" + layer);
  describe();
}
const current = () => tabs.findIndex(t => t.getAttribute("aria-selected") === "true");

for (const t of tabs) t.addEventListener("click", () => show(t.dataset.layer));
window.addEventListener("hashchange", () => show(location.hash.slice(1), false));

// Layer legends on keys are <a href="#name"> links. Map them to tabs.
for (const a of document.querySelectorAll(".stage a")) {
  a.addEventListener("click", e => {
    e.preventDefault();
    const href = a.getAttribute("href") || a.getAttribute("xlink:href") || "";
    show(slug(href.slice(1)));
  });
}

// Search: match a whole legend ("F5", "$") or the start of a word ("vol").
function legends(g) {
  return [...g.querySelectorAll("text, tspan")].map(t => t.textContent.trim().toLowerCase()).filter(Boolean);
}
const index = panels.map(p => [...p.querySelectorAll("g.key:not(.combo-key), g.combo")].map(g => [g, legends(g)]));

function matches(words, term) {
  return words.some(w => w === term || (term.length > 1 && w.split(/[\\s+]+/).some(p => p.startsWith(term))));
}

let counts = [];
function search() {
  const term = q.value.trim().toLowerCase();
  counts = index.map((keys, i) => {
    let n = 0;
    for (const [g, words] of keys) {
      const hit = term !== "" && matches(words, term);
      g.classList.toggle("hit", hit);
      n += hit;
    }
    panels[i].classList.toggle("searching", term !== "");
    tabs[i].querySelector(".count").textContent = term && n ? n : "";
    tabs[i].classList.toggle("nomatch", term !== "" && !n);
    return n;
  });
  describe();
  filterCombos();
}

function describe() {
  const term = q.value.trim();
  if (!term) { status.textContent = ""; return; }
  const where = NAMES.filter((_, i) => counts[i] && i > 0);
  status.textContent = where.length
    ? `"${term}" is on ${where.join(", ")}.` + (counts[current()] ? "" : " Enter jumps there.")
    : `No key matches "${term}".`;
}

// Combos. keymap-drawer numbers each layer's combos (combopos-N) in the
// order they appear in keymap.yaml, which COMBOS keeps.
const COMBOS = {{COMBOS}};
const comboLayer = s => (s === "overview" ? "combos" : s);
const combosOf = s => COMBOS.filter(c => slug(c.layer) === comboLayer(s));
const describeCombo = c =>
  `${c.t} = ${c.keys.join(" + ")}` + (c.h ? ` (hold: ${c.h})` : "") + (c.s ? ` (shift / nav: ${c.s})` : "");

function focusCombo(panel, c, on) {
  panel.classList.toggle("combo-focus", on);
  const list = combosOf(panel.dataset.layer);
  const i = list.indexOf(c);
  panel.querySelector(`g.combopos-${i}`)?.classList.toggle("on", on);
  for (const p of c.p) panel.querySelector(`g.key.keypos-${p}`)?.classList.toggle("src", on);
  listItems.get(c)?.classList.toggle("on", on);
  if (on) status.textContent = describeCombo(c); else describe();
}

for (const panel of panels) {
  const list = combosOf(panel.dataset.layer);
  for (const g of panel.querySelectorAll("g.combo")) {
    const c = list[Number((g.getAttribute("class").match(/combopos-(\\d+)/) || [])[1])];
    if (!c) continue;
    g.addEventListener("mouseenter", () => focusCombo(panel, c, true));
    g.addEventListener("mouseleave", () => focusCombo(panel, c, false));
    g.addEventListener("click", () => focusCombo(panel, c, !g.classList.contains("on")));
  }
}

const listItems = new Map();
const comboSection = document.getElementById("combo-section");
const comboList = document.getElementById("combo-list");
for (const c of combosOf("combos")) {
  const li = document.createElement("li");
  const out = document.createElement("span");
  out.className = "out";
  out.textContent = c.t;
  if (c.h) {
    const small = document.createElement("small");
    small.textContent = "hold " + c.h;
    out.append(small);
  }
  const keys = document.createElement("span");
  keys.className = "keys";
  c.keys.forEach((k, i) => {
    if (i) keys.append("+");
    const kbd = document.createElement("kbd");
    kbd.textContent = k;
    keys.append(kbd);
  });
  li.append(out, keys);
  li.dataset.words = [c.t, c.h, c.s].join(" ").toLowerCase();
  const panel = () => panels[current()];
  li.addEventListener("mouseenter", () => focusCombo(panel(), c, true));
  li.addEventListener("mouseleave", () => focusCombo(panel(), c, false));
  comboList.append(li);
  listItems.set(c, li);
}

// Show the combo list on the tabs that draw these combos, and a game's bind
// list on its tabs. Search filters both.
const games = [...document.querySelectorAll("section.game")];
const legend = document.getElementById("legend");
const baseShow = show;
show = (layer, push = true) => {
  baseShow(layer, push);
  const tab = tabs[current()];
  comboSection.hidden = !["combos", "overview"].includes(tab.dataset.layer);
  for (const g of games) g.hidden = g.dataset.game !== tab.dataset.game;
  legend.hidden = tab.dataset.game !== "";
};
const bindItems = [...document.querySelectorAll("ul.binds li")];
function filterCombos() {
  const term = q.value.trim().toLowerCase();
  const miss = el => term !== "" && !matches(el.dataset.words.split(" ").filter(Boolean), term);
  for (const li of listItems.values()) li.hidden = miss(li);
  for (const li of bindItems) li.hidden = miss(li);
  // open the menu-only list when the search hits one of its binds
  for (const d of document.querySelectorAll("section.game details"))
    if (term && [...d.querySelectorAll("li")].some(li => !li.hidden)) d.open = true;
  for (const grp of document.querySelectorAll(".bind-group"))
    grp.hidden = ![...grp.querySelectorAll("li")].some(li => !li.hidden);
}

q.addEventListener("input", search);
q.addEventListener("keydown", e => {
  if (e.key === "Enter") {
    // jump to the next layer with a match
    for (let k = 1; k <= tabs.length; k++) {
      const i = (current() + k) % tabs.length;
      if (counts[i] && i > 0) { show(tabs[i].dataset.layer); break; }
    }
  } else if (e.key === "Escape") { q.value = ""; search(); q.blur(); }
});

document.addEventListener("keydown", e => {
  if (e.target === q || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === "/") { e.preventDefault(); q.focus(); return; }
  const n = Number(e.key);
  if (e.key.length === 1 && n >= 0 && n < tabs.length) show(tabs[n].dataset.layer);
  else if (e.key === "ArrowRight") show(tabs[(current() + 1) % tabs.length].dataset.layer);
  else if (e.key === "ArrowLeft") show(tabs[(current() - 1 + tabs.length) % tabs.length].dataset.layer);
});

show(location.hash.slice(1) || "overview", false);
// ?q=... pre-fills the search, so a search can be linked.
const initial = new URLSearchParams(location.search).get("q");
if (initial) { q.value = initial; search(); }
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
