"""Offline audience strategy and production-path regression tests."""
import copy
import inspect
import os
import random
import time
import unittest
from unittest.mock import patch

import main
import growth_strategy as growth


class GrowthStrategyTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GROWTH_STRATEGY": "builders-v1",
                                          "TOPIC_PICK_MODE": "argmax"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_workflow_signals_not_generic_ai_or_company_names(self):
        for title, pillar in (
            ("PostgreSQL 18 query planner release", "build-with-it"),
            ("Local inference memory benchmark", "know-the-trade-off"),
            ("RubyGems caching vulnerability executes code", "before-it-breaks"),
            ("LLM benchmark measures coding agents", "know-the-trade-off"),
        ):
            self.assertEqual(growth.classify_topic(title)["pillar"], pillar)
        for title in ("OpenAI CEO controversy", "Apple phone colors leaked",
                      "Everyone should slow down AI", "Fastmail banner artwork",
                      "The rust-colored snake is back", "Siri can use Claude"):
            self.assertEqual(growth.classify_topic(title)["pillar"], "unclassified", title)

    def test_preference_is_read_only_and_falls_back(self):
        rows = [{"title": "OpenAI CEO controversy"},
                {"title": "Postgres query planner release"}]
        before = copy.deepcopy(rows)
        self.assertEqual(growth.prefer_audience_candidates(rows), [rows[1]])
        self.assertEqual(rows, before)
        self.assertEqual(growth.prefer_audience_candidates(rows[:1]), rows[:1])
        self.assertEqual(growth.prefer_audience_candidates([]), [])
        with patch.dict(os.environ, {"GROWTH_STRATEGY": "off"}):
            self.assertEqual(growth.prefer_audience_candidates(rows), rows)
            self.assertEqual(growth.audience_directive(), "")
            self.assertEqual(growth.growth_metadata(rows[1]), {})

    def test_production_selector_prefers_fit_after_dedup(self):
        rows = [dict(title="OpenAI CEO controversy", engagement=2000, comments=900,
                     age_hours=2, _hn_id="a"),
                dict(title="Postgres query planner release", engagement=100,
                     comments=20, age_hours=2, _hn_id="b")]
        with patch.object(main, "get_feedback_stats", return_value=None):
            chosen, repeated = main.filter_and_pick_story(copy.deepcopy(rows), [], random.Random(1))
            self.assertEqual(chosen["_hn_id"], "b")
            self.assertFalse(repeated)
            chosen, repeated = main.filter_and_pick_story(
                copy.deepcopy(rows), [{"id": "b"}], random.Random(1))
            self.assertEqual(chosen["_hn_id"], "a")
            self.assertFalse(repeated)
            with patch.dict(os.environ, {"GROWTH_STRATEGY": "off"}):
                chosen, _ = main.filter_and_pick_story(copy.deepcopy(rows), [], random.Random(1))
                self.assertEqual(chosen["_hn_id"], "a")

    def test_brief_reaches_news_tech_and_editorial_judge(self):
        directive = growth.audience_directive()
        self.assertIn("AUDIENCE CONTRACT", directive)
        self.assertIn("Never invent", directive)
        with patch.object(main, "get_feedback_stats", return_value=None):
            self.assertIn(directive, main.build_hn_news_prompt("Postgres", "release", seed=1))
        self.assertIn(directive, main.build_viral_topic_prompt({"subject": "Postgres"}))
        with patch.object(main, "query_llm_with_failover", return_value='{"subject":""}') as llm:
            main.plan_story_angle("Postgres release", "query planner details")
            self.assertIn(directive, llm.call_args.kwargs["user_prompt"])

    def test_render_wiring_covers_pack_prompts_without_touching_manual(self):
        src = inspect.getsource(main._execute_render_unlocked)
        self.assertIn('audience_directive() if is_auto_channel else ""', src)
        self.assertIn('growth_metadata(ledger_topic) if is_auto_channel else {}', src)
        self.assertNotIn('"growth"', inspect.getsource(main.compute_feedback_stats))

    def test_metadata_records_proxy_and_revision(self):
        meta = growth.growth_metadata({"title": "Postgres query planner release"})
        self.assertEqual(meta["strategy"], "builders-v1")
        self.assertEqual(meta["pillar"], "build-with-it")
        self.assertTrue(meta["signals"])

    def test_strategy_is_on_by_default_and_unknown_values_disable(self):
        with patch.dict(os.environ):
            os.environ.pop("GROWTH_STRATEGY", None)
            self.assertTrue(growth.audience_directive())
        with patch.dict(os.environ, {"GROWTH_STRATEGY": "typo"}):
            self.assertEqual(growth.audience_directive(), "")

    def test_audience_cannot_resurrect_stale_or_cooled_candidates(self):
        rows = [dict(title="Postgres query planner release", engagement=100,
                     comments=20, age_hours=60, _hn_id="a"),
                dict(title="A new computer ships today", engagement=50,
                     comments=10, age_hours=2, _hn_id="b")]
        with patch.object(main, "get_feedback_stats", return_value=None):
            with patch.dict(os.environ, {"TOPIC_MAX_AGE_H": "36"}):
                chosen, repeated = main.filter_and_pick_story(copy.deepcopy(rows), [], random.Random(1))
                self.assertEqual(chosen["_hn_id"], "b")
                self.assertFalse(repeated)
            rows[0]["age_hours"] = 2
            history = [{"title": "Postgres update", "entities": ["postgresql"],
                        "ts": time.time() - 3600}]
            with patch.dict(os.environ, {"TOPIC_ENTITY_COOLDOWN_H": "48",
                                        "TOPIC_COOLDOWN_OVERRIDE_SCORE": "99"}):
                chosen, repeated = main.filter_and_pick_story(copy.deepcopy(rows), history, random.Random(1))
                self.assertEqual(chosen["_hn_id"], "b")
                self.assertFalse(repeated)


if __name__ == "__main__":
    unittest.main()
