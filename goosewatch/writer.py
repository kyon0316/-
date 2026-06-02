"""
writer.py
飞书多维表格写入模块。
使用飞书 Bitable API v1，将商品数据写入指定表格。
表格字段需提前在飞书多维表格中创建好（见 README 字段说明）。
"""
import logging
import requests
from goosewatch.config import FEISHU_APP_ID, FEISHU_APP_SECRET, BITABLE_APP_TOKEN, BITABLE_TABLE_ID

logger = logging.getLogger(__name__)

# 飞书字段名映射（飞书多维表格中的字段名 -> 数据字典 key）
FIELD_MAP = {
    "平台": "platform",
    "搜索词": "keyword",
    "商品名称": "title",
    "价格": "price",
    "原价": "original_price",
    "月销量": "sales",
    "店铺名称": "shop_name",
    "评分": "rating",
    "商品链接": "url",
    "商品ID": "sku_id",
    "采集日期": "collect_date",
    "价格变化(%)": "price_change_pct",
}


def get_access_token() -> str:
    """获取飞书 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书 Token 获取失败: {data}")
    return data["tenant_access_token"]


def write_to_bitable(items: list[dict]) -> int:
    """
    批量写入飞书多维表格。
    每次最多 500 条（飞书接口限制）。
    返回成功写入的条数。
    """
    if not items:
        logger.info("[Writer] 无数据需要写入")
        return 0

    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records/batch_create"

    total_written = 0
    batch_size = 500

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        records = []
        for item in batch:
            fields = {}
            for feishu_field, data_key in FIELD_MAP.items():
                val = item.get(data_key)
                if val is not None:
                    # 链接字段特殊处理
                    if data_key == "url" and val:
                        fields[feishu_field] = {"link": val, "text": val}
                    else:
                        fields[feishu_field] = val
            records.append({"fields": fields})

        payload = {"records": records}
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        if result.get("code") == 0:
            written = len(result.get("data", {}).get("records", []))
            total_written += written
            logger.info(f"[Writer] 批次 {i//batch_size + 1}: 写入 {written} 条")
        else:
            logger.warning(f"[Writer] 批次写入部分失败: {result}")

    logger.info(f"[Writer] 共写入 {total_written} 条")
    return total_written


def fetch_yesterday_records(collect_date: str) -> list[dict]:
    """
    从飞书多维表格中获取指定日期的历史记录（用于价格对比）。
    collect_date: 'YYYY-MM-DD'
    """
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records"

    params = {
        "filter": f'CurrentValue.[采集日期] = "{collect_date}"',
        "page_size": 500,
    }

    all_records = []
    page_token = None

    while True:
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            logger.warning(f"[Writer] 查询历史记录失败: {data}")
            break

        records = data.get("data", {}).get("items") or []
        for rec in records:
            fields = rec.get("fields", {})
            # 转回标准格式
            item = {}
            for feishu_field, data_key in FIELD_MAP.items():
                item[data_key] = fields.get(feishu_field)
            all_records.append(item)

        page_info = data.get("data", {})
        if page_info.get("has_more"):
            page_token = page_info.get("page_token")
        else:
            break

    logger.info(f"[Writer] 查询到 {collect_date} 历史记录 {len(all_records)} 条")
    return all_records
