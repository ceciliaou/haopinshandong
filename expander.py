"""本地「素材扩写」模块。

把用户提供的简短产品素材，扩写成结构完整、可直接发布的长文案。
不调用大模型：通过事实抽取、方向匹配和本地短语库完成扩写；
只复述素材里已有的事实，缺失信息会变成补全建议，而不是编造。
"""
from __future__ import annotations

import random
import re

import content_gaps
import engine

LENGTHS = {
    "精简": 240,
    "标准": 420,
    "详细": 620,
}

STYLES = ["自然种草", "生活分享", "专业讲解", "礼赠推荐"]

SENSORY_DETAILS = [
    "能听到清脆的声响，汁水顺着果肉渗出来。",
    "甜味不腻，吃完嘴里还留着一点果香。",
    "不是寡淡的甜，而是有层次的清甜。",
    "入口先是脆，嚼两下甜味才慢慢出来。",
    "果肉细腻，纤维感不重，吃起来很顺口。",
    "冷藏之后再吃，清爽感会更明显。",
    "切开后汁水丰盈，盘底很快就能看到果汁。",
    "香气不冲，凑近闻是自然的果香。",
]

STYLE_HOOKS = {
    "自然种草": [
        "如果你也在找一款{product}，先别急着下单，这几个细节值得看完。",
        "最近认真试了{product}，发现真正影响体验的，不是包装，而是几个很具体的地方。",
        "说到{product}，大家最关心的其实就三件事：好不好吃、新不新鲜、买得放不放心。",
        "把{product}放进日常之后，才发现它不只是“好吃”两个字能概括的。",
        "如果你只记得{product}的一个优点，我希望是：{highlight}。",
        "同样是{product}，为什么有的让人记住，有的吃完就忘？差别往往在细节里。",
    ],
    "生活分享": [
        "最近家里常备{product}，早上、下午、周末都能用得上，顺手分享一下。",
        "以前买{product}总是碰运气，这次认真看了几个细节，体验确实不一样。",
        "如果你也喜欢在家里囤一点{product}，这篇可以先收藏。",
        "把{product}放进冰箱之后，随手就能搭出一顿简单早餐。",
        "最近在试{product}，没有夸张的形容，只说几个真实感受到的点。",
    ],
    "专业讲解": [
        "选{product}，先看三个维度：原料/产地、新鲜度、售后规则。",
        "关于{product}，与其听形容词，不如看几个可以核对的信息。",
        "如果你正在比较不同{product}，建议先把这篇里的几个判断标准记下来。",
        "判断{product}值不值得买，可以从口感、规格、发货和售后四件事入手。",
        "先给结论：{product}适不适合你，主要看{highlight}和你的使用场景。",
    ],
    "礼赠推荐": [
        "如果是送人，{product}既要拿得出手，也要让对方收得安心。",
        "挑{product}做伴手礼，包装、规格、发货时间这三件事比“贵不贵”更重要。",
        "最近在看适合送人的{product}，发现真正加分的不是噱头，而是细节。",
        "送{product}最怕“看起来好看，收到不新鲜”，所以我把售后和发货也一起看了。",
        "如果你也在准备节日/走访的伴手礼，{product}可以先放进备选。",
    ],
}

STYLE_CTAS = {
    "自然种草": [
        "如果你也在找{product}，可以先从这一箱开始。",
        "想吃{highlight}一口的，先把这篇收藏，按自己的场景选。",
        "你更看重口感、新鲜还是售后？评论区聊聊。",
        "有需要的朋友可以问我，按人数和场景帮你选规格。",
        "先确认规格和售后，再决定要不要下单。",
    ],
    "生活分享": [
        "家里常备一点，早上和下午都能派上用场。",
        "如果你也有类似的吃法，欢迎在评论区补充。",
        "先收藏，等下次采购时按这个标准挑。",
        "有需要的朋友可以按自己的场景选，不用一次买太多。",
    ],
    "专业讲解": [
        "把产地、规格、发货、售后四项核对完，再决定是否下单。",
        "如果你更在意其中某一项，可以带着具体需求来问。",
        "先明确使用场景，再选规格，通常比只看价格更不容易买错。",
        "以上是判断思路，具体信息以商品页和包装标注为准。",
    ],
    "礼赠推荐": [
        "送人前先确认礼盒规格、发货时间和售后规则，会更稳妥。",
        "如果是节日走访，建议提前下单，给物流留出时间。",
        "需要送人时，可以按人数和预算选规格，不必盲目追求大箱。",
        "把包装和售后一起确认好，收礼的人会更安心。",
    ],
}

TITLE_PATTERNS = [
    "{product}：好吃是基础，{trust}才是加分项",
    "关于{product}，我想说清楚这几件事",
    "从{highlight}开始，重新认识{product}",
    "{product}怎么挑？先看{highlight}",
    "把{product}放进日常，才发现{highlight}",
    "{product}｜{highlight}，才是值得复购的理由",
    "{product}的{highlight}，吃一次就记住了",
    "选{product}，别只看价格",
    "{product}：{highlight}，还有这些细节",
]

ORIGIN_LINES = [
    "它来自{origin}，这一点会直接写进{product}的味道里。",
    "先看产地：{origin}。对讲究风土的产品来说，产地不是背景，而是底色。",
    "产地信息里，{origin}是一个值得留意的细节。",
    "从{origin}发出的{product}，少了中间周转，新鲜度更容易守住。",
    "对{product}来说，产地不是玄学，{origin}会直接影响口感和稳定性。",
]

TASTE_LINES = [
    "最直观的感受是{taste}。",
    "口感上，{taste}，不是那种寡淡的甜。",
    "咬开是{taste}，{sensory}",
    "如果你喜欢{taste}的口感，这一款会对味。",
    "它的记忆点不在包装，而在入口那一瞬间：{taste}。",
]

FRESHNESS_LINES = [
    "新鲜度上，{freshness}。",
    "从采摘到发货，{freshness}，减少中间周转。",
    "对生鲜来说，{freshness}比“新鲜”两个字更有说服力。",
    "收到后按包装说明保存，口感会更稳定。",
    "发货环节也值得看：{freshness}，到手时状态更有保障。",
]

SPEC_LINES = [
    "规格上，{spec}，大小更均匀，自己吃或送人都方便。",
    "下单前先看清规格：{spec}。",
    "规格信息写得越具体，越不容易买错：{spec}。",
]

SERVICE_LINES = [
    "买水果最怕“图片好看、到手失望”。{service}，收到后先检查，有问题按售后规则处理，尝试成本更低。",
    "售后方面，{service}。对生鲜来说，这比一句“放心买”更有用。",
    "遇到坏果/破损怎么处理，提前写清楚：{service}。",
]

QUALITY_LINES = [
    "品质信息也写清楚：{quality}。",
    "除了口感，可核对的信息也很重要：{quality}。",
    "如果在意标准化，可以重点看这一项：{quality}。",
]

SCENE_LINES = [
    "早上切一盘配酸奶，下午当加餐，周末做一份水果沙拉，都比随手买零食更有满足感。",
    "办公室下午茶、露营野餐、追剧加餐，切一盘都方便。",
    "不想做复杂早餐时，洗切一盘就能上桌；家里来客人，也能当果盘。",
    "冰箱里常备一点，忙的时候不用想要吃什么，拿两个就能垫一垫。",
    "如果家里有孩子或老人，选规格适中、吃起来方便的，会更省心。",
    "切片装盒带走，通勤路上或运动后补充都合适。",
]

GIFT_LINES = [
    "如果是送人，先确认礼盒规格、包装和发货时间；这些细节比“贵不贵”更影响体验。",
    "作为伴手礼，规格整齐、包装稳妥，比堆量更有诚意。",
    "节日走访建议提前下单，给物流留出时间，也让收礼的人更好安排。",
]

STORAGE_LINES = [
    "收到后按包装说明冷藏，尽量保持干燥，吃之前再清洗。",
    "一次吃不完的，先挑出有磕碰的，剩下的按保存说明放好。",
    "想保持脆感，冷藏后拿出来回温几分钟再吃，口感会更平衡。",
]

CHOICE_LINES = [
    "选购时，先确认规格、发货和售后，再比较价格；把这几项对齐，通常不容易买错。",
    "如果更在意新鲜度，优先看采摘和发货；如果更在意性价比，先把规格换算成单果或单斤再比较。",
    "对日常吃的水果来说，规格整齐、坏果有售后，往往比单纯低价更省心。",
    "别只看“大果/中果”的字样，建议把单果克重、果径和个数一起对照。",
]

COMPARE_LINES = [
    "市面上的{product}很多，价格差得也不少。与其只看单价，不如把规格、发货和售后放在一起比较。",
    "同样的预算，有人买到的是大果，有人买到的是小果；下单前把规格和个数对齐，比较才有意义。",
    "如果只看“便宜”，很容易忽略规格和售后；把这三项放在一起看，才知道值不值。",
]

SUIT_LINES = [
    "如果你想要一款日常能吃、送人也拿得出手的{product}，它比较适合；如果更在意价格，建议先对比规格。",
    "它更适合看重口感、新鲜和售后的人；如果只追求低价，可能会觉得不够便宜。",
    "日常自吃、家里常备，或者简单装个果盘，都比较合适；送人则建议先确认礼盒规格。",
]

TRANSITIONS = [
    "再说一个容易被忽略的点。",
    "除了口感，还有一件事值得看。",
    "如果只看价格，很容易漏掉这一层。",
    "对日常吃的水果来说，这一点比包装更重要。",
    "当然，具体怎么选，还要看你的使用场景。",
    "说到这里，其实判断标准已经很清楚了。",
]

FACT_PATTERNS = {
    "origin": (["果园", "基地", "产区", "产地", "来自", "山东", "烟台", "栖霞", "海拔", "土壤", "农场"], ["直发", "发货", "现摘", "现发", "采摘", "冷链"]),
    "taste": (["脆", "甜", "多汁", "香", "细腻", "软糯", "口感", "爆汁", "化渣", "清甜"], []),
    "freshness": (["现摘", "现采", "现发", "当天", "小时", "冷链", "冰袋", "泡沫箱", "采摘", "发货", "新鲜", "直发"], []),
    "spec": (["果径", "克", "斤", "规格", "单果", "大果", "中果", "箱", "个装"], []),
    "service": (["包赔", "坏果", "退换", "售后", "补发", "退款", "破损", "运费险"], []),
    "quality": (["检测", "认证", "溯源", "绿色", "有机", "无公害", "标准", "报告"], []),
    "price": (["元", "价格", "折合", "性价比", "实惠"], []),
    "scene": (["早餐", "下午茶", "送礼", "露营", "办公室", "孩子", "家庭", "聚会"], []),
    "storage": (["冷藏", "储存", "常温", "保存"], []),
    "gift": (["礼盒", "伴手礼", "年货", "送礼", "走访"], []),
    "crowd": (["儿童", "老人", "孕妇", "健身", "控糖", "宝妈"], []),
    "pairing": (["酸奶", "沙拉", "榨汁", "烘焙", "早餐"], []),
}

FACT_NAMES = {
    "origin": "产地与风土",
    "taste": "口感与体验",
    "freshness": "新鲜与时效",
    "spec": "规格与等级",
    "service": "售后与保障",
    "quality": "品质与检测",
    "price": "价格与性价比",
    "scene": "使用场景",
    "storage": "储存方式",
    "gift": "礼赠与包装",
    "crowd": "目标人群",
    "pairing": "搭配与吃法",
    "function": "功效与功能",
    "ingredient": "成分与材料",
    "texture": "质地与肤感",
    "design": "设计与外观",
    "material": "材质与用料",
    "warranty": "质保与维修",
    "usage": "使用方式",
    "certification": "认证与检测",
}

CATEGORIES = ["农产品", "食品", "美妆", "数码", "家居", "通用"]

DETAIL_LINES = {
    "function": [
        "核心功效/功能是{fact}，具体效果因人而异。",
        "它主打{fact}，是否适合要看你的实际需求。",
    ],
    "ingredient": [
        "成分/材料里值得注意的是{fact}，具体配方或用料以包装说明为准。",
        "和{fact}相关的信息，建议再核对浓度/含量与适用人群。",
    ],
    "texture": [
        "质地/肤感：{fact}，初次用建议先局部试。",
        "实际体验上，{fact}；是否黏腻或刺激要看个人感受。",
    ],
    "design": [
        "设计/外观：{fact}。",
        "外观和尺寸：{fact}，买前先确认摆放或携带场景。",
    ],
    "material": [
        "材质/用料：{fact}，具体以商品页标注为准。",
        "用料上写着{fact}，可以再核对厚度、工艺和清洁方式。",
    ],
    "spec": [
        "规格/参数：{fact}。",
        "买前先看清规格：{fact}。",
    ],
    "warranty": [
        "质保/维修：{fact}。",
        "售后条款里写着{fact}，下单前确认范围。",
    ],
    "quality": [
        "可核对的信息：{fact}。",
        "品质/检测信息：{fact}。",
    ],
    "service": [
        "售后方面，{fact}；收到后先检查，有问题按规则处理。",
        "售后/退换：{fact}。",
    ],
    "price": [
        "价格/规格：{fact}，建议换算到单件或单次成本再比较。",
        "算账时看：{fact}。",
    ],
    "taste": [
        "口感/风味：{fact}。",
        "最直观的体验是{fact}。",
    ],
    "freshness": [
        "新鲜/时效：{fact}。",
        "发货/保鲜：{fact}。",
    ],
    "storage": [
        "保存/使用：{fact}。",
        "按说明保存：{fact}。",
    ],
    "crowd": [
        "适用人群：{fact}；不确定是否适配，先局部测试或咨询。",
        "更适合{fact}的人群；不确定是否适配，先局部测试或咨询。",
    ],
    "usage": [
        "用法：{fact}。",
        "使用步骤：{fact}，按说明来更稳妥。",
    ],
    "certification": [
        "认证/检测：{fact}。",
        "可核对的信息：{fact}。",
    ],
}

GENERIC_HOOKS = {
    "自然种草": [
        "如果你也在找{product}，先别急着下单，这几个细节值得看完。",
        "最近认真试了{product}，发现真正影响体验的，不是包装，而是几个具体的地方。",
        "说到{product}，大家最关心的其实就几件事：有没有用、适不适合、买得放不放心。",
        "把{product}放进日常之后，才发现它不只是宣传里的样子。",
        "如果你只记得{product}的一个优点，我希望是：{highlight}。",
    ],
    "生活分享": [
        "最近把{product}放进日常，顺手分享一下真实感受。",
        "以前买{product}总有点碰运气，这次认真看了几个细节，体验确实不一样。",
        "如果你也准备入手{product}，这篇可以先收藏。",
        "用了一段时间{product}，没有夸张的形容，只说几个真实感受到的点。",
    ],
    "专业讲解": [
        "选{product}，先看三个维度：核心功能、规格参数、售后规则。",
        "关于{product}，与其听形容词，不如看几个可以核对的信息。",
        "如果你正在比较不同{product}，建议先把这篇里的判断标准记下来。",
        "先给结论：{product}适不适合你，主要看{highlight}和你的使用场景。",
    ],
    "礼赠推荐": [
        "如果是送人，{product}的包装、规格和售后都要先确认。",
        "挑{product}做礼物，实用性和收礼人的使用习惯比噱头更重要。",
        "最近在看适合送人的{product}，发现真正加分的是细节。",
        "送{product}前先确认规格和发货时间，会比只看价格更稳妥。",
    ],
}

GENERIC_PROFILES = {
    "食品": {
        "titles": [
            "{product}：{highlight}，还有这些细节",
            "关于{product}，我想说清楚这几件事",
            "{product}怎么选？先看{highlight}",
            "选{product}，别只看包装",
        ],
        "scenes": [
            "早餐搭配、下午加餐、办公室抽屉里放一点，都很顺手。",
            "追剧、聚会、出门路上带着，拆开就能吃，不用额外准备。",
            "家里常备一点，忙的时候不用临时找吃的。",
        ],
        "care": [
            "开封后按包装说明保存，尽量密封、避光，注意保质期。",
            "一次吃不完的先分装，别反复开封；具体保存方式以包装为准。",
        ],
        "choice": [
            "先看配料表、规格和保质期，再看价格；配料越清楚，越容易判断。",
            "同类食品很多，重点看配料、口感和分量，不要只看“大包装”。",
        ],
        "cta": [
            "你更看重口味、配料还是性价比？评论区聊聊。",
            "先确认规格和保存方式，再决定买多少。",
            "如果你也在找{product}，可以先从一小份试起。",
        ],
        "tags": ["美食", "好物分享", "零食"],
        "priority": ["taste", "ingredient", "freshness", "spec", "quality", "service", "price", "storage"],
        "facts": {
            "taste": (["香", "脆", "甜", "辣", "咸", "口感", "好吃", "软糯", "酥", "酸"], []),
            "ingredient": (["配料", "成分", "牛奶", "坚果", "可可", "茶", "咖啡", "果干", "麦片"], []),
            "freshness": (["现做", "新鲜", "保质期", "冷链", "发货", "生产日期"], []),
            "spec": (["克", "g", "袋", "盒", "包", "规格", "片"], []),
            "quality": (["检测", "认证", "标准", "配料表", "0添加"], []),
            "service": (["售后", "退换", "包赔", "客服"], []),
            "price": (["元", "价格", "折合", "性价比"], []),
            "storage": (["保存", "冷藏", "常温", "开封"], []),
        },
    },
    "美妆": {
        "titles": [
            "关于{product}，我想说清楚这几件事",
            "选{product}，先看功效、成分和肤感",
            "{product}：{highlight}，还有这些细节",
            "把{product}用进日常，先看这几点",
        ],
        "scenes": [
            "洁面、爽肤水之后用，早晚护肤都能安排；初次用建议从局部开始。",
            "早上护肤后记得防晒，晚上再按步骤使用，别和太多猛药叠在一起。",
            "放在护肤台顺手的位置，洗完脸就能用，步骤越简单越容易坚持。",
            "出差或旅行带一支，按平时的用量用，不要频繁换产品。",
        ],
        "care": [
            "初次用先做耳后或局部测试；避开破损皮肤和眼周。",
            "按包装说明使用，不要为了追求效果叠加过量；出现持续刺痛、泛红先停用。",
            "如果痘痘/皮肤问题比较严重，建议就医，不要只靠护肤品。",
        ],
        "choice": [
            "先确认核心功效、成分和适用肤质，再看价格；不要只看“祛痘/美白”几个字。",
            "同一功效的产品很多，重点看配方、浓度、使用步骤和自己的耐受度。",
            "敏感肌先做局部测试；严重皮肤问题建议咨询专业人士。",
        ],
        "cta": [
            "你是什么肤质、最想改善什么？评论区聊聊。",
            "先确认成分和适用人群，再决定要不要入手。",
            "如果你也在找{product}，可以先从局部试用开始。",
        ],
        "tags": ["护肤", "成分党", "好物分享"],
        "priority": ["function", "ingredient", "texture", "crowd", "usage", "certification", "service", "spec"],
        "facts": {
            "function": (["祛痘", "控油", "保湿", "修护", "提亮", "抗皱", "舒缓", "清洁", "防晒"], []),
            "ingredient": (["烟酰胺", "水杨酸", "积雪草", "玻尿酸", "神经酰胺", "维C", "视黄醇", "果酸", "氨基酸", "胜肽"], []),
            "texture": (["清爽", "不黏", "好吸收", "轻薄", "滋润", "水感", "啫喱", "乳液"], []),
            "crowd": (["油皮", "干皮", "敏感肌", "痘痘肌", "混合肌", "孕妇"], []),
            "usage": (["早晚", "洁面后", "爽肤水后", "点涂", "局部", "湿敷"], []),
            "certification": (["备案", "检测", "敏感肌测试", "无酒精", "无香精"], []),
            "service": (["退换", "售后", "客服", "过敏"], []),
            "price": (["元", "ml", "g", "支", "瓶"], []),
            "spec": (["ml", "g", "支", "瓶", "片"], []),
        },
    },
    "数码": {
        "titles": [
            "{product}：{highlight}，还有这些细节",
            "关于{product}，我想说清楚这几件事",
            "选{product}，先看参数和质保",
            "{product}怎么选？先看{highlight}",
        ],
        "scenes": [
            "通勤路上、办公室、出差或运动时用，主要看便携和续航。",
            "放在桌面或随身包里，连接和充电方不方便，比参数更影响日常体验。",
            "如果你经常在外使用，优先确认重量、续航和充电方式。",
        ],
        "care": [
            "按说明书使用，注意充电/连接方式和防水等级，别用非标配件。",
            "保留包装和购买凭证，出现故障先走官方售后，不要自行拆机。",
        ],
        "choice": [
            "先确认核心功能、参数和质保，再看价格；参数要看实际使用场景。",
            "同类产品很多，重点看续航、兼容性、重量和售后，不要只看跑分。",
        ],
        "cta": [
            "你更看重功能、参数还是质保？评论区聊聊。",
            "先确认兼容性和售后，再决定要不要入手。",
            "如果你也在找{product}，可以先列出自己的三个硬需求。",
        ],
        "tags": ["数码", "科技", "好物分享"],
        "priority": ["function", "spec", "design", "usage", "warranty", "service", "price"],
        "facts": {
            "function": (["降噪", "续航", "快充", "拍摄", "性能", "连接", "蓝牙", "防水"], []),
            "spec": (["小时", "mAh", "英寸", "GB", "mm", "克", "Hz", "W"], []),
            "design": (["金属", "轻", "薄", "颜色", "材质", "便携"], []),
            "usage": (["通勤", "办公", "运动", "旅行", "连接", "充电"], []),
            "warranty": (["质保", "保修", "换新", "维修"], []),
            "service": (["售后", "退换", "客服"], []),
            "price": (["元", "价格", "折合"], []),
        },
    },
    "家居": {
        "titles": [
            "{product}：{highlight}，还有这些细节",
            "关于{product}，我想说清楚这几件事",
            "选{product}，先量尺寸、看材质",
            "{product}怎么选？先看{highlight}",
        ],
        "scenes": [
            "放在厨房、卧室、客厅或租房的小空间里，先量好尺寸再下单。",
            "日常收纳、清洁或做饭时用，顺手和好打理比“颜值”更重要。",
            "如果空间不大，优先看可折叠、可叠加或免安装的款式。",
        ],
        "care": [
            "按安装/使用说明操作，注意承重和清洁方式，别用腐蚀性清洁剂。",
            "先确认尺寸、安装条件和退换规则，大件家具尤其要看清上楼/安装费用。",
        ],
        "choice": [
            "先量尺寸、看材质和承重，再看价格；图片好看不等于适合你家。",
            "同类家居很多，重点看尺寸、材质、清洁和售后，不要只看颜色。",
        ],
        "cta": [
            "你家最需要解决哪个空间问题？评论区聊聊。",
            "先量尺寸、确认安装条件，再决定买哪一款。",
            "如果你也在找{product}，可以先从最需要的场景开始。",
        ],
        "tags": ["家居", "生活灵感", "好物分享"],
        "priority": ["material", "design", "function", "spec", "usage", "service", "price"],
        "facts": {
            "material": (["实木", "不锈钢", "棉", "竹", "塑料", "玻璃", "陶瓷"], []),
            "design": (["颜色", "尺寸", "收纳", "简约", "便携", "颜值"], []),
            "function": (["清洁", "收纳", "加热", "保温", "静音", "省空间"], []),
            "spec": (["cm", "升", "L", "kg", "层", "件"], []),
            "usage": (["厨房", "卧室", "客厅", "卫生间", "租房"], []),
            "service": (["售后", "退换", "安装"], []),
            "price": (["元", "价格", "折合"], []),
        },
    },
    "通用": {
        "titles": [
            "{product}：{highlight}，还有这些细节",
            "关于{product}，我想说清楚这几件事",
            "选{product}，先看需求和售后",
            "{product}怎么选？先看{highlight}",
        ],
        "scenes": [
            "日常使用、办公、出行或送人，先明确最主要的场景。",
            "如果是初次买，建议从基础款/小规格开始，确认适合再升级。",
        ],
        "care": [
            "按说明书使用和保存，保留购买凭证，出现问题先联系售后。",
            "先确认规格、使用条件和退换规则，避免买错。",
        ],
        "choice": [
            "先明确需求、规格和售后，再看价格；不要只看宣传词。",
            "同类产品很多，重点看核心功能、参数和售后，不要只看包装。",
        ],
        "cta": [
            "你更看重哪一点？评论区聊聊。",
            "先确认规格和售后，再决定要不要入手。",
            "如果你也在找{product}，可以先从基础款开始。",
        ],
        "tags": ["好物分享", "生活方式"],
        "priority": ["function", "quality", "spec", "service", "price"],
        "facts": {
            "function": (["省时", "便携", "收纳", "清洁", "提升效率"], []),
            "quality": (["检测", "认证", "标准", "材质"], []),
            "spec": (["cm", "g", "ml", "件", "个", "规格"], []),
            "service": (["售后", "退换", "客服"], []),
            "price": (["元", "价格", "折合"], []),
        },
    },
}

SUGGESTION_MAP = {
    "function": "function",
    "ingredient": "ingredient",
    "texture": "function",
    "crowd": "crowd",
    "usage": "usage",
    "certification": "quality",
    "service": "after_sales",
    "spec": "variety",
    "design": "design",
    "material": "design",
    "warranty": "warranty",
    "taste": "taste",
    "freshness": "freshness",
    "quality": "quality",
    "storage": "storage",
    "price": "price",
}

GENERIC_COMPARE = [
    "同类产品很多，价格差得也不少；把核心功能、规格和售后放在一起看，才知道值不值。",
    "别只看“便宜”或“参数高”，先确认自己的使用场景，再对比规格和售后。",
    "同样的预算，有人买到的是核心功能，有人买到的是包装；下单前把需求排个优先级。",
]

GENERIC_SUIT = [
    "如果你想要一款{product}解决日常需求，它比较适合；如果更在意低价，建议先对比规格。",
    "它更适合看重实际体验和售后的人；如果只追求低价，可能会觉得不够便宜。",
    "初次买建议从基础款或小规格开始，确认适合自己再升级。",
]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip(" ，,。；;：:")


def _clauses(text: str) -> list[str]:
    return [_clean(part) for part in re.split(r"[，,。；;！？!?\n]", text or "") if _clean(part)]


def extract_facts(material: str, category: str = "农产品") -> dict[str, list[str]]:
    """从原始素材中抽取事实，按品类与方向归类；不补充素材里没有的事实。"""
    profile = GENERIC_PROFILES.get(category)
    patterns = profile["facts"] if profile else FACT_PATTERNS
    clauses = _clauses(material)
    facts: dict[str, list[str]] = {key: [] for key in patterns}
    for key, (words, excludes) in patterns.items():
        for clause in clauses:
            if any(word in clause for word in words) and not any(word in clause for word in excludes):
                if clause not in facts[key]:
                    facts[key].append(clause)
    return facts


def _pick(rng: random.Random, items: list[str], seed_text: str = "") -> str:
    if not items:
        return ""
    if seed_text:
        index = sum(ord(ch) for ch in seed_text) % len(items)
        return items[index]
    return rng.choice(items)


def _sentence(text: str) -> str:
    text = _clean(text)
    if not text:
        return ""
    if not re.search(r"[。！？!?…]$", text):
        text += "。"
    return text


def _format(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def _join(paragraphs: list[str]) -> str:
    return "\n\n".join(p for p in paragraphs if p.strip())


def _target_length(channel: str, length: str) -> int:
    target = LENGTHS.get(length, LENGTHS["标准"])
    max_chars = engine.PLATFORMS.get(channel, {}).get("max_chars", 1000)
    if channel == "pengyouquan":
        return min(target, 180)
    if channel == "douyin":
        return min(target, 300)
    return min(target, max_chars - 20)


def _select_highlight(facts: dict[str, list[str]], category: str = "农产品") -> str:
    if category in GENERIC_PROFILES:
        for key in GENERIC_PROFILES[category]["priority"]:
            if facts.get(key):
                return facts[key][0]
        return "核心信息"
    for key in ("taste", "freshness", "spec", "service"):
        if facts.get(key):
            return facts[key][0]
    return "真实口感与细节"


def _build_title(
    product: str,
    facts: dict[str, list[str]],
    rng: random.Random,
    style: str,
    category: str = "农产品",
) -> str:
    highlight = _select_highlight(facts, category)
    trust = facts["service"][0] if facts.get("service") else "细节"
    patterns = GENERIC_PROFILES[category]["titles"] if category in GENERIC_PROFILES else TITLE_PATTERNS
    pattern = _pick(rng, patterns, product + style)
    title = _format(pattern, product=product, highlight=highlight, trust=trust)
    return _clean(title)


def _build_paragraphs(product: str, facts: dict[str, list[str]], channel: str, style: str, rng: random.Random) -> list[str]:
    paragraphs: list[str] = []
    highlight = _select_highlight(facts)
    hook = _pick(rng, STYLE_HOOKS.get(style, STYLE_HOOKS["自然种草"]), product + style)
    paragraphs.append(_sentence(_format(hook, product=product, highlight=highlight)))

    # 产地
    if facts.get("origin"):
        origin = facts["origin"][0]
        paragraphs.append(_sentence(_format(
            _pick(rng, ORIGIN_LINES, product + "origin"),
            product=product, origin=origin,
        )))

    # 口感
    if facts.get("taste"):
        taste = "、".join(facts["taste"][:2])
        sensory = _pick(rng, SENSORY_DETAILS, product + "sensory")
        paragraphs.append(_sentence(_format(
            _pick(rng, TASTE_LINES, product + "taste"),
            product=product, taste=taste, sensory=sensory,
        )))

    # 新鲜 / 规格 / 售后 / 品质
    if facts.get("freshness"):
        paragraphs.append(_sentence(_format(
            _pick(rng, FRESHNESS_LINES, product + "freshness"),
            product=product, freshness=facts["freshness"][0],
        )))
    if facts.get("spec"):
        paragraphs.append(_sentence(_format(
            _pick(rng, SPEC_LINES, product + "spec"),
            product=product, spec=facts["spec"][0],
        )))
    if facts.get("service"):
        paragraphs.append(_sentence(_format(
            _pick(rng, SERVICE_LINES, product + "service"),
            product=product, service=facts["service"][0],
        )))
    if facts.get("quality"):
        paragraphs.append(_sentence(_format(
            _pick(rng, QUALITY_LINES, product + "quality"),
            product=product, quality=facts["quality"][0],
        )))

    # 场景 / 储存 / 礼赠
    if facts.get("gift") or style == "礼赠推荐":
        paragraphs.append(_sentence(_pick(rng, GIFT_LINES, product + "gift")))
    paragraphs.append(_sentence(_pick(rng, SCENE_LINES, product + "scene")))
    paragraphs.append(_sentence(_pick(rng, STORAGE_LINES, product + "storage")))
    paragraphs.append(_sentence(_pick(rng, CHOICE_LINES, product + "choice")))
    paragraphs.append(_sentence(_format(_pick(rng, COMPARE_LINES, product + "compare"), product=product)))
    paragraphs.append(_sentence(_format(_pick(rng, SUIT_LINES, product + "suit"), product=product)))

    # 过渡 + CTA
    paragraphs.append(_sentence(_pick(rng, TRANSITIONS, product + "transition")))
    cta = _pick(rng, STYLE_CTAS.get(style, STYLE_CTAS["自然种草"]), product + "cta")
    paragraphs.append(_sentence(_format(cta, product=product, highlight=highlight)))
    return paragraphs


def _build_generic_paragraphs(
    product: str,
    facts: dict[str, list[str]],
    category: str,
    style: str,
    rng: random.Random,
) -> list[str]:
    profile = GENERIC_PROFILES[category]
    highlight = _select_highlight(facts, category)
    hook = _pick(rng, GENERIC_HOOKS.get(style, GENERIC_HOOKS["自然种草"]), product + style)
    paragraphs = [_sentence(_format(hook, product=product, highlight=highlight))]

    for key in profile["priority"]:
        if not facts.get(key):
            continue
        fact = facts[key][0]
        if key == "crowd":
            fact = fact.replace("适用", "").replace("人群", "").strip() or fact
        template = _pick(rng, DETAIL_LINES[key], product + key)
        paragraphs.append(_sentence(_format(template, product=product, fact=fact)))

    paragraphs.append(_sentence(_pick(rng, profile["scenes"], product + "scene")))
    paragraphs.append(_sentence(_pick(rng, profile["care"], product + "care")))
    paragraphs.append(_sentence(_pick(rng, profile["choice"], product + "choice")))
    paragraphs.append(_sentence(_format(_pick(rng, GENERIC_COMPARE, product + "compare"), product=product)))
    paragraphs.append(_sentence(_format(_pick(rng, GENERIC_SUIT, product + "suit"), product=product)))
    paragraphs.append(_sentence(_pick(rng, profile["cta"], product + "cta")))
    return paragraphs


def _trim_to_target(paragraphs: list[str], target: int) -> list[str]:
    """按段落裁剪，避免把句子从中间切断。"""
    result: list[str] = []
    total = 0
    for paragraph in paragraphs:
        if total and total + len(paragraph) + 2 > target * 1.08:
            break
        result.append(paragraph)
        total += len(paragraph) + 2
    return result


def _tags(product: str, category: str) -> str:
    if category in GENERIC_PROFILES:
        tags = list(GENERIC_PROFILES[category]["tags"]) + [category]
    else:
        tags = [category, "原产地", "好物分享"]
        if "苹果" in product:
            tags.append("苹果")
        if "水果" in product or category == "农产品":
            tags.append("水果")
    unique = []
    for tag in tags:
        if tag and tag not in unique and 2 <= len(tag) <= 10:
            unique.append(tag)
    return " ".join(f"#{tag}" for tag in unique[:4])


def expand(
    product: str,
    material: str,
    channel: str = "xiaohongshu",
    style: str = "自然种草",
    length: str = "标准",
    seed: int = 0,
    category: str = "农产品",
) -> dict:
    product = _clean(product) or "这款产品"
    material = _clean(material)
    if channel not in engine.PLATFORMS:
        channel = "xiaohongshu"
    if style not in STYLES:
        style = "自然种草"
    if length not in LENGTHS:
        length = "标准"
    if category not in CATEGORIES:
        detected = content_gaps.detect_category(f"{product} {material}")
        category = detected if detected in CATEGORIES else "通用"

    facts = extract_facts(material, category)
    rng = random.Random(f"{product}|{material}|{channel}|{style}|{length}|{seed}|{category}")

    if category in GENERIC_PROFILES:
        title = "" if channel == "pengyouquan" else _build_title(product, facts, rng, style, category)
        paragraphs = _build_generic_paragraphs(product, facts, category, style, rng)
    else:
        title = "" if channel == "pengyouquan" else _build_title(product, facts, rng, style, category)
        paragraphs = _build_paragraphs(product, facts, channel, style, rng)
    target = _target_length(channel, length)
    paragraphs = _trim_to_target(paragraphs, target)

    body = _join(paragraphs)
    if len(body) > target * 1.12:
        # 按句号截断，避免切在词中间
        cut = body[: int(target * 1.08)]
        pos = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"))
        body = cut[: pos + 1] if pos > 40 else cut

    text = (title + "\n\n" if title else "") + body
    if channel == "xiaohongshu" and len(text) < target * 1.1:
        text += "\n\n" + _tags(product, category)

    text, _ = engine.sanitize(text)
    text = re.sub(r"[ \t]+\n", "\n", text).strip()

    used_keys = [key for key, value in facts.items() if value]
    used = [FACT_NAMES.get(key, key) for key in used_keys]
    if category in GENERIC_PROFILES:
        priority = GENERIC_PROFILES[category]["priority"]
        missing_keys = [key for key in priority if not facts.get(key)]
        suggestions = []
        for key in missing_keys[:3]:
            mapped = SUGGESTION_MAP.get(key)
            if mapped in content_gaps.DIRECTIONS:
                suggestions.append(
                    f"补「{content_gaps.DIRECTIONS[mapped]['name']}」：{content_gaps.DIRECTIONS[mapped]['angle']}"
                )
    else:
        missing_keys = [key for key in ("origin", "taste", "freshness", "spec", "quality", "service") if not facts.get(key)]
        suggestions = [
            f"补「{content_gaps.DIRECTIONS[key]['name']}」：{content_gaps.DIRECTIONS[key]['angle']}"
            for key in missing_keys[:3]
            if key in content_gaps.DIRECTIONS
        ]

    fact_score = min(35, len(used_keys) * 7)
    length_score = min(25, round(25 * min(1.0, len(body) / max(target, 1))))
    structure_score = 15 if len(paragraphs) >= 4 else 8
    fullness = min(100, 20 + fact_score + length_score + structure_score)
    if fullness >= 80:
        level = "饱满"
    elif fullness >= 60:
        level = "较完整"
    else:
        level = "信息偏少"

    return {
        "product": product,
        "title": title,
        "body": body,
        "text": text,
        "channel": channel,
        "style": style,
        "length": length,
        "category": category,
        "target": target,
        "char_count": len(text),
        "fullness": fullness,
        "fullness_level": level,
        "used": used,
        "missing": [FACT_NAMES.get(key, key) for key in missing_keys],
        "suggestions": suggestions,
        "facts": facts,
        "paragraphs": len(paragraphs),
    }
