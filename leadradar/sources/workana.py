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

URL = "https://www.workana.com/jobs?language={lang}&query={q}"


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def collect(conf: dict, ctx) -> list[Item]:
    if not net.has_scrapling():
        raise SystemExit('sources.workana needs Scrapling: pip install "leadradar[stealth]"')
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for q in ctx.queries:
        status, body = net.fetch_text(URL.format(lang=conf.get("language", "es"), q=quote_plus(q)))
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
                    # Workana only gives relative dates ("Ayer", "Hace 2 horas"); dedupe handles repeats.
                    created_at=now - timedelta(minutes=1),
                    extra={"budget": r.get("budget", ""), "posted": posted, "bids": r.get("totalBids", "")},
                )
            )
    return items
