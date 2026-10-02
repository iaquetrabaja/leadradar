"""Apify actors (APIFY_API_TOKEN): the reliable way to search LinkedIn posts, X,
Instagram, Facebook groups… without logging in with your own account.
Pay-per-result on your Apify account (LinkedIn preset ≈ $2 per 1,000 posts).

Config:
    apify:
      enabled: true
      max_per_query: 25
      actors:
        - preset: linkedin            # built-in mapping
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

RUN = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def _linkedin_window(since: datetime) -> str:
    hours = (datetime.now(timezone.utc) - since).total_seconds() / 3600
    return "24h" if hours <= 24 else "week" if hours <= 168 else "month"


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
}


def _pick(obj, path: str):
    if not path:
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
            return None
    return None


def _run_actor(actor: str, payload: dict, token: str) -> list[dict]:
    resp = net.client().post(
        RUN.format(actor=actor.replace("/", "~")),
        params={"timeout": 240},
        headers={"Authorization": f"Bearer {token}"},  # not in the URL, so it can't leak into error logs
        json=payload,
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def collect(conf: dict, ctx) -> list[Item]:
    token = env("APIFY_API_TOKEN")
    if not token:
        raise SystemExit("sources.apify needs APIFY_API_TOKEN")
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
                rows = _run_actor(actor, payload, token)
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
