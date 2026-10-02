"""collect -> dedupe -> filter -> score -> store -> notify -> report"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from leadradar import notify, report
from leadradar.db import Store, canonical_url
from leadradar.models import Item
from leadradar.sources import SOURCES, Context

log = logging.getLogger("leadradar")


def collect(cfg: dict, only: list[str] | None = None) -> list[Item]:
    since = datetime.now(timezone.utc) - timedelta(hours=cfg["max_age_hours"])
    enabled = {
        name: conf
        for name, conf in cfg["sources"].items()
        # --sources runs the named sources even if disabled in config (handy for testing).
        if name in SOURCES and (name in only if only else conf.get("enabled"))
    }
    log.info("sources: %s", ", ".join(enabled) or "none")

    def run(name: str) -> list[Item]:
        # A source may override the global queries (keyword APIs like short terms).
        ctx = Context(queries=enabled[name].get("queries") or cfg["queries"], since=since)
        try:
            found = SOURCES[name](enabled[name], ctx)
            log.info("  %-11s %4d items", name, len(found))
            return found
        except SystemExit:
            raise
        except Exception as e:
            log.error("  %-11s failed: %s", name, e)
            return []

    # Sources are independent and I/O bound: run them side by side.
    with ThreadPoolExecutor(max_workers=len(enabled) or 1) as pool:
        results = list(pool.map(run, enabled))
    items = [it for batch in results for it in batch]

    # Dedupe within this run and drop stale / empty / excluded items.
    exclude = [w.lower() for w in cfg.get("exclude", [])]
    unique: dict[str, Item] = {}
    urls: set[str] = set()
    for it in items:
        if it.created_at and it.created_at < since:
            continue
        blob = f"{it.title} {it.text}".lower()
        if len(blob.strip()) < 25 or any(w in blob for w in exclude):
            continue
        # The same post can arrive via two sources (e.g. LinkedIn via web search and Apify).
        url = canonical_url(it.url)
        if it.id in unique or url in urls:
            continue
        unique[it.id] = it
        urls.add(url)
    return list(unique.values())





def fair_share(items: list[Item], cap: int) -> list[Item]:
    """Round-robin across sources (newest first within each) so one noisy
    source can't take the whole per-run budget."""
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    by_source: dict[str, list[Item]] = {}
    for it in sorted(items, key=lambda it: it.created_at or oldest, reverse=True):
        by_source.setdefault(it.source, []).append(it)
    queues = list(by_source.values())
    picked: list[Item] = []
    while len(picked) < cap and queues:
        for q in list(queues):
            if len(picked) >= cap:
                break
            picked.append(q.pop(0))
            if not q:
                queues.remove(q)
    return picked


def run(cfg: dict, *, notify_enabled: bool = True, use_llm: bool = True, only: list[str] | None = None) -> dict:
    store = Store(cfg["storage"]["db_path"])
    items = collect(cfg, only)
    fresh = store.unseen(items)
    cap = cfg["scoring"]["max_items_per_run"]
    if len(fresh) > cap:
        log.info("capping %d new items to max_items_per_run=%d (rest next run)", len(fresh), cap)
        fresh = fair_share(fresh, cap)
    log.info("%d candidates, %d new", len(items), len(fresh))
    stats = {"collected": len(items), "scored": len(fresh), "leads": 0}

    if not use_llm:
        for it in fresh:
            print(f"- [{it.source}] {it.title or it.text[:80]!r}\n  {it.url}")
        return stats
    if not fresh:
        if notify_enabled:
            notify.send_all([], cfg["notify"], stats, cfg["profile"]["report_language"])
        report.write(store, cfg["storage"]["output_dir"], cfg["notify"]["min_score"])
        return stats

    from leadradar.scorer import Scorer

    scorer = Scorer(cfg["profile"], cfg["scoring"])
    leads = scorer.score(fresh)
    # Only mark items seen once scored, so a crash mid-run retries them next time.
    scored_ids = {l.item.id for l in leads}
    store.mark_seen([it for it in fresh if it.id in scored_ids])
    # Items Claude declined/couldn't parse are retried once, then dropped (network errors don't count).
    store.mark_seen(store.bump_tries(scorer.rejected, limit=2))
    store.save_leads(leads)

    hot = sorted((l for l in leads if l.score >= cfg["notify"]["min_score"]), key=lambda l: -l.score)
    hot = hot[: cfg["notify"]["max_leads"]]
    stats["leads"] = len(hot)
    log.info("%d leads >= %d", len(hot), cfg["notify"]["min_score"])

    if notify_enabled:
        delivered = notify.send_all(hot, cfg["notify"], stats, cfg["profile"]["report_language"])
        store.mark_notified(delivered)
    else:
        for l in hot:
            print(f"\n{l.score}/100 [{l.item.source}] {l.summary}\n  {l.item.url}\n  why: {l.why}\n  draft: {l.draft}")

    out = report.write(store, cfg["storage"]["output_dir"], cfg["notify"]["min_score"])
    log.info("report: %s", out)
    return stats
