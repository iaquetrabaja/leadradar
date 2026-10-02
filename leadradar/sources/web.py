"""Web search restricted to sites — this is how LinkedIn, X, Quora, forums etc.
are covered without logging in (no account, no ban risk).

Providers:
- ddgs   : free metasearch, no key. Fine to start; results are thinner.
- serper : Google results (SERPER_API_KEY, 2,500 free queries).
- brave  : Brave Search API (BRAVE_API_KEY).
- exa    : semantic search (EXA_API_KEY) — great for "people asking for X".
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone

from leadradar import net
from leadradar.config import env
from leadradar.models import Item

log = logging.getLogger("leadradar")

FRESHNESS = {
    "ddgs": {"day": "d", "week": "w", "month": "m"},
    "serper": {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m"},
    "brave": {"day": "pd", "week": "pw", "month": "pm"},
}


def date_from_url(url: str) -> datetime | None:
    """LinkedIn activity ids and X status ids embed their creation time (first 41 bits =
    milliseconds), so search results without a date can still be filtered by age."""
    m = re.search(r"(?:activity[-:]|ugcPost[-:]|share[-:])(\d{18,20})", url)
    if m and "linkedin.com" in url:
        return datetime.fromtimestamp((int(m.group(1)) >> 22) / 1000, tz=timezone.utc)
    m = re.search(r"(?:x|twitter)\.com/[^/]+/status/(\d{15,20})", url)
    if m:
        return datetime.fromtimestamp(((int(m.group(1)) >> 22) + 1288834974657) / 1000, tz=timezone.utc)
    return None


def _site_label(url: str, sites: list[str]) -> str:
    for s in sites:
        if s.split("/")[0] in url:
            return s.split("/")[0]
    return "web"


def _ddgs(query: str, conf: dict) -> list[dict]:
    from ddgs import DDGS

    res = DDGS().text(
        query,
        region=conf.get("region", "wt-wt"),
        timelimit=FRESHNESS["ddgs"][conf["freshness"]],
        max_results=conf["results_per_query"],
    )
    return [{"url": r["href"], "title": r.get("title", ""), "text": r.get("body", "")} for r in res or []]


def _serper(query: str, conf: dict) -> list[dict]:
    key = env("SERPER_API_KEY")
    if not key:
        raise SystemExit("web.provider=serper needs SERPER_API_KEY")
    region = conf.get("region", "")
    payload = {"q": query, "tbs": FRESHNESS["serper"][conf["freshness"]], "num": conf["results_per_query"]}
    if "-" in region:
        payload["gl"], payload["hl"] = region.split("-")[1], region.split("-")[0]
    resp = net.client().post("https://google.serper.dev/search", json=payload, headers={"X-API-KEY": key})
    resp.raise_for_status()
    return [
        {"url": r["link"], "title": r.get("title", ""), "text": r.get("snippet", ""), "date": r.get("date")}
        for r in resp.json().get("organic", [])
    ]


def _brave(query: str, conf: dict) -> list[dict]:
    key = env("BRAVE_API_KEY")
    if not key:
        raise SystemExit("web.provider=brave needs BRAVE_API_KEY")
    data = net.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "freshness": FRESHNESS["brave"][conf["freshness"]], "count": min(conf["results_per_query"], 20)},
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
    ).json()
    return [
        {"url": r["url"], "title": r.get("title", ""), "text": r.get("description", ""), "date": r.get("age")}
        for r in data.get("web", {}).get("results", [])
    ]


def _exa(query: str, conf: dict, domains: list[str], since: datetime) -> list[dict]:
    key = env("EXA_API_KEY")
    if not key:
        raise SystemExit("web.provider=exa needs EXA_API_KEY")
    resp = net.client().post(
        "https://api.exa.ai/search",
        headers={"x-api-key": key},
        json={
            "query": query,
            "numResults": conf["results_per_query"],
            "includeDomains": domains,
            "startPublishedDate": since.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "contents": {"text": {"maxCharacters": 1500}},
        },
    )
    resp.raise_for_status()
    return [
        {"url": r["url"], "title": r.get("title") or "", "text": r.get("text") or "", "date": r.get("publishedDate"), "author": r.get("author") or ""}
        for r in resp.json().get("results", [])
    ]


def collect(conf: dict, ctx) -> list[Item]:
    provider = conf.get("provider", "ddgs")
    sites: list[str] = conf.get("sites") or []
    budget = conf.get("max_requests", 40)
    raw: list[dict] = []

    if provider == "exa":
        # Exa filters domains natively: one request per query covers all sites.
        domains = sorted({s.split("/")[0] for s in sites})
        for q in ctx.queries[:budget]:
            raw += _exa(q, conf, domains, ctx.since)
    else:
        search = {"ddgs": _ddgs, "serper": _serper, "brave": _brave}[provider]
        pairs = [(q, s) for s in (sites or [""]) for q in ctx.queries]
        if len(pairs) > budget:
            log.info("web: %d site×query combos, capped to max_requests=%d", len(pairs), budget)
        for q, site in pairs[:budget]:
            query = f"site:{site} {q}" if site else q
            try:
                raw += search(query, conf)
            except SystemExit:
                raise
            except Exception as e:  # one bad query shouldn't kill the run
                (log.debug if "No results" in str(e) else log.warning)("web: %s failed for %r: %s", provider, query, e)
            time.sleep(1.5 if provider == "ddgs" else 0.3)

    # Snippet-only results have no reliable date; trust the engine's freshness filter.
    fallback_date = datetime.now(timezone.utc) - timedelta(hours=1)
    items = []
    for r in raw:
        created = None
        if r.get("date"):
            try:
                created = datetime.fromisoformat(str(r["date"]).replace("Z", "+00:00"))
            except ValueError:
                created = None
        created = date_from_url(r["url"]) or created
        items.append(
            Item(
                source=f"web:{_site_label(r['url'], sites)}",
                native_id=r["url"].split("?")[0],
                url=r["url"],
                title=r.get("title", ""),
                text=r.get("text", ""),
                author=r.get("author", ""),
                created_at=created or fallback_date,
            )
        )
    return items
