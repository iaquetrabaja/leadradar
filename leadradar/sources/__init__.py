"""Sources. Each module exposes `collect(conf, ctx) -> list[Item]`.

To add a source: create a module here with a `collect` function and register it
in SOURCES. `conf` is the source's block from config.yaml; `ctx` is a Context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from leadradar.sources import agentreach, apify, bluesky, freelancer, hackernews, reddit, rss, scrape, web, workana


@dataclass
class Context:
    queries: list[str]
    since: datetime  # only items newer than this


SOURCES = {
    "hackernews": hackernews.collect,
    "reddit": reddit.collect,
    "bluesky": bluesky.collect,
    "freelancer": freelancer.collect,
    "workana": workana.collect,
    "apify": apify.collect,
    "agentreach": agentreach.collect,
    "web": web.collect,
    "rss": rss.collect,
    "scrape": scrape.collect,
}
