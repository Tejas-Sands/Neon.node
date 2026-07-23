"""Seed public/post_ledger.json from posts that ALREADY exist on the accounts.

The feedback loop needs history to learn from; without a backfill it would
start blind and take a week of new posts to say anything. Backfilled entries
carry no creative metadata (style pack / hook / seed / voice — those weren't
recorded at post time), so they are marked "backfilled": true and contribute
to the per-platform performance baselines only.

Usage (needs the same env vars as the pipeline):
    python scripts/backfill_ledger.py            # IG + YT (whatever creds allow)
    BACKFILL_CHANNEL=news python scripts/backfill_ledger.py

Instagram: needs FB_ACCESS_TOKEN[_TECH/_NEWS] + INSTAGRAM[_TECH/_NEWS]
_BUSINESS_ACCOUNT_ID.
YouTube: needs YT_API_KEY + YT_CHANNEL_ID (the upload OAuth token has
upload-only scope and cannot list videos).
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

from main import (  # noqa: E402
    POST_LEDGER_FILE,
    _extract_topic_keywords,
    _meta_graph_get,
    load_post_ledger,
    save_post_ledger,
)

BACKFILL_CHANNEL = os.environ.get("BACKFILL_CHANNEL", "tech").strip() or "tech"
BACKFILL_LIMIT = int(os.environ.get("BACKFILL_LIMIT", "30"))


def _parse_ts(value: str, fmt: str) -> int:
    try:
        return int(datetime.datetime.strptime(value, fmt).timestamp())
    except Exception:
        return 0


def _base_entry(session: str, ts: int, title: str) -> dict:
    return {
        "session": session,
        "ts": ts,
        "posted_hour_utc": datetime.datetime.utcfromtimestamp(ts).hour if ts else None,
        "channel": BACKFILL_CHANNEL,
        "topic": {"title": title[:160], "keywords": _extract_topic_keywords(title)},
        "backfilled": True,
        "platforms": {},
        "metrics": {},
    }


def backfill_instagram(ledger: dict, known_ids: set) -> int:
    token = (os.environ.get("FB_ACCESS_TOKEN_TECH") if BACKFILL_CHANNEL == "tech"
             else os.environ.get("FB_ACCESS_TOKEN_NEWS")) or os.environ.get("FB_ACCESS_TOKEN", "")
    biz_id = (os.environ.get("INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID") if BACKFILL_CHANNEL == "tech"
              else os.environ.get("INSTAGRAM_NEWS_BUSINESS_ACCOUNT_ID")) \
        or os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    token, biz_id = (token or "").strip(), (biz_id or "").strip()
    if not (token and biz_id):
        print("[Backfill] Instagram skipped — FB access token / business account id not set.")
        return 0
    data = _meta_graph_get(
        f"{biz_id}/media?fields=id,caption,timestamp,media_type"
        f"&limit={BACKFILL_LIMIT}&access_token={token}",
        session_id="Backfill",
    )
    if data.get("error"):
        raise Exception(f"IG media list failed: {data['error'].get('message', data)}")
    added = 0
    for media in data.get("data", []):
        media_id = str(media.get("id", ""))
        if not media_id or media_id in known_ids or media.get("media_type") not in (None, "VIDEO", "REELS"):
            continue
        ts = _parse_ts(media.get("timestamp", ""), "%Y-%m-%dT%H:%M:%S%z")
        title = (media.get("caption") or "").split("\n")[0]
        entry = _base_entry(f"backfill-ig-{media_id}", ts, title)
        entry["platforms"]["instagram"] = {"id": media_id, "posted_at": ts}
        entry["metrics"]["instagram"] = {"latest": None, "snap72": None,
                                         "deleted": False, "fetch_errors": 0}
        ledger["entries"].append(entry)
        known_ids.add(media_id)
        added += 1
    print(f"[Backfill] Instagram: added {added} entries.")
    return added


def backfill_youtube(ledger: dict, known_ids: set) -> int:
    api_key = os.environ.get("YT_API_KEY", "").strip()
    channel_id = os.environ.get("YT_CHANNEL_ID", "").strip()
    if not (api_key and channel_id):
        print("[Backfill] YouTube skipped — set YT_API_KEY and YT_CHANNEL_ID "
              "(the upload OAuth token cannot list videos).")
        return 0
    res = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={"part": "snippet", "channelId": channel_id, "order": "date",
                "type": "video", "maxResults": min(BACKFILL_LIMIT, 50), "key": api_key},
        timeout=30,
    )
    if res.status_code != 200:
        raise Exception(f"YT search failed ({res.status_code}): {res.text[:300]}")
    added = 0
    for item in res.json().get("items", []):
        video_id = str((item.get("id") or {}).get("videoId", ""))
        if not video_id or video_id in known_ids:
            continue
        snippet = item.get("snippet", {})
        ts = _parse_ts(snippet.get("publishedAt", ""), "%Y-%m-%dT%H:%M:%SZ")
        entry = _base_entry(f"backfill-yt-{video_id}", ts, snippet.get("title", ""))
        entry["platforms"]["youtube"] = {"id": video_id, "posted_at": ts}
        entry["metrics"]["youtube"] = {"latest": None, "snap72": None,
                                       "deleted": False, "fetch_errors": 0}
        ledger["entries"].append(entry)
        known_ids.add(video_id)
        added += 1
    print(f"[Backfill] YouTube: added {added} entries.")
    return added


def main() -> None:
    ledger = load_post_ledger()
    known_ids = {
        str(plat.get("id"))
        for e in ledger["entries"]
        for plat in (e.get("platforms") or {}).values()
        if plat.get("id")
    }
    added = backfill_instagram(ledger, known_ids) + backfill_youtube(ledger, known_ids)
    if not added:
        print("[Backfill] Nothing new to add.")
        return
    # Oldest first so the LEDGER_CAP trim in save keeps the newest entries.
    ledger["entries"].sort(key=lambda e: e.get("ts") or 0)
    save_post_ledger(ledger)
    print(f"[Backfill] Saved {added} new entries to {POST_LEDGER_FILE}. "
          f"Run `python generate_now.py --collect-only` (optionally with "
          f"METRICS_MIN_AGE_HOURS=0) to fetch their metrics now.")


if __name__ == "__main__":
    main()
