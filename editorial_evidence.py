"""Small source excerpts for visible evidence, never fabricated UI captures."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse


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


def news_alert(topic, source_prompt, now=None):
    """Conservative source signal for a major, confirmed event within 72h.

    Feed age, viral score, generated copy and creative instructions cannot
    establish freshness. Require a dated event in the original article block.
    Undated and historical stories keep their normal opening.
    """
    now = now or datetime.now(timezone.utc)
    title = str((topic or {}).get('title') or '')
    url = urlparse(str((topic or {}).get('url') or ''))
    if url.scheme not in ('https', 'http') or not url.hostname or not title:
        return False
    marker = '- Main Content Text:\n'
    if marker not in source_prompt:
        return False
    article = source_prompt.split(marker, 1)[1]
    article = re.split(r'\n(?:EDITORIAL PLAN \(|PLATFORM:|SCENE OUTLINE)', article, maxsplit=1)[0]
    impact_patterns = (
        ('security', r'zero[- ]day|actively exploited|critical vulnerabilit\w*|data breach|massive recall'),
        ('disruption', r'global outage|nationwide outage|worldwide outage|emergency shutdown'),
        ('discovery', r'first[- ]ever|record[- ]breaking|world[- ]record'),
    )
    patterns = [(kind, re.compile(r'\b(?:' + p + r')\b', re.I)) for kind, p in impact_patterns]
    relevant = [(kind, p) for kind, p in patterns if p.search(title)]
    if not relevant:
        return False

    numeric_date = r'\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b'
    months = 'January February March April May June July August September October November December'.split()
    month_date = r'\b(' + '|'.join(months) + r')\s+(\d{1,2}),?\s+(20\d{2})\b'

    def dates(text):
        found = []
        for match in re.finditer(numeric_date, text):
            try:
                found.append(datetime(*(int(v) for v in match.groups()), tzinfo=timezone.utc))
            except ValueError:
                return None
        for match in re.finditer(month_date, text, re.I):
            try:
                month = next(i + 1 for i, name in enumerate(months) if name.lower() == match[1].lower())
                found.append(datetime(int(match[3]), month, int(match[2]), tzinfo=timezone.utc))
            except ValueError:
                return None
        return found

    def recent(date):
        return 0 <= (now - date).total_seconds() <= 72 * 3600

    url_dates = dates(url.path)
    if url_dates is None or any(not recent(d) for d in url_dates):
        return False
    # Impact keywords and reporting verbs are not the affected subject. Their
    # overlap cannot make a different product's incident support this headline.
    generic = set(('with from this that first ever news fixes fixed releases released '
                   'announces announced confirms confirmed warns warning critical '
                   'vulnerability vulnerabilities actively exploited zero data breach '
                   'massive recall global nationwide worldwide outage emergency shutdown '
                   'record breaking world scientists researchers discovery detects '
                   'detected discovers discovered reported published study report').split())
    subjects = set(re.findall(r'[a-z]{4,}', title.lower())) - generic
    for sentence in re.split(r'(?<=[.!?])\s+|\n+', article):
        matches = {kind for kind, p in relevant if p.search(sentence)}
        if (not matches
                or not subjects.intersection(re.findall(r'[a-z]{4,}', sentence.lower()))
                or re.search(r"\b(no|not|never|might|may|could|will|plans?|rumou?r|unconfirmed|ago)\b|n['’]t\b", sentence, re.I)):
            continue
        # Date the consequential action, not a publication about it. Only
        # the first reporting/event verb can establish the dated event;
        # later subordinate claims cannot borrow a reporter's current date.
        action = re.search(r'\b(released|announced|confirmed|detected|discovered|issued|began|started|observed|measured|published|reported|wrote|reviewed|described|revisited|said|recalled)\b', sentence, re.I)
        if not action or action[1].lower() in {
                'published', 'reported', 'wrote', 'reviewed', 'described', 'revisited', 'said', 'recalled'}:
            continue
        action_object = re.split(r'[,;]', sentence[action.end():], maxsplit=1)[0][:80]
        if re.search(r'\b(report|analysis|retrospective|review|recap|roundup|article|history)\b', action_object, re.I):
            continue  # Releasing an analysis still dates the analysis alone.
        # A current publication date does not date the underlying event.
        # Reject retrospective wording and bare historical years too.
        without_dates = re.sub(month_date, '', re.sub(numeric_date, '', sentence), flags=re.I)
        if (re.search(r'\b(retrospective|anniversary|previously|historical|originally)\b|\blast (?:year|month)\b', sentence, re.I)
                or any(int(year) != now.year for year in re.findall(r'\b((?:19|20)\d{2})\b', without_dates))):
            continue
        if matches == {'discovery'} and not (
                re.search(r'\b(observatory|astronom\w*|scient\w*|research\w*|physics|quantum|space|planet\w*|galax\w*|telescope|fusion|particle\w*|medical|clinical)\b', sentence, re.I)
                and re.search(r'\b(confirmed|detected|discovered|observed|measured)\b', sentence, re.I)):
            continue  # "First-ever" marketing is not a scientific discovery.
        event_dates = dates(sentence)
        if event_dates and all(recent(d) for d in event_dates):
            return True
        # Relative dates are usable only with an independently dated source
        # URL. A freshly republished feed item never supplies that evidence.
        if event_dates == [] and url_dates and re.search(r'\btoday\b', sentence, re.I):
            return True
    return False
