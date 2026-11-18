"""本地规则引擎：合规预审、渠道改写、关键词提取、传播预判。

不依赖任何在线大模型。所有词表、模板与评分规则都在本文件内，
可以按行业继续扩充，页面层只负责展示。
"""
from __future__ import annotations

import html as html_lib
import random
import re
from collections import Counter

# ---------------------------------------------------------------------------
# 1. 合规词库
# ---------------------------------------------------------------------------

VIOLATION_DB = {
    "absolute": {
        "label": "极限词",
        "category": "极限词（广告法第九条）",
        "severity": "high",
        "suggest": "删除极限词，或替换为「优秀 / 领先 / 优质」等可举证的客观表述",
        "words": [
            "国家级", "最高级", "最佳", "最好", "最大", "第一", "唯一", "首个", "首选", "独家",
            "顶级", "极致", "万能", "百强", "第一品牌", "全国第一", "全网最低", "销量第一",
            "排名第一", "冠军", "绝无仅有", "前无古人", "史无前例", "独一无二", "空前", "顶级品牌",
            "最便宜", "最低价", "最优惠", "最流行", "最时尚", "最聚信赖", "最先进", "最科学",
            "最合理", "最专业", "最权威", "最值得", "最高端", "最奢侈", "最顶级", "最极致",
            "最领先", "最低", "最赚", "最划算", "最安全", "最快速", "最强", "最牛", "最顶尖",
            "最巅峰", "最出色", "最完美", "最优", "最值得信赖", "最值得拥有", "最懂你", "最贴心",
        ],
    },
    "fake": {
        "label": "虚假宣传",
        "category": "虚假宣传 / 夸大功效",
        "severity": "high",
        "suggest": "删除绝对化承诺，改为「有助于 / 可改善」等谨慎表述，并确保有检测或数据支撑",
        "words": [
            "包治百病", "根治", "痊愈", "100%有效", "100%纯天然", "纯天然", "零风险", "绝对安全",
            "无副作用", "永不复发", "药到病除", "神奇功效", "立竿见影", "当天见效", "秒杀一切",
            "万人好评", "好评率99%", "全网爆款", "人人都在用", "卖了上亿", "抢疯了", "卖疯了",
            "断货王", "家家必备", "永久", "终身", "永不过期", "永不褪色", "永久免费", "永久有效",
            "长生不老", "返老还童", "延年益寿",
        ],
    },
    "claim": {
        "label": "功效/成分宣称",
        "category": "功效或成分宣称待验证",
        "severity": "mid",
        "suggest": "功效/成分宣称需有评价报告、检测依据或备案信息，避免绝对化表达",
        "words": ["零添加", "美白", "修复", "抗衰", "祛斑", "生发", "防脱"],
    },
    "medical": {
        "label": "医疗用语",
        "category": "医疗用语（非医疗产品违规）",
        "severity": "high",
        "suggest": "非医疗产品不得使用医疗术语，改为「呵护 / 保养 / 滋养」等普通用语",
        "words": [
            "治疗", "疗效", "治愈", "消炎", "止痛", "镇静", "抗炎", "抗病毒", "抗菌", "抑菌",
            "消毒", "理疗", "化疗", "处方", "药用", "修复细胞", "激活细胞", "细胞再生",
            "促进新陈代谢", "调节免疫", "增强免疫力", "提高免疫力", "排毒", "解毒", "通经络",
            "活血", "化瘀", "补肾", "壮阳", "健脾", "养胃", "润肺", "清热", "降火",
            "降血压", "降血糖", "降血脂", "减肥", "丰胸",
        ],
    },
    "finance": {
        "label": "收益承诺",
        "category": "投资收益承诺",
        "severity": "high",
        "suggest": "金融广告不得承诺收益，改为「历史表现 / 参考收益」，并补充风险提示",
        "words": [
            "稳赚不赔", "保本保息", "零风险投资", "百分百盈利", "日赚", "月入十万", "月入百万",
            "年化收益", "收益保证", "保底收益", "投资回报率", "回报率高达", "稳收益", "躺赚",
            "轻松赚钱", "暴富", "一夜暴富", "发财", "稳赚", "必定盈利", "只涨不跌",
        ],
    },
    "induce": {
        "label": "诱导互动",
        "category": "诱导互动 / 低俗",
        "severity": "mid",
        "suggest": "减少紧迫感和诱导性表述，用产品事实与真实价值驱动转化",
        "words": [
            "速来抢", "再不抢就没了", "仅限今天", "最后3小时", "最后一天", "仅剩10个",
            "马上售罄", "紧急通知", "震惊", "惊呆了", "不看后悔", "千万别点", "偷偷告诉你",
            "内部消息", "机密", "劲爆", "大曝光", "曝光", "删前速看", "速看即将删除",
        ],
    },
    "compare": {
        "label": "贬低竞品",
        "category": "贬低竞品 / 不当比较",
        "severity": "mid",
        "suggest": "不得贬低他人商品，改为陈述自身产品可验证的优势",
        "words": [
            "秒杀竞品", "秒杀所有竞品", "吊打同行", "完爆", "碾压同行", "远超同类", "吊打",
            "甩同行几条街", "别家都是垃圾", "别家的不行",
        ],
    },
    "platform": {
        "label": "平台导流",
        "category": "平台社区规范敏感",
        "severity": "mid",
        "suggest": "平台禁止导流站外交易，改为引导关注账号或店铺内成交",
        "words": [
            "加微信", "加V信", "加我微信", "加我私聊", "扫码加我", "二维码", "加好友", "私聊",
            "+v", "VX", "微信同号", "电话同号", "转账", "打款", "支付宝", "银行卡", "代付",
            "代购", "刷单", "兼职", "日结", "高薪兼职", "足不出户",
        ],
    },
    "data": {
        "label": "未验证数据",
        "category": "未验证数据 / 未标注来源",
        "severity": "low",
        "suggest": "引用数据需标注具体来源，认证需出示证书编号或备案信息",
        "words": [
            "据调查", "据统计", "数据显示", "研究表明", "实验证明", "临床证明", "权威认证",
            "国家认证", "国际认证", "FDA认证", "ISO认证", "3C认证", "绿色食品", "有机认证",
            "免检产品", "国家免检",
        ],
    },
}

# 合规替换：只用于改写稿，尽量写成自然措辞
REPLACEMENTS = {
    "国家级": "行业认可", "国家级认证": "相关认证", "最高级": "优秀", "最佳": "优选",
    "最好": "出色", "最大": "规模领先", "第一": "领先", "唯一": "独特", "首个": "率先推出",
    "首选": "优选", "独家": "专属", "顶级": "高端", "极致": "精益求精", "万能": "多功能",
    "百强": "行业前列", "第一品牌": "口碑品牌", "全国第一": "全国领先", "全网最低": "价格实惠",
    "全网最低价": "价格实惠", "销量第一": "销量领先", "排名第一": "位居前列", "冠军": "优胜",
    "绝无仅有": "难能可贵", "前无古人": "开创性", "史无前例": "前所未有", "独一无二": "独具特色",
    "空前": "前所未有", "顶级品牌": "高端品牌", "最便宜": "价格实惠", "最低价": "特惠价",
    "最优惠": "特惠", "最流行": "很受欢迎", "最时尚": "设计感强", "最聚信赖": "值得信赖",
    "最先进": "技术领先", "最科学": "科学合理", "最合理": "科学合理", "最专业": "专业可靠",
    "最权威": "行业认可", "最值得": "非常推荐", "最高端": "高端定位", "最奢侈": "奢华",
    "最顶级": "一流", "最极致": "臻于完美", "最领先": "行业领跑", "最低": "亲民",
    "最赚": "收益可观", "最划算": "超值", "最安全": "安全可靠", "最快速": "高效",
    "最强": "实力强劲", "最牛": "业内领先", "最顶尖": "行业顶尖", "最巅峰": "巅峰之作",
    "最出色": "表现出色", "最完美": "趋于完美", "最优": "优质", "最值得信赖": "值得信赖",
    "最值得拥有": "值得拥有", "最懂你": "贴心", "最贴心": "贴心周到",
    "包治百病": "有助于改善多种不适", "根治": "从根源调理", "痊愈": "逐步好转",
    "100%有效": "多数人反馈有效", "100%纯天然": "天然", "纯天然": "天然", "零风险": "风险可控",
    "绝对安全": "安全可靠", "无副作用": "温和低敏", "永不复发": "持续改善", "药到病除": "见效快",
    "神奇功效": "效果显著", "立竿见影": "见效快", "当天见效": "不久即可感受",
    "秒杀一切": "相比同类产品更具优势", "万人好评": "广受好评", "好评率99%": "多数用户好评",
    "全网爆款": "热销产品", "人人都在用": "很多人在用", "卖了上亿": "销量可观",
    "抢疯了": "热销中", "卖疯了": "热销中", "断货王": "库存紧张", "家家必备": "家庭常备",
    "永久": "长期有效", "终身": "长期", "终身免费": "长期免费", "永不过期": "保质期长",
    "永不褪色": "色彩持久", "永久免费": "长期免费", "永久有效": "长期有效",
    "长生不老": "延缓衰老", "返老还童": "重焕活力", "延年益寿": "健康管理",
    "零添加": "配方简洁", "美白": "提亮", "修复": "养护", "抗衰": "年轻态护理",
    "祛斑": "改善肤色不均", "生发": "养护头皮", "防脱": "养护发根",
    "治疗": "调理", "疗效": "改善程度", "治愈": "好转", "消炎": "舒缓", "止痛": "缓解不适",
    "镇静": "放松身心", "抗炎": "舒缓", "抗病毒": "提升自护力", "抗菌": "抑菌",
    "抑菌": "减少细菌", "消毒": "清洁", "理疗": "物理调理", "化疗": "化学治疗",
    "处方": "方案", "药用": "养护用", "修复细胞": "滋养细胞", "激活细胞": "唤醒细胞活力",
    "细胞再生": "促进细胞更新", "促进新陈代谢": "促进代谢", "调节免疫": "提升自护力",
    "增强免疫力": "提升自护力", "提高免疫力": "提升抵抗力", "排毒": "促进代谢",
    "解毒": "促进代谢", "通经络": "促进循环", "活血": "促进循环", "化瘀": "化解淤积",
    "补肾": "滋养肾气", "壮阳": "提升精力", "健脾": "养护脾胃", "养胃": "温和养护",
    "润肺": "滋润", "清热": "清凉", "降火": "去火润燥", "降血压": "辅助调节血压",
    "降血糖": "辅助调节血糖", "降血脂": "辅助调节血脂", "减肥": "管理体态",
    "丰胸": "提升曲线",
    "稳赚不赔": "合理配置", "保本保息": "本金保障", "零风险投资": "风险可控",
    "百分百盈利": "收益可期", "日赚": "每日收益", "月入十万": "月入可观",
    "月入百万": "高收入潜力", "年化收益": "参考收益", "收益保证": "收益可期",
    "保底收益": "基础收益保障", "投资回报率": "参考回报率", "回报率高达": "回报率可观",
    "稳收益": "收益稳健", "躺赚": "被动收入", "轻松赚钱": "灵活创收", "暴富": "财富积累",
    "一夜暴富": "财富增长", "发财": "财富增长", "稳赚": "稳健获益", "必定盈利": "盈利可期",
    "只涨不跌": "长期看好",
    "速来抢": "库存有限", "再不抢就没了": "库存不多", "仅限今天": "限时优惠",
    "最后3小时": "即将结束", "最后一天": "最后机会", "仅剩10个": "库存紧张",
    "马上售罄": "即将售完", "紧急通知": "温馨提示", "震惊": "惊人发现", "惊呆了": "出乎意料",
    "不看后悔": "不容错过", "千万别点": "建议一看", "偷偷告诉你": "悄悄分享",
    "内部消息": "独家资讯", "机密": "重要资讯", "劲爆": "重磅消息", "大曝光": "深度揭秘",
    "曝光": "揭秘", "删前速看": "限时分享", "速看即将删除": "限时内容",
    "秒杀竞品": "相比同类产品更具优势", "秒杀所有竞品": "相比同类产品更具优势",
    "吊打同行": "差异化明显", "完爆": "优势明显", "碾压同行": "综合实力强",
    "远超同类": "表现更佳", "吊打": "优势明显", "甩同行几条街": "差异化显著",
    "别家都是垃圾": "我们专注于品质与体验", "别家的不行": "我们更注重品质把控",
    "加微信": "私信客服", "加V信": "私信客服", "加我微信": "联系客服",
    "加我私聊": "私信咨询", "扫码加我": "扫码关注", "二维码": "入口", "加好友": "关注账号",
    "私聊": "私信沟通", "+v": "私信", "VX": "私信", "微信同号": "同号联系",
    "电话同号": "同号联系", "转账": "平台支付", "打款": "付款", "支付宝": "平台支付",
    "银行卡": "银行转账", "代付": "代付款", "代购": "跨境购", "刷单": "真实交易",
    "兼职": "副业", "日结": "按日结算", "高薪兼职": "高收入副业", "足不出户": "线上即可",
    "据调查": "公开资料显示", "据统计": "公开数据表明", "数据显示": "公开数据表明",
    "研究表明": "相关研究显示", "实验证明": "实验结果显示", "临床证明": "临床研究显示",
    "权威认证": "相关认证", "国家认证": "相关认证", "国际认证": "国际相关认证",
    "FDA认证": "FDA 认证", "ISO认证": "ISO 认证", "3C认证": "3C 认证",
    "绿色食品": "绿色标准", "有机认证": "有机相关认证", "免检产品": "通过检测的产品",
    "国家免检": "通过相关检测",
}

SEVERITY_ORDER = {"high": 0, "mid": 1, "low": 2}
SEVERITY_LABEL = {"high": "高危", "mid": "中危", "low": "低危"}
LEVEL_META = {
    "safe": {"label": "安全", "color": "#0f9d58", "bg": "#e9f8ef"},
    "low": {"label": "低风险", "color": "#b7791f", "bg": "#fff8e6"},
    "mid": {"label": "中风险", "color": "#c05621", "bg": "#fff1e6"},
    "high": {"label": "高风险", "color": "#c53030", "bg": "#fdecec"},
}

# ---------------------------------------------------------------------------
# 2. 改写语料
# ---------------------------------------------------------------------------

SYNONYMS = {
    "非常好": ["相当不错", "很出色"],
    "很好": ["挺不错", "很不错"],
    "不错": ["令人满意", "挺出彩"],
    "推荐": ["值得一试", "可以试试"],
    "效果": ["使用感", "表现"],
    "适合": ["适配"],
    "改善": ["缓解"],
    "帮助": ["有助于"],
    "快速": ["迅速"],
    "方便": ["省事"],
    "安全": ["稳妥"],
    "天然": ["自然"],
    "保湿": ["补水"],
    "美白": ["提亮"],
    "清爽": ["清透"],
    "持久": ["耐用"],
    "舒服": ["舒适"],
    "好看": ["颜值高"],
    "便宜": ["实惠"],
    "贵": ["价格偏高"],
    "喜欢": ["偏爱"],
    "满意": ["认可"],
    "问题": ["困扰"],
    "特点": ["亮点"],
    "成分": ["配方"],
    "技术": ["工艺"],
    "价格": ["价位"],
    "感觉": ["感受"],
    "发现": ["注意到"],
    "需要": ["要"],
    "可以": ["能"],
}

TEMPLATES = {
    "xiaohongshu": {
        "titles": [
            "被问爆的{topic}，到底值不值？",
            "实测{topic}：优点、短板一次说清",
            "不吹不黑，聊聊{topic}",
            "{topic}怎么选？看完这篇再决定",
            "关于{topic}，我想说几句真心话",
        ],
        "expansions": [
            "我比较在意的一点是：{point}。",
            "如果只能留一个建议：重点看{point}。",
            "我自己的判断标准很简单——看{point}。",
        ],
        "ctas": [
            "你们还想看哪方面的细节？评论区告诉我～",
            "用过同款的姐妹，来评论区交流下真实感受～",
            "有同样困扰的姐妹，评论区蹲一个反馈～",
        ],
    },
    "douyin": {
        "hooks": [
            "别再乱买了！{topic}选错，真的白花钱。",
            "等等！你是不是也在纠结{topic}怎么选？",
            "这条视频，把{topic}讲明白。",
            "用了这么久{topic}，今天说点大实话。",
        ],
        "twists": [
            "但真正影响体验的，往往不是宣传语，而是它适不适合你的使用场景。",
            "但你先别急着下单——同价位里，适合你的才是更划算的。",
        ],
        "expansions": [
            "{point}，这一点值得单独说。",
            "同等价位里，{point}往往最容易被忽略。",
        ],
        "ctas": [
            "想要详细清单的，评论区扣「1」，下期接着拆。",
            "关注我，下期讲{topic}怎么避坑。",
        ],
    },
    "gongzhonghao": {
        "titles": [
            "{topic}怎么选？从卖点到体验，一次讲清",
            "实测{topic}：优点、短板与适合人群",
            "深度｜{topic}的真实体验与选择建议",
        ],
        "expansions": [
            "原文里提到{point}，这一点值得留意。",
            "{point}只是判断的一部分，还要结合使用场景。",
        ],
        "ctas": [],
    },
    "pengyouquan": {
        "hooks": [
            "最近在试{topic}，说点真实感受。",
            "用了几天{topic}，来交个作业。",
            "不吹不黑，聊聊{topic}。",
        ],
        "expansions": [
            "我比较看重的点是：{point}。",
            "还有一点：{point}。",
        ],
        "ctas": [
            "你们平时怎么挑{topic}？评论区聊聊～",
            "有需要的朋友可以问我，看到都会回～",
        ],
    },
}

PLATFORMS = {
    "xiaohongshu": {
        "name": "小红书", "icon": "📕", "desc": "种草 / 情感共鸣 / 分享体",
        "max_chars": 1000, "hint": "建议 300–600 字",
        "emojis": ["✨", "🌿", "💫", "🌸", "💡", "📌"],
        "tags": ["好物分享", "真实体验"],
    },
    "douyin": {
        "name": "抖音", "icon": "🎬", "desc": "短视频脚本 / 口播 / 反转",
        "max_chars": 300, "hint": "口播建议 150–300 字",
        "emojis": ["🎬", "🔥", "👉"], "tags": [],
    },
    "gongzhonghao": {
        "name": "公众号", "icon": "📱", "desc": "深度 / 逻辑 / 专业体",
        "max_chars": 1200, "hint": "建议 600–1000 字",
        "emojis": [], "tags": [],
    },
    "pengyouquan": {
        "name": "朋友圈", "icon": "💬", "desc": "短平快 / 生活感 / 种草",
        "max_chars": 150, "hint": "建议 80–150 字",
        "emojis": ["🌿"], "tags": [],
    },
}

CATEGORY_TAGS = [
    (re.compile(r"面膜|面霜|护肤|精华|水乳|洁面|防晒|眼霜|身体乳"), ["护肤", "成分党"]),
    (re.compile(r"手表|手环|耳机|音箱|充电|数码|手机|平板"), ["数码", "智能穿戴"]),
    (re.compile(r"咖啡|茶|零食|美食|餐厅|食品|烘焙"), ["美食", "咖啡"]),
    (re.compile(r"家居|收纳|清洁|拖把|床品|香薰|厨房"), ["家居", "生活灵感"]),
    (re.compile(r"健身|减肥|瑜伽|运动|跑步|塑形"), ["健身", "自律"]),
    (re.compile(r"课程|学习|英语|读书|考试|知识"), ["学习", "自我提升"]),
    (re.compile(r"宝宝|儿童|母婴|奶粉|纸尿裤|育儿"), ["母婴", "育儿"]),
    (re.compile(r"宠物|猫咪|狗狗|养宠"), ["宠物", "萌宠"]),
    (re.compile(r"旅行|酒店|民宿|露营|出游"), ["旅行", "生活方式"]),
    (re.compile(r"苹果|樱桃|水果|农产品|果园|产地直发"), ["农产品", "原产地", "助农"]),
]

PRODUCT_TERMS = [
    "扫地机器人", "智能手表", "空气炸锅", "净水器", "投影仪", "洗发水", "沐浴露", "护手霜",
    "身体乳", "洗面奶", "防晒霜", "精华液", "纸尿裤", "充电宝", "行李箱", "面膜", "面霜",
    "精华", "水乳", "洁面", "防晒", "眼霜", "口红", "粉底液", "香水", "手表", "手环",
    "耳机", "音箱", "手机", "平板", "咖啡", "茶叶", "零食", "奶粉", "猫粮", "狗粮",
    "课程", "书籍", "枕头", "床垫", "沙发", "苹果", "樱桃", "葡萄", "草莓", "梨",
]

TOPIC_STOPWORDS = {
    "这款", "那款", "产品", "东西", "效果", "体验", "感觉", "使用", "购买", "推荐", "分享",
    "朋友", "大家", "我们", "你们", "他们", "自己", "一个", "可以", "非常", "真的", "比较",
    "觉得", "认为", "发现", "建议", "注意", "需要", "想要", "能够", "已经", "正在", "一起",
    "每天", "每次", "现在", "以后", "然后", "因为", "所以", "但是", "如果", "还是", "就是",
    "不是", "没有", "怎么", "什么", "这样", "那样", "这里", "那里", "这么", "那么", "一样",
    "一些", "一点", "一次", "一下", "一直", "也许", "大概", "可能", "应该", "首先", "其次",
    "最后", "总之", "其实", "确实", "当然", "最近", "在用", "入手", "试了", "添加",
}

KEYWORD_STOPWORDS = {
    "这款", "那款", "产品", "商品", "东西", "我们", "你们", "他们", "自己", "大家", "朋友",
    "效果", "体验", "感觉", "使用", "购买", "推荐", "分享", "可以", "非常", "真的", "比较",
    "觉得", "认为", "发现", "建议", "注意", "需要", "想要", "能够", "已经", "正在", "一起",
    "每天", "每次", "现在", "以后", "然后", "因为", "所以", "但是", "如果", "还是", "就是",
    "不是", "没有", "怎么", "什么", "这样", "那样", "这里", "那里", "这么", "那么", "一样",
    "一些", "一点", "一次", "一下", "一直", "也许", "大概", "可能", "应该", "首先", "其次",
    "最后", "总之", "其实", "确实", "当然", "最近", "品牌", "优势", "特点", "方面", "情况",
    "相关", "进行", "通过", "以及", "对于", "关于", "同时", "而且", "并且", "虽然", "不过",
}

KEYWORD_STOP_CHARS = set("的了是在和与及或我你他她它这那有会就都也很更最并而被把让给对从到为以于其之者得地着过吗呢吧啊哦嗯还又才只不没无等各该些个种次款们请想要能可将")

KEYWORD_BLOCK_FRAGMENTS = [
    "同类", "相比", "产品", "品牌", "优势", "方面", "问题", "相关", "进行", "通过", "我们",
    "你们", "他们", "这款", "那款", "各种", "所有", "以及", "对于", "关于", "同时", "而且",
    "并且", "虽然", "不过", "可以", "非常", "真的", "比较", "觉得", "认为", "发现", "建议",
    "注意", "需要", "想要", "能够", "已经", "正在", "表明", "显示", "使用", "效果", "研究",
]

KEYWORD_SUFFIXES = [
    "成分", "配方", "质地", "口感", "续航", "认证", "设计", "技术", "价格", "包装",
    "服务", "数据", "调理", "改善", "体验", "吸收", "清洁", "保湿", "提亮",
]

KEYWORD_BAD_STARTS = set("关类比同相种款们这那其此该各被把将对从到为以于之者得地着过")

KEYWORD_DICTIONARY = [
    "天然成分", "成分", "配方", "肌肤", "敏感肌", "干皮", "油皮", "保湿", "补水", "提亮",
    "美白", "修护", "清洁", "控油", "防晒", "精华", "面霜", "面膜", "眼霜", "水乳",
    "续航", "快充", "降噪", "音质", "便携", "性价比", "颜值", "口感", "香气", "咖啡因",
    "乳胶", "支撑", "透气", "认证", "质检", "数据", "设计", "包装", "售后", "脆甜",
    "多汁", "产地直发", "现摘现发", "果园", "助农",
]

CTA_RE = re.compile(r"扫码|加微信|加我|私聊|私信|关注|评论|点赞|转发|收藏|下单|购买|链接|内部价|优惠|领取|联系客服|咨询客服")


def _build_index(words):
    index = {}
    for word in sorted(set(words), key=len, reverse=True):
        if not word:
            continue
        index.setdefault(word[0], []).append(word)
    return index


VIOLATION_META = {}
for _key, _cat in VIOLATION_DB.items():
    for _word in _cat["words"]:
        VIOLATION_META[_word] = {
            "label": _cat["label"], "category": _cat["category"],
            "severity": _cat["severity"], "suggest": _cat["suggest"],
        }

VIOLATION_INDEX = _build_index(VIOLATION_META.keys())
REPLACEMENT_INDEX = _build_index(REPLACEMENTS.keys())
SYNONYM_INDEX = _build_index(SYNONYMS.keys())


def _normalize(text) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _scan(text: str, index: dict) -> list[tuple[int, int, str]]:
    hits = []
    i = 0
    while i < len(text):
        matched = None
        for word in index.get(text[i], ()):
            if text.startswith(word, i):
                matched = word
                break
        if matched:
            hits.append((i, i + len(matched), matched))
            i += len(matched)
        else:
            i += 1
    return hits


def audit(text: str) -> dict:
    """合规预审：返回命中词、分组、风险分、合规分与标注 HTML。"""
    text = _normalize(text)
    hits = _scan(text, VIOLATION_INDEX)
    grouped = {}
    for start, end, word in hits:
        meta = VIOLATION_META[word]
        item = grouped.setdefault(word, {
            "word": word, "severity": meta["severity"], "category": meta["category"],
            "suggest": meta["suggest"], "count": 0,
        })
        item["count"] += 1

    violations = sorted(
        grouped.values(),
        key=lambda item: (SEVERITY_ORDER[item["severity"]], -item["count"], -len(item["word"])),
    )
    counts = {"high": 0, "mid": 0, "low": 0}
    for item in violations:
        counts[item["severity"]] += 1

    if counts["high"] >= 3:
        level, risk_score = "high", min(100, 60 + counts["high"] * 8)
    elif counts["high"] >= 1:
        level, risk_score = "mid", min(59, 35 + counts["high"] * 10 + counts["mid"] * 4)
    elif counts["mid"] >= 2:
        level, risk_score = "mid", min(55, 25 + counts["mid"] * 8 + counts["low"] * 3)
    elif counts["mid"] >= 1 or counts["low"] >= 3:
        level, risk_score = "low", min(34, 15 + counts["mid"] * 6 + counts["low"] * 3)
    else:
        level, risk_score = "safe", 5

    # 同一个高危词重复出现，也应提高风险分
    repeat_bonus = min(15, max(0, len(hits) - len(violations)) * 2)
    if repeat_bonus:
        risk_score = min(100, risk_score + repeat_bonus)

    annotated = ""
    cursor = 0
    for start, end, word in hits:
        annotated += html_lib.escape(text[cursor:start])
        annotated += (
            '<mark class="risk-mark risk-' + VIOLATION_META[word]["severity"] + '">'
            + html_lib.escape(text[start:end]) + "</mark>"
        )
        cursor = end
    annotated += html_lib.escape(text[cursor:])

    return {
        "text": text,
        "hits": hits,
        "violations": violations,
        "counts": counts,
        "level": level,
        "level_label": LEVEL_META[level]["label"],
        "risk_score": risk_score,
        "score": max(0, 100 - risk_score),
        "annotated": annotated,
        "total": len(hits),
    }


def sanitize(text: str) -> tuple[str, list[tuple[str, str]]]:
    """单次扫描替换，替换结果不会被二次扫描。"""
    text = _normalize(text)
    out, replaced = [], []
    i = 0
    while i < len(text):
        matched = None
        for word in REPLACEMENT_INDEX.get(text[i], ()):
            if text.startswith(word, i):
                matched = word
                break
        if matched:
            out.append(REPLACEMENTS[matched])
            replaced.append((matched, REPLACEMENTS[matched]))
            i += len(matched)
        else:
            out.append(text[i])
            i += 1
    return "".join(out), replaced


# ---------------------------------------------------------------------------
# 3. 文本结构
# ---------------------------------------------------------------------------

def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.findall(r"[^。！？!?\n]+[。！？!?]?", text) if s.strip()]


def strip_end(text: str) -> str:
    return re.sub(r"[。！？!?，,、；;：:\s]+$", "", text).strip()


def strip_cta_clauses(sentence: str) -> str:
    parts = re.findall(r"[^，,；;]+[，,；;]?", sentence)
    kept = "".join(part for part in parts if not CTA_RE.search(part))
    if not kept.strip():
        return ""
    if re.search(r"[。！？!?]$", kept):
        return kept
    return re.sub(r"[，,；;]+$", "", kept) + "。"


def _clean_clause(text: str) -> str:
    text = strip_end(text)
    text = re.sub(r"^(我们的|我家的|本款|这款|本品)\s*", "", text)
    text = re.sub(r"^产品是", "", text)
    return _polish(text)


def _polish(text: str) -> str:
    text = re.sub(r"相关认证的优选([^，。！？]+?)品牌", r"通过相关认证的\1", text)
    text = re.sub(r"相关认证的([^，。！？]+?)品牌", r"通过相关认证的\1", text)
    text = re.sub(r"优选([^，。！？]+?)品牌", r"优质\1", text)
    text = re.sub(r"([^，。！？、\s]{2,})品牌(?=[，。！？]|$)", r"\1", text)
    text = text.replace("，天然成分", "，采用天然成分")
    text = re.sub(r"^天然成分$", "采用天然成分", text)
    return text


def humanize(sentence: str) -> str:
    sentence = re.sub(r"^(我们的|我司的|本公司的)\s*(产品|商品)\s*(是|为)?\s*", "这款", sentence)
    return _polish(sentence)


def extract_topic(text: str) -> str:
    named = re.search(r"这款\s*([\u4e00-\u9fa5]{2,4})", text)
    if named and named.group(1) not in TOPIC_STOPWORDS:
        return named.group(1)
    for term in sorted(PRODUCT_TERMS, key=len, reverse=True):
        if term in text:
            return term
    for word in re.findall(r"[\u4e00-\u9fa5]{2,6}", text):
        if word not in TOPIC_STOPWORDS and "的" not in word and not re.match(r"^(这款|那款|一个|我们|你们|他们|自己|可以|非常|真的)", word):
            return word[:10]
    return "这款产品"


def build_selling_points(sentences: list[str], limit: int = 4) -> list[str]:
    points = []
    for sentence in sentences:
        for part in re.split(r"[，,；;]", strip_end(sentence)):
            clause = _clean_clause(part)
            if not clause or len(clause) < 3 or CTA_RE.search(clause):
                continue
            point = clause[:26]
            if point not in points:
                points.append(point)
    return points[:limit]


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    chars = list(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9%]+", " ", text))
    raw = Counter()
    bonus = {}

    for term in sorted(PRODUCT_TERMS, key=len, reverse=True):
        if term in text:
            bonus[term] = 40
    for term in KEYWORD_DICTIONARY:
        if term in text:
            bonus[term] = max(bonus.get(term, 0), 30 + len(term))

    def is_char(ch: str) -> bool:
        return bool(re.match(r"[\u4e00-\u9fa5A-Za-z0-9%]", ch))

    for i, ch in enumerate(chars):
        if not is_char(ch):
            continue
        gram = ""
        for n in range(4):
            if i + n >= len(chars) or not is_char(chars[i + n]):
                break
            gram += chars[i + n]
            if len(gram) < 2 or gram in KEYWORD_STOPWORDS:
                continue
            if any(c in KEYWORD_STOP_CHARS for c in gram):
                continue
            if gram[0] in KEYWORD_BAD_STARTS:
                continue
            if any(fragment in gram for fragment in KEYWORD_BLOCK_FRAGMENTS):
                continue
            raw[gram] += 1

    scores = {}
    for word, count in raw.items():
        known = word in bonus
        suffix = any(word.endswith(item) for item in KEYWORD_SUFFIXES)
        if not known and not suffix and count < 2:
            continue
        score = count * len(word) + bonus.get(word, 0) + (8 if suffix else 0)
        scores[word] = score
    for word, score in bonus.items():
        scores.setdefault(word, score)

    selected = []
    for word, _score in sorted(scores.items(), key=lambda item: (-item[1], -len(item[0]))):
        if len(selected) >= limit:
            break
        if any(word in picked or picked in word for picked in selected):
            continue
        selected.append(word)
    return selected


def build_tags(text: str, topic: str, keywords: list[str]) -> list[str]:
    tags = []
    if topic and topic != "这款产品":
        tags.append(topic)
    for pattern, category_tags in CATEGORY_TAGS:
        if pattern.search(text):
            tags.extend(category_tags)
    for word in keywords:
        if len(word) <= 6 and re.search(r"面膜|面霜|精华|水乳|洁面|防晒|眼霜|手表|手环|耳机|咖啡|茶|零食|成分|配方|保湿|补水|提亮|续航|便携|天然|温和|清爽|耐用|颜值|性价比|苹果|樱桃|脆甜|多汁|果园|产地", word):
            tags.append(word)
            if len(tags) >= 5:
                break
    tags.extend(PLATFORMS["xiaohongshu"]["tags"])
    unique = []
    for tag in tags:
        if tag and tag not in unique and 2 <= len(tag) <= 10:
            unique.append(tag)
    return ["#" + tag for tag in unique[:7]]


def build_profile(text: str, product: str = "") -> dict:
    text = _normalize(text)
    sentences = split_sentences(text)
    stripped = [strip_cta_clauses(sentence) for sentence in sentences]
    content = [humanize(sentence) for sentence in stripped if sentence]
    if not content:
        content = [humanize(sentence) for sentence in sentences]
    topic = _normalize(product) or extract_topic(text)
    keywords = []
    for word in [topic] + extract_keywords(text, 8):
        if word not in keywords:
            keywords.append(word)
    return {
        "text": text,
        "topic": topic,
        "content": content,
        "first": strip_end(content[0]) if content else "",
        "points": build_selling_points(content),
        "keywords": keywords[:9],
        "tags": build_tags(text, topic, keywords),
    }


# ---------------------------------------------------------------------------
# 4. 渠道改写
# ---------------------------------------------------------------------------

def _pick(rng: random.Random, items):
    return rng.choice(items) if items else ""


def _fill(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def _rewrite_sentence(sentence: str, rng: random.Random, max_changes: int = 2) -> str:
    out, changes, i = [], 0, 0
    while i < len(sentence):
        matched = None
        for word in SYNONYM_INDEX.get(sentence[i], ()):
            if sentence.startswith(word, i):
                matched = word
                break
        if matched and changes < max_changes:
            out.append(_pick(rng, SYNONYMS[matched]))
            i += len(matched)
            changes += 1
        else:
            out.append(sentence[i])
            i += 1
    return "".join(out)


def _clause_parts(sentence: str) -> list[str]:
    return [part.strip() for part in re.findall(r"[^，,]+[，,]?", sentence) if part.strip()]


def _xhs_paragraphs(sentences: list[str]) -> list[str]:
    parts = []
    for sentence in sentences:
        parts.extend(_clause_parts(sentence))
    paragraphs = []
    for i in range(0, len(parts), 2):
        line = "".join(parts[i:i + 2]).rstrip("，,")
        if not re.search(r"[。！？!?]$", line):
            line += "。"
        paragraphs.append(line)
    return paragraphs


def _expansion(profile: dict, channel: str, rng: random.Random) -> str:
    options = TEMPLATES.get(channel, {}).get("expansions", [])
    if not options or not profile["points"]:
        return ""
    return _fill(_pick(rng, options), point=profile["points"][0], topic=profile["topic"])


def rewrite(text: str, channel: str, seed: int = 0, product: str = "") -> dict:
    clean, replaced = sanitize(text)
    profile = build_profile(clean, product)
    rng = random.Random(seed)
    topic = profile["topic"]
    rewritten = [_rewrite_sentence(sentence, rng) for sentence in profile["content"]]
    channel_meta = PLATFORMS[channel]
    lines = []

    if channel == "xiaohongshu":
        lines.append("🌿 " + _fill(_pick(rng, TEMPLATES[channel]["titles"]), topic=topic))
        lines.append("")
        for index, paragraph in enumerate(_xhs_paragraphs(rewritten)):
            lines.append(paragraph + " " + channel_meta["emojis"][index % len(channel_meta["emojis"])])
            lines.append("")
        expansion = _expansion(profile, channel, rng)
        if expansion:
            lines.extend([expansion + " " + _pick(rng, channel_meta["emojis"]), ""])
        points = build_selling_points(rewritten)[:3]
        if not points and profile["first"]:
            points = [profile["first"][:26]]
        lines.append("📝 我整理的重点：")
        for index, point in enumerate(points, 1):
            lines.append(f"{index}. {point}")
        lines.append("")
        lines.append(_fill(_pick(rng, TEMPLATES[channel]["ctas"]), topic=topic))
        lines.append(" ".join(profile["tags"]))

    elif channel == "douyin":
        points = build_selling_points(rewritten)[:3] or [profile["first"][:24]]
        selling = "\n".join(f"{index}. {point}" for index, point in enumerate(points, 1))
        expansion = _expansion(profile, channel, rng)
        lines.extend([
            "【0–3 秒｜钩子】",
            f"画面：{topic}特写 + 大字字幕",
            "口播：" + _fill(_pick(rng, TEMPLATES[channel]["hooks"]), topic=topic),
            "",
            "【3–8 秒｜痛点】",
            "画面：日常使用场景 / 对比镜头",
            f"口播：选{topic}最怕两件事——买贵了，以及买回来不适合自己。",
            "",
            "【8–18 秒｜卖点】",
            "画面：分点展示产品细节",
            "口播：",
            selling,
        ])
        if expansion:
            lines.append("口播（补充）：" + expansion)
        lines.extend([
            "",
            "【18–24 秒｜反转】",
            "画面：镜头拉近，语气加重",
            "口播：" + _pick(rng, TEMPLATES[channel]["twists"]),
            "",
            "【结尾｜互动】",
            "画面：产品 + 关注引导",
            "口播：" + _fill(_pick(rng, TEMPLATES[channel]["ctas"]), topic=topic),
        ])
        body = "\n".join(lines).replace("我们", "咱").replace("您", "你")
        return _rewrite_result(channel, body, replaced, profile)

    elif channel == "gongzhonghao":
        groups = []
        size = max(1, (len(rewritten) + 1) // 2)
        for i in range(0, len(rewritten), size):
            groups.append(rewritten[i:i + size])
        lines.append("# " + _fill(_pick(rng, TEMPLATES[channel]["titles"]), topic=topic))
        lines.append("")
        lines.append(f"> 这篇不堆参数，聊聊{topic}的真实体验和选购思路。")
        lines.append("")
        labels = ["核心信息", "体验与细节"]
        expansion = _expansion(profile, channel, rng)
        for index, group in enumerate(groups):
            lines.append(f"## {index + 1}. {labels[index] if index < len(labels) else '补充信息'}")
            lines.append("")
            lines.append("".join(group))
            lines.append("")
            if index == 0 and expansion:
                lines.extend([expansion, ""])
        lines.extend([
            f"## {len(groups) + 1}. 购买建议",
            "",
            f"选购{topic}时，建议先明确使用场景和预算，再核对成分或参数、售后条款与真实评价；拿不准时优先选择支持退换、信息标注清晰的渠道。",
            "",
            "---",
            "*本文基于公开文案整理，产品功效、数据与资质请以品牌官方说明为准。*",
        ])

    elif channel == "pengyouquan":
        short = "".join(rewritten)
        if len(short) > 80:
            short = short[:80].rstrip("，。！？!?") + "…"
        lines.append(_fill(_pick(rng, TEMPLATES[channel]["hooks"]), topic=topic))
        lines.append("")
        if short:
            lines.extend([short, ""])
        expansion = _expansion(profile, channel, rng)
        if expansion and len(short) + len(expansion) < 110:
            lines.extend([expansion, ""])
        lines.append(_fill(_pick(rng, TEMPLATES[channel]["ctas"]), topic=topic))

    return _rewrite_result(channel, "\n".join(lines), replaced, profile)


def _rewrite_result(channel: str, body: str, replaced, profile: dict) -> dict:
    result_audit = audit(body)
    chars = len(re.sub(r"\s", "", body))
    return {
        "channel": channel,
        "name": PLATFORMS[channel]["name"],
        "icon": PLATFORMS[channel]["icon"],
        "text": body,
        "chars": chars,
        "hint": PLATFORMS[channel]["hint"],
        "max_chars": PLATFORMS[channel]["max_chars"],
        "audit": result_audit,
        "keywords": profile["keywords"],
        "replaced": replaced,
    }


def rewrite_all(text: str, channels: list[str], product: str = "") -> list[dict]:
    return [rewrite(text, channel, seed=0, product=product) for channel in channels]


# ---------------------------------------------------------------------------
# 5. 传播预判
# ---------------------------------------------------------------------------

DIMENSIONS = [
    ("title", "标题吸引力", 0.20, "标题能否在信息流中被注意到"),
    ("emotion", "情感强度", 0.15, "内容能否激发强烈的情绪反应"),
    ("topic", "话题性", 0.20, "内容能否引发讨论与二次传播"),
    ("utility", "实用价值", 0.15, "读者是否觉得「有用、用得上」"),
    ("interact", "互动引导", 0.10, "是否设置互动钩子引导评论与分享"),
    ("readability", "可读性", 0.10, "结构是否清晰、是否适合碎片化阅读"),
    ("originality", "原创度", 0.10, "是否有新颖视角或独特表达"),
]

BENCHMARKS = {
    "xiaohongshu": {"title": 1.2, "emotion": 1.3, "topic": 1.1, "interact": 1.2},
    "douyin": {"title": 1.4, "emotion": 1.2, "readability": 0.8, "interact": 1.1},
    "gongzhonghao": {"utility": 1.2, "readability": 1.2, "originality": 1.1},
    "pengyouquan": {"title": 0.8, "utility": 1.1, "interact": 0.8, "originality": 0.9},
}

EMOTION_WORDS = ["震惊", "惊呆", "太好了", "绝了", "救命", "哇", "爱了", "哭了", "笑死", "太棒了", "牛", "厉害", "神", "爆", "疯", "燃", "泪目"]
TOPIC_WORDS = ["为什么", "如何", "怎么", "揭秘", "真相", "内幕", "对比", "选择", "区别", "到底", "真的", "假的"]
STEP_WORDS = ["步骤", "方法", "技巧", "教程", "攻略", "指南", "清单", "注意", "建议", "首先", "其次", "最后"]
INTERACT_WORDS = ["评论", "留言", "关注", "点赞", "分享", "转发", "收藏", "讨论", "你觉得", "说说", "聊聊"]


def _clamp(value: float) -> int:
    return max(5, min(100, round(value)))


def predict(text: str, channel: str = "xiaohongshu") -> dict:
    text = _normalize(text)
    bench = BENCHMARKS.get(channel, {})
    first_line = (re.split(r"[。！？!?\n]", text) or [""])[0].strip()
    title = 50
    if 12 <= len(first_line) <= 35:
        title += 20
    elif len(first_line) > 35:
        title += 5
    if re.search(r"\d", first_line):
        title += 10
    if re.search(r"[！？!?]", first_line):
        title += 10
    if len(first_line) < 8:
        title -= 15
    scores = {"title": _clamp(title * bench.get("title", 1))}

    exclamations = text.count("！") + text.count("!")
    emotion_hits = sum(1 for word in EMOTION_WORDS if word in text)
    scores["emotion"] = _clamp((40 + exclamations * 8 + emotion_hits * 10) * bench.get("emotion", 1))

    questions = text.count("？") + text.count("?")
    topic_hits = sum(1 for word in TOPIC_WORDS if word in text)
    scores["topic"] = _clamp((40 + questions * 12 + topic_hits * 10) * bench.get("topic", 1))

    list_markers = len(re.findall(r"(?:^|\n)\s*[1-9][.、]", text))
    step_hits = sum(1 for word in STEP_WORDS if word in text)
    data_count = len(re.findall(r"\d+%", text))
    scores["utility"] = _clamp((35 + list_markers * 10 + step_hits * 8 + data_count * 8) * bench.get("utility", 1))

    interact_hits = sum(1 for word in INTERACT_WORDS if word in text)
    scores["interact"] = _clamp((30 + interact_hits * 15) * bench.get("interact", 1))

    paragraphs = len([line for line in text.split("\n") if line.strip()])
    readability = 50
    if 50 < len(text) < 500:
        readability += 15
    if 150 < len(text) < 400:
        readability += 5
    if paragraphs >= 3:
        readability += 15
    elif paragraphs == 1 and len(text) > 200:
        readability -= 10
    if len(text) > 800:
        readability -= 15
    if len(text) < 30:
        readability -= 10
    scores["readability"] = _clamp(readability * bench.get("readability", 1))

    chars = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    ratio = len(set(chars)) / max(1, len(chars))
    scores["originality"] = _clamp((35 + ratio * 65) * bench.get("originality", 1))

    total = round(sum(scores[key] * weight for key, _name, weight, _desc in DIMENSIONS))

    if total >= 80:
        potential = {"level": "爆款潜力", "color": "#c53030", "desc": "内容具备较强传播性，有望获得显著自然流量"}
    elif total >= 65:
        potential = {"level": "良好潜力", "color": "#dd6b20", "desc": "传播性不错，配合适当运营可获得较好曝光"}
    elif total >= 50:
        potential = {"level": "中等潜力", "color": "#b7791f", "desc": "具备基础传播力，但存在明显短板需要补强"}
    else:
        potential = {"level": "待优化", "color": "#718096", "desc": "传播性偏弱，建议按下方建议逐项优化"}

    ranked = sorted(DIMENSIONS, key=lambda item: scores[item[0]], reverse=True)
    best, worst = ranked[0], ranked[-1]
    attributions = []
    if scores[best[0]] >= 70:
        attributions.append(f"主驱动是{best[1]}（{scores[best[0]]} 分），建议在标题与封面中放大这一亮点。")
    if scores[worst[0]] < 50:
        attributions.append(f"主要短板是{worst[1]}（{scores[worst[0]]} 分），优先补强这一项。")
    if scores["emotion"] < 40:
        attributions.append("情绪偏平，建议加入个人故事或真实感受。")
    if scores["interact"] < 40:
        attributions.append("缺少互动钩子，结尾可以加一句提问。")

    suggestions = []
    if scores["title"] < 60:
        suggestions.append("标题控制在 15–30 字，加入数字或疑问句式。")
    if scores["emotion"] < 50:
        suggestions.append("增加真实体验、场景或情绪化表达。")
    if scores["topic"] < 50:
        suggestions.append("设置悬念、抛出问题或制造对比冲突。")
    if scores["utility"] < 50:
        suggestions.append("用分点、数据或具体步骤提升信息密度。")
    if scores["interact"] < 50:
        suggestions.append("结尾加「你怎么看？」「评论区聊聊」等钩子。")
    if scores["readability"] < 50:
        suggestions.append("增加分段、缩短句子，总字数控制在 200–500 字。")
    if scores["originality"] < 50:
        suggestions.append("加入独特视角或个人见解，避免套话。")
    if not suggestions:
        suggestions.append("各维度表现均衡，保持当前策略。")

    return {
        "scores": scores,
        "total": total,
        "potential": potential,
        "attributions": attributions,
        "suggestions": suggestions,
        "dims": DIMENSIONS,
    }


# ---------------------------------------------------------------------------
# 6. 本地文案生成（无 API 时的兜底）
# ---------------------------------------------------------------------------

GENERATION_TEMPLATES = {
    "xiaohongshu": [
        "{product}这次可以冲：{p1}，{p2}。{cta}",
        "最近在试{product}：{p1}，{p2}，整体体验不错。{cta}",
        "被问爆的{product}，我比较看重{p1}和{p2}。{cta}",
    ],
    "douyin": [
        "别再乱买{product}了！{p1}，{p2}，这才是关键。{cta}",
        "{product}怎么选？先看{p1}，再看{p2}。{cta}",
        "同样的预算，{product}我更看重{p1}和{p2}。{cta}",
    ],
    "gongzhonghao": [
        "{product}怎么选？先看{p1}，再看{p2}，最后核对售后与资质。",
        "关于{product}：{p1}，{p2}。选购前建议先明确使用场景。",
        "{product}的真实体验：{p1}，{p2}，适合的人群更值得关注。",
    ],
    "pengyouquan": [
        "最近在试{product}：{p1}，{p2}，分享给需要的朋友。",
        "{product}用了几天，{p1}，{p2}，整体挺省心。",
        "不吹不黑，{product}的{p1}和{p2}值得留意。",
    ],
}

GENERATION_CTAS = {
    "xiaohongshu": "你们还想看哪方面？评论区聊聊～",
    "douyin": "关注我，下期接着拆。",
    "gongzhonghao": "",
    "pengyouquan": "有需要的朋友可以问我。",
}


def generate_local(product: str, features: str, channel: str, count: int = 3, seed: int = 0) -> list[str]:
    """不调用 API 的本地生成，返回合规处理后的短文案。"""
    product = _normalize(product) or "这款产品"
    clean, _ = sanitize(features)
    profile = build_profile(clean)
    points = profile["points"] or ["产地直发", "品质稳定"]
    templates = GENERATION_TEMPLATES.get(channel, GENERATION_TEMPLATES["xiaohongshu"])
    cta = GENERATION_CTAS.get(channel, "")
    copies = []
    for index in range(count):
        template = templates[index % len(templates)]
        p1 = points[index % len(points)]
        p2 = points[(index + 1) % len(points)] if len(points) > 1 else p1
        text = template.format(
            product=product,
            p1=p1,
            p2=p2,
            cta=cta,
        )
        clean_text, _ = sanitize(text)
        clean_text = re.sub(r"\s+", "", clean_text)
        if len(clean_text) > 80:
            clean_text = clean_text[:79] + "…"
        copies.append(clean_text)
    return copies
