"""
processor.py
数据清洗 / 去重 / 价格异动检测。
- 清洗：统一字段格式，去掉空 title
- 去重：同平台 + keyword + sku_id + 日期只保留一条
- 异动：与昨日数据对比，标记 price_change_pct
"""
import logging
from datetime import date, timedelta
from goosewatch.config import PRICE_CHANGE_THRESHOLD

logger = logging.getLogger(__name__)


def process(raw_items: list[dict], yesterday_items: list[dict] = None) -> tuple[list[dict], list[dict]]:
    """
    处理当天抓取的原始数据。

    Args:
        raw_items: 今天所有平台抓取的原始列表
        yesterday_items: 昨天飞书表格中已存储的数据（用于价格对比）

    Returns:
        (cleaned, alerts): 清洗后的列表，以及需要告警的价格异动列表
    """
    yesterday_items = yesterday_items or []

    # 1. 清洗：过滤空 title，价格修正
    cleaned = []
    for item in raw_items:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        try:
            price = float(item.get("price") or 0)
        except (ValueError, TypeError):
            price = 0.0
        item["title"] = title
        item["price"] = round(price, 2)
        item["original_price"] = round(float(item.get("original_price") or price), 2)
        item["sales"] = int(item.get("sales") or 0)
        cleaned.append(item)

    # 2. 去重：同平台 + keyword + sku_id 每天只保留第一条
    seen = set()
    deduped = []
    for item in cleaned:
        key = (item["platform"], item["keyword"], item.get("sku_id", ""), item["collect_date"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    logger.info(f"[Processor] 原始 {len(raw_items)} 条 → 清洗后 {len(cleaned)} → 去重后 {len(deduped)}")

    # 3. 价格异动：与昨日数据对比
    yesterday_map = {}
    for yi in yesterday_items:
        k = (yi.get("platform"), yi.get("keyword"), yi.get("sku_id", ""))
        yesterday_map[k] = float(yi.get("price") or 0)

    alerts = []
    for item in deduped:
        key = (item["platform"], item["keyword"], item.get("sku_id", ""))
        yesterday_price = yesterday_map.get(key)
        if yesterday_price and yesterday_price > 0:
            change = (item["price"] - yesterday_price) / yesterday_price
            item["price_change_pct"] = round(change * 100, 2)
            if abs(change) >= PRICE_CHANGE_THRESHOLD:
                alerts.append({
                    **item,
                    "yesterday_price": yesterday_price,
                    "change_pct": round(change * 100, 2),
                })
        else:
            item["price_change_pct"] = None

    logger.info(f"[Processor] 发现价格异动 {len(alerts)} 条")
    return deduped, alerts
