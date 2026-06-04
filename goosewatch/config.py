"""
goosewatch / config.py
全局配置：飞书凭证、鹅产品调研关键词、飞书多维表格信息
"""
import os

# ── 飞书 App 凭证 ──────────────────────────────────────────────
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

# ── 飞书 Webhook（群通知） ─────────────────────────────────────
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")

# ── 飞书多维表格（Bitable） ───────────────────────────────────
BITABLE_APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN", "")  # 多维表格的 app_token
BITABLE_TABLE_ID  = os.environ.get("BITABLE_TABLE_ID", "")   # 表格 table_id

# ── 鹅产品调研配置 ─────────────────────────────────────────────
# 深加工成品鹅产品关键词（用于互联网信息搜索）
# 按5大品类分类：酱卤熟食、烧腊预制菜、鹅肝深加工、速冻调理品、休闲零食
# 利润评级: S=极高(净利30%+), A=高(净利20-30%), B=中等(净利15-20%), C=一般(净利<15%)
GOOSE_PRODUCTS = [
    # ── 酱卤熟食（最大品类，占深加工市场60%+） ──────────────────
    {"name": "整只卤鹅",       "keywords": "卤鹅 成品 批发价 利润 潮汕卤鹅",       "category": "酱卤熟食"},
    {"name": "盐水鹅",         "keywords": "盐水鹅 成品 批发价 市场 老鹅",         "category": "酱卤熟食"},
    {"name": "卤鹅翅",         "keywords": "卤鹅翅 熟食 批发价 休闲食品",         "category": "酱卤熟食"},
    {"name": "卤鹅掌",         "keywords": "卤鹅掌 熟食 批发价 零食",             "category": "酱卤熟食"},
    {"name": "卤鹅脖",         "keywords": "卤鹅脖 熟食 批发价 休闲零食",         "category": "酱卤熟食"},

    # ── 烧腊预制菜（增速最快，年增15%+） ─────────────────────
    {"name": "烧鹅预制菜",     "keywords": "烧鹅 预制菜 加热即食 批发价 供应链",   "category": "烧腊预制菜"},
    {"name": "红烧鹅块预制菜", "keywords": "红烧鹅块 预制菜 加热即食 批发价",     "category": "烧腊预制菜"},
    {"name": "鹅汤预制菜",     "keywords": "老鹅汤 预制菜 胡椒猪肚鹅汤 批发价",   "category": "烧腊预制菜"},

    # ── 鹅肝深加工（高端顶端，溢价5-10倍） ──────────────────
    {"name": "鹅肝酱",         "keywords": "鹅肝酱 法式 成品 批发价 零售价 利润",   "category": "鹅肝深加工"},
    {"name": "即食法式鹅肝",   "keywords": "法式鹅肝 即食 真空包装 批发价 高端",   "category": "鹅肝深加工"},

    # ── 速冻调理品（工业化初期，B端供应链） ──────────────────
    {"name": "鹅肉丸",         "keywords": "鹅肉丸 火锅食材 冷冻 批发价 供应链",   "category": "速冻调理品"},
    {"name": "调理鹅肉卷",     "keywords": "鹅肉卷 调理 火锅 批发价 深加工",       "category": "速冻调理品"},
    {"name": "速冻鹅肉块",     "keywords": "速冻鹅肉块 半成品 预制菜 批发价",       "category": "速冻调理品"},

    # ── 休闲零食（新兴蓝海，年轻化消费） ──────────────────
    {"name": "鹅肉干",         "keywords": "鹅肉干 手撕鹅肉 零食 批发价 零售价",   "category": "休闲零食"},
    {"name": "鹅肉肠",         "keywords": "鹅肉肠 鹅肝肠 即食熟食 批发价 利润",   "category": "休闲零食"},
    {"name": "香辣鹅脖零食",   "keywords": "香辣鹅脖 真空小包装 零食 批发价 电商", "category": "休闲零食"},
]

# 信息源配置
DATA_SOURCES = [
    {"name": "一亩田",       "url": "https://www.ymt.com",           "type": "农产品批发"},
    {"name": "1688",         "url": "https://www.1688.com",          "type": "批发平台"},
    {"name": "百度爱采购",    "url": "https://b2b.baidu.com",         "type": "B2B平台"},
    {"name": "惠农网",       "url": "https://www.cnhnb.com",         "type": "农产品行情"},
    {"name": "食品商务网",    "url": "https://price.21food.cn",       "type": "食品价格行情"},
]

MAX_RESULTS_PER_PRODUCT = 5       # 每个产品最多记录条数
PRICE_CHANGE_THRESHOLD = 0.10     # 价格变化超过 10% 则告警

# ── 反爬 / 请求配置 ───────────────────────────────────────────
REQUEST_DELAY = 2          # 请求间隔（秒），别改太小
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
