import sys, json, httpx, feedparser
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup

def scrape_api(source):
    """抓取 JSON API"""
    r = httpx.get(source["url"], timeout=15)
    ids = r.json()[:source.get("limit", 10)]
    items = []
    for id_ in ids:
        detail = httpx.get(
            f"https://hacker-news.firebaseio.com/v0/item/{id_}.json"
        ).json()
        items.append({
            "title": detail.get("title"),
            "url": detail.get("url"),
            "score": detail.get("score")
        })
    return items

def scrape_web(source):
    """抓取网页内容"""
    r = httpx.get(source["url"], timeout=15,
                  headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for el in soup.select(source["selector"])[:10]:
        items.append({"text": el.get_text(strip=True)[:300]})
    return items

def scrape_rss(source):
    """抓取 RSS Feed"""
    feed = feedparser.parse(source["url"])
    return [
        {"title": e.title, "summary": e.get("summary", "")[:300]}
        for e in feed.entries[:source.get("limit", 10)]
    ]

if __name__ == "__main__":
    source = json.loads(sys.argv[1])
    scrapers = {"api": scrape_api, "web": scrape_web, "rss": scrape_rss}
    result = scrapers[source["type"]](source)

    Path("data").mkdir(exist_ok=True)
    filename = f"data/{source['name']}_{date.today()}.json"
    Path(filename).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Saved {len(result)} items to {filename}")
