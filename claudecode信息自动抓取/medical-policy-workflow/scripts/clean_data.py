"""
政策数据清洗与校验脚本

功能：
1. 从 data/cn/full/*.json 加载所有政策数据
2. 修复 NHSA 的错误日期格式（从 URL 提取真实日期）
3. 使用 Pydantic v2 校验数据完整性
4. 按 link 去重（first-seen wins）
5. 保留 fwzh（文号）、cwrq（成文日期）、source_col 等原始字段
6. （可选）调用 LLM 过滤非医药相关政策（--llm-filter 参数）
7. 标注 7 个政策主题标签列（tag_集采 等）
8. 输出 output/cleaned_policies.parquet 和 output/error_log.json

用法：
  python -X utf8 scripts/clean_data.py
  python -X utf8 scripts/clean_data.py --llm-filter         # 含LLM过滤
  python -X utf8 scripts/clean_data.py --llm-filter --llm-cache output/my_cache.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd
from pydantic import BaseModel, ValidationError, field_validator

os.environ["PYTHONIOENCODING"] = "utf-8"

# 确保项目根目录在 sys.path 中，使 `from scripts.llm_filter import ...` 可解析
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data" / "cn" / "full"
OUTPUT_DIR = ROOT / "output"

# ── Pydantic 数据模型 ──────────────────────────────────────────────────────────

class PolicySchema(BaseModel):
    title: str
    department: str
    pub_date: datetime
    link: str           # 保留 str，避免 HttpUrl 规范化影响去重
    summary: Optional[str] = None
    policy_type: Optional[str] = None
    source_file: str
    # 国务院文件专属字段
    cwrq: Optional[str] = None          # 成文日期
    fwzh: Optional[str] = None          # 文号，如"国办发〔2010〕4号"
    # NHSA 专属字段
    source_col: Optional[str] = None    # 来源栏目（col104/col147等）
    # LLM 过滤结果（仅在 --llm-filter 时有值）
    llm_is_medical: Optional[bool] = None
    llm_confidence: Optional[str] = None

    model_config = {"str_strip_whitespace": True}

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v

    @field_validator("link")
    @classmethod
    def link_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("link must not be empty")
        return v

# ── 政策主题标签体系 ──────────────────────────────────────────────────────────

KEYWORD_TAXONOMY: dict[str, list[str]] = {
    "集采":    ["集采", "带量采购", "集中带量采购", "联采", "集中采购"],
    "医保":    ["医保谈判", "医保目录", "医疗保障", "基本医疗保险", "医保"],
    "创新药":  ["创新药", "生物制品", "生物医药", "新药", "生命科学"],
    "医改":    ["医改", "医药卫生体制", "医疗卫生改革", "医疗体制"],
    "临床试验": ["临床试验", "药物临床试验"],
    "药监":    ["药品监管", "药品审评", "药品注册", "药品监督", "药品管理"],
    "疫苗":    ["疫苗", "预防接种"],
}

# ── 日期解析 ──────────────────────────────────────────────────────────────────

_ISO_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y年%m月%d日"]
_NHSA_URL_PATTERN = re.compile(r"/art/(\d{4})/(\d{1,2})/(\d{1,2})/")


def parse_pub_date(raw: str, link: str) -> Optional[datetime]:
    """
    解析发布日期：
    1. 尝试标准格式（gov_policy 等来源）
    2. 失败则从 URL 提取（NHSA 的 /art/YYYY/M/D/ 格式）
    3. 均失败返回 None → 进入 error_log
    """
    for fmt in _ISO_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue

    m = _NHSA_URL_PATTERN.search(link)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d)
        except ValueError:
            pass

    return None


# ── 数据加载与去重 ────────────────────────────────────────────────────────────

def load_json_files(data_dir: Path) -> Tuple[List[dict], List[dict]]:
    """
    按文件名字母序加载 data_dir 下所有 *.json 文件。
    返回 (valid_records, error_records)。
    - 按 link 去重（first-seen wins）
    - 日期无法解析的记录进入 error_records
    - 每条记录附加 source_file 字段
    """
    seen_links: set = set()
    valid_records: List[dict] = []
    error_records: List[dict] = []

    for json_path in sorted(data_dir.glob("*.json")):
        try:
            raw_list = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [WARN] 读取 {json_path.name} 失败: {e}", file=sys.stderr)
            continue

        if not isinstance(raw_list, list):
            print(f"  [SKIP] {json_path.name} 不是列表格式", file=sys.stderr)
            continue

        file_valid = file_error = 0
        for record in raw_list:
            link = record.get("link", "").strip()
            if link in seen_links:
                continue
            seen_links.add(link)

            raw_date = record.get("pub_date", "")
            parsed_date = parse_pub_date(raw_date, link)

            record = dict(record)
            record["source_file"] = json_path.name
            record["_parsed_date"] = parsed_date

            if parsed_date is None:
                record["_error"] = (
                    f"Cannot parse pub_date={raw_date!r}; "
                    f"no /art/YYYY/M/D/ found in link={link!r}"
                )
                error_records.append(record)
                file_error += 1
            else:
                valid_records.append(record)
                file_valid += 1

        print(f"  {json_path.name}: {file_valid} 条有效，{file_error} 条日期错误")

    return valid_records, error_records


# ── 政策主题标注 ──────────────────────────────────────────────────────────────

def build_keyword_tags(title: str) -> dict:
    """生成 7 个政策主题 bool 列，以及展示用的顿号拼接字符串。"""
    tags = {}
    active_labels = []
    for label, keywords in KEYWORD_TAXONOMY.items():
        hit = any(kw in title for kw in keywords)
        tags[f"tag_{label}"] = hit
        if hit:
            active_labels.append(label)
    tags["tags_display"] = "、".join(active_labels) if active_labels else ""
    return tags


# ── Pydantic 校验 + DataFrame 构建 ───────────────────────────────────────────

def validate_and_convert(records: List[dict]) -> Tuple[pd.DataFrame, List[dict]]:
    """
    逐条通过 PolicySchema 校验，构建最终 DataFrame。
    校验失败的记录追加到 pydantic_errors 列表。
    """
    rows = []
    pydantic_errors = []

    for rec in records:
        try:
            obj = PolicySchema(
                title=rec.get("title", ""),
                department=rec.get("department", ""),
                pub_date=rec["_parsed_date"],
                link=rec.get("link", ""),
                summary=rec.get("summary"),
                policy_type=rec.get("policy_type"),
                source_file=rec.get("source_file", ""),
                # 新增字段：原始 JSON 中存在时透传，否则为 None
                cwrq=rec.get("cwrq") or None,
                fwzh=rec.get("fwzh") or None,
                source_col=rec.get("source_col") or None,
                llm_is_medical=rec.get("llm_is_medical"),
                llm_confidence=rec.get("llm_confidence"),
            )
        except ValidationError as e:
            pydantic_errors.append({**rec, "_error": str(e)})
            continue

        row = obj.model_dump()
        row["year"] = obj.pub_date.year
        row["month"] = obj.pub_date.month
        row.update(build_keyword_tags(obj.title))
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["pub_date"] = pd.to_datetime(df["pub_date"])

    return df, pydantic_errors


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="政策数据清洗与校验")
    parser.add_argument(
        "--llm-filter",
        action="store_true",
        default=False,
        help="使用 LLM（claude-3-5-haiku）过滤非医药相关政策，需设置 ANTHROPIC_API_KEY",
    )
    parser.add_argument(
        "--llm-cache",
        default=str(OUTPUT_DIR / "llm_filter_cache.json"),
        help="LLM 过滤结果缓存文件路径",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"\n=== 政策数据清洗 ===")
    print(f"数据目录: {DATA_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    if args.llm_filter:
        print(f"LLM 过滤: 开启（缓存: {args.llm_cache}）")
    print()

    # 1. 加载 + 去重 + 日期解析
    valid_records, date_errors = load_json_files(DATA_DIR)
    print(f"\n共加载: {len(valid_records)} 条有效，{len(date_errors)} 条日期错误")

    # 1.5 （可选）LLM 医药相关性过滤
    llm_dropped = []
    if args.llm_filter:
        print("\n[LLM Filter] 运行医药相关性分类...")
        try:
            from scripts.llm_filter import run_llm_filter
            valid_records, llm_dropped = run_llm_filter(
                valid_records,
                cache_path=Path(args.llm_cache),
                verbose=True,
            )
            print(f"  过滤后保留: {len(valid_records)} 条，移除: {len(llm_dropped)} 条")
        except ImportError:
            print("  [ERROR] 无法导入 scripts.llm_filter，跳过 LLM 过滤", file=sys.stderr)
        except Exception as e:
            print(f"  [ERROR] LLM 过滤失败: {e}，跳过", file=sys.stderr)

    # 2. Pydantic 校验 + 政策主题标注
    df, pydantic_errors = validate_and_convert(valid_records)
    all_errors = date_errors + pydantic_errors + llm_dropped
    print(f"DataFrame: {len(df)} 行；Pydantic 校验错误: {len(pydantic_errors)} 条")

    if df.empty:
        print("[ERROR] 没有可用数据，请检查 data/cn/full/ 目录", file=sys.stderr)
        sys.exit(1)

    # 3. 保存 Parquet
    parquet_path = OUTPUT_DIR / "cleaned_policies.parquet"
    df.to_parquet(parquet_path, index=False, engine="pyarrow")
    print(f"\n已保存: {parquet_path.name} ({len(df)} 行)")

    # 政策主题统计
    tag_cols = [c for c in df.columns if c.startswith("tag_")]
    print("\n政策主题分类分布:")
    for col in tag_cols:
        count = int(df[col].sum())
        label = col.replace("tag_", "")
        print(f"  {label}: {count} 条")

    # 新增字段统计
    for field, label in [("fwzh", "文号"), ("cwrq", "成文日期"), ("source_col", "来源栏目")]:
        if field in df.columns:
            n = int(df[field].notna().sum())
            print(f"  {label}({field}): {n} 条有值")

    # 4. 保存 error_log（包含日期错误 + Pydantic 错误 + LLM 过滤移除记录）
    error_path = OUTPUT_DIR / "error_log.json"

    def _clean_error(rec: dict) -> dict:
        return {
            k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            for k, v in rec.items()
            if not k.startswith("_parsed")
        }

    error_path.write_text(
        json.dumps([_clean_error(e) for e in all_errors], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已保存: error_log.json ({len(date_errors + pydantic_errors)} 条数据错误，"
          f"{len(llm_dropped)} 条 LLM 过滤移除)")
    print("\n=== 完成 ===\n")


if __name__ == "__main__":
    main()
