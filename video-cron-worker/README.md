# video-cron

Cloudflare Cron Trigger that dispatches `generate_video.yml` on time, replacing
GitHub's `schedule:` block.

## Why

GitHub's scheduled-workflow queue is best-effort. Measured on this repo
(2026-07-22 → 07-26), **every** scheduled run fired late:

| cron (UTC) | avg delay | actually fired | landed (IST) |
|---|---|---|---|
| 03:23 | +166 min | ~06:10 | ~11:40 |
| 06:47 | +141 min | ~09:10 | ~14:40 |
| 10:11 | +102 min | ~11:50 | ~17:20 |
| 13:36 | +99 min  | ~15:10 | ~20:40 |
| 16:02 | +73 min  | ~17:20 | ~22:50 |

The intended 08:53–21:32 IST spread became 11:40–22:50 IST with a 12–13.5 h
overnight hole, and delivered 3–6 posts/day instead of 5. Cloudflare Cron
Triggers fire within seconds, so the posting plan lives here now.

## How it works

One cron trigger, `*/10 * * * *` — **not** one per post: the Workers Free plan
allows only **5 cron triggers per account**, so a cron-per-post would consume
the entire account budget. Each tick:

1. Rebuild today's plan — `POSTS_PER_DAY` slots inside the IST window, with
   every gap ≥ `MIN_GAP_MIN` and the leftover time distributed across random
   buckets (see `planSlots`). Seeded on the IST date, so times move every day
   but are identical for every tick within a day.
2. Find the most recent slot that is due and no more than `GRACE_MIN` old.
3. Ask GitHub when the workflow last ran. If a run was created at or after that
   slot, it is already served — do nothing.
4. Otherwise `POST .../dispatches`.

Consequences of answering step 3 from GitHub rather than local state: no KV
binding is needed, a missed tick self-heals inside the grace window, a double
tick cannot double-post, and clicking **Run workflow** manually counts as
serving the slot.

Dispatched runs skip the workflow's in-job `sleep` jitter (it is gated on
`github.event_name == 'schedule'`). That is intentional — the randomisation now
lives in the slot planner, and the in-job sleep would only re-add drift.

## Setup

```bash
cd video-cron-worker

# PAT with Actions: read+write on Tejas-Sands/Neon.node
npx wrangler secret put GITHUB_TOKEN

# optional — unlocks the read-only plan endpoint
npx wrangler secret put DEBUG_KEY

npx wrangler deploy
```

Then **disable the `schedule:` block in `.github/workflows/generate_video.yml`**,
or both schedulers fire and you get 12+ runs/day.

## Cadence dial

All in `wrangler.jsonc` `vars` — change `POSTS_PER_DAY` alone to go 6/7/8 and
everything re-spaces itself. Redeploy to apply.

| var | default | meaning |
|---|---|---|
| `POSTS_PER_DAY` | `7` | slots per day (1–12) |
| `WINDOW_START_IST` / `WINDOW_END_IST` | `07:30` / `22:45` | active posting window |
| `MIN_GAP_MIN` | `75` | floor between posts; keep above the worst-case run duration (58 min observed) |
| `GRACE_MIN` | `90` | how stale a missed slot may be before it is written off |

Sample plans at `POSTS_PER_DAY=7` (verified over a 365-day sweep: 0 gap
violations, 0 out-of-window slots, 0 slots unreachable by a `*/10` tick):

```
2026-07-26  08:04  10:18  12:32  14:35  17:03  19:07  21:24
2026-07-27  09:07  10:53  12:49  15:41  17:53  19:41  21:57
2026-07-28  08:49  10:46  12:55  14:52  17:06  19:32  21:54
```

## Checking it

```bash
npx wrangler tail video-cron              # dispatch / failure logs
curl "https://video-cron.<subdomain>.workers.dev/?key=$DEBUG_KEY"
```

The endpoint is read-only — it never dispatches — and returns today's plan, the
slot currently due, the last run time, and what the next tick would decide.
Without a matching `DEBUG_KEY` it returns a bare `video-cron is running`, so the
posting schedule is not one URL guess away.
