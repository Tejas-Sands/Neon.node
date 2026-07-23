/**
 * scenery-bot — Telegram webhook receiver that triggers the Artistic Scenery
 * GitHub Actions workflow (generate_scenery.yml) on demand.
 *
 *   /scenery                  -> autonomous render (LLM picks the place)
 *   /scenery Faroe Islands    -> render THAT place
 *   /start, /help             -> usage
 *
 * Security model:
 *  - Telegram signs every webhook delivery with the secret_token set at
 *    setWebhook time; we verify it timing-safely before touching the body.
 *  - Only ALLOWED_CHAT_ID may trigger renders; everything else is silently
 *    ignored (200 so Telegram never retries, no information leaked).
 *  - Always answers 200 to valid-secret deliveries — a non-2xx makes Telegram
 *    re-deliver the same update and would double-trigger renders.
 *
 * Secrets (wrangler secret put): BOT_TOKEN, WEBHOOK_SECRET, GITHUB_TOKEN,
 * ALLOWED_CHAT_ID. Vars (wrangler.jsonc): GITHUB_REPO, GITHUB_REF.
 */

const WORKFLOW_FILE = "generate_scenery.yml";

/** Timing-safe string comparison (hash first so lengths always match). */
async function secretsMatch(provided, expected) {
  if (!provided || !expected) return false;
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(provided)),
    crypto.subtle.digest("SHA-256", enc.encode(expected)),
  ]);
  return crypto.subtle.timingSafeEqual(a, b);
}

async function sendReply(env, chatId, text) {
  const resp = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
  if (!resp.ok) {
    console.error(JSON.stringify({ event: "telegram_reply_failed", status: resp.status }));
  }
  // Drain so the connection is released even when we ignore the body.
  await resp.arrayBuffer().catch(() => {});
}

async function dispatchWorkflow(env, concept) {
  const inputs = concept ? { concept } : {};
  const resp = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "scenery-bot-worker",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: env.GITHUB_REF || "main", inputs }),
    },
  );
  if (resp.status === 204) return { ok: true };
  const detail = await resp.text().catch(() => "");
  console.error(JSON.stringify({ event: "dispatch_failed", status: resp.status, detail: detail.slice(0, 300) }));
  return { ok: false, status: resp.status };
}

const HELP_TEXT = [
  "🌄 Scenery bot",
  "/scenery — render one artistic scenery video (the pipeline picks a breathtaking place)",
  "/scenery <place> — render a specific place, e.g. /scenery Faroe Islands storm",
  "The finished video lands here in ~10 minutes.",
].join("\n");

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("scenery-bot is running", { status: 200 });
    }

    const provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (!(await secretsMatch(provided, env.WEBHOOK_SECRET))) {
      return new Response(JSON.stringify({ error: "unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("ok", { status: 200 });
    }

    try {
      const message = update.message || update.channel_post;
      const chatId = message?.chat?.id;
      const text = (message?.text || "").trim();
      if (!chatId || String(chatId) !== String(env.ALLOWED_CHAT_ID)) {
        return new Response("ok", { status: 200 });
      }

      // "/scenery@MyBot arg" and "/scenery arg" both parse.
      const match = text.match(/^\/(\w+)(?:@\S+)?\s*(.*)$/s);
      const command = match?.[1]?.toLowerCase();
      const arg = (match?.[2] || "").trim().slice(0, 120);

      if (command === "scenery") {
        const result = await dispatchWorkflow(env, arg);
        await sendReply(
          env,
          chatId,
          result.ok
            ? `🎬 Scenery render started${arg ? ` for “${arg}”` : ""} — the video should arrive here in ~10 minutes.`
            : `❌ Could not start the render (GitHub said ${result.status}). Check the Worker's GITHUB_TOKEN / GITHUB_REPO.`,
        );
      } else if (command === "start" || command === "help") {
        await sendReply(env, chatId, HELP_TEXT);
      }
      // Anything else (plain chatter, other commands): ignore quietly.
    } catch (err) {
      console.error(JSON.stringify({ event: "handler_error", error: String(err).slice(0, 300) }));
    }
    return new Response("ok", { status: 200 });
  },
};
