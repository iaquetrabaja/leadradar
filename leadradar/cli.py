from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from leadradar import __version__

REPO = "https://github.com/iaquetrabaja/leadradar"


def _example(name: str) -> Path | None:
    """Find an example file in the current dir or next to the package (editable install)."""
    for base in (Path.cwd(), Path(__file__).resolve().parent.parent):
        if (base / name).exists():
            return base / name
    return None


def cmd_init(args) -> None:
    target = Path(args.output)
    if target.exists() and not args.force:
        sys.exit(f"{target} already exists — edit it, or pass --force to overwrite.")
    example_path = _example("config.example.yaml")
    if example_path is None:
        sys.exit(f"config.example.yaml not found. Run this inside a clone of {REPO}.")
    env_example = _example(".env.example")
    if env_example and not Path(".env").exists():
        shutil.copy(env_example, ".env")
        print("Created .env — put your API keys there.")

    if args.describe:
        import yaml

        from leadradar.config import env, load_env
        from leadradar.generator import dump, generate

        load_env()
        if not env("ANTHROPIC_API_KEY"):
            sys.exit("Add your ANTHROPIC_API_KEY to .env first (console.anthropic.com), then re-run this command.")
        print("Asking Claude to tailor the config to your business…")
        example = yaml.safe_load(example_path.read_text(encoding="utf-8"))
        target.write_text(dump(generate(args.describe, example), args.describe), encoding="utf-8")
    else:
        shutil.copy(example_path, target)
    print(f"Created {target}. Review it, then run: leadradar run --no-llm")


def cmd_run(args) -> None:
    from leadradar.config import load_config
    from leadradar.pipeline import run

    cfg = load_config(args.config)
    only = args.sources.split(",") if args.sources else None
    stats = run(cfg, notify_enabled=not args.dry_run, use_llm=not args.no_llm, only=only)
    print(f"\ncollected={stats['collected']} new={stats['scored']} leads={stats['leads']}")


def cmd_telegram_setup(args) -> None:
    from leadradar.config import load_env
    from leadradar.notify import telegram

    load_env()
    updates = telegram.call("getUpdates")
    chats = {}
    for u in updates:
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat")
        if chat:
            chats[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name")
    if not chats:
        print("No messages yet. Open your bot in Telegram, send it any message, then run this again.")
        return
    for cid, name in chats.items():
        print(f"TELEGRAM_CHAT_ID={cid}    # {name}")
    print("\nPut that line in your .env (or as a GitHub secret), then: leadradar test-notify")


def cmd_test_notify(args) -> None:
    from leadradar.config import load_config
    from leadradar.models import Item, Lead
    from leadradar.notify import send_all

    cfg = load_config(args.config)
    fake = Lead(
        item=Item(
            source="web:linkedin.com",
            native_id="test",
            url="https://github.com/",
            title="Test lead — LeadRadar is working",
            author="LeadRadar",
        ),
        score=99,
        intent="seeking_provider",
        lang="en",
        summary="This is a test notification.",
        why="If you can read this, notifications are configured correctly.",
        draft="Hi! This is where your personalised reply draft will appear.",
    )
    sent = send_all([fake], cfg["notify"], {"scored": 1}, cfg["profile"]["report_language"])
    print("sent ✓" if sent else "nothing sent — is a channel enabled and configured?")


def main() -> None:
    p = argparse.ArgumentParser(prog="leadradar", description="Find people asking for what you sell.")
    p.add_argument("--version", action="version", version=__version__)
    # config.local.yaml (git-ignored) wins over config.yaml (committed, used by GitHub Actions).
    default_cfg = "config.local.yaml" if Path("config.local.yaml").exists() else "config.yaml"
    p.add_argument("-c", "--config", default=default_cfg)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="create config.yaml (+ .env) — tailored by Claude with --describe")
    i.add_argument("--describe", metavar="TEXT", help='what you sell and to whom, e.g. "SEO freelancer for local businesses in Spain"')
    i.add_argument("-o", "--output", default="config.yaml", help="file to write (default: config.yaml)")
    i.add_argument("--force", action="store_true", help="overwrite an existing config")
    i.set_defaults(fn=cmd_init)
    r = sub.add_parser("run", help="search, score and notify")
    r.add_argument("--dry-run", action="store_true", help="score but print instead of notifying")
    r.add_argument("--no-llm", action="store_true", help="only collect and print candidates (free, tests sources)")
    r.add_argument("--sources", help="comma list to run only some sources, e.g. web,hackernews")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("telegram-setup", help="find your TELEGRAM_CHAT_ID").set_defaults(fn=cmd_telegram_setup)
    sub.add_parser("test-notify", help="send a fake lead to your channels").set_defaults(fn=cmd_test_notify)

    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    for noisy in ("httpx", "httpx2", "httpcore", "scrapling", "primp", "ddgs"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    args.fn(args)
