"""Discord and Slack incoming webhooks (DISCORD_WEBHOOK_URL / SLACK_WEBHOOK_URL)."""

from __future__ import annotations

import time

from leadradar import net
from leadradar.config import env
from leadradar.models import Lead


def _lines(lead: Lead, t: dict) -> str:
    it = lead.item
    title = it.title or it.text[:90]
    body = (
        f"**{lead.score}/100** · {t['intent'].get(lead.intent, lead.intent)} · _{it.source}_\n"
        f"**{title}**\n📝 {lead.summary}\n💡 {lead.why}\n🔗 {it.url}"
    )
    if lead.draft:
        body += f"\n> {lead.draft.replace(chr(10), chr(10) + '> ')}"
    return body


def _slack_escape(s: str) -> str:
    # Slack treats <...> as links/mentions (<!channel>); escape so post text can't ping or spoof.
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _post(url: str, payload: dict) -> None:
    resp = net.client().post(url, json=payload)
    resp.raise_for_status()


def send_discord(leads: list[Lead], stats: dict, t: dict, conf: dict) -> list[str]:
    url = env("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("set DISCORD_WEBHOOK_URL")
    if not leads:
        return []
    no_pings = {"parse": []}  # post text may contain @everyone — never ping
    _post(url, {"content": t["header"].format(n=len(leads), scanned=stats["scored"]), "allowed_mentions": no_pings})
    for lead in leads:
        _post(url, {"content": _lines(lead, t)[:1990], "allowed_mentions": no_pings})
        time.sleep(0.5)
    return [l.item.id for l in leads]


def send_slack(leads: list[Lead], stats: dict, t: dict, conf: dict) -> list[str]:
    url = env("SLACK_WEBHOOK_URL")
    if not url:
        raise RuntimeError("set SLACK_WEBHOOK_URL")
    if not leads:
        return []
    text = t["header"].format(n=len(leads), scanned=stats["scored"]) + "\n\n"
    text += "\n\n".join(_slack_escape(_lines(l, t)).replace("**", "*") for l in leads)
    _post(url, {"text": text[:39000]})
    return [l.item.id for l in leads]
