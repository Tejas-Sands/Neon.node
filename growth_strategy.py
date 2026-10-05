"""Audience positioning for automated tech videos; no network or persistence.

Keyword signals are a transparent relevance proxy, never a factual verdict.
Keep topic freshness/dedup and factual grounding in their existing owners.
"""
import os
import re

STRATEGY = "everyday-v1"
AUDIENCE = "curious everyday people using technology and following science"

# Specific workflow language, deliberately excluding generic AI/company names.
# Order chooses the most useful series when a story matches several.
PILLARS = {
    "before-it-breaks": (
        "vulnerability", "vulnerabilities", "cve", "remote code execution",
        "supply chain attack", "dependency confusion", "outage", "postmortem",
        "data breach", "security patch", "prompt injection", "breaking change",
    ),
    "know-the-trade-off": (
        "benchmark", "benchmarks", "latency", "inference", "vram",
        "quantization", "gpu memory", "api pricing", "api cost", "cloud cost",
        "throughput", "token cost", "context window",
    ),
    "build-with-it": (
        "api", "sdk", "database", "postgres", "postgresql", "sqlite",
        "redis", "compiler", "rust compiler", "python", "javascript",
        "typescript", "node.js", "rubygems", "npm", "dependency",
        "dependencies", "docker", "kubernetes", "deployment", "debugger",
        "developer tool", "coding agent", "coding agents", "codebase",
        "codebases", "local model", "local models", "open weights",
        "claude code", "tailwind", "webassembly", "linux kernel",
        "open-weight", "open-weights", "llm locally", "model runs locally",
    ),
}
_SIGNALS = {
    pillar: [(term, re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I))
             for term in terms]
    for pillar, terms in PILLARS.items()
}
# These words describe consumer products, funding stories and general incidents
# too. Require technical context before treating them as an audience match.
_BROAD_SIGNALS = {"latency", "inference", "benchmark", "benchmarks", "throughput",
                  "vulnerability", "vulnerabilities", "outage", "data breach"}
_WORKFLOW_CONTEXT = re.compile(
    r"\b(?:llm|model|models|query|queries|compute|memory|network|protocol|"
    r"server|servers|build|builds|software|code|package|packages|pipeline|"
    r"training|runtime|runtimes|linux|cloudflare|aws|azure)\b", re.I)
_BUSINESS_ONLY = re.compile(r"\b(?:valuation|funding|fundrais\w*|raises?|round)\b", re.I)

# A broader audience still needs a recognizable subject. Company names or
# "AI" alone do not establish usefulness. The editor must confirm the stakes.
EVERYDAY_PILLARS = {
    "protect-yourself": (
        "scam", "scams", "phishing", "fraud", "privacy", "password", "passwords",
        "passkey", "passkeys", "data breach", "identity theft", "tracking",
        "deepfake", "deepfakes", "account recovery", "security update", "qr code",
        "scammers", "scammer",
    ),
    "daily-life": (
        "phone", "phones", "iphone", "android", "whatsapp", "gmail", "maps",
        "instagram", "youtube", "browser", "browsers", "battery", "batteries",
        "charging", "subscription", "subscriptions", "streaming", "wi-fi",
        "translation", "translate", "accessibility", "hearing", "photos",
        "chatgpt", "gemini app", "voice assistant", "ai assistant", "ai search",
    ),
    "world-explained": (
        "space", "moon", "mars", "asteroid", "asteroids", "telescope", "webb",
        "satellite", "satellites", "ocean", "oceans", "solar", "energy storage",
        "recycling", "plastic", "plastics", "water", "robot", "robots",
        "electric car", "electric cars", "electric vehicle", "electric vehicles",
        "heat wave", "heatwave", "earthquake", "discovery", "discovers",
        "galaxy", "galaxies", "rainbow", "rainbows", "spaceflight", "rover",
    ),
}
_EVERYDAY_SIGNALS = {
    pillar: [(term, re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I))
             for term in terms]
    for pillar, terms in EVERYDAY_PILLARS.items()
}
_PROMOTION = re.compile(r"\b(?:deals?|discounts?|coupon|sale|prime day|black friday|ads|advertisers|ad campaign)\b", re.I)


def active_strategy():
    return os.environ.get("GROWTH_STRATEGY", STRATEGY).strip().lower()


def enabled():
    # Unknown values disable rather than accidentally starting a new strategy.
    return active_strategy() in (STRATEGY, "builders-v1")


def classify_topic(text, strategy=None):
    """Infer a series from workflow terms; usable retrospectively when disabled."""
    text = str(text or "")
    if (strategy or active_strategy()) == STRATEGY:
        if _PROMOTION.search(text) or _BUSINESS_ONLY.search(text):
            return {"pillar": "unclassified", "signals": []}
        for pillar, patterns in _EVERYDAY_SIGNALS.items():
            matched = [term for term, pattern in patterns if pattern.search(text)]
            if matched:
                return {"pillar": pillar, "signals": matched}
        return {"pillar": "unclassified", "signals": []}
    workflow = any(pattern.search(text) for _, pattern in _SIGNALS["build-with-it"])
    context = workflow or bool(_WORKFLOW_CONTEXT.search(text))
    for pillar, patterns in _SIGNALS.items():
        matched = [term for term, pattern in patterns if pattern.search(text)
                   and (term not in _BROAD_SIGNALS or
                        (context and (workflow or not _BUSINESS_ONLY.search(text))))]
        if matched:
            return {"pillar": pillar, "signals": matched}
    return {"pillar": "unclassified", "signals": []}


def prefer_audience_candidates(candidates):
    """Prefer matching ELIGIBLE candidates without reviving used/stale ones."""
    if not enabled() or not candidates:
        return candidates
    matched = [c for c in candidates
               if classify_topic(c.get("title", ""))["signals"]]
    if matched:
        print(f"[Growth] {len(matched)}/{len(candidates)} eligible topics match {active_strategy()}.")
        return matched
    print("[Growth] No audience signal in eligible titles; keeping the existing pool. "
          "Do not invent an audience connection.")
    return candidates


def audience_directive():
    if not enabled():
        return ""
    if active_strategy() == STRATEGY:
        return """
AUDIENCE CONTRACT (everyday-v1; editorial guidance, NOT source evidence):
Write for a curious person who uses a phone, apps and the internet, without assuming coding knowledge.
Our promise: one surprising change, visible evidence, and what it means in everyday life.
Choose ONE lane: protect-yourself (scams/privacy/account safety), daily-life (apps, devices, practical AI, subscriptions), or world-explained (science, space, energy, the physical world).
SELECTION: prefer a named change or documented phenomenon with a specific human stake: time, access, privacy, convenience, or a surprising mechanism someone can explain to a friend. A lab result must stay a lab result; do not pretend it is available to buy. Explain a discovery honestly when there is no immediate personal effect.
Avoid discount roundups, funding gossip, personality disputes, vague AI predictions and specialist implementation details without a demonstrated everyday consequence. Never manufacture a personal threat or savings claim to broaden a niche story.
Keep the article's publication date distinct from the event date. A newly published explanation of an old photograph or discovery is not a new event; do not add "just happened" or "breaking" without evidence.
HOOK: show the consequence or puzzle in at most 12 spoken words, title at most 4 and screen text at most 8. Name the subject on screen. First three spoken words should carry the interesting part. Plain language; explain any necessary jargon immediately.
PROOF: the FIRST body scene must deliver a source-backed detail that answers part of the hook. Prefer a short literal source excerpt, a supported before/after comparison, or a real number with its units and conditions. Use the existing split, comparison or metric types. Preserve quiz/ranking withheld answers. Do not delay all useful information until the ending.
VISUALS: choose images of the actual everyday subject (phone, appliance, telescope, water, battery), not generic code or server racks. Stock images supply context, never evidence of a named event. A recreated interface must say ILLUSTRATION. Never claim an animation is a recording, independent test, or real product demonstration.
PAYOFF: close the exact opening question with one useful implication or source-supported action and its important limit. Explain who it applies to, including device, region or rollout restrictions when given. Attribute vendor claims. No invented numbers, urgency, quotes, certainty or firsthand experience.
One optional content-specific action after value. No keyword-comment bait, generic follow plea or repeated headline. Keep format/runtime/scene limits and factual guards.
"""
    return """
AUDIENCE CONTRACT (builders-v1; editorial guidance, NOT source evidence):
Write for developers and hands-on AI builders choosing tools and understanding failures.
Choose ONE affected workflow and source-backed consequence: a capability, cost/performance trade-off, or reliability/security change.
HOOK: use a grounded shock stat, broken assumption, or stakes reveal. First three spoken words carry the consequence or contradiction; do not start with the product name. Name the subject elsewhere in scene 0. Put a specific workflow cue (such as API, dependency, database, or local model) in its narration OR on-screen label when the source supports it. Keep the existing hook word limits.
PROOF: the next scene delivers a useful verified detail; then explain the mechanism. Preserve quiz/ranking withheld-answer rules. Stock footage and simulated UI are illustrations, not proof of real product behavior.
PAYOFF: close the exact opening promise with who benefits or is affected and under which conditions. Include a source-backed limitation or test condition when supplied. Distinguish vendor-reported results from independent measurements; never claim we tested something we did not test.
Never invent numbers, urgency, affected users, firsthand experience, or a developer connection. An unmatched story must keep its actual scope. The existing verified source facts remain the only factual authority.
One content-specific action at most, after the payoff; no follow request before value, no keyword-comment bait, no generic AI panic. Keep the existing format, runtime and scene count constraints.
"""


def growth_metadata(topic):
    if not enabled():
        return {}
    strategy = active_strategy()
    return {"strategy": strategy, "audience": AUDIENCE if strategy == STRATEGY else "developers and hands-on AI builders",
            "classification": "title-keyword-proxy",
            **classify_topic(topic.get("title", ""))}
