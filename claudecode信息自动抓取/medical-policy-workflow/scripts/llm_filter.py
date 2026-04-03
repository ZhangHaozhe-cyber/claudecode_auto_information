"""
LLM 医药政策相关性过滤模块

使用 claude-3-5-haiku-20241022 批量判断政策标题是否属于医药卫生领域，
去除爬虫关键词匹配带来的误命中（如房地产、教育、交通等无关政策）。

特性：
  - 每批 30 条，一次 API 调用，成本 < $0.001/批
  - 结果持久化缓存（MD5键），避免重复计费
  - 错误保守策略：API 失败时整批保留，不漏政策
  - 支持从 clean_data.py 通过 --llm-filter 参数调用

不建议直接作为独立脚本运行，由 clean_data.py 调用。
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import anthropic

# ── 配置 ─────────────────────────────────────────────────────────────────────

HAIKU_MODEL = "claude-3-5-haiku-20241022"
DEFAULT_BATCH_SIZE = 30
DEFAULT_CACHE_PATH = Path("output/llm_filter_cache.json")

# ── Prompt ───────────────────────────────────────────────────────────────────

CLASSIFICATION_PROMPT_TEMPLATE = """\
你是中国医药产业政策领域的分类专家。

请判断以下每条政策标题是否属于"医药卫生相关政策"。

【属于（is_medical=true）的范畴】
药品（含仿制药、创新药）、医疗器械、医疗保险（医保）、药品集中采购（集采/带量采购）、
临床试验、医院管理、卫生健康、疫苗、中医药、生物医药/生物制品、制药产业、
公共卫生、食品安全、营养标准、健康中国行动

【不属于（is_medical=false）的范畴】
房地产、农业（非食品安全）、基础教育/高等教育、交通/铁路/航空、能源/电力/石油、
军事/国防、外交/外事、纯财政/税收/审计（非医保相关）、环境/气象

【边界情况说明】
- "养老" → 若涉及医疗保障/护理保险 = true；若仅涉及退休金/基本养老保险 = false
- "生物技术/生命科学" → true（医药产业上游）
- "社会保障" → 仅当具体涉及医疗保障时 = true，否则 = false
- 文件标题模糊时，宁可判断为 true（保守策略）

【输入记录】
{records_block}

【输出格式】
严格输出 JSON 数组，不要有任何额外文字或代码块标记：
[
  {{"id": 0, "is_medical": true, "confidence": "high", "reason": "涉及药品集中采购政策"}},
  {{"id": 1, "is_medical": false, "confidence": "high", "reason": "纯房地产调控政策"}},
  ...
]

confidence 取值：high（明确）/ medium（有一定关联）/ low（边界案例）\
"""


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def _record_hash(title: str, link: str) -> str:
    """MD5(title|link) 作为缓存键，防碰撞且计算快速。"""
    raw = f"{title.strip()}|{link.strip()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _load_cache(cache_path: Path) -> Dict[str, dict]:
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: Dict[str, dict], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_records_block(batch: List[dict]) -> str:
    lines = []
    for i, rec in enumerate(batch):
        title = rec.get("title", "（无标题）")
        dept = rec.get("department", "")
        lines.append(f"{i}. [{dept}] {title}")
    return "\n".join(lines)


def _call_haiku_batch(
    client: anthropic.Anthropic,
    batch: List[dict],
) -> List[dict]:
    """
    调用 Haiku 对一批记录进行分类。
    返回 [{"id": int, "is_medical": bool, "confidence": str, "reason": str}]
    如解析失败则抛出 ValueError。
    """
    records_block = _build_records_block(batch)
    prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(records_block=records_block)

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    # 去除可能存在的 markdown 代码块标记
    if raw.startswith("```"):
        lines = raw.split("\n")
        # 移除首尾的 ``` 行
        raw = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    return json.loads(raw)


# ── 主函数 ────────────────────────────────────────────────────────────────────

def run_llm_filter(
    records: List[dict],
    cache_path: Path = DEFAULT_CACHE_PATH,
    batch_size: int = DEFAULT_BATCH_SIZE,
    verbose: bool = True,
) -> Tuple[List[dict], List[dict]]:
    """
    对 records 列表进行医药相关性过滤。

    返回 (kept_records, dropped_records)。
    每条 record 会被原地添加两个字段：
      - llm_is_medical: bool
      - llm_confidence: str  ("high"/"medium"/"low"/"cached"/"error")

    错误保守策略：
      - 任何异常（API 失败、JSON 解析失败、索引越界）均保留对应记录
      - llm_confidence = "error" 标记异常来源，便于人工核查
    """
    cache = _load_cache(cache_path)
    client = anthropic.Anthropic()

    # 分离已缓存 vs 待分类
    cached_count = 0
    to_classify: List[Tuple[int, dict, str]] = []  # (原始索引, record, hash)

    for i, rec in enumerate(records):
        h = _record_hash(rec.get("title", ""), rec.get("link", ""))
        if h in cache:
            rec["llm_is_medical"] = cache[h]["is_medical"]
            rec["llm_confidence"] = cache[h].get("confidence", "cached")
            cached_count += 1
        else:
            to_classify.append((i, rec, h))

    if verbose:
        print(f"  LLM filter: {cached_count} 条命中缓存，{len(to_classify)} 条待分类")

    # 分批调用
    api_calls = 0
    errors = 0
    total_batches = (len(to_classify) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(to_classify), batch_size):
        batch_entries = to_classify[batch_idx: batch_idx + batch_size]
        batch_records = [entry[1] for entry in batch_entries]
        batch_hashes = [entry[2] for entry in batch_entries]
        current_batch = batch_idx // batch_size + 1

        try:
            results = _call_haiku_batch(client, batch_records)
            api_calls += 1

            # 将 LLM 结果写回 record 并更新 cache
            classified_ids = set()
            for res in results:
                idx = res.get("id")
                if idx is None or idx >= len(batch_records):
                    continue
                classified_ids.add(idx)
                is_med = bool(res.get("is_medical", True))
                conf = res.get("confidence", "medium")
                reason = res.get("reason", "")

                batch_records[idx]["llm_is_medical"] = is_med
                batch_records[idx]["llm_confidence"] = conf

                cache[batch_hashes[idx]] = {
                    "is_medical": is_med,
                    "confidence": conf,
                    "reason": reason,
                }

            # 对 LLM 未返回的记录（response 缺失 id），保守保留
            for j, rec in enumerate(batch_records):
                if j not in classified_ids:
                    rec.setdefault("llm_is_medical", True)
                    rec.setdefault("llm_confidence", "error")

            if verbose:
                batch_label = f"批次 {current_batch}/{total_batches}"
                kept_in_batch = sum(1 for r in batch_records if r.get("llm_is_medical", True))
                print(f"  {batch_label}: 保留 {kept_in_batch}/{len(batch_records)} 条")

            # 批次间限速（避免 rate limit）
            if batch_idx + batch_size < len(to_classify):
                time.sleep(1.0)

        except Exception as e:
            errors += 1
            if verbose:
                print(f"  [WARN] 批次 {current_batch} 调用失败: {e}，整批保留", file=sys.stderr)
            for rec in batch_records:
                rec.setdefault("llm_is_medical", True)
                rec.setdefault("llm_confidence", "error")

        # 每批保存 cache（防止中途中断丢失进度）
        _save_cache(cache, cache_path)

    if verbose:
        print(f"  LLM filter: {api_calls} 次 API 调用，{errors} 次错误")

    kept = [r for r in records if r.get("llm_is_medical", True)]
    dropped = [r for r in records if not r.get("llm_is_medical", True)]

    if verbose:
        print(f"  LLM filter: 保留 {len(kept)} 条，移除 {len(dropped)} 条")
        if dropped:
            print("  移除的记录（前 10 条）:")
            for rec in dropped[:10]:
                print(f"    - {rec.get('title', '')[:60]}")

    return kept, dropped
