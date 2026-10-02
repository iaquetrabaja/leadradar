"""Static exports: leads.csv + leads.html (sortable, filterable, works offline)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from leadradar.db import Store

FIELDS = ["found_at", "score", "intent", "source", "title", "summary", "why", "draft", "author", "url"]

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LeadRadar</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e4e4df;--accent:#2f6fed;--hot:#d9480f}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1e1e1c;--fg:#ecece8;--muted:#9a9a93;--line:#30302d;--accent:#7aa2ff;--hot:#ff8a4c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:920px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 16px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
input,select{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}
input{flex:1;min-width:180px}
.lead{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:10px}
.top{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;color:var(--muted);font-size:13px}
.score{font-weight:700;color:var(--fg);font-size:15px}.score.hot{color:var(--hot)}
.title{font-weight:600;margin:6px 0 2px}.title a{color:inherit}
details{margin-top:8px}summary{cursor:pointer;color:var(--accent)}
.draft{white-space:pre-wrap;background:var(--bg);border-radius:8px;padding:10px;margin-top:6px}
button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 10px;cursor:pointer;margin-top:6px}
</style></head><body><main>
<h1>📡 LeadRadar</h1><p class="sub" id="count"></p>
<div class="bar"><input id="q" placeholder="Filter…"><select id="src"><option value="">All sources</option></select>
<select id="min"><option value="0">Any score</option><option value="60">60+</option><option value="70" selected>70+</option><option value="85">85+</option></select></div>
<div id="list"></div></main>
<script>
const LEADS = __DATA__;
const $ = s => document.querySelector(s), esc = s => (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
[...new Set(LEADS.map(l => l.source))].sort().forEach(s => $("#src").insertAdjacentHTML("beforeend", `<option>${esc(s)}</option>`));
function render(){
  const q = $("#q").value.toLowerCase(), src = $("#src").value, min = +$("#min").value;
  const rows = LEADS.filter(l => l.score >= min && (!src || l.source === src) && (!q || JSON.stringify(l).toLowerCase().includes(q)));
  $("#count").textContent = `${rows.length} of ${LEADS.length} leads`;
  $("#list").innerHTML = rows.map((l, i) => `<div class="lead">
    <div class="top"><span class="score ${l.score>=85?"hot":""}">${l.score}</span><span>${esc(l.intent)}</span><span>${esc(l.source)}</span><span>${esc((l.found_at||"").slice(0,10))}</span><span>${esc(l.author)}</span></div>
    <div class="title">${l.url ? `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title || l.summary)}</a>` : esc(l.title || l.summary)}</div>
    <div>${esc(l.summary)}</div><div style="color:var(--muted)">${esc(l.why)}</div>
    ${l.draft ? `<details><summary>Draft</summary><div class="draft">${esc(l.draft)}</div><button data-i="${LEADS.indexOf(l)}">Copy</button></details>` : ""}
  </div>`).join("");
}
document.addEventListener("click", e => { const i = e.target.dataset.i; if (i !== undefined) { navigator.clipboard.writeText(LEADS[i].draft); e.target.textContent = "Copied ✓"; } });
["#q","#src","#min"].forEach(s => $(s).addEventListener("input", render)); render();
</script></body></html>"""


def write(store: Store, output_dir: str, min_score: int) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [{k: r[k] for k in FIELDS} for r in store.recent_leads(min_score=40)]
    with open(out / "leads.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    for r in rows:  # only http(s) links are clickable — no javascript: URLs from scraped data
        if not str(r["url"] or "").lower().startswith(("http://", "https://")):
            r["url"] = ""
    # Escape every "<" so data can never open or close a tag inside the <script>.
    data = json.dumps(rows, ensure_ascii=False).replace("<", "\\u003c")
    page = PAGE.replace("__DATA__", data).replace('value="70" selected', f'value="{min_score}" selected' if min_score in (0, 60, 70, 85) else 'value="70" selected')
    (out / "leads.html").write_text(page, encoding="utf-8")
    return out / "leads.html"
