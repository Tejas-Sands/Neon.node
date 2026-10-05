"""Audience positioning for automated tech videos; no network or persistence.

Keyword signals are a transparent relevance proxy, never a factual verdict.
Keep topic freshness/dedup and factual grounding in their existing owners.
"""
import os
import re

STRATEGY = "builders-v1"
AUDIENCE = "developers and hands-on AI builders"

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


def enabled():
    # Unknown values disable rather than accidentally starting a new strategy.
    return os.environ.get("GROWTH_STRATEGY", STRATEGY).strip().lower() == STRATEGY


def classify_topic(text):
    """Infer a series from workflow terms; usable retrospectively when disabled."""
    text = str(text or "")
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
        print(f"[Growth] {len(matched)}/{len(candidates)} eligible topics carry builder workflow signals.")
        return matched
    print("[Growth] No audience signal in eligible titles; keeping the existing pool. "
          "Do not invent an audience connection.")
    return candidates


def audience_directive():
    if not enabled():
        return ""
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
    return {"strategy": STRATEGY, "audience": AUDIENCE,
            "classification": "title-keyword-proxy",
            **classify_topic(topic.get("title", ""))}
