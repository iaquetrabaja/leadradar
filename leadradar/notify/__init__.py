from __future__ import annotations

import logging

from leadradar.models import Lead

log = logging.getLogger("leadradar")

TEXTS = {
    "en": {
        "header": "📡 LeadRadar: {n} new leads ({scanned} posts scanned)",
        "none": "📡 LeadRadar: no new leads this run ({scanned} posts scanned).",
        "draft": "Draft reply",
        "open": "Open post",
        "intent": {
            "seeking_provider": "🎯 Seeking a provider",
            "seeking_tool": "🧰 Seeking a tool",
            "asking_how": "❓ Asking how",
            "frustrated": "😤 Frustrated",
            "job_post": "💼 Job post",
            "not_relevant": "—",
        },
    },
    "es": {
        "header": "📡 LeadRadar: {n} leads nuevos ({scanned} publicaciones revisadas)",
        "none": "📡 LeadRadar: sin leads nuevos en esta pasada ({scanned} publicaciones revisadas).",
        "draft": "Borrador de respuesta",
        "open": "Abrir publicación",
        "intent": {
            "seeking_provider": "🎯 Busca proveedor",
            "seeking_tool": "🧰 Busca herramienta",
            "asking_how": "❓ Pregunta cómo",
            "frustrated": "😤 Frustrado",
            "job_post": "💼 Oferta de trabajo",
            "not_relevant": "—",
        },
    },
}


def texts(lang: str) -> dict:
    return TEXTS.get(lang, TEXTS["en"])


def send_all(leads: list[Lead], conf: dict, stats: dict, lang: str) -> list[str]:
    """Send leads to every enabled channel. Returns ids delivered to at least one."""
    from leadradar.notify import telegram, webhooks

    t = texts(lang)
    channels = {
        "telegram": telegram.send,
        "discord": webhooks.send_discord,
        "slack": webhooks.send_slack,
    }
    delivered: set[str] = set()
    for name, fn in channels.items():
        channel = conf.get(name) or {}
        if not channel.get("enabled"):
            continue
        try:
            delivered |= set(fn(leads, stats, t, channel))
        except Exception as e:
            log.error("notify: %s failed: %s", name, e)
    return list(delivered)
