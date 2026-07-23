# Repo Rules for AI Assistants

**Required reading before any non-trivial change: [`AI_CONTEXT.md`](AI_CONTEXT.md)** — it is the full technical map of this system and the ledger of hard-won fixes. Its §0 and §4 "Pain Points" are load-bearing; never revert them.

## 🔒 Rule 1 — Instagram reel posting flow is FROZEN

The Instagram posting flow works perfectly in production (user-verified 2026-07-23). **Do not change it — in any file, for any reason — without explicitly asking the user first and getting approval in the same conversation.** This includes "safe" refactors, renames, dependency bumps, and cleanups. Full covered surface is defined in `AI_CONTEXT.md` §0: the Meta Graph API code in `main.py`, delivery dispatch + verification in `generate_now.py`, `get_meta_token.py`, `test_meta_graph_api.py`, `worker.js`, `wrangler.jsonc`, the posting steps of `.github/workflows/generate_video.yml`, and the related env contract.

The same caution applies to every other delivery path (YouTube, Facebook, Telegram): they are production posting code — ask before changing behavior.

## Rule 2 — Styling and editing live in React, not Python

All visual/motion/typography work happens in `src/remotion/` (seed-driven, deterministic — `makeRng(seed)`, never `Math.random()`/`Date.now()`). Do not modify `main.py` for styling or editing changes. Prefer extending `looks.ts` (pure seed→look) over adding schema fields; new draws in `deriveLook` must be appended AFTER all existing draws or every seed's look reshuffles.

## Rule 3 — Sync points and guards

- New theme/animation enum values require updating ALL sync points (zod schema, `ALLOWED_*` lists in `main.py`, prompt docs, TSX unions/switches) — or renders fail validation. Render-side-only modes (kept out of the zod enum) need no sync — prefer them.
- Never reintroduce word-splitting in subtitles/headlines (`break-word`, per-letter spans in wrapping flex) — `AI_CONTEXT.md` Pain Point 6.
- Fabrication guard (no invented people/quotes/numbers), anti-repetition rules, delivery verification, and feedback-loop clamps must never be weakened.
- CI (ubuntu-latest) has no pre-installed assets: all mp3/mp4 are gitignored and materialized by the pipeline; audio-path failures must abort loudly.
