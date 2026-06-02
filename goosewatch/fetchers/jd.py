"""
fetchers/jd.py
京东搜索爬虫 —— 使用京东移动端 API，反爬较轻。
"""
import re
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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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
    """多渠道尝试京东搜索"""
    today = str(date.today())

    # 策略1: 京东移动端 JSON API (m.jd.com)
    items = _search_jd_mobile(session, keyword, today)
    if items:
        logger.info(f"[JD] '{keyword}' 移动端API获取 {len(items)} 条")
        return items

    # 策略2: PC端搜索 + 页面内嵌JSON提取
    items = _search_jd_pc(session, keyword, today)
    if items:
        logger.info(f"[JD] '{keyword}' PC端获取 {len(items)} 条")
        return items

    logger.info(f"[JD] '{keyword}' 获取 0 条")
    return items


def _search_jd_mobile(session: requests.Session, keyword: str, today: str) -> list[dict]:
    """京东移动端搜索 API"""
    from urllib.parse import quote

    items = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Referer": "https://m.jd.com/",
    }

    # 方法A: 移动端搜索页
    try:
        url = f"https://m.jd.com/search?keyword={quote(keyword)}"
        resp = session.get(url, headers=headers, timeout=15)
        content = resp.text

        # 从页面提取 goods 数据
        # 移动端页面经常内嵌 JSON
        json_match = re.search(r'window\.searchData\s*=\s*({.+?});', content)
        if not json_match:
            json_match = re.search(r'"wareList"\s*:\s*(\[.+?\])', content)
        if not json_match:
            json_match = re.search(r'"goodsList"\s*:\s*(\[.+?\])', content)

        if json_match:
            try:
                data = json_match.group(1)
                if isinstance(data, str):
                    data = json.loads(data)
                if isinstance(data, dict):
                    goods = data.get("wareList") or data.get("goodsList") or data.get("goods") or []
                elif isinstance(data, list):
                    goods = data
                else:
                    goods = []
                for g in goods[:MAX_RESULTS_PER_PLATFORM]:
                    sku = str(g.get("wareId") or g.get("skuId") or g.get("ware_id", ""))
                    title = g.get("warename") or g.get("wname") or g.get("title", "")
                    price = float(g.get("jdPrice") or g.get("jd_price") or 0)
                    shop = g.get("shopName") or g.get("shop_name", "")
                    items.append({
                        "platform": "京东", "keyword": keyword, "title": title,
                        "price": price, "original_price": price,
                        "sales": int(g.get("inOrderCount30Days") or 0),
                        "shop_name": shop, "rating": g.get("goodRate"),
                        "url": f"https://item.jd.com/{sku}.html" if sku else "",
                        "sku_id": sku, "collect_date": today, "price_change_pct": None,
                    })
                if items:
                    return items
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
    except Exception as e:
        logger.debug(f"[JD] 移动端API失败: {e}")

    # 方法B: soa.jd.com 搜索建议接口（有时包含商品数据）
    try:
        url = "https://soa.jd.com/search/suggest"
        params = {"keyword": keyword, "terminal": "m"}
        resp = session.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        goods = data.get("wareList") or data.get("result") or []
        for g in goods[:MAX_RESULTS_PER_PLATFORM]:
            sku = str(g.get("wareId") or g.get("skuId", ""))
            items.append({
                "platform": "京东", "keyword": keyword,
                "title": g.get("warename") or g.get("title", ""),
                "price": float(g.get("jdPrice") or 0),
                "original_price": float(g.get("jdPrice") or 0),
                "sales": int(g.get("inOrderCount30Days") or 0),
                "shop_name": g.get("shopName", ""),
                "rating": g.get("goodRate"),
                "url": f"https://item.jd.com/{sku}.html" if sku else "",
                "sku_id": sku, "collect_date": today, "price_change_pct": None,
            })
        if items:
            return items
    except Exception as e:
        logger.debug(f"[JD] soa API失败: {e}")

    return items


def _search_jd_pc(session: requests.Session, keyword: str, today: str) -> list[dict]:
    """京东 PC 端搜索 + 页面内嵌JSON提取"""
    from urllib.parse import quote
    items = []

    try:
        url = f"https://search.jd.com/Search?keyword={quote(keyword)}&enc=utf-8&page=1"
        resp = session.get(url, timeout=15)
        content = resp.text

        # 从页面 JS 变量中提取
        patterns = [
            r'var\s+pageData\s*=\s*({.+?});',
            r'window\.__searchData\s*=\s*({.+?});',
            r'"mainSkuInfoList"\s*:\s*(\[.+?\])',
            r'"skuId"\s*:\s*"?(\d+)"?.*?"name"\s*:\s*"([^"]{4,100})"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if not matches:
                continue

            if isinstance(matches[0], tuple) and len(matches[0]) == 2:
                # skuId + name 模式
                for sku, title in matches[:MAX_RESULTS_PER_PLATFORM]:
                    items.append({
                        "platform": "京东", "keyword": keyword, "title": title,
                        "price": 0.0, "original_price": 0.0, "sales": 0,
                        "shop_name": "", "rating": None,
                        "url": f"https://item.jd.com/{sku}.html", "sku_id": sku,
                        "collect_date": today, "price_change_pct": None,
                    })
                break

            # JSON 模式
            try:
                data = matches[0]
                if isinstance(data, str):
                    data = json.loads(data)
                goods = []
                if isinstance(data, dict):
                    goods = (data.get("mainSkuInfoList") or data.get("goodsList")
                             or data.get("wareList") or data.get("list") or [])
                elif isinstance(data, list):
                    goods = data
                for g in goods[:MAX_RESULTS_PER_PLATFORM]:
                    sku = str(g.get("skuId") or g.get("wareId") or g.get("sku_id", ""))
                    items.append({
                        "platform": "京东", "keyword": keyword,
                        "title": g.get("name") or g.get("warename") or g.get("title", ""),
                        "price": float(g.get("jdPrice") or g.get("price") or 0),
                        "original_price": float(g.get("jdPrice") or g.get("price") or 0),
                        "sales": int(g.get("inOrderCount30Days") or 0),
                        "shop_name": g.get("shopName") or g.get("shop_name", ""),
                        "rating": g.get("goodRate"),
                        "url": f"https://item.jd.com/{sku}.html" if sku else "",
                        "sku_id": sku, "collect_date": today, "price_change_pct": None,
                    })
                break
            except (json.JSONDecodeError, TypeError):
                continue

    except Exception as e:
        logger.debug(f"[JD] PC端失败: {e}")

    return items
