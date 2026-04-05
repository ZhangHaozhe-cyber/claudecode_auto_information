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


def scrape_playwright(source: dict) -> list:
    """
    Playwright headless Chromium 抓取，适用于：
    - 412 JS 反爬（NMPA、NHC）：真实浏览器头绕过服务器检测
    - AJAX 动态渲染（MIIT）：等待 JS 执行后提取内容
    source 配置字段：
      selector   — 列表项 CSS 选择器
      title_attr — 标题子选择器（默认 "a"）
      date_attr  — 日期子选择器（默认 ""）
      link_attr  — 链接子选择器（默认 "a"）
      wait_for   — 可选，等待此选择器出现后再解析（AJAX 场景）
      limit      — 最多返回条数
    Playwright lazy import：未安装时不影响其他 scraper 类型。
    """
    from playwright.sync_api import sync_playwright

    limit = source.get("limit", 15)
    base_url = source.get("base_url", "")
    keywords = source.get("keywords_filter", [])
    department = source.get("department", "")
    policy_type = source.get("policy_type", "")
    wait_for = source.get("wait_for", source.get("selector", "body"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        page = context.new_page()
        page.goto(source["url"], wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector(wait_for, timeout=15000)
        except Exception:
            pass  # 超时则继续，用已加载内容
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    items = []
    for el in soup.select(source["selector"])[:limit]:
        title_tag = el.select_one(source.get("title_attr", "a"))
        title = title_tag.get_text(strip=True) if title_tag else el.get_text(strip=True)[:100]
        if not title or not _passes_filter(title, keywords):
            continue

        item = {"title": title, "department": department, "policy_type": policy_type}

        link_sel = source.get("link_attr", "a")
        link_tag = (
            el.select_one(link_sel.replace("[href]", ""))
            if "[href]" in link_sel
            else el.select_one(link_sel)
        )
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            item["link"] = (
                href if href.startswith("http")
                else (base_url.rstrip("/") + "/" + href.lstrip("/") if base_url else href)
            )

        date_sel = source.get("date_attr", "")
        if date_sel:
            date_tag = el.select_one(date_sel)
            if date_tag:
                item["pub_date"] = date_tag.get_text(strip=True)

        items.append(item)
    return items


def scrape_miit_api(source: dict) -> list:
    """
    工信部政策文件专用抓取器，使用 search-front-server 搜索 API（JSON）。
    绕过 AJAX 动态渲染限制，直接查询后端接口。
    source 配置字段：
      url          — API 基础 URL（search-front-server/api/search/info）
      base_url     — 用于拼接相对链接（https://www.miit.gov.cn）
      miit_cateid  — 搜索类目 ID（默认 "57" = 文件发布）
      limit        — 最多返回条数
      keywords_filter — 标题关键词过滤（空列表=不过滤）
    """
    from datetime import datetime

    limit = source.get("limit", 10)
    base_url = source.get("base_url", "https://www.miit.gov.cn")
    keywords = source.get("keywords_filter", [])
    department = source.get("department", "工业和信息化部")
    policy_type = source.get("policy_type", "政策文件")
    cateid = source.get("miit_cateid", "57")

    headers = {
        **HEADERS,
        "Referer": "https://www.miit.gov.cn/zwgk/zcwj/wjfb/index.html",
    }
    r = httpx.get(
        source["url"],
        params={"websiteid": "110000000000000", "scope": "basic", "q": "",
                "pg": str(limit * 3), "cateid": cateid, "pos": "1"},
        timeout=20,
        headers=headers,
        follow_redirects=True,
    )
    r.raise_for_status()

    data = r.json()
    raw_results = (
        data.get("data", {})
            .get("searchResult", {})
            .get("dataResults", [])
    )

    items = []
    for row in raw_results:
        if len(items) >= limit:
            break
        d = row.get("data", {})
        title = d.get("title", d.get("title_text", ""))
        if not title or not _passes_filter(title, keywords):
            continue

        href = d.get("url", "")
        link = href if href.startswith("http") else (base_url.rstrip("/") + href if href else "")

        # cdate is Unix milliseconds
        raw_date = d.get("cdate", d.get("jsearch_date", ""))
        if raw_date and str(raw_date).isdigit():
            pub_date = datetime.fromtimestamp(int(raw_date) / 1000).strftime("%Y-%m-%d")
        else:
            pub_date = str(raw_date)

        items.append({
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "department": department,
            "policy_type": policy_type,
        })
    return items


SCRAPERS = {
    "web":            scrape_web,
    "web_cdata":      scrape_web_cdata,
    "api_json":       scrape_api_json,
    "rss":            scrape_rss,
    "web_playwright": scrape_playwright,
    "miit_api":       scrape_miit_api,
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
