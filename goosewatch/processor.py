"""
processor.py
数据清洗 / 去重 / 异动检测。
- 清洗：统一字段格式
- 去重：同产品名称 + 采集日期只保留一条
- 异动：与昨日数据对比
"""
import logging
from goosewatch.config import PRICE_CHANGE_THRESHOLD

logger = logging.getLogger(__name__)


def process(raw_items: list[dict], yesterday_items: list[dict] = None) -> tuple[list[dict], list[dict]]:
    """
    处理当天聚合的原始数据。

    Args:
        raw_items: 今天聚合的原始列表
        yesterday_items: 昨天飞书表格中已存储的数据（用于对比）

    Returns:
        (cleaned, alerts): 清洗后的列表，以及需要告警的异动列表
    """
    yesterday_items = yesterday_items or []

    # 1. 清洗：过滤空产品名称
    cleaned = []
    for item in raw_items:
        name = (item.get("产品名称") or "").strip()
        if not name:
            continue
        item["产品名称"] = name
        cleaned.append(item)

    # 2. 去重：同产品名称 + 采集日期每天只保留第一条
    seen = set()
    deduped = []
    for item in cleaned:
        key = (item.get("产品名称", ""), item.get("采集日期", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    logger.info(f"[Processor] 原始 {len(raw_items)} 条 → 清洗后 {len(cleaned)} → 去重后 {len(deduped)}")

    # 3. 异动检测（简化版：对比是否有新数据源或价格变化）
    yesterday_map = {}
    for yi in yesterday_items:
        k = yi.get("产品名称", "")
        yesterday_map[k] = yi.get("参考价格", "")

    alerts = []
    for item in deduped:
        name = item.get("产品名称", "")
        today_price = item.get("参考价格", "")
        yesterday_price = yesterday_map.get(name)

        if yesterday_price and today_price and yesterday_price != today_price:
            alerts.append({
                **item,
                "昨日价格": yesterday_price,
                "今日价格": today_price,
            })

    logger.info(f"[Processor] 发现数据异动 {len(alerts)} 条")
    return deduped, alerts
