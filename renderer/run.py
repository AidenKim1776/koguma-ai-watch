#!/usr/bin/env python3
"""
KOGUMA AI Watch — Renderer

Reads data/latest.json + config/matrix.json and writes docs/index.html.
Self-contained: data is embedded, so the page works from file:// too.
Standard library only.
"""

import html
import json
import os
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATEST = os.path.join(ROOT, "data", "latest.json")
MATRIX = os.path.join(ROOT, "config", "matrix.json")
OUT = os.path.join(ROOT, "docs", "index.html")

NAMES = {"openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "xai": "xAI"}
PERSONA = {"openai": "Muse", "anthropic": "Hanna", "google": "Vera", "xai": "Scarlett"}

CSS = """
:root{
  --bg:#0e0f11; --panel:#15171a; --line:#24272c; --line2:#1b1e22;
  --fg:#e6e4e0; --dim:#8b8f96; --dimmer:#5c6067;
  --high:#e0a458; --med:#7f93a8; --low:#5c6067;
  --ok:#5c8a6b; --fail:#b4565a; --new:#e0a458;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:14px;letter-spacing:.22em;font-weight:600;margin:0;text-transform:uppercase}
h2{font-size:11px;letter-spacing:.2em;color:var(--dim);font-weight:600;
  text-transform:uppercase;margin:0 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}
section{margin-top:42px}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;
  padding-bottom:18px;border-bottom:1px solid var(--line)}
.stamp{font-size:12px;color:var(--dim);text-align:right;line-height:1.7}
.stamp b{color:var(--fg);font-weight:500}
.stale{color:var(--fail);font-weight:600}
.banner{margin-top:16px;padding:10px 14px;border:1px solid var(--fail);
  border-radius:3px;font-size:13px;color:var(--fail)}

.status{display:grid;grid-template-columns:1fr;gap:1px;background:var(--line2)}
.srow{display:flex;justify-content:space-between;align-items:center;gap:12px;
  background:var(--panel);padding:11px 14px}
.srow.quiet{color:var(--dimmer)}
.srow .co{font-weight:600;letter-spacing:.04em}
.srow .co span{color:var(--dim);font-weight:400;font-size:12px;margin-left:8px}
.srow .n{font-size:12px;color:var(--dim);font-variant-numeric:tabular-nums}

.item{padding:14px 0 14px 14px;border-bottom:1px solid var(--line2);
  border-left:2px solid transparent}
.item.unseen{border-left-color:var(--new)}
.item:last-child{border-bottom:none}
.item .t{font-size:15px;line-height:1.45}
.item .t a{color:var(--fg);text-decoration:none;border-bottom:1px solid var(--line)}
.item .t a:hover{border-bottom-color:var(--dim)}
.item .s{color:var(--dim);font-size:13px;margin-top:5px}
.meta{margin-top:7px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--dimmer);display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.chip{padding:1px 7px;border:1px solid var(--line);border-radius:2px}
.m-high{color:var(--high);border-color:var(--high)}
.m-medium{color:var(--med);border-color:var(--med)}
.m-low{color:var(--low)}
.sub{color:var(--high)}
.group{margin-bottom:26px}
.group h3{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim);
  font-weight:600;margin:0 0 4px}
.none{color:var(--dim);font-size:14px;padding:6px 0}

table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line2);vertical-align:top}
th{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);font-weight:600}
td.co{font-weight:600;white-space:nowrap}
td.empty{color:var(--dimmer)}

.health{font-size:13px}
.health div{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid var(--line2)}
.health .st{width:80px;flex:none;font-size:11px;letter-spacing:.1em;text-transform:uppercase}
.st.ok{color:var(--ok)} .st.failed{color:var(--fail)} .st.empty{color:var(--high)}
.health .msg{color:var(--dim)}

button{font:inherit;font-size:12px;letter-spacing:.1em;text-transform:uppercase;
  background:transparent;color:var(--dim);border:1px solid var(--line);
  padding:7px 14px;border-radius:2px;cursor:pointer}
button:hover{color:var(--fg);border-color:var(--dim)}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);
  font-size:12px;color:var(--dimmer);line-height:1.7}
@media(max-width:600px){.wrap{padding:20px 14px 60px}.stamp{text-align:left}}
"""


def esc(s):
    return html.escape(s or "", quote=True)


def kst(iso):
    if not iso:
        return None
    d = datetime.fromisoformat(iso)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone(timedelta(hours=9)))


def ago(iso, now):
    d = kst(iso)
    if not d:
        return "never"
    h = (now - d).total_seconds() / 3600
    if h < 1:
        return f"{int(h*60)} min ago"
    if h < 48:
        return f"{int(h)} hours ago"
    return f"{int(h/24)} days ago"


def render_item(i):
    cls = "item"
    summary = f'<div class="s">{esc(i["raw_summary"][:220])}</div>' if i.get("raw_summary") else ""
    sub = '<span class="chip sub">subscription</span>' if i.get("subscription_signal") else ""
    return f"""<div class="{cls}" data-id="{esc(i['id'])}" data-seen="{esc(i['first_seen_at'])}">
  <div class="t"><a href="{esc(i['url'])}" target="_blank" rel="noopener">{esc(i['title'])}</a></div>
  {summary}
  <div class="meta">
    <span class="chip m-{esc(i['materiality'])}">{esc(i['materiality'])}</span>
    <span class="chip">{esc(i['category'].replace('_',' '))}</span>
    {sub}
    <span>{esc(i['source_label'])}</span>
  </div>
</div>"""


def main():
    with open(LATEST, encoding="utf-8") as f:
        d = json.load(f)
    with open(MATRIX, encoding="utf-8") as f:
        mx = json.load(f)

    now = kst(datetime.now(timezone.utc).isoformat())
    last = kst(d.get("last_success"))
    stale = last is None or (now - last).total_seconds() > 36 * 3600

    items = d["items"]
    new_ids = set(d.get("new_ids", []))

    # STATUS
    status = ""
    for c in d["companies"]:
        n = sum(1 for i in items if i["company"] == c and i["id"] in new_ids)
        quiet = " quiet" if n == 0 else ""
        label = "—" if n == 0 else f"{n} new"
        status += (f'<div class="srow{quiet}"><div class="co">{NAMES[c]}'
                   f'<span>{PERSONA[c]}</span></div><div class="n">{label}</div></div>')

    # WHAT CHANGED
    changed = ""
    order = {"high": 0, "medium": 1, "low": 2}
    for c in d["companies"]:
        grp = sorted((i for i in items if i["company"] == c and i["id"] in new_ids),
                     key=lambda i: order.get(i["materiality"], 3))
        if not grp:
            continue
        changed += (f'<div class="group"><h3>{NAMES[c]}</h3>'
                    + "".join(render_item(i) for i in grp) + "</div>")
    if not changed:
        changed = '<div class="none">No material updates in the last 24 hours.</div>'

    # MATRIX
    cols = "".join(f"<th>{esc(x)}</th>" for x in mx["columns"])
    rows = ""
    for c in d["companies"]:
        cells = ""
        for v in mx["rows"].get(c, []):
            cells += f'<td class="empty">—</td>' if not v else f"<td>{esc(v)}</td>"
        rows += f'<tr><td class="co">{NAMES[c]}</td>{cells}</tr>'
    reviewed = mx.get("last_reviewed") or "never reviewed"

    # HEALTH
    health = ""
    for h in d["feed_health"]:
        health += (f'<div><span class="st {esc(h["status"])}">{esc(h["status"])}</span>'
                   f'<span>{esc(h["label"])}</span>'
                   f'<span class="msg">{esc(h["message"])}</span></div>')

    banner = ('<div class="banner">Collection is stale — the last successful run was over '
              '36 hours ago. Check the Actions log.</div>') if stale else ""

    digest = json.dumps([{k: i[k] for k in ("company", "title", "url", "category",
                                            "materiality", "subscription_signal")}
                         for i in items if i["id"] in new_ids], ensure_ascii=False)

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KOGUMA AI Watch</title><style>{CSS}</style></head><body>
<div class="wrap">

<div class="head">
  <h1>KOGUMA AI Watch</h1>
  <div class="stamp">
    <b>{last:%Y-%m-%d %H:%M} KST</b> · {ago(d.get('last_success'), now)}<br>
    <span class="{'stale' if stale else ''}">
    {len(new_ids)} new · {len(items)}-item window · {'degraded run' if d.get('degraded') else 'clean run'}</span>
  </div>
</div>
{banner}

<section><h2>Status</h2><div class="status">{status}</div></section>

<section><h2>What changed</h2>{changed}</section>

<section><h2>Capability matrix</h2>
<table><thead><tr><th></th>{cols}</tr></thead><tbody>{rows}</tbody></table>
<p class="none">Slow axis — edited by hand in <code>config/matrix.json</code>. Last reviewed: {esc(str(reviewed))}.</p>
</section>

<section><h2>Judgement</h2>
<p class="none">Analysis is deliberately not automated. Copy the digest and take it to Hanna when something looks like it moves the subscription decision.</p>
<button id="copy">Copy digest</button>
</section>

<section><h2>Feed health</h2><div class="health">{health}</div></section>

<footer>
KOGUMA Systems · central monitoring · sources read in English<br>
The unseen marker is stored in this browser only and does not sync across devices.
</footer>
</div>

<script>
(function(){{
  var KEY='koguma-ai-watch-last-visit';
  var prev=localStorage.getItem(KEY);
  document.querySelectorAll('.item').forEach(function(el){{
    if(!prev || el.dataset.seen > prev) el.classList.add('unseen');
  }});
  localStorage.setItem(KEY, new Date().toISOString());
  var d={digest};
  document.getElementById('copy').addEventListener('click', function(){{
    navigator.clipboard.writeText(JSON.stringify(d,null,1)).then(function(){{
      var b=document.getElementById('copy'); b.textContent='Copied';
      setTimeout(function(){{b.textContent='Copy digest';}},1600);
    }});
  }});
}})();
</script>
</body></html>"""

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"wrote {OUT}  ({len(items)} items, {len(new_ids)} new)")


if __name__ == "__main__":
    main()
