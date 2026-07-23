import sys
from main import (
    test_instagram_unofficial_connection,
    test_instagram_official_connection,
    load_processed_items,
    PROCESSED_TECH_FILE,
    query_llm_with_failover,
    _execute_render,
    RenderRequest,
    PipelineConfig,
    InstagramConfig
)
import os
import uuid

def post_now():
    """Forces exactly one tech video to generate and post right now."""
    print("🚀 Forcing a single Tech Video Generation...")
    
    # 0. Load .env manually
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    if key.strip() and key.strip() not in os.environ:
                        os.environ[key.strip()] = val.strip().strip("'\"")
    
    # 1. Check API Keys
    t_key = (
        os.environ.get("NVIDIA_NIM_KEY") or os.environ.get("TEXT_GEN_KEY") or 
        os.environ.get("GROQ_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or 
        os.environ.get("GEMINI_API_KEY") or ""
    ).strip()
    
    if not t_key:
        print("❌ Error: No LLM API key found in .env (e.g. GROQ_API_KEY).")
        sys.exit(1)

    # 2. Pre-flight Check (Bypassed for local only)
    # 2. Method selection (reads from .env: default "official")
    ig_method = (os.environ.get("INSTAGRAM_TECH_METHOD") or "official").lower()
    print(f"📡 Selected Publishing Method: {ig_method}")
    
    # 3. Generate the Script
    print("🧠 Asking LLM for a tech topic...")
    tech_prompt = (
        "Choose ONE trending, important software development technology, cloud technology, framework, database, or concept "
        "that you have not covered recently. It must be specific (e.g., 'Docker Volumes', 'React Server Components', "
        "'Kubernetes Pods', 'Vector Databases'). Return only the name of the technology, nothing else."
    )
    
    topic = query_llm_with_failover(
        system_prompt="You are a tech selector. Return only the short name of a tech topic.",
        user_prompt=tech_prompt,
        max_tokens=30,
        json_format=False,
        session_id="force-post"
    ).strip().strip("'\"`")
    print(f"✅ Topic chosen: {topic}")
    
    # 4. Trigger the full renderer pipeline
    prompt = (
        f"Create a fast-paced vertical video focusing on the core architecture, real-world use case, and key benefits of {topic}. "
        "Make it extremely engaging for developers and engineers. Emphasize why they should use it and when it is the best tool for the job."
    )

    ig_cfg = None
    if ig_method == "official":
        biz_id = (
            os.environ.get("INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID") or
            os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
        )
        token = (
            os.environ.get("FB_ACCESS_TOKEN_TECH") or
            os.environ.get("FB_PAGE_ACCESS_TOKEN") or
            os.environ.get("FB_ACCESS_TOKEN")
        )
        if biz_id and token:
            ig_cfg = InstagramConfig(
                enabled=True,
                method="official",
                instagram_business_account_id=biz_id,
                fb_access_token=token,
                auto_generate_caption=True
            )
        else:
            print("⚠️ Official Meta Graph API credentials missing from .env. Falling back to local_only.")
            ig_cfg = InstagramConfig(enabled=True, method="local_only", auto_generate_caption=True)
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
        else:
            ig_cfg = InstagramConfig(enabled=True, method="local_only", auto_generate_caption=True)
    else:
        ig_cfg = InstagramConfig(
            enabled=True,
            method="local_only",
            auto_generate_caption=True
        )

    # Build Telegram Config if credentials present in .env
    tg_bot = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
    tg_cfg = None
    if tg_bot and tg_chat:
        from main import TelegramConfig
        tg_cfg = TelegramConfig(enabled=True, bot_token=tg_bot, chat_id=tg_chat, auto_generate_caption=True)
        print("📲 Telegram Delivery: ENABLED")
    else:
        print("ℹ️ Telegram Delivery: Disabled (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not in .env)")

    # Build Facebook Reels Config if credentials present in .env
    fb_page = os.environ.get("FB_PAGE_ID")
    fb_token = os.environ.get("FB_PAGE_ACCESS_TOKEN") or os.environ.get("FB_ACCESS_TOKEN_TECH") or os.environ.get("FB_ACCESS_TOKEN")
    fb_cfg = None
    if fb_page and fb_token:
        from main import FacebookConfig
        fb_cfg = FacebookConfig(enabled=True, page_id=fb_page, page_access_token=fb_token, auto_generate_caption=True)
        print("📘 Facebook Page Reels: ENABLED")

    req = RenderRequest(
        prompt=prompt,
        nvidia_nim_key=t_key,
        pipeline=PipelineConfig(
            quality="standard",
            instagram=ig_cfg,
            telegram=tg_cfg,
            facebook=fb_cfg
        )
    )

    
    try:
        from main import _execute_render_unlocked
        session_id = f"force-post-{str(uuid.uuid4())[:4]}"
        _execute_render_unlocked(req, session_id=session_id, sync_delivery=True)
        print("\n🎉 Successfully rendered and published video via Meta Graph API!")
    except Exception as e:
        print(f"❌ Failed to generate video: {e}")


if __name__ == "__main__":
    post_now()
