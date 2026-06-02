"""
fetchers/taobao.py
淘宝搜索爬虫 —— 使用 h5api 内部接口 + Cookie 方式。
需要在 config 中配置 TAOBAO_COOKIE（登录后从浏览器 DevTools 复制）。

注意：淘宝反爬较强，Cookie 失效需手动更新。
"""
import time
import json
import logging
import requests
from datetime import date
from ..config import KEYWORDS, MAX_RESULTS_PER_PLATFORM, REQUEST_DELAY, USER_AGENT, TAOBAO_COOKIE

logger = logging.getLogger(__name__)


def fetch_taobao(keywords: list[str] = None) -> list[dict]:
    """搜索淘宝，返回标准化商品列表"""
    keywords = keywords or KEYWORDS
    if not TAOBAO_COOKIE:
        logger.warning("[Taobao] 未配置 TAOBAO_COOKIE，跳过淘宝抓取")
        return []

    results = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": "https://www.taobao.com/",
        "Cookie": TAOBAO_COOKIE,
    })

    for kw in keywords:
        logger.info(f"[Taobao] 搜索关键词: {kw}")
        try:
            items = _search_taobao(session, kw)
            results.extend(items)
        except Exception as e:
            logger.warning(f"[Taobao] 关键词 '{kw}' 抓取失败: {e}")
        time.sleep(REQUEST_DELAY)

    return results


def _search_taobao(session: requests.Session, keyword: str) -> list[dict]:
    """
    调用淘宝 h5api 搜索接口。
    接口来自淘宝 H5 页面的 XHR 请求，字段结构偶尔会变化。
    """
    url = "https://h5api.m.taobao.com/h5/mtop.taobao.search.main/6.0/"
    params = {
        "jsv": "2.7.0",
        "appKey": "12574478",
        "data": json.dumps({
            "params": json.dumps({
                "q": keyword,
                "pageNo": "1",
                "pageSize": str(MAX_RESULTS_PER_PLATFORM),
                "spm": "a21bo.2017.201856-taobao-item.1",
            })
        }),
    }

    resp = session.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    items = []
    today = str(date.today())

    try:
        item_list = data["data"]["itemsArray"]
    except (KeyError, TypeError):
        # 接口结构变了，fallback 到 BeautifulSoup 解析普通搜索页
        logger.warning("[Taobao] h5api 返回格式异常，改用页面解析")
        return _search_taobao_html(session, keyword)

    for raw in item_list[:MAX_RESULTS_PER_PLATFORM]:
        try:
            sku_id = raw.get("itemId", "")
            title = raw.get("title", "").replace("<br>", " ")
            price = float(raw.get("price", 0))
            original_price = float(raw.get("originalPrice", price))
            sales_text = raw.get("sold", "0")
            sales = _parse_sales(str(sales_text))
            shop_name = raw.get("nick", "")
            rating = raw.get("rateTotal", None)
            link = f"https://item.taobao.com/item.htm?id={sku_id}"

            items.append({
                "platform": "淘宝",
                "keyword": keyword,
                "title": title,
                "price": price,
                "original_price": original_price,
                "sales": sales,
                "shop_name": shop_name,
                "rating": rating,
                "url": link,
                "sku_id": str(sku_id),
                "collect_date": today,
                "price_change_pct": None,
            })
        except Exception as e:
            logger.debug(f"[Taobao] 解析单条失败: {e}")

    logger.info(f"[Taobao] '{keyword}' 获取 {len(items)} 条")
    return items


def _search_taobao_html(session: requests.Session, keyword: str) -> list[dict]:
    """Fallback：解析淘宝搜索结果页 HTML"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("请安装 beautifulsoup4")

    url = f"https://s.taobao.com/search?q={requests.utils.quote(keyword)}"
    resp = session.get(url, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    today = str(date.today())
    items = []

    for div in soup.select("div[data-id]")[:MAX_RESULTS_PER_PLATFORM]:
        try:
            sku_id = div.get("data-id", "")
            title_el = div.select_one(".title")
            title = title_el.get_text(strip=True) if title_el else ""
            price_el = div.select_one(".price strong")
            price = float(price_el.get_text(strip=True)) if price_el else 0.0
            shop_el = div.select_one(".shop")
            shop_name = shop_el.get_text(strip=True) if shop_el else ""
            link = f"https://item.taobao.com/item.htm?id={sku_id}"

            items.append({
                "platform": "淘宝",
                "keyword": keyword,
                "title": title,
                "price": price,
                "original_price": price,
                "sales": 0,
                "shop_name": shop_name,
                "rating": None,
                "url": link,
                "sku_id": str(sku_id),
                "collect_date": today,
                "price_change_pct": None,
            })
        except Exception as e:
            logger.debug(f"[Taobao HTML] 解析单条失败: {e}")

    return items


def _parse_sales(text: str) -> int:
    text = text.replace("+", "").replace("人付款", "").replace(",", "").strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    try:
        return int(text)
    except ValueError:
        return 0
