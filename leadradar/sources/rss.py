"""Any RSS/Atom feed: job boards, forums, Google Alerts, newsletters…
Items are not keyword-filtered here — Claude decides relevance."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import feedparser

from leadradar import net
from leadradar.models import Item


def collect(conf: dict, ctx) -> list[Item]:
    items: list[Item] = []
    for feed in conf.get("feeds") or []:
        url = feed["url"] if isinstance(feed, dict) else feed
        name = feed.get("name", "rss") if isinstance(feed, dict) else "rss"
        parsed = feedparser.parse(net.get(url).text)
        for e in parsed.entries:
            stamp = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
            created = datetime(*stamp[:6], tzinfo=timezone.utc) if stamp else None
            if created and created < ctx.since:
                continue
            text = html.unescape(re.sub(r"<[^>]+>", " ", e.get("summary", "")))
            items.append(
                Item(
                    source=f"rss:{name}",
                    native_id=e.get("id") or e.get("link", ""),
                    url=e.get("link", ""),
                    title=e.get("title", ""),
                    text=re.sub(r"\s+", " ", text).strip(),
                    author=e.get("author", ""),
                    created_at=created,
                )
            )
    return items
