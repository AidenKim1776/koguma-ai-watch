#!/usr/bin/env python3
"""
KOGUMA AI Watch — Collector

Fetches AI company announcements, normalises them, classifies them by rule,
and writes data/latest.json. Standard library only. No API calls. No cost.

Run:  python3 collector/run.py
"""

import argparse
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDS = os.path.join(ROOT, "config", "feeds.json")
LATEST = os.path.join(ROOT, "data", "latest.json")
ARCHIVE = os.path.join(ROOT, "data", "archive")

UA = "KOGUMA-AI-Watch/1.0 (+https://github.com/)"
TIMEOUT = 25
RETRIES = 2
POLITE_DELAY = 1.5
WINDOW_DAYS = 7
DEFAULT_MAX_ITEMS = 25      # per source, per run
DATELESS_MAX_ITEMS = 12     # scrape sources: no dates, so they linger — keep them tight

COMPANIES = ["openai", "anthropic", "google", "xai"]


# ---------------------------------------------------------------- fetching

def fetch(url):
    """GET a URL with retries. Returns text, or raises the last error."""
    last = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9",
                "Accept-Language": "en",
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
            return raw.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001 — we genuinely want any failure
            last = e
            if attempt < RETRIES:
                time.sleep(2 ** attempt)
    raise last


# ---------------------------------------------------------------- parsing

def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s):
    """Parse RFC-822 or ISO-8601 into an aware UTC datetime, or None."""
    if not s:
        return None
    s = s.strip()
    fmts = [
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d",
    ]
    for f in fmts:
        try:
            d = datetime.strptime(s.replace("GMT", "+0000"), f)
            return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def parse_feed(text):
    """Parse RSS 2.0 or Atom. Returns list of dicts."""
    root = ET.fromstring(text.encode("utf-8"))
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    out = []

    for item in root.iter():
        tag = item.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue

        def get(*names):
            for n in names:
                el = item.find(n) if "}" not in n else item.find(n, ns)
                if el is None:
                    el = item.find("atom:" + n, ns)
                if el is not None and (el.text or "").strip():
                    return el.text.strip()
            return ""

        title = strip_tags(get("title"))
        link = get("link")
        if not link:
            el = item.find("atom:link", ns)
            if el is not None:
                link = el.attrib.get("href", "")
        summary = strip_tags(get("description", "summary", "content"))
        pub = parse_date(get("pubDate", "published", "updated"))

        if title and link:
            out.append({"title": title, "url": link, "raw_summary": summary[:800],
                        "published_at": pub.isoformat() if pub else None})
    return out


def parse_scrape(text, base_url, link_pattern):
    """Extract article links from an index page by href pattern."""
    from urllib.parse import urljoin, urlparse

    rx = re.compile(link_pattern)
    seen, out = set(), []

    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', text, re.I | re.S):
        href, inner = m.group(1), strip_tags(m.group(2))
        path = urlparse(href).path or href
        if not rx.match(path):
            continue
        full = urljoin(base_url, href)
        if full in seen or len(inner) < 12:
            continue
        seen.add(full)
        out.append({"title": inner[:300], "url": full, "raw_summary": "", "published_at": None})
    return out


# ---------------------------------------------------------------- classification

MODEL_WORDS = r"(gpt-?[\d.]+\w*|chatgpt|codex|claude|opus|sonnet|haiku|gemini|gemma|veo|imagen|lyria|grok)"

RULES = [
    ("customer_story", r"^how [\w\s.'&-]+ (uses?|builds?|ships?|scales?|built|is |transform)|case stud|customer stor", "low"),
    ("legal",          r"\b(lawsuit|sued?|court|settlement|antitrust|ftc|subpoena|copyright claim|acquisition|acquires?|acquired|s-1|ipo)\b", "medium"),
    ("pricing",        r"\b(pricing|price|per million tokens|cost|free (tier|users?|access|mode)|"
                       r"subscriptions?|plans?|tiers?|seats?|credits?|rate limits?|usage limits?|"
                       r"quotas?|ads?|advertis\w+|monetiz\w+)\b", "high"),
    ("model_release",  r"\b(introducing|announcing|now available|generally available|launch(es|ing|ed)?|releas(e|es|ing|ed)|preview(ing)?|rolling out)\b.*" + MODEL_WORDS, "high"),
    ("capability",     r"\b(agent|agentic|reasoning|context window|multimodal|memory|voice|vision|tool use|search|coding)\b", "medium"),
    ("infrastructure", r"\b(data ?cent(er|re)|chip|gpu|compute|cluster|stargate|inference|supercomput)\b", "low"),
    ("personnel",      r"\b(appoints?|joins? the board|names? .* (ceo|cto|cfo)|steps? down|hires?|chief \w+ officer)\b", "low"),
    ("policy",         r"\b(safety|policy|governance|regulation|eu ai act|youth|teen|privacy|transparency|national security|election)\b", "medium"),
    ("research",       r"\b(benchmark|paper|research|evaluation|system card|study|report)\b", "low"),
]

# Signals that this item bears on what KOGUMA pays for.
SUBSCRIPTION_RX = re.compile(
    r"\b(pricing|price|subscriptions?|plans?|tiers?|free (users?|tier|access|mode)|pro\b|plus\b|"
    r"max\b|supergrok|business|enterprise seats?|rate limits?|usage limits?|quotas?|credits?|"
    r"ads?|advertis\w+|now available to (all )?(users|subscribers))\b", re.I)

# Ownership or control of a provider changing hands outranks its category default.
ESCALATE_RX = re.compile(r"\b(acquir\w+|acquisition|merger|shut(ting)? down|discontinu\w+|"
                         r"deprecat\w+|retire(ment|s|d)?|sunset)\b", re.I)


def classify(title, summary):
    blob = f"{title}. {summary}".lower()
    for cat, rx, mat in RULES:
        if re.search(rx, blob, re.I):
            return cat, mat
    return "other", "low"


def flagship(title):
    """Does the title name a model? Used to promote materiality."""
    return bool(re.search(MODEL_WORDS, title, re.I))


# ---------------------------------------------------------------- pipeline

def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def item_id(url):
    return hashlib.sha1(url.split("?")[0].encode()).hexdigest()[:16]


def load_prev():
    if os.path.exists(LATEST):
        with open(LATEST, encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "feed_health": [], "last_success": None}


def main():
    ap = argparse.ArgumentParser(description="KOGUMA AI Watch collector")
    ap.add_argument("--baseline", action="store_true",
                    help="Treat everything collected as already seen. Applied automatically "
                         "on the first run so that back catalogue is not reported as news.")
    ap.add_argument("--reclassify", action="store_true",
                    help="Re-apply classification rules to every item in the window. "
                         "Use after editing the rules; otherwise only new items are classified.")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    with open(FEEDS, encoding="utf-8") as f:
        sources = json.load(f)["sources"]

    prev = load_prev()
    first_run = not prev.get("items")
    baseline = args.baseline or first_run
    by_id = {i["id"]: i for i in prev.get("items", [])}
    seen_titles = {norm_title(i["title"]) for i in prev.get("items", [])}

    health, fresh = [], []

    for src in sources:
        label = src["label"]
        try:
            text = fetch(src["url"])
            raw = (parse_feed(text) if src["type"] == "rss"
                   else parse_scrape(text, src["url"], src["link_pattern"]))
        except Exception as e:  # noqa: BLE001
            health.append({"label": label, "company": src["company"],
                           "status": "failed", "message": f"{type(e).__name__}: {e}"[:200]})
            print(f"  FAILED  {label}: {e}")
            continue
        finally:
            time.sleep(POLITE_DELAY)

        cap = src.get("max_items") or (DEFAULT_MAX_ITEMS if src["type"] == "rss"
                                       else DATELESS_MAX_ITEMS)
        raw = raw[:cap]   # sources list newest first

        if not raw:
            health.append({"label": label, "company": src["company"],
                           "status": "empty", "message": "Source parsed but returned no items."})
            print(f"  EMPTY   {label}")
            continue

        added = 0
        for r in raw:
            iid = item_id(r["url"])
            nt = norm_title(r["title"])
            if iid in by_id or nt in seen_titles:
                continue
            cat, mat = classify(r["title"], r["raw_summary"])
            if cat == "model_release" and not flagship(r["title"]):
                mat = "medium"
            if ESCALATE_RX.search(r["title"]):
                mat = "high"
            item = {
                "id": iid,
                "company": src["company"],
                "source_label": label,
                "title": r["title"],
                "url": r["url"],
                "raw_summary": r["raw_summary"],
                "published_at": r["published_at"],
                "first_seen_at": now.isoformat(),
                "category": cat,
                "materiality": mat,
                "subscription_signal": bool(SUBSCRIPTION_RX.search(f"{r['title']} {r['raw_summary']}")),
            }
            by_id[iid] = item
            seen_titles.add(nt)
            fresh.append(item)
            added += 1

        health.append({"label": label, "company": src["company"], "status": "ok",
                       "message": f"{len(raw)} of newest items kept (cap {cap}), {added} new."})
        print(f"  OK      {label}: {len(raw)} kept (cap {cap}), {added} new")

    # Rolling window: keep items whose effective date is within WINDOW_DAYS.
    cutoff = now - timedelta(days=WINDOW_DAYS)
    keep, retire = [], []
    for i in by_id.values():
        eff = parse_date(i.get("published_at")) or parse_date(i["first_seen_at"]) or now
        (keep if eff >= cutoff else retire).append(i)

    if args.reclassify:
        for i in keep:
            cat, mat = classify(i["title"], i.get("raw_summary", ""))
            if cat == "model_release" and not flagship(i["title"]):
                mat = "medium"
            if ESCALATE_RX.search(i["title"]):
                mat = "high"
            i["category"], i["materiality"] = cat, mat
            i["subscription_signal"] = bool(
                SUBSCRIPTION_RX.search(f"{i['title']} {i.get('raw_summary','')}"))
        print(f"  reclassified {len(keep)} items")

    keep.sort(key=lambda i: parse_date(i.get("published_at")) or parse_date(i["first_seen_at"]) or now,
              reverse=True)

    if retire:
        os.makedirs(ARCHIVE, exist_ok=True)
        path = os.path.join(ARCHIVE, f"{now:%Y-%m-%d}.json")
        old = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old = json.load(f)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(old + retire, f, ensure_ascii=False, indent=1)

    degraded = any(h["status"] == "failed" for h in health)
    out = {
        "generated_at": now.isoformat(),
        "last_success": now.isoformat() if not all(h["status"] == "failed" for h in health)
                        else prev.get("last_success"),
        "degraded": degraded,
        "window_days": WINDOW_DAYS,
        "companies": COMPANIES,
        "items": keep,
        "new_ids": [] if baseline else [i["id"] for i in fresh],
        "baseline_run": baseline,
        "feed_health": health,
    }
    os.makedirs(os.path.dirname(LATEST), exist_ok=True)
    with open(LATEST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    if baseline:
        print("  BASELINE: this intake is recorded as history, not reported as news.")
    print(f"\n{len(fresh)} collected / {len(keep)} in window / {len(retire)} archived"
          f"{'  [DEGRADED]' if degraded else ''}")


if __name__ == "__main__":
    main()
