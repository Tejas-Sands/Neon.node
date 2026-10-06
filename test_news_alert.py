"""A news graphic must not manufacture urgency from a feed timestamp or hype."""
from datetime import datetime, timezone
import unittest
import editorial_evidence as evidence


class NewsAlertTests(unittest.TestCase):
    def alert(self, title, article, url='https://example.org/2026/10/06/security', now=None, **meta):
        # Production source block; downstream creative instructions are NOT evidence.
        prompt = f'NEWS SOURCE DETAILS:\n- Headline/Title: {title}\n- Main Content Text:\n{article}\n\nPLATFORM: Vertical 9:16\nShow breaking news!'
        return getattr(evidence, 'news_alert', lambda *args, **kwargs: False)(
            dict(title=title, url=url, **meta), prompt,
            now=now or datetime(2026, 10, 6, 12, tzinfo=timezone.utc))

    def test_confirmed_current_high_impact_event_qualifies(self):
        self.assertTrue(self.alert('Browser fixes actively exploited zero-day',
            'On October 6, 2026, Browser released a fix for an actively exploited zero-day.'))
        self.assertTrue(self.alert('Observatory detects first-ever signal',
            'On 2026-10-05, the Observatory confirmed the first-ever signal detection.'))

    def test_historical_republished_future_and_undated_events_do_not_break(self):
        for article, url in [
            ('On September 3, 2026, Browser released a fix for an actively exploited zero-day.', 'https://example.org/2026/10/06/republished'),
            ('On October 8, 2026, Browser will release a fix for an actively exploited zero-day.', 'https://example.org/2026/10/06/preview'),
            ('Browser released a fix for an actively exploited zero-day.', 'https://example.org/story'),
            ('Today Browser released a fix for an actively exploited zero-day.', 'https://example.org/2026/09/03/security'),
        ]:
            with self.subTest(article=article):
                self.assertFalse(self.alert('Browser fixes actively exploited zero-day', article, url, created_at_i=1791288000))

    def test_routine_hype_and_unconfirmed_claims_do_not_qualify(self):
        self.assertFalse(self.alert('This update is crazy', 'On October 6, 2026, Browser released three new colors.'))
        self.assertFalse(self.alert('Browser zero-day warning', 'On October 6, 2026, Browser confirmed the issue is not actively exploited.'))
        self.assertFalse(self.alert('Browser fixes actively exploited zero-day', 'On October 6, 2026, Browser might release a zero-day fix.'))
        self.assertFalse(self.alert('Browser fixes actively exploited zero-day', '', url=''))
        self.assertFalse(self.alert('Browser fixes actively exploited zero-day',
            'On October 6, 2026, Browser released a zero-day fix.', url='file:///tmp/source'))

    def test_a_new_report_about_an_old_event_is_not_a_new_event(self):
        for article in (
            'On October 6, 2026, Browser published a retrospective about the actively exploited zero-day it fixed in 2021.',
            'On October 6, 2026, Browser published a retrospective about its actively exploited zero-day.',
            'On October 6, 2026, Browser confirmed the anniversary of its zero-day discovery.',
            'On October 6, 2026, Browser published an analysis of the actively exploited zero-day it fixed last summer.',
            'On October 6, 2026, Browser reported how it fixed an actively exploited zero-day earlier in the year.',
            'On October 6, 2026, Browser released an analysis of the actively exploited zero-day it fixed last summer.',
        ):
            with self.subTest(article=article):
                self.assertFalse(self.alert('Browser fixes actively exploited zero-day', article))

    def test_a_recent_event_can_cross_new_year(self):
        self.assertTrue(self.alert('Browser fixes actively exploited zero-day',
            'On December 31, 2026, Browser released a fix for an actively exploited zero-day.',
            url='https://example.org/2026/12/31/security',
            now=datetime(2027, 1, 1, 12, tzinfo=timezone.utc)))

    def test_first_ever_marketing_and_a_different_subject_are_not_evidence(self):
        self.assertFalse(self.alert('Browser releases first-ever pink phone case',
            'On October 6, 2026, Browser released its first-ever pink phone case.'))
        self.assertFalse(self.alert('Browser fixes critical vulnerability',
            'On October 6, 2026, Library confirmed a critical vulnerability.'))


if __name__ == '__main__':
    unittest.main()
