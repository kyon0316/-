"""
goosewatch / config.py
全局配置：飞书凭证、搜索关键词、飞书多维表格信息
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

# ── 搜索配置 ──────────────────────────────────────────────────
KEYWORDS = ["鹅绒被", "鹅肝", "鹅掌", "鹅肉", "鹅玩具", "鹅周边"]  # 可随时扩充
MAX_RESULTS_PER_PLATFORM = 20      # 每平台每关键词最多抓取条数
PRICE_CHANGE_THRESHOLD = 0.05      # 价格变化超过 5% 则告警

# ── 反爬 / 请求配置 ───────────────────────────────────────────
REQUEST_DELAY = 2          # 请求间隔（秒），别改太小
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ── 平台 Cookie（需要手动填入或通过 Secrets 注入） ─────────────
TAOBAO_COOKIE  = os.environ.get("TAOBAO_COOKIE", "")   # 淘宝登录 Cookie
DOUYIN_COOKIE  = os.environ.get("DOUYIN_COOKIE", "")   # 抖音登录 Cookie
