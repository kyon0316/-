"""
writer.py
飞书多维表格写入模块。
使用飞书 Bitable API v1，将鹅产品市场行情数据写入指定表格。
"""
import logging
import time
from datetime import datetime, timezone
import requests
from goosewatch.config import FEISHU_APP_ID, FEISHU_APP_SECRET, BITABLE_APP_TOKEN, BITABLE_TABLE_ID

logger = logging.getLogger(__name__)

# 飞书字段名映射（飞书多维表格中的字段名 -> 数据字典 key）
FIELD_MAP = {
    "产品名称":     "产品名称",
    "产品类别":     "产品类别",
    "参考价格":     "参考价格",
    "市场需求":     "市场需求",
    "利润评级":     "利润评级",
    "数据来源":     "数据来源",
    "备注":         "备注",
    "采集日期":     "采集日期",
    # 案例字段
    "真实品牌/企业":  "真实品牌/企业",
    "产品形态":       "产品形态",
    "价格带":         "价格带",
    "销售渠道":       "销售渠道",
    "年销售额/规模":  "年销售额/规模",
    "利润率":         "利润率",
    "亮点与启发":     "亮点与启发",
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
                if val is None:
                    continue
                # 采集日期字段：飞书 Date 类型需要毫秒时间戳
                if data_key == "采集日期" and isinstance(val, str):
                    try:
                        dt = datetime.strptime(val, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        val = int(dt.timestamp() * 1000)
                    except ValueError:
                        pass
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
            logger.error(f"[Writer] 飞书API错误 code={result.get('code')} msg={result.get('msg')}")
            logger.error(f"[Writer] 完整响应: {result}")
            if records:
                logger.info(f"[Writer] 示例record keys: {list(records[0]['fields'].keys())}")

    logger.info(f"[Writer] 共写入 {total_written} 条")
    return total_written


def fetch_yesterday_records(collect_date: str) -> list[dict]:
    """
    从飞书多维表格中获取指定日期的历史记录（用于对比）。
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
