"""
goosewatch / source_discoverer.py
数据源自迭代模块：自动发现新的鹅产品价格数据源，定期扩展覆盖范围。

策略：
1. 通过搜索引擎（DuckDuckGo/Bing）搜索鹅产品相关 B2B/行情平台
2. 提取候选 URL，验证可达性
3. 去重后持久化到 data_sources.json
4. aggregator 读取 config 硬编码源 + 自发现源，合并使用
"""
import json
import logging
import os
import re
import time
from datetime import date
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from goosewatch.config import DATA_SOURCES as BUILTIN_SOURCES, USER_AGENT, REQUEST_DELAY

logger = logging.getLogger(__name__)

# 自发现源存储路径
DISCOVERED_SOURCES_FILE = os.path.join(os.path.dirname(__file__), "data_sources.json")

# 搜索关键词（用于发现新数据源）
DISCOVERY_QUERIES = [
    "鹅产品 批发价格 行情平台",
    "禽肉 B2B 批发平台 价格查询",
    "鹅肉 鹅肝 预制菜 价格行情 网站",
    "农产品批发价格 禽类 数据源",
    "肉鹅 白条鹅 活鹅 报价平台",
]

# 搜索引擎列表
SEARCH_ENGINES = [
    {
        "name": "DuckDuckGo",
        "url": "https://html.duckduckgo.com/html/",
        "params": lambda q: {"q": q},
        "result_selector": "a.result__a",
    },
    {
        "name": "Bing",
        "url": "https://www.bing.com/search",
        "params": lambda q: {"q": q},
        "result_selector": "li.b_algo h2 a",
    },
]

# 已知的垃圾/无关域名（黑名单）
BLACKLIST_DOMAINS = [
    "zhihu.com", "baike.baidu.com", "wikipedia.org", "douyin.com",
    "taobao.com", "jd.com", "pinduoduo.com", "yangkeduo.com",
    "sohu.com", "sina.com.cn", "163.com", "qq.com",
    "weixin.qq.com", "mp.weixin.qq.com",
    "gov.cn",  # 政府网站通常是政策而非价格
]

# 高价值域名关键词（白名单，优先保留）
VALUABLE_KEYWORDS = [
    "price", "hangqing", "b2b", "agri", "food", "poultry",
    "cnhnb", "ymt", "21food", "cnfowl", "nfsc", "moa",
    "jiage", "ncp", "scj", "market", "trade",
]


def _load_discovered() -> list[dict]:
    """从 data_sources.json 加载已发现的数据源。"""
    if os.path.exists(DISCOVERED_SOURCES_FILE):
        try:
            with open(DISCOVERED_SOURCES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_discovered(sources: list[dict]):
    """保存自发现数据源到 data_sources.json。"""
    with open(DISCOVERED_SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def _is_valuable_domain(domain: str) -> bool:
    """判断域名是否值得作为数据源。"""
    domain_lower = domain.lower()

    # 黑名单检查
    for blocked in BLACKLIST_DOMAINS:
        if blocked in domain_lower:
            return False

    # 白名单检查
    for keyword in VALUABLE_KEYWORDS:
        if keyword in domain_lower:
            return True

    return False


def _extract_domains_from_html(html: str, selector: str) -> list[str]:
    """从搜索结果 HTML 中提取域名。"""
    soup = BeautifulSoup(html, "html.parser")
    domains = set()

    for link in soup.select(selector):
        href = link.get("href", "")
        if not href:
            continue

        # 提取域名
        try:
            parsed = urlparse(href)
            domain = parsed.netloc or parsed.path.split("/")[0]
            domain = domain.replace("www.", "").strip()
            if "." in domain and len(domain) > 5:
                domains.add(domain)
        except Exception:
            continue

    return list(domains)


def _verify_source(url: str) -> bool:
    """验证数据源是否可访问。"""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=6)
        return resp.status_code == 200
    except Exception:
        return False


def _guess_source_name(domain: str) -> str:
    """根据域名推测数据源名称。"""
    # 常见映射
    name_map = {
        "price.21food.cn": "食品商务网",
        "www.cnhnb.com": "惠农网",
        "www.ymt.com": "一亩田",
        "b2b.baidu.com": "百度爱采购",
        "www.1688.com": "1688",
        "pfsc.agri.cn": "全国农产品批发价",
        "www.cnfowl.com": "禽网",
        "jiage.cngold.org": "金投价格",
        "cif.mofcom.gov.cn": "商务预报",
        "www.cnuniv.com": "禽网(备用)",
    }
    return name_map.get(domain, domain.split(".")[0])


def _guess_source_type(domain: str) -> str:
    """根据域名推测数据源类型。"""
    if any(k in domain for k in ["b2b", "1688", "trade", "market"]):
        return "B2B平台"
    if any(k in domain for k in ["agri", "ncp", "nfsc", "cnhnb", "ymt"]):
        return "农产品行情"
    if any(k in domain for k in ["price", "jiage", "hangqing"]):
        return "价格行情"
    if any(k in domain for k in ["food", "poultry", "cnfowl"]):
        return "食品/禽类行情"
    return "未知类型"


def discover_new_sources(max_new: int = 5) -> list[dict]:
    """
    自动发现新的鹅产品价格数据源。
    返回本次新发现的数据源列表。
    """
    existing_sources = BUILTIN_SOURCES + _load_discovered()
    existing_domains = {
        urlparse(s["url"]).netloc.replace("www.", "")
        for s in existing_sources
    }

    all_candidates = set()

    for query in DISCOVERY_QUERIES:
        logger.info(f"[Discoverer] 搜索: {query}")

        for engine in SEARCH_ENGINES:
            try:
                params = engine["params"](query)
                resp = requests.get(
                    engine["url"],
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue

                domains = _extract_domains_from_html(resp.text, engine["result_selector"])
                for d in domains:
                    if d not in existing_domains and _is_valuable_domain(d):
                        all_candidates.add(d)

                time.sleep(REQUEST_DELAY * 0.5)
            except Exception as e:
                logger.debug(f"[Discoverer] {engine['name']} 搜索失败: {e}")
                continue

        time.sleep(REQUEST_DELAY)

    # 验证候选域名可达性
    new_sources = []
    candidates = list(all_candidates)

    for domain in candidates[:20]:  # 最多验证 20 个
        if len(new_sources) >= max_new:
            break

        url = f"https://{domain}"
        logger.info(f"[Discoverer] 验证: {url}")

        if _verify_source(url):
            source = {
                "name": _guess_source_name(domain),
                "url": url,
                "type": _guess_source_type(domain),
                "discovered_at": str(date.today()),
            }
            new_sources.append(source)
            logger.info(f"[Discoverer] ✓ 新数据源: {source['name']} ({url})")

        time.sleep(REQUEST_DELAY * 0.3)

    # 持久化
    if new_sources:
        existing_discovered = _load_discovered()
        existing_discovered.extend(new_sources)
        _save_discovered(existing_discovered)
        logger.info(f"[Discoverer] 已保存 {len(new_sources)} 个新数据源")

    return new_sources


def get_all_sources() -> list[dict]:
    """获取所有数据源（内置 + 自发现）。"""
    return BUILTIN_SOURCES + _load_discovered()


def get_discovery_stats() -> dict:
    """获取数据源自迭代统计。"""
    discovered = _load_discovered()
    return {
        "builtin_count": len(BUILTIN_SOURCES),
        "discovered_count": len(discovered),
        "total_count": len(BUILTIN_SOURCES) + len(discovered),
        "discovered_sources": [
            {"name": s["name"], "url": s["url"], "discovered_at": s.get("discovered_at", "unknown")}
            for s in discovered
        ],
    }


if __name__ == "__main__":
    print("=== 数据源自迭代发现 ===\n")
    print(f"内置数据源: {len(BUILTIN_SOURCES)} 个")
    print(f"已发现数据源: {len(_load_discovered())} 个\n")

    print("开始搜索新数据源...\n")
    new = discover_new_sources()
    if new:
        print(f"\n✓ 发现 {len(new)} 个新数据源:")
        for s in new:
            print(f"  - {s['name']} ({s['url']}) [{s['type']}]")
    else:
        print("\n未发现新数据源（所有候选已在列表中或验证失败）")
