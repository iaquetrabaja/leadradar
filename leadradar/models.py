from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Item:
    """A raw post/comment/job found by a source, before scoring."""

    source: str  # e.g. "reddit", "web:linkedin.com"
    native_id: str  # stable id inside the source (url is fine)
    url: str
    title: str = ""
    text: str = ""
    author: str = ""
    created_at: datetime | None = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        # Sources sometimes return naive timestamps; treat them as UTC so comparisons never crash.
        if self.created_at is not None and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

    @property
    def id(self) -> str:
        return f"{self.source.split(':')[0]}:{self.native_id}"

    def as_prompt(self, max_chars: int = 1500) -> str:
        body = (self.text or "").strip()
        if len(body) > max_chars:
            body = body[:max_chars] + "…"
        when = self.created_at.isoformat() if self.created_at else "unknown"
        return (
            f"source: {self.source}\nurl: {self.url}\nauthor: {self.author or 'unknown'}\n"
            f"date: {when}\ntitle: {self.title}\ntext: {body}"
        )


@dataclass
class Lead:
    item: Item
    score: int
    intent: str
    lang: str
    summary: str
    why: str
    draft: str
