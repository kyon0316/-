"""
fetchers/pdd.py
拼多多搜索爬虫 —— 使用 HTTP 请求 + JSON 解析。
拼多多移动端 API 对反爬要求相对较低。
"""
import re
import time
import json
import logging
import requests
from datetime import date
from goosewatch.config import KEYWORDS, MAX_RESULTS_PER_PLATFORM, REQUEST_DELAY, USER_AGENT

logger = logging.getLogger(__name__)


def fetch_pdd(keywords: list[str] = None) -> list[dict]:
    """搜索拼多多，返回标准化商品列表"""
    keywords = keywords or KEYWORDS
    results = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })

    for kw in keywords:
        logger.info(f"[PDD] 搜索关键词: {kw}")
        try:
            items = _search_pdd(session, kw)
            results.extend(items)
        except Exception as e:
            logger.warning(f"[PDD] 关键词 '{kw}' 抓取失败: {e}")
        time.sleep(REQUEST_DELAY)

    return results


def _search_pdd(session: requests.Session, keyword: str) -> list[dict]:
    """多渠道尝试拼多多搜索"""
    today = str(date.today())

    # 策略1: 拼多多移动端搜索页 HTML 解析
    items = _search_pdd_mobile(session, keyword, today)
    if items:
        logger.info(f"[PDD] '{keyword}' 移动端获取 {len(items)} 条")
        return items

    # 策略2: 拼多多 API 代理接口
    items = _search_pdd_api(session, keyword, today)
    if items:
        logger.info(f"[PDD] '{keyword}' API获取 {len(items)} 条")
        return items

    logger.info(f"[PDD] '{keyword}' 获取 0 条")
    return items


def _search_pdd_mobile(session: requests.Session, keyword: str, today: str) -> list[dict]:
    """拼多多移动端搜索页"""
    from urllib.parse import quote

    items = []
    try:
        url = f"https://mobile.yangkeduo.com/search_result.html?search_key={quote(keyword)}"
        resp = session.get(url, timeout=15, allow_redirects=True)
        content = resp.text

        # 拼多多页面中嵌入的 JSON 数据
        # 模式1: window.rawData
        json_match = re.search(r'window\.rawData\s*=\s*({.+?});', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                goods = _extract_goods_from_data(data)
                for g in goods[:MAX_RESULTS_PER_PLATFORM]:
                    items.append(_build_item(g, keyword, today))
                if items:
                    return items
            except (json.JSONDecodeError, KeyError):
                pass

        # 模式2: 内嵌 script 中的 store 数据
        store_match = re.search(r'"goodsList"\s*:\s*(\[.+?\])', content, re.DOTALL)
        if store_match:
            try:
                goods = json.loads(store_match.group(1))
                for g in goods[:MAX_RESULTS_PER_PLATFORM]:
                    items.append(_build_item(g, keyword, today))
                if items:
                    return items
            except json.JSONDecodeError:
                pass

        # 模式3: 正则直接匹配商品名+价格
        price_patterns = [
            r'"goods_name"\s*:\s*"([^"]+)".*?"min_group_price"\s*:\s*(\d+)',
            r'"goodsName"\s*:\s*"([^"]+)".*?"minGroupPrice"\s*:\s*(\d+)',
            r'"title":"([^"]+)".*?"price":(\d+)',
        ]
        for pat in price_patterns:
            matches = re.findall(pat, content, re.DOTALL)
            if matches:
                for title, price_val in matches[:MAX_RESULTS_PER_PLATFORM]:
                    price = float(price_val)
                    if price < 0.01:
                        price = price / 100  # 分转元
                    items.append({
                        "platform": "拼多多", "keyword": keyword, "title": title,
                        "price": round(price, 2), "original_price": round(price, 2),
                        "sales": 0, "shop_name": "", "rating": None,
                        "url": "", "sku_id": "",
                        "collect_date": today, "price_change_pct": None,
                    })
                break

    except Exception as e:
        logger.debug(f"[PDD] 移动端失败: {e}")

    return items


def _search_pdd_api(session: requests.Session, keyword: str, today: str) -> list[dict]:
    """拼多多内部 API 接口（可能随时变化）"""
    from urllib.parse import quote

    items = []
    try:
        # 拼多多搜索建议/推荐接口
        url = "https://mobile.yangkeduo.com/proxy/api/api/search"
        params = {
            "q": keyword,
            "page": 1,
            "size": MAX_RESULTS_PER_PLATFORM,
            "requery": 0,
            "pdduid": 0,
        }
        headers = {
            "User-Agent": "Android",
            "Accept": "application/json",
            "Referer": f"https://mobile.yangkeduo.com/search_result.html?search_key={quote(keyword)}",
        }
        resp = session.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        goods = _extract_goods_from_data(data)
        for g in goods[:MAX_RESULTS_PER_PLATFORM]:
            items.append(_build_item(g, keyword, today))
    except Exception as e:
        logger.debug(f"[PDD] API失败: {e}")

    return items


def _extract_goods_from_data(data: dict) -> list[dict]:
    """从各种格式的数据中提取商品列表"""
    if isinstance(data, list):
        return data
    for key in ["goods_list", "goodsList", "items", "list", "result", "data"]:
        val = data.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            for sub in ["goods_list", "goodsList", "items", "list"]:
                sub_val = val.get(sub)
                if isinstance(sub_val, list):
                    return sub_val
    return []


def _build_item(g: dict, keyword: str, today: str) -> dict:
    """将商品数据字典转为标准格式"""
    title = (g.get("goods_name") or g.get("goodsName") or g.get("title")
             or g.get("name") or g.get("goods_desc", ""))
    price_val = (g.get("min_group_price") or g.get("minGroupPrice")
                 or g.get("price") or g.get("group_price") or 0)
    price = float(price_val)
    if price > 10000:  # 可能是分
        price = round(price / 100, 2)
    elif price < 0.01 and "price_str" in g:
        try:
            price = float(re.sub(r"[^\d.]", "", g["price_str"]) or 0)
        except (ValueError, TypeError):
            pass

    sku = str(g.get("goods_id") or g.get("goodsId") or g.get("sku_id") or "")
    sales = int(g.get("sales") or g.get("sales_tip") or g.get("cnt") or 0)
    shop = g.get("mall_name") or g.get("mallName") or g.get("shop_name") or ""

    return {
        "platform": "拼多多", "keyword": keyword, "title": title,
        "price": price, "original_price": price, "sales": sales,
        "shop_name": shop, "rating": None,
        "url": f"https://mobile.yangkeduo.com/goods.html?goods_id={sku}" if sku else "",
        "sku_id": sku, "collect_date": today, "price_change_pct": None,
    }
