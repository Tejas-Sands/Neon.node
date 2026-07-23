import os
import random
import sys
import uuid
from main import (
    RenderRequest,
    PipelineConfig,
    TelegramConfig,
    InstagramConfig,
    FacebookConfig,
    _execute_render_unlocked,
    _build_env_youtube_config,
    _hn_to_candidates,
    get_hacker_news_frontpage,
    build_hn_news_prompt,
    extract_article_body,
    filter_and_pick_story,
    load_topic_history,
    record_topic_use,
    send_telegram_message,
    render_status_store,
    PROCESSED_NEWS_FILE,
    AUTO_CHANNEL_PREFIXES,
    _derive_seed,
    _extract_topic_keywords,
    collect_ledger_metrics,
)


def _build_env_instagram_config():
    """InstagramConfig from env vars (official Graph API only — the TOS-safe path)."""
    if os.environ.get("ENABLE_INSTAGRAM_AUTOPOST", "").strip().lower() != "true":
        return None
    biz_id = os.environ.get("INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID") or os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    token = os.environ.get("FB_ACCESS_TOKEN_TECH") or os.environ.get("FB_ACCESS_TOKEN")
    if not (biz_id and token):
        print("Instagram autopost enabled but Graph API creds missing; skipping IG.")
        return None
    return InstagramConfig(
        enabled=True,
        method="official",
        instagram_business_account_id=biz_id,
        fb_access_token=token,
        auto_generate_caption=True,
    )


def _build_env_facebook_config():
    """FacebookConfig from env vars (official Reels Publishing API only)."""
    if os.environ.get("ENABLE_FACEBOOK_AUTOPOST", "").strip().lower() != "true":
        return None
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = (os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
             or os.environ.get("FB_ACCESS_TOKEN", "").strip())
    if not (page_id and token):
        print("Facebook autopost enabled but FB_PAGE_ID / token missing; skipping FB.")
        return None
    return FacebookConfig(
        enabled=True,
        page_id=page_id,
        access_token=token,
        auto_generate_caption=True,
    )


def _alert_telegram(text: str, session_id: str):
    """Best-effort Telegram note — must never raise (an alert failing is bad,
    an alert failure killing the run would be worse)."""
    try:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if bot_token and chat_id:
            send_telegram_message(text, bot_token, chat_id, session_id)
    except Exception as tg_err:
        print(f"Could not send Telegram note: {tg_err}")


def main():
    dry_run = "--dry-run" in sys.argv
    if "--collect-only" in sys.argv:
        # Metrics sweep without rendering/posting — used for backfill testing
        # and ad-hoc collection runs.
        print("[Collect-Only] Fetching post metrics only — no render, no posting.")
        try:
            summary = collect_ledger_metrics(session_id="gh-metrics")
            print(f"[Collect-Only] Done: {summary}")
        except Exception as e:
            print(f"[Collect-Only] FAILED: {e}")
            sys.exit(1)
        return
    print("Starting automated video generation via GitHub Actions...")
    if dry_run:
        print("=" * 50)
        print("[DRY-RUN] Story selection + history only — no render, no posting.")
        print("=" * 50)

    # We generate a unique session ID for logging
    session_id = f"gh-{str(uuid.uuid4())[:6]}"

    # One try covers EVERYTHING after the session id — story ranking and prompt
    # building crash too (e.g. bad API data), and those failures must reach the
    # Telegram alert below just like render failures.
    try:
        print("Fetching trending topics from Hacker News...")
        stories = []
        try:
            stories = get_hacker_news_frontpage(min_score=100, limit=15)
        except Exception as e:
            print(f"Failed to get HN stories: {e}")

        best = None
        if not stories:
            print("Could not fetch HackerNews stories. Falling back to default tech prompt.")
            prompt = (
                "Create a fast-paced vertical video about ONE specific, real, currently-relevant developer tool or "
                "product release (pick a concrete named one — e.g. a specific framework version, database feature, or "
                "gadget). Show what it is, how it's used in practice, and one real number that proves it matters. "
                "No generic filler."
            )
        else:
            # Rank real stories by viral potential, EXCLUDING ones recent runs
            # already covered — the history file is committed back to the repo
            # by the workflow, so it survives ephemeral CI runners. The pick is
            # weighted-random over the top 5 (not argmax): while a big headline
            # sits on the front page all day, a deterministic argmax re-picked
            # it on every one of the day's crons.
            history = load_topic_history(PROCESSED_NEWS_FILE)
            print(f"Loaded topic history: {len(history)} previously used stories.")
            candidates = _hn_to_candidates(stories)
            rng = random.Random(_derive_seed(session_id))
            best, was_fallback = filter_and_pick_story(candidates, history, rng, top_n=5)
            if was_fallback and not dry_run:
                _alert_telegram(
                    "⚠️ Topic dedup fallback: every frontpage story was already "
                    f"used; re-airing least-recent: '{best.get('title', '')[:120]}'",
                    session_id,
                )
            # Match back by HN id first — titles can collide after rewording.
            story = next(
                (s for s in stories if str(s.get("id")) == str(best.get("_hn_id"))), None
            ) or next((s for s in stories if s.get("title") == best["title"]), stories[0])
            title = story.get("title", "")
            # HN story dicts carry no article text — scrape it, exactly like the
            # /render/hn-news endpoint does. Without it the prompt says "No
            # article content available." and the LLM writes thin, headline-only
            # scripts (or invents specifics the fabrication guard then fights).
            body = ""
            try:
                body = extract_article_body(story.get("url", ""))
            except Exception as e:
                print(f"Article scrape failed (continuing with headline only): {e}")
            print(f"Selected story (virality score {best['_score']:.2f}): '{title}' (article body: {len(body)} chars)")
            # gh- sessions get the branded outro appended, so the closer must
            # not carry its own follow ask (it would play twice back-to-back).
            prompt = build_hn_news_prompt(
                title, body, seed=_derive_seed(session_id),
                outro_appended=session_id.startswith(AUTO_CHANNEL_PREFIXES),
            )

        if dry_run:
            print("\n[DRY-RUN] Prompt that would be rendered:\n" + "-" * 50)
            print(prompt[:2000])
            print("-" * 50)
        else:
            # Define the request — Telegram (archive) + Instagram/YouTube from env secrets
            req = RenderRequest(
                prompt=prompt,
                topic_meta=(
                    {
                        "title": best.get("title", ""),
                        "subject": best.get("subject", "") or best.get("title", ""),
                        "url": best.get("url", ""),
                        "source": "hn",
                        "keywords": _extract_topic_keywords(best.get("title", "")),
                        "viral_score": round(float(best.get("_score", 0.0)), 2),
                    }
                    if best is not None else None
                ),
                pipeline=PipelineConfig(
                    quality="standard",
                    outputFormat="mp4",
                    telegram=TelegramConfig(enabled=True),
                    instagram=_build_env_instagram_config(),
                    youtube=_build_env_youtube_config(),
                    facebook=_build_env_facebook_config(),
                )
            )

            # Run the generation synchronously. This ensures the GitHub Action
            # stays alive until the video is fully rendered and delivered!
            result = _execute_render_unlocked(req, session_id=session_id, sync_delivery=True)

            # Verify deliveries actually landed. The posting dispatchers swallow
            # their own errors (so one platform's crash never kills a sibling's
            # upload), which means the render returns "success" even when every
            # post silently died — the run must not go green on that.
            st = render_status_store.get(session_id, {})
            attempted = {
                platform: st.get(f"{platform.lower()}_status")
                for platform in ("Instagram", "Telegram", "YouTube", "Facebook")
                if st.get(f"{platform.lower()}_status") is not None
            }
            failed = {
                platform: st.get(f"{platform.lower()}_error") or status
                for platform, status in attempted.items()
                if status not in ("posted", "facebook_posted")
            }
            if failed and len(failed) == len(attempted):
                details = "; ".join(f"{p}: {e}" for p, e in failed.items())
                raise Exception(
                    f"Video rendered but EVERY delivery failed — {details[:600]}"
                )
            if failed:
                detail_lines = "\n".join(f"• {p}: {e}" for p, e in failed.items())
                msg = f"⚠️ Video posted, but some platforms failed:\n{detail_lines}"[:3900]
                print(msg)
                _alert_telegram(msg, session_id)

            print("\n" + "=" * 50)
            print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
            print(f"Session ID: {result.get('session_id')}")
            print("=" * 50 + "\n")

        # Record history only AFTER success (or in dry-run, where it stands in
        # for the render) — a failed render never burns the story, so the next
        # run can retry it: it never aired.
        if best is not None:
            try:
                record_topic_use(
                    PROCESSED_NEWS_FILE,
                    story_id=best.get("_hn_id"),
                    title=best.get("title", ""),
                    session_id=session_id,
                )
                print(f"Recorded topic use in {PROCESSED_NEWS_FILE}.")
            except Exception as e:
                # The video already went out — the generic "no video was posted"
                # failure alert would lie. Send a precise note and exit cleanly.
                msg = (
                    "⚠️ Video posted OK but topic-history save failed — "
                    f"the next run may repeat this story: {e}"
                )
                print(msg)
                if not dry_run:
                    _alert_telegram(msg, session_id)

        # Collect performance metrics for earlier posts (feedback-loop data).
        # Failure must never fail the run — today's video already went out;
        # like the history save above, alert precisely instead.
        if not dry_run:
            try:
                summary = collect_ledger_metrics(session_id=session_id)
                print(f"Post-metrics collection: {summary}")
            except Exception as e:
                msg = f"⚠️ Video posted OK but metrics collection failed: {e}"
                print(msg)
                _alert_telegram(msg, session_id)

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        # Best-effort Telegram alert — you watch Telegram, not the Actions
        # dashboard, so a silent red X would go unnoticed for hours.
        _alert_telegram(
            f"❌ Scheduled video generation FAILED (no video was posted):\n{str(e)[:400]}",
            session_id,
        )
        # Exit with error code so GitHub Actions marks the run as Failed
        sys.exit(1)


if __name__ == "__main__":
    main()
