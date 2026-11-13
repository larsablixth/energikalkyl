"""
Energy-flow playback: a self-contained HTML/JS player (no Streamlit inside).

player_html(series, capacity_kwh, labels, theme) returns one HTML page that
app.py shows with st.components.v1.html. It animates the battery's flows hour
by hour over the whole period in the browser, so playing, changing speed and
scrubbing never rerun the Streamlit script.

The diagram is a bus: sun, grid and battery feed a junction, which feeds the
house, the EV, hot water/flex loads, battery charging and export. Line width
and dash speed follow the power; every value is also written as text (never
colour alone). At higher speeds each frame shows the average power over the
hours it covers.

Data: controller_check.flow_series() channels, packed as int16 in 1/100 units
(kWh, öre) and base64-encoded: 3 years of hours ≈ 0.8 MB.
"""

from __future__ import annotations

import base64
import json
from array import array

from controller_check import FLOW_SERIES_KEYS

# One colour per entity (same as the Sankey and day chart in app.py)
COLORS = {"solar": "#eda100", "grid": "#2a78d6", "battery": "#1baf7a", "house": "#6250d6",
          "ev": "#e87ba4", "flex": "#eb6834", "export": "#008300", "curtailed": "#e34948"}

SPEEDS_H_PER_S = (1, 6, 24, 24 * 7, 24 * 30)


def _pack(series) -> dict:
    """Each channel → base64 of little-endian int16 in 1/100 units (hour: as is)."""
    packed = {}
    for k in FLOW_SERIES_KEYS:
        scale = 1 if k == "hour" else 100
        a = array("h", (max(-32768, min(32767, int(round(v * scale)))) for v in series[k]))
        if a.itemsize != 2:
            raise RuntimeError("int16 array expected")
        packed[k] = base64.b64encode(a.tobytes()).decode("ascii")
    return packed


def player_html(series, capacity_kwh, labels, theme="light") -> str:
    """The playback page. labels: the UI texts (keys used in the template below)."""
    payload = {
        "data": _pack(series),
        "dates": series["dates"],
        "dayStart": series["day_start"],
        "capacity": capacity_kwh,
        "colors": COLORS,
        "speeds": SPEEDS_H_PER_S,
        "labels": labels,
    }
    return (_TEMPLATE
            .replace("__THEME__", "dark" if theme == "dark" else "light")
            .replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":"))))


_TEMPLATE = r"""<!doctype html>
<html data-theme="__THEME__"><head><meta charset="utf-8">
<style>
:root { --bg: transparent; --text: #1f1f1e; --muted: #6b6a63; --line: #d6d4cc; --panel: #f5f4f0; }
:root[data-theme="dark"] { --text: #f0efec; --muted: #a9a89e; --line: #45443f; --panel: #26261f; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 14px/1.35 "Source Sans Pro", -apple-system, "Segoe UI", sans-serif; }
.wrap { display: flex; flex-wrap: wrap; gap: 12px; }
svg { flex: 1 1 520px; min-width: 300px; max-width: 760px; height: auto; }
.side { flex: 1 1 220px; display: flex; flex-direction: column; gap: 8px; }
.card { background: var(--panel); border-radius: 8px; padding: 10px 12px; }
.when { font-size: 18px; font-weight: 600; }
.muted { color: var(--muted); font-size: 13px; }
.big { font-size: 20px; font-weight: 600; }
.row { display: flex; justify-content: space-between; gap: 8px; }
.controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 8px; }
button, select { font: inherit; color: var(--text); background: var(--panel); border: 1px solid var(--line);
                 border-radius: 6px; padding: 6px 12px; cursor: pointer; min-height: 36px; }
button.primary { background: #2a78d6; color: #fff; border-color: #2a78d6; min-width: 96px; }
input[type=range] { flex: 1 1 260px; min-width: 200px; accent-color: #2a78d6; height: 36px; }
.node-label { font-size: 13px; font-weight: 600; fill: var(--text); text-anchor: middle; }
.node-value { font-size: 13px; fill: var(--text); text-anchor: middle; }
.flow-value { font-size: 12px; fill: var(--muted); }
.flow { fill: none; stroke-linecap: round; }
.flow.on { stroke-dasharray: 6 10; animation: dash linear infinite; }
.flow.rev { animation-direction: reverse; }
.base { fill: none; stroke: var(--line); stroke-width: 2; }
@keyframes dash { to { stroke-dashoffset: -32; } }
</style></head><body>
<div class="wrap">
  <svg id="svg" viewBox="0 0 640 400" role="img"></svg>
  <div class="side">
    <div class="card"><div class="when" id="when"></div><div class="muted" id="window"></div></div>
    <div class="card row"><span id="priceLabel"></span><span class="big" id="price"></span></div>
    <div class="card"><div class="muted" id="sinceLabel"></div>
      <div class="row"><span id="savedLabel"></span><span class="big" id="saved"></span></div>
      <div class="row"><span id="solarUsedLabel"></span><span id="solarUsed"></span></div>
      <div class="row"><span id="boughtLabel"></span><span id="bought"></span></div>
      <div class="row"><span id="curtLabel"></span><span id="curt"></span></div>
    </div>
  </div>
</div>
<div class="controls">
  <button class="primary" id="play"></button>
  <select id="speed" aria-label="speed"></select>
  <input type="range" id="pos" min="0" value="0" aria-label="position">
</div>
<script>
const P = __PAYLOAD__;
const L = P.labels, C = P.colors;
document.documentElement.dataset.theme = document.documentElement.dataset.theme || "light";

// ── data ──
function unpack(b64, scale) {
  const bin = atob(b64), n = bin.length >> 1, out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let v = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8);
    if (v & 0x8000) v -= 0x10000;
    out[i] = v / scale;
  }
  return out;
}
const D = {};
for (const k in P.data) D[k] = unpack(P.data[k], k === "hour" ? 1 : 100);
const N = D.hour.length;
const SUM_KEYS = ["solar", "curtailed", "grid_in", "export", "bat_out", "bat_in", "house", "ev", "flex",
                  "net_ore", "price_ore"];
const CUM = {};      // prefix sums: CUM[k][i] = sum of the first i hours
for (const k of SUM_KEYS) {
  const c = new Float64Array(N + 1);
  for (let i = 0; i < N; i++) c[i + 1] = c[i] + D[k][i];
  CUM[k] = c;
}
const sumRange = (k, a, b) => CUM[k][b] - CUM[k][a];          // hours [a, b)
function dateIndex(i) {   // index of the date containing hour i
  let lo = 0, hi = P.dayStart.length - 1;
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (P.dayStart[m] <= i) lo = m; else hi = m - 1; }
  return lo;
}
const fmtDate = (s) => new Date(s + "T12:00:00").toLocaleDateString(L.locale,
  { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const kw = (v) => (v >= 9.95 ? v.toFixed(0) : v.toFixed(1)) + " kW";
const kwh = (v) => Math.round(v).toLocaleString(L.locale) + " kWh";
const kr = (v) => Math.round(v).toLocaleString(L.locale) + " kr";

// ── diagram ──
const NS = "http://www.w3.org/2000/svg";
const svg = document.getElementById("svg");
function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  (parent || svg).appendChild(e);
  return e;
}
const HUB = [320, 200];
const NODES = {
  solar:   { x: 320, y: 52,  label: L.solar,   color: C.solar },
  curtailed: { x: 470, y: 52, label: L.curtailed, color: C.curtailed, small: true },
  grid:    { x: 80,  y: 200, label: L.grid,    color: C.grid },
  battery: { x: 320, y: 348, label: L.battery, color: C.battery },
  house:   { x: 560, y: 80,  label: L.house,   color: C.house },
  ev:      { x: 560, y: 200, label: L.ev,      color: C.ev },
  flex:    { x: 560, y: 320, label: L.flex,    color: C.flex },
};
// lines: [from, to]; value > 0 flows from → to, < 0 the other way
const LINES = {
  solar:   { a: "solar", b: "hub" },
  curt:    { a: "solar", b: "curtailed" },
  grid:    { a: "grid", b: "hub" },
  battery: { a: "battery", b: "hub" },
  house:   { a: "hub", b: "house" },
  ev:      { a: "hub", b: "ev" },
  flex:    { a: "hub", b: "flex" },
};
const pt = (n) => (n === "hub" ? HUB : [NODES[n].x, NODES[n].y]);
const lineEls = {};
for (const id in LINES) {
  const [x1, y1] = pt(LINES[id].a), [x2, y2] = pt(LINES[id].b);
  el("line", { x1, y1, x2, y2, class: "base" });
  const f = el("line", { x1, y1, x2, y2, class: "flow" });
  // value label beside the line's middle, offset along its normal (never on the line)
  const len = Math.hypot(x2 - x1, y2 - y1) || 1;
  let nx = -(y2 - y1) / len, ny = (x2 - x1) / len;
  if (ny > 0 || (ny === 0 && nx > 0)) { nx = -nx; ny = -ny; }      // above / left of the line
  const t = el("text", { x: (x1 + x2) / 2 + nx * 14, y: (y1 + y2) / 2 + ny * 14 + 4, class: "flow-value",
                         "text-anchor": Math.abs(nx) > 0.5 ? (nx < 0 ? "end" : "start") : "middle" });
  lineEls[id] = { f, t };
}
el("circle", { cx: HUB[0], cy: HUB[1], r: 5, fill: "var(--muted)" });
const nodeEls = {};
for (const id in NODES) {
  const n = NODES[id], r = n.small ? 18 : 32;
  const g = el("g", {});
  el("circle", { cx: n.x, cy: n.y, r, fill: "var(--panel)", stroke: n.color, "stroke-width": 3 }, g);
  let fill = null;
  if (id === "battery") {   // fill level from the bottom
    const clip = el("clipPath", { id: "batclip" }, g);
    el("circle", { cx: n.x, cy: n.y, r: r - 3 }, clip);
    fill = el("rect", { x: n.x - r, y: n.y + r, width: 2 * r, height: 0, fill: n.color, opacity: 0.45,
                        "clip-path": "url(#batclip)" }, g);
  }
  const below = n.y > HUB[1] + 50;
  el("text", { x: n.x, y: below ? n.y + r + 18 : n.y - r - 8, class: "node-label" }, g).textContent = n.label;
  const v = el("text", { x: n.x, y: n.y + 5, class: "node-value" }, g);
  const state = id === "battery" ? el("text", { x: n.x + r + 8, y: n.y + 5, class: "flow-value" }, g) : null;
  nodeEls[id] = { v, fill, r, state };
}

function setLine(id, val, color, maxKw) {
  const { f, t } = lineEls[id], a = Math.abs(val);
  if (a < 0.05) {
    f.setAttribute("class", "flow"); f.setAttribute("stroke", "none"); t.textContent = ""; return;
  }
  const w = 2 + 10 * Math.sqrt(Math.min(1, a / maxKw));
  f.setAttribute("stroke", color);
  f.setAttribute("stroke-width", w.toFixed(1));
  f.setAttribute("class", "flow on" + (val < 0 ? " rev" : ""));
  f.style.animationDuration = Math.max(0.25, 2.2 - 1.9 * Math.min(1, a / maxKw)).toFixed(2) + "s";
  t.textContent = kw(a);
}

// ── state ──
const speedSel = document.getElementById("speed"), pos = document.getElementById("pos"),
      play = document.getElementById("play");
P.speeds.forEach((h, k) => {
  const o = document.createElement("option");
  o.value = h; o.textContent = L.speeds[k];
  if (h === 24) o.selected = true;
  speedSel.appendChild(o);
});
pos.max = Math.max(0, N - 1);
let cur = 0, playing = false, last = null, carry = 0;
const MAXKW = (() => {   // scale for line widths: a high hourly power, not the single extreme
  const v = [];
  for (const k of ["grid_in", "bat_out", "bat_in", "house", "ev", "solar"])
    for (let i = 0; i < N; i += 7) v.push(D[k][i]);
  v.sort((a, b) => a - b);
  return Math.max(1, v[Math.floor(v.length * 0.98)] || 1);
})();

function render() {
  const rate = +speedSel.value;
  const win = Math.max(1, Math.round(rate / 2));             // hours averaged per frame
  const b = Math.min(N, cur + 1), a = Math.max(0, b - win);
  const n = b - a, avg = (k) => sumRange(k, a, b) / n;
  const solar = avg("solar"), curt = avg("curtailed");
  const gridNet = avg("grid_in") - avg("export");
  const batNet = avg("bat_out") - avg("bat_in");
  setLine("solar", solar - curt, C.solar, MAXKW);
  setLine("curt", curt, C.curtailed, MAXKW);
  setLine("grid", gridNet, gridNet >= 0 ? C.grid : C.export, MAXKW);
  setLine("battery", batNet, C.battery, MAXKW);
  setLine("house", avg("house"), C.house, MAXKW);
  setLine("ev", avg("ev"), C.ev, MAXKW);
  setLine("flex", avg("flex"), C.flex, MAXKW);
  nodeEls.solar.v.textContent = kw(solar);
  nodeEls.curtailed.v.textContent = curt >= 0.05 ? kw(curt) : "";
  nodeEls.grid.v.textContent = gridNet >= 0 ? kw(gridNet) : "−" + kw(-gridNet);
  nodeEls.house.v.textContent = kw(avg("house"));
  nodeEls.ev.v.textContent = kw(avg("ev"));
  nodeEls.flex.v.textContent = kw(avg("flex"));
  const soc = D.soc[b - 1], frac = Math.max(0, Math.min(1, soc / P.capacity));
  const br = nodeEls.battery.r, by = NODES.battery.y;
  nodeEls.battery.fill.setAttribute("y", (by + br - 2 * br * frac).toFixed(1));
  nodeEls.battery.fill.setAttribute("height", (2 * br * frac).toFixed(1));
  nodeEls.battery.v.textContent = Math.round(100 * frac) + " %";
  nodeEls.battery.state.textContent = batNet > 0.05 ? L.discharging : batNet < -0.05 ? L.charging : "";

  const di = dateIndex(b - 1), hr = D.hour[b - 1];
  document.getElementById("when").textContent =
    fmtDate(P.dates[di]) + (win === 1 ? "  " + String(hr).padStart(2, "0") + ":00" : "");
  const da = dateIndex(a);
  document.getElementById("window").textContent = win === 1 ? L.hourly
    : L.average.replace("{from}", fmtDate(P.dates[da])).replace("{to}", fmtDate(P.dates[di]));
  document.getElementById("price").textContent = (avg("price_ore") / 100).toFixed(2) + " kr/kWh";
  document.getElementById("saved").textContent = kr(sumRange("net_ore", 0, b) / 100);
  document.getElementById("solarUsed").textContent =
    kwh(sumRange("solar", 0, b) - sumRange("curtailed", 0, b));
  document.getElementById("bought").textContent = kwh(sumRange("grid_in", 0, b));
  document.getElementById("curt").textContent = kwh(sumRange("curtailed", 0, b));
  pos.value = cur;
}

function tick(ts) {
  if (!playing) return;
  if (last !== null) {
    carry += (ts - last) / 1000 * +speedSel.value;
    const step = Math.floor(carry);
    if (step > 0) {
      carry -= step;
      cur = Math.min(N - 1, cur + step);
      render();
      if (cur >= N - 1) { setPlaying(false); return; }
    }
  }
  last = ts;
  requestAnimationFrame(tick);
}
function setPlaying(on) {
  playing = on; last = null; carry = 0;
  play.textContent = on ? "❚❚ " + L.pause : "▶ " + L.play;
  if (on) { if (cur >= N - 1) cur = 0; requestAnimationFrame(tick); }
}
play.onclick = () => setPlaying(!playing);
pos.oninput = () => { cur = +pos.value; render(); };
speedSel.onchange = () => { carry = 0; render(); };
for (const [id, key] of [["priceLabel", "price"], ["sinceLabel", "since"], ["savedLabel", "saved"],
                         ["solarUsedLabel", "solarUsed"], ["boughtLabel", "bought"], ["curtLabel", "curtailedTotal"]])
  document.getElementById(id).textContent = L[key];
svg.setAttribute("aria-label", L.aria);
setPlaying(false);
render();
</script></body></html>
"""
