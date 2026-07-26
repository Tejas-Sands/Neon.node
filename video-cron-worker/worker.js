/**
 * video-cron — Cloudflare Cron Trigger that fires generate_video.yml ON TIME.
 *
 * Why this exists
 * ---------------
 * GitHub's `schedule:` queue is best-effort and, on this repo, chronically
 * late: measured over 2026-07-22..26 every scheduled run fired 52-175 minutes
 * after its cron, worst in the 03:00-07:00 UTC band (03:23 cron -> ~+166 min
 * average). That pushed the intended 08:53-21:32 IST spread into 11:40-22:50
 * IST and opened a 12-13.5 h overnight hole. Cloudflare Cron Triggers fire
 * within seconds, so the posting plan lives here instead.
 *
 * Design
 * ------
 * ONE cron trigger (`*&#47;10 * * * *`), not one per post: the Workers Free plan
 * allows only 5 cron triggers PER ACCOUNT. Every tick the Worker rebuilds
 * today's post plan and asks "is a slot due that hasn't been served yet?".
 *
 *  - Slot times are derived from a PRNG seeded on the IST date, so the daily
 *    times shift every day (anti-pattern-detection) while staying stable
 *    within a day — every tick of the same day computes the same plan, which
 *    is what makes the "already served?" check reliable.
 *  - "Already served?" is answered by GitHub itself (latest run's created_at),
 *    not by local state. That makes the Worker stateless (no KV binding), and
 *    self-healing: a missed tick still fires inside the grace window, and a
 *    double tick can't double-post.
 *  - Dispatched runs skip the workflow's in-job `sleep` jitter step (it is
 *    gated on `github.event_name == 'schedule'`). That is intentional: the
 *    randomisation now lives in the slot planner, and a 0-25 min in-job sleep
 *    would only re-introduce the drift this Worker exists to remove.
 *
 * Config (wrangler.jsonc vars): GITHUB_REPO, GITHUB_REF, WORKFLOW_FILE,
 *   POSTS_PER_DAY, WINDOW_START_IST, WINDOW_END_IST, MIN_GAP_MIN, GRACE_MIN.
 * Secrets (wrangler secret put): GITHUB_TOKEN (needs Actions: read+write),
 *   DEBUG_KEY (optional — unlocks the read-only plan endpoint).
 */

const IST_OFFSET_MIN = 330; // India has no DST — a constant offset is correct.
const MINUTE = 60_000;

// --- deterministic PRNG (mulberry32), same family as the renderer's looks.ts
function makeRng(seed) {
  let a = seed >>> 0 || 0x9e3779b9;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** FNV-1a 32-bit — turns the IST date string into a stable seed. */
function hashString(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** "HH:MM" -> minutes after IST midnight. */
function parseHm(value, fallback) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(String(value || "").trim());
  if (!m) return fallback;
  const mins = Number(m[1]) * 60 + Number(m[2]);
  return Number.isFinite(mins) && mins >= 0 && mins <= 24 * 60 ? mins : fallback;
}

function num(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function readConfig(env) {
  return {
    repo: env.GITHUB_REPO || "",
    ref: env.GITHUB_REF || "main",
    workflowFile: env.WORKFLOW_FILE || "generate_video.yml",
    posts: Math.max(1, Math.min(12, Math.round(num(env.POSTS_PER_DAY, 7)))),
    windowStart: parseHm(env.WINDOW_START_IST, 7 * 60 + 30),
    windowEnd: parseHm(env.WINDOW_END_IST, 22 * 60 + 45),
    minGap: Math.max(15, num(env.MIN_GAP_MIN, 75)),
    grace: Math.max(10, num(env.GRACE_MIN, 90)),
  };
}

/** UTC-ms of IST midnight for whichever IST day `nowMs` falls in. */
function istDayStart(nowMs) {
  const shifted = nowMs + IST_OFFSET_MIN * MINUTE;
  const dayMs = 24 * 60 * MINUTE;
  return Math.floor(shifted / dayMs) * dayMs - IST_OFFSET_MIN * MINUTE;
}

function istDateKey(nowMs) {
  return new Date(nowMs + IST_OFFSET_MIN * MINUTE).toISOString().slice(0, 10);
}

/**
 * Today's posting plan as UTC epoch-ms, ascending.
 *
 * Built by distributing SLACK rather than jittering fixed positions. Every gap
 * starts at exactly `minGap`; whatever time the window has left over is split
 * across `posts + 1` random buckets — one before the first post, one on each
 * gap, one after the last. That construction gives three properties a
 * jitter-and-clamp approach cannot:
 *   - no gap is ever below minGap, so two renders never queue behind each
 *     other (observed run duration 10-58 min, avg ~22);
 *   - nothing is ever clamped to the window edge, so the first and last post
 *     of the day are NOT the same clock time every day — clamping was
 *     re-creating exactly the fixed-time fingerprint this Worker removes;
 *   - the whole plan is re-rolled per IST day but stable within it, which is
 *     what makes the "has this slot been served?" check reliable.
 */
function planSlots(nowMs, cfg) {
  const dayStart = istDayStart(nowMs);
  const rng = makeRng(hashString(`${istDateKey(nowMs)}|${cfg.posts}|v1`));

  const span = cfg.windowEnd - cfg.windowStart;
  if (cfg.posts === 1) {
    return [dayStart + Math.round(cfg.windowStart + rng() * span) * MINUTE];
  }

  // If the window is too tight for posts x minGap, honour the post count and
  // shrink the gap — the operator asked for N posts, not for N-1.
  const gapFloor = Math.min(cfg.minGap, Math.floor(span / (cfg.posts - 1)));
  const slack = Math.max(0, span - gapFloor * (cfg.posts - 1));

  // posts + 1 buckets: [head, ...gap extras, tail]. Weights are floored well
  // above zero so a bucket rarely collapses to the bare minimum gap.
  const weights = Array.from({ length: cfg.posts + 1 }, () => 0.35 + rng());
  const total = weights.reduce((a, w) => a + w, 0);
  const share = weights.map((w) => (w / total) * slack);

  const minutes = [];
  let cursor = cfg.windowStart + share[0];
  minutes.push(Math.round(cursor));
  for (let i = 1; i < cfg.posts; i++) {
    cursor += gapFloor + share[i];
    minutes.push(Math.round(cursor));
  }
  return minutes.map((m) => dayStart + m * MINUTE);
}

const ghHeaders = (env) => ({
  Authorization: `Bearer ${env.GITHUB_TOKEN}`,
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent": "video-cron-worker",
});

/** Epoch-ms the most recent run of the workflow was CREATED, or null. */
async function lastRunCreatedAt(env, cfg) {
  const url =
    `https://api.github.com/repos/${cfg.repo}/actions/workflows/` +
    `${cfg.workflowFile}/runs?per_page=1`;
  const resp = await fetch(url, { headers: ghHeaders(env) });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "");
    throw new Error(`runs query failed ${resp.status}: ${detail.slice(0, 200)}`);
  }
  const body = await resp.json();
  const run = body?.workflow_runs?.[0];
  return run?.created_at ? Date.parse(run.created_at) : null;
}

async function dispatchWorkflow(env, cfg) {
  const resp = await fetch(
    `https://api.github.com/repos/${cfg.repo}/actions/workflows/` +
      `${cfg.workflowFile}/dispatches`,
    {
      method: "POST",
      headers: { ...ghHeaders(env), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: cfg.ref, inputs: {} }),
    },
  );
  if (resp.status === 204) return { ok: true };
  const detail = await resp.text().catch(() => "");
  return { ok: false, status: resp.status, detail: detail.slice(0, 300) };
}

/**
 * Decide what this tick should do. Pure apart from the two GitHub reads, so
 * the debug endpoint can show exactly what the next cron tick would decide.
 */
async function evaluate(env, nowMs) {
  const cfg = readConfig(env);
  if (!cfg.repo) return { action: "misconfigured", reason: "GITHUB_REPO unset" };
  if (!env.GITHUB_TOKEN) {
    return { action: "misconfigured", reason: "GITHUB_TOKEN secret unset" };
  }

  const slots = planSlots(nowMs, cfg);
  // The most recent slot that is due. Slots older than the grace window are
  // written off — a 4-hour Cloudflare outage must not dump a post at 02:00.
  let due = null;
  for (const slot of slots) {
    if (slot <= nowMs && nowMs - slot <= cfg.grace * MINUTE) due = slot;
  }
  if (due === null) return { action: "idle", cfg, slots };

  const lastRun = await lastRunCreatedAt(env, cfg);
  // A run created at or after the slot opened already served it. This is also
  // what makes manual "Run workflow" clicks count — no double post.
  if (lastRun !== null && lastRun >= due) {
    return { action: "already-served", cfg, slots, due, lastRun };
  }
  if (lastRun !== null && nowMs - lastRun < cfg.minGap * MINUTE) {
    return { action: "too-soon", cfg, slots, due, lastRun };
  }
  return { action: "dispatch", cfg, slots, due, lastRun };
}

const hhmmIst = (ms) =>
  new Date(ms + IST_OFFSET_MIN * MINUTE).toISOString().slice(11, 16);

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      (async () => {
        const now = event.scheduledTime || Date.now();
        let decision;
        try {
          decision = await evaluate(env, now);
        } catch (err) {
          console.error(
            JSON.stringify({ event: "evaluate_failed", error: String(err).slice(0, 300) }),
          );
          return;
        }

        if (decision.action !== "dispatch") {
          // Only log the interesting non-actions; 144 "idle" lines a day is noise.
          if (decision.action !== "idle") {
            console.log(JSON.stringify({ event: decision.action, reason: decision.reason }));
          }
          return;
        }

        const result = await dispatchWorkflow(env, decision.cfg);
        console.log(
          JSON.stringify({
            event: result.ok ? "dispatched" : "dispatch_failed",
            slot_ist: hhmmIst(decision.due),
            status: result.status,
            detail: result.detail,
          }),
        );
      })(),
    );
  },

  /**
   * Read-only status endpoint — never dispatches. Returns the plan only when
   * DEBUG_KEY is configured AND matches, so the posting schedule is not a
   * public URL away from anyone who finds the workers.dev hostname.
   */
  async fetch(request, env) {
    const url = new URL(request.url);
    const key = url.searchParams.get("key");
    if (!env.DEBUG_KEY || key !== env.DEBUG_KEY) {
      return new Response("video-cron is running", { status: 200 });
    }
    const now = Date.now();
    let decision;
    try {
      decision = await evaluate(env, now);
    } catch (err) {
      return Response.json({ error: String(err).slice(0, 300) }, { status: 502 });
    }
    return Response.json({
      now_ist: hhmmIst(now),
      ist_date: istDateKey(now),
      would_do: decision.action,
      reason: decision.reason,
      plan_ist: (decision.slots || []).map(hhmmIst),
      due_slot_ist: decision.due ? hhmmIst(decision.due) : null,
      last_run_ist: decision.lastRun ? hhmmIst(decision.lastRun) : null,
      config: decision.cfg && {
        repo: decision.cfg.repo,
        workflow: decision.cfg.workflowFile,
        posts_per_day: decision.cfg.posts,
        window_ist: `${hhmmIst(istDayStart(now) + decision.cfg.windowStart * MINUTE)}-${hhmmIst(istDayStart(now) + decision.cfg.windowEnd * MINUTE)}`,
        min_gap_min: decision.cfg.minGap,
      },
    });
  },
};
