"""Hacker News via the free Algolia API (no key)."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from leadradar import net
from leadradar.models import Item

API = "https://hn.algolia.com/api/v1/search_by_date"


def _clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def collect(conf: dict, ctx) -> list[Item]:
    items: list[Item] = []
    since_ts = int(ctx.since.timestamp())
    for q in ctx.queries:
        data = net.get(
            API,
            params={
                "query": q,
                "tags": "(story,comment)",
                "numericFilters": f"created_at_i>{since_ts}",
                "hitsPerPage": 30,
            },
        ).json()
        for h in data.get("hits", []):
            oid = h["objectID"]
            items.append(
                Item(
                    source="hackernews",
                    native_id=oid,
                    url=f"https://news.ycombinator.com/item?id={oid}",
                    title=h.get("title") or h.get("story_title") or "",
                    text=_clean(h.get("comment_text") or h.get("story_text") or ""),
                    author=h.get("author", ""),
                    created_at=datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc),
                )
            )
    return items
