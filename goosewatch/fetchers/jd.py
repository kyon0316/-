"""
fetchers/jd.py
京东搜索爬虫 —— 京东价格接口相对公开，用 requests 即可。
返回字段统一为 STANDARD_FIELDS 格式。
"""
import time
import json
import logging
import requests
from datetime import date
from goosewatch.config import KEYWORDS, MAX_RESULTS_PER_PLATFORM, REQUEST_DELAY, USER_AGENT

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
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": "https://www.jd.com/",
    })

    for kw in keywords:
        logger.info(f"[JD] 搜索关键词: {kw}")
        try:
            items = _search_jd(session, kw)
            results.extend(items)
        except Exception as e:
            logger.warning(f"[JD] 关键词 '{kw}' 抓取失败: {e}")
        time.sleep(REQUEST_DELAY)

    return results


def _search_jd(session: requests.Session, keyword: str) -> list[dict]:
    """调用京东搜索接口，解析商品列表"""
    url = "https://search.jd.com/Search"
    params = {
        "keyword": keyword,
        "enc": "utf-8",
        "page": 1,
        "s": 1,
        "click": 0,
    }
    resp = session.get(url, params=params, timeout=15)
    resp.raise_for_status()

    # 京东搜索结果在 HTML 里，用 BeautifulSoup 解析
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("请安装 beautifulsoup4: pip install beautifulsoup4")

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    today = str(date.today())

    product_list = soup.select("ul.gl-warp > li.gl-item")[:MAX_RESULTS_PER_PLATFORM]
    for li in product_list:
        try:
            sku_id = li.get("data-sku", "")
            title_el = li.select_one(".p-name em") or li.select_one(".p-name")
            title = title_el.get_text(strip=True) if title_el else ""
            price_el = li.select_one(".p-price strong i")
            price = float(price_el.get_text(strip=True)) if price_el else 0.0
            shop_el = li.select_one(".p-shop a")
            shop_name = shop_el.get_text(strip=True) if shop_el else "京东自营"
            commit_el = li.select_one(".p-commit strong a")
            sales_text = commit_el.get_text(strip=True) if commit_el else "0"
            sales = _parse_sales(sales_text)
            link = f"https://item.jd.com/{sku_id}.html" if sku_id else ""

            items.append({
                "platform": "京东",
                "keyword": keyword,
                "title": title,
                "price": price,
                "original_price": price,
                "sales": sales,
                "shop_name": shop_name,
                "rating": None,
                "url": link,
                "sku_id": sku_id,
                "collect_date": today,
                "price_change_pct": None,
            })
        except Exception as e:
            logger.debug(f"[JD] 解析单条失败: {e}")

    logger.info(f"[JD] '{keyword}' 获取 {len(items)} 条")
    return items


def _parse_sales(text: str) -> int:
    """'2万+' -> 20000，'3000+' -> 3000"""
    text = text.replace("+", "").replace(",", "").strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    try:
        return int(text)
    except ValueError:
        return 0
