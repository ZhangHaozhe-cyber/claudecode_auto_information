import sys, json, re, argparse, httpx
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _passes_filter(text: str, keywords: list) -> bool:
    """空列表=不过滤；有值=标题包含任一词才保留"""
    if not keywords:
        return True
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def scrape_web_cdata(source: dict) -> list:
    """
    抓取 NHSA 风格的页面：内容嵌在 <script type="text/xml"><datastore> 的
    <record><![CDATA[...]]></record> 段落中，用 regex 提取。
    """
    headers = {**HEADERS, "Referer": source.get("base_url", source["url"])}
    r = httpx.get(source["url"], timeout=20, headers=headers, follow_redirects=True)
    r.raise_for_status()

    records = re.findall(r"<record><!\[CDATA\[(.*?)\]\]></record>", r.text, re.DOTALL)
    limit = source.get("limit", 15)
    keywords = source.get("keywords_filter", [])
    base_url = source.get("base_url", "")
    department = source.get("department", "")
    policy_type = source.get("policy_type", "")

    items = []
    for cdata in records[:limit]:
        soup = BeautifulSoup(cdata, "html.parser")
        a_tag = soup.find("a")
        span_tag = soup.find("span")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        if not title or not _passes_filter(title, keywords):
            continue
        href = a_tag.get("href", "")
        if href and not href.startswith("http") and base_url:
            href = base_url.rstrip("/") + "/" + href.lstrip("/")
        item = {
            "title": title,
            "link": href,
            "pub_date": span_tag.get_text(strip=True) if span_tag else "",
            "department": department,
            "policy_type": policy_type,
        }
        items.append(item)
    return items


def scrape_api_json(source: dict) -> list:
    """
    抓取返回 JSON 列表的 API（如 gov.cn ZUIXINZHENGCE.json）。
    通过 field_map 将 API 字段映射到标准字段。
    """
    headers = {**HEADERS, "Referer": source.get("base_url", source["url"])}
    r = httpx.get(source["url"], timeout=20, headers=headers, follow_redirects=True)
    r.raise_for_status()

    data = r.json()
    if isinstance(data, dict):
        # 部分 API 将列表嵌在某个 key 里
        list_key = source.get("list_key", "")
        data = data.get(list_key, []) if list_key else list(data.values())[0]

    limit = source.get("limit", 20)
    keywords = source.get("keywords_filter", [])
    field_map: dict = source.get("field_map", {})
    department = source.get("department", "")
    policy_type = source.get("policy_type", "")

    items = []
    for row in data:  # 遍历全量，过滤后再截断
        if len(items) >= limit:
            break
        title_key = field_map.get("title", "TITLE")
        link_key = field_map.get("link", "URL")
        date_key = field_map.get("pub_date", "DOCRELPUBTIME")

        title = row.get(title_key, "")
        if not title or not _passes_filter(title, keywords):
            continue
        items.append({
            "title": title,
            "link": row.get(link_key, ""),
            "pub_date": row.get(date_key, ""),
            "department": department,
            "policy_type": policy_type,
        })
    return items


def scrape_web(source: dict) -> list:
    """抓取普通 HTML 网页（CSS selector 方式）"""
    headers = {**HEADERS, "Referer": source.get("base_url", source["url"])}
    r = httpx.get(source["url"], timeout=20, headers=headers, follow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    limit = source.get("limit", 15)
    base_url = source.get("base_url", "")
    keywords = source.get("keywords_filter", [])
    department = source.get("department", "")
    policy_type = source.get("policy_type", "")

    items = []
    for el in soup.select(source["selector"])[:limit]:
        title_tag = el.select_one(source.get("title_attr", "a"))
        title = title_tag.get_text(strip=True) if title_tag else el.get_text(strip=True)[:100]
        if not title or not _passes_filter(title, keywords):
            continue

        item = {"title": title, "department": department, "policy_type": policy_type}

        link_sel = source.get("link_attr", "a")
        link_tag = el.select_one(link_sel.replace("[href]", "")) if "[href]" in link_sel else el.select_one(link_sel)
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            item["link"] = href if href.startswith("http") else (base_url.rstrip("/") + "/" + href.lstrip("/") if base_url else href)

        date_sel = source.get("date_attr", "")
        if date_sel:
            date_tag = el.select_one(date_sel)
            if date_tag:
                item["pub_date"] = date_tag.get_text(strip=True)

        items.append(item)
    return items


def scrape_rss(source: dict) -> list:
    """抓取 RSS Feed"""
    import feedparser
    feed = feedparser.parse(source["url"])
    keywords = source.get("keywords_filter", [])
    items = []
    for e in feed.entries[:source.get("limit", 15)]:
        title = getattr(e, "title", "")
        if not _passes_filter(title, keywords):
            continue
        items.append({
            "title": title,
            "summary": getattr(e, "summary", "")[:400],
            "link": getattr(e, "link", ""),
            "pub_date": getattr(e, "published", ""),
            "department": source.get("department", ""),
            "policy_type": source.get("policy_type", ""),
        })
    return items


SCRAPERS = {
    "web": scrape_web,
    "web_cdata": scrape_web_cdata,
    "api_json": scrape_api_json,
    "rss": scrape_rss,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_json", help="Source config as JSON string")
    parser.add_argument("--country", default="cn")
    args = parser.parse_args()

    source = json.loads(args.source_json)

    # skip 标记：跳过暂不可用的源
    if source.get("skip"):
        print(f"[SKIP] {source['name']} is marked as skip (requires_browser or unavailable)")
        sys.exit(0)

    scrape_fn = SCRAPERS.get(source["type"])
    if not scrape_fn:
        print(f"[ERROR] Unknown source type: {source['type']}", file=sys.stderr)
        sys.exit(1)

    result = scrape_fn(source)

    data_dir = Path(f"data/{args.country}")
    data_dir.mkdir(parents=True, exist_ok=True)
    filename = data_dir / f"{source['name']}_{date.today()}.json"
    filename.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(result)} items to {filename}")
