"""P1 回归测试：合规漏词、风险重复加权、品类/否定/单字误判。"""
import unittest

import content_gaps
import engine


class AuditTests(unittest.TestCase):
    def test_new_claim_words_are_detected(self):
        for word in ["纯天然", "无副作用", "零添加", "美白", "修复"]:
            with self.subTest(word=word):
                self.assertNotEqual(engine.audit(word)["level"], "safe")

    def test_repeated_high_risk_word_raises_score(self):
        once = engine.audit("最佳")["risk_score"]
        three_times = engine.audit("最佳最佳最佳")["risk_score"]
        self.assertGreater(three_times, once)

    def test_clean_copy_is_safe(self):
        result = engine.audit("烟台红富士苹果，脆甜多汁，产地直发。")
        self.assertEqual(result["level"], "safe")
        self.assertEqual(result["score"], 95)

    def test_annotated_html_is_escaped(self):
        result = engine.audit("A&B 最佳")
        self.assertIn("&amp;", result["annotated"])
        self.assertIn("risk-mark", result["annotated"])


class ContentGapTests(unittest.TestCase):
    def test_iphone_is_not_agriculture(self):
        self.assertEqual(content_gaps.detect_category("苹果手机"), "数码")

    def test_apple_is_agriculture(self):
        self.assertEqual(content_gaps.detect_category("烟台红富士苹果"), "农产品")

    def test_negated_keywords_do_not_count_as_covered(self):
        result = content_gaps.analyze(
            "烟台红富士苹果",
            "不是产地直发，也没有坏果包赔。",
            category="农产品",
        )
        covered = {item["key"] for item in result["covered"]}
        self.assertNotIn("origin", covered)
        self.assertNotIn("after_sales", covered)

    def test_single_char_taste_is_not_false_positive(self):
        result = content_gaps.analyze("测试产品", "香港香薰", category="农产品")
        covered = {item["key"] for item in result["covered"]}
        self.assertNotIn("taste", covered)

    def test_source_facts_are_flagged_as_available(self):
        result = content_gaps.analyze(
            "烟台红富士苹果",
            "脆甜多汁，产地直发。",
            category="农产品",
            source="果园现摘现发，坏果包赔。",
        )
        available = {item["key"]: item["available"] for item in result["recommended"]}
        self.assertTrue(available.get("freshness"))
        self.assertTrue(available.get("after_sales"))


class DirectionLibraryTests(unittest.TestCase):
    def test_library_is_expanded(self):
        self.assertGreaterEqual(len(content_gaps.DIRECTIONS), 25)

    def test_every_category_key_exists(self):
        for category, entries in content_gaps.CATEGORY_DIRECTIONS.items():
            with self.subTest(category=category):
                for key, _ in entries:
                    self.assertIn(key, content_gaps.DIRECTIONS)

    def test_new_directions_appear_in_recommendations(self):
        result = content_gaps.analyze(
            "烟台红富士苹果",
            "烟台风土，脆甜多汁，红富士品种。",
        )
        names = {item["name"] for item in result["recommended"]}
        self.assertTrue(names & {"口碑与复购", "时令与节日", "营养与健康"})

    def test_templates_have_variants(self):
        self.assertGreaterEqual(len(content_gaps.TEMPLATE_VARIANTS["taste"]), 2)
        self.assertGreaterEqual(len(content_gaps.TEMPLATE_VARIANTS["reviews"]), 2)


if __name__ == "__main__":
    unittest.main()
