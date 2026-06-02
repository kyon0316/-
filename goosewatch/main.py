"""
main.py
鹅产品监控主入口 —— 每日定时运行。
流程：抓取 → 处理 → 写入飞书 → 通知
"""
import logging
import sys
from datetime import date, timedelta
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("goosewatch.main")


def run():
    logger.info("===== 鹅产品监控启动 =====")
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))

    from goosewatch.fetchers import fetch_taobao, fetch_jd, fetch_pdd, fetch_douyin
    from goosewatch.processor import process
    from goosewatch.writer import write_to_bitable, fetch_yesterday_records
    from goosewatch.notifier import send_daily_summary, send_error_alert

    try:
        # ── 1. 抓取各平台 ──────────────────────────────────────
        logger.info("--- 开始抓取 ---")
        raw = []

        logger.info("[Step 1/4] 抓取京东")
        raw += fetch_jd()

        logger.info("[Step 2/4] 抓取淘宝")
        raw += fetch_taobao()

        logger.info("[Step 3/4] 抓取拼多多")
        raw += fetch_pdd()

        logger.info("[Step 4/4] 抓取抖音")
        raw += fetch_douyin()

        logger.info(f"--- 抓取完成，共 {len(raw)} 条原始数据 ---")

        # ── 2. 获取昨日数据用于价格对比 ───────────────────────
        logger.info(f"--- 查询昨日({yesterday})历史数据 ---")
        yesterday_records = fetch_yesterday_records(yesterday)

        # ── 3. 数据处理 ────────────────────────────────────────
        logger.info("--- 数据处理中 ---")
        cleaned, alerts = process(raw, yesterday_records)

        # ── 4. 写入飞书多维表格 ────────────────────────────────
        logger.info("--- 写入飞书多维表格 ---")
        total_written = write_to_bitable(cleaned)

        # ── 5. 统计各平台数量 ──────────────────────────────────
        platform_stats = dict(Counter(item["platform"] for item in cleaned))

        # ── 6. 发送飞书通知 ────────────────────────────────────
        logger.info("--- 发送飞书通知 ---")
        send_daily_summary(total_written, alerts, platform_stats)

        logger.info(f"===== 鹅产品监控完成，写入 {total_written} 条，异动 {len(alerts)} 条 =====")
        return 0

    except Exception as e:
        logger.exception(f"运行异常: {e}")
        try:
            from goosewatch.notifier import send_error_alert
            send_error_alert(str(e))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(run())
