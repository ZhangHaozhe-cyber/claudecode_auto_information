"""
医药政策数据全量更新流水线

执行步骤：
  1. 调用 run.py 抓取当日最新政策（可跳过）
  2. 将新数据合并入 data/cn/full/（按 link 去重）
  3. 运行 scripts/clean_data.py 重新生成 parquet（可含 LLM 过滤）
  4. 打印更新摘要，提示 git push 到 HF Spaces

用法：
  python pipeline/run_full_pipeline.py
  python pipeline/run_full_pipeline.py --skip-scrape       # 只重跑清洗
  python pipeline/run_full_pipeline.py --llm-filter        # 含 LLM 医药过滤
  python pipeline/run_full_pipeline.py --dry-run           # 只打印步骤，不执行
  python pipeline/run_full_pipeline.py --country cn        # 指定国家（默认 cn）
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def run_step(cmd: list, step_name: str, dry_run: bool = False) -> None:
    print(f"\n{'─'*55}")
    print(f"步骤: {step_name}")
    print(f"命令: {' '.join(str(c) for c in cmd)}")
    if dry_run:
        print("[DRY RUN] 跳过执行")
        return
    result = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    if result.returncode != 0:
        print(f"[ERROR] '{step_name}' 失败（exit code {result.returncode}）", file=sys.stderr)
        sys.exit(result.returncode)


def merge_new_data(data_dir: Path, full_dir: Path, today: date, country: str) -> int:
    """
    将 data_dir 下当日生成的 {source}_{date}.json 合并入 full_dir/{source}.json。
    按 link 去重（full/ 中已有的不重复添加）。
    返回新增记录数。
    """
    date_str = today.isoformat()
    full_dir.mkdir(parents=True, exist_ok=True)
    new_total = 0

    for new_file in sorted(data_dir.glob(f"*_{date_str}.json")):
        source_name = new_file.stem[: -len(f"_{date_str}")]
        target_path = full_dir / f"{source_name}.json"

        try:
            new_records: list = json.loads(new_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [WARN] 读取 {new_file.name} 失败: {e}")
            continue

        if target_path.exists():
            existing: list = json.loads(target_path.read_text(encoding="utf-8"))
            existing_links = {r.get("link", "") for r in existing}
            added = [r for r in new_records if r.get("link", "") not in existing_links]
            existing.extend(added)
            target_path.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  合并 {new_file.name} → {target_path.name}：新增 {len(added)} 条")
            new_total += len(added)
        else:
            target_path.write_text(
                json.dumps(new_records, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  创建 {target_path.name}：{len(new_records)} 条")
            new_total += len(new_records)

    return new_total


def print_summary(parquet_path: Path, new_records: int) -> None:
    try:
        import pandas as pd
        df = pd.read_parquet(parquet_path)
        print(f"\n{'='*55}")
        print("更新摘要:")
        print(f"  parquet 总行数: {len(df)}")
        print(f"  本次新增记录: {new_records}")
        print(f"  年份范围: {df['year'].min()} – {df['year'].max()}")
        dept_counts = df["department"].value_counts()
        for dept, count in dept_counts.items():
            print(f"    {dept}: {count} 条")
        if "llm_is_medical" in df.columns:
            n = df["llm_is_medical"].notna().sum()
            print(f"  LLM 过滤标注: {n} 条")
    except Exception as e:
        print(f"  [WARN] 无法生成摘要: {e}")


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="医药政策数据全量更新流水线")
    parser.add_argument("--country", default="cn", help="国家代码（默认 cn）")
    parser.add_argument("--skip-scrape", action="store_true", help="跳过抓取步骤")
    parser.add_argument("--llm-filter", action="store_true", help="运行 LLM 医药相关性过滤")
    parser.add_argument("--dry-run", action="store_true", help="只打印命令，不实际执行")
    args = parser.parse_args()

    today = date.today()
    data_dir = ROOT / "data" / args.country
    full_dir = data_dir / "full"
    parquet_path = ROOT / "output" / "cleaned_policies.parquet"

    print(f"\n{'#'*55}")
    print(f"# 医药政策数据更新流水线")
    print(f"# 日期: {today}  国家: {args.country}")
    if args.dry_run:
        print("# 模式: DRY RUN（仅显示步骤）")
    print(f"{'#'*55}")

    # ── 步骤 1：抓取 ────────────────────────────────────────────────────────
    new_records = 0
    if not args.skip_scrape:
        run_step(
            [sys.executable, "-X", "utf8", "run.py", "--country", args.country, "--dry-run"],
            "1. 抓取当日最新政策（--dry-run 模式，仅抓不分析）",
            dry_run=args.dry_run,
        )

        # ── 步骤 2：合并 ────────────────────────────────────────────────────
        print(f"\n{'─'*55}")
        print("步骤: 2. 合并新数据到 full/ 目录")
        if not args.dry_run:
            new_records = merge_new_data(data_dir, full_dir, today, args.country)
            print(f"  共新增 {new_records} 条记录")
        else:
            print(f"[DRY RUN] 将合并 data/{args.country}/*_{today}.json → data/{args.country}/full/")
    else:
        print("\n[SKIP] 跳过抓取和合并步骤（--skip-scrape）")

    # ── 步骤 3：清洗 ────────────────────────────────────────────────────────
    clean_cmd = [sys.executable, "-X", "utf8", "scripts/clean_data.py"]
    if args.llm_filter:
        clean_cmd.append("--llm-filter")

    run_step(clean_cmd, "3. 数据清洗 → 生成 parquet", dry_run=args.dry_run)

    # ── 步骤 4：摘要 ────────────────────────────────────────────────────────
    if not args.dry_run:
        print_summary(parquet_path, new_records)

    # ── 提示 git push ───────────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    print("下一步：推送数据到 Hugging Face Spaces")
    print()
    print("  # 进入 HF Space 本地 clone 目录")
    print("  cd /path/to/hf-space-clone")
    print()
    print("  # 复制最新 parquet（以及如需更新 JSON 源文件）")
    print("  cp output/cleaned_policies.parquet /path/to/hf-space-clone/output/")
    print()
    print("  git add output/cleaned_policies.parquet")
    print(f"  git commit -m 'data: update {today}'")
    print("  git push")
    print()
    print("  HF Spaces 收到 push 后自动重启，@st.cache_data 失效，新数据立即生效。")
    print(f"\n{'#'*55}\n")


if __name__ == "__main__":
    main()
