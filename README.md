# 📡 LeadRadar

**Find people who are asking for what you sell — on LinkedIn, X, Reddit, Workana, Freelancer.com, Hacker News, Bluesky and any site you point it at. Claude reads every post, scores real buying intent, writes a helpful first reply, and pings you on Telegram.**

> 🇪🇸 [Leer en español](README.es.md)

```
 sources ──► recent only ──► dedupe ──► Claude scores intent + fit ──► Telegram / Discord / Slack
 (10 kinds)  (≤ 72 h)        (SQLite)    and drafts a reply              + leads.html / leads.csv
```

- **Intent, not mentions.** Social-listening tools tell you someone said "n8n". LeadRadar tells you *"a hostel wants a WhatsApp booking agent and is hiring a freelancer — here's a reply"*. People offering their own services are filtered out.
- **Fresh leads only.** Every source is filtered by its real publication date (default: last 72 h) — no month-old job posts.
- **Drafts only, never auto-sends.** You stay in control of what goes out.
- **No account bans.** LinkedIn, X and Reddit are reached through no-cookie Apify actors — never your own logged-in session.
- **Any trade.** `leadradar init --describe "SEO freelancer for Shopify stores"` writes the config for you.
- **Cheap and serverless.** ~$0.09 of Claude per 100 posts, runs free on GitHub Actions.

## API keys — as few as possible

| Key | Needed? | What for | Where to get it | Cost |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Required** | Claude scores posts and writes drafts | [console.anthropic.com](https://console.anthropic.com) → API keys | ~$0.09 per 100 posts (Haiku) |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | **Required** (or Discord/Slack) | Where leads arrive | @BotFather in Telegram, then `leadradar telegram-setup` | Free |
| `APIFY_API_TOKEN` | Recommended | **LinkedIn + X + Reddit** in one key, no cookies | [apify.com](https://apify.com) → Settings → API & Integrations | Pay per result, free monthly credit; ~$0.10–0.30 per run at defaults |
| `SERPER_API_KEY` | Optional | `web` source: Quora, Indie Hackers, forums via Google | [serper.dev](https://serper.dev) | 2,500 free searches |
| `DISCORD_WEBHOOK_URL` / `SLACK_WEBHOOK_URL` | Optional | Other notification channels | Channel settings → Integrations → Webhooks | Free |

With only the two required keys you already get **Workana, Freelancer.com, Hacker News and Bluesky** (no key needed). Add Apify for LinkedIn, X and Reddit. Without the Apify key, that source is skipped automatically.

## What it looks like

Each lead arrives in Telegram as a card:

```
92/100 · 🎯 Seeking a provider · workana
Hostel needs an n8n agent for WhatsApp, Gmail and Instagram bookings
📝 Small hostel wants bookings answered automatically across WhatsApp, Gmail and Instagram.
💡 WhatsApp + email automation for a small business: core offer.
💰 USD 250 - 500
Draft reply ▸ (tap to expand)
[ Open post ]
```

…and every run also writes `output/leads.html`: a filterable page with one-click "copy draft".

## Sources

| Source | Key | Notes |
|---|---|---|
| `workana` | – | Spain + LatAm projects (uses [Scrapling](https://github.com/D4Vinci/Scrapling) to get past the bot wall). Filtered by "posted N hours/days ago". |
| `freelancer` | – | Freelancer.com open projects. |
| `hackernews` | – | Algolia API. Posts + comments. |
| `bluesky` | – | Public search API, language filter. |
| `apify` | `APIFY_API_TOKEN` | Presets: **`linkedin`** (post search, no cookies), **`x`** (tweet search), **`reddit`** (post search). Or any other Apify actor via a field mapping (Instagram, Facebook groups…). |
| `web` | `SERPER_API_KEY` | `site:` searches on Quora, Indie Hackers, forums… (also `ddgs` free/no key, Brave, Exa). Dates of LinkedIn/X results are decoded from their post ids. |
| `rss` | – | Any RSS/Atom feed: job boards, Google Alerts, forums. |
| `scrape` | – | Any listing page with CSS selectors (incl. stealth browser for Cloudflare). |
| `reddit` | – | Keyless Reddit RSS. Heavily rate-limited and blocked from CI — prefer the Apify `reddit` preset. |
| `agentreach` | your session | Reddit + X through [Agent-Reach](https://github.com/Panniantong/Agent-Reach)'s CLIs (`rdt-cli`, `twitter-cli`), which reuse **your logged-in cookies**. Against those platforms' automation terms — secondary account, low volume, local only. Off by default. |

Adding a source is one file with a `collect(conf, ctx) -> list[Item]` function — see `leadradar/sources/`.

## Works for any trade

Nothing is hard-wired to one niche. Describe your business in one sentence and Claude writes the whole config — buyer phrases for each source, subreddits, noise filters, reply tone:

```bash
leadradar init --describe "SEO freelancer for local businesses and Shopify stores in Spain and LatAm"
leadradar init --describe "Email marketing with Klaviyo for e-commerce brands, remote, English-speaking"
```

Ready-made examples (generated exactly like that): [`examples/seo.yaml`](examples/seo.yaml), [`examples/email-marketing.yaml`](examples/email-marketing.yaml). In a test run, the SEO config surfaced a Madrid accounting firm, a sports doctor and a Shopify cacao brand all hiring for SEO.

## Quick start (local)

Requires Python 3.10+.

```bash
git clone https://github.com/iaquetrabaja/leadradar && cd leadradar
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[stealth]"

leadradar init                                       # creates config.yaml + .env
# put your keys in .env, then tailor the config to your business:
leadradar init --force --describe "what you sell and to whom"

leadradar run --no-llm       # free: just see what each source finds (--sources workana,apify to pick)
leadradar run --dry-run      # score with Claude, print leads instead of notifying
leadradar run                # the real thing
```

### Telegram in 2 minutes

1. In Telegram, talk to **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Open your new bot and press **Start** (or send it any message).
3. `leadradar telegram-setup` prints your `TELEGRAM_CHAT_ID`. Paste it into `.env`.
4. `leadradar test-notify` — you should get a test card.

(Want it in a group with your team? Add the bot to the group, send a message there, and run `telegram-setup` again.)

## Run it on GitHub Actions (free, no server)

1. Click **Use this template → Create a new repository** and make it **private**. (Your config describes your business, and run artifacts contain the leads — in a public repo anyone can download them.)
2. Copy `config.example.yaml` to `config.yaml` (or generate it with `init --describe`), edit it, and commit it.
3. **Settings → Secrets and variables → Actions → New repository secret**: add `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `APIFY_API_TOKEN` if you use it.
4. **Actions** tab → **LeadRadar** → **Run workflow** to test it once.

It then runs on the schedule in `.github/workflows/leadradar.yml` (3×/day by default — once a day is plenty for most people and a third of the cost). The seen-items database is kept in the Actions cache so you never get the same lead twice, and each run uploads `leads.html` as an artifact.

## Configuration

Everything lives in `config.yaml` — the [example](config.example.yaml) is commented line by line. The parts that matter most:

- **`profile.offer` / `ideal_client` / `not_a_fit`** — Claude scores every post against these. Be specific.
- **`queries`** — phrases your buyers actually write (*"busco a alguien que automatice"*, *"looking for a zapier expert"*). Keyword APIs (Bluesky, HN, Workana…) work better with their own short `queries` per source; Claude filters intent afterwards.
- **`max_age_hours`** — 72 by default. Use 24 for a daily run if you only want today's posts.
- **`notify.min_score`** — 60 by default. Hard rules cap vendors at 30 and on-topic chatter at 55, so anything ≥ 60 is a buyer explicitly asking for help; raise it to 75–85 for only the hottest.
- **`scoring.model`** — `claude-haiku-4-5` by default: measured at **~$0.09 per 100 posts**. `claude-sonnet-5-5` or `claude-opus-5-5` write sharper drafts for ~3–4× the price. `max_items_per_run` caps spend, and every run logs tokens and estimated cost.

`config.local.yaml` (git-ignored) takes precedence over `config.yaml` if present — handy for local experiments.

## How scoring works

Posts are sent to Claude in batches with your offer in the system prompt. Claude returns structured JSON per post (validated with Pydantic): whether the author is a **buyer or a vendor** and whether they **explicitly ask for help** (vendors are capped at 30 and on-topic chatter at 55, so neither is ever notified), `score` (0–100), `intent` (seeking provider / tool / asking how / frustrated / job post), a one-line summary and reason in your language, and — for leads — a reply draft **in the post's language** that leads with something useful instead of a pitch. Post content is treated as untrusted data (instructions inside posts are ignored).

## Using it responsibly

- **Don't spam.** LeadRadar never sends anything to prospects; replying is up to you. Answer publicly where people asked, or reach out personally and briefly.
- **Cold email/DM rules vary by country** (e.g. GDPR + ePrivacy in the EU, LSSI in Spain, CAN-SPAM in the US). Know yours.
- **Respect sites' terms.** Use official APIs and keys where available, keep request volumes low (defaults are polite), and don't scrape behind logins.

## Related projects

LeadRadar borrows ideas from [LeadEcho](https://github.com/rohansx/leadecho), [OpenOutreach](https://github.com/eracle/OpenOutreach) and [upwork-job-alerts](https://github.com/janglewood/upwork-job-alerts), and uses [Scrapling](https://github.com/D4Vinci/Scrapling) for hard-to-fetch sites.

## License

MIT
