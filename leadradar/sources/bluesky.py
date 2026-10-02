"""Bluesky public search (AppView, no login needed)."""

from __future__ import annotations

from datetime import datetime

from leadradar import net
from leadradar.models import Item

API = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def collect(conf: dict, ctx) -> list[Item]:
    items: list[Item] = []
    langs = conf.get("langs") or [None]
    since = ctx.since.strftime("%Y-%m-%dT%H:%M:%SZ")
    for q in ctx.queries:
        for lang in langs:
            params = {"q": q, "sort": "latest", "since": since, "limit": 50}
            if lang:
                params["lang"] = lang
            data = net.get(API, params=params).json()
            for p in data.get("posts", []):
                handle = p["author"]["handle"]
                rkey = p["uri"].rsplit("/", 1)[-1]
                items.append(
                    Item(
                        source="bluesky",
                        native_id=p["uri"],
                        url=f"https://bsky.app/profile/{handle}/post/{rkey}",
                        text=p.get("record", {}).get("text", ""),
                        author=handle,
                        created_at=_parse_dt(p.get("record", {}).get("createdAt")),
                    )
                )
    return items
