"""Workana (big in Spain + LatAm). The listing blocks plain HTTP clients, so this
uses Scrapling's browser fingerprint — install with `pip install "leadradar[stealth]"`.
Projects are embedded as JSON in the page, no fragile selectors needed."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from leadradar import net
from leadradar.models import Item

URL = "https://www.workana.com/jobs?language={lang}&query={q}&publication={window}"

UNITS = {"min": 1 / 60, "hora": 1, "d": 24, "semana": 24 * 7, "mes": 24 * 30, "año": 24 * 365}


def parse_relative(posted: str, now: datetime) -> datetime | None:
    """'Hace 5 horas' / 'Ayer' / 'Hace 2 semanas' (also 'X hours ago') -> datetime."""
    s = (posted or "").lower().replace("publicado:", "").strip()
    if not s:
        return None
    if s.startswith(("hoy", "today")) or "minut" in s and not re.search(r"\d", s):
        return now
    if s.startswith(("ayer", "yesterday")):
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\s*(min|hora|hour|d|semana|week|mes|month|año|year)", s)
    if not m:
        return None
    unit = {"hour": "hora", "week": "semana", "month": "mes", "year": "año"}.get(m.group(2), m.group(2))
    return now - timedelta(hours=int(m.group(1)) * UNITS[unit])


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def collect(conf: dict, ctx) -> list[Item]:
    if not net.has_scrapling():
        raise SystemExit('sources.workana needs Scrapling: pip install "leadradar[stealth]"')
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    # Ask Workana itself for recent projects only (1 day or 1 week window).
    window = "1d" if (now - ctx.since) <= timedelta(hours=24) else "1w"
    for q in ctx.queries:
        status, body = net.fetch_text(URL.format(lang=conf.get("language", "es"), q=quote_plus(q), window=window))
        m = re.search(r"results-initials='([^']*)'", body)
        if status != 200 or not m:
            raise RuntimeError(f"unexpected Workana response ({status}) for {q!r}")
        for r in json.loads(html.unescape(m.group(1))).get("results", []):
            posted = r.get("postedDate") or ""
            items.append(
                Item(
                    source="workana",
                    native_id=r["slug"],
                    url=f"https://www.workana.com/job/{r['slug']}",
                    title=_strip(r.get("title", "")),
                    text=_strip(r.get("description", "")),
                    author=r.get("authorName", ""),
                    # Workana only gives relative dates ("Ayer", "Hace 2 horas"); unknown -> drop as stale.
                    created_at=parse_relative(posted, now) or (now - timedelta(days=3650)),
                    extra={"budget": r.get("budget", ""), "posted": posted, "bids": r.get("totalBids", "")},
                )
            )
    return items
