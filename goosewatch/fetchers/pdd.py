"""
fetchers/pdd.py
拼多多搜索爬虫 —— 使用 playwright 无头浏览器模拟搜索。
"""
import re
import time
import logging
from datetime import date
from goosewatch.config import KEYWORDS, MAX_RESULTS_PER_PLATFORM, REQUEST_DELAY

logger = logging.getLogger(__name__)


def fetch_pdd(keywords: list[str] = None) -> list[dict]:
    """搜索拼多多，返回标准化商品列表"""
    keywords = keywords or KEYWORDS
    results = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("[PDD] 请安装 playwright: pip install playwright && playwright install chromium")
        return []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
            viewport={"width": 412, "height": 915},
            locale="zh-CN",
        )
        page = context.new_page()

        for kw in keywords:
            logger.info(f"[PDD] 搜索关键词: {kw}")
            try:
                items = _search_pdd(page, kw)
                results.extend(items)
            except Exception as e:
                logger.warning(f"[PDD] 关键词 '{kw}' 抓取失败: {e}")
            time.sleep(REQUEST_DELAY)

        browser.close()

    return results


def _search_pdd(page, keyword: str) -> list[dict]:
    """在拼多多搜索页面抓取商品列表"""
    from urllib.parse import quote

    today = str(date.today())
    items = []

    # 拼多多移动端搜索页
    search_url = f"https://mobile.yangkeduo.com/search_result.html?search_key={quote(keyword)}"
    page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    # 滚动加载
    for _ in range(5):
        page.evaluate("window.scrollBy(0, 600)")
        page.wait_for_timeout(1000)

    content = page.content()

    # 策略1: 从页面内嵌 JSON 提取（最可靠）
    items = _extract_from_json(content, keyword, today)
    if items:
        logger.info(f"[PDD] '{keyword}' JSON提取 {len(items)} 条")
        return items

    # 策略2: HTML 选择器
    # 新版拼多多商品卡片
    selectors = [
        ".search-result-item",
        ".goods-list-item",
        "div[class*='goods']",
        "div[class*='item']",
    ]

    for sel in selectors:
        cards = page.query_selector_all(sel)
        if cards:
            for card in cards[:MAX_RESULTS_PER_PLATFORM]:
                try:
                    title_el = card.query_selector("[class*='title'], [class*='name'], [class*='desc']")
                    title = title_el.inner_text().strip() if title_el else ""
                    if not title or len(title) < 3:
                        continue

                    price_el = card.query_selector("[class*='price']")
                    price_text = price_el.inner_text().strip() if price_el else "0"
                    price = _parse_price(price_text)

                    sales_el = card.query_selector("[class*='sales'], [class*='sold'], [class*='sell']")
                    sales_text = sales_el.inner_text().strip() if sales_el else "0"
                    sales = _parse_sales(sales_text)

                    link_el = card.query_selector("a")
                    href = link_el.get_attribute("href") if link_el else ""
                    if href and not href.startswith("http"):
                        href = "https://mobile.yangkeduo.com" + href

                    sku_match = re.search(r"goods_id=(\d+)", href or "")
                    sku_id = sku_match.group(1) if sku_match else ""

                    items.append({
                        "platform": "拼多多", "keyword": keyword, "title": title,
                        "price": price, "original_price": price, "sales": sales,
                        "shop_name": "", "rating": None, "url": href,
                        "sku_id": sku_id, "collect_date": today, "price_change_pct": None,
                    })
                except Exception as e:
                    logger.debug(f"[PDD] 单条解析失败: {e}")
            if items:
                break

    if items:
        logger.info(f"[PDD] '{keyword}' HTML获取 {len(items)} 条")
    else:
        logger.info(f"[PDD] '{keyword}' 获取 0 条")
    return items


def _extract_from_json(content: str, keyword: str, today: str) -> list[dict]:
    """从拼多多页面内嵌 JSON 数据中提取商品信息"""
    import json

    items = []

    # 拼多多新版把商品数据放在 window.rawData 或 script 标签的 JSON 里
    # 尝试多种模式
    patterns = [
        r'window\.rawData\s*=\s*(\{.+?\});',
        r'"goods_list"\s*:\s*(\[.+?\])',
        r'"items"\s*:\s*(\[.+?\])',
        r'"goods_name"\s*:\s*"([^"]+)".*?"group"\s*:.*?"price"\s*:\s*(\d+)',
        r'"goodsName"\s*:\s*"([^"]+)".*?"minGroupPrice"\s*:\s*(\d+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            continue

        # 如果匹配到 goods_name 格式
        if isinstance(matches[0], tuple) and len(matches[0]) == 2:
            for title, price_fen in matches[:MAX_RESULTS_PER_PLATFORM]:
                try:
                    items.append({
                        "platform": "拼多多", "keyword": keyword, "title": title,
                        "price": round(int(price_fen) / 100, 2),
                        "original_price": round(int(price_fen) / 100, 2),
                        "sales": 0, "shop_name": "", "rating": None,
                        "url": "", "sku_id": "",
                        "collect_date": today, "price_change_pct": None,
                    })
                except Exception:
                    pass
            break

        # JSON 数组格式
        try:
            data = matches[0]
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, list):
                for g in data[:MAX_RESULTS_PER_PLATFORM]:
                    title = g.get("goods_name") or g.get("goodsName") or g.get("title") or ""
                    price_fen = g.get("price") or g.get("min_group_price") or g.get("minGroupPrice") or 0
                    sku = str(g.get("goods_id") or g.get("goodsId") or "")
                    items.append({
                        "platform": "拼多多", "keyword": keyword, "title": title,
                        "price": round(int(price_fen) / 100, 2) if int(price_fen) > 100 else float(price_fen),
                        "original_price": round(int(price_fen) / 100, 2) if int(price_fen) > 100 else float(price_fen),
                        "sales": int(g.get("sales") or g.get("sales_tip") or 0),
                        "shop_name": g.get("mall_name") or g.get("shop_name") or "",
                        "rating": None,
                        "url": f"https://mobile.yangkeduo.com/goods.html?goods_id={sku}" if sku else "",
                        "sku_id": sku,
                        "collect_date": today, "price_change_pct": None,
                    })
                break
        except (json.JSONDecodeError, ValueError):
            continue

    return items


def _parse_price(text: str) -> float:
    """从价格文本中提取数字"""
    text = text.replace("¥", "").replace(",", "").strip()
    try:
        return float(re.sub(r"[^\d.]", "", text) or 0)
    except ValueError:
        return 0.0


def _parse_sales(text: str) -> int:
    text = text.replace("+", "").replace("万人付款", "0000").replace("人付款", "").replace("已拼", "").strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    try:
        return int("".join(filter(str.isdigit, text)) or 0)
    except ValueError:
        return 0
