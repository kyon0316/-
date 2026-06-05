"""
main.py
鹅产品市场调研主入口 —— 每日定时运行。
流程：互联网信息聚合 → 处理 → 写入飞书 → 通知
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
    logger.info("===== 鹅产品市场调研启动 =====")
    today = str(date.today())

    from goosewatch.aggregator import aggregate_all
    from goosewatch.processor import process
    from goosewatch.writer import write_to_bitable, fetch_yesterday_records
    from goosewatch.notifier import send_daily_summary, send_error_alert

    try:
        # ── 0. 数据源自迭代（每周自动发现新源） ──────────────────
        logger.info("--- 数据源自迭代检查 ---")
        try:
            from goosewatch.source_discoverer import discover_new_sources, get_discovery_stats
            stats = get_discovery_stats()
            logger.info(f"当前数据源: {stats['total_count']} 个 (内置{stats['builtin_count']}+自发现{stats['discovered_count']})")

            # 每周运行一次发现（周一 = 0）
            if date.today().weekday() == 0:
                new_sources = discover_new_sources()
                if new_sources:
                    logger.info(f"发现 {len(new_sources)} 个新数据源")
                else:
                    logger.info("本次未发现新数据源")
            else:
                logger.info("非周一，跳过数据源发现（每周一自动运行）")
        except Exception as e:
            logger.warning(f"数据源发现跳过: {e}")

        # ── 1. 互联网信息聚合 ──────────────────────────────────
        logger.info("--- 开始互联网信息聚合 ---")
        try:
            raw = aggregate_all()
        except Exception as e:
            logger.exception("聚合失败")
            from goosewatch.notifier import send_error_alert
            send_error_alert(f"数据聚合异常: {e}")
            return 1

        logger.info(f"--- 聚合完成，共 {len(raw)} 条原始数据 ---")

        # ── 2. 获取昨日数据用于对比 ─────────────────────────────
        yesterday = str(date.today() - timedelta(days=1))
        logger.info(f"--- 查询昨日({yesterday})历史数据 ---")
        try:
            yesterday_records = fetch_yesterday_records(yesterday)
        except Exception as e:
            logger.warning(f"查询昨日数据失败（跳过对比）: {e}")
            yesterday_records = []

        # ── 3. 数据处理 ────────────────────────────────────────
        logger.info("--- 数据处理中 ---")
        cleaned, alerts = process(raw, yesterday_records)

        # ── 4. 写入飞书多维表格 ────────────────────────────────
        logger.info(f"--- 写入飞书多维表格 ({len(cleaned)} 条待写入) ---")
        try:
            total_written = write_to_bitable(cleaned)
        except Exception as e:
            logger.exception(f"写入飞书失败: {e}")
            total_written = 0

        # ── 5. 统计各品类数量 ──────────────────────────────────
        category_stats = dict(Counter(item.get("产品类别", "未知") for item in cleaned))

        # ── 6. 发送飞书通知 ────────────────────────────────────
        logger.info("--- 发送飞书通知 ---")
        send_daily_summary(total_written, alerts, category_stats)

        logger.info(f"===== 鹅产品市场调研完成，写入 {total_written} 条，异动 {len(alerts)} 条 =====")
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
