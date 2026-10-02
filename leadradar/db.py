"""SQLite store: what we've already seen (dedupe) and every scored lead."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from leadradar.models import Lead


def canonical_url(url: str) -> str:
    """Normalise a URL so the same post found via different sources/links matches."""
    url = url.split("#")[0].split("?")[0].rstrip("/").lower()
    return url.replace("://www.", "://").replace("://old.", "://").replace("twitter.com/", "x.com/")

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
  id TEXT PRIMARY KEY,
  source TEXT,
  first_seen TEXT,
  url TEXT
);
CREATE TABLE IF NOT EXISTS tries (
  id TEXT PRIMARY KEY,
  n INTEGER
);
CREATE TABLE IF NOT EXISTS leads (
  id TEXT PRIMARY KEY,
  source TEXT, url TEXT, title TEXT, text TEXT, author TEXT, created_at TEXT,
  score INTEGER, intent TEXT, lang TEXT, summary TEXT, why TEXT, draft TEXT,
  found_at TEXT, notified INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS leads_score ON leads(score);
"""


class Store:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(seen)")}
        if "url" not in cols:  # databases created by v0.1
            self.conn.execute("ALTER TABLE seen ADD COLUMN url TEXT")
        self.conn.execute("CREATE INDEX IF NOT EXISTS seen_url ON seen(url)")

    def _existing(self, column: str, values: list[str]) -> set[str]:
        found: set[str] = set()
        for i in range(0, len(values), 500):
            chunk = values[i : i + 500]
            q = f"SELECT {column} FROM seen WHERE {column} IN ({','.join('?' * len(chunk))})"
            found |= {r[0] for r in self.conn.execute(q, chunk)}
        return found

    def unseen(self, items) -> list:
        """Items never seen before — by id, or by URL (the same post found via another source)."""
        ids = self._existing("id", [it.id for it in items])
        urls = self._existing("url", [canonical_url(it.url) for it in items])
        return [it for it in items if it.id not in ids and canonical_url(it.url) not in urls]

    def mark_seen(self, items) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.executemany(
            "INSERT OR IGNORE INTO seen(id, source, first_seen, url) VALUES (?,?,?,?)",
            [(it.id, it.source, now, canonical_url(it.url)) for it in items],
        )
        self.conn.commit()

    def bump_tries(self, items, limit: int) -> list:
        """Count failed scoring attempts; return the items that hit `limit` (give up on them)."""
        self.conn.executemany(
            "INSERT INTO tries(id, n) VALUES (?, 1) ON CONFLICT(id) DO UPDATE SET n = n + 1",
            [(it.id,) for it in items],
        )
        self.conn.commit()
        if not items:
            return []
        q = f"SELECT id FROM tries WHERE n >= ? AND id IN ({','.join('?' * len(items))})"
        done = {r[0] for r in self.conn.execute(q, [limit, *[it.id for it in items]])}
        return [it for it in items if it.id in done]

    def save_leads(self, leads: list[Lead]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.executemany(
            """INSERT OR REPLACE INTO leads
               (id, source, url, title, text, author, created_at, score, intent, lang,
                summary, why, draft, found_at, notified)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            [
                (
                    l.item.id, l.item.source, l.item.url, l.item.title, l.item.text,
                    l.item.author, l.item.created_at.isoformat() if l.item.created_at else None,
                    l.score, l.intent, l.lang, l.summary, l.why, l.draft, now,
                )
                for l in leads
            ],
        )
        self.conn.commit()

    def mark_notified(self, ids: list[str]) -> None:
        self.conn.executemany("UPDATE leads SET notified=1 WHERE id=?", [(i,) for i in ids])
        self.conn.commit()

    def recent_leads(self, min_score: int = 0, limit: int = 500) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM leads WHERE score >= ? ORDER BY found_at DESC, score DESC LIMIT ?",
                (min_score, limit),
            )
        )
