import unittest

from scripts.collect import (
    build_index,
    cluster_articles,
    is_claim_candidate,
    normalize_text,
    score_cluster,
    stable_id,
)


def article(article_id, title, source_name, weight=0.8, language="ar"):
    return {
        "id": article_id,
        "title": title,
        "normalized_title": normalize_text(title),
        "url": f"https://example.com/{article_id}",
        "published_at": "2026-08-12T20:00:00Z",
        "language": language,
        "channel": "test",
        "source": {
            "name": source_name,
            "url": "https://example.com",
            "domain": "example.com",
            "weight": weight,
            "category": "test",
        },
    }


class CollectorTests(unittest.TestCase):
    def test_normalization_removes_punctuation_and_normalizes_case(self):
        self.assertEqual(normalize_text("Maroc: TEST!"), "maroc test")
        self.assertEqual(normalize_text("المغرب: خبرٌ"), "المغرب خبر")

    def test_stable_id_is_deterministic(self):
        self.assertEqual(stable_id("a", "b"), stable_id("a", "b"))
        self.assertNotEqual(stable_id("a", "b"), stable_id("a", "c"))

    def test_identical_headlines_cluster_together(self):
        items = [
            article("1", "المغرب يعلن عن برنامج جديد", "Source A"),
            article("2", "المغرب يعلن عن برنامج جديد", "Source B"),
        ]
        clusters = cluster_articles(items)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 2)

    def test_single_source_requires_review(self):
        score, status = score_cluster([article("1", "خبر 2026", "Source A")])
        self.assertEqual(status, "needs_review")
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)

    def test_three_sources_can_be_corroborated(self):
        cluster = [
            article("1", "خبر 2026", "Source A", 1.0, "ar"),
            article("2", "خبر 2026", "Source B", 0.9, "fr"),
            article("3", "خبر 2026", "Source C", 0.8, "en"),
        ]
        score, status = score_cluster(cluster)
        self.assertEqual(status, "corroborated")
        self.assertGreaterEqual(score, 0.70)

    def test_question_is_not_claim_candidate(self):
        self.assertFalse(is_claim_candidate("هل تم إلغاء الامتحان؟"))
        self.assertTrue(is_claim_candidate("تم إلغاء الامتحان في 2026"))

    def test_index_notice_is_not_truth_probability(self):
        index = build_index([article("1", "خبر 2026", "Source A")])
        self.assertIn("not an automated truth verdict", index["notice"])
        self.assertEqual(index["stats"]["articles"], 1)


if __name__ == "__main__":
    unittest.main()
