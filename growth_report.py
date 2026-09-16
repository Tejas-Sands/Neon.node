"""Read-only growth review from the saved ledger; no app import or API calls."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import statistics

from growth_strategy import classify_topic

MIN_EXPOSURE = 20
MIN_OBSERVATIONS = 20


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _dict(value):
    return value if isinstance(value, dict) else {}


def _metric(values):
    return {"n": len(values), "median": statistics.median(values) if values else None}


def _summarize(rows):
    views, watch, shares, saves, ages = [], [], [], [], []
    low_exposure = utility = 0
    for row in rows:
        snap = row["snapshot"]
        v, reach = _number(snap.get("views")), _number(snap.get("reach"))
        if v is not None:
            views.append(v)
        ages.append(row["age_hours"])
        if v is None or v < MIN_EXPOSURE:
            low_exposure += 1
            continue
        awt = _number(snap.get("ig_reels_avg_watch_time"))
        if awt is not None:
            watch.append(awt / 1000)
        if reach is None or reach < MIN_EXPOSURE:
            continue
        sh, sv = _number(snap.get("shares")), _number(snap.get("saved"))
        if sh is not None:
            shares.append(1000 * sh / reach)
        if sv is not None:
            saves.append(1000 * sv / reach)
        if (sh or 0) > 0 or (sv or 0) > 0:
            utility += 1
    enough = min(len(views), len(watch), len(shares), len(saves)) >= MIN_OBSERVATIONS
    return {"mature_snapshots": len(rows), "views": _metric(views),
            "watch_seconds": _metric(watch),
            "shares_per_1000_reached": _metric(shares),
            "saves_per_1000_reached": _metric(saves),
            "snapshot_age_hours": _metric(ages),
            "low_exposure": low_exposure, "posts_with_utility": utility,
            "evidence": "descriptive-only" if enough else "insufficient"}


def build_report(ledger, now, days=30):
    """Compare only snapshots actually collected 48h–7d after publication.

    No latest fallback: otherwise older lifetime metrics masquerade as snap72.
    Rows remain grouped by strategy/format/experiment to expose confounding.
    """
    if days < 0:
        raise ValueError("days must be non-negative")
    entries = ledger if isinstance(ledger, list) else _dict(ledger).get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("ledger entries must be a list")
    rows, eligible = [], 0
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("backfilled"):
            continue
        metrics = _dict(_dict(entry.get("metrics")).get("instagram"))
        if metrics.get("deleted"):
            continue
        platform = _dict(_dict(entry.get("platforms")).get("instagram"))
        posted = _number(platform.get("posted_at"))
        if posted is None:
            posted = _number(entry.get("ts"))
        if posted is None or posted > now or (days and posted < now - days * 86400):
            continue
        # Don't count YouTube-only rows as missing Instagram observations.
        if not platform and not metrics:
            continue
        eligible += 1
        snap = _dict(metrics.get("snap72"))
        fetched = _number(snap.get("fetched_at"))
        if fetched is None or fetched > now or not 48 * 3600 <= fetched - posted <= 7 * 86400:
            continue
        growth = _dict(entry.get("growth"))
        topic = _dict(entry.get("topic"))
        pillar = growth.get("pillar") or classify_topic(topic.get("title", ""))["pillar"]
        strategy = growth.get("strategy") or "historical-untagged"
        rows.append({"snapshot": snap, "age_hours": (fetched - posted) / 3600,
                     "cohort": str(strategy) + " / " + str(pillar),
                     "strategy": str(strategy),
                     "format": str(entry.get("format_pack") or "legacy-news"),
                     "experiment": _dict(entry.get("experiment"))})

    cohorts, experiments = {}, {}
    for row in rows:
        cohorts.setdefault(row["cohort"], []).append(row)
        exp = row["experiment"]
        if exp.get("name") and exp.get("arm"):
            key = " / ".join((row["strategy"], str(exp["name"]), str(exp["arm"]), row["format"]))
            experiments.setdefault(key, []).append(row)
    return {"as_of": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
            "days": days, "ledger_entries": len(entries), "eligible_posts": eligible,
            "unmeasured_or_invalid_snapshot": eligible - len(rows),
            "overall": _summarize(rows),
            "cohorts": {k: _summarize(v) for k, v in sorted(cohorts.items())},
            "experiments": {k: _summarize(v) for k, v in sorted(experiments.items())},
            "limits": [
                "Local saved ledger, not a live account audit; missing metrics are unknown.",
                "48h–7d collection window is approximate age matching, not exactly 72h.",
                "Historical series use retrospective title keywords, not audience demographics.",
                "Shares are not DM sends; average watch time is not completion rate.",
                "No per-post follows, profile conversion, 3-second retention or audience identity measured.",
                "20 observations per metric is a review floor, not significance or a winner.",
                "Era comparisons are observational; format/topic/timing may confound results.",
            ]}


def format_report(report):
    def value(metric):
        n, median = metric["n"], metric["median"]
        return f"{median:.2f} (n={n})" if median is not None else "unknown (n=0)"

    lines = ["# Audience growth review", "",
             f"As of {report['as_of']}; window: {report['days'] or 'all retained'} days.",
             f"Ledger entries: {report['ledger_entries']}; eligible posts: {report['eligible_posts']}; "
             f"missing/invalid mature snapshots: {report['unmeasured_or_invalid_snapshot']}.", "",
             "All metric cells are per-post medians with their own sample counts.", "",
             "| Cohort | Snapshots | Views | Watch seconds | Shares/1k reached | Saves/1k reached | Evidence |",
             "| --- | ---: | --- | --- | --- | --- | --- |"]
    groups = [("Overall", report["overall"])] + list(report["cohorts"].items())
    groups += [("Experiment: " + key, val) for key, val in report["experiments"].items()]
    for label, group in groups:
        cells = [value(group[k]) for k in ("views", "watch_seconds", "shares_per_1000_reached",
                                         "saves_per_1000_reached")]
        lines.append(f"| {label.replace('|', '/')} | {group['mature_snapshots']} | "
                     + " | ".join(cells) + f" | {group['evidence']} |")
    overall = report["overall"]
    lines += ["", f"Median snapshot age: {value(overall['snapshot_age_hours'])} hours.",
              f"Below view floor or missing views: {overall['low_exposure']}; "
              f"posts with observed saves/shares above exposure floors: {overall['posts_with_utility']}.", ""]
    lines += ["- " + limit for limit in report["limits"]]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=Path(__file__).parent / "public/post_ledger.json")
    parser.add_argument("--days", type=int, default=30, help="0 = entire retained ledger")
    parser.add_argument("--as-of", help="ISO-8601 timestamp with timezone")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        now = dt.datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else dt.datetime.now(dt.timezone.utc)
        if now.tzinfo is None:
            raise ValueError("--as-of must include a timezone")
        with args.ledger.open() as handle:
            ledger = json.load(handle)
        if not isinstance(ledger, (dict, list)) or (isinstance(ledger, dict) and "entries" not in ledger):
            raise ValueError("expected a ledger object with entries, or an entries list")
        report = build_report(ledger, now.timestamp(), args.days)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, allow_nan=False) if args.json else format_report(report))


if __name__ == "__main__":
    main()
