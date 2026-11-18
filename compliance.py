"""兼容旧接口的合规检查。

原来的 `check_compliance(text)` 返回 `(score, risks)`，被旧版 app.py 使用。
新版页面直接调用 `engine.audit()`，这里保留旧函数，内部复用完整词库。
"""
from __future__ import annotations

from engine import audit, sanitize

RISK_WORDS = {
    "治疗": "医疗功效宣称违规（普通食品/化妆品不得宣称治疗作用）",
    "根治": "绝对化用语违规",
    "第一": "绝对化用语违规",
    "最好": "绝对化用语违规",
    "纯天然": "可能涉及虚假宣传，需提供证明",
    "无副作用": "绝对化安全承诺违规",
}


def check_compliance(text: str) -> tuple[int, list[str]]:
    """返回 (合规分, 风险说明列表)。

    说明：AI 生成标识是平台合规要求，不属于广告法词库；
    新版页面会在 AI 生成结果上自动追加「（AI生成）」，
    因此这里保留旧版提示，方便外部脚本继续使用。
    """
    result = audit(text)
    risks = [
        f"检测到违规词「{item['word']}」：{item['category']}，{item['suggest']}"
        for item in result["violations"]
    ]
    score = result["score"]
    if "AI生成" not in text and "人工智能生成" not in text:
        risks.append("缺少AI生成标识（依据《深度合成标识要求》）")
        score = max(0, score - 10)
    return score, risks


def rewrite_compliant(text: str) -> tuple[str, list[tuple[str, str]]]:
    """兼容旧版的本地合规改写，返回 (改写后文案, 替换明细)。"""
    return sanitize(text)
