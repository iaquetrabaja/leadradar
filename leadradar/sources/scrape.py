"""Scrape any listing page with CSS selectors (forums, job boards, marketplaces).
Requires the `stealth` extra (Scrapling). Example config:

    scrape:
      enabled: true
      pages:
        - name: workana
          url: https://www.workana.com/jobs?language=es&query=automatizacion
          item: ".project-item"        # one element per post
          title: "h2"                  # relative to item
          link: "h2 a::attr(href)"
          text: ".project-details"
          stealth: false               # true = real stealth browser (Cloudflare etc.)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from leadradar import net
from leadradar.models import Item

log = logging.getLogger("leadradar")


def _text(el, selector: str | None) -> str:
    if not selector:
        return ""
    if "::" in selector:
        return (el.css(selector).get() or "").strip()
    found = el.css(selector)
    return found[0].get_all_text(strip=True) if found else ""


def collect(conf: dict, ctx) -> list[Item]:
    if not net.has_scrapling():
        raise SystemExit('sources.scrape needs Scrapling: pip install "leadradar[stealth]" && scrapling install')
    from scrapling.fetchers import Fetcher, StealthyFetcher

    net.quiet_scrapling()

    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for page_conf in conf.get("pages") or []:
        url = page_conf["url"]
        try:
            page = (
                StealthyFetcher.fetch(url, headless=True)
                if page_conf.get("stealth")
                else Fetcher.get(url, impersonate="chrome")
            )
        except Exception as e:
            log.warning("scrape: %s failed: %s", url, e)
            continue
        for el in page.css(page_conf["item"]):
            link = _text(el, page_conf.get("link")) or url
            link = urljoin(url, link)
            title = _text(el, page_conf.get("title"))
            items.append(
                Item(
                    source=f"scrape:{page_conf.get('name', 'page')}",
                    native_id=link if link != url else f"{url}#{title}",
                    url=link,
                    title=title,
                    text=_text(el, page_conf.get("text")),
                    created_at=now - timedelta(minutes=1),  # listing pages: assume fresh, dedupe handles repeats
                )
            )
    return items
