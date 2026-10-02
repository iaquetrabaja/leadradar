"""Reddit + X through the CLIs that Agent-Reach installs (rdt-cli, twitter-cli).

⚠️  These ride YOUR logged-in browser session (cookies). That gets far more
results than anonymous access, but it is against Reddit's/X's terms for
automation and can get the account limited. Use a secondary account, keep
volumes low, and run it locally — don't put session cookies in CI secrets.

Setup (https://github.com/Panniantong/Agent-Reach):
    pipx install "git+https://github.com/public-clis/rdt-cli.git"   # then: rdt login
    pipx install twitter-cli                                        # then: see its cookie guide
or `agent-reach install --channels=reddit,twitter`.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone

from leadradar.models import Item

log = logging.getLogger("leadradar")


def _run(cmd: list[str]) -> object | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("agentreach: %s failed: %s", cmd[0], e)
        return None
    try:
        payload = json.loads(proc.stdout or "null")
    except json.JSONDecodeError:
        log.warning("agentreach: %s returned non-JSON output: %s", cmd[0], (proc.stderr or proc.stdout)[:200])
        return None
    # Both CLIs wrap results in {"ok": bool, "data": ..., "error": {...}}.
    if isinstance(payload, dict) and "ok" in payload:
        if not payload["ok"]:
            err = payload.get("error") or {}
            log.warning("agentreach: %s: %s (logged in?)", cmd[0], err.get("message") or err)
            return None
        return payload.get("data")
    return payload


def _reddit_posts(data) -> list[dict]:
    """rdt returns the raw Reddit listing ({"data": {"children": [{"data": post}]}})."""
    if isinstance(data, dict):
        data = data.get("data", data).get("children", [])
    return [c.get("data", c) for c in data or [] if isinstance(c, dict)]


def _time_flag(since: datetime) -> str:
    hours = (datetime.now(timezone.utc) - since).total_seconds() / 3600
    return "day" if hours <= 24 else "week" if hours <= 168 else "month"


def _tweet_time(s: str) -> datetime | None:
    for fmt in ("%a %b %d %H:%M:%S %z %Y", None):
        try:
            return datetime.strptime(s, fmt) if fmt else datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
    return None


def collect(conf: dict, ctx) -> list[Item]:
    items: list[Item] = []
    per_query = conf.get("max_per_query", 25)

    if conf.get("reddit", True):
        if not shutil.which("rdt"):
            log.warning("agentreach: `rdt` not found — install rdt-cli or set reddit: false")
        else:
            for q in ctx.queries:
                data = _run(["rdt", "search", q, "-s", "new", "-t", _time_flag(ctx.since), "-n", str(per_query), "--json"])
                for p in _reddit_posts(data):
                    if not p.get("permalink"):
                        continue
                    items.append(
                        Item(
                            source="reddit",
                            native_id=p.get("name") or p["permalink"],
                            url="https://www.reddit.com" + p["permalink"],
                            title=p.get("title", ""),
                            text=p.get("selftext", ""),
                            author=p.get("author", ""),
                            created_at=datetime.fromtimestamp(p["created_utc"], tz=timezone.utc) if p.get("created_utc") else None,
                            extra={"subreddit": p.get("subreddit")},
                        )
                    )

    if conf.get("x", True):
        if not shutil.which("twitter"):
            log.warning("agentreach: `twitter` not found — install twitter-cli or set x: false")
        else:
            since = ctx.since.strftime("%Y-%m-%d")
            for q in ctx.queries:
                cmd = ["twitter", "search", q, "-t", "latest", "--since", since, "-n", str(per_query), "--exclude", "retweets", "--json"]
                if conf.get("x_lang"):
                    cmd += ["--lang", conf["x_lang"]]
                data = _run(cmd)
                tweets = data.get("tweets", []) if isinstance(data, dict) else data or []
                for t in tweets:
                    handle = (t.get("author") or {}).get("screenName", "")
                    if not (t.get("id") and handle):
                        continue
                    items.append(
                        Item(
                            source="x",
                            native_id=str(t["id"]),
                            url=f"https://x.com/{handle}/status/{t['id']}",
                            text=t.get("text", ""),
                            author="@" + handle,
                            created_at=_tweet_time(t.get("createdAt", "")),
                        )
                    )
    return items
