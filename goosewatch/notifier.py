"""
notifier.py
飞书群 Webhook 通知模块。
每天抓取完成后，推送摘要 + 价格异动告警到飞书群。
"""
import logging
import requests
from datetime import date
from goosewatch.config import FEISHU_WEBHOOK_URL

logger = logging.getLogger(__name__)


def send_daily_summary(total: int, alerts: list[dict], platform_stats: dict):
    """
    发送每日监控摘要到飞书群。

    Args:
        total: 今日总写入条数
        alerts: 价格异动列表
        platform_stats: 各平台抓取数量，如 {"京东": 40, "淘宝": 38, ...}
    """
    if not FEISHU_WEBHOOK_URL:
        logger.warning("[Notifier] 未配置 FEISHU_WEBHOOK_URL，跳过通知")
        return

    today = str(date.today())

    # 平台统计行
    stat_lines = "\n".join(
        f"  · {platform}: {count} 条"
        for platform, count in sorted(platform_stats.items())
    )

    # 价格异动摘要（最多展示5条）
    if alerts:
        alert_lines = []
        for a in alerts[:5]:
            direction = "涨" if a["change_pct"] > 0 else "降"
            alert_lines.append(
                f"  {direction} {abs(a['change_pct']):.1f}%｜{a['platform']}｜"
                f"{a['title'][:20]}｜¥{a['yesterday_price']} → ¥{a['price']}"
            )
        alert_text = "\n".join(alert_lines)
        if len(alerts) > 5:
            alert_text += f"\n  ...还有 {len(alerts)-5} 条"
        alert_section = f"\n**价格异动 ({len(alerts)} 条)**\n{alert_text}"
    else:
        alert_section = "\n价格平稳，无异动"

    content = (
        f"**鹅产品监控日报 · {today}**\n\n"
        f"今日共采集 **{total}** 条商品数据\n\n"
        f"**各平台明细**\n{stat_lines}"
        f"{alert_section}\n\n"
        f"数据已同步至飞书多维表格 ↗"
    )

    _send_webhook(content)


def send_error_alert(error_msg: str):
    """发送报错告警"""
    if not FEISHU_WEBHOOK_URL:
        return
    today = str(date.today())
    _send_webhook(f"**鹅产品监控 · {today} 运行异常**\n\n{error_msg}")


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
                    "content": "鹅产品多平台监控",
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
