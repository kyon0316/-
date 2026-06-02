"""
fetchers/jd.py
京东搜索爬虫 —— 使用 playwright 浏览器模拟，稳定绕过反爬。
"""
import re
import time
import logging
from datetime import date
from goosewatch.config import KEYWORDS, MAX_RESULTS_PER_PLATFORM, REQUEST_DELAY

logger = logging.getLogger(__name__)

STANDARD_FIELDS = [
    "platform", "keyword", "title", "price", "original_price",
    "sales", "shop_name", "rating", "url", "sku_id",
    "collect_date", "price_change_pct"
]


def fetch_jd(keywords: list[str] = None) -> list[dict]:
    """搜索京东，返回标准化商品列表"""
    keywords = keywords or KEYWORDS
    results = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("[JD] 请安装 playwright: pip install playwright && playwright install chromium")
        return []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = context.new_page()

        # 先访问首页建立 session
        try:
            page.goto("https://www.jd.com/", timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
        except Exception:
            pass

        for kw in keywords:
            logger.info(f"[JD] 搜索关键词: {kw}")
            try:
                items = _search_jd(page, kw)
                results.extend(items)
            except Exception as e:
                logger.warning(f"[JD] 关键词 '{kw}' 抓取失败: {e}")
            time.sleep(REQUEST_DELAY)

        browser.close()

    return results


def _search_jd(page, keyword: str) -> list[dict]:
    """用 playwright 打开京东搜索页，解析商品列表"""
    from urllib.parse import quote
    today = str(date.today())
    items = []

    search_url = f"https://search.jd.com/Search?keyword={quote(keyword)}&enc=utf-8&page=1"
    page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # 滚动一下触发懒加载
    page.evaluate("window.scrollBy(0, 800)")
    page.wait_for_timeout(2000)

    # 策略1: 等待商品列表加载
    try:
        page.wait_for_selector(".gl-item", timeout=8000)
    except Exception:
        pass

    content = page.content()

    # 策略1: 解析 HTML 中的商品列表
    cards = page.query_selector_all(".gl-item")
    if cards:
        for card in cards[:MAX_RESULTS_PER_PLATFORM]:
            try:
                sku_id = card.get_attribute("data-sku") or ""
                title_el = card.query_selector(".p-name em") or card.query_selector(".p-name a em") or card.query_selector(".p-name")
                title = title_el.inner_text().strip() if title_el else ""
                if not title:
                    continue

                price_el = card.query_selector(".p-price i") or card.query_selector(".p-price strong i")
                price_text = price_el.inner_text().strip() if price_el else "0"
                price = _parse_price(price_text)

                shop_el = card.query_selector(".p-shop a") or card.query_selector(".p-shop span")
                shop_name = shop_el.inner_text().strip() if shop_el else "京东自营"

                commit_el = card.query_selector(".p-commit a") or card.query_selector(".p-commit strong")
                sales_text = commit_el.inner_text().strip() if commit_el else "0"
                sales = _parse_sales(sales_text)

                link = f"https://item.jd.com/{sku_id}.html" if sku_id else ""

                items.append({
                    "platform": "京东", "keyword": keyword, "title": title,
                    "price": price, "original_price": price, "sales": sales,
                    "shop_name": shop_name, "rating": None, "url": link,
                    "sku_id": sku_id, "collect_date": today, "price_change_pct": None,
                })
            except Exception as e:
                logger.debug(f"[JD] 单条解析失败: {e}")
        if items:
            logger.info(f"[JD] '{keyword}' HTML解析获取 {len(items)} 条")
            return items

    # 策略2: 从页面内嵌 JS 数据提取
    items = _extract_from_js(content, keyword, today)
    if items:
        logger.info(f"[JD] '{keyword}' JS数据提取 {len(items)} 条")
        return items

    logger.info(f"[JD] '{keyword}' 获取 0 条")
    return items


def _extract_from_js(content: str, keyword: str, today: str) -> list[dict]:
    """从京东页面内嵌 JS 变量中提取商品数据"""
    items = []

    # 京东新版本在 <script> 中有初始数据
    # 尝试匹配 price 等 JSON 数据
    patterns = [
        # 搜索页面的商品卡片 JSON
        r'"skuId"\s*:\s*"?(\d+)"?.*?"imageurl"\s*:\s*"([^"]+)".*?"name"\s*:\s*"([^"]+)"',
        # wareInfo
        r'"wareId"\s*:\s*"?(\d+)"?.*?"warename"\s*:\s*"([^"]+)"',
        # goods 数组
        r'"sku_id"\s*:\s*"?(\d+)"?\s*,\s*"name"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            for m in matches[:MAX_RESULTS_PER_PLATFORM]:
                try:
                    sku_id = m[0]
                    title = m[1] if len(m) > 1 else m[-1]
                    items.append({
                        "platform": "京东", "keyword": keyword, "title": title,
                        "price": 0.0, "original_price": 0.0, "sales": 0,
                        "shop_name": "", "rating": None,
                        "url": f"https://item.jd.com/{sku_id}.html", "sku_id": sku_id,
                        "collect_date": today, "price_change_pct": None,
                    })
                except Exception:
                    pass
            break

    return items


def _parse_price(text: str) -> float:
    """从价格文本中提取数字"""
    text = text.replace("¥", "").replace(",", "").strip()
    try:
        return float(re.sub(r"[^\d.]", "", text) or 0)
    except ValueError:
        return 0.0


def _parse_sales(text: str) -> int:
    """'2万+' -> 20000，'3000+' -> 3000"""
    text = text.replace("+", "").replace(",", "").strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    try:
        return int(text)
    except ValueError:
        return 0
