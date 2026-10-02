from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv

DEFAULTS: dict = {
    "profile": {
        "name": "",
        "offer": "",
        "ideal_client": "",
        "not_a_fit": "",
        "tone": "friendly, concise, helpful first — never pushy",
        "signature": "",
        "report_language": "en",  # language for summaries in your notifications
    },
    "queries": [],
    "exclude": [],
    "max_age_hours": 72,
    "sources": {
        "hackernews": {"enabled": True},
        "reddit": {"enabled": False, "subreddits": [], "global_search": True},
        "bluesky": {"enabled": True, "langs": []},
        "freelancer": {"enabled": False, "queries": []},
        "workana": {"enabled": False, "language": "es", "queries": []},
        "apify": {
            "enabled": False,
            "max_per_query": 10,
            "actors": [{"preset": "linkedin"}, {"preset": "x"}, {"preset": "reddit"}],
        },
        "agentreach": {"enabled": False, "reddit": True, "x": True, "x_lang": "", "max_per_query": 25},
        "web": {
            "enabled": False,
            "provider": "ddgs",  # ddgs (free, no key) | serper | brave | exa
            "sites": ["linkedin.com/posts", "x.com", "quora.com", "indiehackers.com"],
            "freshness": "week",  # day | week | month
            "results_per_query": 10,
            "max_requests": 40,
            "region": "es-es",
        },
        "rss": {"enabled": False, "feeds": []},
        "scrape": {"enabled": False, "pages": []},
    },
    "scoring": {
        "provider": "anthropic",  # anthropic | openai | gemini | openai_compatible
        "model": "",  # empty = the provider's cheap default (claude-haiku-4-5, gpt-5-mini, gemini-3.8-flash)
        "base_url": "",  # openai_compatible only
        "effort": "low",
        "batch_size": 15,
        "max_items_per_run": 150,
    },
    "notify": {
        "min_score": 60,
        "max_leads": 15,
        "telegram": {"enabled": True},
        "discord": {"enabled": False},
        "slack": {"enabled": False},
    },
    "storage": {"db_path": "data/leadradar.db", "output_dir": "output"},
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if v is None and isinstance(out.get(k), (dict, list)):
            continue  # e.g. "discord:" left empty in YAML keeps the defaults
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_env() -> None:
    # Look for .env from the current directory (not from where the package is installed).
    load_dotenv(find_dotenv(usecwd=True))


def load_config(path: str | Path) -> dict:
    load_env()
    path = Path(path)
    if not path.exists():
        raise SystemExit(
            f"Config not found: {path}\nRun `leadradar init` to create one from the example."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = _merge(DEFAULTS, data)
    if not cfg["queries"]:
        raise SystemExit("Config has no `queries`. Add the phrases your buyers would write.")
    if not cfg["profile"]["offer"].strip():
        raise SystemExit("Config `profile.offer` is empty. Describe what you sell — Claude scores against it.")
    return cfg


def env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None
