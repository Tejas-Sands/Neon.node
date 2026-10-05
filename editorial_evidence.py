"""Small source excerpts for visible evidence, never fabricated UI captures."""
import re


def normalized(text):
    return " ".join(str(text or "").split())


def verified_excerpt(proposed, article):
    """Accept only a short complete sentence copied from the article.

    Sentence boundaries prevent turning 'X is not available' into 'available'
    or dropping a trailing condition. No paraphrasing, ellipses or truncation.
    Absence is normal: many articles have no useful sentence this short.
    """
    proposed = normalized(proposed)
    if (not 5 <= len(proposed.split()) <= 14 or len(proposed) > 150
            or not re.search(r'[.!?]$', proposed)):
        return ""
    # An abbreviation is not a safe sentence ending: "in the U.S. only on
    # paid plans" must never become "in the U.S.". Reject uncertain endings.
    if re.search(r'\b(?:[A-Za-z]\.){2,}$|\b(?:Mr|Mrs|Ms|Dr|Prof|Inc|Ltd|St|vs|etc)\.$', proposed, re.I):
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', normalized(article))
    return proposed if proposed in sentences else ""


def excerpt_matches(copy, excerpt):
    return bool(excerpt) and normalized(copy) == normalized(excerpt)
