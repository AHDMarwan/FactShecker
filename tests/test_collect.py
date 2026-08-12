import unittest

from scripts.collect import (
    build_index,
    claim_features,
    cluster_articles,
    fact_check_similarity,
    is_claim_candidate,
    match_fact_checks,
    normalize_text,
    score_cluster,
    stable_id,
    strip_publisher_suffix,
)


def article(article_id, title, source_name, weight=0.8, language="ar", category="test"):
    return {
        "id": article_id,
        "title": title,
        "raw_title": title,
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
            "category": category,
        },
    }


class CollectorTests(unittest.TestCase):
    def test_normalization_removes_punctuation_and_normalizes_case(self):
        self.assertEqual(normalize_text("Maroc: TEST!"), "maroc test")
        self.assertEqual(normalize_text("المغرب: خبرٌ"), "المغرب خبر")

    def test_strip_publisher_suffix(self):
        self.assertEqual(
            strip_publisher_suffix("المغرب يعلن برنامجا جديدا - Example News", "Example News"),
            "المغرب يعلن برنامجا جديدا",
        )
        self.assertEqual(
            strip_publisher_suffix("خبر اقتصادي جديد - example.com"),
            "خبر اقتصادي جديد",
        )

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

    def test_fact_checker_does_not_count_as_corroboration(self):
        cluster = [
            article("1", "خبر 2026", "Source A", 1.0, "ar"),
            article("2", "خبر 2026", "Source B", 0.9, "fr"),
            article("3", "خبر 2026", "AFP Fact Check", 0.95, "ar", "fact_checker"),
        ]
        _, status = score_cluster(cluster)
        self.assertEqual(status, "medium_evidence")

    def test_question_is_not_claim_candidate(self):
        self.assertFalse(is_claim_candidate("هل تم إلغاء الامتحان؟"))
        self.assertTrue(is_claim_candidate("أعلنت الوزارة إلغاء الامتحان في 2026"))

    def test_opinion_is_downranked(self):
        features = claim_features("رأي: لماذا يعتبر هذا القرار الأفضل للمغرب")
        self.assertFalse(features["candidate"])
        self.assertIn("opinion_or_analysis", features["reasons"])

    def test_quantified_report_is_check_worthy(self):
        features = claim_features("أكدت الوزارة ارتفاع الصادرات بنسبة 12% في 2026")
        self.assertTrue(features["candidate"])
        self.assertGreaterEqual(features["score"], 0.35)
        self.assertIn("numeric_detail", features["reasons"])

    def test_fact_check_similarity_rewards_overlap(self):
        close = fact_check_similarity(
            "المغرب يعلن إلغاء الامتحان الوطني 2026",
            "حقيقة إلغاء الامتحان الوطني 2026 في المغرب",
            same_language=True,
        )
        distant = fact_check_similarity(
            "المغرب يعلن إلغاء الامتحان الوطني 2026",
            "أسعار النفط ترتفع في الأسواق العالمية",
            same_language=True,
        )
        self.assertGreater(close, distant)

    def test_fact_check_matches_are_separate_from_news_clusters(self):
        news = article("1", "المغرب يعلن إلغاء الامتحان الوطني 2026", "Source A")
        fact_check = article(
            "fc1",
            "حقيقة إلغاء الامتحان الوطني 2026 في المغرب",
            "AFP Fact Check",
            0.95,
            "ar",
            "fact_checker",
        )
        matches = match_fact_checks([[news][0]], [fact_check])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source"]["category"], "fact_checker")

        index = build_index([news, fact_check])
        self.assertEqual(index["stats"]["articles"], 1)
        self.assertEqual(index["stats"]["fact_checks"], 1)
        self.assertEqual(len(index["items"]), 1)
        self.assertEqual(len(index["fact_checks"]), 1)
        self.assertGreaterEqual(len(index["items"][0]["fact_check_matches"]), 1)

    def test_index_notice_is_not_truth_probability(self):
        index = build_index([article("1", "خبر 2026", "Source A")])
        self.assertIn("not an automated truth verdict", index["notice"])
        self.assertEqual(index["stats"]["articles"], 1)


if __name__ == "__main__":
    unittest.main()
