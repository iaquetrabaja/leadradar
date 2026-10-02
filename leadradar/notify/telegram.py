"""Telegram: one header message + one card per lead with the draft and an
"Open post" button. Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
(`leadradar telegram-setup` finds your chat id)."""

from __future__ import annotations

import html
import logging
import time

from leadradar import net
from leadradar.config import env
from leadradar.models import Lead

API = "https://api.telegram.org/bot{token}/{method}"
log = logging.getLogger("leadradar")


def _creds() -> tuple[str, str]:
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not (token and chat):
        raise RuntimeError("set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (run `leadradar telegram-setup`)")
    return token, chat


def call(method: str, **payload) -> dict:
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("set TELEGRAM_BOT_TOKEN (create a bot with @BotFather)")
    resp = net.client().post(API.format(token=token, method=method), json=payload)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method}: {data.get('description')}")
    return data["result"]


def send_text(text: str, **extra) -> None:
    _, chat = _creds()
    call("sendMessage", chat_id=chat, text=text, parse_mode="HTML", link_preview_options={"is_disabled": True}, **extra)


def _cut(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def card(lead: Lead, t: dict) -> str:
    scale = 1.0
    msg = _card(lead, t, scale)
    while len(msg) > 4000 and scale > 0.05:  # heavy escaping (&, <) can inflate the text
        scale /= 2
        msg = _card(lead, t, scale)
    return msg


def _card(lead: Lead, t: dict, scale: float) -> str:
    # Truncate raw fields first, then escape: cutting escaped HTML can break tags/entities.
    e = html.escape

    def cut(s: str, n: int) -> str:
        return _cut(s, max(20, int(n * scale)))

    it = lead.item
    parts = [
        f"<b>{lead.score}/100</b> · {e(t['intent'].get(lead.intent, lead.intent))} · <i>{e(it.source)}</i>",
        f"<b>{e(cut(it.title or it.text, 200))}</b>",
        f"📝 {e(cut(lead.summary, 400))}",
        f"💡 {e(cut(lead.why, 400))}",
    ]
    if it.author:
        parts.append(f"👤 {e(cut(it.author, 150))}")
    if it.extra.get("budget"):
        parts.append(f"💰 {e(cut(str(it.extra['budget']), 80))}")
    if lead.draft:
        parts.append(f"\n<b>{e(t['draft'])}:</b>\n<blockquote expandable>{e(cut(lead.draft, 1800))}</blockquote>")
    return "\n".join(parts)


def send(leads: list[Lead], stats: dict, t: dict, conf: dict) -> list[str]:
    if not leads:
        if conf.get("notify_empty", False):
            send_text(t["none"].format(scanned=stats["scored"]))
        return []
    send_text(t["header"].format(n=len(leads), scanned=stats["scored"]))
    sent = []
    for lead in leads:
        try:
            send_text(
                card(lead, t),
                reply_markup={"inline_keyboard": [[{"text": t["open"], "url": lead.item.url}]]},
            )
        except Exception as e:  # keep going: one bad card shouldn't drop the rest
            log.warning("telegram: could not send %s: %s", lead.item.url, e)
            continue
        sent.append(lead.item.id)
        time.sleep(0.4)  # stay under Telegram's per-chat rate limit
    return sent
