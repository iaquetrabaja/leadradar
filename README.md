# 📡 LeadRadar

**Find people who are asking for what you sell — on LinkedIn, Reddit, X, Hacker News, Bluesky, Workana, Freelancer.com and any site you point it at. Claude reads every post, scores real buying intent, writes a helpful first reply, and pings you on Telegram.**

> 🇪🇸 [Leer en español](README.es.md)

```
 sources ──► dedupe ──► Claude scores intent + fit ──► Telegram / Discord / Slack
 (10 kinds)  (SQLite)    and drafts a reply              + leads.html / leads.csv
```

- **Intent, not mentions.** Social-listening tools tell you someone said "n8n". LeadRadar tells you *"a dental clinic owner wants WhatsApp appointment reminders and is asking for a freelancer — here's a reply"*.
- **Drafts only, never auto-sends.** You stay in control of what goes out (and stay on the right side of platform rules and anti-spam law).
- **No account bans.** LinkedIn and X are reached through search engines or no-cookie Apify actors — never your own logged-in session.
- **Runs free on GitHub Actions.** Copy the template, add secrets, done. No server, no Docker, no database to host.
- **Any language.** Queries, scoring and drafts work in Spanish, English or whatever your clients speak.

## What it looks like

Each lead arrives in Telegram as a card:

```
85/100 · 🎯 Seeking a provider · workana
WhatsApp AI chatbot for prices, opening hours and shipping
📝 Shop wants a WhatsApp bot answering prices, hours and shipping, with a panel.
💡 Customer-support automation for a small e-commerce: core offer.
💰 USD 250 - 500
Draft reply ▸ (tap to expand)
[ Open post ]
```

…and every run also writes `output/leads.html`: a filterable page with one-click "copy draft".

## Sources

| Source | Key needed | Notes |
|---|---|---|
| `hackernews` | – | Algolia API. Posts + comments. |
| `bluesky` | – | Public search API, language filter. |
| `freelancer` | – | Freelancer.com open projects. |
| `workana` | – | Spain + LatAm projects. Needs the `stealth` extra (Scrapling). |
| `reddit` | optional | Public RSS (heavily rate-limited). Uses `REDDIT_CLIENT_ID`/`SECRET` if you already have them (Reddit closed self-service API keys in late 2025). |
| `web` | optional | `site:` searches on LinkedIn, X, Quora, Indie Hackers, forums… via `ddgs` (free, thin results), **Serper** (Google, 2,500 free queries — recommended), Brave or Exa (semantic). |
| `apify` | `APIFY_API_TOKEN` | Reliable **LinkedIn post search without cookies** (~$2 / 1,000 posts) and any other Apify actor (X, Instagram, Facebook groups…) via a field mapping. |
| `agentreach` | your session | Reddit + X through [Agent-Reach](https://github.com/Panniantong/Agent-Reach)'s CLIs (`rdt-cli`, `twitter-cli`), which reuse **your logged-in cookies**. Best coverage, but against those platforms' automation terms — secondary account, low volume, local only. Off by default. |
| `rss` | – | Any RSS/Atom feed: job boards, Google Alerts, forums. |
| `scrape` | – | Any listing page with CSS selectors, powered by [Scrapling](https://github.com/D4Vinci/Scrapling) (incl. stealth browser for Cloudflare-protected sites). |

Adding a source is one file with a `collect(conf, ctx) -> list[Item]` function — see `leadradar/sources/`.

## Works for any trade

Nothing is hard-wired to one niche. Describe your business in one sentence and Claude writes the whole config — buyer phrases for each source, subreddits, noise filters, reply tone:

```bash
leadradar init --describe "SEO freelancer for local businesses and Shopify stores in Spain and LatAm"
leadradar init --describe "Email marketing with Klaviyo for e-commerce brands, remote, English-speaking"
```

Ready-made examples (generated exactly like that): [`examples/seo.yaml`](examples/seo.yaml), [`examples/email-marketing.yaml`](examples/email-marketing.yaml). In a test run, the SEO config surfaced a Madrid accounting firm, a sports doctor and a Shopify cacao brand all hiring for SEO — out of 339 posts.

## Quick start (local)

Requires Python 3.10+.

```bash
git clone https://github.com/Daaviid3792/leadradar && cd leadradar
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[stealth]"

# put your ANTHROPIC_API_KEY in .env (created by init), then:
leadradar init --describe "what you sell and to whom"   # or plain `leadradar init` to edit by hand

leadradar run --no-llm       # free: just see what each source finds (--sources web,workana to pick)
leadradar run --dry-run      # score with Claude, print leads instead of notifying
leadradar run                # the real thing
```

### Telegram in 2 minutes

1. In Telegram, talk to **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Open your new bot and send it any message.
3. `leadradar telegram-setup` prints your `TELEGRAM_CHAT_ID`. Paste it into `.env`.
4. `leadradar test-notify` — you should get a test card.

(Want it in a group with your team? Add the bot to the group, send a message there, and run `telegram-setup` again.)

## Run it on GitHub Actions (free, no server)

1. Click **Use this template → Create a new repository** and make it **private**. (Your config describes your business, and run artifacts contain the leads — in a public repo anyone can download them. A fork of a public repo can't be private, and GitHub disables scheduled workflows on forks until you enable them.)
2. Copy `config.example.yaml` to `config.yaml`, edit it, and commit it.
3. **Settings → Secrets and variables → Actions**: add `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` and any optional keys.
4. **Actions** tab → enable workflows → run **LeadRadar** once by hand.

It then runs 3×/day (edit the cron in `.github/workflows/leadradar.yml`). The seen-items database is kept in the Actions cache so you never get the same lead twice, and each run uploads `leads.html` as an artifact.

> Reddit usually blocks GitHub's datacenter IPs on the keyless RSS route. In CI, cover Reddit with `reddit.com` in `web.sites` (best with Serper or Exa). The `agentreach` source is meant for local runs only.

## Configuration

Everything lives in `config.yaml` — the [example](config.example.yaml) is commented line by line. The parts that matter most:

- **`profile.offer` / `ideal_client` / `not_a_fit`** — Claude scores every post against these. Be specific.
- **`queries`** — phrases your buyers actually write (*"busco a alguien que automatice"*, *"looking for a zapier expert"*). Keyword APIs (Bluesky, HN, Workana…) work better with their own short `queries` per source; Claude filters intent afterwards.
- **`notify.min_score`** — 70 is a good start; 85+ = explicitly hiring.
- **`scoring.model`** — defaults to `claude-opus-5-5` at `effort: low`: measured at **~$0.16 per 45 posts** (≈ $0.50 for a full 150-post run). `claude-haiku-4-5` is ~4× cheaper. `max_items_per_run` caps spend per run, and every run logs tokens and estimated cost.

`config.local.yaml` (git-ignored) takes precedence over `config.yaml` if present — handy for local experiments.

## How scoring works

Posts are sent to Claude in batches with a cached system prompt containing your offer. Claude returns structured JSON per post (validated with Pydantic): `score` (0–100), `intent` (seeking provider / tool / asking how / frustrated / job post), a one-line summary and reason in your language, and — for leads — a reply draft **in the post's language** that leads with something useful instead of a pitch. Post content is treated as untrusted data (instructions inside posts are ignored).

## Using it responsibly

- **Don't spam.** LeadRadar never sends anything to prospects; replying is up to you. Answer publicly where people asked, or reach out personally and briefly.
- **Cold email/DM rules vary by country** (e.g. GDPR + ePrivacy in the EU, LSSI in Spain, CAN-SPAM in the US). Know yours.
- **Respect sites' terms.** Use official APIs and keys where available, keep request volumes low (defaults are polite), and don't scrape behind logins.

## Related projects

LeadRadar borrows ideas from [LeadEcho](https://github.com/rohansx/leadecho), [OpenOutreach](https://github.com/eracle/OpenOutreach) and [upwork-job-alerts](https://github.com/janglewood/upwork-job-alerts). For agent-driven deep research on platforms that need a login, see [Agent-Reach](https://github.com/Panniantong/Agent-Reach).

## License

MIT
