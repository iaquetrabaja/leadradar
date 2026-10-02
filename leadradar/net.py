"""Shared HTTP helpers: polite client, retries, and an optional Scrapling fallback."""

from __future__ import annotations

import logging
import time

import httpx

log = logging.getLogger("leadradar")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 leadradar/0.1"
)

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            headers={"User-Agent": UA}, timeout=25, follow_redirects=True
        )
    return _client


def get(url: str, *, retries: int = 2, **kwargs) -> httpx.Response:
    """GET with backoff on 429/5xx. Raises httpx.HTTPStatusError on final failure."""
    delay = 3.0
    for attempt in range(retries + 1):
        resp = client().get(url, **kwargs)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < retries:
                wait = float(resp.headers.get("retry-after", delay))
                log.debug("HTTP %s on %s, retrying in %.0fs", resp.status_code, url, wait)
                time.sleep(min(wait, 30))
                delay *= 2
                continue
        resp.raise_for_status()
        return resp
    raise RuntimeError("unreachable")


def has_scrapling() -> bool:
    try:
        import scrapling  # noqa: F401
    except ImportError:
        return False
    return True


def quiet_scrapling() -> None:
    # Scrapling configures an INFO console logger on import; keep our output clean.
    logging.getLogger("scrapling").setLevel(logging.WARNING)


def fetch_text(url: str, *, stealth: bool = False) -> tuple[int, str]:
    """Fetch a page body, using Scrapling when installed (browser-grade TLS
    fingerprint; `stealth=True` launches a real stealth browser).
    Falls back to httpx. Returns (status, body)."""
    if has_scrapling():
        from scrapling.fetchers import Fetcher, StealthyFetcher

        quiet_scrapling()
        page = (
            StealthyFetcher.fetch(url, headless=True)
            if stealth
            else Fetcher.get(url, impersonate="chrome")
        )
        body = page.body
        if isinstance(body, bytes):
            try:
                body = body.decode("utf-8")
            except UnicodeDecodeError:
                body = body.decode("cp1252", "replace")  # some sites still serve Latin-1
        return page.status, body
    resp = client().get(url)
    return resp.status_code, resp.text
