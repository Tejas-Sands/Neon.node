"""Artistic Scenery branch — CI entry point.

10-20s fast-cut cinematic scenery montages: real stock footage (Pexels/Pixabay)
mixed with AI-generated surreal stills, edited render-side by the
ArtisticScenery Remotion composition (beat-grid cuts, whip/flash/rgb edits,
one poetic overlay line). Music-only — no TTS, so none of main.py's
spoken-runtime machinery applies here.

Delivery is Telegram-only for now (iteration mode); platform posting comes
later once the look is dialed in.

Run modes:
    python generate_scenery.py                          # full run: concept -> fetch -> render -> post
    python generate_scenery.py --dry-run                # concept selection only, nothing rendered
    python generate_scenery.py --concept "Faroe Islands"  # film a REQUESTED place (Telegram bot /scenery <place>)

The SCENERY_FORCED_CONCEPT env var is equivalent to --concept (used by CI so
the workflow never interpolates user text into a shell command).
"""
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

# Branch-specific LLM keys: the scenery branch has its own Gemini/Groq quota so
# a burst of scenery runs can never rate-limit the news pipeline (and vice
# versa). Must be mapped BEFORE importing main — query_llm_with_failover reads
# GEMINI_API_KEY / GROQ_API_KEY from the environment at call time.
for _base, _branch in (
    ("GEMINI_API_KEY", "GEMINI_API_KEY_SCENERY"),
    ("GROQ_API_KEY", "GROQ_API_KEY_SCENERY"),
):
    _val = os.environ.get(_branch, "").strip()
    if _val:
        os.environ[_base] = _val

from main import (  # noqa: E402
    PUBLIC_DIR,
    PEXELS_API_KEY,
    PIXABAY_API_KEY,
    HOOK_VIDEO_MAX_BYTES,
    POLLINATIONS_API_TOKEN,
    _derive_seed,
    get_available_cores,
    load_topic_history,
    post_to_telegram,
    query_llm_with_failover,
    record_topic_use,
    send_telegram_message,
)

SCENERY_HISTORY_FILE = os.path.join(PUBLIC_DIR, "processed_scenery_concepts.json")
CLIPS_DIRNAME = "scenery-clips"

SCENERY_MIN_SEC = int(os.environ.get("SCENERY_MIN_SEC", "12"))
SCENERY_MAX_SEC = int(os.environ.get("SCENERY_MAX_SEC", "18"))
SCENERY_TARGET_CLIPS = int(os.environ.get("SCENERY_TARGET_CLIPS", "7"))
SCENERY_MAX_AI_STILLS = int(os.environ.get("SCENERY_MAX_AI_STILLS", "2"))
# Below this many visuals the montage cannot sustain its cut cadence — abort
# loudly rather than ship a 3-clip "fast cut" that repeats itself. Same
# philosophy as the voiceover guard: never degrade silently.
SCENERY_MIN_VISUALS = 4

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) SceneryPipeline/1.0"

# Steers concept variety across runs (seed-picked suggestions, LLM may deviate).
SCENERY_DOMAINS = [
    "volcanic landscapes", "polar ice and glaciers", "desert dunes and rock",
    "ocean and coastline", "high mountains", "canyons and gorges",
    "aurora and night skies", "waterfalls", "caves and caverns",
    "ancient forests", "salt flats and mirror lakes", "geothermal springs",
    "river deltas from above", "bioluminescent phenomena", "terraced valleys",
]

# Calm, soothing beds only — Kevin MacLeod (incompetech.com), CC-BY 4.0.
# Scenery deliberately does NOT share the news pipeline's energetic
# SoundHelix tracks: these films are meant to feel peaceful, not punchy.
MUSIC_URLS = {
    "calm-piano": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%20Impromptu%2001.mp3",
    "floating-cities": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Floating%20Cities.mp3",
    "healing-ambient": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Healing.mp3",
    "dreamy-flashback": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dreamy%20Flashback.mp3",
}
MOOD_MUSIC = {
    "ethereal": "floating-cities",
    "epic": "healing-ambient",
    "serene": "calm-piano",
    "electric": "dreamy-flashback",
}

SCENERY_SYSTEM_PROMPT = """You are a location scout and film editor for ultra-short cinematic scenery films. You output ONLY one valid JSON object. NO markdown fences, NO explanation, NO comments.

Rules:
R1. Pick ONE real, named, visually breathtaking place or natural phenomenon on Earth. It must be concrete and nameable (e.g. "Dallol sulfur springs, Ethiopia") — NEVER a generic vibe like "beautiful mountains".
R2. NEVER invent people, quotes, or attributions. No person names anywhere in any field.
R3. "overlay_line": ONE short poetic line, max 38 characters, no quotation marks, no hashtags, no emoji, and NOT a repeat of place_name. A whispered thought, not ad copy.
R4. "search_queries": 6-9 SHORT stock-footage search phrases (2-4 words each) that find real footage of THIS place/phenomenon — different angles, times of day, close details. All must be genuinely different from each other.
R5. "ai_image_prompts": 0-2 richly detailed prompts for a surreal painterly vertical still of the same place. Empty list if pure realism suits it better.
R6. "mood": exactly one of "ethereal", "epic", "serene", "electric" — whichever fits the place.
R7. "caption": 1-2 factual sentences naming the place (no invented numbers), then 2-4 fitting hashtags.

Output JSON shape:
{"concept": "...", "place_name": "...", "overlay_line": "...", "search_queries": ["..."], "ai_image_prompts": ["..."], "mood": "...", "caption": "..."}"""


def _scenery_telegram_creds():
    """Scenery has its own bot + channel (TELEGRAM_*_SCENERY) so montages and
    their alerts stay out of the news archive; falls back to the main bot so
    nothing breaks before the new bot is configured."""
    bot_token = (os.environ.get("TELEGRAM_BOT_TOKEN_SCENERY", "").strip()
                 or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID_SCENERY", "").strip()
               or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
    return bot_token, chat_id


def _alert_telegram(text: str, session_id: str):
    """Best-effort Telegram note — must never raise."""
    try:
        bot_token, chat_id = _scenery_telegram_creds()
        if bot_token and chat_id:
            send_telegram_message(text, bot_token, chat_id, session_id)
    except Exception as tg_err:
        print(f"Could not send Telegram note: {tg_err}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", (s or "").lower()).strip()


def _query_similarity(a: str, b: str) -> float:
    """Token-set Jaccard — catches near-duplicate search queries ('bamboo
    forest misty dawn' vs 'bamboo forest misty morning') that exact-normalized
    dedup misses. Near-dupes hit the same stock results and waste searches."""
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _parse_json_object(raw: str) -> dict:
    # Delegate to main's coercer — the failover's JSON gate approves output
    # based on it (think-blocks, fences, unquoted keys, prose-wrapped JSON),
    # so this parser must recover everything the gate lets through.
    from main import _coerce_llm_json
    data = _coerce_llm_json(raw, quiet=True)
    if not isinstance(data, dict):
        raise ValueError(f"LLM returned no JSON object: {(raw or '')[:200]}")
    return data


def select_concept(session_id: str, seed: int, history: list, forced_place: str = "") -> dict:
    """Ask the LLM for one concrete scenery concept, deduped against history.

    forced_place: a user-requested place (Telegram /scenery <place>). The LLM
    still writes the queries/line/mood, but for THAT place — and history dedup
    is skipped: an explicit request may repeat an already-covered spot."""
    rng = random.Random(seed)
    recent = [h.get("title", "") for h in history if h.get("title")][-40:]
    recent_norms = set() if forced_place else {_norm(t) for t in recent}
    suggestions = rng.sample(SCENERY_DOMAINS, k=3)

    exclusion_note = ""
    for attempt in range(3):
        if forced_place:
            user_prompt = (
                "Scout one location for a 10-20 second vertical scenery film.\n"
                f'The user has REQUESTED this exact place: "{forced_place}". '
                "Film THIS place — do not substitute another location. "
                "Use its real, full name in concept and place_name.\n"
                + exclusion_note
                + "Return the JSON object now."
            )
        else:
            user_prompt = (
                "Scout one location for a 10-20 second vertical scenery film.\n"
                f"Domain inspiration (pick one of these or surprise us within nature/landscape): {', '.join(suggestions)}.\n"
                + (f"Already covered recently, do NOT pick any of these or close variants: {'; '.join(recent[-25:])}.\n" if recent else "")
                + exclusion_note
                + "Return the JSON object now."
            )
        raw = query_llm_with_failover(
            SCENERY_SYSTEM_PROMPT, user_prompt,
            max_tokens=1200, json_format=True, session_id=session_id,
        )
        try:
            data = _parse_json_object(raw)
        except ValueError as e:
            # A parse miss is a retryable attempt, not a run-fatal error.
            print(f"[{session_id}] WARN: concept attempt {attempt + 1} unparseable: {e}")
            exclusion_note = "Your previous answer was not valid JSON. Reply with ONLY the JSON object. "
            continue

        concept = str(data.get("concept", "")).strip()
        place = str(data.get("place_name", "")).strip() or concept
        if not concept:
            exclusion_note = "Your previous answer was missing 'concept'. "
            continue
        # Weak models sometimes echo the FORMAT into 'concept' ("Vertical
        # scenery film") while the real place sits only in place_name. A
        # concept sharing NO tokens with the named place is that failure —
        # record the place instead (place is the canonical dedup key). If
        # neither field names anything capitalized, retry (concreteness rule).
        if place and place != concept and _query_similarity(concept, place) == 0.0:
            print(f"[{session_id}] Concept '{concept}' looks like format echo — using place_name '{place}'.")
            concept = place
        if not re.search(r"\b[A-Z]", concept):
            exclusion_note = (
                "Your 'concept' was generic. It must NAME a real specific place "
                "(proper noun), e.g. 'Dallol sulfur springs, Ethiopia'. "
            )
            continue
        if _norm(concept) in recent_norms or _norm(place) in recent_norms:
            print(f"[{session_id}] Concept '{concept}' already covered — retrying with exclusion.")
            exclusion_note = f"You already suggested '{concept}' — it is USED, pick a different place. "
            continue

        # Overlay line hygiene: no quotes/hashtags (fabrication + spam guards),
        # hard length cap, and never a duplicate of the place label shown
        # beneath it (the redundant-copy rule).
        line = str(data.get("overlay_line", "")).strip().strip('"“”‘’\'')
        line = re.sub(r"#\S+", "", line).strip()[:48]
        if line and _norm(line) == _norm(place):
            place = ""  # keep the line, drop the duplicate small label

        queries = []
        for q in data.get("search_queries", []) or []:
            q = str(q).strip()
            if not q or len(q.split()) > 6:
                continue
            if any(_query_similarity(q, kept) > 0.7 for kept in queries):
                continue
            queries.append(q)
        if len(queries) < 4:
            exclusion_note = "You returned fewer than 4 distinct search_queries. "
            continue

        mood = str(data.get("mood", "")).strip().lower()
        if mood not in ("ethereal", "epic", "serene", "electric"):
            mood = "epic"

        ai_prompts = [str(p).strip() for p in (data.get("ai_image_prompts") or []) if str(p).strip()]
        caption = str(data.get("caption", "")).strip() or f"{concept}. #scenery #earth #cinematic"

        return {
            "concept": concept,
            "place_name": place,
            "overlay_line": line,
            "search_queries": queries[:9],
            "ai_image_prompts": ai_prompts[:SCENERY_MAX_AI_STILLS],
            "mood": mood,
            "caption": caption,
        }
    raise Exception("Concept selection failed: 3 attempts produced no usable, unused concept.")


def _download_video_capped(video_url: str, provider: str, session_id: str):
    """Chunked download with the same 40MB cap as the main pipeline's b-roll."""
    try:
        dl_req = urllib.request.Request(video_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(dl_req, timeout=45) as dl_resp:
            length = dl_resp.headers.get("Content-Length")
            if length and int(length) > HOOK_VIDEO_MAX_BYTES:
                print(f"[{session_id}] {provider} clip too large ({length} bytes), skipping")
                return None
            chunks, total = [], 0
            while True:
                chunk = dl_resp.read(1024 * 512)
                if not chunk:
                    break
                total += len(chunk)
                if total > HOOK_VIDEO_MAX_BYTES:
                    print(f"[{session_id}] {provider} clip exceeded cap mid-download, skipping")
                    return None
                chunks.append(chunk)
            content = b"".join(chunks)
            if len(content) < 50_000:
                return None
            return content
    except Exception as e:
        print(f"[{session_id}] {provider} clip download failed: {e}")
        return None


def _pexels_clip(query: str, used_ids: set, session_id: str, rng: random.Random):
    if not PEXELS_API_KEY:
        return None
    url = (
        "https://api.pexels.com/videos/search?query=" + urllib.parse.quote(query)
        + f"&per_page=10&page={rng.randint(1, 3)}&orientation=portrait&size=medium"
    )
    try:
        api_req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Authorization": PEXELS_API_KEY})
        with urllib.request.urlopen(api_req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        videos = data.get("videos", [])
        rng.shuffle(videos)
        for video in videos:
            duration = float(video.get("duration", 0))
            # 3s floor: montage segments run up to ~2.5s and the cut engine
            # trims into clips, so anything shorter would freeze-frame.
            if duration < 3 or duration > 120:
                continue
            vid_id = f"pexels-{video.get('id')}"
            if vid_id in used_ids:
                continue
            files = [
                f for f in video.get("video_files", [])
                if f.get("file_type") == "video/mp4" and f.get("link") and f.get("width") and f.get("height")
            ]
            files.sort(key=lambda f: abs(max(f["width"], f["height"]) - 1920))
            for vf in files[:2]:
                content = _download_video_capped(vf["link"], "Pexels", session_id)
                if content:
                    used_ids.add(vid_id)
                    return content, duration
    except Exception as e:
        print(f"[{session_id}] Pexels VIDEO API error for '{query}': {e}")
    return None


def _pixabay_clip(query: str, used_ids: set, session_id: str, rng: random.Random):
    if not PIXABAY_API_KEY:
        return None
    url = (
        f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}"
        + "&q=" + urllib.parse.quote(query) + "&per_page=20&safesearch=true"
    )
    try:
        api_req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(api_req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        hits = data.get("hits", [])
        rng.shuffle(hits)
        for hit in hits:
            duration = float(hit.get("duration", 0))
            if duration < 3:
                continue
            vid_id = f"pixabay-{hit.get('id')}"
            if vid_id in used_ids:
                continue
            sizes = hit.get("videos", {})
            for size_key in ("large", "medium", "small"):
                vf = sizes.get(size_key) or {}
                if vf.get("url"):
                    content = _download_video_capped(vf["url"], "Pixabay", session_id)
                    if content:
                        used_ids.add(vid_id)
                        return content, duration
    except Exception as e:
        print(f"[{session_id}] Pixabay VIDEO API error for '{query}': {e}")
    return None


def _pollinations_still(prompt: str, idx: int, session_id: str, seed: int):
    full_prompt = f"{prompt}, vertical composition, cinematic, no text, no watermark"
    url = (
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(full_prompt)
        + f"?width=1080&height=1920&nologo=true&seed={seed + idx}"
    )
    headers = {"User-Agent": USER_AGENT}
    if POLLINATIONS_API_TOKEN:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_TOKEN}"
    try:
        api_req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(api_req, timeout=60) as resp:
            content = resp.read(12 * 1024 * 1024)
        if len(content) < 30_000:
            return None
        if not (content[:3] == b"\xff\xd8\xff" or content[:8] == b"\x89PNG\r\n\x1a\n"):
            return None
        print(f"[{session_id}] ✓ Pollinations still OK ({len(content)} bytes)")
        return content
    except Exception as e:
        print(f"[{session_id}] Pollinations still failed: {e}")
        return None


def gather_visuals(concept: dict, session_id: str, seed: int) -> list:
    """Fetch stock clips + AI stills into public/scenery-clips/. Returns the
    clips list for the composition props (relative public/ paths)."""
    clips_dir = os.path.join(PUBLIC_DIR, CLIPS_DIRNAME)
    os.makedirs(clips_dir, exist_ok=True)
    rng = random.Random(seed ^ 0x7A3F)
    used_ids: set = set()
    clips = []

    queries = list(concept["search_queries"])
    rng.shuffle(queries)
    for query in queries:
        if len(clips) >= SCENERY_TARGET_CLIPS:
            break
        got = _pexels_clip(query, used_ids, session_id, rng) or _pixabay_clip(query, used_ids, session_id, rng)
        if not got:
            print(f"[{session_id}] No clip for '{query}'")
            continue
        content, duration = got
        filename = f"clip-{session_id}-{len(clips)}.mp4"
        with open(os.path.join(clips_dir, filename), "wb") as f:
            f.write(content)
        print(f"[{session_id}] ✓ clip {len(clips)}: '{query}' ({duration:.1f}s, {len(content)} bytes)")
        clips.append({"src": f"{CLIPS_DIRNAME}/{filename}", "kind": "video", "durationSec": duration})

    for idx, prompt in enumerate(concept.get("ai_image_prompts", [])[:SCENERY_MAX_AI_STILLS]):
        content = _pollinations_still(prompt, idx, session_id, seed)
        if content:
            ext = "png" if content[:4] == b"\x89PNG" else "jpg"
            filename = f"still-{session_id}-{idx}.{ext}"
            with open(os.path.join(clips_dir, filename), "wb") as f:
                f.write(content)
            clips.append({"src": f"{CLIPS_DIRNAME}/{filename}", "kind": "image"})

    return clips


def ensure_music(music_track: str, session_id: str):
    if music_track not in MUSIC_URLS:
        return
    local_music_path = os.path.join(PUBLIC_DIR, f"{music_track}.mp3")
    if os.path.exists(local_music_path):
        return
    print(f"[{session_id}] Downloading music track '{music_track}'...")
    urllib.request.urlretrieve(MUSIC_URLS[music_track], local_music_path)


def render_montage(props: dict, session_id: str) -> str:
    props_filepath = os.path.join(PUBLIC_DIR, f"props-{session_id}.json")
    with open(props_filepath, "w") as f:
        json.dump(props, f)

    video_filepath = os.path.join(PUBLIC_DIR, f"video-{session_id}.mp4")
    cores = get_available_cores()
    concurrency = cores if cores <= 3 else cores - 1
    remotion_cmd = [
        "npx", "remotion", "render",
        "ArtisticScenery",
        video_filepath,
        f"--props={props_filepath}",
        "--width=1080", "--height=1920",
        "--crf=18",
        "--codec=h264",
        "--overwrite",
        f"--concurrency={concurrency}",
    ]
    print(f"[{session_id}] Invoking Remotion: {' '.join(remotion_cmd)}")
    # Popen + merged line streaming (not run(capture_output=True)): Remotion is
    # chatty enough to fill an OS pipe buffer and deadlock a blocked reader.
    process = subprocess.Popen(
        remotion_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print(f"[{session_id}][Remotion] {line.strip()}")
    process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        raise Exception(f"Remotion render failed with exit code {return_code}")
    if not os.path.exists(video_filepath) or os.path.getsize(video_filepath) < 200_000:
        raise Exception("Render produced no usable video file — aborting before posting.")
    print(f"[{session_id}] ✓ Rendered {video_filepath} ({os.path.getsize(video_filepath)} bytes)")
    return video_filepath


def cleanup_session_assets(session_id: str):
    """Best-effort removal of this run's downloaded clips (runner disk hygiene)."""
    clips_dir = os.path.join(PUBLIC_DIR, CLIPS_DIRNAME)
    try:
        for name in os.listdir(clips_dir):
            if session_id in name:
                os.remove(os.path.join(clips_dir, name))
    except Exception:
        pass


def _cli_arg_value(flag: str) -> str:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1].strip()
    return ""


def main():
    dry_run = "--dry-run" in sys.argv
    forced_place = (_cli_arg_value("--concept")
                    or os.environ.get("SCENERY_FORCED_CONCEPT", "").strip())[:120]
    session_id = f"scenery-{str(uuid.uuid4())[:6]}"
    seed = _derive_seed(session_id)
    print(f"Starting Artistic Scenery generation ({session_id}, seed {seed})...")
    if forced_place:
        print(f"[{session_id}] User-requested place: '{forced_place}'")

    try:
        history = load_topic_history(SCENERY_HISTORY_FILE)
        print(f"Loaded scenery history: {len(history)} previous concepts.")

        concept = select_concept(session_id, seed, history, forced_place=forced_place)
        print(f"[{session_id}] Concept: '{concept['concept']}' | mood={concept['mood']} | "
              f"line='{concept['overlay_line']}' | {len(concept['search_queries'])} queries")

        if dry_run:
            print("\n[DRY-RUN] Concept that would be filmed:\n" + "-" * 50)
            print(json.dumps(concept, indent=2))
            print("-" * 50)
            return

        # Telegram pre-check BEFORE spending fetch/render compute — if the
        # delivery channel is down, the whole run is pointless (Telegram is the
        # only destination for this branch right now).
        bot_token, chat_id = _scenery_telegram_creds()
        if not bot_token or not chat_id:
            raise Exception("No Telegram credentials (TELEGRAM_*_SCENERY or TELEGRAM_*) — scenery branch is Telegram-only, nothing to deliver to.")
        start_note = f"🌄 Scenery render starting: {concept['concept']} ({concept['mood']})"
        if forced_place:
            start_note += f" — requested: '{forced_place}'"
        if not send_telegram_message(start_note, bot_token, chat_id, session_id):
            raise Exception("Telegram pre-check failed — aborting before fetch/render compute.")

        clips = gather_visuals(concept, session_id, seed)
        videos = sum(1 for c in clips if c["kind"] == "video")
        print(f"[{session_id}] Visuals gathered: {len(clips)} total ({videos} video, {len(clips) - videos} stills)")
        if len(clips) < SCENERY_MIN_VISUALS:
            raise Exception(
                f"Only {len(clips)} visuals fetched (need {SCENERY_MIN_VISUALS}+) — "
                "a fast-cut montage would visibly repeat itself; aborting loudly."
            )

        duration_sec = SCENERY_MIN_SEC + (seed % max(1, SCENERY_MAX_SEC - SCENERY_MIN_SEC + 1))
        music_track = MOOD_MUSIC.get(concept["mood"], "calm-piano")
        ensure_music(music_track, session_id)

        props = {
            "clips": clips,
            "overlayLine": concept["overlay_line"],
            "placeName": concept["place_name"],
            "musicTrack": music_track,
            "mood": concept["mood"],
            "durationInFrames": duration_sec * 30,
            "seed": seed,
        }
        video_path = render_montage(props, session_id)

        caption = concept["caption"][:1000]
        if not post_to_telegram(video_path, caption, bot_token, chat_id, session_id):
            raise Exception("Telegram video delivery failed — the render exists but nothing was posted.")

        # Record AFTER successful delivery only — a failed run never burns the
        # concept, so the next run can retry it: it never aired.
        try:
            record_topic_use(
                SCENERY_HISTORY_FILE,
                story_id=None,
                title=concept["concept"],
                subject=concept["place_name"],
                session_id=session_id,
            )
            print(f"Recorded concept in {SCENERY_HISTORY_FILE}.")
        except Exception as e:
            msg = f"⚠️ Scenery video posted OK but history save failed — next run may repeat this place: {e}"
            print(msg)
            _alert_telegram(msg, session_id)

        cleanup_session_assets(session_id)
        print("\n" + "=" * 50)
        print(f"🎉 SCENERY PIPELINE COMPLETED: {concept['concept']}")
        print("=" * 50 + "\n")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        _alert_telegram(
            f"❌ Scenery generation FAILED (no video was posted):\n{str(e)[:400]}",
            session_id,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
