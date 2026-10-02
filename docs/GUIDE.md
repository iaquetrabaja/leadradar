# Step-by-step guide — LeadRadar without installing anything

> 🇪🇸 [Versión en español](GUIA.md) · ⬅ [Back to README](../README.md)

In about 15 minutes you'll have a radar that **every morning finds people asking for what you sell** (on Workana, Freelancer, LinkedIn, X, Reddit, Hacker News and Bluesky), drops the ones who are just selling or chatting, and **sends each opportunity to Telegram** with a reply draft.

Everything happens in the browser: no Python, no server. It runs free on GitHub Actions.

**Contents**
1. [What you need](#1-what-you-need)
2. [Copy the template](#2-copy-the-template)
3. [Get an AI key (Claude, ChatGPT or Gemini)](#3-get-an-ai-key)
4. [Create your Telegram bot](#4-create-your-telegram-bot)
5. [(Optional) Apify for LinkedIn, X and Reddit](#5-optional-apify-for-linkedin-x-and-reddit)
6. [Configure what you sell and what to look for](#6-configure-what-you-sell-and-what-to-look-for)
7. [Store the keys as secrets](#7-store-the-keys-as-secrets)
8. [Run it and see the result](#8-run-it-and-see-the-result)
9. [Most useful options](#9-most-useful-options)
10. [Switching AI provider](#10-switching-ai-provider)
11. [What it costs](#11-what-it-costs)
12. [Troubleshooting](#12-troubleshooting)
13. [Running it on your computer (advanced)](#13-running-it-on-your-computer-advanced)

---

## 1. What you need

| | Required? | Cost |
|---|---|---|
| GitHub account | Yes | Free |
| **One** AI key: Claude, ChatGPT **or** Gemini | Yes | Cents per run |
| Telegram on your phone | Yes (or Discord/Slack) | Free |
| Apify account | No — adds LinkedIn, X and Reddit | Pay per result, free monthly credit |

With just the required items it already searches **Workana, Freelancer.com, Hacker News and Bluesky**.

## 2. Copy the template

1. Sign in to GitHub and open **https://github.com/iaquetrabaja/leadradar**.
2. Click the green **Use this template → Create a new repository** button.
3. Name it (e.g. `my-leadradar`) and choose **Private** — your config describes your business and the reports contain the leads.
4. Click **Create repository**.

![Repository page: once signed in, the "Use this template" button appears](img/01-use-this-template.png)

> Don't see the button? Make sure you're signed in — GitHub hides it from logged-out visitors.

## 3. Get an AI key

Pick **one**. All three work well for this; the difference is mostly price and where you already have an account.

| AI | Where to get the key | Secret name | Default model |
|---|---|---|---|
| **Claude** (recommended) | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) → *Create Key* | `ANTHROPIC_API_KEY` | `claude-haiku-4-5` |
| **ChatGPT** (OpenAI) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) → *Create new secret key* | `OPENAI_API_KEY` | `gpt-5-mini` |
| **Gemini** (Google) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → *Create API key* | `GEMINI_API_KEY` | `gemini-3.8-flash` |

Copy the key somewhere safe for a moment — it's shown only once. In all three cases the API account needs credit or billing enabled (separate from a ChatGPT Plus / Claude Pro subscription). Gemini usually offers a rate-limited free tier.

## 4. Create your Telegram bot

1. In Telegram, find **@BotFather** and send `/newbot`.
2. Pick a name and a username ending in `bot` (e.g. `MyLeadsBot`).
3. BotFather gives you a **token** like `8123456789:AAH...` — that's your `TELEGRAM_BOT_TOKEN`.
4. Open your new bot (the `t.me/...` link) and press **Start**.
5. To get your `TELEGRAM_CHAT_ID`, open this address in your browser, replacing `YOUR_TOKEN`:

   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```

   You'll see `"chat":{"id":123456789,...` — that number is your `TELEGRAM_CHAT_ID`. (Empty? Send the bot another message and reload.)

> Want it in a team group? Add the bot to the group, write something there and repeat step 5: group ids start with `-`.

> 🔒 Treat the token like a password. If you leak it, send `/revoke` to BotFather to get a new one.

## 5. (Optional) Apify for LinkedIn, X and Reddit

These networks don't allow searching without an account, and using your own account risks a ban. Apify does it with "actors" that don't need your login.

1. Create an account at [apify.com](https://apify.com).
2. Go to **Settings → API & Integrations** and copy the **Personal API token** — that's your `APIFY_API_TOKEN`.

Without it, LeadRadar simply skips LinkedIn, X and Reddit.

## 6. Configure what you sell and what to look for

In your new repository:

1. Open **`config.example.yaml`** and click the copy icon (⧉ *Copy raw file*).
2. Back on the repo home → **Add file → Create new file**, name it **`config.yaml`** and paste.
3. Change at least these parts (the rest can stay as is):

```yaml
profile:
  offer: |
    I build WordPress and Shopify websites for small businesses: new sites,
    redesigns, speed and basic SEO.
  ideal_client: |
    Local businesses, shops and freelancers without a technical team.
  not_a_fit: |
    Agencies looking to outsource cheaply, full-time job offers.
  report_language: en

queries:                      # phrases YOUR client would write when asking for help
  - "looking for someone to build my website"
  - "need a website redesign"
  - "recommend a web designer"
  - "looking for a shopify developer"

scoring:
  provider: anthropic         # anthropic | openai | gemini  (the one from step 3)
```

4. Also review the short per-source `queries` (`workana`, `freelancer`, `bluesky`, `hackernews`, `apify`): use keywords from your trade (`wordpress`, `shopify`, `web design`…).
5. Click **Commit changes**.

> 💡 Don't want to write the phrases? Section [13](#13-running-it-on-your-computer-advanced) has a command that **generates the whole `config.yaml` with AI** from one sentence ("SEO freelancer for Shopify stores"). Ready-made examples: [`examples/seo.yaml`](../examples/seo.yaml), [`examples/email-marketing.yaml`](../examples/email-marketing.yaml).

## 7. Store the keys as secrets

Keys **never** go in `config.yaml` — they're stored encrypted by GitHub.

1. In your repo: **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** and add one per key (exact name on the left, value on the right):

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` **or** `OPENAI_API_KEY` **or** `GEMINI_API_KEY` | your key from step 3 |
| `TELEGRAM_BOT_TOKEN` | the BotFather token |
| `TELEGRAM_CHAT_ID` | the number from step 4.5 |
| `APIFY_API_TOKEN` | (optional) your Apify token |

## 8. Run it and see the result

1. Open the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. On the left pick **LeadRadar** → **Run workflow** → **Run workflow**.
3. Within 3–5 minutes leads start arriving in Telegram:

![Real leads arriving on a phone (names blurred)](img/06-telegram-real.png)

Each card has the score (0–100), what they need, why it fits you, the budget if any, an expandable **reply draft** and an **Open post** button.

Open the run to see its log:

![Run log: sources, new posts, cost and leads](img/04-terminal.png)

And under **Artifacts** you can download **leads-report** with a `leads.html` page to review, filter and copy drafts:

![leads.html report (sample data)](img/05-report.png)

From then on it **runs by itself** on the schedule in `.github/workflows/leadradar.yml` (by default 06:00, 12:00 and 18:00 UTC). It never sends the same lead twice.

## 9. Most useful options

All in `config.yaml` (the example explains each line):

| Option | What it does | Default |
|---|---|---|
| `max_age_hours` | Only posts from the last N hours | `72` |
| `notify.min_score` | Minimum score to notify. 60 = a buyer asking for help with something you offer; 80+ = only the hottest | `60` |
| `notify.max_leads` | Max notifications per run | `15` |
| `scoring.max_items_per_run` | Max posts the AI reads per run (caps spend) | `100` |
| `scoring.provider` / `model` | Which AI (see section 10) | `anthropic` / cheapest |
| `apify.max_per_query` | Results per search on LinkedIn/X/Reddit (caps Apify spend) | `10` |
| `apify.x_lang` | Restrict X to one language, e.g. `en` | all |
| `exclude` | Drop any post containing these words | — |
| `<source>.enabled` | Turn each source on/off | see example |
| `notify.telegram.notify_empty` | Also message when nothing was found | `false` |

**Change the schedule**: edit the `cron` line in `.github/workflows/leadradar.yml`. It's UTC; e.g. `"0 6 * * *"` = every day at 06:00 UTC. Once a day is usually enough and costs a third.

## 10. Switching AI provider

Just change the `scoring` block in `config.yaml` and store the matching secret:

```yaml
# Claude (default)                   → secret ANTHROPIC_API_KEY
scoring:
  provider: anthropic
  model: ""                  # empty = claude-haiku-4-5. Sharper drafts: claude-sonnet-5-5

# ChatGPT                            → secret OPENAI_API_KEY
scoring:
  provider: openai
  model: ""                  # empty = gpt-5-mini. Cheaper: gpt-5-nano

# Gemini                             → secret GEMINI_API_KEY
scoring:
  provider: gemini
  model: ""                  # empty = gemini-3.8-flash

# Any OpenAI-compatible API (OpenRouter, Groq, Together, local Ollama…)
#                                    → secret LLM_API_KEY
scoring:
  provider: openai_compatible
  base_url: https://openrouter.ai/api/v1
  model: meta-llama/llama-4-maverick
```

For models LeadRadar doesn't know, the log shows tokens but no cost; add `price: [input, output]` ($ per million tokens) to see it.

## 11. What it costs

Measured with the defaults (100 posts read per run):

| Item | Approx. cost |
|---|---|
| AI with Claude Haiku 4.5 | ~$0.10 per run |
| Apify (LinkedIn + X + Reddit, 10 results per search) | ~$0.10–0.30 per run |
| GitHub Actions, Telegram | Free |

Once a day: roughly **$3–10/month** in total. To spend less, lower `scoring.max_items_per_run` or `apify.max_per_query`, or run it once a day.

## 12. Troubleshooting

**Nothing arrives in Telegram.**
Check the run log (Actions → the run → *Run LeadRadar*). `0 leads` means nothing passed the filter: lower `notify.min_score` to 50 or review your `queries`. `telegram failed` means checking `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` and that you pressed **Start** in the bot.

**`needs ANTHROPIC_API_KEY` (or OPENAI / GEMINI).**
The `provider` in `config.yaml` doesn't match the secret you stored — they must be the same AI.

**The workflow says "No config.yaml in this repo yet".**
Step 6 is missing: the file must be named exactly `config.yaml`, at the repo root.

**`apify: no APIFY_API_TOKEN — skipping`.**
Normal if you don't use Apify. If you do, check the secret name.

**Leads that don't fit.**
Make `offer` and especially `not_a_fit` more specific, add words to `exclude`, or raise `notify.min_score` to 70.

**The schedule stopped running.**
In **public** repos GitHub pauses scheduled workflows after 60 days without activity (another reason to keep yours private). Re-enable it in Actions or push any commit.

## 13. Running it on your computer (advanced)

Requires Python 3.10+.

```bash
git clone https://github.com/YOUR_USER/my-leadradar && cd my-leadradar
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[stealth]"

leadradar init                    # creates .env (put your keys there) and config.yaml
leadradar init --force --describe "WordPress web design for local businesses in the UK"
leadradar telegram-setup          # prints your TELEGRAM_CHAT_ID
leadradar test-notify             # sends a test card

leadradar run --no-llm            # free: see what each source finds
leadradar run --dry-run           # score but print instead of notifying
leadradar run                     # full run
```

`init --describe` uses whichever AI key is in `.env` and writes a complete `config.yaml` for your trade: buyer phrases per source, subreddits, exclusions and tone. Review it and commit it to your repo.
