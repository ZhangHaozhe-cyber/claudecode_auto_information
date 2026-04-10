import argparse
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

os_chdir_done = False


def _load_data_files(data_dir: Path, mode: str, today: date) -> dict:
    """按 department 分组加载今日（或本周）的所有抓取数据"""
    if mode == "weekly":
        # 本周一到今天
        start = today - timedelta(days=today.weekday())
        dates = [(start + timedelta(days=i)) for i in range((today - start).days + 1)]
        pattern_dates = {str(d) for d in dates}
    else:
        pattern_dates = {str(today)}

    grouped: dict[str, list] = {}
    for json_file in sorted(data_dir.glob("*.json")):
        # 文件名格式：{source_name}_{YYYY-MM-DD}.json
        stem = json_file.stem
        parts = stem.rsplit("_", 3)
        if len(parts) < 2:
            continue
        file_date = "_".join(parts[-3:]) if len(parts) >= 4 else parts[-1]
        if file_date not in pattern_dates:
            continue

        items = json.loads(json_file.read_text(encoding="utf-8"))
        if not items:
            continue

        dept = items[0].get("department", "其他") if items else "其他"
        if dept not in grouped:
            grouped[dept] = []
        grouped[dept].extend(items)

    return grouped


def _build_prompt(grouped_data: dict, config: dict, mode: str, today: date) -> str:
    research_context = config["report"].get("research_context", "")
    did_keywords = config["report"].get("did_keywords", [])
    country_name = config.get("country_name", "")

    sections_key = "weekly_sections" if mode == "weekly" else "daily_sections"
    sections = config["report"].get(sections_key, [])

    if mode == "weekly":
        start = today - timedelta(days=today.weekday())
        date_range = f"{start} 至 {today}"
        report_title = f"{country_name}医药产业政策周报（{date_range}）"
        time_desc = f"本周（{date_range}）"
    else:
        report_title = f"{country_name}医药产业政策日报 {today}"
        time_desc = f"今日（{today}）"

    data_block = json.dumps(grouped_data, ensure_ascii=False, indent=2)

    dept_sections = "\n".join(
        f"## {i+2}、{s}" for i, s in enumerate(s for s in sections
                                                 if s not in ("执行摘要", "本周执行摘要",
                                                              "集采相关重点事件标记", "DID分析相关事件汇总",
                                                              "数据抓取质量说明"))
    )

    prompt = f"""你是一位专注于{country_name}医药产业政策研究的分析师，正在辅助一项关于"{research_context}"的实证研究。

以下是{time_desc}从{country_name}各部委/监管机构官方网站自动抓取的政策数据，已按机构分组：

{data_block}

DID研究关键词（请在报告中特别标记包含这些主题的政策）：
{', '.join(did_keywords)}

---

请生成{time_desc}{country_name}医药产业政策报告，格式为 Markdown，严格按以下章节结构：

# {report_title}

## 一、执行摘要
（3-5句，突出集采相关最重要信息，如有新一轮集采公告或重大政策出台请首句点明）

{dept_sections}

每个机构章节的格式要求：
- 发布条目数量及主要政策类型概括（1句）
- 各条政策逐条列出：
  - **标题**（尽量保留原文）
  - 发布日期 | 来源链接（如有）
  - 一句话内容概述
  - 与集采/临床试验关联性：高 / 中 / 低 / 无

## 七、集采相关重点事件 ⚑
> 本节专为DID实证分析标记具有外生冲击性质的政策节点

请逐一识别{time_desc}数据中是否存在以下类型事件（若有则详细描述，若无则注明"本期无符合条件事件"）：
- 新一轮集采启动公告或招标文件
- 集采中标结果公布、价格降幅数据
- 医保目录调整（纳入/移出品种）
- 上市许可或审批加速政策
- 其他可用作DID断点的明确政策时间节点

## 八、数据抓取质量说明
- 本次共加载 {sum(len(v) for v in grouped_data.values())} 条记录，来自 {len(grouped_data)} 个机构
- 如数据中某机构条目为空，请注明可能的原因（如抓取失败、当日无更新等）
- 已知局限性提示
"""
    return prompt


def _call_deepseek(prompt: str) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "medical-policy-workflow/1.0 (+python-httpx)",
        "Connection": "close",
        "Authorization": f"Bearer {api_key}",
    }
    data = None
    # 首先禁用环境代理变量（部分本地代理会导致 TLS EOF），失败后再回退 trust_env=True。
    for trust_env in (False, True):
        for attempt in range(2):
            try:
                with httpx.Client(timeout=120, http2=False, trust_env=trust_env) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                break
            except httpx.HTTPError as e:
                if attempt == 0:
                    time.sleep(2)
                    continue
                if not trust_env:
                    print(f"[WARN] DeepSeek request failed with trust_env=False: {e}")
                    break
                raise RuntimeError(f"DeepSeek request failed: {e}") from e
        if data is not None:
            break

    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected DeepSeek response type: {type(data)}")
    return data["choices"][0]["message"]["content"]


def _extract_json_array(raw_text: str) -> list:
    """Extract and parse a JSON array from model output with optional markdown fences."""
    raw = (raw_text or "").strip()
    if raw.startswith("```"):
        lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("```")]
        raw = "\n".join(lines).strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        m = re.search(r"\[[\s\S]*\]", raw)
        if not m:
            return []
        try:
            parsed = json.loads(m.group(0))
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []


def enrich_policy_records(records: list[dict], sample_size: int = 10) -> list[dict]:
    """Use DeepSeek to enrich a sampled subset of policy records with relevance/tags/reason fields."""
    if not records:
        return []

    sample = records[: max(0, sample_size)]
    indexed = []
    for i, rec in enumerate(sample):
        indexed.append(
            {
                "idx": i,
                "title": rec.get("title", ""),
                "department": rec.get("department", ""),
                "pub_date": str(rec.get("pub_date", "")),
                "link": rec.get("link", ""),
            }
        )

    prompt = (
        "请对以下政策记录做医药政策相关增强标注。\n"
        "返回严格 JSON 数组，每项包含字段: idx, llm_relevance(高/中/低/无), llm_tags(字符串数组), llm_reason(一句话)。\n"
        "不要输出任何解释文本。\n\n"
        f"records:\n{json.dumps(indexed, ensure_ascii=False, indent=2)}"
    )
    raw = _call_deepseek(prompt)
    rows = _extract_json_array(raw)
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        idx = row.get("idx")
        if not isinstance(idx, int) or idx < 0 or idx >= len(sample):
            continue
        out.append(
            {
                "idx": idx,
                "llm_relevance": str(row.get("llm_relevance", "")).strip() or "中",
                "llm_tags": row.get("llm_tags") if isinstance(row.get("llm_tags"), list) else [],
                "llm_reason": str(row.get("llm_reason", "")).strip(),
            }
        )
    return out


def analyze(data_dir: Path, config: dict, mode: str, today: date) -> str:
    grouped = _load_data_files(data_dir, mode, today)

    if not grouped:
        print(f"[ERROR] No data found in {data_dir} for mode={mode}, date={today}")
        sys.exit(1)

    prompt = _build_prompt(grouped, config, mode, today)
    print("[INFO] Analyzer LLM provider: deepseek")
    return _call_deepseek(prompt)



if __name__ == "__main__":
    os.chdir(Path(__file__).parent)

    parser = argparse.ArgumentParser(description="Medical Policy Analyzer")
    parser.add_argument("--country", default="cn")
    parser.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    args = parser.parse_args()

    config_path = Path(f"config/{args.country}.json")
    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    country = config["country"]
    today = date.today()

    data_dir = Path(f"data/{country}")
    if not data_dir.exists():
        print(f"[ERROR] Data directory not found: {data_dir}")
        sys.exit(1)

    report = analyze(data_dir, config, args.mode, today)

    report_dir = Path(f"reports/{country}/{args.mode}")
    report_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "weekly":
        week_str = today.strftime("%Y-W%W")
        out = report_dir / f"report_week_{week_str}.md"
    else:
        out = report_dir / f"report_{today}.md"

    out.write_text(report, encoding="utf-8")
    print(f"Report saved to {out}")
