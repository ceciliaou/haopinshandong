"""好品山东 · GEO合规智能传播工作台（Streamlit 页面）。

保留原来的「输入产品信息 → 生成 → 合规检查 → 传播预判」主流程，
把本地规则引擎、合规预审、传播评分与作品说明装进同一页面。
"""
from __future__ import annotations

import html
import os
import re
import textwrap
from pathlib import Path

import streamlit as st

import content
import content_gaps
import engine
import expander

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="好品山东 · GEO合规智能传播工作台",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

MODEL_NAME = "deepseek-ai/DeepSeek-V3.2"
BASE_URL = "https://api.siliconflow.cn/v1"
PLATFORM_KEYS = list(engine.PLATFORMS.keys())
GEN_PLATFORM_KEYS = PLATFORM_KEYS + ["all"]
PLATFORM_LABELS = {key: f'{engine.PLATFORMS[key]["icon"]} {engine.PLATFORMS[key]["name"]}' for key in PLATFORM_KEYS}
PLATFORM_LABELS["all"] = "🌐 全部渠道"


def _load_env() -> None:
    """读取 .env / .evn，不覆盖已经存在的环境变量，也不打印密钥。"""
    for filename in (".env", ".evn"):
        path = Path(__file__).with_name(filename)
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()
API_KEY = os.getenv("SILICONFLOW_API_KEY", "").strip()


# ---------------------------------------------------------------------------
# 视觉样式
# ---------------------------------------------------------------------------

CSS = """
<style>
:root {
  --ink:#102a43; --muted:#627d98; --brand:#0b3d5c; --brand-2:#0f766e;
  --gold:#d69e2e; --bg:#f5f7fa; --card:#ffffff; --line:#dbe4ee;
}
.stApp { background:
  radial-gradient(1200px 500px at 10% -10%, #e8f1f8 0%, transparent 55%),
  radial-gradient(900px 500px at 100% 0%, #eef8f4 0%, transparent 45%),
  var(--bg);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppDeployButton"], .stDeployButton { display: none !important; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1280px; }

/* 侧边栏 */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0a2a43 0%, #0d3b55 55%, #0b4a54 100%);
  border-right: 1px solid rgba(255,255,255,.06);
}
[data-testid="stSidebar"] * { color: #e6f1f8; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #ffffff; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {
  color: #102a43 !important; background: #f8fbfd !important; border-radius: 10px !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] * { color: #102a43 !important; }
[data-testid="stSidebar"] [data-testid="stAlert"] *,
[data-testid="stSidebar"] .stAlert * { color: #102a43 !important; }
[data-testid="stSidebar"] [data-testid="stAlert"] svg,
[data-testid="stSidebar"] .stAlert svg { color: #0f766e !important; }
[data-testid="stSidebar"] [data-testid="stAlert"] a,
[data-testid="stSidebar"] .stAlert a { color: #0f766e !important; }
[data-testid="stSidebar"] .stButton > button {
  background: linear-gradient(135deg, #f0b64a, #d69e2e); color: #14213d; border: 0;
  font-weight: 800; border-radius: 12px; padding: .65rem 1rem;
}
[data-testid="stSidebar"] .stButton > button:hover { filter: brightness(1.04); }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.14); }
.side-brand { display:flex; align-items:center; gap:10px; margin: 4px 0 2px; }
.side-mark {
  width: 38px; height: 38px; border-radius: 11px; display:grid; place-items:center;
  background: linear-gradient(135deg, #f6d58b, #d69e2e); color:#0b2b45; font-weight:900; font-size:18px;
}
.side-title { font-size: 18px; font-weight: 800; letter-spacing:.02em; color:#fff; }
.side-sub { font-size: 11px; color: rgba(230,241,248,.65); letter-spacing:.14em; }
.side-label {
  font-size: 11px; font-weight: 800; letter-spacing:.14em; color:#f6d58b;
  margin: 16px 0 6px;
}
.engine-chip {
  display:flex; align-items:center; gap:8px; padding:10px 12px; border-radius:12px;
  background: rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.12);
  font-size:12px; line-height:1.5; color:#dcecf5; margin-top: 10px;
}
.dot { width:8px; height:8px; border-radius:50%; background:#54d38a; box-shadow:0 0 0 4px rgba(84,211,138,.15); flex:none; }
.dot.off { background:#f6ad55; box-shadow:0 0 0 4px rgba(246,173,85,.15); }

/* 首屏 */
.hero {
  position: relative; overflow: hidden; border-radius: 22px; padding: 36px 40px 30px;
  background:
    radial-gradient(600px 260px at 88% 10%, rgba(246,213,139,.18), transparent 60%),
    linear-gradient(120deg, #09263d 0%, #0b3d5c 48%, #0f766e 100%);
  color: #fff; box-shadow: 0 24px 50px rgba(9,38,61,.18); margin-bottom: 18px;
}
.hero:after {
  content:""; position:absolute; right:-70px; bottom:-110px; width:300px; height:300px;
  border-radius:50%; border:1px solid rgba(255,255,255,.12);
}
.hero-kicker { font-size: 11px; letter-spacing:.24em; color:#f6d58b; font-weight:800; }
.hero h1 { font-size: 34px; line-height:1.2; margin: 10px 0 8px; color:#fff; font-weight: 900; }
.hero h1 span { color:#f6d58b; }
.hero p { color: rgba(255,255,255,.78); font-size: 14px; margin: 0; }
.hero-badges { display:flex; flex-wrap:wrap; gap:8px; margin-top: 18px; }
.hero-badge {
  padding: 5px 11px; border-radius: 999px; font-size: 12px; color:#eaf6ff;
  border:1px solid rgba(255,255,255,.18); background: rgba(255,255,255,.08);
}

/* 通用卡片 */
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: 16px;
  padding: 18px 20px; box-shadow: 0 8px 24px rgba(16,42,67,.05);
}
.card h3 { margin: 0 0 6px; font-size: 16px; color: var(--ink); }
.card p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.75; }
.section-kicker {
  font-size: 11px; font-weight: 800; letter-spacing:.16em; color: var(--brand-2);
  margin: 6px 0 10px;
}
.section-title { font-size: 20px; font-weight: 800; color: var(--ink); margin: 0 0 6px; }
.section-desc { color: var(--muted); font-size: 13px; margin: 0 0 14px; }
.stat-grid { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; margin: 12px 0 18px; }
.stat {
  background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px 16px;
}
.stat .label { font-size:11px; color:var(--muted); letter-spacing:.08em; font-weight:700; }
.stat .value { font-size:26px; font-weight:900; color:var(--ink); line-height:1.2; margin-top:2px; }
.stat .hint { font-size:11px; color:var(--muted); }

/* 文案卡 */
.copy-card {
  background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px 20px;
  box-shadow: 0 8px 22px rgba(16,42,67,.05); margin-bottom: 10px;
}
.copy-top { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
.copy-index {
  font-size:11px; font-weight:900; color:#fff; background:var(--brand);
  padding:2px 8px; border-radius:6px; letter-spacing:.08em;
}
.pill { font-size:11px; font-weight:800; padding:3px 9px; border-radius:999px; }
.copy-meta { margin-left:auto; font-size:11px; color:var(--muted); }
.copy-text { color:var(--ink); font-size:14px; line-height:1.9; white-space:pre-wrap; }

/* 风险 */
.risk-mark { padding:1px 4px; border-radius:4px; font-weight:700; }
.risk-high { background:#fdecec; color:#c53030; }
.risk-mid { background:#fff1e6; color:#c05621; }
.risk-low { background:#fff8e6; color:#b7791f; }
.annotated {
  background:#fbfcfe; border:1px solid var(--line); border-radius:14px; padding:16px 18px;
  font-size:14px; line-height:2.1; color:var(--ink); white-space:pre-wrap;
}
.risk-item {
  display:flex; gap:10px; align-items:flex-start; padding:12px 14px; border:1px solid var(--line);
  border-radius:12px; background:#fff; margin-bottom:8px;
}
.risk-item .tag { font-size:11px; font-weight:800; padding:2px 8px; border-radius:6px; flex:none; }
.risk-item .body { font-size:13px; color:var(--ink); line-height:1.65; }
.risk-item .body small { color:var(--muted); }

/* 关键词 / 徽章 */
.keyword-row { display:flex; flex-wrap:wrap; gap:7px; margin: 4px 0 14px; }
.keyword-chip {
  padding:4px 11px; border-radius:999px; background:#eef6f4; color:#0f766e;
  border:1px solid #cfe9e2; font-size:12px; font-weight:700;
}
.tag-chip {
  padding:4px 10px; border-radius:999px; background:#f3f0e6; color:#8a6a1f;
  border:1px solid #eadfc0; font-size:11.5px; font-weight:700;
}

/* 内容缺口 / 方向补全 */
.gap-summary { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:10px; margin:14px 0 8px; }
.gap-summary > div { background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px 14px; }
.gap-summary b { display:block; font-size:22px; color:var(--ink); line-height:1.25; }
.gap-summary span { font-size:11px; color:var(--muted); }
.gap-row-head { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:6px; }
.gap-row-note { margin-left:auto; font-size:11px; color:var(--muted); }
.gap-covered-label { font-size:11px; font-weight:700; color:var(--muted); margin-right:2px; }
.expand-title { font-size:21px; font-weight:900; color:var(--ink); line-height:1.45; margin:8px 0 4px; }
@media (max-width: 900px) {
  .gap-summary { grid-template-columns:repeat(2, minmax(0,1fr)); }
  .gap-row-note { margin-left:0; }
}
.gap-card {
  background:#fff; border:1px solid var(--line); border-radius:14px; padding:16px 18px;
  margin-bottom:10px; box-shadow:0 6px 18px rgba(16,42,67,.04);
}
.gap-head { display:flex; align-items:center; gap:9px; flex-wrap:wrap; margin-bottom:6px; }
.gap-name { font-size:15px; font-weight:800; color:var(--ink); }
.gap-stage { margin-left:auto; font-size:11px; color:var(--muted); }
.gap-priority { font-size:11px; font-weight:800; padding:2px 8px; border-radius:999px; }
.gap-priority.high { background:#fdecec; color:#c53030; }
.gap-priority.mid { background:#fff8e6; color:#b7791f; }
.gap-priority.low { background:#eef6f4; color:#0f766e; }
.gap-priority.ready { background:#e9f8ef; color:#0f7b45; }
.gap-why { font-size:12.5px; color:var(--muted); line-height:1.7; margin:0 0 8px; }
.gap-angle { font-size:12.5px; color:var(--ink); line-height:1.7; margin-bottom:7px; }
.gap-template {
  background:#fbfcfe; border:1px dashed #cfe0ec; border-radius:10px;
  padding:9px 11px; font-size:12.5px; color:#334e68; line-height:1.7;
}
.gap-source { margin-top:8px; padding:6px 9px; border-radius:8px; font-size:12px; line-height:1.6; }
.gap-source.ready { background:#f0fbf5; color:#0f6b43; }
.gap-source.missing { background:#fffaf0; color:#8a6a1f; }
.gap-outline {
  background: linear-gradient(135deg, #0b3d5c, #0f4d63);
  color:#eaf6ff; border-radius:16px; padding:18px 22px; margin-top:6px;
}
.gap-outline .section-kicker { color:#f6d58b; }
.gap-outline p { margin:4px 0; font-size:13px; line-height:1.8; color:#eaf6ff; }
.gap-outline b { color:#fff; }

/* 时间线 */
.timeline { border-left:2px solid #cfe0ec; margin-left:6px; padding-left:18px; }
.timeline-item { position:relative; margin-bottom:16px; }
.timeline-item:before {
  content:""; position:absolute; left:-25px; top:6px; width:10px; height:10px; border-radius:50%;
  background:#0f766e; box-shadow:0 0 0 4px #e3f3ee;
}
.timeline-stage { font-size:11px; font-weight:800; letter-spacing:.12em; color:#0f766e; }
.timeline-title { font-size:14px; font-weight:800; color:var(--ink); margin:2px 0; }
.timeline-summary { font-size:12.5px; color:var(--muted); line-height:1.7; }

/* 页签 / 按钮 / 输入 */
/* 页签：胶囊式切换，当前项高对比填充（兼容新旧 Streamlit 结构） */
.stTabs [data-baseweb="tab-list"],
.stTabs [role="tablist"] {
  gap: 6px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 6px;
  width: fit-content;
  max-width: 100%;
  box-shadow: 0 8px 22px rgba(16,42,67,.06);
  margin-bottom: 10px;
  overflow-x: auto;
}
.stTabs [data-baseweb="tab"],
.stTabs [data-testid="stTab"] {
  height: auto;
  min-height: 42px;
  padding: 9px 18px !important;
  border-radius: 10px !important;
  color: #486581 !important;
  font-weight: 700;
  border: 1px solid transparent;
  background: transparent;
  transition: background .15s, color .15s, box-shadow .15s;
}
.stTabs [data-testid="stTab"] p {
  margin: 0 !important;
  color: inherit !important;
  font-weight: 700 !important;
}
.stTabs [data-baseweb="tab"]:hover,
.stTabs [data-testid="stTab"]:hover {
  background: #eef4f8 !important;
  color: var(--brand) !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"],
.stTabs [data-testid="stTab"][aria-selected="true"] {
  background: linear-gradient(135deg, #0b3d5c, #0f766e) !important;
  color: #ffffff !important;
  border-color: transparent !important;
  box-shadow: 0 8px 18px rgba(11,61,92,.20);
}
.stTabs [data-testid="stTab"][aria-selected="true"] p { color: #ffffff !important; }
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"],
.stTabs .react-aria-SelectionIndicator { display: none !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 6px; }
.stButton > button { border-radius: 10px; border:1px solid var(--line); font-weight: 700; }
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #0b3d5c, #0f766e); border: 0; color:#fff;
  padding: .55rem 1.1rem;
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.06); }
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] { border-radius: 10px; }
div[data-testid="stMetric"] {
  background:#fff; border:1px solid var(--line); border-radius:14px; padding:12px 14px;
}
.quote {
  border-left: 4px solid var(--gold); background:#fffaf0; padding:16px 20px; border-radius:0 12px 12px 0;
  color:#5b4a1f; font-size:14px; line-height:1.9;
}
.footer-note { color:var(--muted); font-size:11px; text-align:center; margin-top: 26px; }

@media (max-width: 900px) {
  .hero { padding: 26px 22px 22px; }
  .hero h1 { font-size: 26px; }
  .stat-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def block(markup: str) -> None:
    st.markdown(textwrap.dedent(markup).strip(), unsafe_allow_html=True)


def level_pill(result: dict) -> str:
    meta = engine.LEVEL_META[result["level"]]
    return f'<span class="pill" style="color:{meta["color"]};background:{meta["bg"]}">{meta["label"]} · 合规分 {result["score"]}</span>'


def stat(label: str, value: str, hint: str = "") -> str:
    return f'<div class="stat"><div class="label">{html.escape(label)}</div><div class="value">{html.escape(str(value))}</div><div class="hint">{html.escape(hint)}</div></div>'


def suggest_gap_fill(item: dict, source: str) -> str:
    """从产品资料里找一条包含证据关键词的短句，作为补全输入框的默认值。"""
    if not item.get("available"):
        return ""
    for clause in re.split(r"[，,；;。！？\n]", source or ""):
        clause = clause.strip()
        if clause and any(word in clause for word in item.get("evidence", [])):
            return clause
    return ""


def sync_gap_source() -> None:
    """按钮回调：在 gap_source 组件实例化前同步侧边栏资料。"""
    st.session_state["gap_source"] = st.session_state["features"]
    st.session_state["gap_sync_flash"] = "已同步侧边栏产品资料，建议重新扫描内容缺口。"


def parse_ai_copies(raw: str, count: int = 3) -> list[str]:
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^\s*(?:\d+[.、)]|[-*•])\s*", "", line)
        line = line.strip("「」\"' ")
        if len(line) >= 8:
            lines.append(line)
    if len(lines) < count:
        for paragraph in re.split(r"\n{2,}", raw):
            paragraph = re.sub(r"^\s*(?:\d+[.、)]|[-*•])\s*", "", paragraph.strip())
            if len(paragraph) >= 8 and paragraph not in lines:
                lines.append(paragraph)
    return lines[:count]


def ai_generate(product: str, features: str, platform: str, count: int = 3) -> list[str]:
    from openai import OpenAI

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    platform_name = engine.PLATFORMS[platform]["name"]
    prompt = (
        f"你是山东农产品营销文案专家。请为以下产品写 {count} 条{platform_name}文案，每条不超过 80 字。\n"
        f"产品：{product}\n特点：{features}\n"
        "要求：语言自然、有画面感，突出产地与可举证的品质信息；遵守广告法，"
        "不使用绝对化用语、医疗功效词、投资收益承诺；不要编造检测数据。"
        f"只输出 {count} 条文案，每条一行，不要编号和解释。"
    )
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=700,
        timeout=45,
    )
    raw = (response.choices[0].message.content or "").strip()
    copies = parse_ai_copies(raw, count)
    return [copy + ("" if "AI生成" in copy else "（AI生成）") for copy in copies]


def build_generation(product: str, features: str, platform: str, use_ai: bool) -> dict:
    # 全部渠道：每个渠道各生成 1 条，共 4 条
    if platform == "all":
        channels = list(engine.PLATFORMS.keys())
        items = []
        warnings = []
        ai_success = 0
        for channel in channels:
            channel_copies: list[str] = []
            if use_ai and API_KEY:
                try:
                    channel_copies = ai_generate(product, features, channel, count=1)
                    if channel_copies:
                        ai_success += 1
                except Exception as exc:  # 单个渠道失败不影响其他渠道
                    warnings.append(
                        f"{engine.PLATFORMS[channel]['name']} AI 生成失败，已回退本地：{type(exc).__name__}"
                    )
            if not channel_copies:
                channel_copies = engine.generate_local(product, features, channel, count=1)
            text = channel_copies[0]
            items.append({"text": text, "audit": engine.audit(text), "platform": channel})
        mode = "AI 增强" if ai_success == len(channels) else ("混合模式" if ai_success else "本地规则引擎")
        return {
            "product": product,
            "features": features,
            "platform": "all",
            "mode": mode,
            "items": items,
            "warning": "；".join(warnings),
        }

    mode = "AI 增强"
    warning = ""
    copies: list[str] = []
    if use_ai and API_KEY:
        try:
            copies = ai_generate(product, features, platform)
        except Exception as exc:  # 网络/额度/模型异常时回退本地
            warning = f"AI 生成失败，已回退本地规则引擎：{type(exc).__name__}"
    if not copies:
        mode = "本地规则引擎"
        copies = engine.generate_local(product, features, platform)
    if len(copies) < 3:
        copies = (copies + engine.generate_local(product, features, platform))[:3]

    items = []
    for text in copies[:3]:
        items.append({"text": text, "audit": engine.audit(text), "platform": platform})
    return {"product": product, "features": features, "platform": platform, "mode": mode, "items": items, "warning": warning}


def render_copy_card(index: int, item: dict, platform: str) -> None:
    result = item["audit"]
    item_platform = item.get("platform", platform)
    block(
        f"""
        <div class="copy-card">
          <div class="copy-top">
            <span class="copy-index">0{index}</span>
            {level_pill(result)}
            <span class="copy-meta">{len(item["text"])} 字 · {engine.PLATFORMS[item_platform]["name"]}</span>
          </div>
          <div class="copy-text">{html.escape(item["text"]).replace(chr(10), "<br>")}</div>
        </div>
        """
    )
    if result["violations"]:
        with st.expander(f"查看 {len(result['violations'])} 条风险提示"):
            for violation in result["violations"]:
                st.markdown(
                    f"- **{violation['word']}**（{engine.SEVERITY_LABEL[violation['severity']]}，"
                    f"{violation['category']}）：{violation['suggest']}"
                )


def render_risk_result(result: dict) -> None:
    block(
        f"""
        <div class="stat-grid">
          {stat("合规分", f"{result['score']}/100", "越高越合规")}
          {stat("风险等级", result["level_label"], f"风险分 {result['risk_score']}")}
          {stat("命中词", result["total"], f"{len(result['violations'])} 类")}
          {stat("高危 / 中危", f"{result['counts']['high']} / {result['counts']['mid']}", f"低危 {result['counts']['low']}")}
        </div>
        """
    )
    block(f'<div class="section-kicker">原文标注</div><div class="annotated">{result["annotated"].replace(chr(10), "<br>")}</div>')
    if result["violations"]:
        st.markdown("##### 逐条修改建议")
        for violation in result["violations"]:
            color = engine.LEVEL_META[{"high": "high", "mid": "mid", "low": "low"}[violation["severity"]]]["color"]
            block(
                f"""
                <div class="risk-item">
                  <span class="tag" style="color:{color};background:{engine.LEVEL_META[violation['severity']]['bg']}">
                    {engine.SEVERITY_LABEL[violation['severity']]}
                  </span>
                  <div class="body">
                    <strong>{html.escape(violation['word'])}</strong>
                    <small>· {html.escape(violation['category'])} · 出现 {violation['count']} 次</small><br>
                    {html.escape(violation['suggest'])}
                  </div>
                </div>
                """
            )
    else:
        st.success("未检测到明显违规词，可以继续优化表达。")


# ---------------------------------------------------------------------------
# 侧边栏
# ---------------------------------------------------------------------------

for key, value in {
    "product": "烟台红富士苹果",
    "features": "脆甜多汁，产地直发，果园现摘现发，果径 80mm 以上，坏果包赔。",
    "platform": "xiaohongshu",
    "gen": None,
    "audit_result": None,
    "gap_result": None,
}.items():
    st.session_state.setdefault(key, value)

with st.sidebar:
    block(
        """
        <div class="side-brand">
          <div class="side-mark">鲁</div>
          <div>
            <div class="side-title">好品山东</div>
            <div class="side-sub">GEO COMPLIANCE STUDIO</div>
          </div>
        </div>
        """
    )
    st.markdown('<div class="side-label">产品信息</div>', unsafe_allow_html=True)
    product = st.text_input("产品名称", key="product")
    features = st.text_area("产品特点", key="features", height=120)
    platform = st.selectbox(
        "传播渠道",
        GEN_PLATFORM_KEYS,
        format_func=lambda key: PLATFORM_LABELS[key],
        key="platform",
    )

    st.markdown('<div class="side-label">生成模式</div>', unsafe_allow_html=True)
    mode_options = ["本地规则引擎（0 API）", "AI 增强（DeepSeek-V3.2）"]
    mode = st.radio("生成模式", mode_options, index=0, label_visibility="collapsed")
    if mode.startswith("AI"):
        if API_KEY:
            st.success("已检测到 API Key，可调用 AI 增强。", icon="✅")
        else:
            st.info("未配置 SILICONFLOW_API_KEY，将自动使用本地引擎。", icon="ℹ️")

    generate = st.button("生成并检查", type="primary", use_container_width=True)

    st.markdown('<div class="side-label">引擎状态</div>', unsafe_allow_html=True)
    if API_KEY:
        block('<div class="engine-chip"><span class="dot"></span><div><b>AI 增强可用</b><br>默认仍走本地规则引擎</div></div>')
    else:
        block('<div class="engine-chip"><span class="dot off"></span><div><b>本地模式</b><br>词库 / 模板 / 评分全部离线</div></div>')

    st.markdown("---")
    st.caption("合规词库 9 类 · 本地生成 · 内容缺口 · 传播评分")
    st.caption("运行时 0 API 也可完整使用")

if generate:
    use_ai = mode.startswith("AI")
    with st.spinner("正在生成并做合规检查..."):
        st.session_state["gen"] = build_generation(product, features, platform, use_ai=use_ai and bool(API_KEY))
    new_copy = st.session_state["gen"]["items"][0]["text"]
    st.session_state["audit_text"] = new_copy
    st.session_state["gap_text"] = new_copy
    st.session_state["gap_source"] = st.session_state["features"]
    st.session_state["predict_text"] = new_copy
    st.session_state["audit_result"] = None
    st.session_state["gap_result"] = None
    st.session_state["gap_review"] = None
    st.session_state["gap_merged"] = None
    st.session_state["gap_flash"] = None
    st.session_state["gap_reviewed_text"] = ""
    for gap_key in [key for key in st.session_state.keys() if key.startswith("gap_fill_")]:
        del st.session_state[gap_key]
    st.session_state["predict_result"] = None
    st.session_state["gen_fixed"] = None
    st.session_state["expand_source"] = st.session_state["features"]
    st.session_state["expand_platform"] = platform if platform in PLATFORM_KEYS else "xiaohongshu"
    st.session_state["expand_result"] = None
    st.session_state["expand_body"] = ""
    st.session_state["expand_seed"] = 0
    st.session_state["expand_flash"] = None

# 演示模式：?demo=1 自动生成，方便截图和演示
if st.query_params.get("demo") == "1" and st.session_state.get("gen") is None:
    st.session_state["gen"] = build_generation(
        st.session_state["product"], st.session_state["features"], st.session_state["platform"], use_ai=False
    )

# 方向补全 → 合规预审：先把待审文案写入状态，再进入页签
if "audit_pending" in st.session_state:
    pending_text = st.session_state.pop("audit_pending")
    st.session_state["audit_text"] = pending_text
    st.session_state["audit_result"] = engine.audit(pending_text)


# ---------------------------------------------------------------------------
# 首屏
# ---------------------------------------------------------------------------

block(
    """
    <div class="hero">
      <div class="hero-kicker">GOOD PRODUCTS · SHANDONG</div>
      <h1>好品山东 <span>·</span> GEO合规智能传播工作台</h1>
      <p>输入产品信息 → 生成营销文案 → 自动合规检查 → 方向补全 → 传播预判</p>
      <div class="hero-badges">
        <span class="hero-badge">🛡️ 9 类合规词库</span>
        <span class="hero-badge">🧩 本地规则生成</span>
        <span class="hero-badge">🧭 内容缺口扫描</span>
        <span class="hero-badge">📈 七维传播评分</span>
        <span class="hero-badge">⚡ 0 API 可离线</span>
      </div>
    </div>
    """
)

tab_gen, tab_expand, tab_gap, tab_audit, tab_predict, tab_about = st.tabs(
    ["✍️ 智能生成", "📝 素材扩写", "🧭 方向补全", "🛡️ 合规预审", "📈 传播预判", "📦 作品说明"]
)

# ---------------------------------------------------------------------------
# 1. 智能生成
# ---------------------------------------------------------------------------

with tab_gen:
    gen = st.session_state.get("gen")
    if not gen:
        block(
            """
            <div class="section-kicker">START HERE</div>
            <div class="section-title">从一条真实的产品信息开始</div>
            <div class="section-desc">在左侧填写产品名称、特点与传播渠道，点击「生成并检查」。默认走本地规则引擎，不联网也能用。</div>
            """
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            block('<div class="card"><h3>1 · 生成</h3><p>按渠道生成 3 条短文案，突出产地、口感、售后等可举证信息。</p></div>')
        with col2:
            block('<div class="card"><h3>2 · 检查</h3><p>逐条扫描极限词、医疗功效、收益承诺、功效宣称等 9 类风险，给出修改建议。</p></div>')
        with col3:
            block('<div class="card"><h3>3 · 预判</h3><p>从标题、情感、话题、实用价值等七个维度看传播潜力，并给出补强建议。</p></div>')
    else:
        if gen.get("warning"):
            st.warning(gen["warning"])
        platform_label = "全渠道" if gen["platform"] == "all" else engine.PLATFORMS[gen["platform"]]["name"]
        block(
            f"""
            <div class="section-kicker">GENERATED COPY</div>
            <div class="section-title">{html.escape(gen['product'])} · {platform_label}文案</div>
            <div class="section-desc">生成模式：{html.escape(gen['mode'])} · 共 {len(gen['items'])} 条 · 每条 ≤80 字</div>
            """
        )
        for index, item in enumerate(gen["items"], 1):
            render_copy_card(index, item, gen["platform"])
        with st.expander(f"复制纯文本（{len(gen['items'])} 条）"):
            for item in gen["items"]:
                st.code(item["text"], language=None)

        total_risks = sum(len(item["audit"]["violations"]) for item in gen["items"])
        average = round(sum(item["audit"]["score"] for item in gen["items"]) / len(gen["items"]))
        block(
            f"""
            <div class="stat-grid">
              {stat("平均合规分", f"{average}/100", "满分 100")}
              {stat("文案条数", len(gen["items"]), "可下载")}
              {stat("待处理风险", total_risks, "点击展开查看")}
              {stat("生成模式", gen["mode"], "本地优先")}
            </div>
            """
        )

        action1, action2, action3 = st.columns([1.1, 1, 1.2])
        with action1:
            if st.button("一键合规优化", key="fix_generated", use_container_width=True):
                fixed = []
                changes = []
                for item in gen["items"]:
                    clean, replaced = engine.sanitize(item["text"])
                    fixed.append({"text": clean, "audit": engine.audit(clean), "platform": item.get("platform", gen["platform"])})
                    changes.extend(replaced)
                st.session_state["gen_fixed"] = {"items": fixed, "changes": changes}
        with action2:
            all_text = "\n\n".join(item["text"] for item in gen["items"])
            st.download_button(
                "下载全部文案" if gen["platform"] == "all" else "下载三条文案",
                data=all_text,
                file_name="好品山东_生成文案.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with action3:
            st.caption("建议：先处理风险提示，再到「传播预判」看看潜力。")

        fixed = st.session_state.get("gen_fixed")
        if fixed:
            st.markdown("##### ✅ 合规优化版")
            for index, item in enumerate(fixed["items"], 1):
                render_copy_card(index, item, gen["platform"])
            with st.expander("复制优化版纯文本"):
                for item in fixed["items"]:
                    st.code(item["text"], language=None)
            if fixed["changes"]:
                with st.expander(f"查看替换明细（{len(fixed['changes'])} 处）"):
                    for old, new in fixed["changes"]:
                        st.markdown(f"- `{old}` → `{new}`")
            else:
                st.info("未发现需要替换的风险词。")

# ---------------------------------------------------------------------------
# 2. 合规预审
# ---------------------------------------------------------------------------

with tab_audit:
    block(
        """
        <div class="section-kicker">COMPLIANCE AUDIT</div>
        <div class="section-title">发布前，先把风险摊开看</div>
        <div class="section-desc">支持粘贴任意文案；命中词会在原文里标红，并给出逐条修改建议。</div>
        """
    )
    default_audit = ""
    if st.session_state.get("gen"):
        default_audit = "\n".join(item["text"] for item in st.session_state["gen"]["items"])
    st.session_state.setdefault("audit_text", default_audit)
    if st.button("填入风险示例", key="load_audit_demo"):
        demo_text = "国家级认证的最佳苹果，100%纯天然，根治便秘，投资回报率高达500%，加微信享内部价。"
        st.session_state["audit_text"] = demo_text
        st.session_state["audit_result"] = engine.audit(demo_text)
    audit_text = st.text_area(
        "待审核文案",
        height=150,
        key="audit_text",
        placeholder="粘贴需要审核的文案...",
    )
    if st.button("开始预审", type="primary", key="run_audit"):
        if not audit_text.strip():
            st.warning("请先输入文案。")
        else:
            st.session_state["audit_result"] = engine.audit(audit_text)
    if st.session_state.get("audit_result"):
        render_risk_result(st.session_state["audit_result"])

# ---------------------------------------------------------------------------
# 2. 素材扩写
# ---------------------------------------------------------------------------

with tab_expand:
    block(
        """
        <div class="section-kicker">MATERIAL EXPANSION</div>
        <div class="section-title">把三句话，扩成一篇能发的文案</div>
        <div class="section-desc">基于原始简短素材补结构、补场景、补细节；只复述素材里的事实，缺的信息会变成补全建议。</div>
        """
    )

    flash = st.session_state.pop("expand_flash", "")
    if flash:
        st.success(flash)

    default_expand_platform = st.session_state.get("platform", "xiaohongshu")
    if default_expand_platform not in PLATFORM_KEYS:
        default_expand_platform = "xiaohongshu"
    if st.session_state.get("expand_platform") not in PLATFORM_KEYS:
        st.session_state["expand_platform"] = default_expand_platform
    st.session_state.setdefault("expand_style", expander.STYLES[0])
    st.session_state.setdefault("expand_length", "标准")
    st.session_state.setdefault("expand_seed", 0)
    st.session_state.setdefault("expand_source", st.session_state["features"])

    input_col, setting_col = st.columns([1.3, 1], gap="large")
    with input_col:
        expand_source = st.text_area(
            "原始简短素材",
            height=170,
            key="expand_source",
            placeholder="例如：烟台苹果，脆甜多汁，现摘现发，果径80mm以上，坏果包赔。",
        )
        st.caption("几句话、几个卖点即可。扩写会保留这些事实，不会自动编造检测、价格或产地。")
    with setting_col:
        expand_platform = st.selectbox(
            "目标渠道",
            PLATFORM_KEYS,
            format_func=lambda key: PLATFORM_LABELS[key],
            key="expand_platform",
        )
        expand_style = st.selectbox("表达风格", expander.STYLES, key="expand_style")
        expand_length = st.selectbox("篇幅", list(expander.LENGTHS.keys()), key="expand_length")
        button_col, reroll_col = st.columns(2)
        with button_col:
            run_expand = st.button("扩写成完整文案", type="primary", key="run_expand", use_container_width=True)
        with reroll_col:
            reroll = st.button("换一版", key="reroll_expand", use_container_width=True)

    def _run_expand() -> bool:
        if not expand_source.strip():
            st.warning("请先输入几句原始素材。")
            return False
        result = expander.expand(
            product,
            expand_source,
            expand_platform,
            expand_style,
            expand_length,
            seed=st.session_state.get("expand_seed", 0),
        )
        st.session_state["expand_result"] = result
        st.session_state["expand_body"] = result["body"]
        return True

    if run_expand:
        _run_expand()
    if reroll:
        st.session_state["expand_seed"] = st.session_state.get("expand_seed", 0) + 1
        _run_expand()

    result = st.session_state.get("expand_result")
    if result:
        block(
            f"""
            <div class="stat-grid">
              {stat("文案字数", result["char_count"], f"目标约 {result.get('target', 0)} 字")}
              {stat("饱满度", f"{result['fullness']}%", result["fullness_level"])}
              {stat("采用素材", len(result["used"]), "个方向")}
              {stat("待补事实", len(result["missing"]), "个方向")}
            </div>
            """
        )
        st.progress(result["fullness"] / 100, text=f"{result['fullness_level']} · {result['style']} · {PLATFORM_LABELS[result['channel']]}")
        if result.get("title"):
            block(f'<div class="expand-title">{html.escape(result["title"])}</div>')

        st.session_state.setdefault("expand_body", result["body"])
        body_text = st.text_area(
            "扩写后的正文（可继续编辑）",
            height=420,
            key="expand_body",
        )
        full_text = (result["title"] + "\n\n" if result.get("title") else "") + body_text

        action_col, audit_col = st.columns([1, 1])
        with action_col:
            st.download_button(
                "下载扩写文案",
                data=full_text,
                file_name="好品山东_扩写文案.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with audit_col:
            if st.button("送去合规预审", type="primary", key="expand_to_audit", use_container_width=True):
                if not body_text.strip():
                    st.warning("文案为空，无法预审。")
                else:
                    st.session_state["audit_pending"] = full_text
                    st.session_state["expand_flash"] = "扩写文案已同步到「合规预审」页签。"
                    st.rerun()

        with st.expander("这篇用了哪些素材 / 还可以补什么"):
            if result["used"]:
                block(
                    '<div class="keyword-row">'
                    + "".join(f'<span class="keyword-chip">{html.escape(name)}</span>' for name in result["used"])
                    + "</div>"
                )
            else:
                st.caption("素材信息较少，建议先补一两个具体事实。")
            if result["suggestions"]:
                st.markdown("**补上会更饱满：**")
                for suggestion in result["suggestions"]:
                    st.markdown(f"- {suggestion}")
            st.caption("本地扩写只复述素材中的事实；价格、检测、认证等具体信息请以商品页和包装为准。")


# ---------------------------------------------------------------------------
# 4. 方向补全
# ---------------------------------------------------------------------------

with tab_gap:
    block(
        """
        <div class="section-kicker">CONTENT GAP RADAR</div>
        <div class="section-title">先补全，再送审</div>
        <div class="section-desc">左边补缺口，右边出文案；补完直接送合规审查。</div>
        """
    )

    review = st.session_state.get("gap_review")
    sync_flash = st.session_state.pop("gap_sync_flash", "")
    if sync_flash:
        st.success(sync_flash)
    if review:
        flash = st.session_state.pop("gap_flash", "")
        if flash:
            st.success(flash)
        block('<div class="section-kicker">补全文案审查</div>')
        block(
            f"""
            <div class="stat-grid">
              {stat("合规分", f"{review['score']}/100", "补全文案")}
              {stat("风险等级", review["level_label"], f"风险分 {review['risk_score']}")}
              {stat("命中词", review["total"], f"{len(review['violations'])} 类")}
              {stat("可继续", "是" if review["level"] in ("safe", "low") else "先修改", "发布前复核")}
            </div>
            """
        )
        if review["violations"]:
            for violation in review["violations"][:3]:
                st.markdown(
                    f"- **{violation['word']}**（{engine.SEVERITY_LABEL[violation['severity']]}）：{violation['suggest']}"
                )
            st.caption("完整标注与逐条建议已同步到「合规预审」页签。")
        else:
            st.success("未检测到明显违规词，可进入发布前人工复核。")
        if st.session_state.get("gap_merged") and st.session_state.get("gap_review") and \
                st.session_state.get("gap_reviewed_text") != st.session_state.get("gap_merged"):
            st.warning("补全文案在审查后有修改，请重新审查。")
        st.divider()

    st.session_state.setdefault("gap_source", st.session_state["features"])
    source_col, copy_col = st.columns(2)
    with source_col:
        gap_source = st.text_area(
            "产品资料 / 可补充数据",
            height=100,
            key="gap_source",
            placeholder="产地、品种、采摘、检测、售后...",
        )
    with copy_col:
        default_gap = st.session_state["features"]
        if st.session_state.get("gen"):
            default_gap = st.session_state["gen"]["items"][0]["text"]
        st.session_state.setdefault("gap_text", default_gap)
        gap_text = st.text_area(
            "当前广告文案",
            height=100,
            key="gap_text",
            placeholder="粘贴一条正在使用的广告文案...",
        )

    category_col, scan_col, sync_col = st.columns([1.2, 1, 1], vertical_alignment="bottom")
    with category_col:
        gap_category = st.selectbox(
            "品类",
            content_gaps.CATEGORY_LABELS,
            key="gap_category",
        )
    with scan_col:
        if st.button("扫描内容缺口", type="primary", key="run_gap", use_container_width=True):
            if not gap_text.strip():
                st.warning("请先输入一段广告文案。")
            else:
                for key in list(st.session_state.keys()):
                    if key.startswith("gap_fill_") or key in ("gap_merged", "gap_review", "gap_flash", "gap_reviewed_text"):
                        del st.session_state[key]
                st.session_state["gap_result"] = content_gaps.analyze(
                    product, gap_text, gap_category, source=gap_source
                )
    with sync_col:
        st.button("同步侧边栏", key="sync_gap_source", use_container_width=True, on_click=sync_gap_source)

    gap = st.session_state.get("gap_result")
    if gap:
        block(
            f"""
            <div class="gap-summary">
              <div><b>{gap['score']}%</b><span>方向覆盖</span></div>
              <div><b>{html.escape(gap['category'])}</b><span>识别品类</span></div>
              <div><b>{gap['covered_count']}/{gap['total']}</b><span>已覆盖</span></div>
              <div><b>{gap['available_count']}</b><span>素材已有</span></div>
            </div>
            """
        )
        st.progress(gap["score"] / 100, text=f"{gap['level']} · {gap['summary']}")
        block(
            '<div class="keyword-row" style="margin-bottom:6px;"><span class="gap-covered-label">已覆盖</span>'
            + ("".join(f'<span class="keyword-chip">{html.escape(item["name"])}</span>' for item in gap["covered"]) or '<span class="text-muted">还没有覆盖任何方向</span>')
            + "</div>"
        )

        left, right = st.columns([1.25, 1], gap="large")
        with left:
            block('<div class="section-kicker">缺口与补全</div>')
            for item in gap["recommended"]:
                priority_class = "high" if item["weight"] >= 1.3 else ("mid" if item["weight"] >= 1.0 else "low")
                badge_class = "ready" if item["available"] else priority_class
                badge_text = "素材已有" if item["available"] else item["priority"]
                note = (
                    "产品资料已有：" + "、".join(item["evidence"])
                    if item["available"]
                    else "产品资料也没有，先补事实"
                )
                with st.container(border=True):
                    block(
                        f"""
                        <div class="gap-row-head">
                          <span class="gap-priority {badge_class}">{badge_text}</span>
                          <span class="gap-name">{html.escape(item["name"])}</span>
                          <span class="gap-row-note">{html.escape(note)}</span>
                        </div>
                        """
                    )
                    fill_key = f"gap_fill_{item['key']}"
                    st.session_state.setdefault(fill_key, suggest_gap_fill(item, gap_source))
                    st.text_input(
                        f"{item['name']}｜补一句",
                        key=fill_key,
                        placeholder=item["template"],
                        help=f"{item['why']} {item['angle']}",
                        label_visibility="collapsed",
                    )

            if len(gap["missing"]) > len(gap["recommended"]):
                with st.expander(f"还有 {len(gap['missing']) - len(gap['recommended'])} 个方向未展开"):
                    st.write("、".join(item["name"] for item in gap["missing"][len(gap["recommended"]):]))

        with right:
            block('<div class="section-kicker">补全文案</div>')
            if st.button("生成补全文案", key="build_gap_copy", use_container_width=True):
                parts = [gap_text.strip()]
                for item in gap["recommended"]:
                    fill = str(st.session_state.get(f"gap_fill_{item['key']}", "")).strip()
                    if not fill or fill in parts:
                        continue
                    if not re.search(r"[。！？!?]$", fill):
                        fill += "。"
                    parts.append(fill)
                if len(parts) <= 1:
                    st.warning("请至少补充一条内容，再生成补全文案。")
                else:
                    st.session_state["gap_merged"] = "\n\n".join(parts)

            if st.session_state.get("gap_merged"):
                merged_text = st.text_area(
                    "补全后的广告文案",
                    height=190,
                    key="gap_merged",
                    label_visibility="collapsed",
                )
                st.download_button(
                    "下载补全文案",
                    data=merged_text,
                    file_name="好品山东_补全文案.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
                if st.button("补全并审查", type="primary", key="gap_to_audit", use_container_width=True):
                    if not merged_text.strip():
                        st.warning("补全文案为空，无法审查。")
                    else:
                        st.session_state["audit_pending"] = merged_text
                        st.session_state["gap_review"] = engine.audit(merged_text)
                        st.session_state["gap_reviewed_text"] = merged_text
                        st.session_state["gap_flash"] = "补全文案已同步到「合规预审」页签，完整报告可在该页签查看。"
                        st.rerun()
            else:
                st.caption("填写左侧补全句后，点「生成补全文案」。")

            outline_text = (
                f"【{gap['category']}】内容缺口分析\n"
                f"方向覆盖：{gap['score']}%（{gap['covered_count']}/{gap['total']}）\n"
                f"判断：{gap['level']}\n\n"
                "已覆盖：" + "、".join(item["name"] for item in gap["covered"]) + "\n\n"
                "建议补全：\n" + "\n".join(gap["outline"]) + "\n\n"
                "可填空句式：\n" + "\n".join(
                    f"- {item['name']}（{'素材已有：' + '、'.join(item['evidence']) if item['available'] else '先补事实'}）：{item['template']}"
                    for item in gap["recommended"]
                )
            )
            with st.expander("补全提纲 / 下载"):
                for line in gap["outline"]:
                    st.markdown(f"- {line}")
                st.download_button(
                    "下载补全提纲",
                    data=outline_text,
                    file_name="好品山东_内容补全提纲.txt",
                    mime="text/plain",
                )

# ---------------------------------------------------------------------------
# 5. 传播预判
# ---------------------------------------------------------------------------

with tab_predict:
    block(
        """
        <div class="section-kicker">CONTENT POTENTIAL</div>
        <div class="section-title">发布前，先估一估传播力</div>
        <div class="section-desc">七维定性评分，用于自查，不代表平台实际流量。</div>
        """
    )
    default_predict = st.session_state["features"]
    if st.session_state.get("gen"):
        default_predict = st.session_state["gen"]["items"][0]["text"]
    st.session_state.setdefault("predict_text", default_predict)
    predict_text = st.text_area(
        "待评估文案",
        height=150,
        key="predict_text",
    )
    predict_platform = st.selectbox(
        "投放渠道",
        PLATFORM_KEYS,
        format_func=lambda key: PLATFORM_LABELS[key],
        key="predict_platform",
    )
    if st.button("开始预判", type="primary", key="run_predict"):
        st.session_state["predict_result"] = engine.predict(predict_text, predict_platform)

    prediction = st.session_state.get("predict_result")
    if prediction:
        potential = prediction["potential"]
        block(
            f"""
            <div class="card" style="margin-bottom:14px;">
              <div style="display:flex;align-items:flex-end;gap:14px;flex-wrap:wrap;">
                <div style="font-size:52px;font-weight:900;line-height:1;color:{potential['color']}">{prediction['total']}</div>
                <div>
                  <div style="font-size:18px;font-weight:800;color:{potential['color']}">{potential['level']}</div>
                  <div style="color:#627d98;font-size:13px;">{potential['desc']}</div>
                </div>
              </div>
            </div>
            """
        )
        for key, name, _weight, desc in prediction["dims"]:
            score = prediction["scores"][key]
            st.markdown(f"**{name}** · {desc}")
            st.progress(score / 100, text=f"{score} 分")

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("##### 归因")
            for item in prediction["attributions"]:
                st.markdown(f"- {item}")
        with col_b:
            st.markdown("##### 优化建议")
            for item in prediction["suggestions"]:
                st.markdown(f"- {item}")

# ---------------------------------------------------------------------------
# 6. 作品说明
# ---------------------------------------------------------------------------

with tab_about:
    block(
        f"""
        <div class="section-kicker">ABOUT THE WORK</div>
        <div class="section-title">{html.escape(content.WORK['name'])}</div>
        <div class="section-desc">{html.escape(content.WORK['tagline'])}</div>
        <div class="quote">{html.escape(content.WORK['intro'])}</div>
        """
    )
    st.caption(f"作品链接：{content.WORK['link']}")

    st.markdown("##### 设计思路")
    col1, col2 = st.columns(2)
    for index, item in enumerate(content.DESIGN_IDEAS):
        with (col1 if index % 2 == 0 else col2):
            block(f'<div class="card" style="margin-bottom:10px;"><h3>{html.escape(item["title"])}</h3><p>{html.escape(item["body"])}</p></div>')

    st.markdown("##### 传播理念")
    for item in content.COMMUNICATION_IDEAS:
        st.markdown(f"- {item}")

    st.markdown("##### 创新点")
    col3, col4 = st.columns(2)
    for index, item in enumerate(content.INNOVATIONS):
        with (col3 if index % 2 == 0 else col4):
            block(f'<div class="card" style="margin-bottom:10px;"><h3>{html.escape(item["title"])}</h3><p>{html.escape(item["body"])}</p></div>')

    st.markdown("##### 使用的 AI 工具")
    for tool in content.AI_TOOLS:
        block(f'<div class="card" style="margin-bottom:8px;"><h3>{html.escape(tool["name"])}</h3><p>{html.escape(tool["role"])}</p></div>')

    st.markdown("##### 从对话到作品")
    for item in content.CONVERSATION:
        block(
            f"""
            <div class="timeline">
              <div class="timeline-item">
                <div class="timeline-stage">{html.escape(item['stage'])}</div>
                <div class="timeline-title">{html.escape(item['title'])}</div>
                <div class="timeline-summary">{html.escape(item['summary'])}</div>
              </div>
            </div>
            """
        )

    st.markdown("##### 一句话原则")
    block('<div class="keyword-row">' + "".join(f'<span class="tag-chip">{html.escape(item)}</span>' for item in content.PRINCIPLES) + "</div>")

block('<div class="footer-note">好品山东 · GEO合规智能传播工作台 · 本地规则引擎优先，AI 增强可选</div>')
