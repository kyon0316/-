"""
notifier.py
飞书群 Webhook 通知模块。
每天聚合完成后，推送摘要 + 数据异动告警到飞书群。
"""
import logging
import requests
from datetime import date
from goosewatch.config import FEISHU_WEBHOOK_URL

logger = logging.getLogger(__name__)


def send_daily_summary(total: int, alerts: list[dict], category_stats: dict):
    """
    发送每日鹅产品市场调研摘要到飞书群。

    Args:
        total: 今日总写入条数
        alerts: 数据异动列表
        category_stats: 各品类数量，如 {"内脏": 10, "部位肉": 8, ...}
    """
    if not FEISHU_WEBHOOK_URL:
        logger.warning("[Notifier] 未配置 FEISHU_WEBHOOK_URL，跳过通知")
        return

    today = str(date.today())

    # 品类统计行
    stat_lines = "\n".join(
        f"  · {cat}: {count} 条"
        for cat, count in sorted(category_stats.items())
    )

    # 数据异动摘要（最多展示5条）
    if alerts:
        alert_lines = []
        for a in alerts[:5]:
            alert_lines.append(
                f"  ⚠️ {a.get('产品名称', '?')}｜{a.get('昨日价格', '?')} → {a.get('今日价格', '?')}"
            )
        alert_text = "\n".join(alert_lines)
        if len(alerts) > 5:
            alert_text += f"\n  ...还有 {len(alerts)-5} 条"
        alert_section = f"\n**数据异动 ({len(alerts)} 条)**\n{alert_text}"
    else:
        alert_section = "\n数据稳定，无异动"

    content = (
        f"**鹅产品市场调研日报 · {today}**\n\n"
        f"今日共采集 **{total}** 条市场信息\n\n"
        f"**各品类明细**\n{stat_lines}"
        f"{alert_section}\n\n"
        f"数据已同步至飞书多维表格"
    )

    _send_webhook(content)


def send_error_alert(error_msg: str):
    """发送报错告警"""
    if not FEISHU_WEBHOOK_URL:
        return
    today = str(date.today())
    _send_webhook(f"**鹅产品市场调研 · {today} 运行异常**\n\n{error_msg}")


def _send_webhook(text: str):
    """发送飞书 Webhook 消息（markdown 格式）"""
    payload = {
        "msg_type": "interactive",
        "card": {
            "elements": [{
                "tag": "div",
                "text": {
                    "content": text,
                    "tag": "lark_md",
                }
            }],
            "header": {
                "title": {
                    "content": "鹅产品市场调研",
                    "tag": "plain_text",
                },
                "template": "blue",
            }
        }
    }

    try:
        resp = requests.post(FEISHU_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            logger.info("[Notifier] 飞书通知发送成功")
        else:
            logger.warning(f"[Notifier] 飞书通知返回异常: {result}")
    except Exception as e:
        logger.warning(f"[Notifier] 发送飞书通知失败: {e}")
