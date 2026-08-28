# KOGUMA AI Watch

Daily monitoring of OpenAI, Anthropic, Google, and xAI. Sources are read in
their original English. One page, opened each morning.

Operated by KOGUMA Systems as a central monitoring instrument. It exists to
answer one recurring question: **has anything changed that should alter which
AI subscriptions KOGUMA pays for?**

## Cost

**Zero.** No API keys, no paid services, no dependencies.

- Python standard library only — nothing to `pip install`.
- GitHub Actions and Pages are free on public repositories.
- Analysis is rule-based. No model is called at any point.

Judgement is deliberately left to a human. The dashboard has a **Copy digest**
button; take the digest to Hanna when something looks like it moves the
subscription decision. That runs on an existing Claude subscription and costs
nothing extra.

## Setup

1. Create a **public** repository and push this tree.
   Public matters: Pages is free there, and everything monitored is public news
   anyway. Note that the rendered page is publicly reachable — keep private
   judgements out of `config/matrix.json`.
2. Settings → Pages → Source: *Deploy from a branch*, branch `main`, folder `/docs`.
3. Actions → *KOGUMA AI Watch* → **Run workflow** to seed the first run.
4. Bookmark `https://<user>.github.io/<repo>/`.

Locally: `python3 collector/run.py && python3 renderer/run.py`, then open
`docs/index.html`. It works from `file://` — the data is embedded.

## Repairing a broken source

`FEED HEALTH` at the bottom of the page names every failure. When a source
breaks, edit `config/feeds.json`:

- `type: rss` — set `url` to the feed. Nothing else needed.
- `type: scrape` — set `url` to the index page and `link_pattern` to a regex
  matched against link paths (e.g. `^/news/[a-z0-9-]+$`). Deliberately loose:
  it survives CSS changes, unlike a selector.

Scrape sources have no publication date. `first_seen_at` is used instead, so an
article already on the page when a scraper is first added will be dated the day
you added it. This settles within a week.

## After editing the rules

`collector/run.py` classifies **new items only**. Having changed the rules in
`RULES`, `SUBSCRIPTION_RX`, or `ESCALATE_RX`, run:

```
python3 collector/run.py --reclassify
```

Without it, the existing seven-day window keeps its old labels.

## Capability matrix

`config/matrix.json` is the slow axis and is **never written by the collector**.
Empty values render as `—` rather than a guess. Fill a cell only when you have
verified it; the point of the dashboard is that it does not assert things nobody
checked.

## Verification

`python3 selftest.py` runs the whole pipeline offline against captured items,
including a deliberately failing source, and confirms a degraded run still
produces a page.

## Known limits

- The unseen marker uses `localStorage` — per browser, no sync across devices.
- Actions `cron` is frequently delayed. Trust the timestamp in the header, not
  the schedule.
- Rule-based classification is shallow by design. It sorts and surfaces; it does
  not interpret.

---

*Sources verified 2026-08-25. Anthropic publishes no RSS feed; xAI publishes none
either and now brands as SpaceXAI following the SpaceX acquisition — both are
scraped.*
