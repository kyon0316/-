"""
fetchers/pdd.py
拼多多搜索爬虫 —— 使用 playwright 无头浏览器模拟搜索。
拼多多无法通过纯 requests 稳定获取，需要执行 JS。

依赖：pip install playwright && playwright install chromium
"""
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
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
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
    import re
    from urllib.parse import quote

    url = f"https://mobile.pinduoduo.com/search_result.html?search_key={quote(keyword)}"
    page.goto(url, timeout=30000, wait_until="networkidle")
    page.wait_for_timeout(3000)

    # 向下滚动触发懒加载
    for _ in range(3):
        page.evaluate("window.scrollBy(0, 1000)")
        page.wait_for_timeout(1000)

    today = str(date.today())
    items = []

    # 拼多多 HTML 结构：搜索结果卡片
    cards = page.query_selector_all("div.goods-item, li[class*='goods'], div[class*='product-item']")
    if not cards:
        # 兜底：抓取页面内所有价格+标题组合
        logger.warning("[PDD] 标准选择器未找到，尝试通用解析")
        return _parse_pdd_fallback(page, keyword, today)

    for card in cards[:MAX_RESULTS_PER_PLATFORM]:
        try:
            title_el = card.query_selector("[class*='title'], [class*='name']")
            title = title_el.inner_text().strip() if title_el else ""
            price_el = card.query_selector("[class*='price'] strong, [class*='price'] span")
            price_text = price_el.inner_text().strip() if price_el else "0"
            price = float(re.sub(r"[^\d.]", "", price_text) or 0)
            sales_el = card.query_selector("[class*='sell'], [class*='sale'], [class*='sold']")
            sales_text = sales_el.inner_text().strip() if sales_el else "0"
            sales = _parse_sales(sales_text)
            link_el = card.query_selector("a")
            href = link_el.get_attribute("href") if link_el else ""
            if href and not href.startswith("http"):
                href = "https://mobile.pinduoduo.com" + href

            sku_match = re.search(r"goods_id=(\d+)", href or "")
            sku_id = sku_match.group(1) if sku_match else ""

            items.append({
                "platform": "拼多多",
                "keyword": keyword,
                "title": title,
                "price": price,
                "original_price": price,
                "sales": sales,
                "shop_name": "",
                "rating": None,
                "url": href,
                "sku_id": sku_id,
                "collect_date": today,
                "price_change_pct": None,
            })
        except Exception as e:
            logger.debug(f"[PDD] 解析单条失败: {e}")

    logger.info(f"[PDD] '{keyword}' 获取 {len(items)} 条")
    return items


def _parse_pdd_fallback(page, keyword: str, today: str) -> list[dict]:
    """通用兜底解析：从页面 JSON 数据中提取商品信息"""
    import re
    import json

    content = page.content()
    # 尝试从内联 JSON 中提取商品数据
    pattern = r'"goods_name"\s*:\s*"([^"]+)".*?"min_group_price"\s*:\s*(\d+)'
    matches = re.findall(pattern, content)
    items = []
    for title, price_fen in matches[:MAX_RESULTS_PER_PLATFORM]:
        items.append({
            "platform": "拼多多",
            "keyword": keyword,
            "title": title,
            "price": round(int(price_fen) / 100, 2),
            "original_price": round(int(price_fen) / 100, 2),
            "sales": 0,
            "shop_name": "",
            "rating": None,
            "url": f"https://mobile.pinduoduo.com/search_result.html?search_key={keyword}",
            "sku_id": "",
            "collect_date": today,
            "price_change_pct": None,
        })
    return items


def _parse_sales(text: str) -> int:
    text = text.replace("+", "").replace("万人付款", "0000").replace("人付款", "").strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    try:
        return int("".join(filter(str.isdigit, text)) or 0)
    except ValueError:
        return 0
