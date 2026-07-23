#!/usr/bin/env python3
"""
Meta Graph API Comprehensive Test & Diagnostics Module
======================================================
A complete, standalone test harness for validating and experimenting with Meta Graph API
endpoints (Instagram Professional/Business Accounts & Facebook Pages).

This module enables you to test all Graph API workflows—token debugging, account inspection,
Instagram Reels publishing, Facebook Page Reels uploading, media insights, token exchange,
and proxy verification—before or alongside main system integration.

Features:
  - Token & Permission Inspector (/debug_token, /me, /me/accounts)
  - Instagram Business Account Profile & Recent Media Query
  - Facebook Page Profile & Videos Query
  - Instagram Reels Container Creation & Status Polling (Dry-Run & Full Publish)
  - Facebook Page Reels Upload Pipeline (Start -> Binary Upload -> Finish as DRAFT/PUBLISHED -> Poll Status)
  - Instagram & Facebook Media Insights Fetcher
  - Long-Lived Token & Non-Expiring Page Token Exchange Wizard
  - Cloudflare Worker / Custom Proxy Connectivity Test
  - Dual Mode: Interactive Console UI & Scriptable CLI Flags

Usage:
  python test_meta_graph_api.py                     # Interactive menu mode
  python test_meta_graph_api.py --inspect           # Inspect token, IG account, & FB pages
  python test_meta_graph_api.py --ig-profile        # Detailed Instagram account & recent media audit
  python test_meta_graph_api.py --fb-profile        # Detailed Facebook Page audit
  python test_meta_graph_api.py --test-ig-reel      # Test IG Reel upload (dry-run container check)
  python test_meta_graph_api.py --test-fb-reel      # Test FB Reel upload (as DRAFT)
  python test_meta_graph_api.py --test-insights     # Test fetching insights for recent media
  python test_meta_graph_api.py --exchange-token    # Long-Lived Token Exchange Wizard
  python test_meta_graph_api.py --all               # Run all non-destructive diagnostics
"""

import sys
import os
import time
import json
import argparse
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# -----------------------------------------------------------------------------
# Terminal Styling & Formatting Helpers
# -----------------------------------------------------------------------------
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

def print_header(title: str):
    width = 70
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * width}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  {title}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * width}{Colors.RESET}")

def print_success(msg: str):
    print(f"{Colors.GREEN}{Colors.BOLD}[✓ SUCCESS]{Colors.RESET} {msg}")

def print_error(msg: str):
    print(f"{Colors.RED}{Colors.BOLD}[✗ ERROR]{Colors.RESET} {msg}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}{Colors.BOLD}[! WARNING]{Colors.RESET} {msg}")

def print_info(msg: str):
    print(f"{Colors.BLUE}[i INFO]{Colors.RESET} {msg}")

def print_substep(msg: str):
    print(f"{Colors.DIM}  ➔ {msg}{Colors.RESET}")

# -----------------------------------------------------------------------------
# Environment & Configuration Reader
# -----------------------------------------------------------------------------
def load_env_file(env_path: str = ".env"):
    """Lightweight .env loader (no external dependencies required)."""
    p = Path(env_path)
    if not p.exists():
        return
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = val

load_env_file()

def resolve_meta_config() -> Dict[str, str]:
    """Resolves Meta Graph API credentials from environment variables."""
    # Access Token priority: FB_PAGE_ACCESS_TOKEN -> FB_ACCESS_TOKEN_TECH -> FB_ACCESS_TOKEN -> INSTAGRAM_ACCESS_TOKEN -> META_ACCESS_TOKEN
    access_token = (
        os.environ.get("FB_PAGE_ACCESS_TOKEN") or
        os.environ.get("FB_ACCESS_TOKEN_TECH") or
        os.environ.get("FB_ACCESS_TOKEN") or
        os.environ.get("FB_ACCESS_TOKEN_NEWS") or
        os.environ.get("INSTAGRAM_ACCESS_TOKEN") or
        os.environ.get("META_ACCESS_TOKEN") or ""
    ).strip()

    # IG Business Account ID priority: INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID -> INSTAGRAM_NEWS_BUSINESS_ACCOUNT_ID -> INSTAGRAM_BUSINESS_ACCOUNT_ID -> IG_USER_ID
    ig_account_id = (
        os.environ.get("INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID") or
        os.environ.get("INSTAGRAM_NEWS_BUSINESS_ACCOUNT_ID") or
        os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID") or
        os.environ.get("IG_USER_ID") or ""
    ).strip()

    # FB Page ID
    fb_page_id = (
        os.environ.get("FB_PAGE_ID") or ""
    ).strip()

    # API Base & Graph Version
    api_base = os.environ.get("INSTAGRAM_API_BASE_URL", "https://graph.facebook.com").strip().rstrip("/")
    graph_version = os.environ.get("FB_GRAPH_VERSION", "v21.0").strip()

    return {
        "access_token": access_token,
        "ig_account_id": ig_account_id,
        "fb_page_id": fb_page_id,
        "api_base": api_base,
        "graph_version": graph_version
    }

# -----------------------------------------------------------------------------
# Network & Graph API HTTP Client (curl-based matching main.py)
# -----------------------------------------------------------------------------
def make_curl_request(
    url: str,
    method: str = "GET",
    form_data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    data_binary: Optional[str] = None,
    timeout: int = 60,
    insecure: bool = False
) -> Dict[str, Any]:
    """Executes Graph API requests via curl subprocess.
    
    This matches the main system's curl transport, bypassing Python TLS EOF issues
    with Meta servers and supporting custom proxy target headers.
    """
    cmd = ["curl", "-sS", "-X", method.upper(), "--max-time", str(timeout)]
    
    # TLS flags matching main.py
    cmd += ["--tlsv1.2", "--retry", "2", "--retry-delay", "3", "--retry-connrefused"]
    if insecure:
        cmd.append("--insecure")
        
    if headers:
        for hk, hv in headers.items():
            cmd += ["-H", f"{hk}: {hv}"]
            
    if form_data:
        for fk, fv in form_data.items():
            cmd += ["--form-string", f"{fk}={fv}"]
            
    if data_binary:
        cmd += ["--data-binary", data_binary]
        
    cmd.append(url)
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
        if res.returncode != 0:
            # Exit code 35 = OpenSSL TLS connect/EOF error -> retry once with --insecure
            if res.returncode == 35 and not insecure:
                print_substep("OpenSSL TLS handshake issue (exit 35). Retrying with --insecure flag...")
                return make_curl_request(url, method, form_data, headers, data_binary, timeout, insecure=True)
            return {"error": {"message": f"curl command failed (exit code {res.returncode}): {res.stderr.strip()}"}}
            
        out_str = res.stdout.strip()
        if not out_str:
            return {"error": {"message": "Empty response received from Meta Graph API"}}
            
        try:
            return json.loads(out_str)
        except json.JSONDecodeError:
            return {"raw_response": out_str, "error": {"message": "Non-JSON response received"}}
            
    except subprocess.TimeoutExpired:
        return {"error": {"message": f"Request timed out after {timeout} seconds"}}
    except Exception as e:
        return {"error": {"message": f"Execution error: {e}"}}

# -----------------------------------------------------------------------------
# Diagnostic Module 1: Token & Permission Inspector
# -----------------------------------------------------------------------------
def inspect_token_and_permissions(config: Dict[str, str]) -> bool:
    """Inspects Access Token validity, user identity, permissions, and linked accounts."""
    print_header("MODULE 1: TOKEN & PERMISSION INSPECTOR")
    
    token = config["access_token"]
    api_base = config["api_base"]
    ver = config["graph_version"]
    
    if not token:
        print_error("No Access Token found! Please set FB_PAGE_ACCESS_TOKEN or FB_ACCESS_TOKEN in .env or pass --token")
        return False
        
    print_info(f"Using Graph API Version: {ver}")
    print_info(f"Target API Endpoint: {api_base}")
    print_info(f"Access Token Prefix: {token[:12]}...{token[-6:]}")
    
    # 1. Query /me to get Basic Identity (works for both User Tokens and Page Tokens)
    me_url = f"{api_base}/{ver}/me?fields=id,name&access_token={urllib.parse.quote(token)}"
    me_res = make_curl_request(me_url)
    
    if "error" in me_res:
        err = me_res["error"]
        print_error(f"Failed to query /me: {err.get('message', err)}")
        _diagnose_error(err)
        return False
        
    user_id = me_res.get("id", "Unknown")
    user_name = me_res.get("name", "Unknown")
    print_success(f"Token Authenticated as User/Page: '{user_name}' (ID: {user_id})")
    
    # 2. Query /me/permissions safely (Page tokens can skip permissions field)
    perm_url = f"{api_base}/{ver}/me/permissions?access_token={urllib.parse.quote(token)}"
    perm_res = make_curl_request(perm_url)
    perms = perm_res.get("data", []) if isinstance(perm_res, dict) else []
    granted_perms = [p["permission"] for p in perms if p.get("status") == "granted"]
    declined_perms = [p["permission"] for p in perms if p.get("status") == "declined"]
    
    print("\n" + Colors.BOLD + "Granted Permissions Scopes:" + Colors.RESET)
    required_scopes = {
        "instagram_basic": "Read IG Account Info & Media",
        "instagram_content_publish": "Publish Reels/Posts to IG Business",
        "pages_show_list": "List Facebook Pages",
        "pages_read_engagement": "Read Page engagement/insights",
        "pages_manage_posts": "Manage & Post to Facebook Pages",
        "publish_video": "Upload Facebook Reels/Videos"
    }
    
    if granted_perms:
        for scope, desc in required_scopes.items():
            if scope in granted_perms:
                print(f"  {Colors.GREEN}[✓ GRANTED]{Colors.RESET}  {scope:<28} ({desc})")
            else:
                print(f"  {Colors.YELLOW}[! UNCHECKED]{Colors.RESET}  {scope:<28} ({desc})")
    else:
        print_info("Operating with a direct Page Access Token (Page tokens inherit assigned Page permissions).")
            
    if declined_perms:
        print_warning(f"Declined Permissions: {', '.join(declined_perms)}")

        
    # 2. Query /me/accounts to find Facebook Pages & Connected Instagram Accounts
    accounts_url = f"{api_base}/{ver}/me/accounts?fields=id,name,category,access_token,instagram_business_account&access_token={urllib.parse.quote(token)}"
    acc_res = make_curl_request(accounts_url)
    
    print("\n" + Colors.BOLD + "Connected Facebook Pages & IG Accounts:" + Colors.RESET)
    pages = acc_res.get("data", [])
    if not pages:
        print_warning("No Facebook Pages found linked to this token via /me/accounts.")
        print_info("Note: If using a Page Access Token directly, /me/accounts will be empty.")
    else:
        for p in pages:
            p_id = p.get("id")
            p_name = p.get("name")
            ig_biz = p.get("instagram_business_account", {})
            ig_id = ig_biz.get("id") if isinstance(ig_biz, dict) else None
            
            print(f"  • Page: {Colors.BOLD}{p_name}{Colors.RESET} (ID: {p_id})")
            if ig_id:
                print(f"    └── Linked IG Business Account ID: {Colors.GREEN}{Colors.BOLD}{ig_id}{Colors.RESET}")
            else:
                print(f"    └── {Colors.DIM}No IG Business Account linked to this page{Colors.RESET}")
                
    return True

# -----------------------------------------------------------------------------
# Diagnostic Module 2: Instagram Business Account Inspector
# -----------------------------------------------------------------------------
def inspect_instagram_account(config: Dict[str, str]) -> bool:
    """Queries detailed profile metadata and recent posts for an Instagram Business Account."""
    print_header("MODULE 2: INSTAGRAM BUSINESS ACCOUNT INSPECTOR")
    
    token = config["access_token"]
    ig_id = config["ig_account_id"]
    api_base = config["api_base"]
    ver = config["graph_version"]
    
    if not ig_id:
        print_error("No Instagram Business Account ID configured! Set INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID in .env or pass --ig-id")
        return False
        
    print_info(f"Target IG Business Account ID: {ig_id}")
    
    # 1. Fetch Account Details
    fields = "id,name,username,profile_picture_url,followers_count,follows_count,media_count,biography"
    url = f"{api_base}/{ver}/{ig_id}?fields={fields}&access_token={urllib.parse.quote(token)}"
    res = make_curl_request(url)
    
    if "error" in res:
        err = res["error"]
        print_error(f"Failed to query IG Account ({ig_id}): {err.get('message', err)}")
        _diagnose_error(err)
        return False
        
    username = res.get("username", "Unknown")
    name = res.get("name", "Unknown")
    followers = res.get("followers_count", 0)
    media_cnt = res.get("media_count", 0)
    bio = res.get("biography", "").replace("\n", " ")
    
    print_success(f"Instagram Account Found: @{username} ({name})")
    print(f"  • Account ID:       {ig_id}")
    print(f"  • Followers:        {followers:,}")
    print(f"  • Total Media Posts:{media_cnt:,}")
    print(f"  • Bio:              {bio[:80]}...")
    
    # 2. Fetch Recent Media Items
    media_fields = "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count"
    media_url = f"{api_base}/{ver}/{ig_id}/media?fields={media_fields}&limit=5&access_token={urllib.parse.quote(token)}"
    m_res = make_curl_request(media_url)
    
    posts = m_res.get("data", [])
    print("\n" + Colors.BOLD + f"Recent Instagram Posts (Top {len(posts)}):" + Colors.RESET)
    if not posts:
        print_info("No recent media items found on this account.")
    else:
        for idx, post in enumerate(posts, 1):
            m_id = post.get("id")
            m_type = post.get("media_type")
            likes = post.get("like_count", 0)
            comments = post.get("comments_count", 0)
            caption = (post.get("caption") or "").replace("\n", " ")[:60]
            permalink = post.get("permalink", "")
            ts = post.get("timestamp", "")[:10]
            
            print(f"  {idx}. [{m_type}] {ts} - ID: {m_id}")
            print(f"     Caption: \"{caption}\"")
            print(f"     Stats:   ❤️ {likes} likes | 💬 {comments} comments")
            print(f"     URL:     {permalink}")
            
    return True

# -----------------------------------------------------------------------------
# Diagnostic Module 3: Facebook Page Profile Inspector
# -----------------------------------------------------------------------------
def inspect_facebook_page(config: Dict[str, str]) -> bool:
    """Queries detailed Facebook Page details and published video list."""
    print_header("MODULE 3: FACEBOOK PAGE INSPECTOR")
    
    token = config["access_token"]
    page_id = config["fb_page_id"]
    api_base = config["api_base"]
    ver = config["graph_version"]
    
    if not page_id:
        print_error("No Facebook Page ID configured! Set FB_PAGE_ID in .env or pass --page-id")
        return False
        
    print_info(f"Target Facebook Page ID: {page_id}")
    
    # 1. Fetch Page Details
    fields = "id,name,category,followers_count,fan_count,link"
    url = f"{api_base}/{ver}/{page_id}?fields={fields}&access_token={urllib.parse.quote(token)}"
    res = make_curl_request(url)
    
    if "error" in res:
        err = res["error"]
        print_error(f"Failed to query FB Page ({page_id}): {err.get('message', err)}")
        _diagnose_error(err)
        return False
        
    name = res.get("name", "Unknown")
    category = res.get("category", "Unknown")
    followers = res.get("followers_count", res.get("fan_count", 0))
    link = res.get("link", "")
    
    print_success(f"Facebook Page Found: '{name}'")
    print(f"  • Page ID:     {page_id}")
    print(f"  • Category:    {category}")
    print(f"  • Followers:   {followers:,}")
    print(f"  • Page URL:    {link}")
    
    # 2. Fetch Page Published Videos/Reels
    video_url = f"{api_base}/{ver}/{page_id}/videos?fields=id,description,created_time,published&limit=5&access_token={urllib.parse.quote(token)}"
    v_res = make_curl_request(video_url)
    
    videos = v_res.get("data", [])
    print("\n" + Colors.BOLD + f"Recent Page Videos/Reels (Top {len(videos)}):" + Colors.RESET)
    if not videos:
        print_info("No videos found on this Facebook Page.")
    else:
        for idx, vid in enumerate(videos, 1):
            v_id = vid.get("id")
            desc = (vid.get("description") or "").replace("\n", " ")[:60]
            created = vid.get("created_time", "")[:10]
            pub = vid.get("published", True)
            status_str = "Published" if pub else "Draft/Unpublished"
            print(f"  {idx}. [{status_str}] {created} - Video ID: {v_id}")
            print(f"     Desc: \"{desc}\"")
            
    return True

# -----------------------------------------------------------------------------
# Diagnostic Module 4: Instagram Reels Upload & Publishing Test
# -----------------------------------------------------------------------------
def test_instagram_reels_flow(
    config: Dict[str, str],
    video_url_or_path: Optional[str] = None,
    caption: str = "🚀 Testing Meta Graph API Reel Publishing pipeline! #test #meta #api",
    publish: bool = False
) -> bool:
    """Tests the 3-step Instagram Reels container & publishing pipeline.
    
    If publish=False (default), runs in DRY-RUN mode: creates container and polls status
    until FINISHED, validating that Meta's servers accept and process the video, but skips
    the final media_publish call to prevent test clutter.
    """
    print_header("MODULE 4: INSTAGRAM REELS PUBLISHING TEST")
    
    token = config["access_token"]
    ig_id = config["ig_account_id"]
    api_base = config["api_base"]
    ver = config["graph_version"]
    
    if not ig_id or not token:
        print_error("Missing IG Account ID or Access Token. Cannot test Instagram Reels upload.")
        return False
        
    video_url = _resolve_test_video_url(video_url_or_path)
    if not video_url:
        print_error("Could not resolve a valid public video URL for Instagram Reels container creation.")
        print_info("Instagram Graph API requires a publicly accessible HTTP/HTTPS video URL (e.g. hosted on your server, S3, or Cloudflare).")
        return False
        
    mode_str = "FULL PUBLISH" if publish else "DRY-RUN (Container Check & Poll only)"
    print_info(f"Execution Mode: {Colors.BOLD}{mode_str}{Colors.RESET}")
    print_info(f"Target IG Account ID: {ig_id}")
    print_info(f"Video Source URL: {video_url[:80]}...")
    
    # Step 1: Create Container
    print_substep("Step 1: Creating Instagram Reel Container...")
    container_url = f"{api_base}/{ver}/{ig_id}/media"
    form_data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": token
    }
    
    data = make_curl_request(container_url, method="POST", form_data=form_data, timeout=120)
    if "error" in data:
        print_error(f"Container Creation Failed: {data['error'].get('message', data)}")
        _diagnose_error(data["error"])
        return False
        
    container_id = data.get("id")
    if not container_id:
        print_error(f"No container ID returned in response: {data}")
        return False
        
    print_success(f"Container created successfully! Container ID: {container_id}")
    
    # Step 2: Poll Container Status until FINISHED
    print_substep("Step 2: Polling Container Processing Status (up to 12 minutes)...")
    max_polls = 48
    finished = False
    
    for poll in range(1, max_polls + 1):
        time.sleep(10)
        status_url = f"{api_base}/{ver}/{container_id}?fields=status_code,status&access_token={urllib.parse.quote(token)}"
        s_data = make_curl_request(status_url, timeout=30)
        
        if "error" in s_data:
            print_warning(f"Poll {poll}/{max_polls} API request error: {s_data['error'].get('message', s_data)}")
            continue
            
        status_code = s_data.get("status_code")
        print_substep(f"Poll {poll}/{max_polls}: Container Status = {Colors.BOLD}{status_code}{Colors.RESET}")
        
        if status_code == "FINISHED":
            finished = True
            break
        elif status_code == "ERROR":
            print_error(f"Container processing failed on Meta's servers: {s_data}")
            return False
            
    if not finished:
        print_error("Timed out waiting for container to reach FINISHED state.")
        return False
        
    print_success("Container processed and READY on Meta servers!")
    
    # Step 3: Publish Container (if requested)
    if not publish:
        print_success("DRY-RUN COMPLETE! Instagram Reel container creation and status polling succeeded.")
        print_info("To publish publicly, run with --publish flag.")
        return True
        
    print_substep("Step 3: Executing media_publish to post Reel to Instagram...")
    pub_url = f"{api_base}/{ver}/{ig_id}/media_publish"
    pub_data = {
        "creation_id": container_id,
        "access_token": token
    }
    
    p_res = make_curl_request(pub_url, method="POST", form_data=pub_data, timeout=60)
    if "error" in p_res:
        print_error(f"Failed to publish container: {p_res['error'].get('message', p_res)}")
        return False
        
    published_media_id = p_res.get("id")
    print_success(f"REEL PUBLISHED LIVE! Instagram Media ID: {published_media_id}")
    return True

# -----------------------------------------------------------------------------
# Diagnostic Module 5: Facebook Page Reels Upload Test
# -----------------------------------------------------------------------------
def test_facebook_reels_flow(
    config: Dict[str, str],
    video_path_or_url: Optional[str] = None,
    description: str = "🎬 Testing Meta Graph API Facebook Reel upload pipeline! #test #reels",
    publish: bool = False
) -> bool:
    """Tests the official 4-phase Facebook Page Reels upload pipeline:
    Start Session -> Upload Video Payload -> Finish as DRAFT/PUBLISHED -> Poll Status.
    """
    print_header("MODULE 5: FACEBOOK PAGE REELS UPLOAD TEST")
    
    token = config["access_token"]
    page_id = config["fb_page_id"]
    api_base = config["api_base"]
    ver = config["graph_version"]
    
    if not page_id or not token:
        print_error("Missing Facebook Page ID or Access Token. Cannot test FB Reels upload.")
        return False
        
    target_state = "PUBLISHED" if publish else "DRAFT"
    print_info(f"Target Page ID: {page_id}")
    print_info(f"Target Video State: {Colors.BOLD}{target_state}{Colors.RESET}")
    
    # Find local video file or URL
    local_file, remote_url = _resolve_test_video_sources(video_path_or_url)
    if not local_file and not remote_url:
        print_error("No video file or hosted URL found for Facebook Reels upload test.")
        return False
        
    proxied = "graph.facebook.com" not in api_base
    
    # Phase 1: Start Upload Session
    print_substep("Phase 1: Initializing Facebook Reels Upload Session...")
    start_url = f"{api_base}/{ver}/{page_id}/video_reels"
    start_data = {
        "upload_phase": "start",
        "access_token": token
    }
    
    s_res = make_curl_request(start_url, method="POST", form_data=start_data, timeout=60)
    if "error" in s_res or not s_res.get("video_id"):
        err = s_res.get("error", s_res)
        print_error(f"Phase 1 (Start) Failed: {err.get('message', err) if isinstance(err, dict) else err}")
        _diagnose_error(err if isinstance(err, dict) else {})
        return False
        
    video_id = s_res["video_id"]
    print_success(f"Upload session initialized! Video ID: {video_id}")
    
    # Phase 2: Binary / URL Upload
    upload_url = (f"{api_base}/video-upload/{ver}/{video_id}" if proxied
                  else f"https://rupload.facebook.com/video-upload/{ver}/{video_id}")
                  
    headers = {"Authorization": f"OAuth {token}"}
    if proxied:
        headers["x-target-domain"] = "rupload.facebook.com"
        
    uploaded = False
    if local_file and os.path.exists(local_file):
        file_size = os.path.getsize(local_file)
        print_substep(f"Phase 2: Uploading local binary file ({file_size:,} bytes)...")
        headers["offset"] = "0"
        headers["file_size"] = str(file_size)
        
        u_res = make_curl_request(
            upload_url,
            method="POST",
            headers=headers,
            data_binary=f"@{local_file}",
            timeout=300
        )
        if u_res.get("success"):
            uploaded = True
            print_success("Local binary upload accepted by Facebook rupload servers!")
        else:
            print_warning(f"Binary upload response: {u_res}")
            
    if not uploaded and remote_url:
        print_substep(f"Phase 2 (Fallback): Uploading via hosted file URL ({remote_url[:60]}...)...")
        headers["file_url"] = remote_url
        u_res = make_curl_request(upload_url, method="POST", headers=headers, timeout=120)
        if u_res.get("success"):
            uploaded = True
            print_success("Hosted file URL upload accepted by Facebook servers!")
        else:
            print_error(f"Hosted file URL upload failed: {u_res}")
            return False
            
    if not uploaded:
        print_error("Failed to upload video binary or hosted URL.")
        return False
        
    # Phase 3: Finish Session
    print_substep(f"Phase 3: Finishing Reel Upload (Setting video_state={target_state})...")
    finish_data = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": target_state,
        "description": description,
        "access_token": token
    }
    
    f_res = make_curl_request(start_url, method="POST", form_data=finish_data, timeout=120)
    if "error" in f_res:
        print_error(f"Phase 3 (Finish) Failed: {f_res['error'].get('message', f_res)}")
        return False
        
    print_success("Reel upload phase FINISHED successfully!")
    
    # Phase 4: Poll Status
    print_substep("Phase 4: Polling Reel processing status on Facebook Page...")
    for poll in range(1, 49):
        time.sleep(10)
        poll_url = f"{api_base}/{ver}/{video_id}?fields=status&access_token={urllib.parse.quote(token)}"
        p_res = make_curl_request(poll_url, timeout=30)
        
        status_obj = p_res.get("status", {})
        video_status = status_obj.get("video_status")
        proc_status = (status_obj.get("processing_phase") or {}).get("status")
        pub_status = (status_obj.get("publishing_phase") or {}).get("status")
        
        print_substep(f"Poll {poll}/48: video_status={Colors.BOLD}{video_status}{Colors.RESET} | processing={proc_status} | publishing={pub_status}")
        
        if video_status == "error":
            print_error(f"Facebook Reel processing failed: {p_res}")
            return False
            
        if video_status in ("ready", "published") or pub_status == "complete":
            print_success(f"FACEBOOK REEL IS LIVE ON PAGE! Video ID: {video_id}")
            return True
            
        if target_state == "DRAFT" and proc_status == "complete":
            print_success(f"FACEBOOK DRAFT REEL PROCESSED & READY IN CREATOR STUDIO! Video ID: {video_id}")
            return True
            
    print_error("Timed out polling Facebook Reel status.")
    return False

# -----------------------------------------------------------------------------
# Diagnostic Module 6: Insights & Analytics Retrieval Test
# -----------------------------------------------------------------------------
def fetch_media_insights(config: Dict[str, str]) -> bool:
    """Tests retrieving Instagram Media Insights & Analytics metrics."""
    print_header("MODULE 6: MEDIA INSIGHTS & ANALYTICS TEST")
    
    token = config["access_token"]
    ig_id = config["ig_account_id"]
    api_base = config["api_base"]
    ver = config["graph_version"]
    
    if not ig_id or not token:
        print_error("Missing IG Account ID or Access Token. Cannot fetch insights.")
        return False
        
    # 1. Fetch recent media list to pick a post
    media_url = f"{api_base}/{ver}/{ig_id}/media?fields=id,caption,media_type,timestamp&limit=3&access_token={urllib.parse.quote(token)}"
    m_res = make_curl_request(media_url)
    
    posts = m_res.get("data", [])
    if not posts:
        print_warning("No recent media items found to query insights for.")
        return False
        
    target_post = posts[0]
    m_id = target_post.get("id")
    m_type = target_post.get("media_type")
    
    print_info(f"Targeting Recent Media ID: {m_id} ({m_type})")
    
    # 2. Query Media Insights
    # Metrics differ by media type
    if m_type == "REELS":
        metrics = "views,reach,total_interactions,likes,comments,shares,saved"
    else:
        metrics = "impressions,reach,engagement,saved"
        
    insights_url = f"{api_base}/{ver}/{m_id}/insights?metric={metrics}&access_token={urllib.parse.quote(token)}"
    i_res = make_curl_request(insights_url)
    
    if "error" in i_res:
        err = i_res["error"]
        print_error(f"Failed to fetch insights for media {m_id}: {err.get('message', err)}")
        _diagnose_error(err)
        return False
        
    print_success(f"Insights Retrieved for Media {m_id}:")
    for metric_item in i_res.get("data", []):
        m_name = metric_item.get("name")
        m_val = metric_item.get("values", [{}])[0].get("value", 0)
        title = metric_item.get("title", m_name)
        print(f"  • {title:<25}: {Colors.BOLD}{m_val:,}{Colors.RESET}")
        
    return True

# -----------------------------------------------------------------------------
# Diagnostic Module 7: Cloudflare Proxy Worker Connectivity Test
# -----------------------------------------------------------------------------
def test_proxy_connection(config: Dict[str, str]) -> bool:
    """Verifies connection to custom Cloudflare Worker proxy endpoint if configured."""
    print_header("MODULE 7: CLOUDFLARE PROXY WORKER CONNECTIVITY")
    
    api_base = config["api_base"]
    if "graph.facebook.com" in api_base:
        print_info("INSTAGRAM_API_BASE_URL is pointing directly to Meta's graph.facebook.com (No Proxy in use).")
        print_info("If you deploy worker.js to Cloudflare, set INSTAGRAM_API_BASE_URL=https://your-worker.workers.dev to use the proxy.")
        return True
        
    print_info(f"Testing Proxy Connection to: {Colors.BOLD}{api_base}{Colors.RESET}")
    
    # Test lightweight GET request through proxy
    test_url = f"{api_base}/v21.0/me"
    res = make_curl_request(test_url, timeout=15)
    
    if "error" in res:
        err_msg = res["error"].get("message", str(res["error"]))
        if "OAuth" in err_msg or "token" in err_msg.lower() or "An access token is required" in err_msg:
            print_success(f"Proxy is LIVE & reachable! (Proxy forwarded Meta Graph API error response cleanly)")
            return True
        else:
            print_error(f"Proxy request failed: {err_msg}")
            return False
            
    print_success(f"Proxy response received successfully from {api_base}")
    return True

# -----------------------------------------------------------------------------
# Interactive Long-Lived Token Exchange Wizard
# -----------------------------------------------------------------------------
def exchange_token_wizard():
    """Interactive guided tool to generate a 60-day Long-Lived User Token & Non-Expiring Page Access Token."""
    print_header("TOKEN EXCHANGE WIZARD")
    
    print("This wizard helps you convert a short-lived User Access Token (from Graph API Explorer)")
    print("into a 60-day Long-Lived User Token and a Never-Expiring Page Access Token.\n")
    
    app_id = input(f"{Colors.BOLD}Enter Meta App ID (from Meta Developer Portal): {Colors.RESET}").strip()
    app_secret = input(f"{Colors.BOLD}Enter Meta App Secret: {Colors.RESET}").strip()
    short_token = input(f"{Colors.BOLD}Enter Short-Lived User Access Token: {Colors.RESET}").strip()
    
    if not app_id or not app_secret or not short_token:
        print_error("App ID, App Secret, and Short Token are required for exchange.")
        return
        
    print_substep("Step 1: Exchanging Short-Lived Token for 60-Day Long-Lived User Token...")
    exchange_url = (
        f"https://graph.facebook.com/v21.0/oauth/access_token"
        f"?grant_type=fb_exchange_token"
        f"&client_id={app_id}"
        f"&client_secret={app_secret}"
        f"&fb_exchange_token={short_token}"
    )
    
    res = make_curl_request(exchange_url)
    if "error" in res:
        print_error(f"Token Exchange Failed: {res['error'].get('message', res)}")
        return
        
    long_user_token = res.get("access_token")
    expires_in = res.get("expires_in", 0)
    days = expires_in // 86400 if expires_in else 60
    
    print_success(f"60-Day Long-Lived User Access Token Generated! (Expires in ~{days} days)")
    print(f"\n{Colors.GREEN}{long_user_token}{Colors.RESET}\n")
    
    print_substep("Step 2: Deriving Non-Expiring Page Access Token(s)...")
    accounts_url = f"https://graph.facebook.com/v21.0/me/accounts?fields=id,name,access_token,instagram_business_account&access_token={long_user_token}"
    acc_res = make_curl_request(accounts_url)
    
    pages = acc_res.get("data", [])
    if not pages:
        print_warning("No Facebook Pages found associated with this user token.")
        return
        
    print_success(f"Found {len(pages)} Facebook Page(s) with Non-Expiring Page Tokens:\n")
    for p in pages:
        p_name = p.get("name")
        p_id = p.get("id")
        p_token = p.get("access_token")
        ig_biz = p.get("instagram_business_account", {})
        ig_id = ig_biz.get("id") if isinstance(ig_biz, dict) else "None"
        
        print(f"📌 {Colors.BOLD}Page: {p_name}{Colors.RESET} (ID: {p_id})")
        print(f"   Linked IG Account ID: {ig_id}")
        print(f"   FB_PAGE_ACCESS_TOKEN: {Colors.CYAN}{p_token}{Colors.RESET}\n")

# -----------------------------------------------------------------------------
# Internal Diagnostic Helpers & Resolvers
# -----------------------------------------------------------------------------
def _diagnose_error(err_dict: Dict[str, Any]):
    """Prints actionable diagnostic advice for common Meta Graph API error codes."""
    if not isinstance(err_dict, dict):
        return
    code = err_dict.get("code")
    subcode = err_dict.get("error_subcode")
    msg = err_dict.get("message", "")
    
    print("\n" + Colors.YELLOW + Colors.BOLD + "💡 DIAGNOSTIC & FIX ADVICE:" + Colors.RESET)
    
    if code == 190:
        print("  • Issue: Invalid or Expired OAuth Access Token.")
        print("  • Solution: Generate a new token from Graph API Explorer or run `python test_meta_graph_api.py --exchange-token`.")
    elif code == 200 or code == 10:
        print("  • Issue: Missing Granted Permission or Scope.")
        print("  • Solution: Ensure your token has `instagram_content_publish`, `pages_manage_posts`, and `publish_video` granted.")
    elif code == 100 and "business" in msg.lower():
        print("  • Issue: Invalid Instagram Business Account ID.")
        print("  • Solution: Verify your Instagram account is converted to a Professional/Business Account and linked to your Facebook Page.")
    elif "age" in msg.lower() or "week" in msg.lower() or "restricted" in msg.lower():
        print("  • Issue: Account restriction / Account age limitation.")
        print("  • Solution: Meta enforces a 7-day cooldown on brand new Business accounts before enabling API posting capabilities.")
    else:
        print(f"  • Code: {code} | Subcode: {subcode}")
        print(f"  • Detail: {msg}")

def _resolve_test_video_url(url_or_path: Optional[str]) -> Optional[str]:
    """Resolves a valid HTTP/HTTPS URL for Instagram container creation."""
    if url_or_path and url_or_path.startswith(("http://", "https://")):
        return url_or_path
    # Public sample fallback URL for testing if no URL provided
    return os.environ.get("TEST_VIDEO_URL", "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/freeheadmovement.mp4")

def _resolve_test_video_sources(url_or_path: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Resolves (local_file_path, remote_url) for Facebook Reels upload."""
    local_file = None
    remote_url = None
    
    if url_or_path:
        if url_or_path.startswith(("http://", "https://")):
            remote_url = url_or_path
        elif os.path.exists(url_or_path):
            local_file = url_or_path
            
    if not local_file:
        # Search public/ directory for existing mp4 files
        public_dir = Path("public")
        if public_dir.exists():
            mp4s = list(public_dir.glob("*.mp4"))
            if mp4s:
                local_file = str(mp4s[0])
                print_info(f"Auto-selected local test video file: {local_file}")
                
    if not remote_url:
        remote_url = os.environ.get("TEST_VIDEO_URL", "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/freeheadmovement.mp4")
        
    return local_file, remote_url

# -----------------------------------------------------------------------------
# Interactive Menu UI
# -----------------------------------------------------------------------------
def run_interactive_menu():
    """Renders the main interactive console menu for testing Meta Graph API."""
    config = resolve_meta_config()
    
    while True:
        print_header("META GRAPH API INTERACTIVE TEST HARNESS")
        print(f"Configured Credentials:")
        print(f"  • Token:       {'Configured (' + config['access_token'][:10] + '...)' if config['access_token'] else Colors.RED + 'MISSING' + Colors.RESET}")
        print(f"  • IG Account:  {config['ig_account_id'] or Colors.YELLOW + 'Not set' + Colors.RESET}")
        print(f"  • FB Page ID:  {config['fb_page_id'] or Colors.YELLOW + 'Not set' + Colors.RESET}")
        print(f"  • API Base:    {config['api_base']}")
        print(f"  • Version:     {config['graph_version']}\n")
        
        print(f"{Colors.BOLD}Select Test Option:{Colors.RESET}")
        print("  1. Inspect Token & Permissions Scope (/debug_token & /me)")
        print("  2. Inspect Instagram Business Account & Recent Media")
        print("  3. Inspect Facebook Page Profile & Videos")
        print("  4. Test Instagram Reel Upload (Dry-Run / Container Check)")
        print("  5. Test Instagram Reel Upload (FULL LIVE PUBLISH)")
        print("  6. Test Facebook Page Reel Upload (as DRAFT)")
        print("  7. Test Facebook Page Reel Upload (FULL LIVE PUBLISH)")
        print("  8. Fetch Instagram & Facebook Media Insights")
        print("  9. Test Cloudflare Proxy Worker Connection")
        print(" 10. Run Long-Lived Token Exchange Wizard")
        print(" 11. Run ALL Non-Destructive Diagnostics (Options 1, 2, 3, 8, 9)")
        print("  0. Exit\n")
        
        choice = input(f"{Colors.BOLD}Enter choice (0-11): {Colors.RESET}").strip()
        
        if choice == "1":
            inspect_token_and_permissions(config)
        elif choice == "2":
            inspect_instagram_account(config)
        elif choice == "3":
            inspect_facebook_page(config)
        elif choice == "4":
            test_instagram_reels_flow(config, publish=False)
        elif choice == "5":
            confirm = input(f"{Colors.YELLOW}{Colors.BOLD}Are you sure you want to PUBLISH a live Reel to Instagram? (y/N): {Colors.RESET}")
            if confirm.lower() == 'y':
                test_instagram_reels_flow(config, publish=True)
        elif choice == "6":
            test_facebook_reels_flow(config, publish=False)
        elif choice == "7":
            confirm = input(f"{Colors.YELLOW}{Colors.BOLD}Are you sure you want to PUBLISH a live Reel to Facebook Page? (y/N): {Colors.RESET}")
            if confirm.lower() == 'y':
                test_facebook_reels_flow(config, publish=True)
        elif choice == "8":
            fetch_media_insights(config)
        elif choice == "9":
            test_proxy_connection(config)
        elif choice == "10":
            exchange_token_wizard()
        elif choice == "11":
            inspect_token_and_permissions(config)
            inspect_instagram_account(config)
            inspect_facebook_page(config)
            fetch_media_insights(config)
            test_proxy_connection(config)
        elif choice == "0":
            print("\nExiting Meta Graph API Test Module. Goodbye!")
            sys.exit(0)
            
        input(f"\n{Colors.DIM}Press Enter to return to menu...{Colors.RESET}")

# -----------------------------------------------------------------------------
# Main CLI Entrypoint
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Meta Graph API Comprehensive Test & Diagnostics Module",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("--inspect", action="store_true", help="Inspect Access Token, identity, and granted scopes")
    parser.add_argument("--ig-profile", action="store_true", help="Inspect Instagram Business Account profile & recent media")
    parser.add_argument("--fb-profile", action="store_true", help="Inspect Facebook Page details & recent videos")
    parser.add_argument("--test-ig-reel", action="store_true", help="Test Instagram Reel creation & container status polling")
    parser.add_argument("--test-fb-reel", action="store_true", help="Test Facebook Page Reel upload pipeline")
    parser.add_argument("--test-insights", action="store_true", help="Test fetching Instagram & Facebook media insights")
    parser.add_argument("--proxy-test", action="store_true", help="Test connection to Cloudflare Proxy Worker")
    parser.add_argument("--exchange-token", action="store_true", help="Run Long-Lived Token Exchange Wizard")
    parser.add_argument("--all", action="store_true", help="Run all non-destructive diagnostics")
    
    parser.add_argument("--publish", action="store_true", help="Execute actual public publishing (overrides dry-run/draft defaults)")
    parser.add_argument("--token", type=str, help="Override Access Token")
    parser.add_argument("--ig-id", type=str, help="Override Instagram Business Account ID")
    parser.add_argument("--page-id", type=str, help="Override Facebook Page ID")
    parser.add_argument("--video", type=str, help="Specify custom video file path or URL for Reels test")
    
    args = parser.parse_args()
    
    config = resolve_meta_config()
    if args.token:
        config["access_token"] = args.token
    if args.ig_id:
        config["ig_account_id"] = args.ig_id
    if args.page_id:
        config["fb_page_id"] = args.page_id
        
    # If no flags passed, launch interactive menu UI
    if not any([
        args.inspect, args.ig_profile, args.fb_profile, args.test_ig_reel,
        args.test_fb_reel, args.test_insights, args.proxy_test, args.exchange_token, args.all
    ]):
        run_interactive_menu()
        return
        
    success = True
    if args.inspect or args.all:
        success &= inspect_token_and_permissions(config)
    if args.ig_profile or args.all:
        success &= inspect_instagram_account(config)
    if args.fb_profile or args.all:
        success &= inspect_facebook_page(config)
    if args.proxy_test or args.all:
        success &= test_proxy_connection(config)
    if args.test_insights or args.all:
        success &= fetch_media_insights(config)
    if args.test_ig_reel:
        success &= test_instagram_reels_flow(config, video_url_or_path=args.video, publish=args.publish)
    if args.test_fb_reel:
        success &= test_facebook_reels_flow(config, video_path_or_url=args.video, publish=args.publish)
    if args.exchange_token:
        exchange_token_wizard()
        
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
