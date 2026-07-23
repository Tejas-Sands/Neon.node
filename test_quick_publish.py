#!/usr/bin/env python3
"""
Quick Meta Graph API & Telegram End-to-End Test Script
======================================================
Takes an existing pre-rendered video from public/ directory (e.g. public/test.mp4)
and immediately executes:
  1. Instagram Reels publishing via official Meta Graph API
  2. Facebook Page Reels publishing via official Meta Graph API
  3. Direct Telegram video upload & deployment status report
"""

import os
import sys
import uuid
from pathlib import Path
from test_meta_graph_api import load_env_file, Colors

from main import (
    post_to_instagram_official,
    post_to_facebook_reel,
    post_to_telegram,
    _resolve_fb_page_token,
    InstagramConfig,
    FacebookConfig,
    TelegramConfig
)


def run_quick_test():
    # 1. Load .env
    load_env_file()
    
    # Locate existing 9:16 rendered mp4 file
    test_video = None
    for candidate in [
        "public/video-force-post-23f5.mp4",
        "public/video-force-post-9d90.mp4",
        "public/video-auto-tech-cmp27.mp4",
        "public/video-auto-tech-cmp3.mp4",
        "public/test-final.mp4"
    ]:
        if os.path.exists(candidate):
            test_video = candidate
            break

    if not test_video:
        print("❌ No existing 9:16 rendered video file found in public/ directory.")
        sys.exit(1)
        
    session_id = f"test-pub-{str(uuid.uuid4())[:4]}"
    print(f"\n🚀 Starting Quick End-to-End Test Pipeline [{session_id}]")
    print(f"📁 Video file: {test_video} ({os.path.getsize(test_video):,} bytes)")
    
    # Resolve Credentials
    ig_biz_id = os.environ.get("INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID") or os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    fb_token = os.environ.get("FB_ACCESS_TOKEN_TECH") or os.environ.get("FB_PAGE_ACCESS_TOKEN") or os.environ.get("FB_ACCESS_TOKEN")
    fb_page_id = os.environ.get("FB_PAGE_ID")
    tg_bot = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not ig_biz_id or not fb_token:
        print("❌ Missing Instagram Meta Graph API credentials in .env")
        sys.exit(1)
    if not tg_bot or not tg_chat:
        print("❌ Missing Telegram credentials in .env")
        sys.exit(1)
        
    caption = (
        "🚀 Live Meta Graph API Integration Verification Video!\n\n"
        "🤖 Automated 9:16 vertical tech reel generated & published using Remotion + Meta Graph API.\n\n"
        "#remotion #meta #instagramreels #automation #tech #neonnode"
    )
    
    status_report = []
    
    # 1. Instagram Reels Publish via Meta Graph API
    print("\n--------------------------------------------------")
    print("Step 1: Publishing 9:16 Reel to Instagram via Meta Graph API...")
    print("--------------------------------------------------")
    
    ig_media_id = None
    try:
        ig_media_id = post_to_instagram_official(
            video_url=test_video,
            caption=caption,
            business_account_id=ig_biz_id,
            access_token=fb_token,
            session_id=session_id
        )
        status_report.append(f"• Instagram Reel (Meta Graph API): ✅ Published (Media ID: {ig_media_id})")
        print(f"✅ Instagram Reel Live! Media ID: {ig_media_id}")

    except Exception as ex:
        print(f"❌ Instagram Reel failed: {ex}")
        status_report.append(f"• Instagram Reel (Meta Graph API): ❌ Failed ({ex})")

    # 2. Facebook Page Reels Publish via Meta Graph API
    if fb_page_id:
        print("\n--------------------------------------------------")
        print("Step 2: Publishing Reel to Facebook Page via Meta Graph API...")
        print("--------------------------------------------------")
        try:
            page_token = _resolve_fb_page_token(fb_page_id, fb_token, session_id=session_id)
            fb_video_id = post_to_facebook_reel(
                video_path_or_url=test_video,
                description=caption,
                page_id=fb_page_id,
                access_token=page_token,
                session_id=session_id,
                hosted_fallback_url=None,
                video_state="PUBLISHED"
            )

            status_report.append(f"• Facebook Page Reel (Meta Graph API): ✅ Published (Video ID: {fb_video_id})")
            print(f"✅ Facebook Page Reel Live! Video ID: {fb_video_id}")
        except Exception as ex:
            print(f"❌ Facebook Reel failed: {ex}")
            status_report.append(f"• Facebook Page Reel (Meta Graph API): ❌ {ex}")

    # 3. Telegram Video Delivery & Report
    print("\n--------------------------------------------------")
    print("Step 3: Delivering Video & Status Report to Telegram...")
    print("--------------------------------------------------")
    
    tg_caption = "🎬 AI Video Generation & Publishing Test Complete!\n\n🚀 Meta Graph API Deployment Report:\n"
    tg_caption += "\n".join(status_report) + "\n\n📝 Caption:\n" + caption
    
    tg_success = post_to_telegram(
        video_path_or_url=test_video,
        caption=tg_caption,
        bot_token=tg_bot,
        chat_id=tg_chat,
        session_id=session_id
    )
    
    if tg_success:
        print(f"✅ Telegram Video Delivery Successful! Sent to Chat ID: {tg_chat}")
    else:
        print(f"❌ Telegram delivery failed.")

    print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Quick End-to-End Test Finished Successfully!{Colors.RESET}\n")

if __name__ == "__main__":
    run_quick_test()
