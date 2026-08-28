#!/usr/bin/env python3
"""Offline verification: real captured items, no network."""
import importlib.util, json, os, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

col = load("col", "collector/run.py")

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>OpenAI News</title>
<item><title><![CDATA[Advancing price-performance for developers with GPT-5.6 in Kiro]]></title>
<description><![CDATA[GPT-5.6 is now available in Kiro, helping developers plan, build, review, and test software with better price-performance.]]></description>
<link>https://openai.com/index/gpt-5-6-in-kiro</link><pubDate>Mon, 24 Aug 2026 12:00:00 GMT</pubDate></item>
<item><title><![CDATA[Improving GPT-5.6 Sol in ChatGPT-and expanding access to GPT-5.6 Luna for free users]]></title>
<description><![CDATA[ChatGPT introduces improved GPT-5.6 Sol with better accuracy, plus expanded access for free users and unlimited everyday chats with GPT-5.6 Luna.]]></description>
<link>https://openai.com/index/improving-gpt-5-6-sol-in-chatgpt</link><pubDate>Sun, 23 Aug 2026 10:00:00 GMT</pubDate></item>
<item><title><![CDATA[How NVIDIA scales expertise with ChatGPT Work]]></title>
<description><![CDATA[NVIDIA teams use ChatGPT Work to reduce manual tasks and scale successful workflows globally.]]></description>
<link>https://openai.com/index/nvidia/chatgpt-work</link><pubDate>Sat, 22 Aug 2026 00:00:00 GMT</pubDate></item>
<item><title><![CDATA[Testing ads in ChatGPT]]></title>
<description><![CDATA[OpenAI begins testing ads in ChatGPT to support free access, with clear labeling and user control.]]></description>
<link>https://openai.com/index/testing-ads-in-chatgpt</link><pubDate>Fri, 21 Aug 2026 10:00:00 GMT</pubDate></item>
<item><title><![CDATA[OpenAI appoints Dali Rajic as Chief Revenue Officer]]></title>
<description><![CDATA[OpenAI appoints Dali Rajic as Chief Revenue Officer to lead its global revenue organization.]]></description>
<link>https://openai.com/index/dali-rajic-chief-revenue-officer</link><pubDate>Fri, 21 Aug 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""

HTML_INDEX = """<html><body>
<a href="/news/claude-opus-5-1">Introducing Claude Opus 5.1</a>
<a href="/news/usage-limits-update">Updated usage limits for Claude Pro and Max plans</a>
<a href="/news/interpretability-research">New interpretability research on feature steering</a>
<a href="/pricing">Pricing</a><a href="/news/x">short</a>
</body></html>"""

XAI_INDEX = """<html><body>
<a href="/news/grok-4-6">Grok 4.6 is now available to all SuperGrok subscribers</a>
<a href="/news/spacex-acquires-xai">SpaceX announced today that it has acquired xAI.</a>
</body></html>"""

FEEDS = {"sources": [
  {"company":"openai","label":"OpenAI News","type":"rss","url":"mock://openai"},
  {"company":"anthropic","label":"Anthropic News","type":"scrape","url":"https://www.anthropic.com/news","link_pattern":"^/news/[a-z0-9-]+$"},
  {"company":"xai","label":"xAI News","type":"scrape","url":"https://x.ai/news","link_pattern":"^/news/[a-z0-9-]+$"},
  {"company":"google","label":"Gemini API Release Notes","type":"scrape","url":"https://ai.google.dev/x","link_pattern":"^/y/[a-z]+$"},
]}

MOCK = {"mock://openai": RSS,
        "https://www.anthropic.com/news": HTML_INDEX,
        "https://x.ai/news": XAI_INDEX}

def fake_fetch(url):
    if url in MOCK: return MOCK[url]
    raise TimeoutError("simulated network failure")

col.fetch = fake_fetch
col.POLITE_DELAY = 0
# Never clobber the real config.
tmp = os.path.join(ROOT, "config", "_feeds.selftest.json")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(FEEDS, f)
col.FEEDS = tmp
import sys; sys.argv=["x","--reclassify"]; col.main()

with open(os.path.join(ROOT, "data/latest.json"), encoding="utf-8") as f:
    d = json.load(f)

print("\n--- classification ---")
for i in d["items"]:
    print(f"  {i['materiality']:6} {i['category']:15} {'SUB ' if i['subscription_signal'] else '    '}{i['title'][:62]}")
print("\n--- health ---")
for h in d["feed_health"]:
    print(f"  {h['status']:7} {h['label']}: {h['message'][:60]}")

ren = load("ren", "renderer/run.py")
ren.main()
