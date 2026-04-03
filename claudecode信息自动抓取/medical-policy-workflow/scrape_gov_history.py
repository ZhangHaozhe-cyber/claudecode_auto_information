"""
国务院历史政策全量抓取脚本
使用 sousuoht.www.gov.cn 搜索 API，抓取 2010-01-01 至今所有医药相关政策。

用法：
  python -X utf8 scrape_gov_history.py                  # 关键词过滤（默认）
  python -X utf8 scrape_gov_history.py --no-filter      # 不过滤，保存全量2010+政策
  python -X utf8 scrape_gov_history.py --from 2010-01-01 --to 2026-12-31

API 说明：
  - 域名: sousuoht.www.gov.cn
  - 认证: RSA-PKCS1v15 加密 appKey 后作为请求头 athenaAppKey
  - 数据: 共 6169 条（1996-2026），本脚本仅保留 2010+ 数据
  - 分页: 每页最多 100 条，最多 1000 页（实际约 62 页可覆盖 2010+ 数据）
"""

import argparse, base64, json, re, time, urllib.parse
from datetime import date, datetime
from pathlib import Path

import httpx
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding

# ── API 配置 ─────────────────────────────────────────────────────────────────

DOMAIN = "https://sousuoht.www.gov.cn"
GET_CODE_PATH = "/athena/forward/DA2FE8C6CAD0EEBC5F97F7E3F3633A7188DAA40373EEA0E4024A081201F4D546"
SEARCH_PATH = "/athena/forward/486B5ABFBAD0FF5743F5E82E007EF04DDD6388E7989E9EC9CC7B84917AC81A5F"

RSA_PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCSMhMJQ+XLI7oW0k9Bwufur4Ag"
    "40tcsrzT7WZf6Ao0O/hyY1gZtCSYFxkxIZUXjW46j27XSW8IDX1rTJoHaMxHCWsO"
    "pTi2W5stybGYZytsY5on8gd8AIaS1d52h9eaS2TFydtJJtE50xHmT0WmoyoinWCu"
    "VCOkdCLhh9b9jSdeSQIDAQAB"
)
ATHENA_APP_KEY_RAW = "a46884b2013e4d189f2a8e2d49a23525"
ATHENA_APP_NAME = "国网搜索"
THIRD_PARTY_CODE = "thirdparty_code_107"
VIEW_ID = 30
SITE_ID = 8

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.gov.cn/zhengce/xxgk/index.htm",
    "Origin": "https://www.gov.cn",
}

MEDICAL_KEYWORDS = [
    "医药", "医疗", "药品", "卫生", "健康", "医保", "集采",
    "生物", "制药", "临床", "医院", "疾控", "疫苗", "中医",
    "药监", "药械", "生命科学", "医学", "公共卫生", "保健",
    "仿制药", "原研药", "创新药", "生物制品",
]


def _rsa_encrypt(plaintext: str) -> str:
    """用页面内嵌公钥 RSA-PKCS1v15 加密字符串，返回 URL-encoded base64。"""
    pem = f"-----BEGIN PUBLIC KEY-----\n{RSA_PUBLIC_KEY}\n-----END PUBLIC KEY-----"
    pub_key = serialization.load_pem_public_key(pem.encode(), backend=default_backend())
    encrypted = pub_key.encrypt(plaintext.encode("utf-8"), asym_padding.PKCS1v15())
    return urllib.parse.quote(base64.b64encode(encrypted).decode("ascii"))


def _build_headers() -> dict:
    return {
        **BASE_HEADERS,
        "Content-Type": "application/json;charset=utf-8",
        "athenaAppKey": _rsa_encrypt(ATHENA_APP_KEY_RAW),
        "athenaAppName": urllib.parse.quote(ATHENA_APP_NAME),
    }


def get_code(client: httpx.Client, headers: dict) -> str:
    """获取查询用的 codeCode（每次运行开始时获取一次）。"""
    url = f"{DOMAIN}{GET_CODE_PATH}?thirdPartyName=hycloud&thirdPartyTenantId={SITE_ID}"
    # GET code 端点不需要 Content-Type
    get_headers = {k: v for k, v in headers.items() if k != "Content-Type"}
    r = client.get(url, headers=get_headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("resultCode", {}).get("code") != 200:
        raise RuntimeError(f"getCode failed: {data}")
    return data["result"]["data"]


def search_page(
    client: httpx.Client,
    headers: dict,
    code_code: str,
    page_no: int,
    page_size: int = 100,
    keyword: str = "",
) -> dict:
    """查询单页数据，返回 {pager, list} 结构。"""
    params = {
        "code": code_code,
        "thirdPartyCode": THIRD_PARTY_CODE,
        "thirdPartyTableId": VIEW_ID,
        "resultFields": ["pub_url", "maintitle", "fwzh", "cwrq", "publish_time"],
        "trackTotalHits": "true",
        "searchFields": [{"fieldName": "maintitle" if keyword else "", "searchWord": keyword}],
        "isPreciseSearch": 0,
        "sorts": [{"sortField": "publish_time", "sortOrder": "ASC"}],
        "childrenInfoIds": [],
        "pageSize": page_size,
        "pageNo": page_no,
    }
    url = f"{DOMAIN}{SEARCH_PATH}"
    r = client.post(url, headers=headers, content=json.dumps(params), timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("resultCode", {}).get("code") != 200:
        raise RuntimeError(f"Search failed on page {page_no}: {data}")
    return data["result"]["data"]


def _strip_tags(text: str) -> str:
    """移除 <em> 等高亮标签。"""
    return re.sub(r"<[^>]+>", "", text)


def scrape_gov_history(
    start_date: str = "2010-01-01",
    end_date: str = None,
    no_filter: bool = False,
    page_size: int = 100,
    delay: float = 0.4,
) -> list:
    """
    分页抓取国务院政策全库，保留 start_date ~ end_date 范围内的条目。
    no_filter=False 时额外按 MEDICAL_KEYWORDS 过滤标题。
    """
    end_date = end_date or date.today().isoformat()
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date + " 23:59:59")

    print(f"  日期范围: {start_date} ~ {end_date}")
    print(f"  关键词过滤: {'关闭（全量）' if no_filter else '开启'}")

    headers = _build_headers()

    with httpx.Client() as client:
        print("  获取 codeCode ...")
        code_code = get_code(client, headers)
        print(f"  codeCode = {code_code}")

        # 先查第 1 页获取总页数
        first = search_page(client, headers, code_code, 1, page_size)
        pager = first.get("pager", {})
        total_pages = min(pager.get("pageCount", 1), 1000)
        total_count = pager.get("total", 0)
        print(f"  API 总条目: {total_count}，共 {total_pages} 页（每页 {page_size}）")

        all_items = []
        seen_urls = set()

        def process_page_items(raw_list):
            for row in raw_list:
                pub_time_str = row.get("publish_time", "")
                if not pub_time_str:
                    continue
                try:
                    pub_dt = datetime.fromisoformat(pub_time_str)
                except ValueError:
                    continue
                if pub_dt < start_dt or pub_dt > end_dt:
                    continue
                title = _strip_tags(row.get("maintitle", ""))
                if not no_filter and not any(kw in title for kw in MEDICAL_KEYWORDS):
                    continue
                url = row.get("pub_url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                all_items.append({
                    "title": title,
                    "link": url,
                    "pub_date": pub_time_str[:10],
                    "cwrq": (row.get("cwrq") or "")[:10],
                    "fwzh": row.get("fwzh", ""),
                    "department": "国务院",
                    "policy_type": "纲领性文件",
                })

        process_page_items(first.get("list", []))
        print(f"  第 1/{total_pages} 页 ... 累计 {len(all_items)} 条")

        for page_no in range(2, total_pages + 1):
            time.sleep(delay)
            try:
                result = search_page(client, headers, code_code, page_no, page_size)
                items_on_page = result.get("list", [])
                process_page_items(items_on_page)

                # 若本页最早条目已早于 start_date 且全量抓取，可以不提前退出
                # 但若按 ASC 排序，一旦所有条目晚于 end_date 也可 break
                if items_on_page:
                    latest_on_page = items_on_page[-1].get("publish_time", "")
                    if latest_on_page and datetime.fromisoformat(latest_on_page) > end_dt:
                        print(f"  第 {page_no} 页已超出截止日期，停止分页")
                        break

                if page_no % 10 == 0 or page_no == total_pages:
                    print(f"  第 {page_no}/{total_pages} 页 ... 累计 {len(all_items)} 条")
            except Exception as e:
                print(f"  [WARN] 第 {page_no} 页失败: {e}，跳过")

    return all_items


def main():
    parser = argparse.ArgumentParser(description="国务院历史政策全量抓取")
    parser.add_argument("--from", dest="start", default="2010-01-01", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--to", dest="end", default=None, help="截止日期 YYYY-MM-DD（默认今日）")
    parser.add_argument("--no-filter", action="store_true", help="不过滤关键词，保存全量国务院政策")
    parser.add_argument("--page-size", type=int, default=100, help="每页条数（最大100）")
    parser.add_argument("--delay", type=float, default=0.4, help="翻页间隔（秒）")
    parser.add_argument("--out", default="data/cn/full", help="输出目录")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()

    print(f"\n=== 国务院历史政策抓取 ({today}) ===\n")

    items = scrape_gov_history(
        start_date=args.start,
        end_date=args.end,
        no_filter=args.no_filter,
        page_size=args.page_size,
        delay=args.delay,
    )

    suffix = "all" if args.no_filter else "medical"
    out_path = out_dir / f"gov_policy_historical_{suffix}.json"
    out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Saved {len(items)} 条 → {out_path.resolve()}")
    print(f"\n=== 完成 ===")


if __name__ == "__main__":
    main()
