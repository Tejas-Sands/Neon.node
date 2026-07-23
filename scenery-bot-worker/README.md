# scenery-bot — Telegram → GitHub Actions trigger

A tiny Cloudflare Worker (free plan) that lets you start an Artistic Scenery
render by messaging a Telegram bot:

```
/scenery                   → autonomous render (pipeline picks the place)
/scenery Faroe Islands     → render that specific place
```

It receives the bot's webhook, verifies Telegram's secret token, checks the
message is from YOUR chat, and fires `workflow_dispatch` on
`generate_scenery.yml` via the GitHub API. The finished video is delivered
back to the same chat by the pipeline (via `TELEGRAM_BOT_TOKEN_SCENERY`).

## One-time setup (~10 minutes)

### 1. Create the bot

In Telegram, talk to **@BotFather** → `/newbot` → pick a name/username.
Copy the **bot token** (`123456:ABC-...`).

Optional polish: `/setcommands` → `scenery - Render an artistic scenery video`.

### 2. Get your chat id

Send `/start` to your new bot, then run (webhook not set yet, so getUpdates works):

```bash
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates" | python3 -m json.tool | grep -A2 '"chat"'
```

The `"id"` under `"chat"` is your chat id. It is stored as a Worker secret
(step 4), not in `wrangler.jsonc`, so it never lands in the repo.

### 3. Create a GitHub token for dispatching

GitHub → Settings → Developer settings → **Fine-grained personal access
tokens** → Generate new token:

- Repository access: **Only select repositories** → this repo
- Permissions: **Actions → Read and write** (nothing else)

### 4. Deploy the Worker

```bash
cd scenery-bot-worker
npx wrangler login                 # first time only
npx wrangler deploy                # note the printed URL: https://scenery-bot.<your-subdomain>.workers.dev

npx wrangler secret put BOT_TOKEN        # paste the BotFather token
npx wrangler secret put WEBHOOK_SECRET   # paste output of: openssl rand -hex 32
npx wrangler secret put GITHUB_TOKEN     # paste the fine-grained PAT
npx wrangler secret put ALLOWED_CHAT_ID  # paste the chat id from step 2
```

### 5. Point the bot's webhook at the Worker

```bash
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -d "url=https://scenery-bot.<your-subdomain>.workers.dev" \
  -d "secret_token=<WEBHOOK_SECRET>"
```

### 6. GitHub repo secrets (delivery side)

In the repo → Settings → Secrets and variables → Actions, add:

- `TELEGRAM_BOT_TOKEN_SCENERY` — the same bot token from step 1
- `TELEGRAM_CHAT_ID_SCENERY` — the chat id from step 2

(Until these exist, the pipeline falls back to the main news bot/chat.)

### 7. Test

Message the bot: `/scenery` → it replies "🎬 Scenery render started…" and the
video arrives in ~10 minutes. `/scenery Grand Prismatic Spring` films that
exact place.

## Troubleshooting

- Bot replies "GitHub said 401/404" → GITHUB_TOKEN is wrong/expired, or
  `GITHUB_REPO` in wrangler.jsonc doesn't match, or the workflow file isn't on
  the `main` branch yet.
- No reply at all → check `getWebhookInfo`:
  `curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"` — a pending
  error there usually means the Worker URL or WEBHOOK_SECRET mismatch.
- Live Worker logs: `npx wrangler tail scenery-bot`.
