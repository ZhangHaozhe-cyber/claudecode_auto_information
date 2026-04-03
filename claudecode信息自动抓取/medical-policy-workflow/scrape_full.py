"""
全量历史数据抓取脚本（一次性使用）
抓取所有可用来源的全部内容，保存到 data/cn/full/ 目录

可用来源：
  - NHSA 医保动态 (col14)      : 最多 45 条
  - NHSA 集采专栏 (col147)     : 最多 43 条
  - NHSA 政策法规 (col104)     : 最多 45 条
  - NHSA 政策解读 (col105)     : 最多 45 条
  - 国务院最新政策 JSON API     : 全部 1028 条（按关键词过滤）

用法：
  python -X utf8 scrape_full.py
  python -X utf8 scrape_full.py --no-filter   # 国务院不过滤关键词，保存全量
"""

import argparse, json, re, time
import httpx
from bs4 import BeautifulSoup
from datetime import date
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

NHSA_BASE = "https://www.nhsa.gov.cn"
GOV_JSON_URL = "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json"

GOV_KEYWORDS = [
    "医药", "医疗", "药品", "卫生", "健康", "医保", "集采",
    "生物", "制药", "临床", "医院", "疾控", "疫苗", "中医",
]

NHSA_SOURCES = [
    {"col": "col14",  "name": "nhsa_news",   "department": "国家医疗保障局", "policy_type": "医保动态"},
    {"col": "col147", "name": "nhsa_jicai",  "department": "国家医疗保障局", "policy_type": "集采专栏"},
    {"col": "col104", "name": "nhsa_policy", "department": "国家医疗保障局", "policy_type": "政策法规"},
    {"col": "col105", "name": "nhsa_jiedu",  "department": "国家医疗保障局", "policy_type": "政策解读"},
]


def scrape_nhsa_col(col: str, department: str, policy_type: str) -> list:
    """抓取 NHSA 单个栏目的全部 CDATA 记录"""
    url = f"{NHSA_BASE}/col/{col}/index.html"
    headers = {**HEADERS, "Referer": NHSA_BASE}
    r = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
    r.raise_for_status()

    records = re.findall(r"<record><!\[CDATA\[(.*?)\]\]></record>", r.text, re.DOTALL)
    items = []
    for cdata in records:
        soup = BeautifulSoup(cdata, "html.parser")
        a_tag = soup.find("a")
        span_tag = soup.find("span")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        href = a_tag.get("href", "")
        if href and not href.startswith("http"):
            href = NHSA_BASE + "/" + href.lstrip("/")
        items.append({
            "title": title,
            "link": href,
            "pub_date": span_tag.get_text(strip=True) if span_tag else "",
            "department": department,
            "policy_type": policy_type,
            "source_col": col,
        })
    return items


def scrape_gov_all(no_filter: bool = False) -> list:
    """抓取国务院 JSON API 全量数据（可选是否过滤医疗关键词）"""
    headers = {**HEADERS, "Referer": "https://www.gov.cn"}
    r = httpx.get(GOV_JSON_URL, headers=headers, timeout=30, follow_redirects=True)
    r.raise_for_status()
    data = r.json()

    items = []
    for row in data:
        title = row.get("TITLE", "")
        if not title:
            continue
        if not no_filter and not any(kw in title for kw in GOV_KEYWORDS):
            continue
        items.append({
            "title": title,
            "link": row.get("URL", ""),
            "pub_date": row.get("DOCRELPUBTIME", ""),
            "department": "国务院",
            "policy_type": "纲领性文件",
        })
    return items


def save(items: list, name: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}_full.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Saved {len(items)} items → {path}")
    return len(items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-filter", action="store_true", help="国务院数据不过滤关键词，保存全量1028条")
    args = parser.parse_args()

    out_dir = Path("data/cn/full")
    today = date.today()
    total = 0

    print(f"=== 全量历史数据抓取 ({today}) ===\n")

    # ── NHSA 四个栏目 ──────────────────────────────
    all_nhsa = []
    for src in NHSA_SOURCES:
        print(f"[NHSA] {src['policy_type']} ({src['col']}) ...")
        try:
            items = scrape_nhsa_col(src["col"], src["department"], src["policy_type"])
            total += save(items, src["name"], out_dir)
            all_nhsa.extend(items)
            time.sleep(0.5)
        except Exception as e:
            print(f"  [ERROR] {e}")

    # 合并 NHSA 保存一份汇总文件
    merged_path = out_dir / "nhsa_all_full.json"
    merged_path.write_text(json.dumps(all_nhsa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [NHSA 汇总] {len(all_nhsa)} 条 → {merged_path}")

    # ── 国务院 JSON API ──────────────────────────────
    print(f"\n[国务院] JSON API {'（全量，不过滤）' if args.no_filter else '（按医疗关键词过滤）'} ...")
    try:
        gov_items = scrape_gov_all(no_filter=args.no_filter)
        total += save(gov_items, "gov_policy", out_dir)
    except Exception as e:
        print(f"  [ERROR] {e}")

    print(f"\n=== 完成：共 {total} 条记录，输出目录 {out_dir.resolve()} ===")


if __name__ == "__main__":
    main()
