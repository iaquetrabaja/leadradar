"""Apify actors (APIFY_API_TOKEN): the reliable way to search LinkedIn posts, X,
Instagram, Facebook groups… without logging in with your own account.
Pay-per-result on your Apify account. Presets: linkedin (≈ $2 / 1,000 posts),
x (≈ $0.40 / 1,000 tweets), reddit (Reddit Scraper Lite, pay per result).

Config:
    apify:
      enabled: true
      max_per_query: 25
      actors:
        - preset: linkedin            # built-in mappings: linkedin | x | reddit
        - preset: x
        - actor: someuser/x-search    # any actor, with your own input + field map
          input: {searchTerms: "{queries}", maxItems: 25}
          fields: {url: url, text: text, author: author.userName, date: createdAt, title: ""}
In `input`, the string "{queries}" becomes the query list and "{query}" runs
the actor once per query.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from leadradar import net
from leadradar.config import env
from leadradar.models import Item

log = logging.getLogger("leadradar")



def _linkedin_window(since: datetime) -> str:
    hours = (datetime.now(timezone.utc) - since).total_seconds() / 3600
    return "24h" if hours <= 24 else "week" if hours <= 168 else "month"


def _reddit_window(since: datetime) -> str:
    hours = (datetime.now(timezone.utc) - since).total_seconds() / 3600
    return "day" if hours <= 24 else "week" if hours <= 168 else "month"


PRESETS = {
    "linkedin": {
        "actor": "harvestapi/linkedin-post-search",
        "input": lambda conf, ctx: {
            "searchQueries": ctx.queries,
            "maxPosts": conf.get("max_per_query", 25),
            "postedLimit": _linkedin_window(ctx.since),
            "sortBy": "date",
        },
        "fields": {
            "url": "linkedinUrl",
            "text": "content",
            "author": "author.name",
            "author_info": "author.info",
            "date": "postedAt.date",
            "title": "",
        },
        "label": "linkedin.com",
    },
    # X/Twitter search, no account needed (~$0.40 per 1,000 tweets).
    "x": {
        "actor": "apidojo/tweet-scraper",
        "input": lambda conf, ctx: {
            "searchTerms": ctx.queries,
            "maxItems": conf.get("max_per_query", 25) * len(ctx.queries),
            "sort": "Latest",
            "start": ctx.since.strftime("%Y-%m-%d"),
            **({"tweetLanguage": conf["x_lang"]} if conf.get("x_lang") else {}),
        },
        "fields": {"url": "url", "text": "fullText|text", "author": "author.userName", "date": "createdAt", "title": ""},
        "label": "x.com",
    },
    # Reddit search without login — Reddit blocks anonymous API access since 2025.
    "reddit": {
        "actor": "trudax/reddit-scraper-lite",
        "input": lambda conf, ctx: {
            # Quoted = exact phrase; unquoted Reddit search matches almost anything.
            "searches": [q if q.startswith('"') else f'"{q}"' for q in ctx.queries],
            "sort": "new",
            "time": _reddit_window(ctx.since),
            "maxItems": conf.get("max_per_query", 25) * len(ctx.queries),
            "maxPostCount": conf.get("max_per_query", 25),
            "searchPosts": True,
            "skipComments": True,
            "skipUserPosts": True,
            "skipCommunity": True,
            "includeNSFW": False,
        },
        "fields": {"url": "url", "text": "body", "author": "username", "date": "createdAt", "title": "title"},
        "label": "reddit.com",
    },
}


def _pick(obj, path: str):
    """Dotted path into a row; "a|b" tries a, then b."""
    if not path:
        return ""
    if "|" in path:
        for alt in path.split("|"):
            value = _pick(obj, alt)
            if value not in ("", None):
                return value
        return ""
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return ""
    return obj if obj is not None else ""


def _fill(template, queries: list[str], query: str | None):
    if isinstance(template, dict):
        return {k: _fill(v, queries, query) for k, v in template.items()}
    if template == "{queries}":
        return queries
    if template == "{query}":
        return query
    return template


def _parse_date(value) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=timezone.utc)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:  # Twitter style: "Fri Oct 02 07:14:31 +0000 2026"
            return datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
        except ValueError:
            return None
    return None


def _run_actor(actor: str, payload: dict, token: str, max_wait: int = 480) -> list[dict]:
    """Start the actor, wait up to `max_wait` s, and return its dataset — even if it is
    still running (slow scrapers like Reddit's), in which case it is aborted to stop billing."""
    api = "https://api.apify.com/v2"
    headers = {"Authorization": f"Bearer {token}"}  # not in the URL, so it can't leak into error logs
    resp = net.client().post(
        f"{api}/acts/{actor.replace('/', '~')}/runs", params={"waitForFinish": 60}, headers=headers, json=payload, timeout=90
    )
    resp.raise_for_status()
    run = resp.json()["data"]
    waited = 60
    while run["status"] in ("READY", "RUNNING") and waited < max_wait:
        resp = net.client().get(f"{api}/actor-runs/{run['id']}", params={"waitForFinish": 60}, headers=headers, timeout=90)
        resp.raise_for_status()
        run = resp.json()["data"]
        waited += 60
    if run["status"] in ("READY", "RUNNING"):
        log.info("apify: %s still running after %ds — using partial results", actor, max_wait)
        net.client().post(f"{api}/actor-runs/{run['id']}/abort", headers=headers, timeout=30)
    elif run["status"] != "SUCCEEDED":
        log.warning("apify: %s ended with %s — using whatever it collected", actor, run["status"])
    items = net.client().get(
        f"{api}/datasets/{run['defaultDatasetId']}/items", params={"clean": "true"}, headers=headers, timeout=90
    )
    items.raise_for_status()
    data = items.json()
    return data if isinstance(data, list) else []


def collect(conf: dict, ctx) -> list[Item]:
    token = env("APIFY_API_TOKEN")
    if not token:
        log.warning("apify: no APIFY_API_TOKEN — skipping LinkedIn/X/Reddit (add the key to enable them)")
        return []
    items: list[Item] = []
    for spec in conf.get("actors") or [{"preset": "linkedin"}]:
        if "preset" in spec:
            preset = PRESETS[spec["preset"]]
            actor, fields, label = preset["actor"], preset["fields"], preset["label"]
            payloads = [preset["input"](conf, ctx)]
        else:
            actor, fields = spec["actor"], spec["fields"]
            label = spec.get("label", actor.split("/")[-1])
            tmpl = spec.get("input", {})
            per_query = "{query}" in str(tmpl)
            payloads = [_fill(tmpl, ctx.queries, q) for q in ctx.queries] if per_query else [_fill(tmpl, ctx.queries, None)]
        for payload in payloads:
            try:
                rows = _run_actor(actor, payload, token, conf.get("max_wait_seconds", 480))
            except Exception as e:
                log.warning("apify: %s failed: %s", actor, e)
                continue
            for r in rows:
                url = _pick(r, fields["url"])
                if not url:
                    continue
                author = _pick(r, fields.get("author", ""))
                info = _pick(r, fields.get("author_info", ""))
                items.append(
                    Item(
                        source=f"apify:{label}",
                        native_id=str(url).split("?")[0],
                        url=str(url),
                        title=str(_pick(r, fields.get("title", ""))),
                        text=str(_pick(r, fields.get("text", ""))),
                        author=f"{author} — {info}" if info else str(author),
                        created_at=_parse_date(_pick(r, fields.get("date", ""))),
                    )
                )
    return items
