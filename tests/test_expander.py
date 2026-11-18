"""素材扩写模块回归测试。"""
import unittest

import engine
import expander


class ExpandTests(unittest.TestCase):
    SOURCE = "脆甜多汁，产地直发，果园现摘现发，果径80mm以上，坏果包赔。"

    def test_expands_short_material_into_full_copy(self):
        result = expander.expand("烟台红富士苹果", self.SOURCE)
        self.assertGreater(result["char_count"], 300)
        self.assertGreaterEqual(result["fullness"], 70)
        self.assertIn("脆甜多汁", result["text"])
        self.assertIn("坏果包赔", result["text"])

    def test_does_not_invent_missing_facts(self):
        result = expander.expand("烟台红富士苹果", self.SOURCE)
        self.assertNotIn("检测报告", result["text"])
        self.assertNotIn("有机认证", result["text"])
        self.assertIn("品质与检测", result["missing"])

    def test_short_source_stays_modest(self):
        result = expander.expand("苹果", "苹果，好吃。")
        self.assertNotIn("现摘", result["text"])
        self.assertNotIn("坏果包赔", result["text"])
        self.assertIn(result["fullness_level"], {"信息偏少", "较完整"})

    def test_origin_is_not_misread_as_freshness(self):
        facts = expander.extract_facts("果园现摘现发，果径80mm以上。")
        self.assertEqual(facts["origin"], [])
        self.assertTrue(facts["freshness"])

    def test_channel_and_audit(self):
        result = expander.expand("烟台红富士苹果", self.SOURCE, "pengyouquan", "生活分享", "精简")
        self.assertEqual(result["channel"], "pengyouquan")
        self.assertLessEqual(result["char_count"], 200)
        self.assertEqual(engine.audit(result["text"])["level"], "safe")


if __name__ == "__main__":
    unittest.main()
