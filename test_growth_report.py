"""Age, denominator and cohort integrity for the offline growth report."""
import copy
import unittest

from growth_report import build_report

NOW = 2_000_000_000


def entry(views=100, reach=80, **metrics):
    return {"ts": NOW - 5 * 86400, "topic": {"title": "Postgres release"},
            "platforms": {"instagram": {"posted_at": NOW - 5 * 86400}},
            "metrics": {"instagram": {"snap72": {
                "fetched_at": NOW - 2 * 86400, "views": views, "reach": reach,
                **metrics}}}}


class GrowthReportTests(unittest.TestCase):
    def test_rates_watch_units_and_zero_are_observations(self):
        ledger = {"entries": [entry(shares=2, saved=0, ig_reels_avg_watch_time=2500)]}
        before = copy.deepcopy(ledger)
        report = build_report(ledger, NOW)
        summary = report["overall"]
        self.assertEqual(summary["views"]["median"], 100)
        self.assertEqual(summary["watch_seconds"]["median"], 2.5)
        self.assertEqual(summary["shares_per_1000_reached"]["median"], 25)
        self.assertEqual(summary["saves_per_1000_reached"]["median"], 0)
        self.assertEqual(summary["snapshot_age_hours"]["median"], 72)
        self.assertEqual(ledger, before)
        self.assertEqual(summary["evidence"], "insufficient")

    def test_missing_is_unknown_and_low_exposure_does_not_vote_on_quality(self):
        report = build_report({"entries": [entry(), entry(views=1, reach=1,
            shares=1, saved=1, ig_reels_avg_watch_time=40000)]}, NOW)
        summary = report["overall"]
        self.assertEqual(summary["views"]["n"], 2)
        self.assertEqual(summary["watch_seconds"]["n"], 0)
        self.assertIsNone(summary["saves_per_1000_reached"]["median"])
        self.assertEqual(summary["low_exposure"], 1)

    def test_latest_deleted_backfilled_and_bad_age_are_excluded(self):
        latest = entry()
        latest["metrics"]["instagram"]["latest"] = latest["metrics"]["instagram"].pop("snap72")
        deleted, backfilled, early, late, future = [entry() for _ in range(5)]
        deleted["metrics"]["instagram"]["deleted"] = True
        backfilled["backfilled"] = True
        early["metrics"]["instagram"]["snap72"]["fetched_at"] = NOW - 4 * 86400
        late["platforms"]["instagram"]["posted_at"] = NOW - 12 * 86400
        future["metrics"]["instagram"]["snap72"]["fetched_at"] = NOW + 1
        report = build_report({"entries": [latest, deleted, backfilled, early, late, future, entry()]}, NOW)
        self.assertEqual(report["eligible_posts"], 5)
        self.assertEqual(report["overall"]["mature_snapshots"], 1)
        self.assertEqual(report["unmeasured_or_invalid_snapshot"], 4)

    def test_invalid_numbers_and_missing_age_are_not_zeroes(self):
        rows = [entry(views=float("nan"), reach=0, shares=5,
                      ig_reels_avg_watch_time=-4), entry(views=True, reach="bad")]
        missing = entry()
        missing["metrics"]["instagram"]["snap72"].pop("fetched_at")
        report = build_report({"entries": rows + [missing, None, {}]}, NOW)
        self.assertEqual(report["overall"]["views"]["n"], 0)
        self.assertEqual(report["overall"]["watch_seconds"]["n"], 0)
        self.assertEqual(report["overall"]["shares_per_1000_reached"]["n"], 0)

    def test_strategy_and_experiment_groups_do_not_pool_eras(self):
        old, new = entry(), entry()
        for row in (old, new):
            row["experiment"] = {"name": "runtime", "arm": "short"}
        new["growth"] = {"strategy": "builders-v1", "pillar": "build-with-it"}
        report = build_report({"entries": [old, new]}, NOW)
        self.assertEqual(len(report["cohorts"]), 2)
        self.assertEqual(len(report["experiments"]), 2)
        self.assertTrue(all(g["mature_snapshots"] == 1 for g in report["experiments"].values()))

    def test_view_sample_alone_cannot_establish_utility(self):
        report = build_report({"entries": [entry() for _ in range(20)]}, NOW)
        self.assertEqual(report["overall"]["evidence"], "insufficient")
        report = build_report({"entries": [entry(shares=0, saved=0,
                             ig_reels_avg_watch_time=1000) for _ in range(20)]}, NOW)
        self.assertEqual(report["overall"]["evidence"], "descriptive-only")
        self.assertEqual(report["overall"]["posts_with_utility"], 0)


if __name__ == "__main__":
    unittest.main()
