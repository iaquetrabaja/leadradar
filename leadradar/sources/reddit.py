"""Reddit.

Two modes:
- OAuth (recommended, set REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET): app-only
  token, official API, generous limits.
- No credentials: public RSS search feeds. Reddit rate-limits these hard, so we
  go slowly and fall back to Scrapling's browser fingerprint when installed.
  For extra coverage add "reddit.com" to `sources.web.sites`.
"""

from __future__ import annotations

import html
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import httpx

from leadradar import net
from leadradar.config import env
from leadradar.models import Item

log = logging.getLogger("leadradar")


def _time_window(since: datetime) -> str:
    hours = (datetime.now(timezone.utc) - since).total_seconds() / 3600
    return "day" if hours <= 24 else "week" if hours <= 168 else "month"


def _targets(conf: dict) -> list[str]:
    """All subreddits in one multireddit path (r/a+b+c) plus optional site-wide search."""
    subs = [s.strip().removeprefix("r/") for s in conf.get("subreddits") or [] if s.strip()]
    targets = ["r/" + "+".join(subs)] if subs else []
    if conf.get("global_search", True) or not targets:
        targets.append("")
    return targets


def _query_groups(queries: list[str], size: int = 6) -> list[str]:
    """Reddit search supports OR: fold queries into a few requests instead of dozens."""
    return [" OR ".join(f'"{q}"' for q in queries[i : i + size]) for i in range(0, len(queries), size)]


def _oauth_token() -> str | None:
    cid, secret = env("REDDIT_CLIENT_ID"), env("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    resp = net.client().post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(cid, secret),
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _collect_oauth(token: str, conf: dict, ctx) -> list[Item]:
    items = []
    t = _time_window(ctx.since)
    headers = {"Authorization": f"bearer {token}"}
    for target in _targets(conf):
        for q in _query_groups(ctx.queries):
            base = f"https://oauth.reddit.com/{target + '/' if target else ''}search"
            params = {"q": q, "sort": "new", "t": t, "limit": 50, "restrict_sr": bool(target)}
            data = net.get(base, params=params, headers=headers).json()
            for child in data.get("data", {}).get("children", []):
                d = child["data"]
                created = datetime.fromtimestamp(d["created_utc"], tz=timezone.utc)
                items.append(
                    Item(
                        source="reddit",
                        native_id=d["name"],
                        url="https://www.reddit.com" + d["permalink"],
                        title=d.get("title", ""),
                        text=d.get("selftext", ""),
                        author=d.get("author", ""),
                        created_at=created,
                        extra={"subreddit": d.get("subreddit")},
                    )
                )
            time.sleep(1)
    return items


def _fetch_feed(url: str) -> str | None:
    try:
        return net.get(url, retries=1).text
    except httpx.HTTPStatusError as e:
        if net.has_scrapling():
            status, body = net.fetch_text(url)
            if status == 200 and "<feed" in body[:500]:
                return body
        log.warning("reddit: %s on %s (add REDDIT_CLIENT_ID/SECRET for reliable access)", e.response.status_code, url)
        return None


def _collect_rss(conf: dict, ctx) -> list[Item]:
    items = []
    t = _time_window(ctx.since)
    failures = 0
    for target in _targets(conf):
        for q in _query_groups(ctx.queries):
            if failures >= 2:
                log.warning("reddit: rate-limited, skipping the rest of this run")
                return items
            prefix = f"https://www.reddit.com/{target + '/' if target else ''}search.rss"
            url = f"{prefix}?q={quote_plus(q)}&sort=new&t={t}" + ("&restrict_sr=1" if target else "")
            body = _fetch_feed(url)
            time.sleep(4)  # be polite: public feeds are heavily rate-limited
            if not body:
                failures += 1
                continue
            failures = 0
            for e in feedparser.parse(body).entries:
                created = None
                if getattr(e, "updated_parsed", None):
                    created = datetime(*e.updated_parsed[:6], tzinfo=timezone.utc)
                text = html.unescape(re.sub(r"<[^>]+>", " ", e.get("summary", "")))
                items.append(
                    Item(
                        source="reddit",
                        native_id=e.get("id") or e.link,
                        url=e.link,
                        title=e.get("title", ""),
                        text=re.sub(r"\s+", " ", text).strip(),
                        author=e.get("author", ""),
                        created_at=created,
                    )
                )
    return items


def collect(conf: dict, ctx) -> list[Item]:
    token = _oauth_token()
    return _collect_oauth(token, conf, ctx) if token else _collect_rss(conf, ctx)
