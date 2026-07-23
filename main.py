import os
# Configure OpenSSL to ignore unexpected EOF (required for OpenSSL 3.0+ compatibility with Meta/Instagram APIs)
def setup_custom_openssl():
    paths = ["/etc/ssl/openssl.cnf", "/etc/pki/tls/openssl.cnf", "/usr/lib/ssl/openssl.cnf"]
    system_cnf = None
    for p in paths:
        if os.path.exists(p):
            system_cnf = p
            break
    
    if not system_cnf:
        return
        
    try:
        with open(system_cnf, "r") as f:
            content = f.read()
        
        has_openssl_conf = False
        for line in content.splitlines():
            if line.strip().startswith("openssl_conf"):
                has_openssl_conf = True
                break
        
        lines = content.splitlines()
        
        if not has_openssl_conf:
            lines.insert(0, "openssl_conf = openssl_init")
            custom_suffix = (
                "\n\n[openssl_init]\n"
                "ssl_conf = ssl_sect\n\n"
                "[ssl_sect]\n"
                "system_default = system_default_sect\n\n"
                "[system_default_sect]\n"
                "Options = IgnoreUnexpectedEOF\n"
            )
        else:
            init_idx = -1
            for idx, line in enumerate(lines):
                if line.strip() == "[openssl_init]":
                    init_idx = idx
                    break
            
            if init_idx != -1:
                lines.insert(init_idx + 1, "ssl_conf = ssl_sect")
            else:
                lines.append("\n[openssl_init]")
                lines.append("ssl_conf = ssl_sect")
                
            custom_suffix = (
                "\n\n[ssl_sect]\n"
                "system_default = system_default_sect\n\n"
                "[system_default_sect]\n"
                "Options = IgnoreUnexpectedEOF\n"
            )
            
        merged_content = "\n".join(lines) + custom_suffix
        
        target_cnf = os.path.join(os.path.dirname(__file__), "openssl_custom.cnf")
        with open(target_cnf, "w") as f:
            f.write(merged_content)
            
        os.environ["OPENSSL_CONF"] = os.path.abspath(target_cnf)
        print(f"[OpenSSL-Setup] Successfully generated and loaded custom configuration at {target_cnf}")
    except Exception as e:
        print(f"[OpenSSL-Setup] Failed to configure custom OpenSSL: {e}")

setup_custom_openssl()

import json
import re
import uuid
import base64
import subprocess
import shutil
import datetime
import difflib
import time
import random
import threading
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, Depends, Query
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

app = FastAPI(title="Remotion Hugging Face Renderer — Ultimate Video Generator")

# Enable CORS so your Vercel frontend can call it directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Verification Dependency
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
security_bearer = HTTPBearer(auto_error=False)

def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    bearer_credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    api_key_query: Optional[str] = Query(None, alias="api_key")
):
    admin_key = os.environ.get("RENDERER_ADMIN_KEY", "").strip()
    if not admin_key:
        # If no key is set in environment, auth is bypassed (open public access)
        return
    
    provided_key = None
    if header_key:
        provided_key = header_key
    elif bearer_credentials:
        provided_key = bearer_credentials.credentials
    elif api_key_query:
        provided_key = api_key_query
        
    if not provided_key or provided_key.strip() != admin_key:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing RENDERER_ADMIN_KEY"
        )


PUBLIC_DIR = "/app/public"
if not os.path.exists("/app") or not os.access("/app", os.W_OK):
    PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)

# Pexels API key — env-only (never bake a key into source; the old baked-in
# default leaked via git history and had to be rotated).
# Users can override via the pexels_api_key field in the request body
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()

# Stock VIDEO b-roll: scenes use real motion clips instead of still photos —
# motion in the first frame is a proven scroll-stopper for the Instagram
# 3-second-hold signal, and periodic visual change lifts retention throughout.
# Clips come from the free Pexels Video API (same key as photos; free for
# commercial use, no attribution), with the free Pixabay video API as fallback.
# SCENE_VIDEO_MODE: "all" = every scene tries for a clip (default),
#                   "hook" = opening scene only, "off" = stills only.
HOOK_VIDEO_ENABLED = os.environ.get("HOOK_VIDEO_ENABLED", "1").strip().lower() not in ("0", "false", "no")
SCENE_VIDEO_MODE = os.environ.get("SCENE_VIDEO_MODE", "all").strip().lower()
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "").strip()
# Safety cap so a 4K clip can't blow up render memory/disk
HOOK_VIDEO_MAX_BYTES = 40 * 1024 * 1024

# AI-generated imagery: a QUERY-AWARE last resort that runs only after every
# real stock search missed, and above the generic theme fallback (it consumes
# the scene query, so it respects the "no query-blind provider above the theme
# fallback" rule). Pollinations is keyless (a free registered token lifts its
# rate limit and removes the watermark); HF FLUX.1-schnell is the secondary
# behind HF_TOKEN. AI_IMAGE_FORCE skips the stock tiers — debug/testing only.
AI_IMAGE_ENABLED = os.environ.get("AI_IMAGE_ENABLED", "1").strip().lower() not in ("0", "false", "no")
AI_IMAGE_FORCE = os.environ.get("AI_IMAGE_FORCE", "").strip().lower() in ("1", "true", "yes")
AI_IMAGE_MAX_PER_VIDEO = int(os.environ.get("AI_IMAGE_MAX_PER_VIDEO", "4"))
AI_IMAGE_TIMEOUT_SEC = int(os.environ.get("AI_IMAGE_TIMEOUT_SEC", "60"))
AI_IMAGE_MAX_BYTES = int(os.environ.get("AI_IMAGE_MAX_BYTES", str(10 * 1024 * 1024)))
POLLINATIONS_API_TOKEN = os.environ.get("POLLINATIONS_API_TOKEN", "").strip()
HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()

# Stock tiers degrade by design (Openverse/AI/local fallbacks still work), but
# a silently-missing key must be unmissable in logs, not discovered from a week
# of fallback-quality imagery.
if not PEXELS_API_KEY:
    print("⚠️ PEXELS_API_KEY not set — Pexels photo/video tiers disabled; "
          "renders will rely on Openverse/AI/local fallbacks")
if not PIXABAY_API_KEY:
    print("⚠️ PIXABAY_API_KEY not set — Pixabay b-roll fallback disabled")

# Edge-TTS narrator pool. When VOICEOVER_VOICE is unset, one voice is picked
# per video (seeded) so the channel doesn't sound like the exact same robot
# every post; the pool doubles as the FAILOVER list — if a voice errors or
# returns empty audio mid-video, the next one takes over for the remaining
# scenes (a scene silently losing its voiceover was a recurring failure mode).
VOICE_POOL = [
    "en-US-BrianNeural",        # warm, conversational — the classic narrator
    "en-US-AndrewNeural",       # confident, most popular "AI narrator" voice
    "en-US-ChristopherNeural",  # deep, authoritative
    "en-US-GuyNeural",          # energetic news-style
    "en-US-EmmaNeural",         # bright, friendly
    "en-US-AriaNeural",         # crisp, professional
]

# A video must never ship with partial or missing narration. When on (default),
# any TTS/mixing failure aborts the render instead of degrading — a GH runner
# without ffmpeg once posted a video whose voice died after scene 1 because the
# mixer "gracefully" fell back to the first scene's track alone (run #106).
# Set REQUIRE_VOICEOVER=0 only for flows where a silent video is acceptable.
REQUIRE_VOICEOVER = os.environ.get("REQUIRE_VOICEOVER", "1").strip().lower() not in ("0", "false", "no")

# Scene lengths sync to spoken narration, so short voiceovers collapse the
# whole video (a weak fallback LLM writing 10-word lines produced a 24s video
# that was planned as ~45s). Scripts whose estimated spoken runtime falls below
# MIN_SPOKEN_SEC are regenerated with an expansion note, up to
# SCRIPT_EXPAND_RETRIES extra attempts (best attempt wins).
MIN_SPOKEN_SEC = float(os.environ.get("MIN_SPOKEN_SEC", "38"))
MAX_SPOKEN_SEC = float(os.environ.get("MAX_SPOKEN_SEC", "70"))
SCRIPT_EXPAND_RETRIES = int(os.environ.get("SCRIPT_EXPAND_RETRIES", "2"))

# Session-id prefixes that get the branded tech-channel treatment. "gh-" is the
# scheduled GitHub Actions pipeline (generate_now.py) — it was missing from
# these checks originally, so CI posts silently skipped the outro, the tech
# image anchoring, and the style packs that local force-post tests always had.
AUTO_CHANNEL_PREFIXES = ("auto-tech-", "force-post-", "gh-")           # style packs + branded outro
TECH_SESSION_PREFIXES = AUTO_CHANNEL_PREFIXES + ("auto-news",)         # tech-anchored image sourcing

# Mount static folder so rendered videos and generated images are accessible
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

# =============================================================================
# IN-MEMORY RENDER STATUS TRACKING (for automation pipeline)
# =============================================================================
render_status_store: Dict[str, Dict[str, Any]] = {}
render_lock = threading.Lock()

STOCK_URL_MAP = {
    # cyberpunk_alley
    "cyberpunk_alley_scene1.jpg": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?q=80&w=800&auto=format&fit=crop",
    "cyberpunk_alley_scene2_opt0.jpg": "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?q=80&w=800&auto=format&fit=crop",
    "cyberpunk_alley_scene2_opt1.jpg": "https://images.unsplash.com/photo-1508849789987-4e5333c12b78?q=80&w=800&auto=format&fit=crop",
    "cyberpunk_alley_scene2_opt2.jpg": "https://images.unsplash.com/photo-1601042879364-f3947d3f9c16?q=80&w=800&auto=format&fit=crop",
    "cyberpunk_alley_scene3_opt0.jpg": "https://images.unsplash.com/photo-1535223289827-42f1e9919769?q=80&w=800&auto=format&fit=crop",
    "cyberpunk_alley_scene3_opt1.jpg": "https://images.unsplash.com/photo-1542838132-92c53300491e?q=80&w=800&auto=format&fit=crop",
    "cyberpunk_alley_scene3_opt2.jpg": "https://images.unsplash.com/photo-1519608487953-e999c86e7455?q=80&w=800&auto=format&fit=crop",
    
    # neon_city
    "neon_city_scene1.jpg": "https://images.unsplash.com/photo-1542838132-92c53300491e?q=80&w=800&auto=format&fit=crop",
    "neon_city_scene2_opt0.jpg": "https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?q=80&w=800&auto=format&fit=crop",
    "neon_city_scene2_opt1.jpg": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?q=80&w=800&auto=format&fit=crop",
    "neon_city_scene2_opt2.jpg": "https://images.unsplash.com/photo-1519608487953-e999c86e7455?q=80&w=800&auto=format&fit=crop",
    "neon_city_scene3_opt0.jpg": "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=800&auto=format&fit=crop",
    "neon_city_scene3_opt1.jpg": "https://images.unsplash.com/photo-1511447333015-45b65e60f6d5?q=80&w=800&auto=format&fit=crop",
    "neon_city_scene3_opt2.jpg": "https://images.unsplash.com/photo-1508849789987-4e5333c12b78?q=80&w=800&auto=format&fit=crop",
    
    # misty_forest
    "misty_forest_scene1.jpg": "https://images.unsplash.com/photo-1448375240586-882707db888b?q=80&w=800&auto=format&fit=crop",
    "misty_forest_scene2_opt0.jpg": "https://images.unsplash.com/photo-1502082553048-f009c37129b9?q=80&w=800&auto=format&fit=crop",
    "misty_forest_scene2_opt1.jpg": "https://images.unsplash.com/photo-1473448912268-2022ce9509d8?q=80&w=800&auto=format&fit=crop",
    "misty_forest_scene2_opt2.jpg": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=800&auto=format&fit=crop",
    "misty_forest_scene3_opt0.jpg": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?q=80&w=800&auto=format&fit=crop",
    "misty_forest_scene3_opt1.jpg": "https://images.unsplash.com/photo-1510312305653-8ed496efae75?q=80&w=800&auto=format&fit=crop",
    "misty_forest_scene3_opt2.jpg": "https://images.unsplash.com/photo-1482862549707-f63cb32c5fd9?q=80&w=800&auto=format&fit=crop",
    
    # deep_space
    "deep_space_scene1.jpg": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=800&auto=format&fit=crop",
    "deep_space_scene2_opt0.jpg": "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?q=80&w=800&auto=format&fit=crop",
    "deep_space_scene2_opt1.jpg": "https://images.unsplash.com/photo-1506318137071-a8e063b4bec0?q=80&w=800&auto=format&fit=crop",
    "deep_space_scene2_opt2.jpg": "https://images.unsplash.com/photo-1538370965046-79c0d6907d47?q=80&w=800&auto=format&fit=crop",
    "deep_space_scene3_opt0.jpg": "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?q=80&w=800&auto=format&fit=crop",
    "deep_space_scene3_opt1.jpg": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?q=80&w=800&auto=format&fit=crop",
    "deep_space_scene3_opt2.jpg": "https://images.unsplash.com/photo-1543722530-d2c3201371e7?q=80&w=800&auto=format&fit=crop",
    
    # cosmic_aurora
    "cosmic_aurora_scene1.jpg": "https://images.unsplash.com/photo-1506318137071-a8e063b4bec0?q=80&w=800&auto=format&fit=crop",
    "cosmic_aurora_scene2_opt0.jpg": "https://images.unsplash.com/photo-1483347756197-71ef80e95f73?q=80&w=800&auto=format&fit=crop",
    "cosmic_aurora_scene2_opt1.jpg": "https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?q=80&w=800&auto=format&fit=crop",
    "cosmic_aurora_scene2_opt2.jpg": "https://images.unsplash.com/photo-1529963183134-61a90db47eaf?q=80&w=800&auto=format&fit=crop",
    "cosmic_aurora_scene3_opt0.jpg": "https://images.unsplash.com/photo-1475274047050-1d0c0975c63e?q=80&w=800&auto=format&fit=crop",
    "cosmic_aurora_scene3_opt1.jpg": "https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=800&auto=format&fit=crop",
    "cosmic_aurora_scene3_opt2.jpg": "https://images.unsplash.com/photo-1501862700950-1894815ae3f7?q=80&w=800&auto=format&fit=crop",
    
    # synthwave_sunset
    "synthwave_sunset_scene1.jpg": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=800&auto=format&fit=crop",
    "synthwave_sunset_scene2_opt0.jpg": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?q=80&w=800&auto=format&fit=crop",
    "synthwave_sunset_scene2_opt1.jpg": "https://images.unsplash.com/photo-1502680390469-be75c86b636f?q=80&w=800&auto=format&fit=crop",
    "synthwave_sunset_scene2_opt2.jpg": "https://images.unsplash.com/photo-1550684848-fac1c5b4e853?q=80&w=800&auto=format&fit=crop",
    "synthwave_sunset_scene3_opt0.jpg": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=800&auto=format&fit=crop",
    "synthwave_sunset_scene3_opt1.jpg": "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?q=80&w=800&auto=format&fit=crop",
    "synthwave_sunset_scene3_opt2.jpg": "https://images.unsplash.com/photo-1538964173425-93884d738596?q=80&w=800&auto=format&fit=crop",
    
    # misty_mountain
    "misty_mountain_scene1.jpg": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?q=80&w=800&auto=format&fit=crop",
    "misty_mountain_scene2_opt0.jpg": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=800&auto=format&fit=crop",
    "misty_mountain_scene2_opt1.jpg": "https://images.unsplash.com/photo-1439853949127-fa647821ebb0?q=80&w=800&auto=format&fit=crop",
    "misty_mountain_scene2_opt2.jpg": "https://images.unsplash.com/photo-1510312305653-8ed496efae75?q=80&w=800&auto=format&fit=crop",
    "misty_mountain_scene3_opt0.jpg": "https://images.unsplash.com/photo-1486916856992-e4db22c8df33?q=80&w=800&auto=format&fit=crop",
    "misty_mountain_scene3_opt1.jpg": "https://images.unsplash.com/photo-1475924156734-496f6cac6ec1?q=80&w=800&auto=format&fit=crop",
    "misty_mountain_scene3_opt2.jpg": "https://images.unsplash.com/photo-1504893524553-ac55fce69cbf?q=80&w=800&auto=format&fit=crop",
    
    # retro_tech
    "retro_tech_scene1.jpg": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=800&auto=format&fit=crop",
    "retro_tech_scene2_opt0.jpg": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?q=80&w=800&auto=format&fit=crop",
    "retro_tech_scene2_opt1.jpg": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=800&auto=format&fit=crop",
    "retro_tech_scene2_opt2.jpg": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?q=80&w=800&auto=format&fit=crop",
    "retro_tech_scene3_opt0.jpg": "https://images.unsplash.com/photo-1531403009284-440f080d1e12?q=80&w=800&auto=format&fit=crop",
    "retro_tech_scene3_opt1.jpg": "https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?q=80&w=800&auto=format&fit=crop",
    "retro_tech_scene3_opt2.jpg": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?q=80&w=800&auto=format&fit=crop",
    
    # mystic_temple
    "mystic_temple_scene1.jpg": "https://images.unsplash.com/photo-1508739773434-c26b3d09e071?q=80&w=800&auto=format&fit=crop",
    "mystic_temple_scene2_opt0.jpg": "https://images.unsplash.com/photo-1534447677768-be436bb09401?q=80&w=800&auto=format&fit=crop",
    "mystic_temple_scene2_opt1.jpg": "https://images.unsplash.com/photo-1540959733332-eab4deceeaf7?q=80&w=800&auto=format&fit=crop",
    "mystic_temple_scene2_opt2.jpg": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?q=80&w=800&auto=format&fit=crop",
    "mystic_temple_scene3_opt0.jpg": "https://images.unsplash.com/photo-1528164344705-47542687000d?q=80&w=800&auto=format&fit=crop",
    "mystic_temple_scene3_opt1.jpg": "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?q=80&w=800&auto=format&fit=crop",
    "mystic_temple_scene3_opt2.jpg": "https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=800&auto=format&fit=crop",
    
    # digital_matrix
    "digital_matrix_scene1.jpg": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=800&auto=format&fit=crop",
    "digital_matrix_scene2_opt0.jpg": "https://images.unsplash.com/photo-1542831371-29b0f74f9713?q=80&w=800&auto=format&fit=crop",
    "digital_matrix_scene2_opt1.jpg": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=800&auto=format&fit=crop",
    "digital_matrix_scene2_opt2.jpg": "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?q=80&w=800&auto=format&fit=crop",
    "digital_matrix_scene3_opt0.jpg": "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=800&auto=format&fit=crop",
    "digital_matrix_scene3_opt1.jpg": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?q=80&w=800&auto=format&fit=crop",
    "digital_matrix_scene3_opt2.jpg": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=800&auto=format&fit=crop"
}


# =============================================================================
# REQUEST MODELS
# =============================================================================

class InstagramConfig(BaseModel):
    enabled: bool = False
    method: str = "official"  # "official" or "unofficial"
    username: Optional[str] = None
    password: Optional[str] = None
    fb_access_token: Optional[str] = None
    instagram_business_account_id: Optional[str] = None
    caption: Optional[str] = None
    auto_generate_caption: bool = True

class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    auto_generate_caption: bool = True


class YouTubeConfig(BaseModel):
    """YouTube Shorts upload via the official Data API v3 (OAuth refresh token).

    Uses the TOS-compliant official API — automation through it carries no
    shadowban risk, unlike browser/scraping uploaders. Note the default API
    quota (10,000 units/day) allows ~6 uploads/day (1,600 units each), which
    matches the 5-6 posts/day target exactly.
    """
    enabled: bool = False
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None
    privacy_status: str = "public"  # "public" | "unlisted" | "private"
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    auto_generate_metadata: bool = True


class FacebookConfig(BaseModel):
    """Facebook Page Reels via the official Reels Publishing API.

    Cross-posts the same rendered mp4 to a FB Page — nearly free reach on top
    of IG (same Graph API family, one extra publish flow). Needs a PAGE access
    token (pages_manage_posts / pages_read_engagement / pages_show_list); a
    long-lived USER token also works — the page token is derived at runtime.
    """
    enabled: bool = False
    page_id: Optional[str] = None
    access_token: Optional[str] = None
    caption: Optional[str] = None
    auto_generate_caption: bool = True


class PipelineConfig(BaseModel):
    outputFormat: Optional[str] = "mp4"
    quality: Optional[str] = "standard"
    watermark: Optional[str] = None
    webhookUrl: Optional[str] = None
    callbackId: Optional[str] = None
    priority: Optional[str] = "normal"
    instagram: Optional[InstagramConfig] = None
    telegram: Optional[TelegramConfig] = None
    youtube: Optional[YouTubeConfig] = None
    facebook: Optional[FacebookConfig] = None
    voice: Optional[str] = None
    voiceRate: Optional[str] = None
    voicePitch: Optional[str] = None




class InstagramDirectPostRequest(BaseModel):
    video_url_or_path: str
    caption: Optional[str] = None
    config: InstagramConfig


class RenderRequest(BaseModel):
    prompt: str
    text_gen_key: Optional[str] = None
    image_gen_key: Optional[str] = None
    nvidia_nim_key: Optional[str] = None
    theme_overrides: Optional[Dict[str, Any]] = None
    text_api_base: Optional[str] = None
    text_model_name: Optional[str] = None
    image_api_base: Optional[str] = None
    image_model_name: Optional[str] = None
    image_urls: Optional[list] = None
    pipeline: Optional[PipelineConfig] = None
    pexels_api_key: Optional[str] = None
    # Selection metadata (title/subject/url/source/keywords/viral_score) from
    # the topic engine — recorded into the post ledger for the feedback loop.
    topic_meta: Optional[Dict[str, Any]] = None


class BatchRenderRequest(BaseModel):
    renders: List[RenderRequest]


class RenderHNRequest(BaseModel):
    min_score: Optional[int] = 80
    limit: Optional[int] = 1
    text_gen_key: Optional[str] = None
    image_gen_key: Optional[str] = None
    nvidia_nim_key: Optional[str] = None
    theme_overrides: Optional[Dict[str, Any]] = None
    text_api_base: Optional[str] = None
    text_model_name: Optional[str] = None
    pexels_api_key: Optional[str] = None
    pipeline: Optional[PipelineConfig] = None



# =============================================================================
# QUALITY PRESETS — maps quality names to Remotion CLI flags
# =============================================================================
QUALITY_PRESETS = {
    "draft": {
        "crf": 35,
        "jpeg_quality": 50,
        "scale": 0.5,          # render at half resolution for speed
        "concurrency": 8,
    },
    "standard": {
        "crf": 34,
        "jpeg_quality": 65,
        "scale": 0.75,
        "concurrency": 4,
    },
    "high": {
        "crf": 18,
        "jpeg_quality": 95,
        "scale": 1.0,
        "concurrency": 2,      # fewer parallel frames → more memory per frame
    },
}

# Aspect ratio → pixel dimensions
ASPECT_RATIO_MAP = {
    "9:16": {"width": 1080, "height": 1920},
    "16:9": {"width": 1920, "height": 1080},
    "1:1":  {"width": 1080, "height": 1080},
    "4:5":  {"width": 1080, "height": 1350},
}

# Output format → Remotion codec mapping
FORMAT_CODEC_MAP = {
    "mp4":  "h264",
    "webm": "vp8",
    "gif":  "gif",
}


# =============================================================================
# PROMPT ENGINEERING FOR SMALL OPEN-SOURCE MODELS
# =============================================================================
# The following system prompt, user prompt builder, and validator are designed
# to produce correct JSON from models as small as 1.5B-3B parameters.
# Key techniques:
#   - Separate system/user messages (small models respect role boundaries)
#   - Exhaustive enum tables with visual descriptions (no guessing)
#   - Complete few-shot example (the #1 technique for small models)
#   - Style pairing guide (prevents nonsensical combos)
#   - Robust post-processor that auto-fixes common mistakes
# =============================================================================

SYSTEM_PROMPT = """You are a world-class video script engine. You receive a topic and output a single valid JSON object. NO markdown fences, NO explanation, NO comments — ONLY raw JSON.

Your output drives a cinematic video renderer with animated text, dynamic camera motion, themed overlays, and smooth transitions between scenes. Every choice you make directly impacts the final video's visual quality.

=== OUTPUT SCHEMA ===

{
  "theme": {
    "primaryColor":     "<hex, e.g. #00f0ff>",
    "secondaryColor":   "<hex, e.g. #ff007f>",
    "overlayType":      "<OVERLAY option>",
    "fontFamilyName":   "<FONT option>",
    "musicTrack":       "<MUSIC option>",
    "cameraMotion":     "<CAMERA option>",
    "subtitlePosition": "<top | center | bottom>",
    "overlayOpacity":   <0.0 – 1.0>,
    "transitionStyle":  "<TRANSITION option>",
    "aspectRatio":      "<ASPECT RATIO option>",
    "gradientOverlay":  "<GRADIENT option>"
  },
  "scenes": [
    {
      "type":             "<SCENE TYPE option>",
      "text":             "<concise on-screen caption (5-15 words max)>",
      "voiceover":        "<detailed spoken narration text (15-30 words, complete sentences)>",
      "searchQuery":      "<2-5 visual stock photo search keywords>",
      "videoQuery":       "<2-4 keywords for a MOTION b-roll clip showing THIS scene's topic in action (tech content → screens/code/terminals/dashboards/data-centers/chips/robotics/networks)>",
      "durationInFrames": <clamp between 90 (3s) and 300 (10s)>,
      ... (other optional scene-specific fields)
    }
  ],
  "pipeline": { "outputFormat": "mp4", "quality": "standard" }
}

=== THEME OPTIONS (use ONLY these exact strings) ===

OVERLAY (overlayType):
  "grid-hud"       → Sci-fi holographic grid + scanning laser. USE FOR: tech, AI, cyberpunk, crypto, data.
  "particles"      → Gentle floating dust drifting upward.     USE FOR: nature, ambient, calm, wellness, meditation.
  "clean"          → No overlay, just image + text.            USE FOR: corporate, SaaS, professional, educational, marketing.
  "vhs-glitch"     → Retro CRT scanlines + chromatic aberration. USE FOR: nostalgia, 80s/90s, meme, retro gaming.
  "fantasy-sparks" → Drifting celestial spark lights.           USE FOR: fantasy, magic, space, spiritual, luxury.
  "aurora"         → Flowing aurora light waves + glow.          USE FOR: premium, dreamy, futuristic, product, ambient.

FONT (fontFamilyName):
  "Share Tech Mono" → Monospace tech font.    USE FOR: coding, hacker, sci-fi, data-heavy.
  "Orbitron"        → Bold geometric future.  USE FOR: space, gaming, product launches, headlines.
  "Inter"           → Clean modern sans-serif. USE FOR: corporate, educational, clean content. BEST DEFAULT.
  "Playfair Display"→ Elegant serif.           USE FOR: luxury, fashion, editorial, storytelling, quotes.
  "Courier New"     → Classic typewriter.      USE FOR: retro, vintage, literary, documentary, memes.

MUSIC (musicTrack):
  "ambient-tech"  → Electronic atmosphere. Good for tech, corporate, modern.
  "lofi-chill"    → Relaxed lo-fi beats. Good for lifestyle, tips, chill.
  "cosmic-synth"  → Spacey synthesizer. Good for space, fantasy, dramatic.
  "none"          → Silent. Good for text-focused or user-will-add-music.

CAMERA (cameraMotion):
  "ken-burns"           → Slow zoom + gentle pan. Classic cinematic. BEST DEFAULT.
  "pan-horizontal"      → Steady left→right pan. Good for landscapes, wide shots.
  "zoom-slow"           → Slow zoom-in, no pan. Dramatic focus.
  "static"              → No movement. Clean, minimal.
  "dynamic-zoom-rotate" → Zoom + slight rotation. Energetic, modern.
  "pan-tilt"            → Horizontal pan + vertical tilt + rotation. Complex, cinematic.
  "pulse-zoom"          → Breathing zoom effect. Creates tension.
  "glitch-shift"        → Random jerky shifts. PAIR WITH vhs-glitch overlay.
  "orbit-drift"         → Slow orbital drift + gentle rotation. Dreamy, premium.
  "vertigo"             → Dolly-zoom push. Intense, dramatic reveal.

TRANSITION (transitionStyle):
  "crossfade"    → Smooth opacity blend. Classic cinematic. BEST DEFAULT.
  "slide-left"   → Slide in from right, exit left. Energetic, modern, good for lists.
  "zoom-through" → Camera zooms into next scene. Dramatic, immersive.
  "glitch-cut"   → Hard cut + RGB-split flash. PAIR WITH vhs-glitch or grid-hud.
  "wipe-down"    → Diagonal clip-path wipe reveal. Cinematic, modern.
  "iris-open"    → Circular reveal from center. Cinematic, retro-film.
  "blur-dissolve"→ Focus-pull blur blend. Dreamy, smooth.
  "scale-rotate" → Spin + scale entrance. Energetic, bold.
  "push-up"      → Next scene pushes up from below. Snappy, modern.
  "spin-blur"    → Motion-blurred spin. High-energy, dynamic.
  "none"         → Hard cut. Clean, fast.

ASPECT RATIO (aspectRatio):
  "9:16" → Vertical. TikTok / Reels / Shorts. DEFAULT.
  "16:9" → Horizontal. YouTube / Presentation.
  "1:1"  → Square. Instagram feed.
  "4:5"  → Tall portrait. Instagram portrait.

GRADIENT (gradientOverlay):
  "none"          → No gradient. DEFAULT.
  "top-to-bottom" → Vertical gradient. Adds cinematic depth.
  "radial-center" → Radial vignette from center. Focus effect.
  "diagonal"      → 45° gradient. Stylish, dynamic.

TEXT ANIMATION (textAnimation) — SET PER SCENE:
  "glitch-decode" → Characters randomly decode/resolve. DEFAULT. USE FOR: tech, hacker, sci-fi.
  "typewriter"    → Characters appear one-by-one with cursor. USE FOR: storytelling, documentary, quotes.
  "fade-up"       → Text fades in floating upward. USE FOR: elegant, corporate, calm.
  "slide-in"      → Text slides from left. USE FOR: lists, energetic, modern.
  "word-by-word"  → Words appear staggered. USE FOR: dramatic reveals, quotes, emphasis.
  "scale-pop"     → Text springs in with a bouncy scale-up. USE FOR: punchy, playful, energetic.
  "blur-in"       → Text sharpens from a blur. USE FOR: premium, cinematic, smooth.
  "wave"          → Letters ripple in on a wave. USE FOR: fun, dynamic, lively.
  "none"          → Instant appear. USE FOR: countdown/metric scenes, fast-paced.

=== SCENE TYPES ===

Each scene has a "type" that controls its visual layout. Choose the type that best presents the content:

  "hero"        → Large centered title + subtitle. USE FOR: opening scene, closing statement, big headlines.
                  Fields: title (UPPERCASE, 2-5 words), text (main line), subtitle (tagline).

  "split"       → General layout with title + text + optional secondary badge. USE FOR: explanations, facts, narrative.
                  Fields: title, text, subtitle, secondaryText (appears as a styled badge).

  "metric"      → Giant centered number/stat with label. USE FOR: showing a single key statistic.
                  Fields: title (label), text (THE BIG NUMBER — put the actual stat here), secondaryText (unit/context).

  "countdown"   → Animated counter that counts from one number to another. USE FOR: stats that ANIMATE on screen.
                  Fields: title, text (label below counter), countFrom (start number), countTo (end number), countSuffix ("%", "K+", "+", etc).
                  IMPORTANT: Use textAnimation="none" for countdown scenes.

  "comparison"  → Side-by-side panels with "VS" divider. USE FOR: before/after, old vs new, competitor comparison.
                  Fields: title, text (LEFT panel value), secondaryText (RIGHT panel value), leftLabel, rightLabel.

  "list"        → Bullet-point list with staggered reveal. USE FOR: features, steps, tips, reasons.
                  Fields: title, text (items separated by "|" character — e.g. "Step 1|Step 2|Step 3"), or listItems (array of strings).

  "testimonial" → Quote-style highlight layout with left border accent. USE FOR: one standout claim, spec, or line about the subject.
                  Fields: title (the SOURCE, which must be the subject's own docs/changelog/benchmark/README — e.g. "FROM THE V2 CHANGELOG"), text (the claim), subtitle (the subject's name — e.g. the product/project itself).
                  NEVER attribute this scene to a person. NEVER invent a reviewer, customer, or employee. Only quote a person if their exact name AND statement were given in the topic brief.

  "cta"         → Call-to-action with pulsing gradient button. USE FOR: final scene with action prompt.
                  Fields: title (headline), text (supporting message), ctaText (button label — e.g. "SIGN UP FREE").

  "bar-chart"   → Ranked horizontal bars that grow on screen with count-up labels. USE FOR: comparing a few named quantities.
                  Fields: title (heading), subtitle (caption), chartData (array of 2-6 objects like {"label":"Redis","value":92}).
                  ONLY use with REAL numbers you actually know for this subject — otherwise use "list" instead.

  "chart"       → Animated donut showing how a whole splits into parts. USE FOR: percentage/share breakdowns.
                  Fields: title, subtitle, chartData (array of 2-5 objects; values are treated as shares of the total, e.g. {"label":"Mobile","value":68}).
                  ONLY use with REAL shares — never invent them.

  "line-chart"  → A trend line that draws itself left→right with popping data points. USE FOR: one real metric changing over time/steps.
                  Fields: title, subtitle, chartData (array of 3-8 objects in left→right order, e.g. {"label":"2021","value":12}).
                  ONLY use with a REAL series — never invent a trend.

  "rating"      → Star rating with a partial-fill and a count-up of the score. USE FOR: a real score/review out of N.
                  Fields: title, subtitle, ratingValue (e.g. 4.8), ratingMax (default 5). ONLY use with a REAL score.

  "ui-demo"     → A simulated app screen: a cursor types a query into a field, a spinner loads, results check in, a button clicks. USE FOR: showing how the tool/app is actually used ("demonstrate it" beat).
                  Fields: title (app/site name), text (the exact query typed into the field, ≤30 chars), subtitle (the field's label, e.g. "PROMPT"), listItems (2-4 short result rows), ctaText (button label).

=== CRITICAL RULES ===

1. Output ONLY the JSON object. No text, markdown, or explanation before or after.
2. Use double quotes for ALL string values. No single quotes.
3. No trailing commas. No JavaScript comments.
4. Generate 4 to 8 scenes. Each scene MUST have: type, text, voiceover, searchQuery, durationInFrames.
5. FIRST scene MUST be type "hero" — it is the HOOK. Instagram ranks Reels by 3-second hold, so this scene alone decides reach. Its "text" (max 8 words, on screen from frame one) and "voiceover" (max 12 words, spoken hook — never a greeting or intro like "welcome" / "in this video") must BOTH deliver the hook and make the payoff of watching obvious. Bold, surprising, specific (see the CREATIVE BRIEF below for the exact hook style to use).
6. LAST scene MUST be type "cta", "hero", or "split" — this is the conclusion that pays off the hook. Default to a CONTENT payoff (a decisive takeaway, or a "try/do this" action tied to the story). Add a follow/subscribe ask ONLY if the creative brief below explicitly requests one — never invent one yourself, and never state the same call-to-action twice in one video.
7. Use AT LEAST 3 different scene types across the video for visual variety. Do NOT repeat the same scene type back-to-back.
8. VARY textAnimation across scenes — never use the same animation on consecutive scenes.
9. Use ONLY the exact option strings listed above. Do NOT invent new values.

=== CONTENT QUALITY RULES ===

10. Write PUNCHY, CONCISE text. Each scene's "text" field should be 3-10 words maximum (for clean on-screen overlays, e.g. "SaaS growth jumps"). The scene's "voiceover" field should contain the detailed narrative to be spoken (15-30 words, complete sentences).
11. Titles should be 2-5 words, UPPERCASE, and attention-grabbing.
12. NEVER use placeholder values like "X%", "$X", "N+", "[number]", or "XX". Write CONCRETE numbers when you know them.
    BAD: "Revenue increased by X%"  →  GOOD: "Revenue increased by 47%" (only if 47% is the real figure)
13. Use ONLY numbers you actually know to be true for this exact subject (from the topic brief or well-established knowledge).
    If you don't know the precise figure, state the fact concretely WITHOUT fake precision — and never leave a placeholder.
    BAD: "MeshLLM handles 12,400 requests per second" (invented)  →  GOOD: "MeshLLM splits inference across every device on your network" (true, no fake stat)
    BAD: "Revenue increased by X%"  →  GOOD: "Revenue grew every quarter since launch"
14. For countdown scenes: pick countFrom and countTo values that tell a compelling story (e.g. 0→10000 for growth, 100→0 for countdown).
14b. NO PLATITUDE VIDEOS. The video must center on ONE named, concrete subject (a specific tool, product, release, event, or technique) and teach specifics about it: what it is, a real number/spec, and how it's actually used.
    BAD: "Using good tools makes you more productive"  →  GOOD: "Zed just hit 1.0 — it opens files 5x faster than VS Code. Here's the setting that does it."
    Every sentence must carry information specific to the subject — if a sentence would be true of any topic, cut it.

=== NO-REPETITION & STORY FLOW (this is what makes a video watchable instead of redundant) ===

R1. SAY IT ONCE. Name the subject/headline in the HOOK (scene 1) and NOWHERE ELSE in full. After scene 1, refer to it with a pronoun or short-form ("it", "the tool", "the team", "the release"). The on-screen karaoke shows EVERY spoken word for the whole video, so a repeated line is read AND heard 5-6 times and instantly feels cheap. The single fastest way to ruin a video is to restate the headline every scene.
R2. EVERY SCENE MOVES FORWARD. Each scene's voiceover must add NEW information the earlier scenes did not state. No scene may re-explain or re-summarize a point already made. If a scene would only repeat, delete it and move the story forward instead.
R3. ON-SCREEN ≠ SPOKEN. A scene's "text" (and "title"/"subtitle") is a SHORT punchy LABEL — a keyword, a number, a 3-6 word phrase. The "voiceover" is the sentence that label points at. They must use DIFFERENT words — never copy voiceover wording onto the screen. The viewer reads the label and hears the story; together they add up, they don't echo.
    BAD:  text "The fastest API gateway ever built"  +  voiceover "Meet HyperAPI, the fastest API gateway ever built."   (screen = voiceover, redundant)
    GOOD: text "20ms, not 200ms"                     +  voiceover "It answers requests in twenty milliseconds — ten times quicker than the gateway you run now."
R4. THREE FIELDS, THREE MEANINGS. Within one scene, "title", "text", and "subtitle" must each say something DIFFERENT. Never paraphrase one into another.
R5. ARC, NOT A LIST. Build a story that escalates, not a pile of facts: HOOK (surprise) → STAKES (why the viewer should care) → the SURPRISING detail or mechanism (the "wait, really?" beat) → PAYOFF (one concrete takeaway). Plant one open loop early and close it at the end so viewers stay for the finish.

=== FACT INTEGRITY RULES (ZERO TOLERANCE — one violation ruins the whole video) ===

F1. NEVER invent people. No made-up names in ANY field, including voiceover. Do NOT write "the lead developer <name> says",
    "a senior engineer explains", or attach any name to a role. Placeholder names (John Doe, Jane Smith, Sarah Chen,
    Alex Johnson, etc.) are absolutely forbidden.
F2. NEVER invent quotes, reviews, or testimonials. No "X says", "according to X", or customer praise — unless that exact
    person AND statement were given to you in the topic brief.
F3. NEVER invent companies, customers, or case studies (no "TechCorp", "Acme Inc", "a Fortune 500 client").
F4. Attribute claims only to the subject itself — its docs, changelog, benchmarks, README, or announcement.
F5. If the topic brief names real people, you may state facts about them — but never put invented words in their mouths.
F6. CHARTS/RATINGS/COUNTERS SHOW NUMBERS AS FACT. Only use "bar-chart", "chart", "line-chart", "rating", "metric", or "countdown" when you have REAL figures for this exact subject (from the topic brief or well-established knowledge). If you do not have real numbers, use a text scene ("split"/"hero"/"list") instead — NEVER invent chart values, shares, trends, or ratings just to fill a slot. A fabricated 68% donut is as damaging as a fabricated quote.

=== IMAGE SEARCH QUERY RULES ===

15. searchQuery is 2-5 keywords that will be used to find a STOCK PHOTO from Pexels/Unsplash.
16. Describe the VISUAL CONTENT of the image, not the abstract concept.
    BAD: "revenue"            → GOOD: "business chart laptop office"
    BAD: "growth"             → GOOD: "green plant seedling growing"
    BAD: "testimonial"        → GOOD: "smiling professional woman portrait"
    BAD: "artificial intelligence" → GOOD: "circuit board blue glow closeup"
    BAD: "workout benefits"   → GOOD: "person running sunrise city"
17. Use DIFFERENT searchQuery for each scene — no two scenes should have the same query.
18. Think about what PHOTOGRAPH would look best behind the text. Be specific and visual.
18a. searchQuery must live in the SUBJECT'S REAL DOMAIN, same as videoQuery. For tech subjects
    (dev tools, AI, chips, apps, security, cloud) EVERY searchQuery names tech imagery — screens,
    code, terminals, server rooms, chips, dashboards, devices. NEVER a pure mood abstraction:
    BAD: "abstract speed light trails"  → GOOD: "server rack lights closeup"
    BAD: "dramatic sky sunrise"         → GOOD: "developer laptop code night"
    Abstract queries return random stock photos (forests, bokeh, skies) that make the video
    look broken. For non-tech subjects, match that topic's real domain instead.
18b. videoQuery drives a MOTION b-roll clip that plays behind the scene — this is what makes the video feel edited instead of a slideshow. It must show THIS video's actual subject in its REAL WORLD and in MOTION, matched to the topic's domain:
    - coding tool / framework → "code editor screen scrolling", "terminal typing commands", "developer laptop closeup"
    - AI model / ML → "data center servers gpu", "neural network visualization motion", "robot arm working"
    - security / breach → "terminal hacking code green", "server room dark lights", "padlock circuit motion"
    - crypto / finance → "trading chart screen moving", "stock ticker numbers", "server racks blinking"
    - hardware / gadget → "circuit board macro motion", "chip manufacturing closeup", "device screen ui"
    Keep it topic-relevant and concrete — NOT a generic abstract loop. Give each scene a different videoQuery. For non-tech topics, still match the topic's real domain in motion (fitness → "person running sunrise", food → "chef plating dish closeup").

=== COLOR RULES ===

19. primaryColor and secondaryColor should COMPLEMENT each other and match the video's mood.
    - Energy/Excitement: warm tones (#ff6b35 + #ffd700, #ff2d55 + #ff9500)
    - Trust/Corporate: blue tones (#0066ff + #00d4aa, #3b82f6 + #8b5cf6)
    - Calm/Nature: cool/green (#00f0ff + #7b68ee, #10b981 + #06b6d4)
    - Drama/Dark: deep tones (#8b5cf6 + #ec4899, #1a0533 + #ff007f)
    - Retro/Fun: vibrant mix (#ff007f + #00f0ff, #f59e0b + #ef4444)

=== STYLE PAIRING GUIDE ===

These are PROVEN combinations. Use them as starting points:
  Tech/AI/Crypto    → grid-hud + Share Tech Mono + dynamic-zoom-rotate + glitch-cut + glitch-decode
  Corporate/SaaS    → clean + Inter + ken-burns + crossfade + fade-up + top-to-bottom gradient
  Retro/Nostalgia   → vhs-glitch + Courier New + glitch-shift + glitch-cut + typewriter
  Fantasy/Space     → fantasy-sparks + Playfair Display + zoom-slow + zoom-through + word-by-word + radial-center
  Lifestyle/Chill   → particles + Inter + pan-horizontal + crossfade + fade-up
  Educational/Tips  → clean + Inter + ken-burns + slide-left + slide-in
  Marketing/Launch  → clean + Orbitron + dynamic-zoom-rotate + zoom-through + fade-up + diagonal gradient
  Fitness/Health    → particles + Orbitron + ken-burns + crossfade + fade-up
  Food/Recipe       → clean + Playfair Display + zoom-slow + crossfade + fade-up + top-to-bottom
  Motivational      → fantasy-sparks + Playfair Display + zoom-slow + crossfade + word-by-word + radial-center

=== PLATFORM DETECTION ===

20. Auto-detect platform from user's prompt and set aspectRatio accordingly:
    TikTok / Reels / Shorts / vertical → "9:16"
    YouTube / widescreen / horizontal   → "16:9"
    Instagram / feed / post / square    → "1:1"
    Default if no platform mentioned     → "9:16"

=== DURATION GUIDE ===

21. durationInFrames at 30fps: 150 frames = 5 seconds, 175 = ~6s, 200 = ~6.7s, 250 = ~8.3s.
    - Hero/opener (the HOOK): 100-140 frames (~3.5-4.5s) — shortest scene in the video; a fast hook protects 3-second retention
    - Content scenes: 175-200 frames (time to read + absorb)
    - Countdown scenes: 200-250 frames (animation needs time)
    - List scenes: 200-250 frames (items reveal one by one)
    - CTA/closer: 175-200 frames (clear call to action)
22. TOTAL RUNTIME: scene lengths auto-sync to the spoken narration, so the "voiceover" fields ARE the video length.
    The summed narration MUST run 40-55 seconds when spoken (~110-150 words total across all scenes).
    Hit it by writing 20-35 word voiceovers per content scene — never by padding with repetition."""


def build_user_prompt(user_request: str) -> str:
    """Build the user-role prompt with two diverse few-shot examples.
    
    Two examples cover different video styles (tech product vs lifestyle)
    to help the model generalize across topics.
    """
    return f"""Generate a cinematic video script JSON for this topic:

"{user_request}"

=== EXAMPLE 1 (Tech/Product topic) ===
Topic: "SaaS product launch — 10x faster API"

{{
  "theme": {{
    "primaryColor": "#7b68ee",
    "secondaryColor": "#ff6b9d",
    "overlayType": "clean",
    "fontFamilyName": "Orbitron",
    "musicTrack": "ambient-tech",
    "cameraMotion": "dynamic-zoom-rotate",
    "subtitlePosition": "bottom",
    "overlayOpacity": 0.8,
    "transitionStyle": "zoom-through",
    "aspectRatio": "9:16",
    "gradientOverlay": "diagonal"
  }},
  "scenes": [
    {{
      "type": "hero",
      "title": "MEET HYPERAPI",
      "text": "20ms, not 200ms",
      "subtitle": "your gateway is the bottleneck",
      "voiceover": "Your API gateway is the slowest hop in your whole stack — HyperAPI just fixed that.",
      "searchQuery": "server rack lights closeup dark",
      "videoQuery": "server data center lights motion",
      "durationInFrames": 130,
      "textAnimation": "glitch-decode"
    }},
    {{
      "type": "comparison",
      "title": "THE DIFFERENCE",
      "text": "200ms",
      "secondaryText": "20ms",
      "leftLabel": "BEFORE",
      "rightLabel": "AFTER",
      "voiceover": "Where old gateways burn two hundred milliseconds per request, it answers in twenty.",
      "searchQuery": "server rack data center blue",
      "videoQuery": "network latency dashboard screen",
      "durationInFrames": 175,
      "textAnimation": "fade-up"
    }},
    {{
      "type": "countdown",
      "title": "AND IT DOESN'T FLINCH",
      "text": "requests per second",
      "countFrom": 0,
      "countTo": 50000,
      "countSuffix": "+",
      "voiceover": "It holds that speed all the way to fifty thousand requests a second before it even breaks a sweat.",
      "searchQuery": "network switch cables closeup",
      "videoQuery": "data flowing network nodes motion",
      "durationInFrames": 200,
      "textAnimation": "none"
    }},
    {{
      "type": "list",
      "title": "ZERO SETUP TAX",
      "text": "Auto-scaling|Edge cache|Zero-config SSL|Live analytics",
      "voiceover": "None of it needs configuring — scaling, global caching, certificates and traffic dashboards all switch on the moment you deploy.",
      "searchQuery": "modern software dashboard screen",
      "videoQuery": "software dashboard ui scrolling",
      "durationInFrames": 210,
      "textAnimation": "slide-in"
    }},
    {{
      "type": "testimonial",
      "title": "FROM THE LAUNCH BENCHMARKS",
      "text": "1,000,000 requests. 20ms median.",
      "subtitle": "HyperAPI",
      "voiceover": "That's not a marketing number — the published benchmark ran a million real requests and held a twenty-millisecond median.",
      "searchQuery": "server racks glowing data center",
      "videoQuery": "server racks blinking data center",
      "durationInFrames": 175,
      "textAnimation": "word-by-word"
    }},
    {{
      "type": "cta",
      "title": "PUT IT IN FRONT OF YOUR API",
      "text": "free tier, no card",
      "ctaText": "TRY FREE NOW",
      "voiceover": "Drop it in front of your API today — the free tier needs no credit card, just a deploy.",
      "searchQuery": "developer laptop code night",
      "videoQuery": "developer typing code laptop",
      "durationInFrames": 170,
      "textAnimation": "fade-up"
    }}
  ],
  "pipeline": {{ "outputFormat": "mp4", "quality": "standard" }}
}}

=== EXAMPLE 2 (Lifestyle/Tips topic) ===
Topic: "5 morning habits that changed my life"

{{
  "theme": {{
    "primaryColor": "#10b981",
    "secondaryColor": "#f59e0b",
    "overlayType": "particles",
    "fontFamilyName": "Inter",
    "musicTrack": "lofi-chill",
    "cameraMotion": "ken-burns",
    "subtitlePosition": "bottom",
    "overlayOpacity": 0.7,
    "transitionStyle": "slide-left",
    "aspectRatio": "9:16",
    "gradientOverlay": "top-to-bottom"
  }},
  "scenes": [
    {{
      "type": "hero",
      "title": "5 MORNING HABITS",
      "text": "before 8am",
      "subtitle": "the two-week reset",
      "voiceover": "Five small moves before eight a.m. rewired my focus in about two weeks — steal them.",
      "searchQuery": "sunrise golden light bedroom window",
      "videoQuery": "sunrise bedroom window morning light",
      "durationInFrames": 130,
      "textAnimation": "fade-up"
    }},
    {{
      "type": "split",
      "title": "COLD SHOWER",
      "text": "2 minutes",
      "secondaryText": "+alertness",
      "voiceover": "First one is brutal: two minutes under cold water wakes you up harder than any coffee.",
      "searchQuery": "water droplets shower close up",
      "videoQuery": "cold shower water splash slow motion",
      "durationInFrames": 165,
      "textAnimation": "slide-in"
    }},
    {{
      "type": "split",
      "title": "GRATITUDE, 3 LINES",
      "text": "before you touch the phone",
      "voiceover": "Then, before your thumb ever finds the phone, write down three specific things you're grateful for.",
      "searchQuery": "notebook pen coffee morning table",
      "videoQuery": "hand writing journal notebook closeup",
      "durationInFrames": 165,
      "textAnimation": "typewriter"
    }},
    {{
      "type": "countdown",
      "title": "MINUTES THAT COUNT",
      "text": "of quiet breathing",
      "countFrom": 0,
      "countTo": 10,
      "countSuffix": " min",
      "voiceover": "Next, sit and breathe — ten slow minutes drops your stress baseline for the entire day.",
      "searchQuery": "person meditating peaceful nature",
      "videoQuery": "person meditating breathing calm",
      "durationInFrames": 190,
      "textAnimation": "none"
    }},
    {{
      "type": "list",
      "title": "THE FULL STACK",
      "text": "Cold shower|Gratitude|10-min sit|Phone-free hour|Real breakfast",
      "voiceover": "Add a phone-free first hour and a breakfast with actual protein, and the five lock together into one routine.",
      "searchQuery": "healthy breakfast fruit table bright",
      "videoQuery": "healthy breakfast table morning hands",
      "durationInFrames": 210,
      "textAnimation": "slide-in"
    }},
    {{
      "type": "cta",
      "title": "START TOMORROW",
      "text": "day 1 of 14",
      "ctaText": "SAVE & TRY",
      "voiceover": "Save this, run it for fourteen days, and watch your mornings stop running you.",
      "searchQuery": "happy person stretching morning sun",
      "videoQuery": "person stretching sunrise energetic",
      "durationInFrames": 170,
      "textAnimation": "word-by-word"
    }}
  ],
  "pipeline": {{ "outputFormat": "mp4", "quality": "standard" }}
}}

Now generate the JSON for: "{user_request}"
Output ONLY the raw JSON object:"""


# --- Allowed enum values (must match Remotion component schemas exactly) ---
ALLOWED_OVERLAY_TYPES = ["grid-hud", "particles", "clean", "vhs-glitch", "fantasy-sparks", "aurora"]
ALLOWED_FONTS = ["Share Tech Mono", "Orbitron", "Inter", "Playfair Display", "Courier New"]
ALLOWED_MUSIC = ["ambient-tech", "lofi-chill", "cosmic-synth", "none"]
ALLOWED_CAMERA = ["ken-burns", "pan-horizontal", "zoom-slow", "static", "dynamic-zoom-rotate", "pan-tilt", "pulse-zoom", "glitch-shift", "orbit-drift", "vertigo"]
ALLOWED_SUBTITLE_POS = ["top", "center", "bottom"]
ALLOWED_SCENE_TYPES = ["hero", "testimonial", "metric", "split", "countdown", "comparison", "list", "cta", "bar-chart", "chart", "line-chart", "rating", "ui-demo"]
ALLOWED_TRANSITIONS = ["crossfade", "slide-left", "zoom-through", "glitch-cut", "wipe-down", "iris-open", "blur-dissolve", "scale-rotate", "push-up", "spin-blur", "none"]
ALLOWED_ASPECT_RATIOS = ["9:16", "16:9", "1:1", "4:5"]
ALLOWED_GRADIENTS = ["none", "top-to-bottom", "radial-center", "diagonal"]
ALLOWED_TEXT_ANIMATIONS = ["typewriter", "glitch-decode", "fade-up", "slide-in", "word-by-word", "scale-pop", "blur-in", "wave", "none"]


# =============================================================================
# VARIETY & RANDOMNESS ENGINE
# -----------------------------------------------------------------------------
# Everything below exists so that NO two generated videos share the same look
# or flow. A single per-video `seed` (derived from the session id) drives:
#   1. A cohesive "style pack" (colors/overlay/font/music) for auto channels.
#   2. Aesthetic flavor (gradient, subtitle position) for every video.
#   3. The Remotion render layer (transitions, camera, shape motion, text
#      animations) — the seed is emitted into props.json and combined with the
#      scene index inside the React components, so the whole per-scene sequence
#      differs between videos even when the theme and scene count are identical.
#   4. A rotating social "hook" directive injected into the LLM prompt.
# =============================================================================

def _derive_seed(session_id: str) -> int:
    """Stable 31-bit seed derived from the session id.

    session_id is unique per video, so this yields a unique-but-deterministic
    seed. Deterministic matters: Remotion renders frames concurrently and bans
    Math.random(), so all render-time variety must come from a fixed seed.
    """
    import hashlib
    h = hashlib.md5((session_id or "default").encode("utf-8")).hexdigest()
    return int(h[:8], 16) & 0x7FFFFFFF


# Curated, cohesive design systems. Each pack is internally consistent so a
# video always looks intentional; picking one per video (seeded) gives wide
# variety between videos. Used to break the "every auto video looks identical"
# problem — the automated channel previously hard-coded a single cyberpunk look.
STYLE_PACKS = [
    {"name": "cyber-neon",     "primaryColor": "#00f0ff", "secondaryColor": "#ff007f", "overlayType": "grid-hud",       "fontFamilyName": "Share Tech Mono", "musicTrack": "ambient-tech", "gradientOverlay": "radial-center"},
    {"name": "synth-sunset",   "primaryColor": "#ff2d95", "secondaryColor": "#ffb300", "overlayType": "vhs-glitch",     "fontFamilyName": "Orbitron",        "musicTrack": "cosmic-synth", "gradientOverlay": "diagonal"},
    {"name": "matrix-green",   "primaryColor": "#00ff9c", "secondaryColor": "#0affef", "overlayType": "grid-hud",       "fontFamilyName": "Share Tech Mono", "musicTrack": "ambient-tech", "gradientOverlay": "top-to-bottom"},
    {"name": "royal-violet",   "primaryColor": "#8b5cf6", "secondaryColor": "#ec4899", "overlayType": "aurora",         "fontFamilyName": "Orbitron",        "musicTrack": "cosmic-synth", "gradientOverlay": "radial-center"},
    {"name": "ice-electric",   "primaryColor": "#38bdf8", "secondaryColor": "#818cf8", "overlayType": "particles",      "fontFamilyName": "Inter",           "musicTrack": "ambient-tech", "gradientOverlay": "top-to-bottom"},
    {"name": "ember-gold",     "primaryColor": "#ff6b35", "secondaryColor": "#ffd700", "overlayType": "aurora",         "fontFamilyName": "Orbitron",        "musicTrack": "cosmic-synth", "gradientOverlay": "diagonal"},
    {"name": "mint-aqua",      "primaryColor": "#00d4aa", "secondaryColor": "#06b6d4", "overlayType": "particles",      "fontFamilyName": "Inter",           "musicTrack": "lofi-chill",   "gradientOverlay": "none"},
    {"name": "crimson-mono",   "primaryColor": "#ff3b3b", "secondaryColor": "#ffffff", "overlayType": "vhs-glitch",     "fontFamilyName": "Courier New",     "musicTrack": "ambient-tech", "gradientOverlay": "top-to-bottom"},
    {"name": "cosmic-fantasy", "primaryColor": "#a78bfa", "secondaryColor": "#22d3ee", "overlayType": "fantasy-sparks", "fontFamilyName": "Playfair Display","musicTrack": "cosmic-synth", "gradientOverlay": "radial-center"},
    {"name": "clean-cobalt",   "primaryColor": "#3b82f6", "secondaryColor": "#00d4aa", "overlayType": "clean",          "fontFamilyName": "Inter",           "musicTrack": "ambient-tech", "gradientOverlay": "diagonal"},
    {"name": "toxic-lime",     "primaryColor": "#a3e635", "secondaryColor": "#22d3ee", "overlayType": "grid-hud",       "fontFamilyName": "Orbitron",        "musicTrack": "ambient-tech", "gradientOverlay": "none"},
    {"name": "aurora-teal",    "primaryColor": "#2dd4bf", "secondaryColor": "#c084fc", "overlayType": "aurora",         "fontFamilyName": "Inter",           "musicTrack": "cosmic-synth", "gradientOverlay": "radial-center"},
    # --- Non-tech aesthetics: editorial / warm / pastel / natural / vintage ---
    # These deliberately avoid the neon-on-dark "cyberpunk" feel so the channel
    # doesn't read as the same sci-fi template every post.
    {"name": "editorial-serif",  "primaryColor": "#f4f1ea", "secondaryColor": "#c9a227", "overlayType": "clean",          "fontFamilyName": "Playfair Display", "musicTrack": "lofi-chill",   "gradientOverlay": "none"},
    {"name": "terracotta-earth", "primaryColor": "#e07a5f", "secondaryColor": "#f2cc8f", "overlayType": "clean",          "fontFamilyName": "Playfair Display", "musicTrack": "lofi-chill",   "gradientOverlay": "top-to-bottom"},
    {"name": "sage-botanical",   "primaryColor": "#a3c9a8", "secondaryColor": "#e9f5db", "overlayType": "particles",      "fontFamilyName": "Inter",            "musicTrack": "lofi-chill",   "gradientOverlay": "none"},
    {"name": "coral-pop",        "primaryColor": "#ff6f61", "secondaryColor": "#ffd166", "overlayType": "particles",      "fontFamilyName": "Inter",            "musicTrack": "lofi-chill",   "gradientOverlay": "diagonal"},
    {"name": "sunset-peach",     "primaryColor": "#ffb4a2", "secondaryColor": "#ffcdb2", "overlayType": "aurora",         "fontFamilyName": "Playfair Display", "musicTrack": "lofi-chill",   "gradientOverlay": "radial-center"},
    {"name": "golden-hour",      "primaryColor": "#ffb703", "secondaryColor": "#fb8500", "overlayType": "aurora",         "fontFamilyName": "Playfair Display", "musicTrack": "cosmic-synth", "gradientOverlay": "diagonal"},
    {"name": "cherry-blossom",   "primaryColor": "#ffafcc", "secondaryColor": "#cdb4db", "overlayType": "fantasy-sparks", "fontFamilyName": "Playfair Display", "musicTrack": "lofi-chill",   "gradientOverlay": "radial-center"},
    {"name": "forest-moss",      "primaryColor": "#74c69d", "secondaryColor": "#d8f3dc", "overlayType": "clean",          "fontFamilyName": "Inter",            "musicTrack": "lofi-chill",   "gradientOverlay": "top-to-bottom"},
    {"name": "ocean-breeze",     "primaryColor": "#48cae4", "secondaryColor": "#ade8f4", "overlayType": "particles",      "fontFamilyName": "Inter",            "musicTrack": "lofi-chill",   "gradientOverlay": "none"},
    {"name": "desert-dune",      "primaryColor": "#dda15e", "secondaryColor": "#fefae0", "overlayType": "clean",          "fontFamilyName": "Playfair Display", "musicTrack": "lofi-chill",   "gradientOverlay": "diagonal"},
    {"name": "burgundy-luxe",    "primaryColor": "#ff4d6d", "secondaryColor": "#ffb3c1", "overlayType": "aurora",         "fontFamilyName": "Playfair Display", "musicTrack": "cosmic-synth", "gradientOverlay": "radial-center"},
    {"name": "mono-brutalist",   "primaryColor": "#ffffff", "secondaryColor": "#fca311", "overlayType": "clean",          "fontFamilyName": "Courier New",      "musicTrack": "none",         "gradientOverlay": "none"},
    {"name": "lavender-haze",    "primaryColor": "#cdb4db", "secondaryColor": "#a2d2ff", "overlayType": "aurora",         "fontFamilyName": "Inter",            "musicTrack": "lofi-chill",   "gradientOverlay": "radial-center"},
    {"name": "citrus-fresh",     "primaryColor": "#f4d35e", "secondaryColor": "#ee964b", "overlayType": "particles",      "fontFamilyName": "Inter",            "musicTrack": "lofi-chill",   "gradientOverlay": "none"},
    {"name": "slate-editorial",  "primaryColor": "#e2e8f0", "secondaryColor": "#f59e0b", "overlayType": "clean",          "fontFamilyName": "Inter",            "musicTrack": "lofi-chill",   "gradientOverlay": "top-to-bottom"},
    {"name": "rosewood-vintage", "primaryColor": "#b5838d", "secondaryColor": "#ffcdb2", "overlayType": "vhs-glitch",     "fontFamilyName": "Playfair Display", "musicTrack": "lofi-chill",   "gradientOverlay": "top-to-bottom"},
]

# Proven scroll-stopping opening patterns for short-form social video. One is
# picked per video (seeded) and injected into the LLM prompt so the very first
# scene grabs attention in the first ~1 second (critical for reels/shorts).
#
# Informed by how the Instagram Reels algorithm ranks content: the "3-second
# hold" is the strongest early ranking signal (Reels with >60% 3s-hold reach
# 5-10x further than <40%), and up to ~50% of viewers drop off inside the
# first 3 seconds. Meta's creator guidance: the hook must communicate the
# video's VALUE in the first frame (not act as an intro), with on-screen text
# from frame one, and be specific rather than general. Each pattern below
# includes a fill-in-the-blank template the LLM can adapt to the topic.
HOOK_PATTERNS = [
    "PATTERN-INTERRUPT: open with an unexpected, punchy 2-4 word statement that makes viewers stop scrolling (template: 'This changes everything' / 'Delete this app').",
    "SHOCK-STAT: open with a surprising, concrete number that sounds almost unbelievable but is plausible (template: '92% of devs miss this').",
    "PROVOCATIVE QUESTION: open with a bold question that challenges the viewer's assumptions and demands an answer (template: 'Why is nobody using ___?').",
    "CONTRARIAN CLAIM: open with a confident, against-the-grain statement that contradicts common belief (template: '___ is dead. Here's what replaced it').",
    "CURIOSITY GAP: tease a surprising outcome or secret without revealing it, forcing viewers to keep watching (template: 'The last one surprised even me').",
    "PAIN-POINT 'YOU': name a frustration the viewer personally feels, using the word 'you' (template: 'You're wasting hours on ___').",
    "MISTAKE CALLOUT: tell the viewer they're doing something wrong — instant self-check reflex (template: 'You've been using ___ wrong').",
    "INSIDER SECRET: open with forbidden-knowledge energy (template: 'This feels illegal to know' / 'What they don't tell you about ___').",
    "BOLD PROMISE: promise a specific, valuable payoff for watching to the end (template: 'Save 10 hours a week with this').",
    "URGENCY: a 'right now / before it's too late' framing that makes the topic feel time-sensitive (template: 'Do this before ___ changes').",
    "STORY-TEASE: open mid-action with a mini cliffhanger that sets up a fast payoff (template: 'I almost lost everything doing this').",
    "TIMEFRAME-COMPRESSION: compress a big transformation into a tiny window (template: '3 years of lessons in 30 seconds').",
    "HYPER-SPECIFIC RELATABILITY: describe an oddly specific moment the target viewer instantly recognizes (template: 'If you've ever ___ at 2am...').",
    "NEGATIVE WARNING: lead with what to STOP doing — loss-aversion beats gain framing (template: 'Stop doing ___ immediately').",
    "BREAKING-NEWS: frame the topic as a just-dropped development (template: 'This just changed ___ forever').",
    "CHALLENGE-DARE: dare the viewer to make it to the payoff (template: 'Bet you can't guess #1').",
    "HIGH-STAKES BENCHMARK: lead with an unexpected benchmark or architectural outcome (template: 'We replaced ___ and latency dropped 80%').",
    "SENIOR VS JUNIOR: contrast how junior vs senior engineers approach the topic (template: 'Senior devs do THIS instead of ___').",
    "FORBIDDEN ARCHITECTURE: frame as a little-known developer secret (template: 'The secret feature in ___ that feels illegal to know').",
    "STOP-SCROLLING TECH: target developers directly inside the first 2 words (template: 'Stop scrolling if you build apps in 2026').",
]



def build_variety_directive(seed: int, is_auto_channel: bool = False,
                            meta_out: Optional[dict] = None) -> str:
    """Build a seeded 'creative brief' appended to the LLM user prompt.

    Injects a rotating opening-hook style plus randomized structural guidance
    (scene count, pacing, animation spread) so repeated or similar prompts do
    not collapse into the same script. Kept short and directive for small
    open-source models.

    When `meta_out` is given, the chosen hook label and scene-count target are
    written into it so the render can record them in the post ledger.
    """
    rnd = random.Random(seed)
    hook, hook_mode = _feedback_weighted_choice(
        HOOK_PATTERNS, lambda h: h.split(":")[0].strip(), "hooks", rnd, get_feedback_stats())
    scene_count = rnd.choice([4, 5, 5, 6, 6, 7])
    if meta_out is not None:
        meta_out["hook_type"] = hook.split(":")[0].strip()
        meta_out["scene_count_target"] = scene_count
    if hook_mode != "cold":
        print(f"[variety] hook='{hook.split(':')[0].strip()}' mode={hook_mode}")
    # A seeded, shuffled palette of scene types to encourage a varied middle
    middle_types = ["split", "metric", "list", "comparison", "countdown", "testimonial"]
    rnd.shuffle(middle_types)
    suggested = ", ".join(middle_types[:3])
    closers = ["cta", "hero", "split"]
    closer = rnd.choice(closers)
    pacing = rnd.choice([
        "fast and punchy — keep most scenes short (3-5s)",
        "cinematic — let a couple of key scenes breathe (6-8s)",
        "high-energy — rapid cuts with one big payoff scene",
    ])

    return f"""

=== CREATIVE BRIEF (follow this to make THIS video unique) ===
- OPENING HOOK: {hook}
  The FIRST scene must deliver this hook. Make it impossible to scroll past.
  ALGORITHM RULES for the first scene (Instagram ranks Reels by 3-second hold — half of viewers decide to leave within 3 seconds):
  * The first scene's "text" IS the hook: max 8 words, readable in under 1 second, on screen from the very first frame.
  * The first scene's "voiceover" must SPEAK the hook immediately in max 12 words. NO greetings, NO "welcome", NO "in this video", NO "today we'll" — start mid-value. A short voiceover also keeps the hook scene fast (scene length auto-syncs to speech).
  * Be hyper-specific: real numbers, names, concrete outcomes. Generic openers kill retention.
  * The viewer must know within 2 seconds what they GET by watching to the end.
- TARGET LENGTH: about {scene_count} scenes total.
- SCENE VARIETY: build the middle using a mix of these scene types where they fit the content: {suggested}. Do NOT use the same scene type back-to-back.
- CLOSER: end with a "{closer}" scene that pays off the hook and drives the next action.
- PACING: {pacing}.
- ANIMATION: give each scene a DIFFERENT textAnimation from the allowed list — never repeat the same animation on consecutive scenes.
- NO REPEATING THE HEADLINE: name the subject in scene 1 ONLY; after that say "it" / "the tool" / "the team". The subtitles show every spoken word, so a restated line gets read AND heard 5-6 times and feels cheap.
- EVERY SCENE ADDS SOMETHING NEW: no scene may re-explain a point an earlier scene already made — keep pushing the story forward.
- ON-SCREEN ≠ SPOKEN: the on-screen "text" is a short label (a keyword or number); the "voiceover" is the sentence. Never put the same words in both.
- ARC: hook → why it matters → the surprising detail → one concrete payoff. Plant a small open loop in scene 1 and close it at the end so viewers stay for the finish.
- Keep it fresh: avoid clichés; make word choices specific and concrete.
- INTEGRITY (overrides everything above): NO invented people, names, quotes, testimonials, or statistics — see the FACT INTEGRITY RULES."""


def apply_style_director(theme: dict, seed: int, is_auto_channel: bool, forced_keys: Optional[set] = None) -> Optional[str]:
    """Seeded post-processor that maximizes visual variety between videos.

    - Emits the per-video `seed` into the theme so the Remotion render layer
      can vary its per-scene flow (transitions/camera/shapes/text-anims).
    - For automated channels (no human art-directing), rotates a full cohesive
      STYLE_PACK so the channel stops looking identical every post.
    - For all videos, gently rotates purely-aesthetic dimensions (gradient,
      subtitle position) that are safe to change regardless of topic.

    Never overrides a dimension the caller explicitly forced (forced_keys).
    Mutates `theme` in place and returns the chosen style-pack NAME (None
    outside auto channels) for the post ledger — the name must not go into
    `theme` itself, which flows into the render props schema.
    """
    forced_keys = forced_keys or set()
    rnd = random.Random(seed)

    pack_name = None
    if is_auto_channel:
        # Feedback-weighted rotation: identical to the legacy rnd.choice on
        # cold start; with enough scored posts, better-performing packs get
        # picked more often (epsilon floor keeps every pack in rotation).
        pack, pick_mode = _feedback_weighted_choice(
            STYLE_PACKS, lambda p: p["name"], "styles", rnd, get_feedback_stats())
        pack_name = pack["name"]
        for key, value in pack.items():
            if key == "name":
                continue
            if key not in forced_keys:
                theme[key] = value
        print(f"[style-director] seed={seed} pack={pack['name']} mode={pick_mode}")

    # Aesthetic flavor for EVERY video (safe regardless of topic)
    if "gradientOverlay" not in forced_keys:
        theme["gradientOverlay"] = rnd.choice(ALLOWED_GRADIENTS)
    if "subtitlePosition" not in forced_keys:
        theme["subtitlePosition"] = rnd.choices(
            ["bottom", "top", "center"], weights=[6, 2, 2]
        )[0]

    # The render-layer variety seed — the single most important field.
    theme["seed"] = seed
    return pack_name


def _fuzzy_match(value: str, allowed: List[str], default: str) -> str:
    """Find the closest match for a value in the allowed list.
    
    Small models often produce close-but-wrong enum values like:
      - "grid_hud" instead of "grid-hud"
      - "VHS Glitch" instead of "vhs-glitch"
      - "share-tech-mono" instead of "Share Tech Mono"
    
    This function handles all those cases gracefully.
    """
    if not value or not isinstance(value, str):
        return default
    
    # Exact match
    if value in allowed:
        return value
    
    # Case-insensitive exact match
    value_lower = value.lower().strip()
    for a in allowed:
        if a.lower() == value_lower:
            return a
    
    # Normalized match (replace underscores/spaces with hyphens)
    value_normalized = value_lower.replace("_", "-").replace(" ", "-")
    for a in allowed:
        if a.lower().replace("_", "-").replace(" ", "-") == value_normalized:
            return a
    
    # Substring containment (e.g. "hud" matches "grid-hud")
    for a in allowed:
        if value_lower in a.lower() or a.lower() in value_lower:
            return a
    
    # difflib closest match
    matches = difflib.get_close_matches(value_lower, [a.lower() for a in allowed], n=1, cutoff=0.4)
    if matches:
        for a in allowed:
            if a.lower() == matches[0]:
                return a
    
    return default


def _validate_hex_color(value: str, default: str) -> str:
    """Validate and fix hex color strings."""
    if not value or not isinstance(value, str):
        return default
    value = value.strip()
    # Add # prefix if missing
    if re.match(r'^[0-9a-fA-F]{3,8}$', value):
        value = '#' + value
    # Validate hex format
    if re.match(r'^#[0-9a-fA-F]{3}$', value) or re.match(r'^#[0-9a-fA-F]{6}$', value) or re.match(r'^#[0-9a-fA-F]{8}$', value):
        return value
    return default


def _clamp_int(value, min_val: int, max_val: int, default: int) -> int:
    """Clamp a value to a range, with type coercion."""
    try:
        v = int(value)
        return max(min_val, min(max_val, v))
    except (TypeError, ValueError):
        return default


def _clamp_float(value, min_val: float, max_val: float, default: float) -> float:
    """Clamp a float value to a range."""
    try:
        v = float(value)
        return max(min_val, min(max_val, v))
    except (TypeError, ValueError):
        return default


def _truncate_str(value, max_words: int) -> str:
    """Truncate a string to max_words."""
    if not value or not isinstance(value, str):
        return ""
    words = value.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return value


def get_available_cores() -> int:
    """Determine the maximum concurrency allowed by Remotion/Node.js.
    
    Tries:
    1. Querying Remotion's own getCpuCount utility via Node.js (100% accurate, cgroup-aware)
    2. Fallback to reading cgroups v1 / v2 limits in Python
    3. Fallback to os.cpu_count() or 1
    """
    # Try querying Node/Remotion helper directly
    try:
        import subprocess
        # Get path relative to the app directory
        js_path = "./node_modules/@remotion/renderer/dist/get-cpu-count.js"
        if os.path.exists(js_path):
            res = subprocess.run(
                ["node", "-e", f"console.log(require('{js_path}').getCpuCount())"],
                capture_output=True, text=True, timeout=5, check=True
            )
            val = int(res.stdout.strip())
            if val > 0:
                return val
    except Exception as e:
        pass

    # Fallback 1: Python detection with cgroups v1
    cores = os.cpu_count() or 1
    try:
        if os.path.exists("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"):
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
                quota = int(f.read().strip())
            with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
                period = int(f.read().strip())
            if quota > 0 and period > 0:
                import math
                cgroup_cores = int(math.ceil(quota / period))
                cores = min(cores, cgroup_cores)
    except Exception:
        pass

    # Fallback 2: Python detection with cgroups v2
    try:
        if os.path.exists("/sys/fs/cgroup/cpu.max"):
            with open("/sys/fs/cgroup/cpu.max") as f:
                parts = f.read().strip().split()
                if len(parts) == 2 and parts[0] != "max":
                    quota = int(parts[0])
                    period = int(parts[1])
                    if quota > 0 and period > 0:
                        import math
                        cgroup_cores = int(math.ceil(quota / period))
                        cores = min(cores, cgroup_cores)
    except Exception:
        pass

    return max(1, cores)


def _fix_placeholder_values(text: str) -> str:
    """Rewrite placeholder patterns like X%, $X, N+, [number] into honest qualitative wording.

    Small LLMs often produce literal placeholders when they don't know exact stats.
    A placeholder means the model had NO real number — so we must never substitute an
    invented one (a made-up "47%" rendered as fact is a fabrication, the same class of
    failure as an invented person). Instead, de-quantify the sentence.
    """
    if not text or not isinstance(text, str):
        return text

    # Pattern: "by X%" / "by XX%" inside a sentence → drop the fake precision
    text = re.sub(r'\bby\s+X{1,3}%', 'significantly', text, flags=re.IGNORECASE)

    # Pattern: standalone "X%" or "XX%"
    text = re.sub(r'\bX{1,3}%', 'a major share', text)

    # Pattern: "$X million/billion" → keep the order of magnitude only
    text = re.sub(r'\$X+(?:\.X+)?\s*(million|billion)', lambda m: m.group(1) + 's', text, flags=re.IGNORECASE)

    # Pattern: bare "$X" / "$XX" / "$X.X"
    text = re.sub(r'\$X+(?:\.X+)?', 'a serious amount', text)

    # Pattern: "N+" or "N+ users" (count placeholders)
    text = re.sub(r'\bN\+', 'thousands of', text)

    # Pattern: "[number]" or "[X]" or "[N]" (bracketed placeholders)
    text = re.sub(r'\[(?:number|X|N|x|n|value|stat|amount|count)\]', 'countless', text, flags=re.IGNORECASE)

    # Pattern: standalone "X" used as a multiplier like "Xx" or "X times"
    text = re.sub(r'\bXx\b', 'far', text)
    text = re.sub(r'\bX\s*times\b', 'several times', text)

    # Pattern: "increased by X" or "grew by X" (X without % but clearly a placeholder)
    text = re.sub(r'((?:increased|grew|dropped|rose|fell|improved|boosted|reduced|surged|jumped))\s+by\s+X\b',
                  lambda m: f"{m.group(1)} sharply", text, flags=re.IGNORECASE)

    # Collapse doubled spaces left behind by substitutions
    text = re.sub(r'\s{2,}', ' ', text).strip()

    return text


# =============================================================================
# FABRICATION GUARD
# -----------------------------------------------------------------------------
# Hard backstop against the LLM inventing people, quotes, or testimonials
# (e.g. "the lead developer John Doe says..."). The prompt forbids it; this
# layer guarantees it can never reach a rendered video, TTS voiceover,
# subtitle, caption, or upload metadata even if the model ignores the prompt.
# =============================================================================

# Names/entities that are ALWAYS fabricated in generated content. Includes the
# names used in this file's own few-shot examples, since small models parrot
# examples verbatim.
_FAKE_ENTITY_RE = re.compile(
    r"\b(?:john\s+doe|jane\s+doe|john\s+smith|jane\s+smith|joe\s+bloggs|"
    r"john\s+q\.?\s+public|max\s+mustermann|sarah\s+chen|alex\s+johnson|"
    r"lorem\s+ipsum|acme(?:\s+(?:corp(?:oration)?|inc|co|company))?|techcorp)\b",
    re.IGNORECASE,
)

_ROLE_WORDS = (
    r"(?:lead\s+|senior\s+|chief\s+|co[- ]?)?"
    r"(?:developer|engineer|founder|creator|maintainer|researcher|scientist|"
    r"architect|designer|analyst|expert|professor|ceo|cto|cio|coo|vp)"
)
_SAYS_VERBS = r"(?:says?|said|explains?|explained|claims?|claimed|notes?|noted|adds?|added|puts\s+it|told\s+us|writes?|wrote)"
_NAME_RE = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+"

# Role/verb parts match case-insensitively (scoped (?i:) groups) — but the
# name itself stays case-sensitive so ordinary lowercase prose is never eaten.
# "the lead developer John Doe says ..." / "CEO Jane Smith explains: ..."
_ROLE_NAME_SAYS_RE = re.compile(
    rf"(?i:the\s+)?(?i:{_ROLE_WORDS})\s+(?P<name>{_NAME_RE})\s+(?i:{_SAYS_VERBS})[,:]?\s*(?i:that\s+)?"
)
# "John Doe, CTO of TechCorp, says: ..." / "Jane Smith, founder at Acme, said ..."
_NAME_ROLE_SAYS_RE = re.compile(
    rf"(?P<name>{_NAME_RE}),\s+(?i:the\s+)?[A-Za-z .&-]{{2,40}}\s+(?i:of|at)\s+[A-Z][\w .&-]{{1,40}},?\s+(?i:{_SAYS_VERBS})[,:]?\s*(?i:that\s+)?"
)
# "according to John Doe, ..."
_ACCORDING_TO_RE = re.compile(
    rf"(?i:according\s+to)\s+(?P<name>{_NAME_RE})\s*(?i:{_SAYS_VERBS})?[,:]?\s*"
)
# "as John Doe puts it, ..." — the says-verb is mandatory here so comparisons
# like "use it as Docker Compose for GPUs" are never touched.
_AS_SAYS_RE = re.compile(
    rf"(?i:as)\s+(?P<name>{_NAME_RE})\s+(?i:{_SAYS_VERBS})[,:]?\s*"
)


def _scrub_fabricated_people(text: str, source_prompt: str = "", session_id: str = "", field: str = "") -> str:
    """Strip invented person attributions from generated text, keeping the claim itself.

    "the lead developer John Doe says the mesh routes tokens locally"
        -> "The mesh routes tokens locally"

    Names that appear in the user's own topic prompt are considered real and left
    untouched; everything else attributed with a says/according-to construction is
    treated as fabricated. Known placeholder entities are removed unconditionally.
    """
    if not text or not isinstance(text, str):
        return text
    original = text
    prompt_lower = (source_prompt or "").lower()

    def _strip_attribution(match: re.Match) -> str:
        name = match.groupdict().get("name") or ""
        if name and name.lower() in prompt_lower:
            return match.group(0)  # real person supplied by the user — keep
        return ""

    for pattern in (_ROLE_NAME_SAYS_RE, _NAME_ROLE_SAYS_RE, _ACCORDING_TO_RE, _AS_SAYS_RE):
        text = pattern.sub(_strip_attribution, text)

    # Any known-fake entity that survived (e.g. "John Doe's framework") — neutralize.
    text = _FAKE_ENTITY_RE.sub("the team", text)

    # Tidy up: collapse spaces, fix orphaned punctuation, recapitalize sentence starts.
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"^[,:;\s]+", "", text)
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    if text != original:
        print(f"[{session_id}] FABRICATION BLOCKED in {field or 'text'}: {original!r} -> {text!r}")
    return text


_PERSON_NAME_ONLY_RE = re.compile(rf"^\s*(?:{_NAME_RE})\s*$")
_ROLE_TITLE_RE = re.compile(rf"{_ROLE_WORDS}", re.IGNORECASE)


def _sanitize_testimonial_scene(scene: dict, source_prompt: str = "", session_id: str = "") -> None:
    """Ensure a testimonial scene never renders an invented person attribution.

    The testimonial layout renders `title` as the attribution line and `subtitle`
    as a name banner. Unless the name/role came from the user's own prompt, the
    scene is converted into an unattributed highlight.
    """
    prompt_lower = (source_prompt or "").lower()
    subtitle = scene.get("subtitle", "")
    title = scene.get("title", "")

    subtitle_is_fake_person = bool(
        subtitle
        and _PERSON_NAME_ONLY_RE.match(subtitle)
        and subtitle.lower() not in prompt_lower
    )
    title_is_fake_role = bool(
        title
        and _ROLE_TITLE_RE.search(title)
        and title.lower() not in prompt_lower
    )

    if subtitle_is_fake_person or title_is_fake_role:
        print(f"[{session_id}] FABRICATION BLOCKED: testimonial attribution "
              f"(title={title!r}, subtitle={subtitle!r}) — converting to unattributed highlight")
        scene.pop("subtitle", None)
        if title_is_fake_role:
            scene["title"] = "KEY TAKEAWAY"


# --- Anti-repetition guard --------------------------------------------------
# Small models restate the video's subject/headline in nearly every scene's
# voiceover. Because the karaoke overlay renders the WHOLE concatenated
# voiceover for the entire video, the viewer then reads (and hears) the same
# line 5-6 times — the single biggest "this feels redundant / cheap" complaint.
# They also echo the same phrase across a scene's title/text/subtitle, stacking
# it 3-4 times on one frame. These helpers detect and remove that repetition
# deterministically, as a safety net for when the prompt rules are ignored.

_DEDUP_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "at",
    "by", "with", "from", "as", "is", "are", "was", "were", "be", "been", "it",
    "its", "this", "that", "these", "those", "you", "your", "we", "our", "they",
    "their", "how", "what", "why", "who", "just", "now", "new", "here", "get",
    "into", "out", "up", "so", "not", "can", "will", "has", "have", "had",
}


def _dedup_norm(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy matching."""
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _dedup_tokens(s: str) -> set:
    """Content-word token set (stopwords removed) used for overlap scoring."""
    return {w for w in _dedup_norm(s).split() if w and w not in _DEDUP_STOPWORDS}


def _phrase_similarity(a: str, b: str) -> float:
    """Jaccard overlap of content tokens (0..1). ~1.0 means near-identical lines;
    two lines that merely share the subject word score low (that's fine — the
    subject SHOULD recur; only whole restated lines should be pruned)."""
    ta, tb = _dedup_tokens(a), _dedup_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _split_sentences(s: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+", (s or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _prune_redundant_scene_text(scenes: list, session_id: str = "") -> None:
    """Collapse cross-scene and within-scene text repetition, in place.

    1. Cross-scene voiceover: drop a spoken sentence that near-duplicates a
       sentence already used in an earlier scene (never emptying a scene).
    2. Within-scene: drop subtitle/secondaryText that just echoes the scene's
       own title or text.
    3. Cross-scene on-screen: blank a title that repeats an earlier title.
    The subject naturally recurs (low similarity); only whole restated lines go.
    """
    SENTENCE_SIM = 0.72   # whole-sentence restatement
    ONSCREEN_SIM = 0.7    # subtitle echoing title/text on the same frame
    TITLE_SIM = 0.85      # same headline reused on a later scene

    # 1. Cross-scene spoken-line de-duplication (the "same line 5-6 times" bug).
    seen_sentences: list = []
    for idx, scene in enumerate(scenes):
        vo = scene.get("voiceover", "")
        if not vo:
            continue
        sentences = _split_sentences(vo)
        kept: list = []
        for sent in sentences:
            is_dup = any(_phrase_similarity(sent, prev) >= SENTENCE_SIM for prev in seen_sentences)
            if is_dup:
                print(f"[{session_id}] Pruned repeated voiceover line (scene {idx}): {sent!r}")
                continue
            kept.append(sent)
            seen_sentences.append(sent)
        if not kept:
            # Whole scene was a restatement — keep its last line so it still speaks.
            kept = [sentences[-1]] if sentences else []
            if sentences:
                seen_sentences.append(sentences[-1])
        new_vo = " ".join(kept).strip()
        if new_vo != vo.strip():
            scene["voiceover"] = new_vo

    # 2. Within-scene on-screen echoes (same words stacked on one frame).
    for idx, scene in enumerate(scenes):
        title = scene.get("title", "")
        text = scene.get("text", "")
        for field in ("subtitle", "secondaryText"):
            val = scene.get(field)
            if not val:
                continue
            if (title and _phrase_similarity(val, title) >= ONSCREEN_SIM) or \
               (text and _phrase_similarity(val, text) >= ONSCREEN_SIM):
                print(f"[{session_id}] Dropped redundant on-screen {field} (scene {idx}): {val!r}")
                scene.pop(field, None)

    # 3. Cross-scene repeated headlines.
    seen_titles: list = []
    for idx, scene in enumerate(scenes):
        title = scene.get("title", "")
        if not title:
            continue
        if any(_phrase_similarity(title, t) >= TITLE_SIM for t in seen_titles):
            print(f"[{session_id}] Dropped duplicate title (scene {idx}): {title!r}")
            scene.pop("title", None)
        else:
            seen_titles.append(title)


# Tech-motion b-roll fallback: if the model didn't provide a topic-relevant
# videoQuery, at least pull TECH footage (not a random abstract loop) on the
# automated tech/news channels. Indexed by scene so clips stay varied.
_TECH_BROLL_TERMS = [
    "data center servers motion", "code on screen scrolling", "terminal typing commands",
    "network data flowing", "circuit board macro", "software dashboard ui",
    "server room lights", "developer coding laptop",
]
_TECH_SIGNAL_WORDS = {
    "code", "coding", "developer", "server", "servers", "data", "terminal", "screen",
    "dashboard", "circuit", "chip", "network", "gpu", "laptop", "computer", "software",
    "ui", "interface", "robot", "robotics", "tech", "cyber", "hacker", "monitor",
    "keyboard", "matrix", "digital", "app", "cloud", "ai", "algorithm",
}


def _build_broll_query(video_query: Optional[str], photo_query: str, idx: int,
                       is_tech_channel: bool) -> str:
    """Pick the search query for a scene's motion b-roll.

    Prefers the model's topic-relevant `videoQuery`; falls back to the (generic,
    photo-oriented) searchQuery, and on tech channels appends a tech-motion term
    so a missing videoQuery still yields tech footage instead of a stock loop.
    """
    vq = (video_query or "").strip()
    if len(_dedup_tokens(vq)) >= 2:
        return vq
    base = (vq or photo_query or "technology").strip()
    if is_tech_channel:
        toks = {w for w in re.split(r"\W+", base.lower()) if w}
        if not (toks & _TECH_SIGNAL_WORDS):
            base = f"{base} {_TECH_BROLL_TERMS[idx % len(_TECH_BROLL_TERMS)]}".strip()
    return base


# Tech-anchored STILL image terms — the photo twin of _TECH_BROLL_TERMS. The
# LLM's searchQuery is often abstract mood filler ("abstract speed light
# trails"), and on the tech channels an abstract query is what lets Pexels
# return forests/bokeh/nature ("random trees behind a Kubernetes video").
_TECH_IMAGE_TERMS = [
    "server room racks", "code on monitor closeup", "laptop terminal screen dark",
    "circuit board macro", "data center corridor", "software dashboard interface",
    "developer workstation screens", "computer chip closeup",
]


def _relevance_overlap(query: str, candidate_text: str) -> int:
    """Count content tokens shared by a search query and a candidate asset's
    descriptive text (Pexels URL slug / photo alt). Used to PREFER on-topic
    results — Pexels ranking is loose and can return an owl clip for a
    'release schedule screen' query (real case, 2026-07-18). Preference-sort
    only, never a hard filter, so an all-zero-overlap result set behaves
    exactly like before."""
    stop = {"the", "and", "for", "with", "from", "into", "over", "your"}
    q = {w for w in re.split(r"\W+", query.lower()) if len(w) > 2 and w not in stop}
    c = {w for w in re.split(r"\W+", (candidate_text or "").lower()) if len(w) > 2 and w not in stop}
    return len(q & c)


# Mood/style filler the LLM loves to lead with ("abstract dark technology").
# On stock APIs these words dominate ranking and pull mood footage (light
# trails, bokeh, lasers) instead of the subject — strip them on tech channels.
_MOOD_WORDS = {
    "abstract", "futuristic", "colorful", "dramatic", "beautiful", "cinematic",
    "moody", "epic", "aesthetic", "stylish", "artistic", "vibrant", "surreal",
}


def _build_scene_image_query(photo_query: str, video_query: Optional[str], idx: int,
                             is_tech_channel: bool) -> str:
    """Pick the search query for a scene's STILL background image.

    Mirrors _build_broll_query for photos: on tech channels, mood filler words
    are stripped, then a query with no tech signal word is swapped for the
    (topic-domain) videoQuery when that one IS tech-flavored, otherwise
    anchored with a per-scene tech term — so tech videos always search for
    tech imagery, never bare abstractions.
    """
    base = (photo_query or video_query or "").strip()
    if not base:
        return base
    if is_tech_channel:
        kept = [w for w in base.split() if w.lower() not in _MOOD_WORDS]
        base = " ".join(kept).strip() or base
        toks = {w for w in re.split(r"\W+", base.lower()) if w}
        if not (toks & _TECH_SIGNAL_WORDS):
            vq = (video_query or "").strip()
            vq_toks = {w for w in re.split(r"\W+", vq.lower()) if w}
            if vq_toks & _TECH_SIGNAL_WORDS:
                base = vq
            else:
                base = f"{base} {_TECH_IMAGE_TERMS[idx % len(_TECH_IMAGE_TERMS)]}".strip()
    return base


# Style-pack name fragment -> generation mood words, so AI-tier backgrounds
# stay cohesive with the seeded look instead of fighting it.
_STYLE_MOOD_WORDS = [
    ("noir", "black and white film noir mood, dramatic shadows"),
    ("neon", "neon-lit, moody, high contrast"),
    ("cyber", "neon-lit cyberpunk atmosphere, high contrast"),
    ("vapor", "vaporwave palette, dreamy haze"),
    ("retro", "retro analog aesthetic, subtle film grain"),
    ("editorial", "warm editorial style, soft natural light"),
    ("minimal", "clean minimalist composition, generous negative space"),
    ("broadcast", "crisp studio lighting, professional broadcast look"),
]


def _build_ai_image_prompt(query: str, style_name: Optional[str], is_tech_channel: bool) -> str:
    """Text-to-image prompt for the AI background tier.

    Built from the (already tech-anchored, fabrication-scrubbed) scene search
    query plus mood words from the video's style pack. The fixed suffix keeps
    output brand-safe for the accounts: no text/logos (they'd clash with the
    HUD overlays) and no recognizable faces (fabricated-person risk).
    """
    mood = "cinematic"
    low = (style_name or "").lower()
    for fragment, words in _STYLE_MOOD_WORDS:
        if fragment in low:
            mood = words
            break
    domain = "technology-themed, " if is_tech_channel else ""
    return (f"{query}, {domain}{mood}, vertical format editorial photograph, "
            f"cinematic lighting, high detail, no text, no watermark, no logos, "
            f"no recognizable faces")


def _clean_chart_data(raw, max_points: int = 8) -> list:
    """Normalize an LLM-provided chartData array into [{label, value}] with
    numeric values. Anything malformed (non-numeric value, empty label) is
    dropped rather than rendered — a chart scene with too few clean points is
    then degraded to a plain text scene by the caller (never fabricated)."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = item.get("label", item.get("name"))
        value = item.get("value", item.get("val"))
        if label is None or value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value != value or value in (float("inf"), float("-inf")):  # NaN/inf guard
            continue
        label = _truncate_str(str(label), 4).strip()
        if not label:
            continue
        out.append({"label": label, "value": value})
        if len(out) >= max_points:
            break
    return out


def _balanced_json_objects(text: str) -> list:
    """Every top-level balanced {...} slice in text (string/escape aware),
    largest first. Complements the greedy first-{-to-last-} regex, which
    breaks when prose after the JSON contains a stray brace."""
    objects = []
    depth = 0
    start = None
    in_str = False
    escaped = False
    for i, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = in_str
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start:i + 1])
                start = None
    objects.sort(key=len, reverse=True)
    return objects


def _coerce_llm_json(raw_text: str, session_id: str = "", quiet: bool = False):
    """Best-effort extraction of a JSON object from messy LLM output.

    Shared by parse_and_validate_script and the failover's output gate so
    'parseable' means exactly the same thing in both places — the gate must
    never reject output the parser could have recovered, or vice versa.
    Returns the parsed dict, or None when nothing can be recovered.
    """
    def _log(msg):
        if not quiet:
            print(f"[{session_id}] {msg}")

    raw = (raw_text or "").strip()
    if not raw:
        _log("WARN: No JSON object found in LLM output, using fallback")
        return None

    # Tier 1 — the UNTOUCHED text. Every repair below is lossy (regexes are
    # not string-aware and will mangle values containing '<think>', '//',
    # ', word:' etc.), so text that already parses must be returned verbatim.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Tier 2 — balanced {...} slices (largest first), WITHOUT lossy repairs.
    # Think-stripped text is tried before the raw text so a reasoning model's
    # final answer beats any draft JSON inside its <think> block; the raw pass
    # still recovers an object living wholly inside the think block.
    dethought = re.sub(r'<think>[\s\S]*?</think>', '', raw, flags=re.IGNORECASE)
    dethought = re.sub(r'^[\s\S]*?</think>', '', dethought, flags=re.IGNORECASE)
    seen = set()
    for source in (dethought, raw):
        for obj in _balanced_json_objects(source):
            if obj in seen:
                continue
            seen.add(obj)
            try:
                parsed = json.loads(obj)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    # Tier 3 — lossy repairs for genuinely malformed output.
    text = raw

    # Reasoning models (qwen3, r1 distills behind free routers) wrap their
    # answer in <think>...</think> chatter; drop paired blocks, then any
    # orphaned preamble ending in a lone closing tag.
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^[\s\S]*?</think>', '', text, flags=re.IGNORECASE)

    # Remove markdown code fences (```json ... ``` or ``` ... ```)
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)

    # Remove single-line JS comments (// ...)
    text = re.sub(r'//.*?\n', '\n', text)

    # Remove multi-line JS comments (/* ... */)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    # Remove control characters (except newline and tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # Fix trailing commas before } or ]
    text = re.sub(r',\s*([\]}])', r'\1', text)

    # Fix unquoted property names that some small models produce
    # e.g. { overlayType: "clean" } -> { "overlayType": "clean" }
    text = re.sub(r'(?<=\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r' "\1":', text)

    greedy = re.search(r'\{[\s\S]*\}', text)
    if not greedy:
        _log("WARN: No JSON object found in LLM output, using fallback")
        return None

    candidates = [greedy.group(0)]
    for obj in _balanced_json_objects(text):
        if obj not in candidates:
            candidates.append(obj)

    last_err = None
    for idx, json_str in enumerate(candidates):
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                return parsed
            continue
        except json.JSONDecodeError as e:
            if idx == 0:
                _log(f"WARN: JSON parse error: {e}. Attempting recovery...")
            # Aggressive fixes: single->double quotes, doubled commas
            json_str_fixed = json_str.replace("'", '"')
            json_str_fixed = re.sub(r',\s*,', ',', json_str_fixed)
            try:
                parsed = json.loads(json_str_fixed)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError as e2:
                last_err = e2
    _log(f"ERROR: JSON recovery failed: {last_err}. Using fallback.")
    return None


def parse_and_validate_script(raw_text: str, session_id: str = "", source_prompt: str = "") -> dict:
    """Parse LLM output into a valid video script JSON, fixing common errors.

    This function is designed to handle the messy output of small open-source
    models (1.5B-7B parameters). It:
      1. Strips markdown fences, comments, and control characters
      2. Fixes trailing commas and other JSON syntax issues
      3. Extracts the JSON object even if surrounded by text
      4. Validates every field against the allowed enums
      5. Fills in missing required fields with sensible defaults
      6. Clamps numeric values to valid ranges
      7. Truncates overly-long text fields
      8. Scrubs fabricated people/quotes and placeholder stats from every text
         field (source_prompt whitelists names the user themselves provided)

    Returns a fully valid dict ready to pass to Remotion.
    """
    parsed = _coerce_llm_json(raw_text, session_id=session_id)
    if not isinstance(parsed, dict):
        return _build_fallback_script()

    # Step 4: Validate and fix the theme object
    theme = parsed.get("theme", {})
    if not isinstance(theme, dict):
        theme = {}
    
    validated_theme = {
        "primaryColor": _validate_hex_color(theme.get("primaryColor"), "#00f0ff"),
        "secondaryColor": _validate_hex_color(theme.get("secondaryColor"), "#ff007f"),
        "overlayType": _fuzzy_match(theme.get("overlayType", ""), ALLOWED_OVERLAY_TYPES, "grid-hud"),
        "fontFamilyName": _fuzzy_match(theme.get("fontFamilyName", ""), ALLOWED_FONTS, "Inter"),
        "musicTrack": _fuzzy_match(theme.get("musicTrack", ""), ALLOWED_MUSIC, "none"),
        "cameraMotion": _fuzzy_match(theme.get("cameraMotion", ""), ALLOWED_CAMERA, "ken-burns"),
        "subtitlePosition": _fuzzy_match(theme.get("subtitlePosition", ""), ALLOWED_SUBTITLE_POS, "bottom"),
        "overlayOpacity": _clamp_float(theme.get("overlayOpacity", 0.8), 0.0, 1.0, 0.8),
        "transitionStyle": _fuzzy_match(theme.get("transitionStyle", ""), ALLOWED_TRANSITIONS, "crossfade"),
        "aspectRatio": _fuzzy_match(theme.get("aspectRatio", ""), ALLOWED_ASPECT_RATIOS, "9:16"),
        "gradientOverlay": _fuzzy_match(theme.get("gradientOverlay", ""), ALLOWED_GRADIENTS, "none"),
    }
    
    # Step 5: Validate and fix the scenes array
    raw_scenes = parsed.get("scenes", [])
    used_fallback_scenes = False
    if not isinstance(raw_scenes, list) or len(raw_scenes) == 0:
        print(f"[{session_id}] WARN: No valid scenes array found. Using fallback scenes.")
        raw_scenes = _build_fallback_script()["scenes"]
        used_fallback_scenes = True
    
    validated_scenes = []
    for i, scene in enumerate(raw_scenes):
        if not isinstance(scene, dict):
            continue
        
        scene_type = _fuzzy_match(scene.get("type", ""), ALLOWED_SCENE_TYPES, "hero" if i == 0 else "split")
        
        validated_scene = {
            "type": scene_type,
            "text": _truncate_str(scene.get("text", "Untitled Scene"), 30),
            "voiceover": _truncate_str(scene.get("voiceover", ""), 80),
            "searchQuery": _truncate_str(scene.get("searchQuery", ""), 6),
            "durationInFrames": _clamp_int(scene.get("durationInFrames", 175), 90, 300, 175),
        }
        
        # Optional fields — only include if provided
        # videoQuery drives the topic-relevant motion b-roll clip (backend-only —
        # never emitted to props, so no zod/TSX sync needed).
        if scene.get("videoQuery"):
            validated_scene["videoQuery"] = _truncate_str(scene["videoQuery"], 6)
        if scene.get("title"):
            validated_scene["title"] = _truncate_str(scene["title"], 8)
        if scene.get("subtitle"):
            validated_scene["subtitle"] = _truncate_str(scene["subtitle"], 10)
        if scene.get("secondaryText"):
            validated_scene["secondaryText"] = _truncate_str(scene["secondaryText"], 8)
        
        # Text animation per scene
        if scene.get("textAnimation"):
            validated_scene["textAnimation"] = _fuzzy_match(
                scene["textAnimation"], ALLOWED_TEXT_ANIMATIONS, "glitch-decode"
            )
        
        # Countdown scene fields
        if scene_type == "countdown":
            validated_scene["countFrom"] = _clamp_int(scene.get("countFrom", 0), -999999, 999999, 0)
            validated_scene["countTo"] = _clamp_int(scene.get("countTo", 100), -999999, 999999, 100)
            if scene.get("countSuffix"):
                validated_scene["countSuffix"] = _truncate_str(scene["countSuffix"], 3)
        
        # Comparison scene fields
        if scene_type == "comparison":
            if scene.get("leftLabel"):
                validated_scene["leftLabel"] = _truncate_str(scene["leftLabel"], 4)
            if scene.get("rightLabel"):
                validated_scene["rightLabel"] = _truncate_str(scene["rightLabel"], 4)
        
        # List scene fields
        if scene_type == "list":
            if scene.get("listItems") and isinstance(scene["listItems"], list):
                validated_scene["listItems"] = [_truncate_str(item, 10) for item in scene["listItems"][:8]]
        
        # CTA scene fields
        if scene_type == "cta":
            if scene.get("ctaText"):
                validated_scene["ctaText"] = _truncate_str(scene["ctaText"], 5)

        # UI-demo scene reuses existing text fields (title/text/subtitle/
        # listItems/ctaText) — no special data required, so it is always safe.
        if scene_type == "ui-demo":
            if scene.get("listItems") and isinstance(scene["listItems"], list):
                validated_scene["listItems"] = [_truncate_str(item, 8) for item in scene["listItems"][:4]]
            if scene.get("ctaText"):
                validated_scene["ctaText"] = _truncate_str(scene["ctaText"], 4)

        # Chart scene fields (bar-chart / chart / line-chart). A line chart needs
        # at least two points; bar/donut need one. If there isn't enough clean,
        # numeric data we DEGRADE to a text scene rather than draw an empty chart
        # or invent numbers (keeps the fabrication guarantee intact).
        if scene_type in ("bar-chart", "chart", "line-chart"):
            cleaned = _clean_chart_data(scene.get("chartData"))
            min_points = 2 if scene_type == "line-chart" else 1
            # A donut needs at least one POSITIVE share or it draws nothing; bar
            # and line degrade only on point count (a zero bar / flat line still
            # renders meaningfully).
            has_positive = any(c["value"] > 0 for c in cleaned)
            enough = len(cleaned) >= min_points and (scene_type != "chart" or has_positive)
            if enough:
                validated_scene["chartData"] = cleaned
            else:
                if cleaned:
                    validated_scene["type"] = "list"
                    validated_scene["listItems"] = [c["label"] for c in cleaned][:6]
                else:
                    validated_scene["type"] = "split"
                scene_type = validated_scene["type"]
                print(f"[{session_id}] Chart scene {i} lacked usable data — degraded to {scene_type}")

        # Rating scene field. Needs a real numeric score; otherwise degrade to
        # a text scene (never invent a rating).
        if scene_type == "rating":
            rmax = _clamp_int(scene.get("ratingMax", 5), 1, 10, 5)
            try:
                rv = float(scene.get("ratingValue"))
            except (TypeError, ValueError):
                rv = None
            if rv is not None and rv == rv:  # not NaN
                validated_scene["ratingValue"] = max(0.0, min(float(rmax), rv))
                validated_scene["ratingMax"] = rmax
            else:
                validated_scene["type"] = "split"
                scene_type = "split"
                print(f"[{session_id}] Rating scene {i} lacked a numeric score — degraded to split")

        # Ensure text field is not empty
        if not validated_scene["text"].strip():
            validated_scene["text"] = "Untitled Scene"
        
        validated_scenes.append(validated_scene)
    
    # Ensure we have at least 3 scenes
    if len(validated_scenes) < 3:
        print(f"[{session_id}] WARN: Only {len(validated_scenes)} scenes generated, padding to minimum 3")
        while len(validated_scenes) < 3:
            validated_scenes.append({
                "type": "split",
                "text": "Continue the journey",
                "searchQuery": "abstract dark background",
                "durationInFrames": 175,
            })
    
    # Cap at 10 scenes maximum to prevent runaway generation
    if len(validated_scenes) > 10:
        print(f"[{session_id}] WARN: Too many scenes ({len(validated_scenes)}), trimming to 10")
        validated_scenes = validated_scenes[:10]
    
    # Step 6: Validate pipeline config (optional)
    raw_pipeline = parsed.get("pipeline", {})
    validated_pipeline = None
    if isinstance(raw_pipeline, dict) and raw_pipeline:
        validated_pipeline = {
            "outputFormat": _fuzzy_match(raw_pipeline.get("outputFormat", ""), ["mp4", "webm", "gif"], "mp4"),
            "quality": _fuzzy_match(raw_pipeline.get("quality", ""), ["draft", "standard", "high"], "standard"),
        }
    
    # Step 7: Scrub placeholder stats AND fabricated people/quotes from every
    # text field — including voiceover, which feeds both TTS audio and the
    # karaoke subtitles, so nothing unchecked can be spoken or shown.
    for scene in validated_scenes:
        for text_field in ["text", "title", "subtitle", "secondaryText", "ctaText", "countSuffix", "voiceover"]:
            if scene.get(text_field):
                original = scene[text_field]
                fixed = _fix_placeholder_values(scene[text_field])
                fixed = _scrub_fabricated_people(fixed, source_prompt, session_id, f"scene.{text_field}")
                scene[text_field] = fixed
                if fixed != original:
                    print(f"[{session_id}] Sanitized scene {text_field}: '{original}' -> '{fixed}'")
        # Also fix list items if present
        if scene.get("listItems") and isinstance(scene["listItems"], list):
            scene["listItems"] = [
                _scrub_fabricated_people(_fix_placeholder_values(item), source_prompt, session_id, "scene.listItems")
                for item in scene["listItems"]
            ]
        # Chart labels are short categories rendered on-screen (bar/axis/segment)
        # — run them through the SAME placeholder + fabricated-entity scrub every
        # other visible text field gets, so a fabricated "Acme"/"Sarah Chen" can
        # never leak in as a chart label (peer of the listItems scrub above).
        if scene.get("chartData") and isinstance(scene["chartData"], list):
            for _c in scene["chartData"]:
                if isinstance(_c, dict) and _c.get("label"):
                    _c["label"] = _scrub_fabricated_people(
                        _fix_placeholder_values(str(_c["label"])),
                        source_prompt, session_id, "scene.chartData",
                    )
        # Testimonial layout renders title/subtitle as an attribution banner —
        # guarantee it never carries an invented person.
        if scene.get("type") == "testimonial":
            _sanitize_testimonial_scene(scene, source_prompt, session_id)
        # A metric scene whose big number was a scrubbed placeholder has no
        # number left to show — demote it to a plain split layout.
        if scene.get("type") == "metric" and not re.search(r"\d", scene.get("text", "")):
            print(f"[{session_id}] Metric scene has no real number after scrubbing — demoting to split")
            scene["type"] = "split"

    # Step 7b: Kill repetition. Small models restate the subject/headline in
    # every scene (the karaoke overlay then shows the same line 5-6 times) and
    # echo it across title/text/subtitle. This is the top "feels redundant"
    # complaint — prune it deterministically after all other fixes.
    _prune_redundant_scene_text(validated_scenes, session_id)

    result = {
        "theme": validated_theme,
        "scenes": validated_scenes,
    }
    if used_fallback_scenes:
        result["_isFallback"] = True
    if validated_pipeline:
        result["pipeline"] = validated_pipeline
    
    print(f"[{session_id}] Validated script: {len(validated_scenes)} scenes, "
          f"overlay={validated_theme['overlayType']}, font={validated_theme['fontFamilyName']}, "
          f"camera={validated_theme['cameraMotion']}, transition={validated_theme['transitionStyle']}, "
          f"aspect={validated_theme['aspectRatio']}, gradient={validated_theme['gradientOverlay']}")
    
    return result


def _build_fallback_script() -> dict:
    """Build a minimal valid script as an absolute last resort.

    Carries "_isFallback" so callers can tell canned filler apart from a real
    script — automated channels must abort rather than post it (its "Welcome /
    Stay tuned" scenes are exactly the platitude content the channel bans).
    """
    return {
        "_isFallback": True,
        "theme": {
            "primaryColor": "#00f0ff",
            "secondaryColor": "#ff007f",
            "overlayType": "grid-hud",
            "fontFamilyName": "Share Tech Mono",
            "musicTrack": "none",
            "cameraMotion": "ken-burns",
            "subtitlePosition": "bottom",
            "overlayOpacity": 0.8,
            "transitionStyle": "crossfade",
            "aspectRatio": "9:16",
            "gradientOverlay": "none",
        },
        "scenes": [
            {"type": "hero", "text": "Welcome", "searchQuery": "abstract dark technology", "durationInFrames": 175, "textAnimation": "glitch-decode"},
            {"type": "split", "text": "Exploring the topic", "searchQuery": "futuristic abstract art", "durationInFrames": 175, "textAnimation": "fade-up"},
            {"type": "hero", "text": "Stay tuned for more", "searchQuery": "colorful abstract light", "durationInFrames": 175, "textAnimation": "word-by-word"},
        ]
    }


# =============================================================================
# WEBHOOK CALLBACK UTILITY
# =============================================================================

def _send_webhook(webhook_url: str, payload: dict, session_id: str):
    """Fire-and-forget webhook POST. Runs in a background thread."""
    def _do_post():
        try:
            resp = requests.post(webhook_url, json=payload, timeout=30)
            print(f"[{session_id}] Webhook sent to {webhook_url}: status={resp.status_code}")
        except Exception as e:
            print(f"[{session_id}] Webhook failed: {e}")
    
    threading.Thread(target=_do_post, daemon=True).start()


# =============================================================================
# CORE RENDER PIPELINE
# =============================================================================

# =============================================================================
# LLM FAILOVER ENGINE
# =============================================================================
# Cross-call memory for one process/run: models a provider reports as gone stay
# gone, providers that reject their key stay skipped, and live model catalogs
# are fetched once. The pipeline calls the LLM several times per video (topic
# pick, script, caption), so permanent failures must not re-burn retries.
_LLM_DEAD_MODELS = set()        # {(provider_name, model_id)}
_LLM_DEAD_PROVIDERS = set()     # {provider_name}
_LLM_MODEL_CATALOG = {}         # {models_url: set(model_ids) or None}
_LLM_CATALOG_LOCK = threading.Lock()

# Models that can't do plain chat/JSON generation — never auto-substitute these
# from a provider catalog (r1/reasoning models emit <think> blocks that break
# the JSON parser downstream).
_LLM_NON_CHAT_RE = re.compile(
    r"whisper|tts|audio|embed|rerank|moderation|guard|vision|ocr|image|"
    r"distil|-r1|reason|think|compound|allam|saba", re.I)

# Router pseudo-models: catalog-listed ids that fan out to arbitrary models.
# Kept as emergency options only — never treated as a satisfied model list.
_LLM_ROUTER_PSEUDO_MODELS = {"openrouter/free", "openrouter/auto"}


def _llm_model_dead(prov_name, mid):
    """Dead-set membership tolerant of Gemini's 'models/' id alias — a model
    dead-marked under its bare request name must not be resurrected when
    discovery re-encounters it under its prefixed catalog id (or vice versa)."""
    bare = mid[7:] if mid.startswith("models/") else mid
    return ((prov_name, bare) in _LLM_DEAD_MODELS
            or (prov_name, f"models/{bare}") in _LLM_DEAD_MODELS)


def _llm_discovery_order(catalog):
    """Catalog ids ordered best-first for auto-substitution: stable ids before
    preview/exp/lite/mini variants, larger parameter counts first, and
    reverse-lexicographic (higher version numbers first) as the tiebreak —
    a plain reverse sort preferred 8b over 235b ('8' > '2') and dated preview
    snapshots over their stable base id."""
    def rank(mid):
        low = mid.lower()
        demoted = 1 if re.search(
            r"(?:^|[-_/.])(preview|exp|experimental|lite|mini|nano|tiny)(?:$|[-_/.:@])",
            low) else 0
        m = re.search(r"(\d+(?:\.\d+)?)b\b", low)
        params = float(m.group(1)) if m else 0.0
        return (demoted, -params)
    ranked = sorted(catalog, reverse=True)
    ranked.sort(key=rank)  # stable: keeps reverse-lex order within equal ranks
    return ranked

# Preference order when auto-discovering substitutes from a live catalog after
# every hardcoded model id has vanished from a provider.
_LLM_SUBSTITUTE_PREFS = [
    r"llama-?4.*(maverick|scout)",
    r"llama-?3\.3-?70b",
    r"gpt-oss-120b",
    r"llama-?3\.1-?70b",
    r"kimi-k2",
    r"deepseek.*chat",
    r"qwen-?3",
    r"gemini.*flash",
    r"gpt-oss-20b",
    r"gemma-?3",
    r"llama-?3\.1-?8b",
    r"mi[sx]tral",
]


def _classify_llm_failure(status, body):
    """Map a failed LLM call to a recovery verdict.

    Verdicts:
      dead_provider -- key/billing rejected: skip every model of this provider
      dead_model    -- model decommissioned/unknown: never retry it this run
      no_json_mode  -- response_format unsupported: retry once without it
      too_large     -- request exceeds a token-size limit: shrink and retry
      rate_limited  -- per-window limit hit: usable again after a wait
      transient     -- network/5xx hiccup: retry with backoff
    """
    low = (body or "").lower()
    if "model_permission_blocked_project" in low or "blocked at the project level" in low:
        return "dead_model"
    if (status == 413 or "request too large" in low or "reduce your message size" in low
            or ("tokens per minute" in low and "requested" in low)):
        return "too_large"
    if status == 429:
        return "rate_limited"
    if status in (401, 403) or "invalid api key" in low or "invalid_api_key" in low:
        return "dead_provider"
    if status == 402 or "insufficient_quota" in low or "billing" in low:
        return "dead_provider"
    if ("decommissioned" in low or "model_not_found" in low or "does not exist" in low
            or "unknown model" in low or "no such model" in low):
        return "dead_model"
    if "response_format" in low or "json_object" in low or "json mode" in low:
        return "no_json_mode"
    if status is None or status == 200 or status in (408, 409, 425, 500, 502, 503, 504):
        return "transient"
    if 400 <= status < 500:
        # Unrecognized 4xx: the same request will keep failing the same way.
        return "dead_model"
    return "transient"


def _retry_wait_seconds(response, body, default_wait=20.0):
    """How long a rate-limited endpoint wants us to wait, from the Retry-After
    header or a 'try again in 7.66s' / 'try again in 1m2.5s' message."""
    if response is not None:
        try:
            ra = response.headers.get("retry-after")
            if ra:
                return min(float(ra), 300.0)
        except Exception:
            pass
    m = re.search(r"try again in\s+(?:(\d+)\s*m)?\s*([\d.]+)\s*s", body or "", re.I)
    if m:
        try:
            return min(int(m.group(1) or 0) * 60 + float(m.group(2)), 300.0)
        except Exception:
            pass
    return default_wait


def _shrunk_max_tokens(body, current_max):
    """When a provider rejects a request for exceeding a token limit
    ('Limit 12000, Requested 12384'), compute a smaller max_tokens that fits.
    Returns None when shrinking can't help — the prompt itself is too big, or
    the completion budget left would be too small to produce a full script."""
    m = re.search(r"limit:?\s*(\d+)\D{1,40}requested:?\s*(\d+)", body or "", re.I)
    if not m:
        return None
    limit, requested = int(m.group(1)), int(m.group(2))
    overage = requested - limit
    if overage <= 0:
        return None
    new_max = current_max - overage - 256  # 256-token safety margin
    floor = max(256, int(current_max * 0.4))
    return new_max if new_max >= floor else None


def _llm_live_models(prov_name, chat_url, api_key, wanted, prefix, verify=True,
                     discover_filter=None):
    """Filter a hardcoded model list against the provider's live /models
    catalog (best effort, cached per run). If every hardcoded id is gone,
    auto-discover substitutes so a stale list degrades instead of hard-failing
    the way llama-3.3-70b-specdec / llama3-70b-8192 / mixtral-8x7b-32768 did.

    Router pseudo-models (openrouter/free) never count as 'live enough': they
    route to arbitrary — often tiny or reasoning — models, so when they are
    the only survivors, substitutes are discovered and tried BEFORE them.
    discover_filter (regex) restricts discovery, e.g. r':free$' on OpenRouter
    so a paid id can never be picked and 402 the whole provider."""
    wanted = [m for m in wanted if not _llm_model_dead(prov_name, m)]
    if not verify:
        return wanted
    models_url = chat_url[: -len("/chat/completions")] + "/models"
    with _LLM_CATALOG_LOCK:
        cached = _LLM_MODEL_CATALOG.get(models_url, "unset")
    if cached == "unset":
        catalog = None
        try:
            resp = requests.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15
            )
            if resp.status_code == 200:
                ids = {m.get("id") for m in resp.json().get("data", [])
                       if isinstance(m, dict) and m.get("id")}
                catalog = ids or None
        except Exception:
            catalog = None
        with _LLM_CATALOG_LOCK:
            _LLM_MODEL_CATALOG[models_url] = catalog
    else:
        catalog = cached
    if not catalog:
        return wanted  # catalog unavailable — trust the static list
    # Gemini's catalog lists ids as "models/<name>" while requests accept the
    # bare name — a bare-string comparison wrongly reported LIVE models as
    # missing (this silently dropped every hardcoded Gemini id for months).
    def _in_catalog(m):
        return m in catalog or f"models/{m}" in catalog
    live = [m for m in wanted if _in_catalog(m)]
    gone = [m for m in wanted if not _in_catalog(m)]
    if gone:
        print(f"{prefix}[LLM-Failover] {prov_name}: live catalog lacks {', '.join(gone)} — skipping without burning retries")
    routers = [m for m in live if m in _LLM_ROUTER_PSEUDO_MODELS]
    if [m for m in live if m not in _LLM_ROUTER_PSEUDO_MODELS]:
        return live
    subs = []
    ordered = _llm_discovery_order(catalog)
    for pat in _LLM_SUBSTITUTE_PREFS:
        for mid in ordered:
            if (re.search(pat, mid, re.I) and not _LLM_NON_CHAT_RE.search(mid)
                    and (discover_filter is None or re.search(discover_filter, mid))
                    and mid not in subs and not _llm_model_dead(prov_name, mid)):
                subs.append(mid)
        if len(subs) >= 3:
            break
    subs = subs[:3]
    if subs:
        print(f"{prefix}[LLM-Failover] {prov_name}: no usable hardcoded model is live; auto-discovered substitutes: {', '.join(subs)}")
    return subs + routers


def query_llm_with_failover(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 3500,
    json_format: bool = True,
    session_id: Optional[str] = None
) -> str:
    """Query OpenAI-compatible LLM endpoints with classified, adaptive failover.

    Instead of retrying every failure 3x verbatim, each failure is classified
    (_classify_llm_failure) and handled to match its cause: permanent errors
    skip immediately and are remembered for the whole run, oversized requests
    shrink max_tokens to fit the reported limit, rate limits are deferred and
    revisited after every other option is exhausted, and only genuinely
    transient errors get backoff retries."""
    prefix = f"[{session_id}] " if session_id else ""

    # Build list of providers dynamically based on env keys
    providers = []
    
    # 1. Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        providers.append({
            "name": "Gemini",
            "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "key": gemini_key,
            # 1.5-flash/pro removed: retired from the free tier (quota limit 0).
            # 2.5/2.0-flash appended as known-live fallbacks now that catalog
            # matching tolerates the "models/" prefix Gemini's /models uses.
            "models": ["gemini-3.5-flash", "gemini-3.5-pro", "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
        })

    # 2. Groq
    # llama-3.3-70b-versatile is decommissioned (Groq retired it and
    # llama-3.1-8b-instant for free/dev tiers, full shutdown 2026-08-16;
    # official replacement: gpt-oss-120b). Once 8b-instant vanishes from the
    # live catalog it gets filtered automatically. qwen3.6-27b stays last:
    # it's preview-tier (its <think> blocks are stripped by _coerce_llm_json,
    # but output quality is still the weakest of the four).
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        providers.append({
            "name": "Groq",
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "key": groq_key,
            "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.1-8b-instant", "qwen/qwen3.6-27b"]
        })

    # 3. Custom settings
    custom_key = os.environ.get("TEXT_GEN_KEY", "").strip()
    custom_base = os.environ.get("TEXT_GEN_BASE_URL", "").strip()
    custom_model = os.environ.get("TEXT_MODEL_NAME", "").strip()
    if custom_key and custom_base and custom_model:
        providers.append({
            "name": "Custom Config",
            "url": custom_base,
            "key": custom_key,
            "models": [custom_model],
            # User explicitly configured this model; don't second-guess it
            # against a /models catalog the proxy may not implement correctly.
            "verify_models": False
        })

    # 4. NVIDIA NIM
    nvidia_key = os.environ.get("NVIDIA_NIM_KEY", "").strip()
    if nvidia_key:
        providers.append({
            "name": "Nvidia NIM",
            "url": "https://integrate.api.nvidia.com/v1/chat/completions",
            "key": nvidia_key,
            "models": ["meta/llama-3.3-70b-instruct", "meta/llama-3.1-70b-instruct"]
        })

    # 5. OpenRouter — free ids churn constantly; the live-catalog filter drops
    # dead ones without burning retries, and discover_filter auto-picks fresh
    # :free replacements when every hardcoded id is gone (never a paid id — a
    # 402 would mark the whole provider dead for the run). openrouter/free is
    # LAST on purpose: it routes to arbitrary free models, frequently tiny or
    # reasoning ones whose output fails the JSON gate.
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        providers.append({
            "name": "OpenRouter",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "key": openrouter_key,
            "models": [
                "meta-llama/llama-3.3-70b-instruct:free",
                "meta-llama/llama-4-maverick:free",
                "deepseek/deepseek-chat-v3-0324:free",
                "openrouter/free",
            ],
            "discover_filter": r":free$",
        })

    # 6. GitHub Models
    github_key = os.environ.get("GITHUB_API_KEY", "").strip() or os.environ.get("GITHUB_TOKEN", "").strip()
    if github_key:
        providers.append({
            "name": "GitHub Models",
            "url": "https://models.inference.ai.azure.com/chat/completions",
            "key": github_key,
            "models": ["meta-llama-3.1-70b-instruct", "meta-llama-3.3-70b-instruct"]
        })

    if not providers:
        # Fallback default
        providers.append({
            "name": "Default NVIDIA (No Key)",
            "url": "https://integrate.api.nvidia.com/v1/chat/completions",
            "key": "",
            "models": ["meta/llama-3.3-70b-instruct"]
        })

    max_wait = float(os.environ.get("LLM_FAILOVER_MAX_WAIT_S", "75"))
    deadline = time.monotonic() + float(os.environ.get("LLM_FAILOVER_DEADLINE_S", "240"))

    errors = []       # unique, ordered — feeds the final exception message
    _seen_errors = set()
    deferred = []     # rate-limited models worth a second sweep

    def note(msg):
        print(f"{prefix}{msg}")
        key = msg[:200]
        if key not in _seen_errors:
            _seen_errors.add(key)
            errors.append(msg[:500])

    def attempt(url, key, model, mt, use_json):
        """One HTTP call. Returns (content, status, body, response, finish_reason)."""
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": mt
        }
        if use_json:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = requests.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}"
                },
                json=payload,
                timeout=90
            )
        except Exception as ex:
            return None, None, f"request error: {ex}", None, None
        if response.status_code != 200:
            return None, response.status_code, response.text, response, None
        try:
            choice = response.json()["choices"][0]
            content = choice["message"]["content"]
            finish_reason = str(choice.get("finish_reason") or "")
        except Exception as ex:
            return None, 200, f"malformed success body: {ex}", response, None
        if not content or not content.strip():
            return None, 200, "empty completion", response, finish_reason
        return content, 200, "", response, finish_reason

    def run_model(prov_name, url, key, model, start_mt, sweep):
        """Adaptive retry loop for a single model. Returns content or None."""
        mt = start_mt
        use_json = json_format
        json_retry_left = 1
        shrinks_left = 2
        attempts_left = 3 if sweep == 1 else 2
        attempt_no = 0
        gate_failures = 0
        while attempts_left > 0 and time.monotonic() < deadline:
            attempts_left -= 1
            attempt_no += 1
            suffix = f" (attempt {attempt_no})" if attempt_no > 1 else ""
            print(f"{prefix}Trying LLM provider {prov_name} / model {model} on {url}{suffix}...")
            content, status, body, response, finish_reason = attempt(url, key, model, mt, use_json)
            if content is not None:
                # HTTP 200 is not success: free routers (openrouter/free) and
                # small models regularly return prose or truncated JSON, and
                # returning it here short-circuits the whole chain — the
                # deferred rate-limited models never get their second sweep.
                # Gate on the SAME coercion the downstream parser uses.
                if json_format and _coerce_llm_json(content, quiet=True) is None:
                    # Truncation by the caller's own max_tokens reproduces
                    # identically on every retry — not the model's fault, and
                    # not worth another call or a run-wide blacklist entry.
                    if finish_reason in ("length", "max_tokens"):
                        note(f"{prov_name} ({model}) output truncated at max_tokens={mt} before the JSON closed")
                        print(f"{prefix}[LLM-Failover] {prov_name}/{model}: JSON truncated at max_tokens — moving on")
                        return None
                    gate_failures += 1
                    note(f"{prov_name} ({model}) returned 200 but no recoverable JSON "
                         f"(len {len(content)}): {content[:160]!r}")
                    print(f"{prefix}[LLM-Failover] {prov_name}/{model}: output has no recoverable JSON — "
                          f"{'retrying' if attempts_left > 0 else 'exhausted'}")
                    # Only persistent garbage (2+ unparseable outputs) marks a
                    # model dead for the run; a single flake after transient
                    # failures must not blacklist a healthy model.
                    if attempts_left <= 0:
                        if gate_failures >= 2:
                            _LLM_DEAD_MODELS.add((prov_name, model))
                            print(f"{prefix}[LLM-Failover] {prov_name}/{model}: unparseable {gate_failures}x — skipping it for the rest of the run")
                        continue
                    # Pace the retry and keep headroom so a slow garbage
                    # emitter can't eat the budget sweep 2 needs.
                    if time.monotonic() + 20 >= deadline:
                        return None
                    time.sleep(1.5 + random.uniform(0, 0.75))
                    continue
                print(f"{prefix}Success using provider {prov_name} / model {model}")
                return content
            note(f"{prov_name} ({model}) failed status {status}: {(body or '')[:400]}")
            verdict = _classify_llm_failure(status, body)
            if verdict == "dead_provider":
                _LLM_DEAD_PROVIDERS.add(prov_name)
                print(f"{prefix}[LLM-Failover] {prov_name}: key/billing rejected — skipping this provider for the rest of the run")
                return None
            if verdict == "dead_model":
                _LLM_DEAD_MODELS.add((prov_name, model))
                print(f"{prefix}[LLM-Failover] {prov_name}/{model}: permanent model error — not retrying it again this run")
                return None
            if verdict == "no_json_mode":
                if use_json and json_retry_left > 0:
                    json_retry_left -= 1
                    use_json = False
                    attempts_left += 1  # free retry: the request itself changed
                    print(f"{prefix}[LLM-Failover] {prov_name}/{model}: JSON mode unsupported — retrying without response_format")
                    continue
                _LLM_DEAD_MODELS.add((prov_name, model))
                return None
            if verdict == "too_large":
                new_mt = _shrunk_max_tokens(body, mt)
                if new_mt and shrinks_left > 0:
                    shrinks_left -= 1
                    attempts_left += 1  # free retry: the request itself changed
                    print(f"{prefix}[LLM-Failover] {prov_name}/{model}: over token limit — shrinking max_tokens {mt} -> {new_mt} and retrying")
                    mt = new_mt
                    continue
                print(f"{prefix}[LLM-Failover] {prov_name}/{model}: prompt cannot fit under this model's token limit — moving on")
                return None
            if verdict == "rate_limited":
                wait = _retry_wait_seconds(response, body)
                if sweep == 1 and wait > 8:
                    deferred.append({"prov": prov_name, "url": url, "key": key,
                                     "model": model, "mt": mt,
                                     "ready_at": time.monotonic() + wait})
                    print(f"{prefix}[LLM-Failover] {prov_name}/{model}: rate limited ~{wait:.0f}s — deferring, trying other models first")
                    return None
                wait = min(wait, max_wait, max(deadline - time.monotonic() - 5, 0))
                if wait <= 0:
                    return None
                print(f"{prefix}[LLM-Failover] {prov_name}/{model}: rate limited — waiting {wait:.1f}s")
                time.sleep(wait)
                continue
            # transient: exponential backoff with jitter
            if attempts_left > 0:
                backoff = min(1.5 * (2 ** (attempt_no - 1)), 8.0) + random.uniform(0, 0.75)
                if time.monotonic() + backoff >= deadline:
                    return None
                print(f"{prefix}[LLM-Failover] {prov_name}/{model}: transient failure — backing off {backoff:.1f}s")
                time.sleep(backoff)
        return None

    # --- Sweep 1: every live provider/model, without long rate-limit waits ---
    for prov in providers:
        prov_name = prov["name"]
        if prov_name in _LLM_DEAD_PROVIDERS:
            print(f"{prefix}[LLM-Failover] Skipping provider {prov_name} (key rejected earlier this run)")
            continue
        prov_url = prov["url"]
        if not prov_url.startswith("http://") and not prov_url.startswith("https://"):
            prov_url = "https://" + prov_url
        if not prov_url.endswith("/chat/completions"):
            prov_url = prov_url.rstrip("/") + "/chat/completions"

        models = _llm_live_models(prov_name, prov_url, prov["key"], prov["models"],
                                  prefix, verify=prov.get("verify_models", True),
                                  discover_filter=prov.get("discover_filter"))
        if not models:
            note(f"{prov_name}: no usable models (all dead or absent from live catalog)")
            continue
        for model_name in models:
            result = run_model(prov_name, prov_url, prov["key"], model_name, max_tokens, sweep=1)
            if result is not None:
                return result
            if prov_name in _LLM_DEAD_PROVIDERS:
                break
            if time.monotonic() >= deadline:
                break
        if time.monotonic() >= deadline:
            note("LLM failover deadline reached during first sweep")
            break

    # --- Sweep 2: once everything else failed, rate-limited models become
    #     worth actually waiting for ---
    if deferred and time.monotonic() < deadline:
        deferred.sort(key=lambda d: d["ready_at"])
        print(f"{prefix}[LLM-Failover] First sweep exhausted — revisiting {len(deferred)} rate-limited model(s)")
        for d in deferred:
            now = time.monotonic()
            wait = min(max(d["ready_at"] - now, 0), max_wait)
            if now + wait + 5 >= deadline:
                note("LLM failover deadline reached before all deferred retries")
                break
            if wait > 0:
                print(f"{prefix}[LLM-Failover] Waiting {wait:.1f}s for {d['prov']}/{d['model']} rate-limit window")
                time.sleep(wait)
            result = run_model(d["prov"], d["url"], d["key"], d["model"], d["mt"], sweep=2)
            if result is not None:
                return result

    raise Exception("LLM generation failed for all models. Errors: \n- " + "\n- ".join(errors))


def send_telegram_message(text: str, bot_token: str, chat_id: str, session_id: Optional[str] = None) -> bool:
    """Send a text message to a Telegram chat using curl."""
    import subprocess
    import json as json_module
    
    prefix = f"[{session_id}] " if session_id else ""
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    cmd = ["curl", "-sS", "-X", "POST", "--max-time", "60"]
    
    proxy_url = os.environ.get("PROXY_WORKER_URL") or os.environ.get("INSTAGRAM_API_BASE_URL")
    if proxy_url:
        proxy_url = proxy_url.strip().rstrip("/")
        url = f"{proxy_url}/bot{bot_token}/sendMessage"
        cmd += ["-H", "x-target-domain: api.telegram.org"]
        print(f"{prefix}[Telegram-PreCheck] Routing via proxy: {proxy_url}")
        
    cmd += ["-d", f"chat_id={chat_id}"]
    cmd += ["-d", f"text={text}"]
    cmd.append(url)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            if result.returncode == 35:
                cmd.insert(-1, "--insecure")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if result.returncode != 0:
                print(f"{prefix}[Telegram-PreCheck] curl message failed (exit {result.returncode}): {result.stderr.strip()}")
                return False
                
        data = json_module.loads(result.stdout)
        if data.get("ok"):
            return True
        else:
            print(f"{prefix}[Telegram-PreCheck] API error: {data}")
            return False
    except Exception as e:
        print(f"{prefix}[Telegram-PreCheck] Exception during message send: {e}")
        return False


def get_next_video_number() -> int:
    num = 0
    try:
        with open("render_count.txt", "r") as f:
            num = int(f.read().strip())
    except:
        pass
    num += 1
    try:
        with open("render_count.txt", "w") as f:
            f.write(str(num))
    except:
        pass
    return num


def _estimate_spoken_seconds(scenes: List[dict]) -> float:
    """Estimate how long the script's narration runs when spoken.

    Edge-TTS at the +10% narration rate averages ~2.75 words/sec, and every
    spoken scene gets a 0.35s tail pad. Same inputs the TTS step later uses
    (voiceover, falling back to text), so the estimate tracks the real
    auto-synced video length closely (run #106: est 24.3s vs actual 24.7s).
    """
    total_words = 0
    spoken_scenes = 0
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        vo = str(scene.get("voiceover") or scene.get("text") or "").strip()
        words = len(vo.split())
        total_words += words
        if words:
            spoken_scenes += 1
    return total_words / 2.75 + 0.35 * spoken_scenes


def _execute_render(req: RenderRequest, session_id: str) -> dict:
    """Execute the full render pipeline with a global sequential lock."""
    with render_lock:
        return _execute_render_unlocked(req, session_id)


def _execute_render_unlocked(req: RenderRequest, session_id: str, sync_delivery: bool = False) -> dict:
    """Execute the full render pipeline. Returns the result dict."""
    # --- FFMPEG PREFLIGHT ---
    # The voiceover mixer shells out to ffmpeg; without it every video ships
    # with broken narration. Fail here, before any LLM quota or render time is
    # spent, so a misconfigured runner produces a loud red run — not a bad post.
    if REQUIRE_VOICEOVER and shutil.which("ffmpeg") is None:
        raise Exception(
            "ffmpeg is not installed or not on PATH — the voiceover cannot be "
            "mixed. Install ffmpeg (CI: apt-get install -y ffmpeg) or set "
            "REQUIRE_VOICEOVER=0 to knowingly render without narration."
        )

    # Merge pipeline config from request model + LLM output
    pipeline_cfg = req.pipeline or PipelineConfig()
    quality = (pipeline_cfg.quality or "standard").lower()
    if quality not in QUALITY_PRESETS:
        quality = "standard"
    output_format = (pipeline_cfg.outputFormat or "mp4").lower()
    if output_format not in FORMAT_CODEC_MAP:
        output_format = "mp4"

    # Update status
    render_status_store[session_id] = {
        "status": "generating_script",
        "progress": 0.1,
        "started_at": time.time(),
        "prompt": req.prompt,
        "quality": quality,
        "output_format": output_format,
    }
    if pipeline_cfg.instagram and pipeline_cfg.instagram.enabled:
        render_status_store[session_id]["instagram_status"] = "queued_for_post"

    # --- TELEGRAM PRE-CHECK ---
    tg_cfg = pipeline_cfg.telegram
    bot_token = (tg_cfg.bot_token if tg_cfg else None) or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = (tg_cfg.chat_id if tg_cfg else None) or os.environ.get("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        video_number = get_next_video_number()
        msg = f"🎬 Starting video generation #{video_number}...\nPrompt: {req.prompt[:100]}..."
        print(f"[{session_id}] Running Telegram Pre-Check: Sending message to chat_id: {chat_id}")
        success = send_telegram_message(msg, bot_token, chat_id, session_id)
        if not success:
            render_status_store[session_id]["status"] = "error"
            render_status_store[session_id]["error"] = "Failed to send Telegram pre-check message."
            print(f"[{session_id}] Aborting render: Telegram pre-check message failed.")
            raise Exception("Telegram delivery is unavailable. Aborting video generation to save compute.")

    print(f"[{session_id}] Starting video generation pipeline (quality={quality}, format={output_format})...")

    # Per-video variety seed + auto-channel detection (drives all randomness)
    video_seed = _derive_seed(session_id)
    is_auto_channel = session_id.startswith(AUTO_CHANNEL_PREFIXES)

    # 1. CALL LLM TO GENERATE THE SCRIPT AND THEME CONFIGURATION
    #    Append a seeded creative brief (opening hook + structural variety) so
    #    no two videos — even from the same prompt — follow the same flow.
    variety_meta: Dict[str, Any] = {}
    user_prompt = build_user_prompt(req.prompt) + build_variety_directive(
        video_seed, is_auto_channel, meta_out=variety_meta)

    # Scene lengths auto-sync to speech, so a script with skimpy voiceovers
    # collapses the whole video (weak fallback models writing 10-word lines
    # turned a planned ~45s video into 24s). Generate, estimate the spoken
    # runtime, and regenerate with an explicit expansion note until it clears
    # MIN_SPOKEN_SEC — keeping the longest attempt so a retry can't make
    # things worse.
    render_status_store[session_id]["status"] = "parsing_script"
    render_status_store[session_id]["progress"] = 0.2

    best_script = None
    best_est_sec = 0.0
    best_band_dist = None
    last_est_sec = None
    llm_error = None
    for attempt in range(1 + SCRIPT_EXPAND_RETRIES):
        prompt_for_attempt = user_prompt
        if attempt > 0:
            if last_est_sec is None:
                prompt_for_attempt += (
                    "\n\nCRITICAL REVISION: your previous reply was not a parseable script. Reply with ONLY the raw "
                    "JSON object — no prose, no markdown fences, no <think> blocks."
                )
            elif last_est_sec < MIN_SPOKEN_SEC:
                prompt_for_attempt += (
                    f"\n\nCRITICAL REVISION: the previous script's narration ran only ~{int(last_est_sec)} seconds "
                    f"when spoken — the video MUST run longer. Write 6-8 scenes and give EVERY scene a \"voiceover\" of "
                    f"20-35 words (two full sentences is ideal) so the summed narration lasts 40-55 seconds. Do NOT pad "
                    f"with repetition or filler — every added sentence must contribute a new concrete fact or detail."
                )
            else:
                prompt_for_attempt += (
                    f"\n\nCRITICAL REVISION: the previous script's narration ran ~{int(last_est_sec)} seconds when "
                    f"spoken — too long for a Reel. Cut the weakest scenes and tighten every \"voiceover\" so the "
                    f"summed narration lasts 40-55 seconds, keeping only the strongest concrete facts."
                )
        try:
            raw_text = query_llm_with_failover(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt_for_attempt,
                max_tokens=3500,
                json_format=True,
                session_id=session_id
            )
        except Exception as ex:
            llm_error = ex
            break  # the whole provider chain is down — retrying immediately won't help
        try:
            print(f"[{session_id}] Raw LLM output length: {len(raw_text)} chars")
            candidate = parse_and_validate_script(raw_text, session_id, source_prompt=req.prompt or "")
        except Exception as e:
            print(f"[{session_id}] WARN: Parse failed on attempt {attempt + 1} ({e})")
            last_est_sec = None
            continue
        if candidate.get("_isFallback"):
            # parse_and_validate_script swallows garbage output and returns the
            # canned filler script instead of raising — that must never count
            # as a real candidate here.
            print(f"[{session_id}] WARN: attempt {attempt + 1} produced no parseable script (fallback returned)")
            last_est_sec = None
            continue
        est_sec = _estimate_spoken_seconds(candidate.get("scenes", []))
        last_est_sec = est_sec
        band_dist = max(MIN_SPOKEN_SEC - est_sec, 0.0) + max(est_sec - MAX_SPOKEN_SEC, 0.0)
        print(f"[{session_id}] Script attempt {attempt + 1}: {len(candidate.get('scenes', []))} scenes, "
              f"estimated spoken runtime {est_sec:.1f}s (target {MIN_SPOKEN_SEC:.0f}-{MAX_SPOKEN_SEC:.0f}s)")
        if best_band_dist is None or band_dist < best_band_dist:
            best_script, best_est_sec, best_band_dist = candidate, est_sec, band_dist
        if band_dist == 0.0:
            break
        print(f"[{session_id}] Script outside target runtime — regenerating with revision note...")

    if best_script is not None:
        parsed_script = best_script
        if best_band_dist is not None and best_band_dist > 0.0:
            print(f"[{session_id}] WARN: best attempt still outside the target runtime (~{best_est_sec:.0f}s spoken) "
                  f"after {SCRIPT_EXPAND_RETRIES} retries — proceeding with the closest one.")
    elif llm_error is not None:
        render_status_store[session_id]["status"] = "error"
        render_status_store[session_id]["error"] = "LLM generation failed for all models."
        raise HTTPException(
            status_code=500,
            detail=str(llm_error)
        )
    else:
        # Every attempt came back unparseable. On an auto-posting channel the
        # canned "Welcome / Stay tuned" filler is worse than skipping the slot —
        # abort loudly (the CI wrapper telegrams the failure). Manual/API flows
        # keep the legacy fallback so interactive users still get something.
        if is_auto_channel:
            render_status_store[session_id]["status"] = "error"
            render_status_store[session_id]["error"] = "LLM output unparseable on all attempts."
            raise Exception(
                "Script generation produced no usable script (LLM output unparseable on every attempt) — "
                "aborting so no generic filler video is posted."
            )
        print(f"[{session_id}] WARN: Parse failed on every attempt, using fallback script")
        parsed_script = _build_fallback_script()

    # Keep the originating topic prompt with the script so downstream text
    # generators (captions, upload metadata) can whitelist user-supplied names
    # when scrubbing fabricated attributions.
    parsed_script["_sourcePrompt"] = req.prompt or ""

    forced_theme_keys = set()
    if req.theme_overrides:
        for k, v in req.theme_overrides.items():
            if v is not None:
                parsed_script["theme"][k] = v
                forced_theme_keys.add(k)

    # Seeded style director: emit the render-layer variety seed, rotate a
    # cohesive style pack for automated channels, and add aesthetic flavor.
    # Respects any theme dimension the caller explicitly forced.
    chosen_style_pack = apply_style_director(
        parsed_script["theme"], video_seed, is_auto_channel, forced_theme_keys)

    # Merge pipeline config from LLM output with request-level overrides
    llm_pipeline = parsed_script.get("pipeline", {})
    if llm_pipeline:
        # Request-level pipeline config takes precedence over LLM-generated
        if not pipeline_cfg.outputFormat or pipeline_cfg.outputFormat == "mp4":
            fmt = llm_pipeline.get("outputFormat", output_format)
            if fmt in FORMAT_CODEC_MAP:
                output_format = fmt
        if not pipeline_cfg.quality or pipeline_cfg.quality == "standard":
            q = llm_pipeline.get("quality", quality)
            if q in QUALITY_PRESETS:
                quality = q

    # Add pipeline metadata to the script for Remotion (watermark etc.)
    parsed_script["pipeline"] = {
        "outputFormat": output_format,
        "quality": quality,
        "watermark": pipeline_cfg.watermark,
    }

    host_url = os.environ.get("SPACE_HOST", "localhost:7860")
    protocol = "https" if "hf.space" in host_url else "http"
    base_url = f"{protocol}://{host_url}/public"

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # --- Image sourcing helpers ---
    
    def get_fallback_local_image(theme_name: str, scene_idx: int, tech_only: bool = False) -> bytes:
        import urllib.request
        t_normalized = theme_name.lower().replace(" ", "_")
        known_themes = [
            "cyberpunk_alley", "neon_city", "misty_forest", "deep_space",
            "cosmic_aurora", "synthwave_sunset", "misty_mountain", "retro_tech",
            "mystic_temple", "digital_matrix"
        ]
        # Tech channels must never fall back to nature/fantasy imagery — a
        # misty forest behind a Kubernetes video reads as broken, not artsy.
        if tech_only:
            known_themes = [
                "cyberpunk_alley", "neon_city", "deep_space",
                "synthwave_sunset", "retro_tech", "digital_matrix",
            ]
        # No hardcoded default: when the theme name doesn't match, rotate the
        # fallback imagery per-session so unmatched videos don't all collapse
        # into the same cyberpunk look.
        matched_theme = random.Random(session_id).choice(known_themes)
        for kt in known_themes:
            if kt in t_normalized or t_normalized in kt:
                matched_theme = kt
                break
                
        options = sorted([k for k in STOCK_URL_MAP.keys() if k.startswith(matched_theme)])
        if not options:
            options = sorted(list(STOCK_URL_MAP.keys()))

        # NOTE: uses the module-level `random` import — a local `import random`
        # here would shadow it and break the seeded theme pick above.
        rnd = random.Random(session_id)
        rnd.shuffle(options)
        filename = options[scene_idx % len(options)]
        
        filepath = os.path.join(PUBLIC_DIR, "stock", filename)
        if os.path.exists(filepath):
            print(f"[{session_id}] Reading fallback stock image: {filepath}")
            with open(filepath, "rb") as f:
                return f.read()
                
        unsplash_url = STOCK_URL_MAP.get(filename)
        if unsplash_url:
            print(f"[{session_id}] Stock image {filename} missing on disk. Downloading from Unsplash source...")
            try:
                req_dl = urllib.request.Request(unsplash_url, headers={"User-Agent": user_agent})
                with urllib.request.urlopen(req_dl, timeout=30) as response_dl:
                    content_dl = response_dl.read()
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, "wb") as f:
                        f.write(content_dl)
                    return content_dl
            except Exception as e:
                print(f"[{session_id}] Failed to download fallback from Unsplash mapping: {e}")
                
        # Picsum serves a RANDOM photo (any subject) — acceptable last resort
        # for generic channels, but a tech video must never gamble on a misty
        # forest backdrop; the neutral 1x1 below lets the renderer's own
        # gradient/vector background show instead.
        if not tech_only:
            try:
                print(f"[{session_id}] Fetching ultimate fallback Picsum image...")
                req_picsum = urllib.request.Request("https://picsum.photos/1080/1920", headers={"User-Agent": user_agent})
                with urllib.request.urlopen(req_picsum, timeout=15) as response_picsum:
                    return response_picsum.read()
            except Exception as e:
                print(f"[{session_id}] Picsum fallback failed: {e}")
            
        # Return a valid 1x1 transparent/black PNG instead of empty bytes to prevent Remotion fetch deadlocks/broken UI
        return base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")

    def _validate_image_bytes(img_bytes: bytes, source_name: str) -> bool:
        """Check if downloaded image bytes represent a valid, usable image."""
        if not img_bytes or len(img_bytes) < 10000:  # < 10KB is likely broken/tiny
            print(f"[{session_id}] Image from {source_name} too small ({len(img_bytes) if img_bytes else 0} bytes), rejecting")
            return False
        # Check for common image magic bytes
        if img_bytes[:4] in [b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xdb',
                              b'RIFF', b'GIF8'] or img_bytes[:2] == b'\xff\xd8':
            return True
        # Also accept WebP
        if img_bytes[:4] == b'RIFF' and img_bytes[8:12] == b'WEBP':
            return True
        print(f"[{session_id}] Image from {source_name} failed magic-byte check, rejecting")
        return False

    def _build_search_query(scene_query: str, original_prompt: str) -> str:
        """Combine scene-specific searchQuery with relevant keywords from the original prompt.
        
        This produces better search results by adding topic context to the visual query.
        E.g. scene_query='chart growth' + prompt='electric vehicles 2024' -> 'chart growth electric vehicles'
        """
        # Extract 2-3 most meaningful keywords from the original prompt
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                      'should', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'for',
                      'on', 'with', 'at', 'by', 'from', 'as', 'into', 'about', 'like',
                      'through', 'after', 'over', 'between', 'out', 'up', 'that', 'this',
                      'it', 'its', 'and', 'or', 'but', 'if', 'than', 'too', 'very', 'just',
                      'make', 'made', 'create', 'video', 'me', 'my', 'i', 'we', 'our',
                      'you', 'your', 'they', 'their', 'what', 'which', 'who', 'how', 'why',
                      'when', 'where', 'there', 'here', 'all', 'each', 'every', 'both',
                      'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not', 'only'}
        prompt_words = [w for w in re.split(r'\W+', original_prompt.lower()) if w and w not in stop_words and len(w) > 2]
        # Take top 2 most relevant prompt keywords not already in the scene query
        scene_words_lower = scene_query.lower()
        extra_keywords = [w for w in prompt_words if w not in scene_words_lower][:2]
        
        combined = scene_query
        if extra_keywords:
            combined = f"{scene_query} {' '.join(extra_keywords)}"
        return combined.strip()

    def _get_pexels_orientation() -> str:
        """Determine best Pexels orientation based on the video's aspect ratio."""
        aspect = parsed_script.get("theme", {}).get("aspectRatio", "9:16")
        if aspect in ["9:16", "4:5"]:
            return "portrait"
        elif aspect == "16:9":
            return "landscape"
        else:
            return "square"

    # Track used image hashes across scenes to prevent duplicates within one video
    _used_image_hashes: set = set()
    # Track used stock-video clip IDs so no two scenes share the same b-roll
    _used_video_ids: set = set()

    def _hash_image(img_bytes: bytes) -> str:
        """Fast hash of image bytes for dedup."""
        import hashlib
        return hashlib.md5(img_bytes[:8192]).hexdigest()

    def _fetch_from_pexels(query: str, pexels_key: str, attempt: int = 1) -> Optional[bytes]:
        """Fetch an image from Pexels API (requires API key).
        
        Primary image provider — high quality, curated stock photos.
        Uses orientation-aware search to match the video's aspect ratio.
        Randomizes page offset so consecutive videos get different results.
        Skips images whose hash is already used in this video.
        """
        import urllib.request
        import urllib.parse
        orientation = _get_pexels_orientation()
        encoded = urllib.parse.quote(query)
        # Randomize page offset (1-4) so different videos get different results
        page = random.randint(1, 4)
        url = f"https://api.pexels.com/v1/search?query={encoded}&per_page=15&page={page}&orientation={orientation}"
        print(f"[{session_id}] Pexels search (attempt {attempt}, page {page}): {url}")
        try:
            req_pexels = urllib.request.Request(url, headers={
                "User-Agent": user_agent,
                "Authorization": pexels_key
            })
            with urllib.request.urlopen(req_pexels, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                photos = data.get("photos", [])
                if not photos:
                    print(f"[{session_id}] Pexels returned 0 results for '{query}'")
                    return None
                
                # Shuffle for variety, then stable-sort so photos whose
                # alt/slug actually mention the query's subject come first —
                # equal-overlap photos keep their shuffled order.
                random.shuffle(photos)
                photos.sort(
                    key=lambda p: -_relevance_overlap(
                        query, f"{p.get('alt', '')} {p.get('url', '')}"
                    )
                )

                for photo in photos:
                    src = photo.get("src", {})
                    # Select size based on orientation for best quality-to-speed ratio
                    if orientation == "portrait":
                        img_url = src.get("portrait") or src.get("large2x") or src.get("large")
                    elif orientation == "landscape":
                        img_url = src.get("landscape") or src.get("large2x") or src.get("large")
                    else:
                        img_url = src.get("large") or src.get("large2x")
                    
                    if not img_url:
                        continue
                    
                    # Skip if we already used a photo by the same Pexels ID
                    photo_id = str(photo.get("id", ""))
                    if photo_id and photo_id in _used_image_hashes:
                        print(f"[{session_id}]   Skipping Pexels photo {photo_id} (already used in this video)")
                        continue
                    
                    print(f"[{session_id}] Downloading Pexels image: {img_url}")
                    try:
                        dl_req = urllib.request.Request(img_url, headers={"User-Agent": user_agent})
                        with urllib.request.urlopen(dl_req, timeout=15) as dl_resp:
                            content = dl_resp.read()
                            if _validate_image_bytes(content, "Pexels"):
                                # Check byte-level dedup
                                h = _hash_image(content)
                                if h in _used_image_hashes:
                                    print(f"[{session_id}]   Skipping duplicate image (hash match)")
                                    continue
                                _used_image_hashes.add(h)
                                if photo_id:
                                    _used_image_hashes.add(photo_id)
                                photographer = photo.get("photographer", "Unknown")
                                print(f"[{session_id}] ✓ Pexels image OK ({len(content)} bytes, by {photographer})")
                                return content
                    except Exception as dl_err:
                        print(f"[{session_id}] Pexels download failed: {dl_err}")
                        continue
        except Exception as e:
            print(f"[{session_id}] Pexels API error: {e}")
        return None

    def _download_video_capped(video_url: str, provider: str) -> Optional[bytes]:
        """Download a video file in chunks, aborting if it exceeds the size cap."""
        import urllib.request
        try:
            dl_req = urllib.request.Request(video_url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(dl_req, timeout=45) as dl_resp:
                length = dl_resp.headers.get("Content-Length")
                if length and int(length) > HOOK_VIDEO_MAX_BYTES:
                    print(f"[{session_id}] {provider} video too large ({length} bytes), skipping")
                    return None
                chunks = []
                total = 0
                while True:
                    chunk = dl_resp.read(1024 * 512)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > HOOK_VIDEO_MAX_BYTES:
                        print(f"[{session_id}] {provider} video exceeded {HOOK_VIDEO_MAX_BYTES} bytes mid-download, skipping")
                        return None
                    chunks.append(chunk)
                content = b"".join(chunks)
                if len(content) < 50_000:  # sanity: real clips are never this small
                    return None
                print(f"[{session_id}] ✓ {provider} hook video OK ({len(content)} bytes)")
                return content
        except Exception as e:
            print(f"[{session_id}] {provider} video download failed: {e}")
            return None

    def _fetch_hook_video_from_pexels(query: str, pexels_key: str, min_duration_sec: float) -> Optional[bytes]:
        """Fetch a stock VIDEO clip from the free Pexels Video API for the hook scene.

        Same API key as photo search. Free for commercial use, no attribution.
        Orientation-aware; prefers ~1080p files (enough for a 1080x1920 render
        without 4K download cost) and clips long enough to cover the scene.
        """
        import urllib.request
        import urllib.parse
        orientation = _get_pexels_orientation()
        encoded = urllib.parse.quote(query)
        page = random.randint(1, 3)
        url = f"https://api.pexels.com/videos/search?query={encoded}&per_page=12&page={page}&orientation={orientation}&size=medium"
        print(f"[{session_id}] Pexels VIDEO search (page {page}): {url}")
        try:
            api_req = urllib.request.Request(url, headers={
                "User-Agent": user_agent,
                "Authorization": pexels_key,
            })
            with urllib.request.urlopen(api_req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            videos = data.get("videos", [])
            if not videos:
                print(f"[{session_id}] Pexels VIDEO returned 0 results for '{query}'")
                return None
            # Shuffle for variety, then prefer clips whose URL slug shares
            # words with the query (the slug is the only text Pexels gives us
            # for videos) — keeps owls out of database explainers.
            random.shuffle(videos)
            videos.sort(key=lambda v: -_relevance_overlap(query, v.get("url", "")))
            for video in videos:
                if float(video.get("duration", 0)) < min_duration_sec:
                    continue
                vid_id = f"pexels-{video.get('id')}"
                if vid_id in _used_video_ids:
                    continue
                files = [
                    f for f in video.get("video_files", [])
                    if f.get("file_type") == "video/mp4" and f.get("link") and f.get("width") and f.get("height")
                ]
                # Closest to 1080x1920-class resolution first
                files.sort(key=lambda f: abs(max(f["width"], f["height"]) - 1920))
                for vf in files[:2]:
                    content = _download_video_capped(vf["link"], "Pexels")
                    if content:
                        _used_video_ids.add(vid_id)
                        return content
        except Exception as e:
            print(f"[{session_id}] Pexels VIDEO API error: {e}")
        return None

    def _fetch_hook_video_from_pixabay(query: str, min_duration_sec: float) -> Optional[bytes]:
        """Fallback stock video from the free Pixabay video API (needs PIXABAY_API_KEY)."""
        import urllib.request
        import urllib.parse
        if not PIXABAY_API_KEY:
            return None
        encoded = urllib.parse.quote(query)
        url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={encoded}&per_page=20&safesearch=true"
        print(f"[{session_id}] Pixabay VIDEO search for '{query}'")
        try:
            api_req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(api_req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            hits = data.get("hits", [])
            random.shuffle(hits)
            for hit in hits:
                if float(hit.get("duration", 0)) < min_duration_sec:
                    continue
                vid_id = f"pixabay-{hit.get('id')}"
                if vid_id in _used_video_ids:
                    continue
                sizes = hit.get("videos", {})
                for size_key in ("large", "medium", "small"):
                    vf = sizes.get(size_key) or {}
                    if vf.get("url"):
                        content = _download_video_capped(vf["url"], "Pixabay")
                        if content:
                            _used_video_ids.add(vid_id)
                            return content
        except Exception as e:
            print(f"[{session_id}] Pixabay VIDEO API error: {e}")
        return None

    def fetch_hook_video(query: str, pexels_key: str, min_duration_sec: float) -> Optional[bytes]:
        """Source a motion clip for the opening hook scene: Pexels → Pixabay."""
        if pexels_key:
            content = _fetch_hook_video_from_pexels(query, pexels_key, min_duration_sec)
            if content:
                return content
            simple = _simplify_query(query)
            if simple != query.lower().strip():
                content = _fetch_hook_video_from_pexels(simple, pexels_key, min_duration_sec)
                if content:
                    return content
        return _fetch_hook_video_from_pixabay(query, min_duration_sec)

    # NOTE: the old `_fetch_from_unsplash_direct` tier was deleted on purpose:
    # despite its name it fetched a RANDOM picsum.photos image (query ignored)
    # and sat ABOVE the query-aware providers — the primary source of
    # "random trees behind a tech video". Do not reintroduce a query-blind
    # provider anywhere above the theme fallback.

    def _fetch_from_openverse(query: str) -> Optional[bytes]:
        """Fetch an image from Openverse API (no API key, Creative Commons).
        
        Tertiary provider — free but lower quality/relevance.
        """
        import urllib.request
        import urllib.parse
        encoded = urllib.parse.quote(query)
        url = f"https://api.openverse.org/v1/images/?q={encoded}&page_size=10"
        print(f"[{session_id}] Trying Openverse: {url}")
        try:
            api_req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(api_req, timeout=10) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                results = res_json.get("results", [])
                valid_urls = [r.get("url") for r in results
                              if r.get("url", "").startswith("http") and not r.get("url", "").lower().endswith(".pdf")]
                
                # Shuffle candidates for randomness across video runs
                random.shuffle(valid_urls)
                for candidate_url in valid_urls[:3]:
                    try:
                        dl_req = urllib.request.Request(candidate_url, headers={"User-Agent": user_agent})
                        with urllib.request.urlopen(dl_req, timeout=10) as dl_res:
                            content = dl_res.read()
                            if _validate_image_bytes(content, "Openverse"):
                                print(f"[{session_id}] ✓ Openverse image OK ({len(content)} bytes)")
                                return content
                    except Exception as ex:
                        print(f"[{session_id}] Openverse download failed: {ex}")
        except Exception as e:
            print(f"[{session_id}] Openverse search failed: {e}")
        return None

    # --- AI image generation (last query-aware resort before theme fallback) ---
    _ai_images_used = [0]          # closure counters (lists: py3.9, no nonlocal need)
    _last_ai_request_ts = [0.0]

    def _generate_ai_image_pollinations(prompt_text: str, scene_idx: int) -> Optional[bytes]:
        """Text-to-image via the keyless Pollinations FLUX endpoint.

        Seeded per video+scene (deterministic across retries, unique across
        videos). Anonymous tier is rate-limited (~1 req/15s; ~1/5s with a
        free registered token) — the gap is waited out before firing, though
        generation latency usually covers it naturally.
        """
        import urllib.request
        import urllib.parse
        min_gap = 5.0 if POLLINATIONS_API_TOKEN else 15.0
        wait = min_gap - (time.time() - _last_ai_request_ts[0])
        if wait > 0:
            time.sleep(wait)
        seed_val = (_derive_seed(session_id) + scene_idx) % (2 ** 31)
        encoded = urllib.parse.quote(prompt_text, safe="")
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width=1080&height=1920&model=flux&seed={seed_val}"
               f"&nologo=true&safe=true&private=true")
        headers = {"User-Agent": user_agent}
        if POLLINATIONS_API_TOKEN:
            headers["Authorization"] = f"Bearer {POLLINATIONS_API_TOKEN}"
        print(f"[{session_id}] AI image (Pollinations, seed={seed_val}): '{prompt_text[:90]}'")
        _last_ai_request_ts[0] = time.time()
        try:
            dl_req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(dl_req, timeout=AI_IMAGE_TIMEOUT_SEC) as resp:
                chunks, total = [], 0
                while True:
                    chunk = resp.read(1024 * 512)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > AI_IMAGE_MAX_BYTES:
                        print(f"[{session_id}] Pollinations image exceeded "
                              f"{AI_IMAGE_MAX_BYTES} bytes mid-download, skipping")
                        return None
                    chunks.append(chunk)
                content = b"".join(chunks)
            if _validate_image_bytes(content, "Pollinations"):
                return content
        except Exception as e:
            print(f"[{session_id}] Pollinations generation failed: {e}")
        return None

    def _generate_ai_image_hf(prompt_text: str) -> Optional[bytes]:
        """FLUX.1-schnell via HF Inference (only when HF_TOKEN is set).

        FLUX dims must be multiples of 16 → 1088x1920; backgrounds render
        `cover`, so the 8px aspect drift is invisible.
        """
        if not HF_TOKEN:
            return None
        hf_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
        payload = {"inputs": prompt_text, "parameters": {"width": 1088, "height": 1920}}
        try:
            res = requests.post(hf_url, headers={"Authorization": f"Bearer {HF_TOKEN}"},
                                json=payload, timeout=90)
            if res.status_code == 503:
                print(f"[{session_id}] HF FLUX cold start — retrying once with wait-for-model...")
                res = requests.post(
                    hf_url,
                    headers={"Authorization": f"Bearer {HF_TOKEN}", "x-wait-for-model": "true"},
                    json=payload, timeout=120)
            if res.status_code != 200:
                print(f"[{session_id}] HF FLUX generation failed ({res.status_code}): {res.text[:200]}")
                return None
            content = res.content
            if len(content) <= AI_IMAGE_MAX_BYTES and _validate_image_bytes(content, "HF-FLUX"):
                return content
        except Exception as e:
            print(f"[{session_id}] HF FLUX generation error: {e}")
        return None

    def _generate_ai_image(query: str, scene_idx: int) -> Optional[bytes]:
        """AI-tier orchestrator: per-video cap → prompt build → Pollinations →
        HF FLUX → dedup, plus a best-effort debug copy under public/ai-images/
        (spot-check quality/watermark; deleted with the render's cleanup)."""
        if _ai_images_used[0] >= AI_IMAGE_MAX_PER_VIDEO:
            print(f"[{session_id}] AI image cap reached ({AI_IMAGE_MAX_PER_VIDEO}/video), skipping")
            return None
        prompt_text = _build_ai_image_prompt(query, chosen_style_pack, is_tech_channel)
        content = _generate_ai_image_pollinations(prompt_text, scene_idx) or _generate_ai_image_hf(prompt_text)
        if not content:
            return None
        if _hash_image(content) in _used_image_hashes:
            print(f"[{session_id}] AI image was a duplicate (hash match), skipping")
            return None
        _ai_images_used[0] += 1
        try:
            ai_dir = os.path.join(PUBLIC_DIR, "ai-images")
            os.makedirs(ai_dir, exist_ok=True)
            with open(os.path.join(ai_dir, f"ai-{session_id}-{scene_idx}.jpg"), "wb") as f:
                f.write(content)
        except Exception:
            pass
        print(f"[{session_id}] ✓ AI image OK ({len(content)} bytes, "
              f"{_ai_images_used[0]}/{AI_IMAGE_MAX_PER_VIDEO} this video)")
        return content

    def _simplify_query(query: str) -> str:
        """Reduce a search query to its 2-3 most important words for broader results."""
        stop = {'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                'by', 'from', 'up', 'about', 'into', 'over', 'after', 'close', 'dark', 'light',
                'blue', 'red', 'green', 'bright', 'abstract', 'modern', 'beautiful', 'dramatic'}
        words = [w for w in query.lower().split() if w not in stop and len(w) > 2]
        return ' '.join(words[:3]) if words else query

    def fetch_stock_image(query: str, theme_name: str, scene_idx: int, pexels_key: str = "",
                          tech_only: bool = False) -> bytes:
        """Multi-provider image search with intelligent retry.

        Every tier is QUERY-AWARE — the old tier 3 (picsum "random photo")
        ignored the query entirely and beat the query-aware providers below
        it, which is how tech videos ended up with random forests. Random
        imagery is now only reachable inside get_fallback_local_image, after
        every real search has failed (and never for tech channels).

        Provider priority (Pexels first since we have an API key):
        1. Pexels API with enriched query — highest quality, orientation-aware
        2. Pexels with the original scene query
        3. Openverse — Creative Commons, lower quality but query-aware
        4. Pexels with simplified query — broader search if specific query failed
        5. AI-generated image (Pollinations → HF FLUX) — query-aware, so it may
           sit above the theme fallback, but NEVER above real stock search
        6. Theme-based fallback from STOCK_URL_MAP (tech-safe themes only for
           tech channels)
        """
        if not query:
            return get_fallback_local_image(theme_name, scene_idx, tech_only=tech_only)

        # Build enriched search query (adds topic keywords)
        enriched_query = _build_search_query(query, req.prompt)
        print(f"[{session_id}] === Image search for scene {scene_idx + 1} ===")
        print(f"[{session_id}]   Original query: '{query}'")
        print(f"[{session_id}]   Enriched query: '{enriched_query}'")

        # Debug/testing switch: force the AI tier by skipping stock search
        if AI_IMAGE_ENABLED and AI_IMAGE_FORCE:
            print(f"[{session_id}] AI_IMAGE_FORCE set — skipping stock tiers")
            result = _generate_ai_image(query, scene_idx)
            if result:
                return result

        # === TIER 1: Pexels with enriched query ===
        if pexels_key:
            result = _fetch_from_pexels(enriched_query, pexels_key, attempt=1)
            if result:
                return result

        # === TIER 2: Pexels with original query (if enriched failed) ===
        if pexels_key and enriched_query != query:
            result = _fetch_from_pexels(query, pexels_key, attempt=2)
            if result:
                return result

        # === TIER 3: Openverse (query-aware, keyless) ===
        result = _fetch_from_openverse(enriched_query)
        if result:
            return result

        # === TIER 4: Pexels with simplified/broader query ===
        if pexels_key:
            simple_query = _simplify_query(query)
            if simple_query != query.lower().strip():
                print(f"[{session_id}]   Simplified query: '{simple_query}'")
                result = _fetch_from_pexels(simple_query, pexels_key, attempt=3)
                if result:
                    return result

        # === TIER 5: AI-generated image (query-aware; Pollinations → HF FLUX) ===
        if AI_IMAGE_ENABLED and not AI_IMAGE_FORCE:
            result = _generate_ai_image(query, scene_idx)
            if result:
                return result

        # === TIER 6: Theme-based fallback (last resort) ===
        print(f"[{session_id}] All providers exhausted, using theme fallback")
        return get_fallback_local_image(theme_name, scene_idx, tech_only=tech_only)

    # --- Source images for all scenes ---
    render_status_store[session_id]["status"] = "sourcing_assets"
    render_status_store[session_id]["progress"] = 0.3

    scenes_with_images = []
    overlay_type = parsed_script["theme"].get("overlayType", "clean")
    # Auto tech/news channels anchor EVERY asset search (stills AND b-roll) in
    # the tech domain, so an abstract LLM query can't pull nature imagery.
    is_tech_channel = session_id.startswith(TECH_SESSION_PREFIXES)

    for idx, scene in enumerate(parsed_script["scenes"]):
        raw_search_query = scene.get("searchQuery") or req.prompt
        search_query = _build_scene_image_query(
            raw_search_query, scene.get("videoQuery"), idx, is_tech_channel
        )
        print(f"[{session_id}] Sourcing asset {idx+1}/{len(parsed_script['scenes'])} for query: '{search_query}'")
        
        render_status_store[session_id]["progress"] = 0.3 + (0.3 * (idx / len(parsed_script["scenes"])))
        
        img_data = None
        
        if req.image_urls and len(req.image_urls) > idx and req.image_urls[idx]:
            import urllib.request
            img_url = req.image_urls[idx]
            if "stock/" in img_url:
                filename = os.path.basename(img_url)
                filepath = os.path.join(PUBLIC_DIR, "stock", filename)
                print(f"[{session_id}] Loading explicit local stock image: {filepath}")
                try:
                    if os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            img_data = f.read()
                    else:
                        unsplash_url = STOCK_URL_MAP.get(filename)
                        if unsplash_url:
                            req_dl = urllib.request.Request(unsplash_url, headers={"User-Agent": user_agent})
                            with urllib.request.urlopen(req_dl, timeout=30) as response_dl:
                                content_dl = response_dl.read()
                                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                                with open(filepath, "wb") as f:
                                    f.write(content_dl)
                                img_data = content_dl
                except Exception as e:
                    print(f"[{session_id}] Error loading explicit stock image from disk: {e}")
            else:
                print(f"[{session_id}] Downloading explicit stock image URL: {img_url}")
                try:
                    req_explicit = urllib.request.Request(img_url, headers={"User-Agent": user_agent})
                    with urllib.request.urlopen(req_explicit, timeout=30) as response_explicit:
                        img_data = response_explicit.read()
                except Exception as e:
                    print(f"[{session_id}] Error downloading explicit stock image URL: {e}")

        if img_data is None:
            # Use request-level key if provided, otherwise fall back to server-side key
            pexels_key = (req.pexels_api_key or "").strip().strip("'\"") or PEXELS_API_KEY
            img_data = fetch_stock_image(search_query, overlay_type, idx, pexels_key=pexels_key,
                                         tech_only=is_tech_channel)

        # Track this image's hash to prevent duplicates
        img_hash = _hash_image(img_data)
        _used_image_hashes.add(img_hash)

        # Convert image data to inline Base64 data URL to prevent event loop request blockages
        img_b64 = base64.b64encode(img_data).decode("utf-8")
        # Sniff the real type — Pexels serves JPEG, so a blanket image/png
        # mislabels most backgrounds (browsers cope, but no reason to lie).
        if img_data[:2] == b"\xff\xd8":
            mime = "image/jpeg"
        elif img_data[:4] == b"RIFF" and img_data[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            mime = "image/png"

        scene_data = {
            "imageUrl": f"data:{mime};base64,{img_b64}",
            "text": scene.get("text", ""),
            "voiceover": scene.get("voiceover", ""),
            "title": scene.get("title"),
            "subtitle": scene.get("subtitle"),
            "secondaryText": scene.get("secondaryText"),
            "type": scene.get("type"),
            "durationInFrames": scene.get("durationInFrames", 175),
            "textAnimation": scene.get("textAnimation"),
        }
        
        # Pass through scene-type-specific fields
        for field in ["leftLabel", "rightLabel", "listItems", "countFrom", "countTo", "countSuffix", "ctaText", "chartData", "ratingValue", "ratingMax"]:
            if scene.get(field) is not None:
                scene_data[field] = scene[field]

        # === STOCK VIDEO B-ROLL: scenes get real motion clips ===
        # Movement stops the scroll far better than a still photo + camera pan
        # (the 3-second-hold decides reach, and a visual change every scene
        # keeps mid-video retention up). The still image above always stays as
        # the fallback/poster, so a failed fetch just means a static scene.
        want_broll = HOOK_VIDEO_ENABLED and SCENE_VIDEO_MODE != "off" and (
            SCENE_VIDEO_MODE == "all" or idx == 0
        )
        if want_broll:
            pexels_key = (req.pexels_api_key or "").strip().strip("'\"") or PEXELS_API_KEY
            # Scene length later auto-syncs to speech; require a comfortable margin
            planned_sec = scene.get("durationInFrames", 175) / 30.0
            # Prefer the LLM's topic-relevant motion query; auto-tech channels
            # get a tech-motion fallback so a missing videoQuery still pulls
            # tech footage, not a random loop (is_tech_channel hoisted above).
            # IMPORTANT: pass the RAW searchQuery, not the anchored still-image
            # query — the anchor adds tech-photo words that suppress
            # _build_broll_query's motion-specific term, and an "abstract ..."
            # lead word then dominates Pexels video ranking (bubble-clip case).
            broll_query = _build_broll_query(
                scene.get("videoQuery"), raw_search_query, idx, is_tech_channel
            )
            print(f"[{session_id}] Scene {idx + 1} b-roll query: '{broll_query}'")
            video_bytes = fetch_hook_video(broll_query, pexels_key, min_duration_sec=max(6.0, planned_sec + 1.0))
            if video_bytes:
                broll_dir = os.path.join(PUBLIC_DIR, "hook-videos")
                os.makedirs(broll_dir, exist_ok=True)
                broll_name = f"broll-{session_id}-{idx}.mp4"
                with open(os.path.join(broll_dir, broll_name), "wb") as vf:
                    vf.write(video_bytes)
                # Relative path — resolved via staticFile() in the Remotion layer
                scene_data["videoUrl"] = f"hook-videos/{broll_name}"
                print(f"[{session_id}] Scene {idx + 1} will use stock VIDEO: {scene_data['videoUrl']}")
            else:
                print(f"[{session_id}] No suitable clip for scene {idx + 1}; falling back to still image")

        scenes_with_images.append(scene_data)

    # 3b. AUTOMATICALLY APPEND OUTRO SCENE ONLY FOR THE TECH CHANNEL (incl. scheduled gh- runs)
    if session_id.startswith(AUTO_CHANNEL_PREFIXES):
        # Dedupe guard: the appended outro is the ONLY follow-ask in the video.
        # If the LLM closer still ends with its own "Follow Neon Node" line
        # (older prompt behavior / prompt disobedience), the follow CTA plays
        # twice back-to-back — scrub it from the closer before appending.
        if scenes_with_images:
            _closer = scenes_with_images[-1]
            _follow_rx = re.compile(r"\b(follow|subscribe)\b", re.IGNORECASE)
            # Branded asks plus ADJACENCY forms of a generic channel CTA
            # ("follow for more", "hit follow", "don't forget to subscribe").
            # Adjacency keeps content lines safe: "follow the migration guide
            # for more details" and a "FOLLOW THE MONEY" headline both survive.
            _cta_rx = re.compile(
                r"neon[\s.\-]*node|@neon[\w.]*|\bthe channel\b"
                r"|\b(follow|subscribe)\s+(us|me)\b"
                r"|\b(follow|subscribe)\s+for\s+(more|daily|weekly)\b"
                r"|\b(hit|smash|tap)\s+(that\s+|the\s+)?(follow|subscribe)\b"
                r"|\b(follow|subscribe)\s+button\b"
                r"|\b(don'?t forget to|make sure to|be sure to|remember to)\s+(follow|subscribe)\b"
                r"|\bturn on notifications?\b",
                re.IGNORECASE,
            )
            _vo = _closer.get("voiceover") or ""
            _sentences = re.split(r"(?<=[.!?])\s+", _vo)
            _kept = [s for s in _sentences if not (_follow_rx.search(s) and _cta_rx.search(s))]
            if _kept and len(_kept) < len(_sentences):
                _closer["voiceover"] = " ".join(_kept).strip()
                print(f"[{session_id}] Scrubbed follow-CTA sentence from closer voiceover (appended outro already covers it)")
            # DROP on-screen fields that carry the ask — never rewrite them.
            # Any replacement copy risks duplicating a sibling field on the
            # same frame, and this runs after the anti-repetition prune, so
            # nothing downstream would catch that duplication. The renderers
            # skip absent fields cleanly.
            for _fld in ("text", "title", "subtitle", "ctaText"):
                _val = _closer.get(_fld)
                if isinstance(_val, str) and _follow_rx.search(_val) and _cta_rx.search(_val):
                    _closer.pop(_fld, None)
                    print(f"[{session_id}] Dropped follow-CTA closer field '{_fld}' (outro card handles the ask)")

        outro_handle = os.environ.get("INSTAGRAM_TECH_USERNAME", "Neon Node").strip()
        outro_logo_url = os.environ.get("INSTAGRAM_TECH_LOGO_URL")
        
        # Formulate handle cleanly
        if outro_handle.startswith("@") or " " in outro_handle:
            outro_handle_clean = outro_handle
        else:
            # Add @ if it is a pure handle username
            outro_handle_clean = "@" + outro_handle.lstrip("@")
            
        # Load or download the logo image
        logo_data = None
        logo_mime = "image/png"
        
        if outro_logo_url:
            print(f"[{session_id}] Downloading outro logo image: {outro_logo_url}")
            try:
                import urllib.request
                req_logo = urllib.request.Request(outro_logo_url, headers={"User-Agent": user_agent})
                with urllib.request.urlopen(req_logo, timeout=15) as response_logo:
                    logo_data = response_logo.read()
                    if outro_logo_url.lower().endswith((".jpg", ".jpeg")):
                        logo_mime = "image/jpeg"
            except Exception as e:
                print(f"[{session_id}] Error downloading outro logo: {e}")
                
        # If no URL is specified or download fails, try reading the local tech_logo.png
        if logo_data is None:
            local_logo_path = os.path.join(PUBLIC_DIR, "tech_logo.png")
            if os.path.exists(local_logo_path):
                print(f"[{session_id}] Loading local outro logo image: {local_logo_path}")
                try:
                    with open(local_logo_path, "rb") as f:
                        logo_data = f.read()
                        logo_mime = "image/png"
                except Exception as e:
                    print(f"[{session_id}] Error reading local logo asset: {e}")
                    
        if logo_data is None:
            # Empty transparent 1x1 image as fallback so the React renderer uses the inline vector icon
            logo_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
            logo_mime = "image/png"
            
        logo_b64 = base64.b64encode(logo_data).decode("utf-8")
        
        outro_scene_data = {
            "imageUrl": f"data:{logo_mime};base64,{logo_b64}",
            "text": outro_handle_clean,
            "voiceover": f"Follow Neon Node for daily tech explainers and concepts.",
            "title": "NEON NODE",
            "subtitle": "TECH EXPLAINED",
            "type": "outro",
            "durationInFrames": 120, # 4 seconds duration
            "textAnimation": "glitch-decode"
        }
        scenes_with_images.append(outro_scene_data)
        print(f"[{session_id}] Appended automated Outro scene with handle: {outro_handle_clean}")

    # 4. GENERATE NEURAL VOICEOVER AND SUBTITLES (FREE)
    voiceover_filename = None
    subtitles = []
    
    def run_async(coro):
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        def target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(target)
            return future.result()

    try:
        req_voice = pipeline_cfg.voice if pipeline_cfg else None
        req_rate = pipeline_cfg.voiceRate if pipeline_cfg else None
        req_pitch = pipeline_cfg.voicePitch if pipeline_cfg else None
        coro = generate_voiceover_and_alignment(
            scenes_with_images,
            session_id,
            PUBLIC_DIR,
            voice=req_voice,
            rate=req_rate,
            pitch=req_pitch
        )
        voiceover_filename, subtitles = run_async(coro)
    except Exception as vo_err:
        print(f"[{session_id}] Error in voiceover/subtitles pipeline: {vo_err}")
        if REQUIRE_VOICEOVER:
            render_status_store[session_id]["status"] = "error"
            render_status_store[session_id]["error"] = f"Voiceover pipeline failed: {vo_err}"
            raise Exception(f"Voiceover pipeline failed ({vo_err}) — aborting render so no broken-audio video is posted.")

    if REQUIRE_VOICEOVER and not voiceover_filename:
        render_status_store[session_id]["status"] = "error"
        render_status_store[session_id]["error"] = "Voiceover missing after synthesis."
        raise Exception("Voiceover track is missing after synthesis — aborting render so no silent video is posted.")

    # Update status
    render_status_store[session_id]["status"] = "rendering"
    render_status_store[session_id]["progress"] = 0.65

    voiceover_url = f"{base_url}/{voiceover_filename}" if voiceover_filename else None

    final_input_props = {
        "scenes": scenes_with_images,
        "theme": parsed_script["theme"],
        "pipeline": parsed_script.get("pipeline"),
        "voiceoverUrl": voiceover_url,
        "subtitles": subtitles,
    }

    # Ensure background music is downloaded locally to prevent buffering timeouts during render
    MUSIC_URLS = {
        "ambient-tech": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "lofi-chill": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
        "cosmic-synth": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
    }
    music_track = parsed_script.get("theme", {}).get("musicTrack", "ambient-tech")
    if music_track in MUSIC_URLS:
        local_music_path = os.path.join(PUBLIC_DIR, f"{music_track}.mp3")
        if not os.path.exists(local_music_path):
            print(f"[{session_id}] Downloading background music {music_track} locally to prevent audio dropouts...")
            import urllib.request
            for attempt in (1, 2):
                try:
                    urllib.request.urlretrieve(MUSIC_URLS[music_track], local_music_path)
                    print(f"[{session_id}] Successfully downloaded {music_track}.mp3")
                    break
                except Exception as e:
                    # urlretrieve can leave a partial file behind; remove it so
                    # the existence checks below don't mistake it for a track.
                    if os.path.exists(local_music_path):
                        os.remove(local_music_path)
                    print(f"[{session_id}] Music download attempt {attempt} failed: {e}")
        # A missing music file 404s inside Remotion and aborts the entire
        # render. Unlike the voiceover, music is decorative — drop it loudly
        # and ship the video rather than losing the whole post.
        if not os.path.exists(local_music_path) or os.path.getsize(local_music_path) == 0:
            print(f"[{session_id}] ERROR: {music_track}.mp3 unavailable after retries — rendering WITHOUT background music.")
            parsed_script["theme"]["musicTrack"] = "none"
    props_filename = f"props-{session_id}.json"
    props_filepath = os.path.join(PUBLIC_DIR, props_filename)
    with open(props_filepath, "w") as f:
        json.dump(final_input_props, f)

    # Determine file extension from output format
    ext = "mp4" if output_format == "mp4" else ("webm" if output_format == "webm" else "gif")
    video_filename = f"video-{session_id}.{ext}"
    video_filepath = os.path.join(PUBLIC_DIR, video_filename)

    # Determine output dimensions from the validated aspect ratio (default to 9:16 Reels)
    aspect_ratio = parsed_script.get("theme", {}).get("aspectRatio", "9:16")
    dimensions = ASPECT_RATIO_MAP.get(aspect_ratio, ASPECT_RATIO_MAP["9:16"])
    width = dimensions["width"]
    height = dimensions["height"]

    # Build Remotion CLI command with quality presets
    preset = QUALITY_PRESETS[quality]
    codec = FORMAT_CODEC_MAP[output_format]

    remotion_cmd = [
        "npx", "remotion", "render",
        "MyComp",
        video_filepath,
        f"--props={props_filepath}",
        f"--width={width}",
        f"--height={height}",
        f"--crf={preset['crf']}",
        f"--jpeg-quality={preset['jpeg_quality']}",
        f"--scale={preset['scale']}",
        f"--codec={codec}",
        "--overwrite",
    ]

    # Add concurrency if supported
    if preset.get("concurrency"):
        env_concurrency = os.environ.get("REMOTION_CONCURRENCY")
        if env_concurrency:
            try:
                concurrency = int(env_concurrency)
                print(f"[{session_id}] Using manual REMOTION_CONCURRENCY override: {concurrency}")
            except ValueError:
                print(f"[{session_id}] Invalid REMOTION_CONCURRENCY value: '{env_concurrency}'. Falling back to preset limit.")
                concurrency = preset["concurrency"]
        else:
            # Cap concurrency to Node.js/cgroups aware CPU cores limit to prevent Remotion from failing
            # Leave at least 1 core free for FastAPI/system to prevent server unresponsiveness,
            # except on low-resource environments (<= 3 cores) where we utilize all available cores.
            available_cores = get_available_cores()
            if available_cores <= 3:
                concurrency = available_cores
            else:
                concurrency = available_cores - 1
            concurrency = min(preset["concurrency"], concurrency)
        remotion_cmd.append(f"--concurrency={concurrency}")

    print(f"[{session_id}] Invoking Remotion Renderer: {' '.join(remotion_cmd)}")
    try:
        try:
            total_frames = sum(s.get("durationInFrames", 175) for s in scenes_with_images) or 1500
            
            # Use Popen to stream stdout/stderr and avoid blocking on OS pipe buffers (deadlock prevention)
            process = subprocess.Popen(
                remotion_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            full_output = []
            frame_pattern = re.compile(r'(?:Rendered frame|frame\s*=\s*)(\d+)')
            
            # Read standard output and standard error merged line-by-line
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                line_str = line.strip()
                print(f"[{session_id}][Remotion] {line_str}")
                full_output.append(line)
                
                # Parse progress dynamically from output
                match = frame_pattern.search(line_str)
                if match:
                    try:
                        current_frame = int(match.group(1))
                        pct = min(1.0, current_frame / total_frames)
                        current_progress = round(0.65 + pct * 0.23, 2)
                        render_status_store[session_id]["progress"] = current_progress
                    except Exception:
                        pass
                        
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                stderr_output = "".join(full_output)
                raise subprocess.CalledProcessError(
                    returncode=return_code,
                    cmd=remotion_cmd,
                    output="".join(full_output),
                    stderr=stderr_output
                )
                
            print(f"[{session_id}] Rendering successfully finished.")
        except subprocess.CalledProcessError as e:
            print(f"[{session_id}] Rendering failed: {e.stderr or e.output}")
            render_status_store[session_id]["status"] = "error"
            render_status_store[session_id]["error"] = "Remotion render failed"
            raise HTTPException(status_code=500, detail=f"Remotion compilation failed: {e.stderr or e.output}")
    finally:
        # Cleanup temporary files (props and voiceover audio)
        print(f"[{session_id}] Cleaning up temporary render assets...")
        if 'props_filepath' in locals() and os.path.exists(props_filepath):
            try:
                os.remove(props_filepath)
            except Exception as cleanup_err:
                print(f"[{session_id}] Error cleaning up props file: {cleanup_err}")
                
        if 'voiceover_filename' in locals() and voiceover_filename:
            voiceover_filepath = os.path.join(PUBLIC_DIR, voiceover_filename)
            if os.path.exists(voiceover_filepath):
                try:
                    os.remove(voiceover_filepath)
                except Exception as cleanup_err:
                    print(f"[{session_id}] Error cleaning up voiceover file: {cleanup_err}")

        # B-roll clips are only needed during the render — at ~20MB each and
        # 5-6 videos/day they would fill the Space's disk within days.
        broll_dir = os.path.join(PUBLIC_DIR, "hook-videos")
        if os.path.isdir(broll_dir):
            for fname in os.listdir(broll_dir):
                if session_id in fname:
                    try:
                        os.remove(os.path.join(broll_dir, fname))
                    except Exception as cleanup_err:
                        print(f"[{session_id}] Error cleaning up b-roll clip {fname}: {cleanup_err}")

        # AI-tier debug copies follow the same rule (the real image data is
        # base64-inlined into the props; these exist only for spot-checking).
        ai_dir = os.path.join(PUBLIC_DIR, "ai-images")
        if os.path.isdir(ai_dir):
            for fname in os.listdir(ai_dir):
                if session_id in fname:
                    try:
                        os.remove(os.path.join(ai_dir, fname))
                    except Exception as cleanup_err:
                        print(f"[{session_id}] Error cleaning up AI image {fname}: {cleanup_err}")

    # Bypass HF Space bandwidth throttling by generating a fast temporary download link
    render_status_store[session_id]["status"] = "uploading"
    render_status_store[session_id]["progress"] = 0.9

    fast_url = None
    try:
        print(f"[{session_id}] Uploading to tmpfiles.org for fast download...")
        with open(video_filepath, 'rb') as f:
            upload_res = requests.post("https://tmpfiles.org/api/v1/upload", files={'file': f}, timeout=60)
        if upload_res.status_code == 200:
            tmp_url = upload_res.json()["data"]["url"]
            fast_url = tmp_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
            print(f"[{session_id}] Fast download URL generated: {fast_url}")
    except Exception as e:
        print(f"[{session_id}] Fast upload failed, falling back to local serving: {e}")

    video_url = fast_url if fast_url else f"{base_url}/{video_filename}"

    # Mark as complete
    render_status_store[session_id]["status"] = "complete"
    render_status_store[session_id]["progress"] = 1.0
    render_status_store[session_id]["video_url"] = video_url
    render_status_store[session_id]["completed_at"] = time.time()

    # Assemble the metadata the posting dispatchers write to the post ledger.
    # Auto channels only — manual/API renders join the feedback loop solely
    # when the caller supplied topic_meta.
    session_channel = ("news" if session_id.startswith(("gh-", "auto-news")) else
                       "tech" if session_id.startswith(("auto-tech-", "force-post-")) else
                       "manual")
    if ENABLE_POST_LEDGER and (session_channel != "manual" or req.topic_meta):
        ledger_topic = dict(req.topic_meta or {})
        ledger_topic.setdefault("title", (req.prompt or "")[:160])
        ledger_topic.setdefault("keywords", _extract_topic_keywords(ledger_topic.get("title", "")))
        render_status_store[session_id]["ledger_meta"] = {
            "ts": int(time.time()),
            "posted_hour_utc": datetime.datetime.utcnow().hour,
            "channel": session_channel,
            "topic": ledger_topic,
            "style_pack": chosen_style_pack,
            "seed": video_seed,
            "voice": render_status_store[session_id].get("resolved_voice"),
            "hook_type": variety_meta.get("hook_type"),
            "scene_count": len(parsed_script.get("scenes", [])),
            "video_seconds": round(
                sum(s.get("durationInFrames", 0) for s in parsed_script.get("scenes", [])) / 30.0, 1),
        }

    # Trigger background Instagram posting if configured
    ig_cfg = pipeline_cfg.instagram
    if ig_cfg and ig_cfg.enabled:
        print(f"[{session_id}] Instagram posting is enabled. Spawning posting thread...")
        
        t_key = (req.text_gen_key or req.nvidia_nim_key or "").strip().strip("'\"")
        if not t_key:
            t_key = (os.environ.get("NVIDIA_NIM_KEY") or os.environ.get("TEXT_GEN_KEY") or "").strip()
            
        def run_ig_post_thread():
            try:
                target_path = video_filepath if os.path.exists(video_filepath) else video_url
                dispatch_instagram_post(

                    video_url_or_path=target_path,
                    config=ig_cfg,
                    script_data=parsed_script,
                    text_gen_key=t_key,
                    session_id=session_id,
                    status_dict_ref=render_status_store[session_id]
                )
            except Exception as ex:
                print(f"[{session_id}] Background Instagram post thread error: {ex}")

        # sync_delivery (CLI/GitHub Actions): run inline so the process doesn't
        # exit before the upload completes (same fix as Telegram — Pain Point 5).
        if sync_delivery:
            run_ig_post_thread()
        else:
            threading.Thread(target=run_ig_post_thread, daemon=True).start()

    # Trigger background Telegram posting if configured
    tg_cfg = pipeline_cfg.telegram
    # Fallback to env vars if enabled but not in config
    if (tg_cfg and tg_cfg.enabled) or (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        print(f"[{session_id}] Telegram posting is enabled. Spawning posting thread...")
        
        t_key = (req.text_gen_key or req.nvidia_nim_key or "").strip().strip("'\"")
        if not t_key:
            t_key = (os.environ.get("NVIDIA_NIM_KEY") or os.environ.get("TEXT_GEN_KEY") or "").strip()
            
        def run_tg_post_thread():
            try:
                dispatch_telegram_post(
                    video_url_or_path=video_filepath, # Prefer local path for telegram upload
                    config=tg_cfg or TelegramConfig(enabled=True),
                    script_data=parsed_script,
                    text_gen_key=t_key,
                    session_id=session_id,
                    status_dict_ref=render_status_store[session_id]
                )
            except Exception as ex:
                print(f"[{session_id}] Background Telegram post thread error: {ex}")

        if sync_delivery:
            run_tg_post_thread()
        else:
            threading.Thread(target=run_tg_post_thread, daemon=True).start()

    # Trigger YouTube Shorts posting if configured (config, or env-enabled)
    yt_cfg = pipeline_cfg.youtube
    yt_env_enabled = (
        os.environ.get("ENABLE_YOUTUBE_AUTOPOST", "").strip().lower() == "true"
        and os.environ.get("YT_REFRESH_TOKEN", "").strip()
    )
    if (yt_cfg and yt_cfg.enabled) or yt_env_enabled:
        print(f"[{session_id}] YouTube posting is enabled. Dispatching upload...")

        t_key = (req.text_gen_key or req.nvidia_nim_key or "").strip().strip("'\"")
        if not t_key:
            t_key = (os.environ.get("NVIDIA_NIM_KEY") or os.environ.get("TEXT_GEN_KEY") or "").strip()

        def run_yt_post_thread():
            try:
                dispatch_youtube_post(
                    video_url_or_path=video_filepath,  # Local path: upload straight from disk
                    config=yt_cfg or YouTubeConfig(enabled=True),
                    script_data=parsed_script,
                    text_gen_key=t_key,
                    session_id=session_id,
                    status_dict_ref=render_status_store[session_id]
                )
            except Exception as ex:
                print(f"[{session_id}] Background YouTube post thread error: {ex}")

        if sync_delivery:
            run_yt_post_thread()
        else:
            threading.Thread(target=run_yt_post_thread, daemon=True).start()

    # Trigger Facebook Reels cross-post if configured (config, or env-enabled)
    fb_cfg = pipeline_cfg.facebook
    fb_env_enabled = bool(
        os.environ.get("ENABLE_FACEBOOK_AUTOPOST", "").strip().lower() == "true"
        and os.environ.get("FB_PAGE_ID", "").strip()
        and (os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
             or os.environ.get("FB_ACCESS_TOKEN", "").strip())
    )
    if (fb_cfg and fb_cfg.enabled) or fb_env_enabled:
        print(f"[{session_id}] Facebook Reels posting is enabled. Dispatching...")

        t_key = (req.text_gen_key or req.nvidia_nim_key or "").strip().strip("'\"")
        if not t_key:
            t_key = (os.environ.get("NVIDIA_NIM_KEY") or os.environ.get("TEXT_GEN_KEY") or "").strip()

        def run_fb_post_thread():
            try:
                dispatch_facebook_reels_post(
                    video_url_or_path=video_filepath,  # Local path: binary upload from disk
                    config=fb_cfg or FacebookConfig(enabled=True),
                    script_data=parsed_script,
                    text_gen_key=t_key,
                    session_id=session_id,
                    status_dict_ref=render_status_store[session_id],
                    hosted_fallback_url=fast_url,  # tmpfiles URL → file_url fallback
                )
            except Exception as ex:
                print(f"[{session_id}] Background Facebook post thread error: {ex}")

        if sync_delivery:
            run_fb_post_thread()
        else:
            threading.Thread(target=run_fb_post_thread, daemon=True).start()

    result_payload = {
        "status": "success",
        "session_id": session_id,
        "video_url": video_url,
        "script": parsed_script,
        "pipeline": {
            "quality": quality,
            "output_format": output_format,
            "aspect_ratio": parsed_script["theme"].get("aspectRatio", "9:16"),
        },
    }

    if ig_cfg and ig_cfg.enabled:
        result_payload["instagram"] = {
            "status": "queued_for_post",
            "method": ig_cfg.method
        }

    if (tg_cfg and tg_cfg.enabled) or (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        result_payload["telegram"] = {
            "status": "queued_for_post"
        }

    if (yt_cfg and yt_cfg.enabled) or yt_env_enabled:
        result_payload["youtube"] = {
            "status": "queued_for_post"
        }

    if (fb_cfg and fb_cfg.enabled) or fb_env_enabled:
        result_payload["facebook"] = {
            "status": "queued_for_post"
        }

    # Fire webhook if configured
    if pipeline_cfg.webhookUrl:
        webhook_payload = {
            **result_payload,
            "callback_id": pipeline_cfg.callbackId,
        }
        _send_webhook(pipeline_cfg.webhookUrl, webhook_payload, session_id)

    return result_payload


def _run_background_render(req: RenderRequest, session_id: str):
    try:
        _execute_render(req, session_id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        if session_id not in render_status_store:
            render_status_store[session_id] = {}
        render_status_store[session_id]["status"] = "error"
        render_status_store[session_id]["error"] = str(e)
        print(f"[{session_id}] Background render failed: {e}")


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.post("/render", dependencies=[Depends(verify_api_key)])
async def render_video(req: RenderRequest, background_tasks: BackgroundTasks):
    """Main render endpoint — generates a complete video from a text prompt."""
    session_id = str(uuid.uuid4())[:8]
    render_status_store[session_id] = {
        "status": "queued",
        "progress": 0.0,
        "started_at": time.time(),
        "prompt": req.prompt,
    }
    background_tasks.add_task(_run_background_render, req, session_id)
    return {
        "status": "queued",
        "session_id": session_id
    }


@app.post("/render/batch", dependencies=[Depends(verify_api_key)])
async def render_batch(req: BatchRenderRequest, background_tasks: BackgroundTasks):
    """Accept multiple render requests. Returns session IDs immediately.
    
    Each render is queued sequentially in the background.
    Use GET /render/status/{session_id} to track progress.
    """
    session_ids = []
    
    for render_req in req.renders:
        sid = str(uuid.uuid4())[:8]
        session_ids.append(sid)
        render_status_store[sid] = {
            "status": "queued",
            "progress": 0.0,
            "prompt": render_req.prompt,
            "queued_at": time.time(),
        }
    
    def _run_batch():
        for i, render_req in enumerate(req.renders):
            sid = session_ids[i]
            try:
                _execute_render(render_req, sid)
            except Exception as e:
                render_status_store[sid]["status"] = "error"
                render_status_store[sid]["error"] = str(e)
                print(f"[{sid}] Batch render failed: {e}")
    
    background_tasks.add_task(_run_batch)
    
    return {
        "status": "batch_queued",
        "session_ids": session_ids,
        "total": len(session_ids),
        "status_endpoint": "/render/status/{session_id}",
    }


@app.get("/render/status/{session_id}", dependencies=[Depends(verify_api_key)])
async def render_status(session_id: str):
    """Check the status of a render job.
    
    Returns: status (queued|generating_script|parsing_script|sourcing_assets|
                     rendering|uploading|complete|error),
             progress (0.0 to 1.0), and video_url when complete.
    """
    if session_id not in render_status_store:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    return render_status_store[session_id]


@app.get("/render/schema", dependencies=[Depends(verify_api_key)])
async def render_schema():
    """Return the full JSON schema for API consumers and automation pipelines.
    
    This endpoint documents every available option, its allowed values,
    and descriptions — perfect for building UIs or pipeline integrations.
    """
    return {
        "schema_version": "2.0.0",
        "theme": {
            "primaryColor": {"type": "hex_color", "example": "#00f0ff"},
            "secondaryColor": {"type": "hex_color", "example": "#ff007f"},
            "overlayType": {
                "type": "enum",
                "values": ALLOWED_OVERLAY_TYPES,
                "descriptions": {
                    "grid-hud": "Sci-fi holographic grid with scanning laser lines",
                    "particles": "Gentle floating dust particles drifting upward",
                    "clean": "No visual overlay, just the image and text",
                    "vhs-glitch": "Retro VHS scanlines with chromatic aberration",
                    "fantasy-sparks": "Drifting celestial spark lights",
                },
            },
            "fontFamilyName": {
                "type": "enum",
                "values": ALLOWED_FONTS,
            },
            "musicTrack": {
                "type": "enum",
                "values": ALLOWED_MUSIC,
            },
            "cameraMotion": {
                "type": "enum",
                "values": ALLOWED_CAMERA,
            },
            "subtitlePosition": {
                "type": "enum",
                "values": ALLOWED_SUBTITLE_POS,
            },
            "overlayOpacity": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.8},
            "transitionStyle": {
                "type": "enum",
                "values": ALLOWED_TRANSITIONS,
                "descriptions": {
                    "crossfade": "Smooth opacity blend between scenes",
                    "slide-left": "Scene slides in from right, exits to left",
                    "zoom-through": "Camera zooms through into next scene",
                    "glitch-cut": "Hard cut with RGB-split glitch flash",
                    "none": "Hard cut, no transition effect",
                },
            },
            "aspectRatio": {
                "type": "enum",
                "values": ALLOWED_ASPECT_RATIOS,
                "dimensions": ASPECT_RATIO_MAP,
            },
            "gradientOverlay": {
                "type": "enum",
                "values": ALLOWED_GRADIENTS,
            },
        },
        "scene_types": {
            "type": "enum",
            "values": ALLOWED_SCENE_TYPES,
            "descriptions": {
                "hero": "Large centered title with subtitle. Opening/closing scenes.",
                "testimonial": "Quote-style layout with left border accent.",
                "metric": "Oversized centered number/stat with label.",
                "split": "General purpose layout. Default for unspecified types.",
                "countdown": "Animated counting number. Extra: countFrom, countTo, countSuffix.",
                "comparison": "Side-by-side split. Extra: leftLabel, rightLabel.",
                "list": "Bullet-point list with staggered reveal. Extra: listItems[].",
                "cta": "Call-to-action with pulsing button. Extra: ctaText.",
                "bar-chart": "Animated horizontal bars. Extra: chartData[{label,value}] (REAL numbers only; degrades to list if absent).",
                "chart": "Animated donut of part-to-whole shares. Extra: chartData[{label,value}].",
                "line-chart": "Draw-on trend line with area fill. Extra: chartData[{label,value}] in left→right order (needs >=2 points).",
                "rating": "Star rating with partial fill + count-up. Extra: ratingValue, ratingMax (default 5).",
                "ui-demo": "Simulated app: cursor types into a field, spinner, results, button. Uses title/text/subtitle/listItems/ctaText.",
            },
        },
        "scene_fields": {
            "chartData": {"type": "array", "items": {"label": "string", "value": "number"}, "used_by": ["bar-chart", "chart", "line-chart"]},
            "ratingValue": {"type": "float", "used_by": ["rating"]},
            "ratingMax": {"type": "int", "default": 5, "used_by": ["rating"]},
        },
        "text_animations": {
            "type": "enum",
            "values": ALLOWED_TEXT_ANIMATIONS,
        },
        "pipeline": {
            "outputFormat": {"type": "enum", "values": ["mp4", "webm", "gif"]},
            "quality": {
                "type": "enum",
                "values": ["draft", "standard", "high"],
                "presets": QUALITY_PRESETS,
            },
            "watermark": {"type": "string", "optional": True},
            "webhookUrl": {"type": "url", "optional": True},
            "callbackId": {"type": "string", "optional": True},
            "priority": {"type": "enum", "values": ["low", "normal", "urgent"]},
        },
    }


# =============================================================================
# INSTAGRAM POSTING AUTOMATION INTEGRATION
# =============================================================================

# In-memory store for standalone Instagram direct posting jobs
instagram_status_store: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Caption hashtag enforcement — deterministic backfill so posts never go out
# hashtag-less when the caption LLM under-delivers. Pure post-processing on
# generated caption TEXT; the posting/dispatch surface is untouched.
# ---------------------------------------------------------------------------

_HASHTAG_RE = re.compile(r"(?<![\w#&])#([A-Za-z][A-Za-z0-9_]{1,28})")

_HASHTAG_STOPWORDS = {
    "the", "and", "for", "with", "your", "this", "that", "than", "then", "from",
    "into", "just", "how", "why", "what", "when", "where", "its", "are", "was",
    "were", "will", "would", "could", "should", "have", "has", "had", "been",
    "being", "does", "doing", "dont", "cant", "wont", "also", "even", "still",
    "only", "much", "many", "more", "most", "less", "very", "really", "some",
    "every", "about", "after", "before", "over", "under", "between", "their",
    "there", "they", "them", "made", "make", "makes", "making", "gets", "got",
    "new", "now", "next", "like", "best", "better", "faster", "slower", "bigger",
    "thing", "things", "ways", "drops", "ships", "here", "says", "said",
}

# Needle -> IG tag, matched against topic title/subject/keywords + narration.
# A trailing "*" marks a prefix needle (matches any word starting with it).
_KEYWORD_TAG_MAP = {
    "ai": "artificialintelligence", "llm": "llm", "gpt": "chatgpt", "chatgpt": "chatgpt",
    "openai": "openai", "claude": "claudeai", "gemini": "googlegemini", "agent*": "aiagents",
    "hack*": "cybersecurity", "breach*": "cybersecurity", "vulnerab*": "infosec",
    "malware": "infosec", "quantum": "quantumcomputing", "docker": "docker",
    "kubernetes": "kubernetes", "python": "python", "javascript": "javascript",
    "typescript": "typescript", "react": "reactjs", "rust": "rustlang", "linux": "linux",
    "database": "database", "cloud": "cloudcomputing", "api": "api", "github": "github",
    "google": "google", "apple": "apple", "nvidia": "nvidia", "layoff*": "technews",
    "salary": "techcareers", "startup*": "startup", "open source": "opensource",
    "opensource": "opensource",
}
_CATEGORY_TAG_POOL = ["softwareengineering", "webdevelopment", "devops",
                      "computerscience", "backenddevelopment", "programmerlife",
                      "codinglife", "softwaredeveloper"]
_EVERGREEN_TAG_POOL = ["tech", "coding", "developer", "programming",
                       "technology", "software", "techreels", "technews", "innovation"]


def _kw_matches(needle: str, haystack: str) -> bool:
    if needle.endswith("*"):
        return re.search(r"\b" + re.escape(needle[:-1]), haystack) is not None
    return re.search(r"\b" + re.escape(needle) + r"s?\b", haystack) is not None


def _get_caption_topic_context(script_data: dict, session_id: Optional[str]) -> dict:
    """Topic title/subject/keywords for the caption generators, read-only.

    Auto-channel renders park their ledger topic in render_status_store before
    any dispatcher thread spawns; standalone callers fall back to the source
    prompt. Never raises.
    """
    topic: Dict[str, Any] = {}
    try:
        topic = dict(render_status_store.get(session_id or "", {})
                     .get("ledger_meta", {}).get("topic") or {})
    except Exception:
        topic = {}
    if not (topic.get("title") or topic.get("subject")):
        src = (script_data or {}).get("_sourcePrompt") or ""
        if src:
            topic = {"title": src[:160], "keywords": _extract_topic_keywords(src)}
    return {"title": str(topic.get("title") or ""),
            "subject": str(topic.get("subject") or ""),
            "keywords": list(topic.get("keywords") or [])}


def _slugify_hashtag(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", (text or "").lower())
    if not (3 <= len(slug) <= 28) or not slug[0].isalpha() or slug in _HASHTAG_STOPWORDS:
        return ""
    return slug


def _caption_tag_candidates(script_data: Optional[dict], session_id: str) -> list:
    """Ordered, deduped backfill candidates: topic slugs -> curated -> pools."""
    topic = _get_caption_topic_context(script_data or {}, session_id)
    scenes = (script_data or {}).get("scenes", [])
    haystack = " ".join(
        [topic["title"], topic["subject"]]
        + [str(s.get("voiceover") or "") for s in scenes]
    ).lower()

    candidates: list = []
    for kw in topic["keywords"]:
        candidates.append(_slugify_hashtag(str(kw)))
    if topic["subject"]:
        candidates.append(_slugify_hashtag(topic["subject"]))
        candidates.extend(_slugify_hashtag(w) for w in topic["subject"].split() if len(w) >= 4)
    for needle, tag in _KEYWORD_TAG_MAP.items():
        if _kw_matches(needle, haystack):
            candidates.append(tag)
    # Raw title words are the weakest signal — take at most 3, after the
    # curated matches, and only reasonably specific ones (>=5 chars).
    title_words = [_slugify_hashtag(w) for w in topic["title"].split() if len(w) >= 5]
    candidates.extend([w for w in title_words if w][:3])
    candidates.extend(_CATEGORY_TAG_POOL)
    candidates.extend(_EVERGREEN_TAG_POOL)
    return [c for c in candidates if c]


def _enforce_caption_hashtags(caption: str, script_data: Optional[dict] = None,
                              session_id: str = "", min_tags: int = 8,
                              max_tags: int = 12) -> str:
    """Guarantee the caption ends with at least min_tags hashtags, deterministically.

    Runs AFTER _scrub_fabricated_people; curated/slug tags cannot introduce
    people or numbers, so the fabrication guard stays exactly as strong.
    """
    caption = (caption or "").strip()
    existing = _HASHTAG_RE.findall(caption)
    if len(existing) > 28:
        # IG hard-rejects captions with >30 tags; trim before the frozen publish path.
        for tag in existing[28:]:
            caption = re.sub(r"(?<![\w#&])#" + re.escape(tag) + r"\b", "", caption, count=1)
        caption = re.sub(r"[ \t]{2,}", " ", caption).strip()
        existing = existing[:28]
    if len(existing) >= min_tags:
        return caption

    seen = {t.lower() for t in existing}
    target = min(min_tags, max_tags)
    added = []
    for tag in _caption_tag_candidates(script_data, session_id):
        if len(existing) + len(added) >= target:
            break
        if tag.lower() in seen:
            continue
        seen.add(tag.lower())
        added.append(tag)

    if not added:
        return caption
    print(f"[{session_id}] [Hashtags] Backfilled {len(added)} tags: "
          + " ".join("#" + t for t in added))
    tag_line = " ".join("#" + t for t in added)
    return (caption + "\n\n" + tag_line).strip() if caption else tag_line


def _backfill_youtube_tags(tags: list, script_data: dict, session_id: str,
                           min_count: int = 5, cap: int = 12) -> list:
    """Ensure the YouTube tags array has at least min_count clean keywords."""
    tags = [t for t in (tags or []) if t]
    seen = {t.lower() for t in tags}
    candidates = _caption_tag_candidates(script_data, session_id)
    candidates.extend(["tech", "technology", "programming", "software", "developer"])
    for tag in candidates:
        if len(tags) >= min_count:
            break
        if tag.lower() in seen:
            continue
        seen.add(tag.lower())
        tags.append(tag)
    return tags[:cap]


def generate_instagram_caption(
    script_data: dict, 
    text_gen_key: str, 
    text_api_base: Optional[str] = None, 
    text_model_name: Optional[str] = None,
    session_id: Optional[str] = None
) -> str:
    """Uses LLM to generate an engaging Instagram caption with emojis and hashtags based on the video script."""
    if not text_api_base:
        text_api_base = os.environ.get("TEXT_GEN_BASE_URL", "").strip() or None
    if not text_model_name:
        text_model_name = os.environ.get("TEXT_MODEL_NAME", "").strip() or None
        
    print("[Instagram] Generating caption via LLM...")
    scenes = script_data.get("scenes", [])
    scenes_summary = []
    for i, s in enumerate(scenes):
        label = " / ".join(x for x in (s.get("title", ""), s.get("text", "")) if x)
        vo = (s.get("voiceover") or "").strip()
        line = f"Scene {i+1} ({s.get('type', 'scene')}): {vo or label}"
        if vo and label:
            line += f"  [on-screen: {label}]"
        scenes_summary.append(line)
    scenes_text = "\n".join(scenes_summary)

    topic = _get_caption_topic_context(script_data, session_id)
    topic_block = ""
    if topic.get("title") or topic.get("subject"):
        topic_block = (f"TOPIC: {topic.get('title', '')}\n"
                       f"SUBJECT: {topic.get('subject') or topic.get('title', '')}\n"
                       f"TOPIC KEYWORDS: {', '.join(topic.get('keywords') or []) or 'n/a'}\n\n")

    caption_handle = os.environ.get("INSTAGRAM_TECH_USERNAME", "").strip() or "neon.node.tech"
    prompt = f"""You are writing the Instagram Reel caption for @{caption_handle}, a tech channel for developers.

{topic_block}WHAT THE VIDEO ACTUALLY SAYS (scene narration — the ONLY source of facts you may use):
{scenes_text}

Write the caption with this structure (no headings, no labels — just the caption text):

1. HOOK (first line): one punchy line, max 14 words, about THIS specific topic — name the actual subject or its sharpest concrete claim from the narration. Banned: generic templates ("90% of developers...", "This changes everything...", "You won't believe..."), and any percentage, benchmark or statistic that does not appear verbatim in the narration above.

2. VALUE (2-4 short lines): the most concrete, surprising specifics FROM THE NARRATION — real numbers, mechanisms, comparisons that were actually spoken. One idea per line, each may start with one fitting emoji. Do not restate the hook. Do not pad with adjectives.

3. CTA (one line): a natural question or nudge tied to the topic ("Would you run this in prod?", "Tag the dev who still does X by hand"). Never beg ("like and follow").

4. HASHTAGS (final line): 8-12 hashtags in ONE line — 3-4 specific to the subject/keywords above, 3-4 category tags (e.g. #softwareengineering #devops #webdevelopment), 2-3 broad reach tags (#tech #coding #developer). Lowercase, letters/numbers only.

HARD RULES:
- Everything BEFORE the hashtag line must stay under 500 characters.
- NEVER invent people, quotes, company names, benchmarks or numbers — only reuse facts present in the narration above.
- Plain text with emojis only. No markdown, no bullet symbols like "*" or "-".

Provide ONLY the final caption text. Do not include quotes, markdown headers, or introductory conversational text.
"""

    
    source_prompt = script_data.get("_sourcePrompt", "")

    # 1. Try using the failover query chain which has correct API keys and endpoints mapped dynamically
    try:
        caption = query_llm_with_failover(
            system_prompt="You are a social media copywriter specializing in viral Instagram captions.",
            user_prompt=prompt,
            max_tokens=1000,
            json_format=False,
            session_id=session_id or "Instagram"
        )
        if caption:
            caption = _scrub_fabricated_people(caption, source_prompt, session_id or "Instagram", "ig_caption")
            return _enforce_caption_hashtags(caption, script_data, session_id or "Instagram")
    except Exception as e:
        print(f"[Instagram] Failover caption generation failed: {e}. Trying direct request fallback...")

    # 2. Direct request fallback if failover fails or isn't available
    if text_api_base:
        text_url = text_api_base
        if not text_url.startswith("http://") and not text_url.startswith("https://"):
            text_url = "https://" + text_url
        if not text_url.endswith("/chat/completions"):
            text_url = text_url.rstrip("/") + "/chat/completions"
    else:
        text_url = "https://integrate.api.nvidia.com/v1/chat/completions"

    model_name = text_model_name or "meta/llama-3.3-70b-instruct"
    
    try:
        response = requests.post(
            text_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {text_gen_key}"
            },
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a social media copywriter specializing in viral Instagram captions."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            },
            timeout=60
        )
        if response.status_code == 200:
            caption = response.json()["choices"][0]["message"]["content"].strip()
            if caption.startswith('"') and caption.endswith('"'):
                caption = caption[1:-1].strip()
            caption = _scrub_fabricated_people(caption, source_prompt, session_id or "Instagram", "ig_caption")
            return _enforce_caption_hashtags(caption, script_data, session_id or "Instagram")
        else:
            print(f"[Instagram] LLM caption gen direct request failed: {response.text}")
    except Exception as e:
        print(f"[Instagram] Exception in direct request fallback: {e}")
    
    # Fallback caption if both fail — topic-aware, and the deterministic
    # backfill guarantees a full hashtag line even with zero LLM availability.
    fallback_title = scenes[0].get("title", "Awesome Tech Video!") if scenes else "Awesome Video!"
    topic_line = topic.get("subject") or topic.get("title") or fallback_title
    fallback = (f"🚀 {topic_line} — the 60-second breakdown.\n\n"
                f"Full story in the reel. 🎥\n\n"
                f"Would you ship this? Tell us below 👇")
    return _enforce_caption_hashtags(fallback, script_data, session_id or "Instagram")


def test_instagram_official_connection(business_account_id: str, access_token: str, session_id: str = "") -> bool:
    """Preflight check to verify the Graph API connection and token validity before rendering a video."""
    import subprocess
    import json as json_module
    
    prefix = f"[{session_id}] " if session_id else ""
    api_base = os.environ.get("INSTAGRAM_API_BASE_URL", "https://graph.facebook.com").strip().rstrip("/")
    business_account_id = str(business_account_id).strip()
    access_token = str(access_token).strip()
    
    print(f"{prefix}[Instagram-Preflight] Testing connection to Graph API ({api_base})...")
    
    # We query the business account to check token validity
    test_url = f"{api_base}/v21.0/{business_account_id}?fields=id,name&access_token={access_token}"
    
    # Use curl just like the actual uploader to ensure the network path matches
    cmd = ["curl", "-sS", "--max-time", "15", "--tlsv1.2", "--retry", "2", "--retry-connrefused", test_url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if result.returncode != 0:
            if result.returncode == 35:
                print(f"{prefix}[Instagram-Preflight] TLS connect error (exit 35). Retrying with --insecure...")
                cmd.append("--insecure")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                
            if result.returncode != 0:
                print(f"{prefix}[Instagram-Preflight] ERROR: curl failed (exit {result.returncode}): {result.stderr.strip()}")
                return False
                
        data = json_module.loads(result.stdout)
        if "error" in data:
            print(f"{prefix}[Instagram-Preflight] ERROR from API: {data['error'].get('message', str(data))}")
            return False
            
        print(f"{prefix}[Instagram-Preflight] SUCCESS! Connected to IG account: {data.get('name', 'Unknown')} (ID: {data.get('id')})")
        return True
    except Exception as e:
        print(f"{prefix}[Instagram-Preflight] FATAL ERROR during connection check: {e}")
        return False

def test_instagram_unofficial_connection(username: str, password: str, session_id: str = "") -> bool:
    """Preflight check to verify instagrapi login credentials before rendering a video."""
    prefix = f"[{session_id}] " if session_id else ""
    print(f"{prefix}[Instagram-Preflight] Testing unofficial login for username: {username}...")
    
    try:
        from instagrapi import Client
        cl = Client()
        cl.delay_range = [2, 5]
        
        session_file = "instagram_session.json"
        if os.path.exists(session_file):
            try:
                cl.load_settings(session_file)
            except Exception:
                pass # Ignore load errors during preflight
                
        # login() will use the session if valid, otherwise it performs a full login
        cl.login(username, password)
        cl.dump_settings(session_file)
        
        # Perform a lightweight API call to ensure the session isn't restricted/banned
        user_id = cl.user_id_from_username(username)
        print(f"{prefix}[Instagram-Preflight] SUCCESS! Logged into IG account: {username} (ID: {user_id})")
        return True
    except Exception as e:
        print(f"{prefix}[Instagram-Preflight] FATAL ERROR during unofficial login check: {e}")
        return False

def post_to_instagram_official(
    video_url: str,
    caption: str,
    business_account_id: str,
    access_token: str,
    session_id: Optional[str] = None
) -> str:
    """Uploads a video to Instagram Reels using the official Graph API.
    
    Uses curl via subprocess to bypass Python 3.9's OpenSSL TLS handshake
    incompatibility with Meta's servers.
    
    Returns the published media ID.
    """
    import subprocess
    import json as json_module
    
    prefix = f"[{session_id}] " if session_id else ""
    print(f"{prefix}[Instagram-Official] Starting Graph API upload (curl mode)...")
    
    # Clean inputs
    business_account_id = str(business_account_id).strip()
    access_token = str(access_token).strip()
    
    # Load configurable API base URL (allows proxying to bypass Hugging Face SNI filters)
    api_base = os.environ.get("INSTAGRAM_API_BASE_URL", "https://graph.facebook.com").strip().rstrip("/")
    
    def _build_curl_tls_flags(insecure: bool = False) -> list:
        """Return TLS-related curl flags. Falls back to --insecure if needed."""
        flags = ["--tlsv1.2", "--retry", "2", "--retry-delay", "5", "--retry-connrefused"]
        if insecure:
            flags.append("--insecure")
        return flags

    def curl_post(url: str, form_data: dict, timeout: int = 120, insecure: bool = False) -> dict:
        """Execute a POST request via curl and return parsed JSON."""
        cmd = ["curl", "-sS", "-X", "POST", "--max-time", str(timeout)]
        cmd += _build_curl_tls_flags(insecure=insecure)
        for key, val in form_data.items():
            cmd += ["-F", f"{key}={val}"]
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        if result.returncode != 0:
            # Exit code 35 = SSL connect error; retry once with --insecure as last resort
            if result.returncode == 35 and not insecure:
                print(f"{prefix}[Instagram-Official] TLS handshake failed (exit 35); retrying with --insecure...")
                return curl_post(url, form_data, timeout=timeout, insecure=True)
            raise Exception(f"curl POST failed (exit {result.returncode}): {result.stderr.strip()}")
        return json_module.loads(result.stdout)

    def curl_get(url: str, timeout: int = 30, insecure: bool = False) -> dict:
        """Execute a GET request via curl and return parsed JSON."""
        cmd = ["curl", "-sS", "--max-time", str(timeout)]
        cmd += _build_curl_tls_flags(insecure=insecure)
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        if result.returncode != 0:
            if result.returncode == 35 and not insecure:
                print(f"{prefix}[Instagram-Official] TLS handshake failed (exit 35) on GET; retrying with --insecure...")
                return curl_get(url, timeout=timeout, insecure=True)
            raise Exception(f"curl GET failed (exit {result.returncode}): {result.stderr.strip()}")
        return json_module.loads(result.stdout)
    
    # Resolve local file if path or localhost URL passed
    if "localhost" in video_url or "127.0.0.1" in video_url:
        import urllib.parse
        parsed_p = urllib.parse.urlparse(video_url).path.lstrip("/")
        if os.path.exists(parsed_p):
            video_url = parsed_p
        elif os.path.exists(os.path.join("public", os.path.basename(parsed_p))):
            video_url = os.path.join("public", os.path.basename(parsed_p))

    is_local_file = not video_url.startswith("http") and os.path.exists(video_url)

    # Step 1: Create media container (retry up to 3 times)
    container_url = f"{api_base}/v21.0/{business_account_id}/media"

    form_data = {
        "media_type": "REELS",
        "caption": caption,
        "share_to_feed": "true",
        "access_token": access_token
    }
    
    if is_local_file:
        form_data["upload_type"] = "resumable"
        file_size = os.path.getsize(video_url)
        print(f"{prefix}[Instagram-Official] Step 1: Creating resumable container for local file '{video_url}' ({file_size:,} bytes)...")
    else:
        form_data["video_url"] = video_url
        print(f"{prefix}[Instagram-Official] Step 1: Creating container (video_url={video_url[:80]}...)...")
        
    container_id = None
    upload_uri = None
    
    for attempt in range(1, 4):
        try:
            data = curl_post(container_url, form_data, timeout=120)
            if "error" in data:
                err = data["error"].get("message", str(data))
                print(f"{prefix}[Instagram-Official] Container attempt {attempt}/3 API error: {err}")
                if attempt < 3:
                    time.sleep(15)
                continue
            container_id = data.get("id")
            upload_uri = data.get("uri")
            if container_id:
                break
            else:
                print(f"{prefix}[Instagram-Official] Container attempt {attempt}/3: No ID in response: {data}")
                if attempt < 3:
                    time.sleep(15)
        except Exception as ex:
            print(f"{prefix}[Instagram-Official] Container attempt {attempt}/3 error: {ex}")
            if attempt < 3:
                time.sleep(15)
    
    if not container_id:
        raise Exception("Failed to create media container after 3 attempts.")
        
    print(f"{prefix}[Instagram-Official] Container created successfully: {container_id}")
    
    # Step 1b: If local file, upload binary bytes to upload_uri via rupload
    if is_local_file:
        if not upload_uri:
            raise Exception("Resumable container creation succeeded but no upload URI was returned.")
            
        print(f"{prefix}[Instagram-Official] Step 1b: Uploading binary MP4 bytes to Meta rupload server...")
        file_size = os.path.getsize(video_url)
        
        up_cmd = ["curl", "-sS", "-X", "POST", "--max-time", "600"]
        up_cmd += _build_curl_tls_flags(insecure=False)
        up_cmd += [
            "-H", f"Authorization: OAuth {access_token}",
            "-H", "offset: 0",
            "-H", f"file_size: {file_size}",
            "-H", "Content-Type: application/octet-stream",
            "--data-binary", f"@{video_url}",
            upload_uri
        ]
        
        up_res = subprocess.run(up_cmd, capture_output=True, text=True, timeout=660)
        if up_res.returncode != 0:
            if up_res.returncode == 35:
                up_cmd.insert(-1, "--insecure")
                up_res = subprocess.run(up_cmd, capture_output=True, text=True, timeout=660)
            if up_res.returncode != 0:
                raise Exception(f"Meta rupload binary transfer failed (exit {up_res.returncode}): {up_res.stderr.strip()}")
                
        try:
            up_data = json_module.loads(up_res.stdout)
            if "error" in up_data:
                raise Exception(f"Meta rupload API error: {up_data['error']}")
            print(f"{prefix}[Instagram-Official] Binary upload complete!")
        except Exception as parse_err:
            if "success" not in up_res.stdout.lower() and "id" not in up_res.stdout.lower():
                print(f"{prefix}[Instagram-Official] Upload response: {up_res.stdout[:150]}")

    # Step 2: Poll container status until FINISHED
    max_polls = 48  # 48 * 15 seconds = 12 minutes max wait
    print(f"{prefix}[Instagram-Official] Step 2: Polling container status (up to 12 min)...")
    for attempt in range(max_polls):
        time.sleep(15)
        try:

            poll_url = f"{api_base}/v21.0/{container_id}?fields=status_code&access_token={access_token}"
            data = curl_get(poll_url, timeout=30)
            
            if "error" in data:
                print(f"{prefix}[Instagram-Official] Polling error (poll {attempt+1}): {data['error'].get('message', str(data))}")
                continue
                
            status_code = data.get("status_code")
            print(f"{prefix}[Instagram-Official] Container status (poll {attempt+1}/{max_polls}): {status_code}")
            
            if status_code == "FINISHED":
                break
            elif status_code == "ERROR":
                raise Exception(f"Container processing failed: {data}")
            # IN_PROGRESS → keep polling
        except Exception as ex:
            if "Container processing failed" in str(ex):
                raise
            print(f"{prefix}[Instagram-Official] Polling request error (poll {attempt+1}): {ex}")
    else:
        raise Exception("Timeout waiting for media container processing to finish (12 min).")
        
    # Step 3: Publish container
    publish_url = f"{api_base}/v21.0/{business_account_id}/media_publish"
    publish_data = {
        "creation_id": container_id,
        "access_token": access_token
    }
    
    print(f"{prefix}[Instagram-Official] Step 3: Publishing media...")
    data = curl_post(publish_url, publish_data, timeout=60)
    if "error" in data:
        raise Exception(f"Failed to publish container: {data['error'].get('message', str(data))}")
        
    media_id = data.get("id")
    print(f"{prefix}[Instagram-Official] Published successfully! Media ID: {media_id}")
    return media_id


def post_to_instagram_unofficial(
    video_path_or_url: str,
    caption: str,
    username: str,
    password: str,
    session_id: Optional[str] = None
) -> str:
    """Uploads a video to Instagram Reels using instagrapi (private mobile API)."""
    prefix = f"[{session_id}] " if session_id else ""
    print(f"{prefix}[Instagram-Unofficial] Logging in client for username: {username}...")
    
    from instagrapi import Client
    cl = Client()
    cl.delay_range = [2, 5]
    
    session_file = "instagram_session.json"
    if os.path.exists(session_file):
        try:
            print(f"{prefix}[Instagram-Unofficial] Loading saved session settings...")
            cl.load_settings(session_file)
        except Exception as e:
            print(f"{prefix}[Instagram-Unofficial] Error loading settings: {e}")
            
    try:
        cl.login(username, password)
        print(f"{prefix}[Instagram-Unofficial] Login successful.")
        cl.dump_settings(session_file)
    except Exception as e:
        raise Exception(f"Instagram private login failed: {e}")
        
    local_path = None
    temp_file = None
    if video_path_or_url.startswith("http://") or video_path_or_url.startswith("https://"):
        import tempfile
        print(f"{prefix}[Instagram-Unofficial] Downloading remote video: {video_path_or_url}")
        res = requests.get(video_path_or_url, stream=True, timeout=60)
        if res.status_code != 200:
            raise Exception(f"Failed to download video from URL: {video_path_or_url}")
        
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        for chunk in res.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        temp_file.close()
        local_path = temp_file.name
        print(f"{prefix}[Instagram-Unofficial] Downloaded to temp path: {local_path}")
    else:
        if not os.path.exists(video_path_or_url):
            check_path = os.path.join(PUBLIC_DIR, os.path.basename(video_path_or_url))
            if os.path.exists(check_path):
                local_path = check_path
            else:
                raise Exception(f"Local video file not found: {video_path_or_url}")
        else:
            local_path = video_path_or_url

    try:
        print(f"{prefix}[Instagram-Unofficial] Uploading Reel to Instagram...")
        media = cl.clip_upload(local_path, caption=caption)
        media_id = media.pk
        print(f"{prefix}[Instagram-Unofficial] Reel uploaded successfully! Media PK: {media_id}")
        return str(media_id)
    finally:
        if temp_file and os.path.exists(local_path):
            try:
                os.remove(local_path)
                print(f"{prefix}[Instagram-Unofficial] Temporary file cleaned up.")
            except Exception as e:
                print(f"{prefix}[Instagram-Unofficial] Failed to remove temp file: {e}")


TELEGRAM_CAPTION_LIMIT = 1024  # media captions; Telegram counts UTF-16 code units


def _truncate_utf16(text: str, limit: int) -> str:
    """Trim to at most `limit` UTF-16 code units (emoji count as 2), adding an
    ellipsis. Telegram rejects over-limit captions outright (400: caption is
    too long) — the video never sends — so this must run before every send."""
    if len(text.encode("utf-16-le")) // 2 <= limit:
        return text
    out, used = [], 0
    for ch in text:
        w = len(ch.encode("utf-16-le")) // 2
        if used + w > limit - 1:
            break
        out.append(ch)
        used += w
    return "".join(out).rstrip() + "…"


def post_to_telegram(video_path_or_url: str, caption: str, bot_token: str, chat_id: str, session_id: Optional[str] = None) -> bool:
    """Send video to a Telegram chat using curl to bypass Python SSL issues on HF."""
    import subprocess
    import json as json_module

    prefix = f"[{session_id}] " if session_id else ""
    print(f"{prefix}[Telegram] Sending video to chat_id: {chat_id} (using curl)...")
    caption = _truncate_utf16(caption or "", TELEGRAM_CAPTION_LIMIT)
    
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    
    cmd = ["curl", "-sS", "-X", "POST", "--max-time", "300"]
    
    proxy_url = os.environ.get("PROXY_WORKER_URL") or os.environ.get("INSTAGRAM_API_BASE_URL")
    if proxy_url:
        proxy_url = proxy_url.strip().rstrip("/")
        url = f"{proxy_url}/bot{bot_token}/sendVideo"
        cmd += ["-H", "x-target-domain: api.telegram.org"]
        print(f"{prefix}[Telegram] Routing via proxy: {proxy_url}")
        
    cmd += ["-F", f"chat_id={chat_id}"]
    cmd += ["-F", f"caption={caption}"]
    
    try:
        if video_path_or_url.startswith("http"):
            cmd += ["-F", f"video={video_path_or_url}"]
        else:
            if not os.path.exists(video_path_or_url):
                raise Exception(f"Local video file not found: {video_path_or_url}")
                
            filename = "video.mp4"
            if caption:
                safe_name = "".join(c for c in caption if c.isalnum() or c in " #_").strip()
                safe_name = safe_name.replace(" ", "_")[:100]
                if safe_name:
                    filename = f"{safe_name}.mp4"
            
            # Use curl syntax to attach file with a specific filename
            cmd += ["-F", f"video=@{video_path_or_url};filename={filename};type=video/mp4"]
            
        cmd.append(url)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=330)
        
        if result.returncode != 0:
            if result.returncode == 35:
                print(f"{prefix}[Telegram] TLS handshake failed (exit 35). Retrying with --insecure...")
                cmd.insert(-1, "--insecure")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=330)
            
            if result.returncode != 0:
                print(f"{prefix}[Telegram] curl failed (exit {result.returncode}): {result.stderr.strip()}")
                return False
                
        # Parse response
        try:
            data = json_module.loads(result.stdout)
            if data.get("ok"):
                print(f"{prefix}[Telegram] Successfully sent video to Telegram.")
                return True
            else:
                print(f"{prefix}[Telegram] API error: {data}")
                return False
        except Exception as json_err:
            print(f"{prefix}[Telegram] Failed to parse curl response: {result.stdout[:200]}... Error: {json_err}")
            return False
            
    except Exception as e:
        print(f"{prefix}[Telegram] Exception during send: {e}")
        return False

def dispatch_telegram_post(
    video_url_or_path: str,
    config: TelegramConfig,
    script_data: Optional[dict] = None,
    text_gen_key: Optional[str] = None,
    session_id: Optional[str] = None,
    status_dict_ref: Optional[dict] = None
):
    """Orchestrator to generate caption (if needed) and send via Telegram."""
    prefix = f"[{session_id}] " if session_id else ""
    
    if status_dict_ref is not None:
        status_dict_ref["telegram_status"] = "posting_telegram"
        
    try:
        caption = ""
        if config.auto_generate_caption:
            if script_data and text_gen_key:
                try:
                    caption = generate_instagram_caption(
                        script_data=script_data,
                        text_gen_key=text_gen_key,
                        session_id=session_id
                    )
                except Exception as ex:
                    print(f"{prefix}Failed to auto-generate caption for Telegram: {ex}")
            
        if not caption:
            caption = "Check out this automatically generated video! 🚀\n\n#remotion #ai #automation"

        # Build Deployment Status Confirmation section
        deployment_summary = []
        if status_dict_ref:
            ig_status = status_dict_ref.get("instagram_status")
            ig_id = status_dict_ref.get("instagram_post_id")
            fb_status = status_dict_ref.get("facebook_status")
            yt_status = status_dict_ref.get("youtube_status")

            if ig_status == "posted":
                deployment_summary.append(f"• Instagram Reel (Meta Graph API): ✅ Published (Media ID: {ig_id})")
            elif ig_status in ("posting_instagram", "queued_for_post"):
                deployment_summary.append(f"• Instagram Reel (Meta Graph API): ⏳ In Progress")
            elif ig_status == "failed":
                err = status_dict_ref.get("instagram_error", "Failed")
                deployment_summary.append(f"• Instagram Reel (Meta Graph API): ❌ {err}")

            if fb_status in ("posted", "facebook_posted"):
                deployment_summary.append(f"• Facebook Reel (Meta Graph API): ✅ Published")
            elif fb_status == "posting_facebook":
                deployment_summary.append(f"• Facebook Reel (Meta Graph API): ⏳ In Progress")
            elif fb_status == "failed":
                deployment_summary.append(f"• Facebook Reel (Meta Graph API): ❌ Failed")

            if yt_status == "posted":
                deployment_summary.append(f"• YouTube Shorts: ✅ Published")
            elif yt_status == "failed":
                deployment_summary.append(f"• YouTube Shorts: ❌ Failed")

        header_str = "🎬 AI Video Generation Complete!\n\n🚀 Meta Graph API & Deployment Confirmation:\n"
        if deployment_summary:
            header_str += "\n".join(deployment_summary) + "\n\n"
        else:
            header_str += "• Meta Graph API Deployment: ✅ Verified & Published\n\n"

        full_caption = f"{header_str}📝 Caption:\n{caption}"

        bot_token = config.bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = config.chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            raise Exception("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.")
            
        success = post_to_telegram(
            video_path_or_url=video_url_or_path,
            caption=full_caption,
            bot_token=bot_token,
            chat_id=chat_id,
            session_id=session_id
        )

        
        if status_dict_ref is not None:
            status_dict_ref["telegram_status"] = "posted" if success else "failed"
            
    except Exception as e:
        print(f"{prefix}Fatal error in background Telegram post: {e}")
        if status_dict_ref is not None:
            status_dict_ref["telegram_status"] = "failed"
            status_dict_ref["telegram_error"] = str(e)


def dispatch_instagram_post(
    video_url_or_path: str,
    config: InstagramConfig,
    script_data: Optional[dict] = None,
    text_gen_key: Optional[str] = None,
    session_id: Optional[str] = None,
    status_dict_ref: Optional[dict] = None
):
    """Orchestrator to generate caption (if needed) and upload to Instagram."""
    prefix = f"[{session_id}] " if session_id else ""
    
    if status_dict_ref is not None:
        status_dict_ref["instagram_status"] = "posting_instagram"
        
    try:
        caption = config.caption or ""
        if not caption and config.auto_generate_caption:
            if script_data and text_gen_key:
                try:
                    caption = generate_instagram_caption(
                        script_data=script_data,
                        text_gen_key=text_gen_key,
                        session_id=session_id
                    )
                except Exception as ex:
                    print(f"{prefix}Failed to auto-generate caption: {ex}")
            
            if not caption:
                caption = "Check out this automatically generated video! 🚀\n\n#remotion #ai #automation"

        method = (config.method or "official").lower()
        if method == "official":
            biz_id = config.instagram_business_account_id or os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
            token = config.fb_access_token or os.environ.get("FB_ACCESS_TOKEN")
            
            if not biz_id or not token:
                raise Exception("Missing official Instagram Graph API credentials (business ID or access token).")
                
            media_id = post_to_instagram_official(
                video_url=video_url_or_path,
                caption=caption,
                business_account_id=biz_id,
                access_token=token,
                session_id=session_id
            )
        elif method == "unofficial":
            user = config.username or os.environ.get("INSTAGRAM_USERNAME")
            pwd = config.password or os.environ.get("INSTAGRAM_PASSWORD")
            
            if not user or not pwd:
                raise Exception("Missing unofficial Instagram credentials (username or password).")
                
            media_id = post_to_instagram_unofficial(
                video_path_or_url=video_url_or_path,
                caption=caption,
                username=user,
                password=pwd,
                session_id=session_id
            )
        elif method == "email":
            sender = os.environ.get("EMAIL_SENDER")
            password = os.environ.get("EMAIL_PASSWORD")
            recipient = os.environ.get("EMAIL_RECIPIENT", "")

            if not sender or not password or not recipient:
                print(f"{prefix}[Email] Missing EMAIL_SENDER, EMAIL_PASSWORD or EMAIL_RECIPIENT. Skipping email delivery.")
                media_id = "skipped_no_email_creds"
            else:
                import smtplib
                from email.message import EmailMessage
                import mimetypes

                msg = EmailMessage()
                msg['Subject'] = 'Your AI Generated Tech Video 🚀'
                msg['From'] = sender
                msg['To'] = recipient
                msg.set_content(f"Here is your generated video and caption:\n\n{caption}")

                if os.path.exists(video_url_or_path):
                    ctype, encoding = mimetypes.guess_type(video_url_or_path)
                    if ctype is None or encoding is not None:
                        ctype = 'application/octet-stream'
                    maintype, subtype = ctype.split('/', 1)
                    with open(video_url_or_path, 'rb') as f:
                        msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(video_url_or_path))

                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                    smtp.login(sender, password)
                    smtp.send_message(msg)
                    
                print(f"{prefix}[Email] Successfully sent video to {recipient}")
                media_id = "email_sent"
                
            # AUTO-DELETE functionality for email mode to save server disk space
            if os.path.exists(video_url_or_path):
                try:
                    os.remove(video_url_or_path)
                    print(f"{prefix}[Auto-Delete] Safely deleted {video_url_or_path} from server to free up space.")
                except Exception as e:
                    print(f"{prefix}[Auto-Delete] Failed to delete {video_url_or_path}: {e}")
        elif method == "discord":
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
            if not webhook_url:
                print(f"{prefix}[Discord] Missing DISCORD_WEBHOOK_URL. Skipping Discord delivery.")
                media_id = "skipped_no_discord_url"
            else:
                import requests
                
                # Sneak past Discord anti-bot firewall with a real browser User-Agent
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                # Send caption first
                payload = {"content": f"**Your AI Generated Tech Video is Ready! 🚀**\n\n{caption}"}
                requests.post(webhook_url, json=payload, headers=headers)
                
                # Send video file
                if os.path.exists(video_url_or_path):
                    try:
                        with open(video_url_or_path, 'rb') as f:
                            res = requests.post(webhook_url, files={"file": (os.path.basename(video_url_or_path), f, "video/mp4")}, headers=headers)
                            if not res.ok:
                                print(f"{prefix}[Discord] Error uploading file: {res.text}")
                    except Exception as e:
                        print(f"{prefix}[Discord] Failed to upload video: {e}")
                    
                print(f"{prefix}[Discord] Successfully sent video to Discord.")
                media_id = "discord_sent"
                
            # AUTO-DELETE functionality for discord mode to save server disk space
            if os.path.exists(video_url_or_path):
                try:
                    os.remove(video_url_or_path)
                    print(f"{prefix}[Auto-Delete] Safely deleted {video_url_or_path} from server to free up space.")
                except Exception as e:
                    print(f"{prefix}[Auto-Delete] Failed to delete {video_url_or_path}: {e}")
        elif method == "local_only":
            print("\n========================================================")
            print("🎥 VIDEO GENERATED SUCCESSFULLY (LOCAL ONLY) 🎥")
            
            final_path = os.path.abspath(video_url_or_path)
            target_dir = os.environ.get("LOCAL_ONLY_TARGET_DIR", "").strip()
            if target_dir and os.path.exists(target_dir):
                import shutil
                try:
                    new_path = os.path.join(target_dir, os.path.basename(video_url_or_path))
                    shutil.copy2(final_path, new_path)
                    final_path = new_path
                    
                    # Save caption to file
                    base_name = os.path.splitext(os.path.basename(video_url_or_path))[0]
                    caption_path = os.path.join(target_dir, f"{base_name}_caption.txt")
                    with open(caption_path, "w") as cf:
                        cf.write(caption)
                    print(f"📝 Caption saved at: {caption_path}")
                except Exception as e:
                    print(f"Failed to copy to {target_dir}: {e}")
                    
            print(f"📁 Video saved at: {final_path}")
            print("📝 CAPTION:")
            print("--------------------------------------------------------")
            print(caption)
            print("========================================================\n")
            media_id = "local_only"
        else:
            raise Exception(f"Unsupported Instagram method: {method}")
            
        if status_dict_ref is not None:
            status_dict_ref["instagram_post_id"] = media_id
            status_dict_ref["instagram_status"] = "posted"

        # Feedback-loop ledger: only real Graph API posts (numeric media ids —
        # never the email_sent/discord_sent/local_only/skipped_* sentinels).
        if method == "official" and str(media_id).isdigit():
            try:
                record_post_to_ledger(session_id or "", "instagram", media_id,
                                      meta=(status_dict_ref or {}).get("ledger_meta"))
            except Exception as ledger_err:
                # The post already succeeded — a ledger failure must alert,
                # never unwind the posting path.
                msg = f"⚠️ IG posted OK but post-ledger record failed: {ledger_err}"
                print(f"{prefix}{msg}")
                try:
                    bot = os.environ.get("TELEGRAM_BOT_TOKEN")
                    chat = os.environ.get("TELEGRAM_CHAT_ID")
                    if bot and chat:
                        send_telegram_message(msg, bot, chat, session_id)
                except Exception:
                    pass

        print(f"{prefix}Instagram post succeeded! Media ID: {media_id}")
        return media_id
        
    except Exception as e:
        err_msg = f"Instagram automation failed: {e}"
        print(f"{prefix}{err_msg}")
        if status_dict_ref is not None:
            status_dict_ref["instagram_status"] = "failed"
            status_dict_ref["instagram_error"] = err_msg
        raise e


# =============================================================================
# FACEBOOK PAGE REELS PUBLISHING (official Reels Publishing API)
# =============================================================================

FB_GRAPH_VERSION = "v25.0"


def _resolve_fb_page_token(page_id: str, access_token: str,
                           session_id: Optional[str] = None) -> str:
    """Return a PAGE access token for Reels publishing.

    Reels publishing needs a Page token, but the configured token is often the
    long-lived USER token already used for IG. `GET /{page_id}?fields=
    access_token` with a user token returns the page's token; when the field
    is absent (or the call fails), the input is assumed to already BE a Page
    token and passed through unchanged.
    """
    prefix = f"[{session_id}] " if session_id else ""
    try:
        data = _meta_graph_get(
            f"{page_id}?fields=access_token&access_token={access_token}",
            session_id=session_id or "Facebook",
        )
        page_token = data.get("access_token")
        if page_token:
            print(f"{prefix}[Facebook-Reels] Derived Page access token from user token.")
            return page_token
    except Exception as e:
        print(f"{prefix}[Facebook-Reels] Page-token derivation skipped ({e}); "
              f"assuming the configured token is already a Page token.")
    return access_token


def post_to_facebook_reel(
    video_path_or_url: str,
    description: str,
    page_id: str,
    access_token: str,
    session_id: Optional[str] = None,
    hosted_fallback_url: Optional[str] = None,
    video_state: str = "PUBLISHED",
) -> str:
    """Publish a rendered mp4 to a Facebook Page as a Reel.

    Official Reels Publishing flow (Graph v25.0):
      1. POST /{page_id}/video_reels (upload_phase=start) → video_id
      2. Upload the binary to rupload.facebook.com/video-upload/{ver}/{id}
         (hosted `file_url` variant as fallback — the tmpfiles URL the
         pipeline already produced for IG)
      3. POST /{page_id}/video_reels (upload_phase=finish, video_state=…)
      4. Poll GET /{video_id}?fields=status — the poll is the REAL publish
         confirmation; a successful finish alone does not guarantee the Reel
         went live. Never retry the whole flow after a successful finish
         (duplicate-post risk); retries only cover start/upload.

    Same curl-subprocess pattern as post_to_instagram_official (Python 3.9
    OpenSSL vs Meta TLS; INSTAGRAM_API_BASE_URL proxy base override — the
    Cloudflare worker routes rupload via its x-target-domain header). Specs:
    9:16, ≥540x960, 3–90s — the pipeline's ~40-75s renders fit. `video_state=
    "DRAFT"` makes test posts cheap. Returns the FB video id.
    """
    import subprocess
    import json as json_module

    prefix = f"[{session_id}] " if session_id else ""
    print(f"{prefix}[Facebook-Reels] Starting Reels publish (curl mode, state={video_state})...")

    page_id = str(page_id).strip()
    access_token = str(access_token).strip()
    api_base = os.environ.get("INSTAGRAM_API_BASE_URL", "https://graph.facebook.com").strip().rstrip("/")
    proxied = "graph.facebook.com" not in api_base

    def _tls_flags(insecure: bool = False) -> list:
        flags = ["--tlsv1.2", "--retry", "2", "--retry-delay", "5", "--retry-connrefused"]
        if insecure:
            flags.append("--insecure")
        return flags

    def curl_json(args: list, timeout: int, insecure: bool = False, what: str = "") -> dict:
        cmd = ["curl", "-sS", "--max-time", str(timeout)] + _tls_flags(insecure) + args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        if result.returncode != 0:
            if result.returncode == 35 and not insecure:
                print(f"{prefix}[Facebook-Reels] TLS handshake failed (exit 35) on {what}; "
                      f"retrying with --insecure...")
                return curl_json(args, timeout, insecure=True, what=what)
            raise Exception(f"curl {what} failed (exit {result.returncode}): {result.stderr.strip()}")
        return json_module.loads(result.stdout)

    # Step 1: initialize the upload session (3 attempts)
    start_url = f"{api_base}/{FB_GRAPH_VERSION}/{page_id}/video_reels"
    video_id = None
    for attempt in range(1, 4):
        try:
            data = curl_json(["-X", "POST",
                              "--form-string", "upload_phase=start",
                              "--form-string", f"access_token={access_token}",
                              start_url], timeout=60, what="start")
            if "error" in data:
                print(f"{prefix}[Facebook-Reels] Start attempt {attempt}/3 API error: "
                      f"{data['error'].get('message', str(data))}")
            else:
                video_id = data.get("video_id")
                if video_id:
                    break
                print(f"{prefix}[Facebook-Reels] Start attempt {attempt}/3: no video_id in {data}")
        except Exception as ex:
            print(f"{prefix}[Facebook-Reels] Start attempt {attempt}/3 error: {ex}")
        if attempt < 3:
            time.sleep(15)
    if not video_id:
        raise Exception("Failed to initialize Reels upload session after 3 attempts.")
    print(f"{prefix}[Facebook-Reels] Upload session created: {video_id}")

    # Step 2: upload — local binary first, hosted file_url as fallback
    upload_url = (f"{api_base}/video-upload/{FB_GRAPH_VERSION}/{video_id}" if proxied
                  else f"https://rupload.facebook.com/video-upload/{FB_GRAPH_VERSION}/{video_id}")
    proxy_headers = ["-H", "x-target-domain: rupload.facebook.com"] if proxied else []
    is_url_input = video_path_or_url.startswith(("http://", "https://"))
    uploaded = False
    if not is_url_input and os.path.exists(video_path_or_url):
        file_size = os.path.getsize(video_path_or_url)
        print(f"{prefix}[Facebook-Reels] Step 2: uploading binary ({file_size} bytes)...")
        try:
            data = curl_json(["-X", "POST",
                              "-H", f"Authorization: OAuth {access_token}",
                              "-H", "offset: 0",
                              "-H", f"file_size: {file_size}",
                              "--data-binary", f"@{video_path_or_url}",
                              *proxy_headers, upload_url],
                             timeout=300, what="upload")
            uploaded = bool(data.get("success"))
            if not uploaded:
                print(f"{prefix}[Facebook-Reels] Binary upload not accepted: {data}")
        except Exception as ex:
            print(f"{prefix}[Facebook-Reels] Binary upload error: {ex}")
    if not uploaded:
        file_url = video_path_or_url if is_url_input else hosted_fallback_url
        if not file_url:
            raise Exception("Reels binary upload failed and no hosted fallback URL is available.")
        print(f"{prefix}[Facebook-Reels] Step 2b: hosted-file upload ({file_url[:80]}...)...")
        data = curl_json(["-X", "POST",
                          "-H", f"Authorization: OAuth {access_token}",
                          "-H", f"file_url: {file_url}",
                          *proxy_headers, upload_url],
                         timeout=120, what="upload(file_url)")
        if not data.get("success"):
            raise Exception(f"Reels hosted-file upload failed: {data}")

    # Step 3: finish + set state (no retries past this point — see docstring)
    desc = (description or "").strip()[:1900]
    print(f"{prefix}[Facebook-Reels] Step 3: finishing (video_state={video_state})...")
    finish_data = curl_json(["-X", "POST",
                             "--form-string", "upload_phase=finish",
                             "--form-string", f"video_id={video_id}",
                             "--form-string", f"video_state={video_state}",
                             "--form-string", f"description={desc}",
                             "--form-string", f"access_token={access_token}",
                             start_url], timeout=120, what="finish")
    if "error" in finish_data:
        raise Exception(f"Reels finish failed: {finish_data['error'].get('message', str(finish_data))}")

    # Step 4: poll until processed/published (up to 12 min, like the IG poll)
    print(f"{prefix}[Facebook-Reels] Step 4: polling processing status (up to 12 min)...")
    for attempt in range(48):
        time.sleep(15)
        try:
            data = curl_json([f"{api_base}/{FB_GRAPH_VERSION}/{video_id}"
                              f"?fields=status&access_token={access_token}"],
                             timeout=30, what="status")
            status = data.get("status") or {}
            video_status = status.get("video_status")
            processing = (status.get("processing_phase") or {}).get("status")
            publishing = (status.get("publishing_phase") or {}).get("status")
            print(f"{prefix}[Facebook-Reels] Poll {attempt + 1}/48: video_status={video_status} "
                  f"processing={processing} publishing={publishing}")
            if video_status == "error":
                raise Exception(f"Reel processing failed: {data}")
            if video_status in ("ready", "published") or publishing == "complete":
                print(f"{prefix}[Facebook-Reels] ✓ Reel live on page {page_id}: {video_id}")
                return str(video_id)
            if video_state == "DRAFT" and processing == "complete":
                print(f"{prefix}[Facebook-Reels] ✓ Draft Reel processed: {video_id}")
                return str(video_id)
        except Exception as ex:
            if "Reel processing failed" in str(ex):
                raise
            print(f"{prefix}[Facebook-Reels] Status poll error (poll {attempt + 1}): {ex}")
    raise Exception("Timed out waiting for Reel processing (12 min).")


def dispatch_facebook_reels_post(
    video_url_or_path: str,
    config: "FacebookConfig",
    script_data: Optional[dict] = None,
    text_gen_key: Optional[str] = None,
    session_id: Optional[str] = None,
    status_dict_ref: Optional[dict] = None,
    hosted_fallback_url: Optional[str] = None,
):
    """Orchestrator: caption → page-token resolve → Reels publish → ledger."""
    prefix = f"[{session_id}] " if session_id else ""
    if status_dict_ref is not None:
        status_dict_ref["facebook_status"] = "posting_facebook"
    try:
        caption = config.caption or ""
        if not caption and config.auto_generate_caption:
            if script_data and text_gen_key:
                try:
                    # The IG caption generator's output is platform-neutral
                    # (hook + value + hashtags) — reuse it rather than paying
                    # for a second LLM call.
                    caption = generate_instagram_caption(
                        script_data=script_data,
                        text_gen_key=text_gen_key,
                        session_id=session_id,
                    )
                except Exception as ex:
                    print(f"{prefix}Failed to auto-generate Facebook caption: {ex}")
            if not caption:
                caption = "Daily bite-sized tech. 🚀\n\n#tech #reels"

        page_id = (config.page_id or os.environ.get("FB_PAGE_ID", "")).strip()
        token = (config.access_token
                 or os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
                 or os.environ.get("FB_ACCESS_TOKEN", "").strip())
        if not (page_id and token):
            raise Exception("Missing Facebook Reels credentials (FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN).")
        token = _resolve_fb_page_token(page_id, token, session_id=session_id)

        fb_video_id = post_to_facebook_reel(
            video_path_or_url=video_url_or_path,
            description=caption,
            page_id=page_id,
            access_token=token,
            session_id=session_id,
            hosted_fallback_url=hosted_fallback_url,
        )

        if status_dict_ref is not None:
            status_dict_ref["facebook_status"] = "posted"
            status_dict_ref["facebook_video_id"] = fb_video_id

        if fb_video_id:
            try:
                record_post_to_ledger(session_id or "", "facebook", fb_video_id,
                                      meta=(status_dict_ref or {}).get("ledger_meta"))
            except Exception as ledger_err:
                print(f"{prefix}⚠️ FB posted OK but post-ledger record failed: {ledger_err}")

        print(f"{prefix}Facebook Reel posted! Video ID: {fb_video_id}")
        return fb_video_id
    except Exception as e:
        err_msg = f"Facebook Reels automation failed: {e}"
        print(f"{prefix}{err_msg}")
        if status_dict_ref is not None:
            status_dict_ref["facebook_status"] = "failed"
            status_dict_ref["facebook_error"] = err_msg
        # The delivery-block thread wrapper swallows exceptions, so a failure
        # must alert from here or it dies silently in the status dict.
        try:
            bot = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat = os.environ.get("TELEGRAM_CHAT_ID")
            if bot and chat:
                send_telegram_message(f"❌ {err_msg}", bot, chat, session_id)
        except Exception:
            pass
        raise e


# =============================================================================
# YOUTUBE SHORTS PUBLISHING (official Data API v3 — no shadowban risk)
# =============================================================================

def generate_youtube_metadata(script_data: dict, text_gen_key: str, session_id: Optional[str] = None) -> dict:
    """LLM-generate a YouTube Shorts title/description/tags from the video script.

    Falls back to deriving metadata from the first scene if the LLM fails.
    """
    scenes = script_data.get("scenes", [])
    summary_lines = []
    for i, s in enumerate(scenes):
        label = " / ".join(x for x in (s.get("title", ""), s.get("text", "")) if x)
        vo = (s.get("voiceover") or "").strip()
        summary_lines.append(f"Scene {i+1} ({s.get('type', 'scene')}): {vo or label}")
    scenes_summary = "\n".join(summary_lines)

    topic = _get_caption_topic_context(script_data, session_id)
    topic_block = ""
    if topic.get("title") or topic.get("subject"):
        topic_block = (f"TOPIC: {topic.get('title', '')}\n"
                       f"SUBJECT: {topic.get('subject') or topic.get('title', '')}\n"
                       f"TOPIC KEYWORDS: {', '.join(topic.get('keywords') or []) or 'n/a'}\n\n")

    prompt = f"""Based on this short-form video script, write YouTube Shorts metadata.
Return ONLY a JSON object: {{"title": "...", "description": "...", "tags": ["...", "..."]}}
Rules:
- title: max 80 characters, hook-style, no clickbait-bait words like "MUST SEE", include the core topic. Do NOT use < or > characters.
- description: 2-4 lines with the most concrete specifics from the narration, then a short CTA. End with 3-5 relevant hashtags on the last line, including #Shorts.
- tags: 5-10 short topical keywords (no # symbol).
- Use only facts present in the narration; never invent numbers or people.

{topic_block}VIDEO SCRIPT (scene narration):
{scenes_summary}"""

    try:
        raw = query_llm_with_failover(
            system_prompt="You are a YouTube growth copywriter. Reply with strict JSON only.",
            user_prompt=prompt,
            max_tokens=500,
            json_format=True,
            session_id=session_id or "YouTube"
        )
        meta = _coerce_llm_json(raw, session_id or "YouTube", quiet=True) if isinstance(raw, str) else raw
        if not isinstance(meta, dict):
            meta = {}
        source_prompt = script_data.get("_sourcePrompt", "")
        title = str(meta.get("title", "")).replace("<", "").replace(">", "").strip()[:100]
        title = _scrub_fabricated_people(title, source_prompt, session_id or "YouTube", "yt_title")
        description = str(meta.get("description", "")).strip()[:4800]
        description = _scrub_fabricated_people(description, source_prompt, session_id or "YouTube", "yt_description")
        tags = [str(t).strip().lstrip("#") for t in (meta.get("tags") or []) if str(t).strip()][:12]
        tags = _backfill_youtube_tags(tags, script_data, session_id or "YouTube")
        if title:
            if "#shorts" not in description.lower():
                description = (description + "\n\n#Shorts").strip()
            # YT surfaces the first 3 hashtags and invalidates all past 60 —
            # 4-6 total is the sweet spot.
            description = _enforce_caption_hashtags(
                description, script_data, session_id or "YouTube", min_tags=4, max_tags=6)
            return {"title": title, "description": description, "tags": tags}
    except Exception as e:
        print(f"[{session_id}] YouTube metadata LLM generation failed: {e}")

    # Fallback: derive from the hook scene
    first = scenes[0] if scenes else {}
    title = (first.get("title") or first.get("text") or "Tech in 30 seconds")[:90]
    description = _enforce_caption_hashtags(
        f"{first.get('voiceover', title)}\n\n#Shorts #tech",
        script_data, session_id or "YouTube", min_tags=4, max_tags=6)
    return {
        "title": title,
        "description": description,
        "tags": _backfill_youtube_tags(["tech", "shorts", "technology"], script_data, session_id or "YouTube"),
    }


def _youtube_refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange a long-lived OAuth refresh token for a fresh access token."""
    res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if res.status_code != 200:
        raise Exception(f"YouTube token refresh failed ({res.status_code}): {res.text[:300]}")
    return res.json()["access_token"]


def post_to_youtube_short(
    video_path_or_url: str,
    title: str,
    description: str,
    tags: List[str],
    privacy_status: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    session_id: Optional[str] = None,
) -> str:
    """Upload a vertical video as a YouTube Short via the official Data API v3.

    Uses the resumable upload protocol (init POST → PUT bytes). A vertical
    video under 3 minutes is automatically classified as a Short; #Shorts in
    the metadata reinforces it. Quota: 1,600 units per upload; the default
    10,000/day project quota therefore caps out at ~6 uploads/day.
    """
    prefix = f"[{session_id}] " if session_id else ""

    # Resolve to a local file (Remotion output is local; URLs get downloaded)
    local_path = video_path_or_url
    temp_download = None
    if video_path_or_url.startswith(("http://", "https://")):
        temp_download = os.path.join(PUBLIC_DIR, f"yt-upload-{session_id or uuid.uuid4().hex[:6]}.mp4")
        print(f"{prefix}[YouTube] Downloading video for upload: {video_path_or_url}")
        with requests.get(video_path_or_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(temp_download, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 512):
                    f.write(chunk)
        local_path = temp_download

    try:
        file_size = os.path.getsize(local_path)
        access_token = _youtube_refresh_access_token(client_id, client_secret, refresh_token)

        metadata = {
            "snippet": {
                "title": title[:100],
                "description": description[:4900],
                "tags": tags[:15],
                "categoryId": "28",  # Science & Technology
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        print(f"{prefix}[YouTube] Initiating resumable upload ({file_size} bytes)...")
        init_res = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(file_size),
            },
            json=metadata,
            timeout=30,
        )
        if init_res.status_code != 200:
            raise Exception(f"YouTube upload init failed ({init_res.status_code}): {init_res.text[:500]}")
        upload_url = init_res.headers.get("Location")
        if not upload_url:
            raise Exception("YouTube upload init returned no Location header")

        with open(local_path, "rb") as f:
            upload_res = requests.put(
                upload_url,
                headers={"Content-Type": "video/mp4", "Content-Length": str(file_size)},
                data=f,
                timeout=600,
            )
        if upload_res.status_code not in (200, 201):
            raise Exception(f"YouTube upload failed ({upload_res.status_code}): {upload_res.text[:500]}")

        video_id = upload_res.json().get("id", "")
        print(f"{prefix}[YouTube] ✓ Uploaded Short: https://youtube.com/shorts/{video_id}")
        return video_id
    finally:
        if temp_download and os.path.exists(temp_download):
            try:
                os.remove(temp_download)
            except Exception:
                pass


def dispatch_youtube_post(
    video_url_or_path: str,
    config: YouTubeConfig,
    script_data: Optional[dict] = None,
    text_gen_key: Optional[str] = None,
    session_id: Optional[str] = None,
    status_dict_ref: Optional[dict] = None,
):
    """Orchestrator: generate metadata (if needed) and upload to YouTube Shorts."""
    prefix = f"[{session_id}] " if session_id else ""
    if status_dict_ref is not None:
        status_dict_ref["youtube_status"] = "posting_youtube"

    try:
        client_id = config.client_id or os.environ.get("YT_CLIENT_ID", "").strip()
        client_secret = config.client_secret or os.environ.get("YT_CLIENT_SECRET", "").strip()
        refresh_token = config.refresh_token or os.environ.get("YT_REFRESH_TOKEN", "").strip()
        if not (client_id and client_secret and refresh_token):
            raise Exception("Missing YouTube OAuth credentials (YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN).")

        title, description, tags = config.title, config.description, config.tags
        if config.auto_generate_metadata and not title and script_data:
            meta = generate_youtube_metadata(script_data, text_gen_key or "", session_id=session_id)
            title = meta["title"]
            description = description or meta["description"]
            tags = tags or meta["tags"]
        if not title:
            title = "Tech explained in 30 seconds #Shorts"
        if not description:
            description = "Daily bite-sized tech.\n\n#Shorts"

        video_id = post_to_youtube_short(
            video_path_or_url=video_url_or_path,
            title=title,
            description=description,
            tags=tags or [],
            privacy_status=config.privacy_status or "public",
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            session_id=session_id,
        )
        if status_dict_ref is not None:
            status_dict_ref["youtube_status"] = "posted"
            status_dict_ref["youtube_video_id"] = video_id

        if video_id:
            try:
                record_post_to_ledger(session_id or "", "youtube", video_id,
                                      meta=(status_dict_ref or {}).get("ledger_meta"))
            except Exception as ledger_err:
                msg = f"⚠️ YT posted OK but post-ledger record failed: {ledger_err}"
                print(f"{prefix}{msg}")
                try:
                    bot = os.environ.get("TELEGRAM_BOT_TOKEN")
                    chat = os.environ.get("TELEGRAM_CHAT_ID")
                    if bot and chat:
                        send_telegram_message(msg, bot, chat, session_id)
                except Exception:
                    pass

        return video_id
    except Exception as e:
        err_msg = f"YouTube automation failed: {e}"
        print(f"{prefix}{err_msg}")
        if status_dict_ref is not None:
            status_dict_ref["youtube_status"] = "failed"
            status_dict_ref["youtube_error"] = err_msg
        raise e


# =============================================================================
# NEURAL VOICEOVER & KARAOKE SUBTITLES PIPELINE
# =============================================================================

WHISPER_MODEL = None

def get_whisper_model():
    """Lazily loads the Whisper model to conserve startup memory."""
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        pass
        # from faster_whisper import WhisperModel
        # model_size = os.environ.get("WHISPER_MODEL_SIZE", "base.en")
        # print(f"[Whisper] Loading Whisper model '{model_size}' on CPU...")
        # # CPU loading with int8 computation is extremely fast and light
        # WHISPER_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")
        # print("[Whisper] Model loaded successfully.")
    return WHISPER_MODEL


def mix_scene_audios(audio_paths: List[str], offsets_sec: List[float], output_path: str):
    """Accurately mixes multiple audio tracks at precise offsets using FFmpeg, forcing 48kHz stereo output."""
    if not audio_paths:
        return
    if len(audio_paths) == 1:
        # Even with one track, we must convert/resample it to 48kHz stereo to prevent Remotion render mute/cutoff issues.
        cmd = [
            "ffmpeg", "-y",
            "-i", audio_paths[0],
            "-ar", "48000",
            "-ac", "2",
            "-c:a", "libmp3lame",
            output_path
        ]
        print(f"[FFmpeg] Resampling single audio track: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"FFmpeg resampling failed: {result.stderr}")
        return

    inputs = []
    filter_nodes = []
    for i, (path, offset) in enumerate(zip(audio_paths, offsets_sec)):
        inputs.extend(["-i", path])
        delay_ms = int(offset * 1000)
        filter_nodes.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

    mix_inputs = "".join(f"[a{i}]" for i in range(len(audio_paths)))
    filter_complex = ";".join(filter_nodes) + f";{mix_inputs}amix=inputs={len(audio_paths)}:duration=longest:dropout_transition=0:normalize=0[out]"

    cmd = [
        "ffmpeg", "-y"
    ] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ar", "48000",
        "-ac", "2",
        "-c:a", "libmp3lame",
        output_path
    ]
    print(f"[FFmpeg] Stitching audio tracks: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg mixing failed: {result.stderr}")


async def generate_voiceover_and_alignment(
    scenes: List[dict],
    session_id: str,
    public_dir: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None
) -> tuple:
    """Generates Edge-TTS speech per scene, transcribes timings using native WordBoundary events, auto-adjusts scene durations, and mixes the final track."""
    print(f"[{session_id}] Starting free neural voiceover and karaoke subtitle alignment...")
    import edge_tts
    
    # Resolve parameters from arguments or environment variables. If no voice
    # is forced, rotate one per video (seeded) from the narrator pool.
    resolved_voice = (voice or os.environ.get("VOICEOVER_VOICE", "")).strip()
    if not resolved_voice:
        resolved_voice = random.Random(_derive_seed(session_id)).choice(VOICE_POOL)
        print(f"[{session_id}] Seeded narrator voice for this video: {resolved_voice}")
    # Recorded so the post ledger can attribute performance to the narrator.
    render_status_store.setdefault(session_id, {})["resolved_voice"] = resolved_voice
    resolved_rate = rate or os.environ.get("VOICEOVER_RATE", "+10%")
    resolved_pitch = pitch or os.environ.get("VOICEOVER_PITCH", "+0Hz")
    
    temp_audio_files = []
    offsets = []
    global_subtitles = []
    current_time_offset = 0.0
    failed_scenes = []  # (idx, error) — any entry means the narration has a hole

    for idx, scene in enumerate(scenes):
        scene_text = scene.get("voiceover", "").strip() or scene.get("text", "").strip()
        if not scene_text:
            duration_sec = scene.get("durationInFrames", 175) / 30.0
            current_time_offset += duration_sec
            continue
        
        scene_text_cleaned = scene_text.replace("|", " ").strip()
        scene_audio_filename = f"temp-{session_id}-scene-{idx}.mp3"
        scene_audio_filepath = os.path.join(public_dir, scene_audio_filename)
        
        try:
            # Voice failover: try the chosen narrator, then up to 2 pool
            # fallbacks. Without this, one flaky Edge-TTS response left a
            # scene silently voiceless (with no subtitles) in the final video.
            voice_candidates = [resolved_voice] + [v for v in VOICE_POOL if v != resolved_voice]
            scene_words = []
            synth_ok = False
            last_tts_err: Optional[Exception] = None
            for cand_voice in voice_candidates[:3]:
                try:
                    print(f"[{session_id}] Edge-TTS scene {idx+1}/{len(scenes)}: Synthesizing with voice='{cand_voice}', rate='{resolved_rate}': '{scene_text_cleaned}'")
                    communicate = edge_tts.Communicate(
                        scene_text_cleaned,
                        cand_voice,
                        rate=resolved_rate,
                        pitch=resolved_pitch,
                        boundary="WordBoundary"
                    )

                    scene_words = []
                    with open(scene_audio_filepath, "wb") as f:
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                f.write(chunk["data"])
                            elif chunk["type"] == "WordBoundary":
                                # Convert 100ns ticks to seconds
                                start_sec = chunk["offset"] / 10000000.0
                                dur_sec = chunk["duration"] / 10000000.0
                                scene_words.append({
                                    "text": chunk["text"].strip(),
                                    "start": start_sec,
                                    "end": start_sec + dur_sec
                                })
                    if not scene_words or os.path.getsize(scene_audio_filepath) < 1024:
                        raise Exception("TTS returned empty/near-empty audio")
                    if cand_voice != resolved_voice:
                        print(f"[{session_id}] Voice failover: switching narrator to '{cand_voice}' for the rest of the video (consistency).")
                        resolved_voice = cand_voice
                        render_status_store.setdefault(session_id, {})["resolved_voice"] = resolved_voice
                    synth_ok = True
                    break
                except Exception as tts_err:
                    last_tts_err = tts_err
                    print(f"[{session_id}] TTS voice '{cand_voice}' failed on scene {idx+1}: {tts_err}. Trying fallback voice...")
            if not synth_ok:
                raise Exception(f"All TTS voices failed for scene {idx+1}: {last_tts_err}")

            # Auto-adjust scene duration to match speech duration.
            # PACING: only a short tail of silence after the last word before the
            # cut — a long tail leaves every scene lingering on dead air, which is
            # what makes these feel slow/slideshow-y. 0.35s covers the word's
            # decay and gives one beat before the whoosh-cut into the next scene.
            SCENE_TAIL_PAD_SEC = 0.35
            max_word_end = max((w["end"] for w in scene_words), default=0.0)
            if max_word_end > 0.0:
                spoken_sec = max_word_end + SCENE_TAIL_PAD_SEC
                scene["durationInFrames"] = max(int(spoken_sec * 30), 90)
                print(f"[{session_id}] Scene {idx+1} auto-adjusted to {scene['durationInFrames']} frames ({spoken_sec:.2f}s) to match speech.")
            else:
                max_word_end = scene.get("durationInFrames", 175) / 30.0
            
            for w in scene_words:
                global_subtitles.append({
                    "text": w["text"],
                    "start": w["start"] + current_time_offset,
                    "end": w["end"] + current_time_offset
                })
            
            temp_audio_files.append(scene_audio_filepath)
            offsets.append(current_time_offset)
            
            duration_sec = scene["durationInFrames"] / 30.0
            current_time_offset += duration_sec
            
        except Exception as e:
            print(f"[{session_id}] Error processing voiceover for scene {idx}: {e}")
            failed_scenes.append((idx, e))
            duration_sec = scene.get("durationInFrames", 175) / 30.0
            current_time_offset += duration_sec
            if os.path.exists(scene_audio_filepath):
                try:
                    os.remove(scene_audio_filepath)
                except:
                    pass

    def _cleanup_temp_tracks():
        for file_path in temp_audio_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

    # A scene that lost its narration is a hole the viewer hears. Refuse to
    # continue rather than ship a video whose voice drops out mid-way.
    if failed_scenes and REQUIRE_VOICEOVER:
        _cleanup_temp_tracks()
        failed_desc = ", ".join(f"scene {i + 1} ({err})" for i, err in failed_scenes)
        raise Exception(f"Voiceover synthesis failed for {failed_desc} — aborting so no partially-narrated video is posted.")

    final_voiceover_filename = f"voiceover-{session_id}.mp3"
    final_voiceover_path = os.path.join(public_dir, final_voiceover_filename)

    if temp_audio_files:
        try:
            mix_scene_audios(temp_audio_files, offsets, final_voiceover_path)
            print(f"[{session_id}] Mixed voiceover stitched successfully: {final_voiceover_path}")
        except Exception as mix_err:
            # Copying the first track alone is only a valid fallback when it IS
            # the whole narration. With multiple tracks that "fallback" once
            # shipped a video whose voice stopped after scene 1 — never again.
            if len(temp_audio_files) > 1 and REQUIRE_VOICEOVER:
                raise Exception(f"FFmpeg voiceover mixing failed ({mix_err}) — aborting instead of posting partial narration.")
            print(f"[{session_id}] FFmpeg mixing failed: {mix_err}. Attempting fallback copy of first track...")
            shutil.copyfile(temp_audio_files[0], final_voiceover_path)
        finally:
            _cleanup_temp_tracks()
    else:
        final_voiceover_filename = None

    return final_voiceover_filename, global_subtitles


@app.post("/render/preview", dependencies=[Depends(verify_api_key)])
def render_preview(req: RenderRequest):
    """Generate a single-frame preview image (fast validation).
    
    Renders frame 0 of the composition as a JPEG. Useful for
    validating themes, colors, and layout before a full render.
    """
    session_id = str(uuid.uuid4())[:8]
    
    # Clean keys
    t_key = (req.text_gen_key or req.nvidia_nim_key or "").strip().strip("'\"")
    if not t_key:
        raise HTTPException(status_code=400, detail="Text generation API key required.")

    # Clean other parameters
    text_api_base = (req.text_api_base or "").strip().strip("'\"") or os.environ.get("TEXT_GEN_BASE_URL", "").strip() or None
    text_model_name = (req.text_model_name or "").strip().strip("'\"") or os.environ.get("TEXT_MODEL_NAME", "").strip() or None

    print(f"[{session_id}] Generating preview frame...")

    # Per-video variety seed (mirrors the full render pipeline)
    video_seed = _derive_seed(session_id)

    # Generate script (same pipeline as full render)
    user_prompt = build_user_prompt(req.prompt) + build_variety_directive(video_seed, False)
    
    if text_api_base:
        text_url = text_api_base
        if not text_url.startswith("http://") and not text_url.startswith("https://"):
            text_url = "https://" + text_url
        if not text_url.endswith("/chat/completions"):
            text_url = text_url.rstrip("/") + "/chat/completions"
    else:
        text_url = "https://integrate.api.nvidia.com/v1/chat/completions"

    model_name = text_model_name or "meta/llama-3.3-70b-instruct"
    
    try:
        response = requests.post(
            text_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {t_key}"
            },
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 3500,
                "response_format": {"type": "json_object"}
            },
            timeout=120
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"LLM failed: {response.text}")
        
        raw_text = response.json()["choices"][0]["message"]["content"]
        parsed_script = parse_and_validate_script(raw_text, session_id, source_prompt=req.prompt or "")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[{session_id}] Preview script generation failed: {e}")
        parsed_script = _build_fallback_script()

    forced_theme_keys = set()
    if req.theme_overrides:
        for k, v in req.theme_overrides.items():
            if v is not None:
                parsed_script["theme"][k] = v
                forced_theme_keys.add(k)

    apply_style_director(parsed_script["theme"], video_seed, False, forced_theme_keys)

    # For preview, we just return the script without rendering
    # This is much faster and allows UI to show a preview of the generated config
    return {
        "status": "preview_generated",
        "session_id": session_id,
        "script": parsed_script,
        "estimated_duration_seconds": sum(
            s.get("durationInFrames", 175) for s in parsed_script["scenes"]
        ) / 30,
        "estimated_scene_count": len(parsed_script["scenes"]),
    }
@app.get("/videos", dependencies=[Depends(verify_api_key)])
def list_videos():
    """Lists all generated .mp4 videos in the public directory."""
    videos = []
    if os.path.exists(PUBLIC_DIR):
        for f in os.listdir(PUBLIC_DIR):
            if f.endswith(".mp4"):
                path = os.path.join(PUBLIC_DIR, f)
                stat = os.stat(path)
                videos.append({
                    "filename": f,
                    "url": f"/public/{f}",
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": stat.st_mtime
                })
    # Sort by newest first
    videos.sort(key=lambda x: x["created_at"], reverse=True)
    return {"status": "success", "videos": videos}

@app.delete("/videos/{filename}", dependencies=[Depends(verify_api_key)])
def delete_video(filename: str):
    """Deletes a generated .mp4 video from the public directory."""
    if not filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only .mp4 files can be deleted.")
        
    path = os.path.join(PUBLIC_DIR, filename)
    # Basic directory traversal prevention
    if os.path.abspath(path).startswith(os.path.abspath(PUBLIC_DIR)) is False:
        raise HTTPException(status_code=403, detail="Invalid path.")
        
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video not found.")
        
    try:
        os.remove(path)
        return {"status": "success", "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete {filename}: {str(e)}")


@app.get("/", response_class=FileResponse)
def home():
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    return {"message": "Remotion Hugging Face Renderer active. Use POST /render to trigger."}


def get_hacker_news_frontpage(min_score: int = 100, limit: int = 5) -> list:
    """Fetches top stories from HN front page with a score threshold."""
    print("[HN-Scraper] Fetching front page stories...")
    url = "https://hn.algolia.com/api/v1/search?tags=front_page"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"[HN-Scraper] HN API failed: {response.text}")
            return []
        data = response.json()
        stories = []
        for hit in data.get("hits", []):
            # Algolia can return explicit nulls (e.g. "num_comments": null),
            # so `get(key, 0)` still yields None — `or 0` covers both.
            score = hit.get("points") or 0
            story_url = hit.get("url")
            if story_url and score >= min_score:
                stories.append({
                    "id": hit.get("objectID"),
                    "title": hit.get("title"),
                    "url": story_url,
                    "score": score,
                    "author": hit.get("author"),
                    "num_comments": hit.get("num_comments") or 0,
                    "created_at_i": hit.get("created_at_i") or 0,
                })
                if len(stories) >= limit:
                    break
        return stories
    except Exception as e:
        print(f"[HN-Scraper] Error: {e}")
        return []


def get_github_trending_repos(limit: int = 5) -> list:
    """Fetches popular/trending repositories created in the last 30 days from GitHub API."""
    import datetime
    print("[GitHub-Scraper] Fetching trending repositories...")
    thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=created:>{thirty_days_ago}&sort=stars&order=desc&per_page=15"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[GitHub-Scraper] GitHub API failed: {response.text}")
            return []
        data = response.json()
        repos = []
        for item in data.get("items", []):
            desc = item.get("description") or ""
            repos.append({
                "id": str(item.get("id")),
                "name": item.get("name"),
                "owner": item.get("owner", {}).get("login"),
                "description": desc,
                "stars": item.get("stargazers_count"),
                "url": item.get("html_url"),
                "language": item.get("language")
            })
            if len(repos) >= limit:
                break
        return repos
    except Exception as e:
        print(f"[GitHub-Scraper] Error fetching trending repos: {e}")
        return []


def get_show_hn_stories(min_score: int = 50, limit: int = 5) -> list:
    """Fetches show HN (Show Hacker News) posts with a minimum score threshold."""
    print("[HN-Scraper] Fetching Show HN posts...")
    url = f"https://hn.algolia.com/api/v1/search_by_date?tags=show_hn&numericFilters=points>={min_score}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"[HN-Scraper] Show HN API failed: {response.text}")
            return []
        data = response.json()
        stories = []
        for hit in data.get("hits", []):
            score = hit.get("points", 0)
            story_url = hit.get("url")
            # Fallback to Hacker News thread url if no outbound link
            if not story_url:
                story_url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            stories.append({
                "id": hit.get("objectID"),
                "title": hit.get("title"),
                "url": story_url,
                "score": score,
                "author": hit.get("author")
            })
            if len(stories) >= limit:
                break
        return stories
    except Exception as e:
        print(f"[HN-Scraper] Error: {e}")
        return []


def extract_article_body(url: str) -> str:
    """Scrapes a news article URL and extracts the core body text."""
    from bs4 import BeautifulSoup
    print(f"[Article-Scraper] Extracting text from: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, 'html.parser')
        # Remove script, style, nav, header, footer, etc.
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            element.decompose()
        # Extract paragraph texts
        paragraphs = soup.find_all('p')
        body_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
        return body_text[:3500]
    except Exception as e:
        print(f"[Article-Scraper] Error extracting article body: {e}")
        return ""


def build_hn_news_prompt(title: str, body: str, seed: Optional[int] = None, outro_appended: bool = False) -> str:
    """Builds a fast-paced tech-news prompt with a RANDOMIZED scene flow.

    The visual theme is intentionally left to the backend style-director (which
    rotates a cohesive style pack per video), so this prompt focuses on content,
    a rotating opening hook, and a varied narrative structure — guaranteeing no
    two auto-generated tech videos share the same flow.

    `outro_appended` must mirror the AUTO_CHANNEL_PREFIXES gate in the outro
    block: when True the closer must NOT carry a follow ask (the branded outro
    card right after it is the only one); when False (news scheduler,
    /render/hn-news) no outro card exists, so the closer keeps the follow CTA
    itself — otherwise those videos end with no follow ask at all.
    """
    content_snippet = body.strip() if body else "No article content available."
    rnd = random.Random(seed) if seed is not None else random.Random()

    hook, _hook_mode = _feedback_weighted_choice(
        HOOK_PATTERNS, lambda h: h.split(":")[0].strip(), "hooks", rnd, get_feedback_stats())

    # Pool of narrative "beats" for the middle of the video. We pick a seeded,
    # shuffled subset so the story structure changes every time.
    beat_pool = [
        ("split", "Explain the core concept/announcement in plain terms."),
        ("list", "Break down the key technical details, features, or steps."),
        ("metric", "Highlight ONE standout number or statistic from the story."),
        ("comparison", "Contrast the old way vs the new approach (before/after)."),
        ("countdown", "Animate a key figure counting up/down for impact."),
        ("split", "Explain WHY this matters and who it affects in the real world."),
        ("testimonial", "Highlight the boldest fact from the article as a standout quote card. Attribute it ONLY to the source itself (the product, its docs, or the announcement) — NEVER invent a person; only name a person if the article text above explicitly names them."),
    ]
    rnd.shuffle(beat_pool)
    middle_count = rnd.choice([2, 3, 3, 4])
    middle_beats = beat_pool[:middle_count]

    closer_type = rnd.choice(["cta", "hero", "split"])

    outline_lines = [f'- Scene 1 (HOOK): {hook} Type: "hero". Deliver the news headline in a way that is impossible to scroll past.']
    for i, (beat_type, beat_desc) in enumerate(middle_beats, start=2):
        outline_lines.append(f'- Scene {i}: {beat_desc} Type: "{beat_type}".')
    conclusion_idx = len(middle_beats) + 2
    if outro_appended:
        outline_lines.append(f'- Scene {conclusion_idx} (CONCLUSION): Land a strong, satisfying takeaway on why this story matters. Type: "{closer_type}". Do NOT ask viewers to follow/subscribe and do NOT mention the channel name — a branded outro card is appended automatically right after this scene.')
    else:
        outline_lines.append(f'- Scene {conclusion_idx} (CONCLUSION): Land a strong, satisfying takeaway on why this story matters. Type: "{closer_type}". End with a clear "Follow Neon Node for more tech" call-to-action.')

    outline = "\n".join(outline_lines)

    return f"""Create a highly engaging, fast-paced vertical (9:16) tech-news video summarizing this trending Hacker News article.

NEWS SOURCE DETAILS:
- Headline/Title: {title}
- Main Content Text:
{content_snippet}

PLATFORM: Vertical 9:16 Reels/Shorts. Set "aspectRatio":"9:16".
(The visual theme — colors, overlay, font, music — is applied automatically by the renderer, so you may pick any tasteful tech-appropriate values; focus your energy on the writing and structure below.)

SCENE OUTLINE (follow this structure, but write ORIGINAL, specific copy):
- Core Instruction: Tell this as a STORY that escalates — hook, why it matters, the surprising detail, then a satisfying takeaway — not a list of facts.
{outline}
- Give EACH scene a different textAnimation. Keep on-screen "text" to a short label (a keyword or number); put the actual sentence in the "voiceover" — never the same words in both.
- Give EACH scene a "videoQuery": 2-4 keywords for a TECH MOTION b-roll clip that shows this story's real subject in action (a terminal, code on screen, a dashboard, data-center racks, a chip, a robot, network traffic) — topic-relevant motion, never a generic abstract loop. Use a different videoQuery per scene.

NO-REPETITION (this is the #1 thing that makes these videos feel cheap): name the product/company from the headline in the HOOK scene ONLY. After that, refer to it as "it" / "the tool" / "the team" — do NOT restate the headline in later scenes. The subtitles show every spoken word for the whole video, so a repeated line is read and heard 5-6 times. Every scene must add information the earlier scenes did NOT state.

CONCRETENESS CONTRACT: this video is about THIS story only. Pull real specifics (numbers, names, what changed, what it does) from the article text above into the scenes. BANNED: generic filler everyone already knows ('technology is evolving fast', 'this will change everything', 'tools make life easier') — every sentence must carry information specific to this story.
"""


@app.post("/render/hn-news", dependencies=[Depends(verify_api_key)])
def render_hn_news(req: RenderHNRequest):
    """Fetches the top story on Hacker News, scrapes its webpage content, 
    compiles a structured news prompt, and renders the video automatically.
    """
    stories = get_hacker_news_frontpage(min_score=req.min_score, limit=1)
    if not stories:
        raise HTTPException(
            status_code=404, 
            detail=f"No stories found on Hacker News with score >= {req.min_score} containing article links."
        )
    
    target_story = stories[0]
    title = target_story["title"]
    url = target_story["url"]
    
    # Extract webpage content
    body = extract_article_body(url)
    
    # If content extraction fails, fall back to just summarizing the title
    prompt = build_hn_news_prompt(title, body)
    
    # Create request object for _execute_render
    render_req = RenderRequest(
        prompt=prompt,
        text_gen_key=req.text_gen_key,
        image_gen_key=req.image_gen_key,
        nvidia_nim_key=req.nvidia_nim_key,
        theme_overrides=req.theme_overrides,
        text_api_base=req.text_api_base,
        text_model_name=req.text_model_name,
        pexels_api_key=req.pexels_api_key,
        pipeline=req.pipeline
    )
    
    session_id = str(uuid.uuid4())[:8]
    print(f"[{session_id}] Automated HN Render triggered for story: '{title}' ({url})")
    
    result = _execute_render(render_req, session_id)
    return {
        **result,
        "hn_story": target_story
    }


@app.post("/instagram/post", dependencies=[Depends(verify_api_key)])
async def post_to_instagram_direct(req: InstagramDirectPostRequest, background_tasks: BackgroundTasks):
    """Directly uploads an existing video to Instagram Reels.
    
    Returns a post ID immediately, and handles the download and upload
    asynchronously in a background task.
    """
    post_id = str(uuid.uuid4())[:8]
    instagram_status_store[post_id] = {
        "status": "queued",
        "video_url_or_path": req.video_url_or_path,
        "method": req.config.method,
        "queued_at": time.time()
    }
    
    def run_direct_post():
        try:
            instagram_status_store[post_id]["status"] = "posting"
            media_id = dispatch_instagram_post(
                video_url_or_path=req.video_url_or_path,
                config=req.config,
                session_id=post_id,
                status_dict_ref=None
            )
            instagram_status_store[post_id]["status"] = "complete"
            instagram_status_store[post_id]["media_id"] = media_id
            instagram_status_store[post_id]["completed_at"] = time.time()
        except Exception as e:
            instagram_status_store[post_id]["status"] = "error"
            instagram_status_store[post_id]["error"] = str(e)
            
    background_tasks.add_task(run_direct_post)
    
    return {
        "status": "queued",
        "post_id": post_id,
        "status_endpoint": f"/instagram/status/{post_id}"
    }


@app.get("/instagram/status/{post_id}", dependencies=[Depends(verify_api_key)])
async def get_instagram_status(post_id: str):
    """Checks status of a direct Instagram Reels post request."""
    if post_id not in instagram_status_store:
        raise HTTPException(status_code=404, detail=f"Instagram post job {post_id} not found")
    return instagram_status_store[post_id]


# =============================================================================
# AUTOMATED BACKGROUND SCHEDULERS (MULTI-CHANNEL CONTENT)
# =============================================================================

PROCESSED_NEWS_FILE = os.path.join(PUBLIC_DIR, "processed_news_stories.json")
PROCESSED_TECH_FILE = os.path.join(PUBLIC_DIR, "processed_techs.json")

def load_processed_items(filepath: str) -> list:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_processed_items(filepath: str, items: list):
    try:
        with open(filepath, "w") as f:
            json.dump(items, f)
    except Exception as e:
        print(f"[Scheduler] Error saving processed items: {e}")


# ---------------------------------------------------------------------------
# Cross-run topic history (the fix for "same story picked 4 runs in a row").
#
# The GitHub-Actions path (generate_now.py) used to argmax a deterministic
# virality score with no memory: while a big headline sat on the HN front page
# it won every one of the day's crons. These helpers give every selection path
# one shared, persistent history schema. The workflow commits the news history
# file back to the repo so it survives ephemeral CI runners.
# ---------------------------------------------------------------------------

def load_topic_history(filepath: str) -> list:
    """Cross-run history of used topics as a list of dict entries.

    Missing file = first-run bootstrap (info line, empty history). Corrupt
    file = LOUD warning + empty history — silently restarting dedup is the
    exact bug this file exists to prevent, so the two cases must be
    distinguishable in logs. Legacy entries (bare HN-id strings from the old
    news scheduler, bare subject strings from the tech scheduler) are
    migrated in-memory to the dict schema; the file self-heals on next save.
    """
    if not os.path.exists(filepath):
        print(f"[TopicHistory] No history at {filepath} — starting fresh (first run).")
        return []
    try:
        with open(filepath, "r") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            raise ValueError(f"expected a list, got {type(raw).__name__}")
    except Exception as e:
        print(f"[TopicHistory] WARNING: corrupt history file {filepath} ({e}) — "
              f"treating as EMPTY; dedup restarts from scratch this run.")
        return []
    history = []
    for item in raw:
        if isinstance(item, dict):
            history.append(item)
        elif isinstance(item, (int, float)):
            history.append({"id": str(int(item))})
        elif isinstance(item, str):
            if item.isdigit():
                history.append({"id": item})
            else:
                history.append({"title": item, "norm": _normalize_subject(item)})
    return history


def record_topic_use(filepath: str, story_id=None, title: str = "",
                     subject: str = "", session_id: str = "", cap: int = 200) -> None:
    """Append one used-topic entry, trim to the last `cap`, write atomically.

    RAISES on write failure — the caller decides how loudly to surface it
    (a swallowed save error would quietly resurrect the repeat-topic bug).
    """
    history = load_topic_history(filepath)
    history.append({
        "id": str(story_id) if story_id is not None else None,
        "title": title or "",
        "norm": _normalize_subject(title),
        "subject_norm": _normalize_subject(subject) if subject else None,
        "ts": int(time.time()),
        "session": session_id or "",
    })
    history = history[-cap:]
    tmp = filepath + ".tmp"
    with open(tmp, "w") as f:
        json.dump(history, f, indent=1)
    os.replace(tmp, filepath)


def filter_and_pick_story(candidates: list, history: list, rng: random.Random,
                          top_n: int = 5):
    """Dedup candidates against history, then weighted-random pick.

    Returns (chosen_candidate, was_fallback). A candidate is excluded when its
    HN id is in history, its normalized title matches exactly, or its 3-word
    normalized head appears inside a used title (same reword-catching
    heuristic as select_viral_topic). Survivors are scored and the pick is
    weighted-random over the top `top_n` with weight = score**2 — quality
    still dominates, but two same-day runs over a near-identical front page
    diverge instead of both taking the argmax.

    If EVERY candidate is excluded (slow news day), falls back to the
    least-recently-used repeat — the story whose last airing is oldest, since
    the audience-visible harm of a repeat decays with time — and says so
    loudly; callers alert on was_fallback=True. Never returns None.
    """
    if not candidates:
        raise ValueError("filter_and_pick_story: no candidates supplied")

    used_ids = {str(h.get("id")) for h in history if h.get("id")}
    used_norms = {h.get("norm") for h in history if h.get("norm")}
    used_norms |= {h.get("subject_norm") for h in history if h.get("subject_norm")}

    def _is_used(c: dict) -> bool:
        if c.get("_hn_id") is not None and str(c["_hn_id"]) in used_ids:
            return True
        norm = _normalize_subject(c.get("title", ""))
        if norm and norm in used_norms:
            return True
        head = " ".join(norm.split()[:3])
        if head and any(head in n for n in used_norms):
            return True
        return False

    for c in candidates:
        c["_score"] = score_virality(c)

    fresh = [c for c in candidates if not _is_used(c)]
    if fresh:
        fresh.sort(key=lambda c: c["_score"], reverse=True)
        pool = fresh[:top_n]
        weights = [max(c["_score"], 0.1) ** 2 for c in pool]
        chosen = rng.choices(pool, weights=weights, k=1)[0]
        print(f"[TopicHistory] {len(candidates)} candidates, {len(fresh)} unused; "
              f"picked '{chosen.get('title', '')[:70]}' "
              f"(score {chosen['_score']:.2f}) from top {len(pool)}.")
        return chosen, False

    def _last_used_ts(c: dict) -> int:
        norm = _normalize_subject(c.get("title", ""))
        ts_matches = [
            int(h.get("ts") or 0)
            for h in history
            if (c.get("_hn_id") is not None and str(h.get("id")) == str(c["_hn_id"]))
            or (norm and h.get("norm") == norm)
            or (norm and h.get("subject_norm") == norm)
        ]
        return max(ts_matches) if ts_matches else 0

    chosen = min(candidates, key=lambda c: (_last_used_ts(c), -c["_score"]))
    last_ts = _last_used_ts(chosen)
    ago = f" (last aired ~{(time.time() - last_ts) / 86400.0:.1f} days ago)" if last_ts else ""
    print(f"[TopicHistory] WARNING: all {len(candidates)} candidates already used — "
          f"falling back to least-recently-used repeat: "
          f"'{chosen.get('title', '')[:70]}'{ago}")
    return chosen, True


# ============================================================================
# POST LEDGER + PERFORMANCE METRICS (feedback-loop data collection)
# ----------------------------------------------------------------------------
# Every published post is recorded with the creative choices that produced it
# (topic keywords, style pack, hook type, voice, seed) so later runs can fetch
# real engagement numbers and learn which choices perform. Same persistence
# model as the topic history: a bounded JSON file in public/ that the GitHub
# workflow commits back to the repo. Space-side updates persist only on the
# Space's own disk; the canonical committed copy comes from CI runs.
# ============================================================================

POST_LEDGER_FILE = os.path.join(PUBLIC_DIR, "post_ledger.json")
LEDGER_CAP = int(os.environ.get("LEDGER_CAP", "200"))
ENABLE_POST_LEDGER = os.environ.get("ENABLE_POST_LEDGER", "true").strip().lower() == "true"
# Insights/read calls pin their own Graph version so a Meta version retirement
# shows up here, not spread across call sites. (The posting path keeps its own
# inline version — never touch working posting code for a read-side change.)
GRAPH_API_VERSION = "v21.0"

METRICS_MIN_AGE_HOURS = float(os.environ.get("METRICS_MIN_AGE_HOURS", "24"))
METRICS_REFRESH_HOURS = float(os.environ.get("METRICS_REFRESH_HOURS", "24"))
METRICS_MAX_AGE_DAYS = float(os.environ.get("METRICS_MAX_AGE_DAYS", "30"))
METRICS_IG_PER_RUN = int(os.environ.get("METRICS_IG_PER_RUN", "15"))
METRICS_POLL_HOURS = float(os.environ.get("METRICS_POLL_HOURS", "6"))

_LEDGER_LOCK = threading.Lock()


class MetricsAuthError(Exception):
    """Metrics fetch failed on auth (expired token / missing permission) —
    callers stop that platform for the run and alert ONCE instead of spamming
    a failure per entry."""


def load_post_ledger() -> dict:
    """Cross-run ledger of published posts and their performance metrics.

    Missing file = first-run bootstrap (info line). Corrupt file = LOUD
    warning + empty ledger — mirroring load_topic_history, a silent reset
    must be distinguishable from a fresh start. A legacy bare list is wrapped
    into the versioned schema and self-heals on the next save.
    """
    empty = {"version": 1, "entries": []}
    if not os.path.exists(POST_LEDGER_FILE):
        print(f"[PostLedger] No ledger at {POST_LEDGER_FILE} — starting fresh (first run).")
        return empty
    try:
        with open(POST_LEDGER_FILE, "r") as f:
            raw = json.load(f)
    except Exception as e:
        print(f"[PostLedger] WARNING: corrupt ledger file {POST_LEDGER_FILE} ({e}) — "
              f"treating as EMPTY; performance history restarts this run.")
        return empty
    if isinstance(raw, list):
        return {"version": 1, "entries": [e for e in raw if isinstance(e, dict)]}
    if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
        print(f"[PostLedger] WARNING: unexpected ledger schema in {POST_LEDGER_FILE} — "
              f"treating as EMPTY.")
        return empty
    raw.setdefault("version", 1)
    raw["entries"] = [e for e in raw["entries"] if isinstance(e, dict)]
    return raw


def save_post_ledger(ledger: dict) -> None:
    """Trim to the last LEDGER_CAP entries and write atomically.

    RAISES on failure — the caller decides how loudly to surface it. Posting
    paths must alert-and-continue (never unwind a post that already
    succeeded); collection sweeps may propagate.
    """
    ledger["entries"] = ledger["entries"][-LEDGER_CAP:]
    tmp = POST_LEDGER_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(ledger, f, indent=1)
    os.replace(tmp, POST_LEDGER_FILE)


def _extract_topic_keywords(title: str) -> list:
    """VIRAL_KEYWORDS keys matching a title (same substring rule as
    score_virality). Storing the matched keys — not raw title words — makes
    attribution map 1:1 onto the knob the feedback loop later re-weights."""
    low = (title or "").lower()
    return [w for w in VIRAL_KEYWORDS if w in low]


def record_post_to_ledger(session_id: str, platform: str, post_id,
                          meta: Optional[dict] = None) -> None:
    """Upsert one published post (called from dispatchers at success points).

    The first platform to land creates the entry from `meta` (the render's
    ledger_meta); later platforms attach their post id to the same entry.
    No meta and no existing entry = manual/API render → not tracked.
    RAISES on write failure; callers catch + alert without re-raising into
    the posting path.
    """
    if not ENABLE_POST_LEDGER:
        return
    now = int(time.time())
    with _LEDGER_LOCK:
        ledger = load_post_ledger()
        entry = next((e for e in ledger["entries"] if e.get("session") == session_id), None)
        if entry is None:
            if not meta:
                print(f"[PostLedger] No ledger_meta for session {session_id} "
                      f"(manual render?) — not tracking this {platform} post.")
                return
            entry = dict(meta)
            entry["session"] = session_id
            entry.setdefault("ts", now)
            ledger["entries"].append(entry)
        entry.setdefault("platforms", {})
        entry.setdefault("metrics", {})
        entry["platforms"][platform] = {"id": str(post_id), "posted_at": now}
        entry["metrics"].setdefault(platform, {
            "latest": None, "snap72": None, "deleted": False, "fetch_errors": 0,
        })
        save_post_ledger(ledger)
    print(f"[PostLedger] Recorded {platform} post {post_id} for session {session_id}.")


def _meta_graph_get(path_and_query: str, session_id: str = "Metrics",
                    timeout: int = 30, insecure: bool = False) -> dict:
    """GET against the Meta Graph API via curl subprocess.

    Module-level clone of the closure in post_to_instagram_official — same
    Python 3.9 OpenSSL workaround, exit-35 → --insecure retry, and
    INSTAGRAM_API_BASE_URL proxy override. The working posting closure stays
    untouched on purpose.
    """
    import subprocess
    api_base = os.environ.get("INSTAGRAM_API_BASE_URL", "https://graph.facebook.com").strip().rstrip("/")
    url = f"{api_base}/{GRAPH_API_VERSION}/{path_and_query.lstrip('/')}"
    cmd = ["curl", "-sS", "--max-time", str(timeout),
           "--tlsv1.2", "--retry", "2", "--retry-delay", "5", "--retry-connrefused"]
    if insecure:
        cmd.append("--insecure")
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
    if result.returncode != 0:
        if result.returncode == 35 and not insecure:
            print(f"[{session_id}] [Metrics] TLS handshake failed (exit 35); retrying with --insecure...")
            return _meta_graph_get(path_and_query, session_id, timeout=timeout, insecure=True)
        raise Exception(f"curl GET failed (exit {result.returncode}): {result.stderr.strip()}")
    return json.loads(result.stdout)


# Meta renames Reels insight metrics between Graph versions ('plays' became
# 'views'), so an invalid-metric error walks this reduced ladder instead of
# failing the whole run — with a single drift warning so the set gets fixed.
_IG_INSIGHT_METRIC_SETS = [
    "views,reach,likes,comments,shares,saved,total_interactions",
    "views,reach,likes,comments",
    "reach,likes,comments",
]


def fetch_instagram_media_metrics(media_id: str, access_token: str,
                                  session_id: str = "Metrics") -> dict:
    """Insights for one IG Reel. Raises MetricsAuthError on token problems
    (code 190 = expired — long-lived tokens die at ~60 days; 10/200 = missing
    instagram_manage_insights); returns {"deleted": True} for vanished posts.
    Adds "_metric_drift": True when a reduced metric set was needed."""
    drift = False
    for metric_set in _IG_INSIGHT_METRIC_SETS:
        data = _meta_graph_get(
            f"{media_id}/insights?metric={metric_set}&access_token={access_token}",
            session_id=session_id,
        )
        err = data.get("error")
        if err:
            code = err.get("code")
            msg = str(err.get("message", ""))
            low = msg.lower()
            if code == 190:
                raise MetricsAuthError(f"Instagram token invalid/expired: {msg}")
            if code in (10, 200):
                raise MetricsAuthError(f"Instagram token lacks insights permission: {msg}")
            if code == 100 and "metric" in low:
                drift = True
                continue
            if code == 100 or "does not exist" in low or "unsupported get request" in low:
                return {"deleted": True}
            raise Exception(f"IG insights error for {media_id}: {msg}")
        out = {}
        for item in data.get("data", []):
            name = item.get("name")
            values = item.get("values") or []
            if name and values:
                try:
                    out[name] = int(values[0].get("value") or 0)
                except (TypeError, ValueError):
                    pass
        out["_metric_drift"] = drift
        return out
    raise Exception(f"IG insights: every metric set rejected for {media_id} (Graph version drift?)")


def fetch_youtube_video_metrics(video_ids: list, session_id: str = "Metrics") -> dict:
    """Batched public statistics for up to 50 YouTube video ids (1 quota unit).

    Prefers YT_API_KEY (plain Data API key — videos.list on public videos
    needs no OAuth). Falls back to the upload OAuth token, but NOTE: the
    refresh token minted by get_youtube_token.py carries the upload-only
    scope and may 403 on reads — the raised MetricsAuthError names the fix
    (set YT_API_KEY; same Cloud project, no re-auth, no new scopes).
    Ids missing from the response = deleted/private → {"deleted": True}.
    """
    ids = [str(v) for v in video_ids if v][:50]
    if not ids:
        return {}
    api_key = os.environ.get("YT_API_KEY", "").strip()
    url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={','.join(ids)}"
    headers = {}
    if api_key:
        url += f"&key={api_key}"
    else:
        client_id = os.environ.get("YT_CLIENT_ID", "").strip()
        client_secret = os.environ.get("YT_CLIENT_SECRET", "").strip()
        refresh_token = os.environ.get("YT_REFRESH_TOKEN", "").strip()
        if not (client_id and client_secret and refresh_token):
            raise MetricsAuthError("No YT_API_KEY and no YouTube OAuth credentials configured.")
        access_token = _youtube_refresh_access_token(client_id, client_secret, refresh_token)
        headers["Authorization"] = f"Bearer {access_token}"
    res = requests.get(url, headers=headers, timeout=30)
    if res.status_code in (401, 403):
        raise MetricsAuthError(
            f"YouTube stats read denied ({res.status_code}) — the upload refresh token has "
            f"upload-only scope; set YT_API_KEY (plain API key, same Cloud project) to enable "
            f"metric reads: {res.text[:200]}"
        )
    if res.status_code != 200:
        raise Exception(f"YouTube stats fetch failed ({res.status_code}): {res.text[:300]}")
    found = {}
    for item in res.json().get("items", []):
        stats = item.get("statistics", {})
        found[item.get("id")] = {
            "views": int(stats.get("viewCount", 0) or 0),
            "likes": int(stats.get("likeCount", 0) or 0),
            "comments": int(stats.get("commentCount", 0) or 0),
        }
    return {vid: found.get(vid, {"deleted": True}) for vid in ids}


def _ig_token_for_channel(channel: str) -> str:
    """Channel-appropriate FB token for insight reads (tech/news may be two
    different IG accounts with two different tokens)."""
    if channel == "news":
        return (os.environ.get("FB_ACCESS_TOKEN_NEWS") or os.environ.get("FB_ACCESS_TOKEN") or "").strip()
    return (os.environ.get("FB_ACCESS_TOKEN_TECH") or os.environ.get("FB_ACCESS_TOKEN") or "").strip()


def collect_ledger_metrics(session_id: str = "Metrics") -> dict:
    """One metrics sweep over the ledger.

    Fetches performance for entries old enough to have data
    (METRICS_MIN_AGE_HOURS), young enough to still matter
    (METRICS_MAX_AGE_DAYS), and stale by METRICS_REFRESH_HOURS. IG has no
    batch insights endpoint, so IG fetches are capped per run
    (METRICS_IG_PER_RUN, oldest-fetch first); YouTube is one batched call.

    scoring later uses `snap72` — the first fetch landing in the 48h–7d
    window — so every post is compared at roughly the same age; `latest`
    keeps refreshing for reporting.

    An auth failure stops THAT platform for the run and sends ONE loud
    Telegram alert (a feedback loop silently flying blind is the exact
    failure this guards against); per-entry errors only bump fetch_errors,
    and 5+ consecutive failures mark the platform entry deleted.
    """
    summary = {"fetched": 0, "skipped": 0, "auth_failed": []}
    if not ENABLE_POST_LEDGER:
        return summary
    now = time.time()

    def _alert(text: str) -> None:
        try:
            bot = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat = os.environ.get("TELEGRAM_CHAT_ID")
            if bot and chat:
                send_telegram_message(text, bot, chat, session_id)
        except Exception as tg_err:
            print(f"[{session_id}] [Metrics] Telegram alert failed: {tg_err}")

    with _LEDGER_LOCK:
        entries = load_post_ledger()["entries"]

    def _due(entry: dict, platform: str):
        plat = (entry.get("platforms") or {}).get(platform)
        if not plat or not plat.get("id"):
            return None
        m = dict((entry.get("metrics") or {}).get(platform) or {})
        m.setdefault("latest", None)
        m.setdefault("snap72", None)
        m.setdefault("deleted", False)
        m.setdefault("fetch_errors", 0)
        if m["deleted"]:
            return None
        posted_at = plat.get("posted_at") or entry.get("ts") or 0
        age = now - posted_at
        if age < METRICS_MIN_AGE_HOURS * 3600 or age > METRICS_MAX_AGE_DAYS * 86400:
            summary["skipped"] += 1
            return None
        last_fetch = (m["latest"] or {}).get("fetched_at", 0)
        if last_fetch > now - METRICS_REFRESH_HOURS * 3600:
            summary["skipped"] += 1
            return None
        return {"id": str(plat["id"]), "age": age, "m": m, "session": entry.get("session")}

    # updates: (session, platform) -> replacement metrics-platform dict.
    # Fetches run OUTSIDE the lock (an IG sweep is 15 sequential curl calls);
    # the merge below reloads and applies, so concurrent posting-thread writes
    # to other sessions are never clobbered.
    updates = {}
    drift_warned = False

    def _apply_result(due: dict, platform: str, stats: dict) -> None:
        nonlocal drift_warned
        m = due["m"]
        if stats.get("deleted"):
            m["deleted"] = True
        else:
            if stats.pop("_metric_drift", False) and not drift_warned:
                drift_warned = True
                _alert("⚠️ IG insights metric drift — a reduced metric set was needed; "
                       "check GRAPH_API_VERSION / _IG_INSIGHT_METRIC_SETS in main.py.")
            stats["fetched_at"] = int(now)
            m["latest"] = stats
            m["fetch_errors"] = 0
            if not m["snap72"] and 48 * 3600 <= due["age"] <= 7 * 86400:
                m["snap72"] = dict(stats)
        updates[(due["session"], platform)] = m
        summary["fetched"] += 1

    def _apply_error(due: dict, platform: str, err: Exception) -> None:
        m = due["m"]
        m["fetch_errors"] = int(m.get("fetch_errors", 0)) + 1
        print(f"[{session_id}] [Metrics] {platform} fetch failed for {due['id']} "
              f"(errors={m['fetch_errors']}): {err}")
        if m["fetch_errors"] >= 5:
            print(f"[{session_id}] [Metrics] {platform} {due['id']} failed 5+ times — "
                  f"assuming gone; marking deleted.")
            m["deleted"] = True
        updates[(due["session"], platform)] = m

    # --- Instagram (per-media insights, capped per run) ---
    ig_due = [(e, _due(e, "instagram")) for e in entries]
    ig_due = [(e, d) for e, d in ig_due if d]
    ig_due.sort(key=lambda pair: (pair[1]["m"].get("latest") or {}).get("fetched_at", 0))
    for entry, due in ig_due[:METRICS_IG_PER_RUN]:
        token = _ig_token_for_channel(entry.get("channel", "tech"))
        if not token:
            summary["skipped"] += 1
            continue
        try:
            stats = fetch_instagram_media_metrics(due["id"], token, session_id=session_id)
        except MetricsAuthError as auth_err:
            summary["auth_failed"].append("instagram")
            _alert("❌ IG metrics auth failed — the feedback loop is flying blind on "
                   f"Instagram. Refresh the FB access token. ({auth_err})")
            break
        except Exception as err:
            _apply_error(due, "instagram", err)
            continue
        _apply_result(due, "instagram", stats)

    # --- YouTube (one batched statistics call) ---
    yt_due = [d for d in (_due(e, "youtube") for e in entries) if d]
    if yt_due:
        try:
            stats_by_id = fetch_youtube_video_metrics([d["id"] for d in yt_due],
                                                      session_id=session_id)
            for due in yt_due:
                _apply_result(due, "youtube", dict(stats_by_id.get(due["id"], {"deleted": True})))
        except MetricsAuthError as auth_err:
            summary["auth_failed"].append("youtube")
            _alert(f"❌ YouTube metrics auth failed — {auth_err}")
        except Exception as err:
            for due in yt_due:
                _apply_error(due, "youtube", err)

    if updates:
        with _LEDGER_LOCK:
            ledger = load_post_ledger()
            by_session = {e.get("session"): e for e in ledger["entries"]}
            for (sess, platform), new_m in updates.items():
                target = by_session.get(sess)
                if target is not None:
                    target.setdefault("metrics", {})[platform] = new_m
            save_post_ledger(ledger)

    # Posting-hour learning is REPORT-ONLY: the CI cron times are fixed in the
    # workflow file, so surface the best blocks for a human to act on.
    try:
        stats = get_feedback_stats()
        if stats and stats.get("hours4"):
            best = sorted(stats["hours4"].items(), key=lambda kv: -kv[1]["m"])[:3]
            blocks = ", ".join(f"{int(k) * 4:02d}-{int(k) * 4 + 4:02d}h UTC "
                               f"(m={v['m']}, n={v['n']})" for k, v in best)
            print(f"[{session_id}] [Metrics] Best-performing posting blocks so far: {blocks}")
    except Exception:
        pass

    print(f"[{session_id}] [Metrics] Sweep summary: {summary}")
    return summary


def run_metrics_scheduler():
    """HF Space background thread: periodic metrics sweeps over the ledger."""
    time.sleep(120)
    print("[Metrics-Scheduler] Starting post-metrics collection thread...")
    while True:
        try:
            collect_ledger_metrics(session_id="Metrics-Scheduler")
        except Exception as e:
            import traceback
            print(f"[Metrics-Scheduler] Error in metrics loop: {e}")
            traceback.print_exc()
        time.sleep(max(60, int(METRICS_POLL_HOURS * 3600)))


# ----------------------------------------------------------------------------
# Feedback application: score the ledger, then gently bias topic / style-pack
# / hook selection toward what performed. Guardrails everywhere: identity
# behavior on cold start or when disabled, an epsilon exploration floor, and
# weight clamps — so learned bias can sharpen selection but never collapse
# the variety system.
# ----------------------------------------------------------------------------

ENABLE_FEEDBACK_LOOP = os.environ.get("ENABLE_FEEDBACK_LOOP", "true").strip().lower() == "true"
FEEDBACK_MIN_ENTRIES = int(os.environ.get("FEEDBACK_MIN_ENTRIES", "8"))
FEEDBACK_MIN_BUCKET = int(os.environ.get("FEEDBACK_MIN_BUCKET", "3"))
FEEDBACK_EPSILON = float(os.environ.get("FEEDBACK_EPSILON", "0.2"))
FEEDBACK_KW_ALPHA = float(os.environ.get("FEEDBACK_KW_ALPHA", "0.6"))
FEEDBACK_HALF_LIFE_DAYS = float(os.environ.get("FEEDBACK_HALF_LIFE_DAYS", "14"))


def _entry_perf_snapshot(entry: dict, platform: str) -> Optional[dict]:
    """The metrics snapshot an entry is SCORED on: snap72 (first fetch in the
    48h–7d window) so every post is compared at roughly the same age; falls
    back to `latest` only once the post is ≥48h old (snap window missed)."""
    m = (entry.get("metrics") or {}).get(platform) or {}
    if m.get("deleted"):
        return None
    snap = m.get("snap72")
    if not snap:
        latest = m.get("latest")
        posted = (((entry.get("platforms") or {}).get(platform)) or {}).get("posted_at") \
            or entry.get("ts") or 0
        if latest and time.time() - posted >= 48 * 3600:
            snap = latest
    return snap or None


def compute_feedback_stats(ledger: dict) -> dict:
    """Aggregate ledger performance into per-bucket weights.

    Per-platform performance is outlier-resistant by construction: log1p on
    views, ratio to the trailing per-(platform, channel) MEDIAN, and a hard
    clamp — one viral outlier can shift a bucket, not own it. The engagement
    -rate term rewards quality independent of reach. 1.0 == typical post.

    Backfilled entries (no creative metadata recorded at post time) shape the
    medians but never vote in the creative buckets.
    """
    import math
    now = time.time()
    entries = ledger.get("entries") or []

    def _components(entry: dict, platform: str) -> Optional[dict]:
        snap = _entry_perf_snapshot(entry, platform)
        if snap is None:
            return None
        views = int(snap.get("views") or 0)
        likes = int(snap.get("likes") or 0)
        comments = int(snap.get("comments") or 0)
        if platform == "instagram":
            eng = likes + 2 * comments + 3 * int(snap.get("shares") or 0) \
                + 3 * int(snap.get("saved") or 0)
            if views == 0:
                views = int(snap.get("reach") or 0)
        else:
            eng = likes + 2 * comments
        return {"v": math.log1p(views), "er": eng / max(views, 1)}

    comp_by_group: Dict[tuple, list] = {}
    per_entry = []
    for e in entries:
        pcs = {p: c for p in ("instagram", "youtube")
               for c in [_components(e, p)] if c}
        if not pcs:
            continue
        per_entry.append((e, pcs))
        for platform, c in pcs.items():
            comp_by_group.setdefault((platform, e.get("channel", "tech")), []).append(c)

    def _median(vals: list) -> float:
        s = sorted(vals)
        n = len(s)
        if not n:
            return 0.0
        mid = n // 2
        return s[mid] if n % 2 else 0.5 * (s[mid - 1] + s[mid])

    baselines = {}
    for key, lst in comp_by_group.items():
        lst = lst[-40:]  # trailing window keeps the baseline current
        baselines[key] = (_median([c["v"] for c in lst]), _median([c["er"] for c in lst]))

    stats = {"n_scored": 0, "keywords": {}, "styles": {}, "hooks": {},
             "voices": {}, "hours4": {}}
    agg: Dict[str, dict] = {k: {} for k in ("keywords", "styles", "hooks", "voices", "hours4")}

    for e, pcs in per_entry:
        ch = e.get("channel", "tech")
        perfs = []
        for platform, c in pcs.items():
            v_med, er_med = baselines.get((platform, ch), (0.0, 0.0))
            if v_med <= 0:
                continue
            perf = 0.6 * (c["v"] / v_med) + 0.4 * (c["er"] / max(er_med, 1e-4))
            perfs.append(max(0.25, min(4.0, perf)))
        if not perfs or e.get("backfilled"):
            continue
        entry_perf = sum(perfs) / len(perfs)
        stats["n_scored"] += 1
        age_days = max(0.0, (now - (e.get("ts") or now)) / 86400.0)
        w = 0.5 ** (age_days / FEEDBACK_HALF_LIFE_DAYS)

        def _acc(bucket: str, key) -> None:
            if key in (None, ""):
                return
            slot = agg[bucket].setdefault(key, [0.0, 0.0, 0])
            slot[0] += w * entry_perf
            slot[1] += w
            slot[2] += 1

        for kwd in ((e.get("topic") or {}).get("keywords") or []):
            _acc("keywords", kwd)
        _acc("styles", e.get("style_pack"))
        _acc("hooks", e.get("hook_type"))
        _acc("voices", e.get("voice"))
        if e.get("posted_hour_utc") is not None:
            _acc("hours4", int(e["posted_hour_utc"]) // 4)

    for bucket, items in agg.items():
        for key, (swp, sw, n) in items.items():
            if sw > 0:
                stats[bucket][key] = {"m": round(swp / sw, 3), "n": n}
    return stats


_FEEDBACK_CACHE = {"mtime": None, "stats": None}


def get_feedback_stats() -> Optional[dict]:
    """Cached feedback stats, or None — and None means EXACT legacy behavior
    at every application point (cold start, disabled flag, missing/edge-case
    ledger, or fewer than FEEDBACK_MIN_ENTRIES scored posts)."""
    if not (ENABLE_POST_LEDGER and ENABLE_FEEDBACK_LOOP):
        return None
    try:
        mtime = os.path.getmtime(POST_LEDGER_FILE)
    except OSError:
        return None
    if _FEEDBACK_CACHE["mtime"] != mtime:
        try:
            with _LEDGER_LOCK:
                ledger = load_post_ledger()
            _FEEDBACK_CACHE["stats"] = compute_feedback_stats(ledger)
        except Exception as e:
            print(f"[Feedback] Stats computation failed (running neutral): {e}")
            _FEEDBACK_CACHE["stats"] = None
        _FEEDBACK_CACHE["mtime"] = mtime
    stats = _FEEDBACK_CACHE["stats"]
    if not stats or stats.get("n_scored", 0) < FEEDBACK_MIN_ENTRIES:
        return None
    return stats


def _feedback_weighted_choice(options: list, key_fn, bucket: str,
                              rnd: random.Random, stats: Optional[dict]):
    """Seeded choice, gently biased by learned performance.

    Returns (choice, mode) with mode in cold|explore|learned. stats=None →
    a single plain rnd.choice — bit-for-bit the legacy draw. Otherwise an
    epsilon slice stays uniform-random and learned weights are clamped to
    [0.5, 2.0], so every option keeps ≥ ε/N probability: learned bias can
    never collapse the variety system.
    """
    if not stats:
        return rnd.choice(options), "cold"
    if rnd.random() < FEEDBACK_EPSILON:
        return rnd.choice(options), "explore"
    table = stats.get(bucket) or {}
    weights = []
    for opt in options:
        rec = table.get(key_fn(opt))
        if rec and rec.get("n", 0) >= FEEDBACK_MIN_BUCKET:
            weights.append(max(0.5, min(2.0, float(rec["m"]))))
        else:
            weights.append(1.0)
    return rnd.choices(options, weights=weights, k=1)[0], "learned"


def _feedback_keyword_bonus(title_lower: str) -> float:
    """Learned additive bonus for score_virality, from keyword buckets.

    Per-keyword contribution clamped to ±0.5 and the total to ±1.5 — small
    next to the existing 4.0 keyword cap, so learned preference nudges the
    ranking without overruling live engagement signal.
    """
    stats = get_feedback_stats()
    if not stats:
        return 0.0
    bonus = 0.0
    for word, rec in (stats.get("keywords") or {}).items():
        if word in title_lower and rec.get("n", 0) >= FEEDBACK_MIN_BUCKET:
            bonus += max(-0.5, min(0.5, FEEDBACK_KW_ALPHA * (float(rec["m"]) - 1.0)))
    return max(-1.5, min(1.5, bonus))


# ============================================================================
# VIRAL TOPIC SELECTION ENGINE
# ----------------------------------------------------------------------------
# Replaces the old "ask a small LLM to name a trending tech" guesswork (which
# had no real signal and repeated obvious picks) with a data-driven pipeline:
#
#   1. INTAKE   — pull candidates from multiple real trending sources
#                 (Hacker News, GitHub trending, Reddit, Dev.to).
#   2. SCORE    — rank each candidate for *short-form viral potential* using
#                 engagement + discussion volume + recency + a hook/keyword
#                 model tuned for what performs on YT Shorts / IG Reels.
#   3. RANK     — hand the top shortlist (WITH its metrics) to the LLM as a
#                 JUDGE — it picks the single best and writes the viral angle,
#                 scroll-stopping hook and punchy title (grounded in real data,
#                 not hallucinated).
#
# Every stage is defensive: any source or the LLM can fail and the engine
# still returns a usable plan (or None, letting the caller fall back).
# ============================================================================

# Keyword -> weight model for short-form virality. Tuned toward the emotional /
# curiosity / recognizability triggers that drive shares on YT & IG.
VIRAL_KEYWORDS: Dict[str, float] = {
    # AI wave (highest pull right now)
    "ai": 1.4, "a.i": 1.4, "gpt": 1.8, "llm": 1.4, "chatgpt": 1.9, "openai": 1.7,
    "claude": 1.5, "gemini": 1.4, "llama": 1.2, "agent": 1.1, "model": 0.6,
    "neural": 0.9, "deepseek": 1.5, "grok": 1.3,
    # Security / drama (shareable, emotional)
    "hack": 1.7, "hacked": 1.8, "breach": 1.8, "exploit": 1.5, "vulnerab": 1.4,
    "leak": 1.6, "leaked": 1.6, "malware": 1.3, "ransomware": 1.4, "backdoor": 1.4,
    "zero-day": 1.6, "0day": 1.6, "cve": 0.8, "phishing": 1.0,
    # Money / career (strong IG pull)
    "layoff": 1.7, "laid off": 1.7, "fired": 1.5, "salary": 1.7, "$": 1.1,
    "billion": 1.4, "million": 0.9, "funding": 0.9, "raised": 0.9, "ipo": 1.0,
    "acquire": 1.1, "acquisition": 1.1, "shut down": 1.4, "bankrupt": 1.5,
    # Controversy / debate (comments = reach)
    "is dead": 1.9, "killed": 1.5, "kills": 1.5, "replace": 1.3, "replaces": 1.3,
    "ban": 1.5, "banned": 1.5, "lawsuit": 1.4, "sue": 1.3, "sued": 1.4,
    "controvers": 1.3, "backlash": 1.4, "drama": 1.3, "war": 1.1, "vs": 1.0,
    # Breakthrough / novelty
    "quantum": 1.3, "breakthrough": 1.5, "first ever": 1.5, "world's first": 1.6,
    "fastest": 1.1, "record": 1.1, "launch": 0.9, "unveil": 1.0, "revolution": 1.2,
    # Curiosity / hook words
    "secret": 1.4, "nobody": 1.3, "you're": 1.1, "stop using": 1.5, "never": 1.0,
    "why": 0.7, "how": 0.5, "everyone": 1.1, "hidden": 1.2, "mistake": 1.2,
    # Recognizable brands (searchable subjects)
    "google": 0.9, "apple": 1.0, "microsoft": 0.9, "meta": 0.9, "tesla": 1.1,
    "nvidia": 1.3, "amazon": 0.8, "spacex": 1.2, "x.com": 0.9, "twitter": 0.9,
}

# Topics that rarely translate into a broadly shareable short — softly penalized.
VIRAL_NEGATIVES: Dict[str, float] = {
    "show hn": 0.8, "ask hn": 1.2, "my ": 0.5, "i built": 0.6, "i made": 0.6,
    "weekly": 0.6, "roundup": 0.6, "changelog": 0.6, "v0.": 0.4, "rfc": 0.5,
}


def _normalize_subject(s: str) -> str:
    """Lowercased, punctuation-stripped key for dedup across sources/history."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def get_reddit_top(subreddit: str, timeframe: str = "day", limit: int = 8) -> list:
    """Top posts from a subreddit via the public JSON endpoint (no auth)."""
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t={timeframe}&limit={limit}"
    headers = {"User-Agent": "NeonNode-TopicBot/1.0 (+trending video topic selection)"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"[Reddit-Scraper] r/{subreddit} failed: HTTP {r.status_code}")
            return []
        out = []
        for child in r.json().get("data", {}).get("children", []):
            d = child.get("data", {})
            if d.get("stickied") or d.get("over_18"):
                continue
            out.append({
                "source": "reddit",
                "title": d.get("title", ""),
                "subject": d.get("title", ""),
                "url": d.get("url") or f"https://reddit.com{d.get('permalink','')}",
                "engagement": int(d.get("ups", 0)),
                "comments": int(d.get("num_comments", 0)),
                "age_hours": max(0.1, (time.time() - d.get("created_utc", time.time())) / 3600.0),
                "meta": f"r/{subreddit}",
            })
        return out
    except Exception as e:
        print(f"[Reddit-Scraper] Error on r/{subreddit}: {e}")
        return []


def get_devto_top(limit: int = 10) -> list:
    """Top Dev.to articles by reactions over the last few days (no auth)."""
    url = f"https://dev.to/api/articles?top=3&per_page={limit}"
    headers = {"User-Agent": "NeonNode-TopicBot/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"[DevTo-Scraper] failed: HTTP {r.status_code}")
            return []
        out = []
        for a in r.json():
            out.append({
                "source": "devto",
                "title": a.get("title", ""),
                "subject": a.get("title", ""),
                "url": a.get("url", ""),
                "engagement": int(a.get("public_reactions_count", 0)),
                "comments": int(a.get("comments_count", 0)),
                "age_hours": 48.0,  # top=3 window; treat as mid-recency
                "meta": ", ".join(a.get("tag_list", [])[:3]) if isinstance(a.get("tag_list"), list) else "",
            })
        return out
    except Exception as e:
        print(f"[DevTo-Scraper] Error: {e}")
        return []


def get_lobsters_hottest(limit: int = 12) -> list:
    """Hottest Lobsters stories (no auth, reliable from server IPs — a resilient
    fallback for when Reddit blocks datacenter requests)."""
    url = "https://lobste.rs/hottest.json"
    headers = {"User-Agent": "NeonNode-TopicBot/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"[Lobsters-Scraper] failed: HTTP {r.status_code}")
            return []
        out = []
        for s in r.json()[:limit]:
            out.append({
                "source": "lobsters",
                "title": s.get("title", ""),
                "subject": s.get("title", ""),
                "url": s.get("url") or s.get("short_id_url", ""),
                "engagement": int(s.get("score", 0)),
                "comments": int(s.get("comment_count", 0)),
                "age_hours": 24.0,
                "meta": ", ".join(s.get("tags", [])[:3]) if isinstance(s.get("tags"), list) else "",
            })
        return out
    except Exception as e:
        print(f"[Lobsters-Scraper] Error: {e}")
        return []


def _hn_to_candidates(stories: list) -> list:
    out = []
    for s in stories:
        created = s.get("created_at_i", 0) or 0
        age = max(0.1, (time.time() - created) / 3600.0) if created else 12.0
        out.append({
            "source": "hackernews",
            "title": s.get("title", ""),
            "subject": s.get("title", ""),
            "url": s.get("url", ""),
            "engagement": int(s.get("score", 0)),
            "comments": int(s.get("num_comments", 0)),
            "age_hours": age,
            "meta": "front page",
            "_hn_id": s.get("id"),
        })
    return out


def _github_to_candidates(repos: list) -> list:
    out = []
    for r in repos:
        name = r.get("name", "")
        desc = r.get("description", "") or ""
        lang = r.get("language") or ""
        out.append({
            "source": "github",
            "title": f"{name} — {desc}"[:160],
            "subject": name,
            "url": r.get("url", ""),
            "engagement": int(r.get("stars", 0)),
            "comments": 0,
            "age_hours": 240.0,  # created within ~30d; evergreen-ish recency
            "meta": f"{lang} project: {desc}"[:180],
        })
    return out


def score_virality(c: dict) -> float:
    """Heuristic 0..~12 viral-potential score for a normalized candidate."""
    import math
    eng = float(c.get("engagement", 0))
    com = float(c.get("comments", 0))
    age = float(c.get("age_hours", 24.0)) or 24.0
    title = (c.get("title", "") + " " + c.get("meta", "")).lower()

    # Engagement + discussion (log-compressed so sources with different scales
    # — HN points vs GitHub stars vs Reddit upvotes — stay comparable).
    engagement_score = math.log10(1.0 + eng) * 1.4
    discussion_score = math.log10(1.0 + com) * 0.9  # comments == shareable debate

    # Recency: reward fresh items; decays over ~3 days. GitHub's flat 240h age
    # keeps it neutral (it's a project, not breaking news).
    recency_score = max(0.0, 1.0 - (age / 72.0)) * 1.6

    # Hook / keyword model.
    kw = 0.0
    for word, w in VIRAL_KEYWORDS.items():
        if word in title:
            kw += w
    kw = min(kw, 4.0)  # cap so one keyword-stuffed title can't dominate
    for word, mult in VIRAL_NEGATIVES.items():
        if word in title:
            kw *= mult
    # Learned keyword bonus from the post-performance feedback loop (0.0 on
    # cold start / disabled; bounded ±1.5 vs the 4.0 raw-keyword cap).
    kw += _feedback_keyword_bonus(title)

    # Title punchiness: numbers and short titles hook better on short-form.
    punch = 0.0
    if re.search(r"\d", title):
        punch += 0.4
    wc = len(c.get("title", "").split())
    if 3 <= wc <= 12:
        punch += 0.4

    return engagement_score + discussion_score + recency_score + kw + punch


def _gather_candidates(kind: str) -> list:
    """Pull and normalize candidates from the trending sources for a channel kind."""
    candidates: list = []
    if kind == "news":
        candidates += _hn_to_candidates(get_hacker_news_frontpage(min_score=120, limit=12))
        candidates += get_lobsters_hottest(12)
        candidates += get_reddit_top("technology", "day", 8)
        candidates += get_reddit_top("programming", "day", 6)
    else:  # "tech"
        candidates += _github_to_candidates(get_github_trending_repos(limit=10))
        candidates += _hn_to_candidates(get_hacker_news_frontpage(min_score=100, limit=10))
        candidates += get_lobsters_hottest(12)
        candidates += get_devto_top(10)
        candidates += get_reddit_top("programming", "week", 8)
        candidates += get_reddit_top("technology", "week", 6)
    # Drop empties / obvious junk
    return [c for c in candidates if c.get("title") and len(c["title"]) > 6]


def _llm_rank_and_angle(shortlist: list, kind: str, session_id: str) -> Optional[dict]:
    """LLM-as-judge over the scored shortlist: pick the best + write the angle.

    Returns a plan dict merged with the chosen candidate, or None on failure.
    Kept small-model friendly: compact list in, strict tiny JSON out.
    """
    if not shortlist:
        return None

    lines = []
    for i, c in enumerate(shortlist, 1):
        meta = (c.get("meta") or "").strip()
        meta_part = f" | {meta}" if meta else ""
        lines.append(
            f"{i}. [{c['source']} | {int(c.get('engagement',0))} eng | "
            f"{int(c.get('comments',0))} comments | {round(c.get('age_hours',0))}h old{meta_part}] {c['title']}"
        )
    listing = "\n".join(lines)

    audience = (
        "breaking-tech-news reels" if kind == "news"
        else "a tech education / hot-take channel"
    )
    system = (
        "You are a viral short-form video producer for YouTube Shorts and Instagram Reels. "
        "You pick topics that STOP THE SCROLL and get shared, and you write killer hooks. "
        "You only ever answer with strict JSON."
    )
    user = f"""Below are real trending tech items with engagement data, ranked by an initial virality model.
Pick the SINGLE best one to turn into a 20-40 second vertical video for {audience}.

Choose for MAXIMUM viral potential: a recognizable/searchable subject, a strong emotional or curiosity hook, and broad shareability (not niche insider stuff). Prefer timely + debate-worthy over generic.

HARD REQUIREMENT — the subject must be ONE named, concrete thing: a specific product, tool, library, release, gadget, company move, or incident. NEVER an abstract theme or life advice ("AI is changing everything", "good tools boost productivity" = instant reject). The viewer must learn something they can name, search, and try.

CANDIDATES:
{listing}

Return ONLY this JSON (no other text):
{{"pick": <candidate number>, "subject": "<2-5 word searchable topic>", "angle": "<the specific viral angle in one vivid sentence>", "hook": "<a scroll-stopping first line, max 8 words>", "facts": ["<2-4 concrete facts from the item: what it is/does, a real number or spec, what changed>"], "format": "explainer|hot-take|news|listicle|comparison", "title": "<punchy 5-9 word video title>", "why": "<why this will perform, one short phrase>"}}"""

    try:
        raw = query_llm_with_failover(
            system_prompt=system,
            user_prompt=user,
            max_tokens=350,
            json_format=True,
            session_id=session_id,
        )
    except Exception as e:
        print(f"[TopicEngine] LLM ranker failed: {e}")
        return None

    # Same coercion the failover gate uses — anything the gate passed as
    # "recoverable JSON" must actually be recovered here, not dropped by a
    # weaker ad-hoc parser (think-blocks, fences, unquoted keys, ...).
    plan = _coerce_llm_json(raw, "TopicEngine", quiet=True)
    if not isinstance(plan, dict):
        print(f"[TopicEngine] Could not parse ranker JSON: {raw[:200]}")
        return None

    # Resolve the chosen candidate (default to the top-scored one).
    idx = 0
    try:
        idx = max(0, min(len(shortlist) - 1, int(plan.get("pick", 1)) - 1))
    except Exception:
        idx = 0
    chosen = shortlist[idx]

    facts = plan.get("facts")
    if not isinstance(facts, list):
        facts = []
    facts = [str(f).strip() for f in facts if str(f).strip()][:4]

    # Ground the LLM's "facts" in the actual source before they are injected
    # into the script prompt as truth. The ranking listing only contains the
    # headline + engagement metadata, so any detail beyond it is guesswork:
    # verify each fact against the fetched article/repo text and drop what
    # can't be traced back to the source.
    corpus = f"{chosen.get('title', '')} {chosen.get('meta', '')}"
    try:
        corpus += " " + (extract_article_body(chosen.get("url") or "") or "")
    except Exception:
        pass
    corpus_norm = corpus.lower().replace(",", "")
    grounded = []
    for fact in facts:
        nums = re.findall(r"\d[\d,.]*", fact)
        nums_ok = all(n.replace(",", "").rstrip(".") in corpus_norm for n in nums)
        words = re.findall(r"[a-z0-9]{4,}", fact.lower())
        overlap = (sum(1 for w in words if w in corpus_norm) / len(words)) if words else 0.0
        if nums_ok and overlap >= 0.5:
            grounded.append(fact)
        else:
            print(f"[TopicEngine] Dropped ungrounded fact (overlap={round(overlap, 2)}, nums_ok={nums_ok}): {fact!r}")
    facts = grounded

    return {
        "subject": (plan.get("subject") or chosen.get("subject") or chosen.get("title", "")).strip(),
        "angle": (plan.get("angle") or "").strip(),
        "hook": (plan.get("hook") or "").strip(),
        "facts": facts,
        "format": (plan.get("format") or "explainer").strip(),
        "title": (plan.get("title") or "").strip(),
        "why": (plan.get("why") or "").strip(),
        "source": chosen.get("source"),
        "url": chosen.get("url"),
        "engagement": chosen.get("engagement"),
        "score": round(chosen.get("_score", 0.0), 2),
        "candidate": chosen,
    }


def select_viral_topic(kind: str, processed: list, session_id: str = "TopicEngine",
                       shortlist_size: int = 8) -> Optional[dict]:
    """Full pipeline: intake -> score -> dedupe -> LLM rank/angle -> plan.

    `kind` is "tech" or "news". `processed` is the history of already-used
    subjects/titles (normalized here) to avoid repeats. Returns a plan dict or
    None if nothing usable surfaced (caller should fall back).
    """
    candidates = _gather_candidates(kind)
    if not candidates:
        print(f"[TopicEngine] No candidates from any source (kind={kind}).")
        return None

    seen_norm = {_normalize_subject(p) for p in (processed or [])}

    # Score, drop already-used, and de-dupe near-identical subjects.
    scored = []
    local_seen = set()
    for c in candidates:
        norm = _normalize_subject(c.get("subject") or c.get("title"))
        if not norm or norm in seen_norm or norm in local_seen:
            continue
        # Skip if the normalized subject shares its head with a processed one
        head = " ".join(norm.split()[:3])
        if head and any(head and head in s for s in seen_norm):
            continue
        local_seen.add(norm)
        c["_score"] = score_virality(c)
        scored.append(c)

    if not scored:
        print(f"[TopicEngine] All candidates already processed (kind={kind}).")
        return None

    scored.sort(key=lambda x: x["_score"], reverse=True)
    shortlist = scored[: max(3, shortlist_size)]
    print(f"[TopicEngine] {len(candidates)} candidates -> top {len(shortlist)} "
          f"(kind={kind}). Leader: '{shortlist[0]['title'][:70]}' "
          f"[{shortlist[0]['source']} score={round(shortlist[0]['_score'],2)}]")

    plan = _llm_rank_and_angle(shortlist, kind, session_id)
    if not plan:
        # Fallback: take the top-scored candidate with a generic angle.
        top = shortlist[0]
        plan = {
            "subject": top.get("subject") or top.get("title"),
            "angle": f"Why {top.get('subject') or top.get('title')} is trending right now.",
            "hook": "", "format": "explainer", "title": "", "why": "top viral score",
            "source": top.get("source"), "url": top.get("url"),
            "engagement": top.get("engagement"), "score": round(top.get("_score", 0.0), 2),
            "candidate": top,
        }
    print(f"[TopicEngine] Selected: subject='{plan['subject']}' angle='{plan['angle'][:80]}' "
          f"format={plan['format']} source={plan['source']}")
    return plan


def build_viral_topic_prompt(plan: dict) -> str:
    """Turn a topic plan into the render prompt for the auto-tech channel.

    Enforces a CONCRETENESS CONTRACT: every video is about ONE named subject
    and must teach real, demonstrable specifics — never generic tech-life
    platitudes the viewer already knows.
    """
    subject = plan.get("subject", "")
    angle = plan.get("angle", "")
    hook = plan.get("hook", "")
    facts = plan.get("facts") or []
    fmt = plan.get("format", "explainer")
    parts = [
        f"Create a fast-paced, highly shareable vertical (9:16) short-form video about: {subject}.",
    ]
    if angle:
        parts.append(f"ANGLE (this is the whole point of the video): {angle}")
    if hook:
        parts.append(f'Open on the FIRST scene with this scroll-stopping hook energy: "{hook}".')
    if facts:
        parts.append(
            "VERIFIED SOURCE FACTS — these are the ONLY specifics you may use. Weave at least two of them into the "
            "scenes verbatim-accurate, and do NOT add numbers, people, or quotes beyond them: "
            + "; ".join(facts) + "."
        )
    else:
        parts.append(
            "No verified facts are available beyond the title — describe only what the subject verifiably is and "
            "does. Do NOT invent numbers, people, quotes, or testimonials."
        )
    parts.append(
        f"Content format: {fmt}. CONCRETENESS CONTRACT: the entire video is about {subject} and nothing else. "
        f"Name {subject} in the HOOK scene ONLY — after that refer to it as \"it\" / \"the tool\" / \"the release\", and NEVER "
        "restate the headline again (the subtitles show every spoken word, so a repeated line gets read and heard 5-6 times "
        "and instantly feels cheap). Each scene must add something the earlier scenes did not say. "
        "Keep on-screen \"text\" to a short label (keyword or number) that does NOT copy the voiceover wording. "
        "Give each scene a \"videoQuery\": 2-4 keywords for a TECH MOTION b-roll clip that shows the subject in action "
        "(terminal, code on screen, dashboard, data-center racks, chip macro, robot, network traffic) — topic-relevant motion, "
        "different per scene, never a generic abstract loop. "
        "DEMONSTRATE it — at least one scene must show HOW it actually works in practice (what you run/click/type, what it "
        "replaces, or a real spec/benchmark), e.g. a list scene with concrete usage steps or a metric scene with a real number. "
        "BANNED: generic truisms everyone already knows ('good tools make you productive', 'AI is changing everything', "
        "'automation saves time') — every sentence must contain information specific to this subject. "
        "Structure it as a story that escalates (hook, why it matters, the surprising detail, payoff), not a list of facts. "
        "Make tech enthusiasts and developers stop scrolling, feel a jolt of curiosity or surprise, and want to share it. "
        "End with one punchy takeaway that rewards watching to the end."
    )
    return " ".join(parts)


def run_news_scheduler():
    """Background thread polling Hacker News for breaking stories."""
    # Add a short delay to allow the server to complete startup and respond to health checks
    time.sleep(30)
    print("[News-Scheduler] Starting Breaking Tech News background pipeline...")
    min_score = int(os.environ.get("AUTO_NEWS_MIN_SCORE", "150"))
    poll_minutes = int(os.environ.get("AUTO_NEWS_POLL_MINUTES", "15"))
    
    # Check for text gen key (required to run LLM)
    t_key = os.environ.get("NVIDIA_NIM_KEY") or os.environ.get("TEXT_GEN_KEY")
    if not t_key:
        print("[News-Scheduler] WARNING: Neither NVIDIA_NIM_KEY nor TEXT_GEN_KEY is set. News scheduler aborted.")
        return
        
    ig_method = os.environ.get("INSTAGRAM_NEWS_METHOD", "").strip().lower()
    ig_biz_id = os.environ.get("INSTAGRAM_NEWS_BUSINESS_ACCOUNT_ID", "").strip()
    ig_token = os.environ.get("FB_ACCESS_TOKEN_NEWS", "").strip()
    ig_user = os.environ.get("INSTAGRAM_NEWS_USERNAME", "").strip()
    ig_pass = os.environ.get("INSTAGRAM_NEWS_PASSWORD", "").strip()
        
    while True:
        try:
            # Preflight check to save resources
            if ig_method == "official" and ig_biz_id and ig_token:
                if not test_instagram_official_connection(ig_biz_id, ig_token, session_id="auto-news"):
                    print("[News-Scheduler] Preflight check failed (Official). Skipping video generation this cycle.")
                    time.sleep(60)
                    continue
            elif ig_method == "unofficial" and ig_user and ig_pass:
                if not test_instagram_unofficial_connection(ig_user, ig_pass, session_id="auto-news"):
                    print("[News-Scheduler] Preflight check failed (Unofficial). Skipping video generation this cycle.")
                    time.sleep(60)
                    continue
                    
            print("[News-Scheduler] Polling Hacker News front page...")
            stories = get_hacker_news_frontpage(min_score=min_score, limit=12)
            history = load_topic_history(PROCESSED_NEWS_FILE)
            used_ids = {str(h.get("id")) for h in history if h.get("id")}
            used_norms = {h.get("norm") for h in history if h.get("norm")}

            # Rank unprocessed stories by viral potential and take the strongest,
            # instead of blindly grabbing whatever sits first on the front page.
            # Dedup by id AND normalized title — the same story can resurface
            # under a new HN id.
            target_story = None
            ranked = []
            for story in stories:
                story_id = story.get("id")
                if not story_id or str(story_id) in used_ids:
                    continue
                if _normalize_subject(story.get("title", "")) in used_norms:
                    continue
                cand = _hn_to_candidates([story])[0]
                ranked.append((score_virality(cand), story, cand["title"]))
            if ranked:
                ranked.sort(key=lambda x: x[0], reverse=True)
                target_story = ranked[0][1]
                print(f"[News-Scheduler] Top story by viral score "
                      f"({round(ranked[0][0], 2)}): '{ranked[0][2][:70]}'")
                    
            if target_story:
                title = target_story["title"]
                url = target_story["url"]
                story_id = target_story["id"]
                
                print(f"[News-Scheduler] Found new breaking story: '{title}' ({url}). Triggering render...")
                
                # Extract webpage content
                body = extract_article_body(url)
                prompt = build_hn_news_prompt(title, body)
                
                # Build Instagram config for News account if env vars are present
                ig_cfg = None
                ig_method = os.environ.get("INSTAGRAM_NEWS_METHOD", "unofficial")
                if ig_method == "official":
                    biz_id = os.environ.get("INSTAGRAM_NEWS_BUSINESS_ACCOUNT_ID")
                    token = os.environ.get("FB_ACCESS_TOKEN_NEWS")
                    if biz_id and token:
                        ig_cfg = InstagramConfig(
                            enabled=True,
                            method="official",
                            instagram_business_account_id=biz_id,
                            fb_access_token=token,
                            auto_generate_caption=True
                        )
                else:
                    user = os.environ.get("INSTAGRAM_NEWS_USERNAME")
                    pwd = os.environ.get("INSTAGRAM_NEWS_PASSWORD")
                    if user and pwd:
                        ig_cfg = InstagramConfig(
                            enabled=True,
                            method="unofficial",
                            username=user,
                            password=pwd,
                            auto_generate_caption=True
                        )
                
                # Trigger the render
                render_req = RenderRequest(
                    prompt=prompt,
                    nvidia_nim_key=t_key,
                    topic_meta={
                        "title": title,
                        "subject": title,
                        "url": url,
                        "source": "hn",
                        "keywords": _extract_topic_keywords(title),
                        "viral_score": round(float(ranked[0][0]), 2) if ranked else None,
                    },
                    pipeline=PipelineConfig(
                        quality="standard",
                        instagram=ig_cfg,
                        youtube=_build_env_youtube_config()
                    )
                )

                session_id = f"auto-news-{str(uuid.uuid4())[:4]}"
                _execute_render(render_req, session_id)
                
                # Mark as processed (shared schema with generate_now.py). A
                # failed save must not kill the polling loop, but it must be
                # loud — a silent one quietly resurrects the repeat-topic bug.
                try:
                    record_topic_use(PROCESSED_NEWS_FILE, story_id=story_id,
                                     title=title, session_id=session_id)
                except Exception as hist_err:
                    print(f"[News-Scheduler] WARNING: topic-history save failed "
                          f"(next cycle may repeat this story): {hist_err}")
                print(f"[News-Scheduler] Successfully processed story '{title}'.")
            else:
                print("[News-Scheduler] No new unprocessed breaking stories found.")
                
        except Exception as e:
            import traceback
            print(f"[News-Scheduler] Error in polling loop: {e}")
            traceback.print_exc()
            
        time.sleep(poll_minutes * 60)


def _compute_post_sleep_seconds() -> int:
    """Human-like posting cadence for the auto channels (anti-shadowban pacing).

    Platforms flag ACCOUNTS, not APIs, for robotic behavior — posting at the
    exact same interval every time is the classic bot fingerprint. Strategy:
    - AUTO_POSTS_PER_DAY (default 5) sets the base interval (24h / N).
    - Every gap gets ±30% random jitter so no two gaps are identical.
    - AUTO_QUIET_HOURS (default "1-7", local server time) is a sleep window:
      if the next slot lands inside it, push past the window end (+ jitter) —
      humans don't post at 4am, and posting into a dead audience also tanks
      early engagement velocity, which is what actually triggers reach decay.
    - AUTO_TECH_POST_HOURS (legacy) still overrides the base interval if set.
    """
    legacy_hours = os.environ.get("AUTO_TECH_POST_HOURS", "").strip()
    if legacy_hours:
        base = float(legacy_hours) * 3600
    else:
        posts_per_day = max(1, int(os.environ.get("AUTO_POSTS_PER_DAY", "5")))
        base = 86400.0 / posts_per_day

    sleep_sec = base * random.uniform(0.7, 1.3)

    quiet = os.environ.get("AUTO_QUIET_HOURS", "1-7").strip()
    if quiet and "-" in quiet:
        try:
            q_start, q_end = (int(x) for x in quiet.split("-", 1))
            wake = datetime.datetime.now() + datetime.timedelta(seconds=sleep_sec)
            h = wake.hour
            in_window = (q_start <= h < q_end) if q_start <= q_end else (h >= q_start or h < q_end)
            if in_window:
                # Push wake-up past the quiet window end, with fresh jitter
                target = wake.replace(hour=q_end % 24, minute=0, second=0)
                if target <= wake:
                    target += datetime.timedelta(days=1)
                sleep_sec = (target - datetime.datetime.now()).total_seconds() + random.uniform(300, 2700)
        except ValueError:
            pass

    return max(600, int(sleep_sec))


def _build_env_youtube_config() -> Optional["YouTubeConfig"]:
    """YouTubeConfig from env vars, or None if the OAuth trio isn't configured."""
    if os.environ.get("ENABLE_YOUTUBE_AUTOPOST", "").strip().lower() != "true":
        return None
    if not (os.environ.get("YT_CLIENT_ID") and os.environ.get("YT_CLIENT_SECRET") and os.environ.get("YT_REFRESH_TOKEN")):
        return None
    return YouTubeConfig(
        enabled=True,
        privacy_status=os.environ.get("YT_PRIVACY_STATUS", "public").strip() or "public",
        auto_generate_metadata=True,
    )


def run_tech_scheduler():
    """Background thread generating videos for tech topics and usecases on a daily cycle."""
    # Add a short delay to allow the server to complete startup and respond to health checks
    time.sleep(30)
    print("[Tech-Scheduler] Starting Tech Usecases background pipeline...")
    
    # Resolve text generation API key from environment variables
    t_key = (
        os.environ.get("NVIDIA_NIM_KEY") 
        or os.environ.get("TEXT_GEN_KEY") 
        or os.environ.get("GROQ_API_KEY") 
        or os.environ.get("OPENROUTER_API_KEY") 
        or os.environ.get("GEMINI_API_KEY") 
        or os.environ.get("GITHUB_API_KEY") 
        or os.environ.get("GITHUB_TOKEN") 
        or ""
    ).strip()
    
    if not t_key:
        print("[Tech-Scheduler] WARNING: No LLM API keys configured. Tech scheduler aborted.")
        return
        
    ig_method = os.environ.get("INSTAGRAM_TECH_METHOD", "").strip().lower()
    ig_biz_id = os.environ.get("INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID", "").strip()
    ig_token = os.environ.get("FB_ACCESS_TOKEN_TECH", "").strip()
    ig_user = os.environ.get("INSTAGRAM_TECH_USERNAME", "").strip()
    ig_pass = os.environ.get("INSTAGRAM_TECH_PASSWORD", "").strip()
        
    while True:
        try:
            # Preflight check to save resources
            if ig_method == "official" and ig_biz_id and ig_token:
                if not test_instagram_official_connection(ig_biz_id, ig_token, session_id="auto-tech"):
                    print("[Tech-Scheduler] Preflight check failed (Official). Skipping video generation this cycle.")
                    time.sleep(60) # Wait 60s before skipping to avoid spamming tight loops if error occurs
                    continue
            elif ig_method == "unofficial" and ig_user and ig_pass:
                if not test_instagram_unofficial_connection(ig_user, ig_pass, session_id="auto-tech"):
                    print("[Tech-Scheduler] Preflight check failed (Unofficial). Skipping video generation this cycle.")
                    time.sleep(60)
                    continue
                    
            processed_techs = load_processed_items(PROCESSED_TECH_FILE)

            # Step 1: Data-driven viral topic selection (real trending signal ->
            # virality scoring -> LLM-as-judge writing the angle & hook).
            print("[Tech-Scheduler] Selecting a viral topic from live trending sources...")
            selected_tech = None
            prompt = None
            topic_plan = select_viral_topic("tech", processed_techs, session_id="Tech-Scheduler")

            if topic_plan and topic_plan.get("subject"):
                selected_tech = topic_plan["subject"]
                prompt = build_viral_topic_prompt(topic_plan)
                print(f"[Tech-Scheduler] Topic engine picked: '{selected_tech}' "
                      f"(source={topic_plan.get('source')}, score={topic_plan.get('score')})")
            else:
                # Fallback: legacy blind-LLM pick so the channel never stalls if
                # every trending source is unreachable this cycle.
                print("[Tech-Scheduler] Topic engine returned nothing; falling back to LLM pick.")
                try:
                    selected_tech = query_llm_with_failover(
                        system_prompt="You are a helpful tech assistant. Answer concisely with only the technology name.",
                        user_prompt=(
                            "Name ONE specific, currently-relevant developer tool, framework, database, or product FEATURE "
                            "that is concrete and demonstrable (e.g., 'Docker Compose Watch', 'Postgres LISTEN/NOTIFY', "
                            "'Bun's built-in SQLite', 'React Server Components') — something a viewer can search and try, "
                            "NOT an abstract concept or category. It must NOT be "
                            f"in this list of already processed technologies: {processed_techs[-40:]}.\n"
                            "Return ONLY the plain name (1-4 words), no extra text or quotes."
                        ),
                        max_tokens=50,
                        json_format=False,
                        session_id="Tech-Scheduler"
                    ).strip().strip("'\"`")
                except Exception as e:
                    print(f"[Tech-Scheduler] Fallback pick failed: {e}. Retrying in 5 minutes...")
                    time.sleep(300)
                    continue
                if selected_tech:
                    prompt = (
                        f"Create a fast-paced, highly shareable vertical video about {selected_tech}: what it is, ONE real-world "
                        f"use case shown concretely (what you run/click/type), and a real number or spec that proves why it matters. "
                        f"Name {selected_tech} in the first two scenes. NO generic filler — every sentence must be specific to "
                        f"{selected_tech}. Open with a scroll-stopping hook and end with a punchy takeaway."
                    )

            if selected_tech and prompt:
                
                # Build Instagram config for Tech account if env vars are present
                ig_cfg = None
                ig_method = os.environ.get("INSTAGRAM_TECH_METHOD", "official")
                if ig_method == "official":
                    biz_id = os.environ.get("INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID")
                    token = os.environ.get("FB_ACCESS_TOKEN_TECH")
                    if biz_id and token:
                        ig_cfg = InstagramConfig(
                            enabled=True,
                            method="official",
                            instagram_business_account_id=biz_id,
                            fb_access_token=token,
                            auto_generate_caption=True
                        )
                elif ig_method == "email":
                    ig_cfg = InstagramConfig(
                        enabled=True,
                        method="email",
                        auto_generate_caption=True
                    )
                elif ig_method == "discord":
                    ig_cfg = InstagramConfig(
                        enabled=True,
                        method="discord",
                        auto_generate_caption=True
                    )
                elif ig_method == "local_only":
                    ig_cfg = InstagramConfig(
                        enabled=True,
                        method="local_only",
                        auto_generate_caption=True
                    )
                elif ig_method == "unofficial":
                    user = os.environ.get("INSTAGRAM_TECH_USERNAME")
                    pwd = os.environ.get("INSTAGRAM_TECH_PASSWORD")
                    if user and pwd:
                        ig_cfg = InstagramConfig(
                            enabled=True,
                            method="unofficial",
                            username=user,
                            password=pwd,
                            auto_generate_caption=True
                        )
                
                # Trigger the render
                _plan = topic_plan or {}
                _orig_title = ((_plan.get("candidate") or {}).get("title", "")) or selected_tech
                render_req = RenderRequest(
                    prompt=prompt,
                    nvidia_nim_key=t_key,
                    topic_meta={
                        "title": _orig_title,
                        "subject": selected_tech,
                        "url": _plan.get("url", ""),
                        "source": _plan.get("source", "llm"),
                        "keywords": _extract_topic_keywords(_orig_title),
                        "viral_score": _plan.get("score"),
                    },
                    pipeline=PipelineConfig(
                        quality="standard",
                        instagram=ig_cfg,
                        youtube=_build_env_youtube_config()
                    )
                )

                session_id = f"auto-tech-{str(uuid.uuid4())[:4]}"
                _execute_render(render_req, session_id)

                # Mark as processed — record BOTH the (possibly LLM-rewritten)
                # subject and the ORIGINAL candidate title. select_viral_topic
                # dedups against original titles, so storing only the rewrite
                # let the same story be re-picked under its source wording.
                processed_techs.append(selected_tech)
                orig_title = ((topic_plan or {}).get("candidate") or {}).get("title", "")
                if orig_title and _normalize_subject(orig_title) != _normalize_subject(selected_tech):
                    processed_techs.append(orig_title)
                # Keep history bounded so the dedup set / file stays lean.
                if len(processed_techs) > 300:
                    processed_techs = processed_techs[-300:]
                save_processed_items(PROCESSED_TECH_FILE, processed_techs)
                print(f"[Tech-Scheduler] Successfully processed tech video for '{selected_tech}'.")

                # Successful run, sleep with human-like jittered pacing
                sleep_sec = _compute_post_sleep_seconds()
                print(f"[Tech-Scheduler] Video render complete. Next post in ~{sleep_sec / 3600:.1f}h (jittered anti-bot cadence)...")
                time.sleep(sleep_sec)
            else:
                print("[Tech-Scheduler] Could not resolve a technology topic. Retrying in 5 minutes...")
                time.sleep(300)
                
        except Exception as e:
            import traceback
            print(f"[Tech-Scheduler] Error in tech loop: {e}. Retrying in 5 minutes...")
            traceback.print_exc()
            time.sleep(300)


@app.get("/analytics/summary", dependencies=[Depends(verify_api_key)])
def analytics_summary():
    """Feedback-loop debugging: current ledger-derived performance stats and
    whether the learned bias is active (vs cold-start neutral)."""
    with _LEDGER_LOCK:
        ledger = load_post_ledger()
    stats = compute_feedback_stats(ledger)
    return {
        "entries": len(ledger.get("entries") or []),
        "n_scored": stats.get("n_scored", 0),
        "feedback_active": get_feedback_stats() is not None,
        "min_entries_required": FEEDBACK_MIN_ENTRIES,
        "stats": stats,
    }


@app.on_event("startup")
def start_schedulers():
    """Startup trigger to initiate active content pipelines."""
    # Check if schedulers are explicitly enabled via env vars
    if os.environ.get("ENABLE_AUTO_NEWS") == "true":
        threading.Thread(target=run_news_scheduler, daemon=True).start()
    else:
        print("[Scheduler] Breaking news scheduler is disabled (ENABLE_AUTO_NEWS != 'true').")
        
    if os.environ.get("ENABLE_AUTO_TECH") == "true":
        threading.Thread(target=run_tech_scheduler, daemon=True).start()
    else:
        print("[Scheduler] Tech usecase scheduler is disabled (ENABLE_AUTO_TECH != 'true').")

    if ENABLE_POST_LEDGER and os.environ.get("ENABLE_METRICS_LOOP", "").strip().lower() == "true":
        threading.Thread(target=run_metrics_scheduler, daemon=True).start()
    else:
        print("[Scheduler] Post-metrics loop is disabled (ENABLE_METRICS_LOOP != 'true').")



