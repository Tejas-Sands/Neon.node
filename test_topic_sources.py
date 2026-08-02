#!/usr/bin/env python3
"""
Multi-Source Intake — Regression Tests (B4)
===========================================
Locks the NEWS_SOURCES intake machinery. Everything here is PURE-PARSER
testing — fetchers are thin requests wrappers around pure functions, so
these tests run on inline fixtures with zero network:

  1. _parse_rss handles RSS 2.0 (RFC-822 pubDate) and Atom (ISO + Z),
     computes REAL ages, gives every item a stable prefixed uid in the
     existing _hn_id field, honest engagement=0, and _source_prior =
     trust * 2.2. Malformed XML / itemless feeds → [].
  2. _lobsters_age_hours parses ISO offsets; garbage degrades to 24.0.
  3. _canonical_story_url strips www/query/fragment/trailing slash — HN
     and an outlet's RSS frequently link the identical article.
  4. _merge_and_corroborate: same-URL and same-title(Jaccard≥0.6) merge
     into ONE candidate carrying a sources list, the earliest real age,
     and a corroboration prior boost; distinct stories never merge; the
     engagement-bearing member is the representative.
  5. score_virality with _source_prior ABSENT is bit-identical to legacy;
     present, it adds exactly the prior.
  6. _gather_ci_candidates(["hn"]) equals the legacy candidate shape;
     unknown sources are skipped with count 0.

Usage:
  python test_topic_sources.py       # run all, exit 0/1
  python test_topic_sources.py -v
"""

import sys
import time

import main

VERBOSE = "-v" in sys.argv
FAILURES = []
NOW = time.time()


def check(name, cond, detail=""):
    if cond:
        if VERBOSE:
            print(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# --- 1. RSS 2.0 parsing ----------------------------------------------------------
print("[rss 2.0]")
import email.utils
recent = email.utils.formatdate(NOW - 5 * 3600)  # RFC-822, ~5h ago
RSS2 = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>The Verge</title>
<item><title>Google ships Gemini 3 to every Android phone</title>
<link>https://www.theverge.com/ai/12345/gemini-3-android?utm_source=rss</link>
<pubDate>{recent}</pubDate></item>
<item><title>No link item is skipped</title><pubDate>{recent}</pubDate></item>
<item><title></title><link>https://x.example/y</link></item>
</channel></rss>"""
items = main._parse_rss(RSS2, "rss:theverge")
check("one valid item parsed, junk skipped", len(items) == 1, f"got {len(items)}")
it = items[0] if items else {}
check("title carried", it.get("title", "").startswith("Google ships Gemini 3"))
check("real age from pubDate (~5h)", 4.0 < it.get("age_hours", 0) < 6.0,
      f"age={it.get('age_hours')}")
check("uid is prefixed sha in _hn_id",
      str(it.get("_hn_id", "")).startswith("rss:") and len(str(it.get("_hn_id"))) == 16,
      f"got {it.get('_hn_id')}")
check("honest zero engagement", it.get("engagement") == 0 and it.get("comments") == 0)
check("prior = trust * 2.2 for theverge",
      abs(it.get("_source_prior", 0) - 0.85 * 2.2) < 1e-6, f"got {it.get('_source_prior')}")

# --- 2. Atom parsing -------------------------------------------------------------
print("[atom]")
import datetime as _dt
iso_recent = _dt.datetime.fromtimestamp(NOW - 3 * 3600, _dt.timezone.utc).strftime(
    "%Y-%m-%dT%H:%M:%SZ")
ATOM = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Ars</title>
<entry><title>Intel cancels its 18A fab expansion</title>
<link rel="alternate" href="https://arstechnica.com/tech/intel-18a/"/>
<published>{iso_recent}</published></entry></feed>"""
items = main._parse_rss(ATOM, "rss:arstechnica")
check("atom entry parsed", len(items) == 1 and items[0]["title"].startswith("Intel"),
      f"got {items}")
check("atom Z timestamp → real age (~3h)",
      items and 2.0 < items[0]["age_hours"] < 4.0, f"age={items and items[0]['age_hours']}")
check("malformed XML returns []", main._parse_rss("<rss><channel>", "rss:x") == [])
check("itemless XML returns []", main._parse_rss("<rss><channel></channel></rss>", "rss:x") == [])

# --- 3. Lobsters age + canonical URL ---------------------------------------------
print("[lobsters age / canonical url]")
iso_off = _dt.datetime.fromtimestamp(NOW - 10 * 3600,
                                     _dt.timezone(_dt.timedelta(hours=-5))).isoformat()
check("lobsters ISO offset age (~10h)", 9.0 < main._lobsters_age_hours(iso_off) < 11.0,
      f"got {main._lobsters_age_hours(iso_off)}")
check("garbage created_at degrades to 24h", main._lobsters_age_hours("not-a-date") == 24.0)
check("empty created_at degrades to 24h", main._lobsters_age_hours("") == 24.0)

C = main._canonical_story_url
check("www + query + trailing slash stripped",
      C("https://www.theverge.com/ai/123/story/?utm=rss#top") == "theverge.com/ai/123/story",
      f"got {C('https://www.theverge.com/ai/123/story/?utm=rss#top')}")
check("same article, two dress-ups, one key",
      C("https://news.example.com/a/b") == C("http://www.news.example.com/a/b/"))
check("empty url safe", C("") == "")

# --- 4. Corroboration merge ------------------------------------------------------
print("[corroborate]")
hn_c = {"source": "hackernews", "title": "Gemini 3 ships to every Android phone",
        "subject": "", "url": "https://www.theverge.com/ai/12345/gemini-3-android",
        "engagement": 420, "comments": 200, "age_hours": 8.0, "meta": "front page",
        "_hn_id": "41000001"}
rss_c = {"source": "rss:theverge", "title": "Google ships Gemini 3 to every Android phone",
         "subject": "", "url": "https://www.theverge.com/ai/12345/gemini-3-android?utm_source=rss",
         "engagement": 0, "comments": 0, "age_hours": 5.0, "meta": "theverge",
         "_hn_id": "rss:aaaabbbbcccc", "_source_prior": 1.87}
other = {"source": "lobsters", "title": "Rust 2.0 roadmap published",
         "subject": "", "url": "https://blog.rust-lang.org/roadmap",
         "engagement": 40, "comments": 12, "age_hours": 6.0, "meta": "rust",
         "_hn_id": "lob:abc123"}
merged = main._merge_and_corroborate([hn_c, rss_c, other])
check("same-URL pair merges, distinct story survives", len(merged) == 2,
      f"got {len(merged)}")
rep = next((c for c in merged if "Gemini" in c.get("title", "")), {})
check("engagement-bearing member is the representative",
      rep.get("source") == "hackernews", f"rep source={rep.get('source')}")
check("sources list records both outlets",
      sorted(rep.get("sources", [])) == ["hackernews", "rss:theverge"],
      f"got {rep.get('sources')}")
check("corroboration boost +0.8 lands on the representative",
      abs(rep.get("_source_prior", 0) - 0.8) < 1e-6, f"got {rep.get('_source_prior')}")
check("earliest real age wins", rep.get("age_hours") == 5.0, f"got {rep.get('age_hours')}")

# Title-similarity merge (different URLs, same story reworded).
a = dict(hn_c, url="https://news.ycombinator.com/item?id=1", _hn_id="1")
b = dict(rss_c, url="https://www.theverge.com/other-path",
         title="Gemini 3 now ships to every Android phone")
merged = main._merge_and_corroborate([a, b])
check("title-Jaccard merge catches the reword", len(merged) == 1, f"got {len(merged)}")
merged = main._merge_and_corroborate([hn_c, other])
check("unrelated stories never merge", len(merged) == 2)

# --- 5. score_virality prior term ------------------------------------------------
print("[score prior]")
plain = {"title": "Some database release story", "engagement": 100, "comments": 20,
         "age_hours": 10.0, "meta": ""}
with_zero = dict(plain, _source_prior=0.0)
with_prior = dict(plain, _source_prior=1.87)
s0, sz, sp = (main.score_virality(plain), main.score_virality(with_zero),
              main.score_virality(with_prior))
check("absent field bit-identical to zero field", abs(s0 - sz) < 1e-12)
check("prior adds exactly itself", abs(sp - s0 - 1.87) < 1e-9, f"{sp} vs {s0}+1.87")

# --- 6. _gather_ci_candidates ----------------------------------------------------
print("[gather]")
FAKE_STORIES = [{"id": "41", "title": "A story about compilers and speed",
                 "url": "https://a.example/x", "score": 200, "author": "u",
                 "num_comments": 50, "created_at_i": int(NOW - 4 * 3600)}]
orig = main.get_hacker_news_frontpage
main.get_hacker_news_frontpage = lambda **kw: FAKE_STORIES
try:
    got, counts = main._gather_ci_candidates(["hn"])
    legacy = main._hn_to_candidates(FAKE_STORIES)
    # age_hours is time.time()-derived, so the two calls drift by microseconds
    # — compare it with tolerance and everything else exactly.
    same_shape = (
        len(got) == len(legacy)
        and all(
            {k: v for k, v in g.items() if k != "age_hours"}
            == {k: v for k, v in l.items() if k != "age_hours"}
            and abs(g["age_hours"] - l["age_hours"]) < 0.01
            for g, l in zip(got, legacy)
        )
    )
    check("hn-only equals legacy candidate shape", same_shape, f"got {got}")
    check("counts recorded", counts == {"hn": 1}, f"got {counts}")
    got, counts = main._gather_ci_candidates(["hn", "nosuchsource"])
    check("unknown source skipped with count 0",
          counts.get("nosuchsource") == 0 and len(got) == 1, f"counts={counts}")
finally:
    main.get_hacker_news_frontpage = orig

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s): " + "; ".join(FAILURES[:8]))
    sys.exit(1)
print("test_topic_sources.py: ALL PASS")
