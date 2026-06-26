"""Build a visual, self-contained HTML research report from a research.json.

The Dataset-Research skill emits a compact research.json (validated against
research_schema.json). This module turns that data into a single illustrated
HTML file: hero header, KPI cards, verdict pills, inline SVG donut and bar
charts, distribution sparklines, and a sources panel.

Everything is inline (CSS and SVG, no external assets, no JS) so it renders as a
Claude Code Artifact under a strict CSP.

Usage:
    python build_research_report.py <research.json> <out.html>

It is also called by render.py's `research` mode.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# A fixed, friendly palette for chart series, cycled as needed.
_SERIES = ["#5b8def", "#22c1a4", "#f6ab23", "#9b6bff", "#ff7a8a",
           "#f4c542", "#3fb6e0", "#7bc96f", "#e36bb0", "#c0a36e"]


def _esc(x: Any) -> str:
    return html.escape(str(x))


def _color(i: int) -> str:
    return _SERIES[i % len(_SERIES)]


# ---------------------------------------------------------------- styling ----

_CSS = """
:root{
  --bg:#f6f8fc;--panel:#ffffff;--ink:#1f2733;--muted:#69748a;--soft:#8a94a6;
  --line:#e6eaf1;--accent:#5b8def;--accent2:#22c1a4;
  --good:#1aa179;--good-bg:#e6f7f1;--warn:#b5760a;--warn-bg:#fff4e0;
  --bad:#c5435a;--bad-bg:#fdeaee;--info:#3a6fd8;--info-bg:#eaf1fe;
  --shadow:0 1px 2px rgba(20,30,55,.05),0 6px 24px rgba(20,30,55,.06);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px 90px}

/* hero */
.hero{margin:28px 0 22px;border-radius:20px;overflow:hidden;box-shadow:var(--shadow);
 background:linear-gradient(135deg,#3a6fd8 0%,#5b8def 45%,#22c1a4 120%);color:#fff;position:relative}
.hero:after{content:"";position:absolute;inset:0;
 background:radial-gradient(900px 300px at 85% -20%,rgba(255,255,255,.22),transparent 60%);pointer-events:none}
.hero .inner{position:relative;padding:30px 34px 28px}
.hero .eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.9;font-weight:600}
.hero h1{margin:8px 0 6px;font-size:30px;line-height:1.2;letter-spacing:-.02em;font-weight:700}
.hero .obj{font-size:15px;opacity:.95;max-width:760px}
.hero .meta{margin-top:16px;display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.16);
 border:1px solid rgba(255,255,255,.28);padding:5px 12px;border-radius:999px;font-size:12.5px;font-weight:600}

/* sections */
section{margin:30px 0}
h2{font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--soft);
 margin:0 0 14px;display:flex;align-items:center;gap:10px}
h2:before{content:"";width:22px;height:2px;border-radius:2px;background:var(--accent)}
h3{font-size:16px;margin:18px 0 10px;color:var(--ink)}
p.lead{font-size:16px;line-height:1.65;color:var(--ink);margin:0 0 6px}

/* cards */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
 padding:16px 18px;box-shadow:var(--shadow)}
.card .k{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em;font-weight:600}
.card .v{font-size:24px;font-weight:700;margin-top:6px;letter-spacing:-.01em}
.card .s{color:var(--soft);font-size:12.5px;margin-top:4px}

.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;
 padding:18px 20px;box-shadow:var(--shadow)}
.split{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}

/* tables */
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--panel);box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:460px}
th,td{padding:11px 14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#fbfcfe;color:var(--muted);font-weight:600;font-size:12px;
 text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
tr:last-child td{border-bottom:none}
td.num{text-align:right;font-variant-numeric:tabular-nums}
td .src{color:var(--soft);font-size:12px}

/* pills */
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}
.pill.good{background:var(--good-bg);color:var(--good)}
.pill.warn{background:var(--warn-bg);color:var(--warn)}
.pill.bad{background:var(--bad-bg);color:var(--bad)}
.pill.info{background:var(--info-bg);color:var(--info)}

/* legend rows for charts */
.legend{margin:0;padding:0;list-style:none}
.legend li{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:13.5px}
.legend .dot{width:11px;height:11px;border-radius:3px;flex:0 0 auto}
.legend .lab{flex:1;color:var(--ink)}
.legend .pct{font-variant-numeric:tabular-nums;color:var(--muted);font-weight:600}

/* horizontal bars */
.hbars{margin:6px 0}
.hbar{margin:9px 0}
.hbar .row{display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px}
.hbar .row .lab{color:var(--ink)}
.hbar .row .val{color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums}
.track{height:9px;background:#eef1f7;border-radius:6px;overflow:hidden}
.track>span{display:block;height:100%;border-radius:6px}

/* sparkline for distributions */
.spark{display:flex;align-items:flex-end;gap:2px;height:30px}
.spark>span{flex:1;background:var(--accent);opacity:.85;border-radius:2px 2px 0 0;min-width:3px}

.kvs{display:flex;flex-wrap:wrap;gap:4px 16px}
.kvs .k{color:var(--soft);font-size:12px}
.note{background:#fbfcfe;border:1px solid var(--line);border-left:3px solid var(--accent);
 border-radius:10px;padding:12px 16px;margin:10px 0;color:var(--ink)}
.note.warn{border-left-color:var(--warn)}
ul.clean{margin:8px 0;padding-left:20px}
ul.clean li{margin:5px 0}
a{color:var(--info);text-decoration:none}
a:hover{text-decoration:underline}
.footer{margin-top:50px;color:var(--soft);font-size:12.5px;border-top:1px solid var(--line);padding-top:16px}
.src-list{list-style:none;margin:0;padding:0;counter-reset:s}
.src-list li{counter-increment:s;padding:10px 0;border-bottom:1px solid var(--line);display:flex;gap:12px}
.src-list li:last-child{border-bottom:none}
.src-list .num{flex:0 0 26px;height:26px;border-radius:8px;background:var(--info-bg);color:var(--info);
 font-weight:700;font-size:12px;display:flex;align-items:center;justify-content:center}
.src-list .body .t{font-weight:600}
.src-list .body .u{font-size:12.5px}
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title><style>{_CSS}</style></head>
<body><div class="wrap">{body}
<div class="footer">Generated by the DataGen plugin. This is domain research only.
Read the grounded numbers, correct anything that looks off, then decide what to do next.</div>
</div></body></html>"""


# ----------------------------------------------------------- chart helpers ----

def _donut(items: List[Dict[str, Any]]) -> str:
    """SVG donut from [{label, share}]. Shares are normalized to 100."""
    total = sum(max(0.0, float(i.get("share", 0))) for i in items) or 1.0
    r, cx, cy, sw = 52, 70, 70, 22
    import math
    circ = 2 * math.pi * r
    offset = 0.0
    segs = []
    for idx, it in enumerate(items):
        frac = max(0.0, float(it.get("share", 0))) / total
        length = frac * circ
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{_color(idx)}" stroke-width="{sw}" '
            f'stroke-dasharray="{length:.2f} {circ - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += length
    n = len(items)
    svg = (
        f'<svg viewBox="0 0 140 140" width="140" height="140" role="img">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#eef1f7" stroke-width="{sw}"/>'
        + "".join(segs) +
        f'<text x="{cx}" y="{cy-2}" text-anchor="middle" font-size="20" font-weight="700" fill="#1f2733">{n}</text>'
        f'<text x="{cx}" y="{cy+15}" text-anchor="middle" font-size="9.5" fill="#8a94a6" '
        f'letter-spacing="1">GROUPS</text></svg>'
    )
    legend = '<ul class="legend">' + "".join(
        f'<li><span class="dot" style="background:{_color(i)}"></span>'
        f'<span class="lab">{_esc(it.get("label",""))}</span>'
        f'<span class="pct">{float(it.get("share",0)):.0f}%</span></li>'
        for i, it in enumerate(items)
    ) + "</ul>"
    return (f'<div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap">'
            f'<div>{svg}</div><div style="flex:1;min-width:160px">{legend}</div></div>')


def _hbars(items: List[Dict[str, Any]], color_each: bool = False) -> str:
    total = sum(max(0.0, float(i.get("share", 0))) for i in items) or 1.0
    mx = max((max(0.0, float(i.get("share", 0))) for i in items), default=1.0) or 1.0
    rows = []
    for idx, it in enumerate(items):
        share = max(0.0, float(it.get("share", 0)))
        width = share / mx * 100
        col = _color(idx) if color_each else "var(--accent)"
        rows.append(
            f'<div class="hbar"><div class="row"><span class="lab">{_esc(it.get("label",""))}</span>'
            f'<span class="val">{share:.0f}%</span></div>'
            f'<div class="track"><span style="width:{width:.1f}%;background:{col}"></span></div></div>'
        )
    return '<div class="hbars">' + "".join(rows) + "</div>"


def _spark(n: int = 22, kind: str = "lognormal") -> str:
    """A small decorative sparkline that hints at a distribution shape."""
    import math
    vals = []
    for i in range(n):
        x = (i + 0.5) / n
        if "log" in kind or "pareto" in kind or "exp" in kind or "skew" in kind:
            v = math.exp(-((math.log(x + 0.04) + 1.6) ** 2) / 0.5)
        elif "poisson" in kind or "gamma" in kind:
            k = 3.0
            v = (x * 6) ** k * math.exp(-x * 6)
        elif "uniform" in kind:
            v = 0.8
        else:  # normal-ish bell
            v = math.exp(-((x - 0.5) ** 2) / 0.045)
        vals.append(v)
    mx = max(vals) or 1
    bars = "".join(f'<span style="height:{v/mx*100:.0f}%"></span>' for v in vals)
    return f'<div class="spark">{bars}</div>'


def _verdict_pill(v: str) -> str:
    v = (v or "").lower()
    if v == "plausible":
        return '<span class="pill good">plausible</span>'
    if v == "adjust":
        return '<span class="pill warn">adjust</span>'
    return '<span class="pill bad">unverifiable</span>'


def _src_cell(label: str, url: str) -> str:
    if url:
        return f'<a class="src" href="{_esc(url)}">{_esc(label or "source")}</a>'
    return f'<span class="src">{_esc(label or "")}</span>'


# --------------------------------------------------------------- builder ----

def build(data: Dict[str, Any]) -> str:
    biz = data.get("business", "Business")
    objective = data.get("objective", "")
    comments = data.get("comments", "")
    generated = data.get("generated", "")
    confidence = (data.get("confidence") or "medium").lower()

    body: List[str] = []

    # ----- hero
    conf_label = {"high": "High confidence", "medium": "Medium confidence", "low": "Low confidence"}.get(confidence, "Medium confidence")
    chips = [f'<span class="chip">&#128197; {_esc(generated)}</span>',
             f'<span class="chip">&#9211; {_esc(conf_label)}</span>']
    if comments:
        chips.append(f'<span class="chip">&#128205; {_esc(comments[:60])}</span>')
    body.append(
        '<div class="hero"><div class="inner">'
        '<div class="eyebrow">Domain research report</div>'
        f'<h1>{_esc(biz)}</h1>'
        f'<div class="obj"><strong>Objective.</strong> {_esc(objective)}</div>'
        f'<div class="meta">{"".join(chips)}</div>'
        '</div></div>'
    )

    # ----- summary + KPI cards
    if data.get("summary"):
        body.append(f'<section><p class="lead">{_esc(data["summary"])}</p></section>')

    profile = data.get("business_profile", {})
    attrs = profile.get("attributes", [])
    n_plausible = sum(1 for a in attrs if (a.get("verdict") or "").lower() == "plausible")
    n_adjust = sum(1 for a in attrs if (a.get("verdict") or "").lower() == "adjust")
    n_seg = len(data.get("customer_base", {}).get("segments", []))
    n_src = len(data.get("sources", []))
    body.append('<section><div class="cards">')
    body.append(f'<div class="card"><div class="k">Figures checked</div><div class="v">{len(attrs)}</div>'
                f'<div class="s">{n_plausible} hold up, {n_adjust} adjusted</div></div>')
    body.append(f'<div class="card"><div class="k">Customer segments</div><div class="v">{n_seg}</div>'
                f'<div class="s">archetypes found in research</div></div>')
    body.append(f'<div class="card"><div class="k">Metrics shaped</div><div class="v">{len(data.get("metrics",[]))}</div>'
                f'<div class="s">distributions with parameters</div></div>')
    body.append(f'<div class="card"><div class="k">Sources</div><div class="v">{n_src}</div>'
                f'<div class="s">consulted and cited</div></div>')
    body.append('</div></section>')

    # ----- business profile table
    if attrs:
        body.append('<section><h2>Business profile, fact-checked</h2>')
        rows = []
        for a in attrs:
            adj = f' &rarr; <strong>{_esc(a["adjust_to"])}</strong>' if a.get("adjust_to") else ""
            rows.append(
                f'<tr><td><strong>{_esc(a.get("name",""))}</strong></td>'
                f'<td>{_esc(a.get("stated","not stated"))}</td>'
                f'<td>{_esc(a.get("real_world_range",""))}{adj}</td>'
                f'<td>{_verdict_pill(a.get("verdict",""))}</td>'
                f'<td>{_src_cell(a.get("source",""), a.get("url",""))}</td></tr>'
            )
        body.append('<div class="tablewrap"><table><thead><tr>'
                    '<th>Attribute</th><th>Stated</th><th>Real-world range</th><th>Verdict</th><th>Source</th>'
                    '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')
        if profile.get("sanity_checks"):
            body.append('<div class="note"><strong>Sanity checks.</strong><ul class="clean">'
                        + "".join(f'<li>{_esc(s)}</li>' for s in profile["sanity_checks"]) + '</ul></div>')
        body.append('</section>')

    # ----- customer base: demographics (charts) + segments (donut)
    cb = data.get("customer_base", {})
    demos = cb.get("demographics", [])
    segments = cb.get("segments", [])
    if demos or segments:
        body.append('<section><h2>Who the customers are</h2><div class="split">')
        # demographics: first as donut if it looks like a split, rest as bars
        for i, d in enumerate(demos):
            brk = d.get("breakdown", [])
            chart = _donut(brk) if len(brk) <= 4 else _hbars(brk, color_each=False)
            src = ""
            if d.get("source") or d.get("url"):
                src = f'<div style="margin-top:8px">{_src_cell(d.get("source",""), d.get("url",""))}</div>'
            body.append(f'<div class="panel"><h3>{_esc(d.get("dimension",""))}</h3>{chart}{src}</div>')
        # segments donut
        if segments:
            seg_items = [{"label": s.get("name", ""), "share": s.get("share", 0)} for s in segments]
            body.append('<div class="panel"><h3>Segment mix</h3>' + _donut(seg_items) + '</div>')
        body.append('</div>')

        # segment detail table
        if segments:
            rows = []
            for i, s in enumerate(segments):
                rows.append(
                    f'<tr><td><span class="pill" style="background:{_color(i)}1f;color:{_color(i)}">'
                    f'{_esc(s.get("name",""))}</span></td>'
                    f'<td class="num">{float(s.get("share",0)):.0f}%</td>'
                    f'<td>{_esc(s.get("traits",""))}</td>'
                    f'<td>{_src_cell(s.get("source",""), s.get("url",""))}</td></tr>'
                )
            body.append('<div class="tablewrap" style="margin-top:16px"><table><thead><tr>'
                        '<th>Segment</th><th>Share</th><th>Distinguishing traits</th><th>Source</th>'
                        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')
        body.append('</section>')

    # ----- behavior facts
    behavior = cb.get("behavior", [])
    if behavior:
        body.append('<section><h2>How they behave</h2><div class="tablewrap"><table><thead><tr>'
                    '<th>Metric</th><th>Researched value</th><th>Source</th></tr></thead><tbody>')
        for b in behavior:
            body.append(f'<tr><td><strong>{_esc(b.get("metric",""))}</strong></td>'
                        f'<td>{_esc(b.get("value",""))}</td>'
                        f'<td>{_src_cell(b.get("source",""), b.get("url",""))}</td></tr>')
        body.append('</tbody></table></div></section>')

    # ----- metrics & distributions (with sparkline illustrations)
    metrics = data.get("metrics", [])
    if metrics:
        body.append('<section><h2>Metric shapes</h2><div class="tablewrap"><table><thead><tr>'
                    '<th>Metric</th><th>Shape</th><th>Illustration</th><th>Grounded parameters</th><th>Why</th>'
                    '</tr></thead><tbody>')
        for m in metrics:
            body.append(
                f'<tr><td><strong>{_esc(m.get("name",""))}</strong></td>'
                f'<td><span class="pill info">{_esc(m.get("shape",""))}</span></td>'
                f'<td style="min-width:120px">{_spark(kind=str(m.get("shape","")).lower())}</td>'
                f'<td><code>{_esc(m.get("params",""))}</code></td>'
                f'<td class="src">{_esc(m.get("rationale",""))} {_src_cell(m.get("source",""), m.get("url",""))}</td></tr>'
            )
        body.append('</tbody></table></div></section>')

    # ----- relationships
    rel = data.get("relationships", {})
    cors, conds, cons, outs = (rel.get("correlations", []), rel.get("conditionals", []),
                               rel.get("constraints", []), rel.get("outliers", []))
    if cors or conds or cons or outs:
        body.append('<section><h2>Relationships and rules</h2><div class="split">')
        if cors:
            body.append('<div class="panel"><h3>Correlations</h3><ul class="clean">'
                        + "".join(f'<li><strong>{_esc(c.get("between",""))}</strong>: {_esc(c.get("strength",""))}'
                                  + (f' <span class="src">({_esc(c.get("source",""))})</span>' if c.get("source") else "")
                                  + '</li>' for c in cors) + '</ul></div>')
        if conds:
            body.append('<div class="panel"><h3>Conditional patterns</h3><ul class="clean">'
                        + "".join(f'<li>{_esc(c)}</li>' for c in conds) + '</ul></div>')
        if cons:
            body.append('<div class="panel"><h3>Hard constraints</h3><ul class="clean">'
                        + "".join(f'<li><code>{_esc(c)}</code></li>' for c in cons) + '</ul></div>')
        if outs:
            body.append('<div class="panel"><h3>Outliers and edge cases</h3><ul class="clean">'
                        + "".join(f'<li>{_esc(o)}</li>' for o in outs) + '</ul></div>')
        body.append('</div></section>')

    # ----- open questions
    oq = data.get("open_questions", [])
    if oq:
        body.append('<section><h2>Open questions for you</h2>'
                    '<div class="note warn"><ul class="clean">'
                    + "".join(f'<li>{_esc(q)}</li>' for q in oq) + '</ul></div></section>')

    # ----- sources
    srcs = data.get("sources", [])
    if srcs:
        body.append('<section><h2>Sources</h2><div class="panel"><ol class="src-list">')
        for i, s in enumerate(srcs, 1):
            used = f'<div class="src">{_esc(s.get("used_for",""))}</div>' if s.get("used_for") else ""
            link = f'<a class="u" href="{_esc(s.get("url",""))}">{_esc(s.get("url",""))}</a>' if s.get("url") else ""
            body.append(f'<li><span class="num">{i}</span><div class="body">'
                        f'<div class="t">{_esc(s.get("title",""))}</div>{link}{used}</div></li>')
        body.append('</ol></div></section>')

    return _page(f"Research, {biz}", "\n".join(body))


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    src, out = argv[0], argv[1]
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    Path(out).write_text(build(data), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
