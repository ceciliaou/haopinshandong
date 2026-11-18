"""本地「内容缺口 / 方向补全」模块。

不调用任何模型：用品类知识库 + 关键词命中，找出广告文案还没讲到的方向，
给出补充理由、可补角度与可填空句式，帮助运营把内容写得更完整。
"""
from __future__ import annotations

import re

# 每个方向的：名称、关键词、为什么重要、可补充角度、可填空句式、默认权重
DIRECTIONS = {
    "origin": {
        "name": "产地与风土",
        "keywords": ["产地", "原产地", "果园", "基地", "产区", "核心产区", "农场", "庄园", "海拔", "土壤", "光照", "昼夜温差", "地理标志", "合作社", "农户", "直发"],
        "why": "农产品/食品的信任起点，能解释“为什么不一样”。",
        "angle": "补充产地、风土或种植方式，建立差异化。",
        "template": "「{product}来自____，____的土壤与昼夜温差，让它____。」",
        "weight": 1.4,
        "stage": "信任",
    },
    "variety": {
        "name": "品种与规格",
        "keywords": ["品种", "果径", "甜度", "规格", "等级", "红富士", "产地直采", "单果", "克重", "尺寸"],
        "why": "用户需要知道“我买到的具体是什么”，品种与规格比形容词更有说服力。",
        "angle": "把品种名、果径/克重、等级标准写清楚。",
        "template": "「{product}选的是____，单果____，甜度____，按____标准分级。」",
        "weight": 1.2,
        "stage": "信息",
    },
    "freshness": {
        "name": "新鲜与时效",
        "keywords": ["现摘", "现采", "现发", "当天", "24小时", "48小时", "冷链", "冰袋", "泡沫箱", "新鲜", "采摘", "发货", "到货", "顺丰", "直发"],
        "why": "生鲜/食品的“新鲜”不能只喊口号，采摘与发货时效才是证据。",
        "angle": "写清采摘时间、发货时效、冷链/包装方式。",
        "template": "「____采摘，____小时内发货，____冷链/包装，收到还是____。」",
        "weight": 1.4,
        "stage": "信任",
    },
    "taste": {
        "name": "口感与体验",
        "keywords": ["脆甜", "脆爽", "香脆", "甜度", "多汁", "爆汁", "果香", "香气", "口感", "细腻", "化渣", "鲜甜", "软糯", "嚼劲", "入口"],
        "why": "用户无法在下单前试吃/试用，需要用可感知的词建立预期。",
        "angle": "用脆、甜、多汁、香气等可感知词，最好加一个对照。",
        "template": "「入口是____的感觉，____分甜，____，和普通____相比更____。」",
        "weight": 1.3,
        "stage": "体验",
    },
    "scene": {
        "name": "使用场景",
        "keywords": ["早餐", "下午茶", "送礼", "办公室", "孩子", "家庭", "聚会", "追剧", "通勤", "露营", "野餐", "加餐"],
        "why": "没有场景，用户不知道“什么时候该买”。",
        "angle": "把产品放进一个具体的生活场景里。",
        "template": "「早上____ / 下午____ / 周末____，切一盘{product}，____。」",
        "weight": 1.0,
        "stage": "场景",
    },
    "crowd": {
        "name": "目标人群",
        "keywords": ["宝妈", "儿童", "老人", "孕妇", "孕妈", "健身", "控糖", "上班族", "学生", "敏感肌", "干皮", "油皮"],
        "why": "写给所有人，等于没写给任何人；明确人群更容易被记住。",
        "angle": "明确“适合谁 / 不适合谁”，降低决策成本。",
        "template": "「如果你____（人群/需求），{product}会更适合；如果你____，建议先____。」",
        "weight": 1.0,
        "stage": "人群",
    },
    "quality": {
        "name": "品质与检测",
        "keywords": ["检测", "农残", "溯源", "认证", "标准", "分级", "筛选", "报告", "检测报告", "质检", "糖度", "0添加"],
        "why": "“好吃/好用”是主观的，检测与标准才是可验证的。",
        "angle": "补充检测项目、抽检频率、溯源方式或分级标准。",
        "template": "「每批抽检____，检测报告编号____；____可溯源。」",
        "weight": 1.2,
        "stage": "信任",
    },
    "trust": {
        "name": "口碑与信任",
        "keywords": ["口碑", "复购", "真实评价", "资质", "品牌", "证书", "荣誉", "老客", "回购"],
        "why": "新用户需要“别人买过且愿意再买”的信号。",
        "angle": "用真实评价、复购率、资质或合作背书，注意不要编造。",
        "template": "「老客复购____次，真实评价里被提到最多的是____。」",
        "weight": 1.0,
        "stage": "信任",
    },
    "after_sales": {
        "name": "售后与保障",
        "keywords": ["包赔", "退换", "售后", "坏果", "破损", "无理由", "客服", "补发", "退款", "运费险"],
        "why": "生鲜/高客单产品，售后承诺能显著降低下单顾虑。",
        "angle": "把坏果/破损/退换规则写具体，而不是只说“放心买”。",
        "template": "「坏果/破损怎么赔、多久到账：____；____天内可____。」",
        "weight": 1.2,
        "stage": "信任",
    },
    "price": {
        "name": "价格与性价比",
        "keywords": ["价格", "实惠", "性价比", "折合", "斤", "箱", "规格", "单价", "包邮", "划算"],
        "why": "用户需要把价格换算成可比较的单位，才能判断值不值。",
        "angle": "写清规格、单价、对比口径，避免只写“便宜”。",
        "template": "「____斤/箱，折合每斤____元；和同规格相比____。」",
        "weight": 0.9,
        "stage": "决策",
    },
    "gift": {
        "name": "礼赠与包装",
        "keywords": ["礼盒", "送礼", "伴手礼", "节日", "包装", "年货", "走亲访友", "企业福利"],
        "why": "礼赠是农产品/食品的高客单场景，但常被广告忽略。",
        "angle": "补充礼盒规格、包装质感、适合的节日/对象。",
        "template": "「____礼盒，适合送____；包装是____，打开后____。」",
        "weight": 0.8,
        "stage": "场景",
    },
    "emotion": {
        "name": "产地故事与情感",
        "keywords": ["助农", "乡村", "农户", "家乡", "故事", "情怀", "坚持", "传承", "老树"],
        "why": "情绪让内容被记住，但必须建立在真实的人和事上。",
        "angle": "讲一个具体的农户/产區/传承细节，避免空泛煽情。",
        "template": "「这片果园由____打理，____年树龄，每年只做____。」",
        "weight": 0.7,
        "stage": "情绪",
    },
    "storage": {
        "name": "储存与食用",
        "keywords": ["冷藏", "常温", "保存", "存放", "保质期", "食用方法", "怎么吃", "保鲜"],
        "why": "生鲜/食品的“买回去怎么放”直接影响体验与差评率。",
        "angle": "写清冷藏/常温天数、食用方法、最佳赏味期。",
        "template": "「收到后冷藏____天 / 常温____天；吃之前____，口感更好。」",
        "weight": 0.9,
        "stage": "使用",
    },
    "usage": {
        "name": "使用方法",
        "keywords": ["怎么用", "用法", "步骤", "搭配", "食用", "适用", "用量", "频率"],
        "why": "降低使用门槛，用户才知道“买回去能不能用起来”。",
        "angle": "用 1-2-3 步写清用法、用量、频率或搭配。",
        "template": "「用法很简单：第一步____，第二步____，每周____次。」",
        "weight": 1.0,
        "stage": "使用",
    },
    "function": {
        "name": "功能与结果",
        "keywords": ["功能", "续航", "性能", "效果", "解决", "支持", "防水", "降噪", "快充", "容量"],
        "why": "参数本身不感人，要把参数翻译成用户能感知的结果。",
        "angle": "把功能翻译成“所以你能____”，而不是只罗列参数。",
        "template": "「不是只说____，而是你能____；实测/标称____。」",
        "weight": 1.2,
        "stage": "体验",
    },
    "ingredient": {
        "name": "成分与原料",
        "keywords": ["成分", "原料", "配方", "添加", "0添加", "天然", "提取", "核心成分"],
        "why": "美妆/食品用户越来越看成分，成分表比“神奇功效”更可信。",
        "angle": "写清核心成分/原料及其作用，避免医疗化表述。",
        "template": "「核心成分是____，主要作用是____；不含____。」",
        "weight": 1.2,
        "stage": "信息",
    },
    "craft": {
        "name": "工艺与制作",
        "keywords": ["工艺", "低温", "烘焙", "筛选", "加工", "手工", "传统", "发酵", "冷榨"],
        "why": "工艺决定差异，也容易形成可传播的记忆点。",
        "angle": "把工艺量化：几道筛选、多少小时、什么温度。",
        "template": "「经过____道筛选、____小时____工艺，保留了____。」",
        "weight": 1.0,
        "stage": "信息",
    },
    "design": {
        "name": "设计与外观",
        "keywords": ["设计", "材质", "颜色", "尺寸", "外观", "收纳", "便携", "重量", "颜值"],
        "why": "家居/数码/礼赠产品，外观与尺寸是决策的一部分。",
        "angle": "写清材质、尺寸、重量、颜色与收纳方式。",
        "template": "「____材质，____色，____cm，重____，收纳时____。」",
        "weight": 0.9,
        "stage": "体验",
    },
    "warranty": {
        "name": "质保与维修",
        "keywords": ["质保", "保修", "维修", "保修期", "只换不修", "上门"],
        "why": "耐用品/数码产品，质保条款比“质量好”更有说服力。",
        "angle": "写清质保年限、范围、维修/换新流程。",
        "template": "「整机质保____年，____范围内只换不修，寄修____天完成。」",
        "weight": 1.0,
        "stage": "信任",
    },
    "nutrition": {
        "name": "营养与健康",
        "keywords": ["营养", "维生素", "膳食纤维", "热量", "低卡", "花青素", "果胶", "矿物质", "轻食"],
        "why": "食品/农产品从“好吃”升级到“吃得明白”，营养信息能覆盖健康型用户。",
        "angle": "补充可验证的营养成分、热量或适合人群，不要做治疗性承诺。",
        "template": "「{product}的____含量/热量____，适合____人群；每天建议____。」",
        "weight": 1.0,
        "stage": "信息",
    },
    "season": {
        "name": "时令与节日",
        "keywords": ["时令", "当季", "应季", "季节", "节日", "年货", "中秋", "春节", "圣诞", "端午"],
        "why": "生鲜/食品有强时令性，错过季节就失去购买理由。",
        "angle": "点明当季/节日窗口，制造“现在买正合适”的理由。",
        "template": "「____季 / ____节，{product}正当时；错过要等____。」",
        "weight": 1.0,
        "stage": "场景",
    },
    "logistics": {
        "name": "物流与包装",
        "keywords": ["冷链", "顺丰", "物流", "泡沫箱", "冰袋", "发货", "到货", "破损", "包装"],
        "why": "生鲜/易碎品的体验有一半发生在路上，包装和时效决定差评率。",
        "angle": "写清包装方式、冷链/快递、发货与到货时效。",
        "template": "「用____包装 + ____冷链，____小时内发走，到货____。」",
        "weight": 1.1,
        "stage": "信任",
    },
    "certification": {
        "name": "认证与资质",
        "keywords": ["认证", "地理标志", "绿色食品", "有机", "无公害", "检测报告", "溯源", "资质", "证书"],
        "why": "认证/地理标志是可验证的差异点，比“品质好”更容易建立信任。",
        "angle": "补充认证名称、证书编号、检测报告或溯源方式。",
        "template": "「已通过____认证/检测，报告编号____，可扫码溯源。」",
        "weight": 1.1,
        "stage": "信任",
    },
    "comparison": {
        "name": "选购对比",
        "keywords": ["对比", "区别", "怎么选", "选购", "避坑", "值不值", "同价位", "同级"],
        "why": "用户往往在几个选项之间犹豫，主动给比较框架能降低决策成本。",
        "angle": "给出同价位/同品类的比较维度，明确适合与不适合。",
        "template": "「和同价位____相比，{product}的优势是____；不适合____。」",
        "weight": 0.9,
        "stage": "决策",
    },
    "reviews": {
        "name": "口碑与复购",
        "keywords": ["好评", "回头客", "复购", "老客", "评价", "口碑", "推荐", "晒单"],
        "why": "真实评价和复购是最低成本的信任背书。",
        "angle": "引用真实评价/复购数据，注意不要编造。",
        "template": "「老客复购____次，评价里被提到最多的是____。」",
        "weight": 1.0,
        "stage": "信任",
    },
    "brand": {
        "name": "品牌与荣誉",
        "keywords": ["品牌", "荣誉", "获奖", "老字号", "非遗", "创始", "年份", "传承"],
        "why": "品牌历史、奖项或非遗身份能解释“为什么是你”。",
        "angle": "补充品牌年份、奖项、非遗/老字号等可查信息。",
        "template": "「____年创立/传承，获得____荣誉，主打____。」",
        "weight": 0.8,
        "stage": "信任",
    },
    "promotion": {
        "name": "活动与赠品",
        "keywords": ["活动", "赠品", "满减", "优惠", "套餐", "会员", "团购", "拼团"],
        "why": "明确的交易理由能提升当下转化，但要写清规则避免误解。",
        "angle": "写清活动门槛、赠品、适用规格与截止时间。",
        "template": "「活动期____，赠品是____，适合____时入手。」",
        "weight": 0.8,
        "stage": "决策",
    },
    "pairing": {
        "name": "搭配与吃法",
        "keywords": ["搭配", "吃法", "榨汁", "沙拉", "烘焙", "酸奶", "冰镇", "果切", "早餐"],
        "why": "告诉用户“怎么吃”，能创造更多使用场景和复购理由。",
        "angle": "给出 2–3 种简单吃法/搭配，最好对应不同场景。",
        "template": "「早餐配____ / 下午茶做____ / 冰镇后____，三种吃法。」",
        "weight": 0.8,
        "stage": "使用",
    },
    "sustainability": {
        "name": "环保与助农",
        "keywords": ["助农", "乡村振兴", "环保", "可持续", "公益", "合作社"],
        "why": "产地故事与助农价值能形成情绪认同，但必须真实、具体。",
        "angle": "讲清合作农户、助农方式或环保包装，避免空泛口号。",
        "template": "「每卖出一箱，支持____农户/____公益；包装采用____。」",
        "weight": 0.7,
        "stage": "情绪",
    },
}

TEMPLATE_VARIANTS = {
    "origin": [
        "「{product}来自____，____的土壤与昼夜温差，让它____。」",
        "「产地故事：____（产区/海拔/树龄），____；这也是{product}____的原因。」",
    ],
    "freshness": [
        "「____采摘，____小时内发货，____冷链/包装，收到还是____。」",
        "「____点采摘、____点发走，用____包装；从枝头到餐桌只要____小时。」",
    ],
    "taste": [
        "「入口是____的感觉，____分甜，____，和普通____相比更____。」",
        "「咬开是____，甜度____，汁水____；放两天后____。」",
    ],
    "scene": [
        "「早上____ / 下午____ / 周末____，切一盘{product}，____。」",
        "「把{product}放进三个场景：____、____、____。」",
    ],
    "quality": [
        "「每批抽检____，检测报告编号____；____可溯源。」",
        "「检测不是一句“放心”：每批____、报告____、溯源方式____。」",
    ],
    "after_sales": [
        "「坏果/破损怎么赔、多久到账：____；____天内可____。」",
        "「坏果怎么赔：拍照____、审核____、到账____；是否需要寄回____。」",
    ],
    "price": [
        "「____斤/箱，折合每斤____元；和同规格相比____。」",
        "「算笔账：____个/箱，单果____g，折合每斤____元，比____。」",
    ],
    "gift": [
        "「____礼盒，适合送____；包装是____，打开后____。」",
        "「送礼场景：____礼盒，____个装，包装____，适合____。」",
    ],
    "nutrition": [
        "「{product}的____含量/热量____，适合____人群；每天建议____。」",
        "「每100g含____，热量____；适合当____，但____人群要控制量。」",
    ],
    "season": [
        "「____季 / ____节，{product}正当时；错过要等____。」",
        "「只卖____月到____月；现在下单，预计____前收到。」",
    ],
    "logistics": [
        "「用____包装 + ____冷链，____小时内发走，到货____。」",
        "「发货地____，用____快递；____省通常____天到，破损____。」",
    ],
    "certification": [
        "「已通过____认证/检测，报告编号____，可扫码溯源。」",
        "「证书/报告：____；编号____；扫码后能看到____。」",
    ],
    "reviews": [
        "「老客复购____次，评价里被提到最多的是____。」",
        "「____位老客复购，最常见评价是“____”；差评主要集中在____。」",
    ],
    "comparison": [
        "「和同价位____相比，{product}的优势是____；不适合____。」",
        "「三句话讲清区别：____；____；所以更适合____。」",
    ],
}

CATEGORY_DIRECTIONS = {
    "农产品": [
        ("origin", 1.5), ("freshness", 1.4), ("taste", 1.3), ("variety", 1.2),
        ("quality", 1.2), ("after_sales", 1.2), ("nutrition", 1.2), ("season", 1.2),
        ("reviews", 1.2), ("logistics", 1.1), ("certification", 1.1), ("scene", 1.0),
        ("comparison", 1.0), ("storage", 0.9), ("price", 0.9), ("gift", 0.8),
        ("crowd", 0.8), ("brand", 0.9), ("promotion", 0.9), ("pairing", 0.9),
        ("emotion", 0.7), ("sustainability", 0.8),
    ],
    "食品": [
        ("taste", 1.3), ("ingredient", 1.2), ("craft", 1.2), ("freshness", 1.1),
        ("quality", 1.1), ("nutrition", 1.2), ("season", 1.1), ("scene", 1.0),
        ("reviews", 1.1), ("storage", 0.9), ("logistics", 1.0), ("certification", 1.0),
        ("price", 0.8), ("gift", 0.8), ("brand", 0.9), ("pairing", 0.9),
        ("crowd", 0.8), ("comparison", 0.9), ("promotion", 0.8),
    ],
    "美妆": [
        ("ingredient", 1.4), ("function", 1.3), ("usage", 1.1), ("quality", 1.1),
        ("trust", 1.0), ("crowd", 1.0), ("reviews", 1.1), ("comparison", 1.0),
        ("certification", 1.0), ("price", 0.8), ("design", 0.8), ("brand", 0.9),
        ("promotion", 0.8),
    ],
    "数码": [
        ("function", 1.4), ("design", 1.1), ("quality", 1.1), ("warranty", 1.1),
        ("usage", 1.0), ("reviews", 1.0), ("comparison", 1.0), ("price", 0.9),
        ("scene", 0.8), ("brand", 0.9), ("promotion", 0.8), ("crowd", 0.7),
    ],
    "家居": [
        ("design", 1.2), ("function", 1.2), ("quality", 1.1), ("warranty", 1.0),
        ("usage", 1.0), ("scene", 0.9), ("reviews", 1.0), ("comparison", 1.0),
        ("price", 0.8), ("brand", 0.9), ("promotion", 0.8), ("crowd", 0.7),
    ],
    "通用": [
        ("function", 1.2), ("quality", 1.2), ("scene", 1.0), ("trust", 1.0),
        ("after_sales", 1.0), ("reviews", 1.0), ("comparison", 1.0), ("price", 0.9),
        ("brand", 0.9), ("promotion", 0.9), ("certification", 0.9), ("crowd", 0.8),
        ("emotion", 0.7),
    ],
}

CATEGORY_LABELS = ["自动识别", "农产品", "食品", "美妆", "数码", "家居", "通用"]

CATEGORY_RULES = [
    ("数码", ["苹果手机", "iPhone", "手机", "平板", "耳机", "手表", "手环", "相机", "投影", "充电宝", "数码"]),
    ("美妆", ["面膜", "面霜", "精华", "护肤", "口红", "粉底", "香水", "洁面", "防晒", "眼霜"]),
    ("家居", ["家居", "收纳", "清洁", "床品", "厨房", "沙发", "枕头", "香薰", "拖把"]),
    ("农产品", ["苹果", "樱桃", "葡萄", "草莓", "梨", "桃", "水果", "果园", "产地直发", "现摘", "农产品", "农货"]),
    ("食品", ["零食", "茶", "咖啡", "食品", "烘焙", "牛奶", "坚果", "果干", "礼盒"]),
]

NEGATION_PHRASES = ("不是", "并非", "没有", "不含", "无需", "不添加", "不使用", "不加")


def detect_category(text: str) -> str:
    text = str(text or "")
    for label, words in CATEGORY_RULES:
        if any(word in text for word in words):
            return label
    return "通用"


def _is_negated(text: str, index: int) -> bool:
    prefix = text[max(0, index - 6):index]
    if any(token in prefix for token in NEGATION_PHRASES):
        return True
    if re.search(r"[不没无]\s*$", prefix):
        return True
    # “非产地直发”算否定；“非常好吃”不算
    return "非" in prefix and "非常" not in prefix


def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
    """命中的关键词，排除「不是产地直发」这类否定句。"""
    hits = []
    for keyword in keywords:
        start = 0
        while True:
            index = text.find(keyword, start)
            if index < 0:
                break
            if not _is_negated(text, index):
                hits.append(keyword)
                break
            start = index + len(keyword)
    return hits


def _priority(weight: float) -> str:
    if weight >= 1.3:
        return "优先补"
    if weight >= 1.0:
        return "建议补"
    return "锦上添花"


def analyze(product: str, copy: str, category: str | None = None, limit: int = 5, source: str = "") -> dict:
    """扫描当前文案的方向覆盖，并对照产品资料，区分「素材已有」与「需补事实」。"""
    product = str(product or "这款产品").strip()
    copy = str(copy or "").strip()
    source = str(source or "").strip()
    if not category or category == "自动识别":
        category = detect_category(f"{product} {copy}")
    if category not in CATEGORY_DIRECTIONS:
        category = "通用"

    entries = CATEGORY_DIRECTIONS[category]
    covered, missing = [], []

    for key, weight in entries:
        direction = DIRECTIONS[key]
        hits = _keyword_hits(copy, direction["keywords"])
        source_hits = _keyword_hits(source, direction["keywords"])
        variants = TEMPLATE_VARIANTS.get(key, [direction["template"]])
        seed = sum(ord(ch) for ch in f"{product}{copy[:16]}{key}")
        template = variants[seed % len(variants)]
        item = {
            "key": key,
            "name": direction["name"],
            "why": direction["why"],
            "angle": direction["angle"],
            "template": template.format(product=product),
            "stage": direction["stage"],
            "weight": weight,
            "priority": _priority(weight),
            "available": bool(source_hits),
            "evidence": source_hits,
        }
        if hits:
            item["hits"] = hits
            covered.append(item)
        else:
            missing.append(item)

    # 新方向会扩充词库，但不应稀释核心覆盖率：分数只看权重最高的 10 个方向
    core_keys = {key for key, _ in sorted(entries, key=lambda pair: -pair[1])[:10]}
    core_total = sum(weight for key, weight in entries if key in core_keys)
    core_covered = sum(item["weight"] for item in covered if item["key"] in core_keys)
    score = round(100 * core_covered / core_total) if core_total else 0
    available_count = sum(1 for item in missing if item["available"])
    missing.sort(key=lambda item: (-(item["weight"] + (0.6 if item["available"] else 0)), item["name"]))
    recommended = missing[:limit]

    outline = []
    for index, item in enumerate(recommended[:3], 1):
        flag = "素材已有" if item["available"] else "先补事实"
        outline.append(f"{index}. 补「{item['name']}」（{flag}）：{item['angle']}")

    if not missing:
        level = "覆盖较完整"
        summary = "常见决策方向基本都提到了，可以转而做差异化表达或更具体的事实补充。"
    elif score >= 60:
        level = "有基础，但仍有缺口"
        summary = "核心信息已经建立，建议优先补 2–3 个高权重方向，让决策链更完整。"
    elif score >= 30:
        level = "方向偏窄"
        summary = "文案集中在少数卖点，用户还缺少信任、场景或售后信息。"
    else:
        level = "信息明显不足"
        summary = "目前更像一句口号，建议先补信任与场景，再谈转化。"

    if available_count:
        summary += f" 其中 {available_count} 个方向的产品资料里已有素材，可以直接补进广告。"

    return {
        "category": category,
        "score": score,
        "level": level,
        "summary": summary,
        "covered": covered,
        "missing": missing,
        "recommended": recommended,
        "outline": outline,
        "total": len(entries),
        "covered_count": len(covered),
        "available_count": available_count,
    }


def merge_copy(original: str, fills: list[dict]) -> dict:
    """把补全句插入到原文的语义位置，而不是统一粘在末尾。"""
    original = str(original or "").strip()
    if not original:
        return {"text": "", "inserted": [], "skipped": []}

    sentences = [s.strip() for s in re.findall(r"[^。！？!?；;\n]+[。！？!?；;]?", original) if s.strip()]
    if not sentences:
        sentences = [original]

    stage_transition = {
        "信任": "此外，",
        "信息": "具体来说，",
        "体验": "口感上，",
        "场景": "日常使用时，",
        "决策": "选购时，",
        "使用": "使用上，",
    }
    key_prefix = {
        "after_sales": "售后方面，",
        "quality": "品质信息上，",
        "freshness": "新鲜度上，",
        "logistics": "物流包装上，",
        "spec": "规格上，",
        "variety": "规格上，",
        "price": "价格上，",
        "scene": "日常使用时，",
        "usage": "使用上，",
        "gift": "如果是送人，",
        "reviews": "口碑方面，",
        "certification": "认证信息上，",
        "nutrition": "营养信息上，",
        "season": "时令上，",
        "brand": "品牌背景上，",
        "promotion": "活动方面，",
        "sustainability": "产地与助农方面，",
        "pairing": "吃法上，",
        "comparison": "对比来看，",
    }
    inserted, skipped = [], []
    anchor_counts: dict[int, int] = {}
    for fill in fills:
        text = str(fill.get("text", "")).strip()
        if not text:
            continue
        bare = text.rstrip("。！？!?；;")
        if not bare or bare in original:
            skipped.append(fill.get("key", ""))
            continue

        key = fill.get("key", "")
        direction = DIRECTIONS.get(key, {})
        keywords = direction.get("keywords", [])
        scores = [sum(1 for kw in keywords if kw in sentence) for sentence in sentences]
        best = max(scores) if scores else 0
        if best > 0:
            anchor = scores.index(best)
        else:
            stage = fill.get("stage", "信息")
            if stage in ("场景", "决策", "使用", "信任"):
                anchor = max(0, len(sentences) - 2)
            else:
                anchor = 0

        if not re.search(r"[。！？!?；;]$", text):
            text += "。"
        prefix = key_prefix.get(key) or stage_transition.get(fill.get("stage", "信息"), "此外，")
        lead_words = (
            "另外", "此外", "同时", "如果", "选购", "日常", "使用", "口感", "具体",
            "售后", "品质", "新鲜", "物流", "规格", "价格", "口碑", "认证", "营养",
            "时令", "品牌", "活动", "产地", "吃法", "对比",
        )
        if not text.startswith(lead_words):
            text = prefix + text
        insert_at = anchor + 1 + anchor_counts.get(anchor, 0)
        sentences.insert(insert_at, text)
        anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1
        inserted.append(key)

    # 每 2 句一段，避免补全后变成一整块文字
    paragraphs = ["".join(sentences[i:i + 2]) for i in range(0, len(sentences), 2)]
    return {"text": "\n\n".join(paragraphs), "inserted": inserted, "skipped": skipped}
