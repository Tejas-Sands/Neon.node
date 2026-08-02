import os
import random
import sys
import time
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
    _gather_ci_candidates,
    get_hacker_news_frontpage,
    build_hn_news_prompt,
    extract_article_body,
    filter_and_pick_story,
    load_topic_history,
    plan_story_angle,
    record_topic_use,
    send_telegram_message,
    render_status_store,
    PROCESSED_NEWS_FILE,
    AUTO_CHANNEL_PREFIXES,
    _derive_seed,
    _extract_topic_keywords,
    _normalize_subject,
    collect_ledger_metrics,
)
from format_packs import build_pack_prompt, resolve_pack
from main import plan_pack_brief


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

    # Format pack for this run: FORMAT_PACK env pin, unset/unknown -> the
    # legacy news pipeline bit-for-bit. This is how a 12-post format
    # commitment window is run (pin the pack in the CI env). Seeded/bandit
    # rotation joins later, once the ledger carries scored pack labels.
    format_pack = resolve_pack(os.environ.get("FORMAT_PACK"))["name"]
    if format_pack != "legacy-news":
        print(f"Format pack: {format_pack}")

    # One try covers EVERYTHING after the session id — story ranking and prompt
    # building crash too (e.g. bad API data), and those failures must reach the
    # Telegram alert below just like render failures.
    try:
        # Multi-source intake (B4): NEWS_SOURCES repo Variable, comma list of
        # hn|hnbest|lobsters|rss. Unset/"hn" = the legacy HN-only path
        # byte-for-byte. Non-HN candidates carry a prefixed uid in _hn_id
        # (lob:<id>, rss:<sha1>), so history dedup and the record_topic_use
        # call in the frozen delivery region work unchanged.
        sources = [s.strip().lower()
                   for s in os.environ.get("NEWS_SOURCES", "hn").split(",") if s.strip()]
        multi_source = sources != ["hn"]

        stories = []
        candidates = []
        if multi_source:
            print(f"Fetching trending topics from sources: {', '.join(sources)}...")
            try:
                candidates, source_counts = _gather_ci_candidates(sources)
            except Exception as e:
                print(f"Multi-source intake failed: {e}")
                candidates, source_counts = [], {s: 0 for s in sources}
            dead = [k for k, v in source_counts.items() if v == 0]
            if dead and len(dead) * 2 > len(source_counts) and not dry_run:
                _alert_telegram(
                    f"⚠️ Topic intake: {len(dead)}/{len(source_counts)} sources "
                    f"returned nothing ({', '.join(dead)}) — running on a thin pool.",
                    session_id,
                )
        else:
            print("Fetching trending topics from Hacker News...")
            try:
                stories = get_hacker_news_frontpage(min_score=100, limit=15)
            except Exception as e:
                print(f"Failed to get HN stories: {e}")
            candidates = _hn_to_candidates(stories)

        best = None
        plan = None
        pack_brief = None
        if not candidates:
            print("Could not fetch HackerNews stories. Falling back to default tech prompt.")
            if format_pack in ("quiz-reveal", "data-rankings"):
                # Brief packs need a real article to ground their data —
                # degrade rather than render a quiz with nothing to quiz.
                print(f"[PackBrief] No stories to ground a {format_pack} brief — degrading to facts-explainer.")
                format_pack = "facts-explainer"
            prompt = (
                "Create a fast-paced vertical video about ONE specific, real, currently-relevant developer tool or "
                "product release (pick a concrete named one — e.g. a specific framework version, database feature, or "
                "gadget). Show what it is, how it's used in practice, and one real number that proves it matters. "
                "No generic filler."
            )
        else:
            # Rank real stories by viral potential, EXCLUDING ones recent runs
            # already covered — the history file is committed back to the repo
            # by the workflow, so it survives ephemeral CI runners. Pick mode /
            # freshness / entity-cooldown behavior is flag-gated inside
            # filter_and_pick_story (TOPIC_* repo Variables; defaults legacy).
            history = load_topic_history(PROCESSED_NEWS_FILE)
            print(f"Loaded topic history: {len(history)} previously used stories.")
            rng = random.Random(_derive_seed(session_id))
            best, was_fallback = filter_and_pick_story(candidates, history, rng, top_n=5)
            if was_fallback and not dry_run:
                _alert_telegram(
                    "⚠️ Topic dedup fallback: every frontpage story was already "
                    f"used; re-airing least-recent: '{best.get('title', '')[:120]}'",
                    session_id,
                )
            elif not dry_run and 0 < best.get("_fresh_pool", 99) < 3:
                # Early warning BEFORE the LRU fallback ever fires — the pool
                # after dedup/freshness/cooldown is nearly dry.
                _alert_telegram(
                    f"⚠️ Thin topic pool: only {best.get('_fresh_pool')} eligible "
                    "candidate(s) after dedup/freshness/cooldown — tomorrow may "
                    "hit the repeat fallback.",
                    session_id,
                )
            if multi_source:
                # Observability: the ranked shortlist with source/age tags —
                # the only way to sanity-check cross-source scoring from logs.
                ranked = sorted(candidates, key=lambda c: c.get("_score", 0.0), reverse=True)[:8]
                for i, c in enumerate(ranked, 1):
                    srcs = ",".join(c.get("sources") or [c.get("source", "?")])
                    print(f"  #{i} [{srcs}|{float(c.get('age_hours', 0)):.0f}h|"
                          f"{float(c.get('_score', 0)):.2f}] {c.get('title', '')[:80]}")

            def _resolve_pick(b):
                """Title + url for a picked candidate. HN picks match back to
                the raw story dict by id (titles can collide after rewording);
                other sources carry their url on the candidate itself."""
                if not multi_source:
                    st = next(
                        (s for s in stories if str(s.get("id")) == str(b.get("_hn_id"))), None
                    ) or next((s for s in stories if s.get("title") == b["title"]), stories[0])
                    return st.get("title", ""), st.get("url", "")
                return b.get("title", ""), b.get("url", "")

            title, story_url = _resolve_pick(best)
            # Candidates carry no article text — scrape it, exactly like the
            # /render/hn-news endpoint does. Without it the prompt says "No
            # article content available." and the LLM writes thin, headline-only
            # scripts (or invents specifics the fabrication guard then fights).
            body = ""
            try:
                body = extract_article_body(story_url)
            except Exception as e:
                print(f"Article scrape failed (continuing with headline only): {e}")
            print(f"Selected story (virality score {best['_score']:.2f}): '{title}' (article body: {len(body)} chars)")

            # Editorial judge: turn the picked story into a concrete end-to-end
            # plan (subject/angle/insight + facts copied from the article). A
            # vague-story verdict re-picks once; every failure path degrades to
            # the plain news prompt — the judge can delay a run, never kill it.
            if os.environ.get("CI_TOPIC_JUDGE", "true").strip().lower() == "true":
                repicks = int(os.environ.get("CI_TOPIC_REPICKS", "1"))
                for _round in range(1 + repicks):
                    plan = plan_story_angle(
                        title, body, url=story_url, session_id=session_id)
                    if plan is None:
                        break  # LLM/parse failure — a retry would fail the same way
                    if plan.get("subject"):
                        break  # concrete subject found
                    if _round >= repicks:
                        break  # verdicts exhausted — ship this pick, plain prompt
                    # Vague-story verdict: exclude this pick via a synthetic
                    # history entry (id + norm, same shape record_topic_use
                    # writes) and judge the next-best story instead.
                    history = history + [{
                        "id": str(best.get("_hn_id")) if best.get("_hn_id") is not None else None,
                        "title": best.get("title", ""),
                        "norm": _normalize_subject(best.get("title", "")),
                        "ts": int(time.time()),
                    }]
                    nxt, nxt_fb = filter_and_pick_story(candidates, history, rng, top_n=5)
                    if nxt_fb:
                        break  # nothing fresh left — keep the original pick
                    best, plan = nxt, None
                    title, story_url = _resolve_pick(best)
                    body = ""
                    try:
                        body = extract_article_body(story_url)
                    except Exception as e:
                        print(f"Article scrape failed on re-pick (continuing with headline only): {e}")
                    print(f"[TopicJudge] Re-picked story (virality score {best['_score']:.2f}): "
                          f"'{title}' (article body: {len(body)} chars)")
                if plan is not None and not plan.get("subject"):
                    plan = None  # still vague — current pick ships with today's prompt

            # Brief packs (quiz/rankings): plan the grounded data brief from
            # the SAME scraped article the judge saw. A thin/failed brief
            # DEGRADES the run to facts-explainer — a slot is never lost to
            # an unquizzable story.
            if format_pack in ("quiz-reveal", "data-rankings"):
                pack_brief = plan_pack_brief(
                    format_pack, title, body, plan=plan, session_id=session_id)
                if pack_brief is None:
                    print(f"[PackBrief] No usable {format_pack} brief — degrading to facts-explainer.")
                    format_pack = "facts-explainer"

            # gh- sessions get the branded outro appended, so the closer must
            # not carry its own follow ask (it would play twice back-to-back).
            # Loop-ending packs (LOOP_ENDING + pack bit) instead end on the
            # payoff with NO ask anywhere in the script — the render-side
            # FollowChip is the single follow-ask.
            loop_ending = (
                os.environ.get("LOOP_ENDING", "false").strip().lower() in ("1", "true", "yes")
                and bool(resolve_pack(format_pack)["loop_ending"])
            )
            if pack_brief is not None:
                # Pack prompts carry their own outline + no-ask rules.
                prompt = build_pack_prompt(
                    format_pack, title, pack_brief, seed=_derive_seed(session_id))
            else:
                prompt = build_hn_news_prompt(
                    title, body, seed=_derive_seed(session_id),
                    outro_appended=session_id.startswith(AUTO_CHANNEL_PREFIXES),
                    plan=plan,
                    ending="no-ask" if loop_ending else None,
                )

        if dry_run:
            print(f"[DRY-RUN] Format pack: {format_pack}")
            print("\n[DRY-RUN] Prompt that would be rendered:\n" + "-" * 50)
            print(prompt[:2000])
            print("-" * 50)
            if best is not None:
                if plan:
                    print(f"[DRY-RUN] Judge plan: subject='{plan.get('subject')}' "
                          f"angle='{(plan.get('angle') or '')[:80]}' "
                          f"insight='{(plan.get('insight') or '')[:80]}' "
                          f"facts={len(plan.get('facts') or [])}")
                else:
                    print("[DRY-RUN] Judge plan: none (plain news prompt)")
        else:
            # Define the request — Telegram (archive) + Instagram/YouTube from env secrets
            req = RenderRequest(
                prompt=prompt,
                format_pack=format_pack,
                pack_brief=pack_brief,
                topic_meta=(
                    {
                        "title": best.get("title", ""),
                        "subject": ((plan or {}).get("subject")
                                    or best.get("subject", "") or best.get("title", "")),
                        "url": best.get("url", ""),
                        # "hn" preserved for HN picks (ledger continuity);
                        # other sources record their own key (lobsters/rss:*).
                        "source": ("hn" if best.get("source") in (None, "hackernews")
                                   else best.get("source", "hn")),
                        "keywords": _extract_topic_keywords(best.get("title", "")),
                        "viral_score": round(float(best.get("_score", 0.0)), 2),
                        # Additive judge fields — the ledger copies this dict
                        # as-is and the feedback loop reads only "keywords",
                        # so extra keys are inert to both.
                        "sources": best.get("sources") or [],
                        "display_title": (plan or {}).get("display_title", ""),
                        "angle": (plan or {}).get("angle", ""),
                        "insight": (plan or {}).get("insight", ""),
                        "judge": "plan" if plan else "none",
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
                    subject=(plan or {}).get("subject", ""),
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
