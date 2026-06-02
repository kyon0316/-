"""
fetchers/douyin.py
抖音电商搜索爬虫 —— 通过 playwright 访问抖音小店搜索页。
抖音反爬较强，需要登录 Cookie，且频率不宜过高。

依赖：pip install playwright && playwright install chromium
"""
import re
import time
import json
import logging
from datetime import date
from ..config import KEYWORDS, MAX_RESULTS_PER_PLATFORM, REQUEST_DELAY, DOUYIN_COOKIE

logger = logging.getLogger(__name__)


def fetch_douyin(keywords: list[str] = None) -> list[dict]:
    """搜索抖音电商，返回标准化商品列表"""
    keywords = keywords or KEYWORDS
    if not DOUYIN_COOKIE:
        logger.warning("[Douyin] 未配置 DOUYIN_COOKIE，跳过抖音抓取")
        return []

    results = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("[Douyin] 请安装 playwright: pip install playwright && playwright install chromium")
        return []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            )
        )

        # 注入 Cookie
        _inject_cookies(context, DOUYIN_COOKIE)
        page = context.new_page()

        for kw in keywords:
            logger.info(f"[Douyin] 搜索关键词: {kw}")
            try:
                items = _search_douyin(page, kw)
                results.extend(items)
            except Exception as e:
                logger.warning(f"[Douyin] 关键词 '{kw}' 抓取失败: {e}")
            time.sleep(REQUEST_DELAY * 2)  # 抖音多等一会

        browser.close()

    return results


def _inject_cookies(context, cookie_str: str):
    """把 Cookie 字符串解析后注入 playwright context"""
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".douyin.com",
                "path": "/",
            })
    if cookies:
        context.add_cookies(cookies)


def _search_douyin(page, keyword: str) -> list[dict]:
    """在抖音电商搜索页抓取商品"""
    from urllib.parse import quote

    # 抖音电商搜索入口（H5）
    url = f"https://www.douyin.com/search/{quote(keyword)}?type=product"
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    # 滚动加载更多
    for _ in range(3):
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(1500)

    today = str(date.today())
    items = []

    # 抖音商品卡片选择器（结构会随版本更新而变化，需要定期维护）
    cards = page.query_selector_all(
        "div[data-e2e='search-product-card'], "
        "div[class*='product-card'], "
        "li[class*='product-item']"
    )

    if not cards:
        logger.warning(f"[Douyin] '{keyword}' 未找到商品卡片，尝试解析网络数据")
        return _parse_douyin_network(page, keyword, today)

    for card in cards[:MAX_RESULTS_PER_PLATFORM]:
        try:
            title_el = card.query_selector("[class*='title'], [class*='name'], h3, h4")
            title = title_el.inner_text().strip() if title_el else ""
            price_el = card.query_selector("[class*='price']")
            price_text = price_el.inner_text().strip() if price_el else "0"
            price = float(re.sub(r"[^\d.]", "", price_text.split("\n")[0]) or 0)
            sales_el = card.query_selector("[class*='sale'], [class*='sold'], [class*='sell']")
            sales_text = sales_el.inner_text().strip() if sales_el else "0"
            sales = _parse_sales(sales_text)
            shop_el = card.query_selector("[class*='shop'], [class*='store']")
            shop_name = shop_el.inner_text().strip() if shop_el else ""
            link_el = card.query_selector("a")
            href = link_el.get_attribute("href") if link_el else ""
            if href and href.startswith("/"):
                href = "https://www.douyin.com" + href
            sku_match = re.search(r"id=(\d+)", href or "")
            sku_id = sku_match.group(1) if sku_match else ""

            items.append({
                "platform": "抖音",
                "keyword": keyword,
                "title": title,
                "price": price,
                "original_price": price,
                "sales": sales,
                "shop_name": shop_name,
                "rating": None,
                "url": href,
                "sku_id": sku_id,
                "collect_date": today,
                "price_change_pct": None,
            })
        except Exception as e:
            logger.debug(f"[Douyin] 解析单条失败: {e}")

    logger.info(f"[Douyin] '{keyword}' 获取 {len(items)} 条")
    return items


def _parse_douyin_network(page, keyword: str, today: str) -> list[dict]:
    """兜底：从页面源码中提取 JSON 数据块"""
    content = page.content()
    # 尝试提取 __NEXT_DATA__ 或内联 JSON
    match = re.search(r'"product_name"\s*:\s*"([^"]+)".*?"price"\s*:\s*(\d+)', content)
    items = []
    if match:
        items.append({
            "platform": "抖音",
            "keyword": keyword,
            "title": match.group(1),
            "price": round(int(match.group(2)) / 100, 2),
            "original_price": round(int(match.group(2)) / 100, 2),
            "sales": 0,
            "shop_name": "",
            "rating": None,
            "url": f"https://www.douyin.com/search/{keyword}?type=product",
            "sku_id": "",
            "collect_date": today,
            "price_change_pct": None,
        })
    return items


def _parse_sales(text: str) -> int:
    text = re.sub(r"[已付款销售]", "", text).strip()
    if "万" in text:
        return int(float(text.replace("万", "").replace("+", "")) * 10000)
    try:
        return int(re.sub(r"[^\d]", "", text) or 0)
    except ValueError:
        return 0
