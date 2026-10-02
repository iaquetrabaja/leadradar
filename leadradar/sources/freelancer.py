"""Freelancer.com public projects API (no key). Works best with short,
skill-style `queries` set on the source."""

from __future__ import annotations

from datetime import datetime, timezone

from leadradar import net
from leadradar.models import Item

API = "https://www.freelancer.com/api/projects/0.1/projects/active/"


def collect(conf: dict, ctx) -> list[Item]:
    items: list[Item] = []
    for q in ctx.queries:
        data = net.get(
            API,
            params={
                "query": q,
                "limit": 30,
                "compact": "true",
                "full_description": "true",
                "from_time": int(ctx.since.timestamp()),
                "sort_field": "submitdate",
            },
        ).json()
        for p in data.get("result", {}).get("projects", []):
            budget = p.get("budget") or {}
            cur = (p.get("currency") or {}).get("code", "")
            items.append(
                Item(
                    source="freelancer",
                    native_id=str(p["id"]),
                    url=f"https://www.freelancer.com/projects/{p.get('seo_url', p['id'])}",
                    title=p.get("title", ""),
                    text=p.get("description") or p.get("preview_description", ""),
                    created_at=datetime.fromtimestamp(p["submitdate"], tz=timezone.utc),
                    extra={"budget": f"{budget.get('minimum', '?')}-{budget.get('maximum', '?')} {cur}"},
                )
            )
    return items
