"""
自动数据更新流水线（扩展版）

执行步骤：
  1. 合并 data/cn/full/*.json → 去重 → 保存 data/cleaned_policies.json
  2. 运行 scripts/clean_data.py → 生成 output/cleaned_policies.parquet
  3. 运行 scripts/scraper_drugs.py → 生成 data/drug_pipeline.json
  4. [STUB] DeepSeek API 增强分析 — Phase 3 实现
  5. 生成 Next.js 前端所需的分类 JSON 文件

用法：
  python scripts/auto_pipeline.py                   # 标准流水线
  python scripts/auto_pipeline.py --skip-drugs      # 跳过药管线抓取
  python scripts/auto_pipeline.py --skip-frontend   # 跳过前端 JSON 生成（Step 5）
  python scripts/auto_pipeline.py --llm-filter      # 启用 LLM 语义过滤（需 ANTHROPIC_API_KEY）
  python scripts/auto_pipeline.py --dry-run         # 仅打印步骤，不执行

注意：DeepSeek 集成在 Phase 3 添加，当前为占位（step4_deepseek_stub）
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "cn" / "full"
CLEANED_JSON_PATH = ROOT / "data" / "cleaned_policies.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 工具函数 ─────────────────────────────────────────────────────────────────

def _run(cmd: list[str], step: str) -> None:
    """执行子进程命令，失败时打印错误并退出。"""
    print(f"\n{'─' * 55}\n  {step}")
    result = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    if result.returncode != 0:
        print(f"\n[ERROR] 步骤失败 (exit {result.returncode}): {step}", file=sys.stderr)
        sys.exit(result.returncode)

# ── Step 1：合并政策 JSON ─────────────────────────────────────────────────────

def step1_merge_policies() -> int:
    """
    读取 data/cn/full/*.json → 按 link 字段去重（first-seen wins）
    → 保存中间文件 data/cleaned_policies.json。
    此文件不是最终产物，只是 clean_data.py 的数据上游。
    返回合并后的记录总数。
    """
    if not DATA_DIR.exists():
        print(f"  [WARN] 数据目录不存在，跳过合并: {DATA_DIR}")
        return 0

    seen_links: set[str] = set()
    all_records: list[dict] = []

    for json_path in sorted(DATA_DIR.glob("*.json")):
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [WARN] 读取失败，跳过 {json_path.name}: {e}")
            continue
        if not isinstance(raw, list):
            continue
        before = len(all_records)
        for rec in raw:
            link = rec.get("link", "").strip()
            if link and link not in seen_links:
                seen_links.add(link)
                all_records.append(rec)
        added = len(all_records) - before
        print(f"  {json_path.name}: +{added} 条")

    CLEANED_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLEANED_JSON_PATH.write_text(
        json.dumps(all_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  合并完成：共 {len(all_records)} 条去重记录 → {CLEANED_JSON_PATH.name}")
    return len(all_records)


# ── Step 2：clean_data.py → parquet ──────────────────────────────────────────

def step2_clean_data(llm_filter: bool) -> None:
    cmd = [sys.executable, "-X", "utf8", "scripts/clean_data.py"]
    if llm_filter:
        cmd.append("--llm-filter")
    _run(cmd, "2. clean_data.py → output/cleaned_policies.parquet")


# ── Step 3：scraper_drugs.py → drug_pipeline.json ────────────────────────────

def step3_scrape_drugs() -> None:
    _run(
        [sys.executable, "-X", "utf8", "scripts/scraper_drugs.py"],
        "3. scraper_drugs.py → data/drug_pipeline.json",
    )


# ── Step 4：DeepSeek 增强分析（占位） ────────────────────────────────────────

# ── Mock data for news and academic (mirrors Streamlit pages) ─────────────────

MOCK_NEWS: list[dict] = [
    {
        "date": "2026-03-28",
        "title": "第十一批国家集中带量采购结果公布，45个品种中选，平均降幅62%",
        "tags": ["集采", "医保"],
        "summary": (
            "国家医保局联合多部委正式发布第十一批药品集中带量采购结果。本批次共45个品种、"
            "328个产品中选，平均降幅达62%。其中心血管类药物占比最高，阿托伐他汀钙、"
            "瑞舒伐他汀等多个大品种降价明显。业界预计本批次将进一步压缩仿制药市场空间，"
            "头部企业加速转型创新药赛道。"
        ),
    },
    {
        "date": "2026-03-15",
        "title": "国家药监局优化创新药审评审批流程，临床急需品种最快90天获批",
        "tags": ["创新药", "监管"],
        "summary": (
            "国家药监局发布《关于进一步优化创新药审评审批工作的若干措施》，"
            "对临床急需的创新药实行优先审评审批，承诺最快90个工作日完成技术审查。"
            "同时新设「突破性治疗药物」认定通道，适用于针对严重威胁生命疾病且现有治疗手段不足的品种。"
        ),
    },
    {
        "date": "2026-02-28",
        "title": "DRG/DIP支付改革全面扩面，全国统一医保结算标准年内落地",
        "tags": ["DRG", "DIP", "医改"],
        "summary": (
            "国家医保局宣布，2026年底前DRG/DIP支付方式改革将覆盖全国所有统筹地区，"
            "三级公立医院参与率须达到100%。配套出台的《全国统一医保结算标准》同步落地，"
            "解决地区间结算数据互认难题。"
        ),
    },
    {
        "date": "2026-02-10",
        "title": "国家药监局发布医疗器械网络销售监督管理办法（修订版），明确平台主体责任",
        "tags": ["器械", "监管"],
        "summary": (
            "《医疗器械网络销售监督管理办法》（修订版）正式发布，将于2026年6月1日施行。"
            "修订版强化电商平台主体责任，要求平台对入驻商家的经营资质进行实质性审核，"
            "并建立违规产品快速下架机制。"
        ),
    },
    {
        "date": "2026-01-20",
        "title": "生物类似药纳入集采政策细则出台，首批包含单抗类药物5个品种",
        "tags": ["集采", "创新药"],
        "summary": (
            "国家医保局、卫健委联合印发《生物类似药集中带量采购工作指引》，"
            "明确生物类似药纳入集采的质量等效性评价标准和申报条件。"
            "首批纳入范围的5个单抗品种包括曲妥珠单抗、贝伐珠单抗等肿瘤治疗大品种。"
        ),
    },
]

MOCK_ACADEMIC: list[dict] = [
    {
        "title": "集中带量采购对原研药企业创新投入的影响——基于DID方法的实证分析",
        "authors": "张伟, 李明华, 王晓东",
        "journal": "中国卫生经济, 2025, Vol.44(3): 12–19",
        "pub_date": "2025-03",
        "keywords": ["集中带量采购", "创新投入", "DID", "原研药"],
        "url": "#",
        "abstract": (
            "本文利用2018—2024年上市制药企业季度面板数据，以国家集中带量采购批次实施时间为准自然实验，"
            "采用双重差分（DID）方法识别集采政策对企业研发投入的因果效应。研究发现：集采实施后，"
            "受冲击产品主要生产企业的研发支出占比平均下降1.8个百分点（p<0.01），"
            "但创新型企业的效应不显著。机制检验显示，利润压缩是核心传导渠道。"
        ),
    },
    {
        "title": "药品集中采购价格机制与仿制药质量一致性：基于医院用药数据的准实验研究",
        "authors": "李明华, 陈静, 赵磊",
        "journal": "经济研究, 2024, Vol.59(8): 78–95",
        "pub_date": "2024-08",
        "keywords": ["质量一致性", "集采价格", "仿制药", "准实验"],
        "url": "#",
        "abstract": (
            "价格竞争是否影响仿制药质量是集采政策评估的核心争议。本文以第三、四批国家集采品种为处理组，"
            "利用三甲医院用药数据库中的药物不良反应上报记录，构建仿制药质量替代指标。"
            "断点回归（RDD）结果表明，集采中选仿制药的质量投诉率与对照组无统计显著差异（p=0.38）。"
        ),
    },
    {
        "title": "医保目录动态调整对创新药可及性的影响：来自中国的证据",
        "authors": "王晓东, 孙菊, 刘洋",
        "journal": "卫生经济研究, 2025, Vol.42(1): 3–15",
        "pub_date": "2025-01",
        "keywords": ["医保目录", "创新药可及性", "价格谈判", "Panel Data"],
        "url": "#",
        "abstract": (
            "本文基于31个省城镇职工医保数据与NMPA药品批准数据库的匹配面板，"
            "评估谈判纳入目录对创新药使用量的影响。事件研究法结果显示，"
            "谈判成功后12个月内，用药人数中位数增长约3.2倍（95%CI: 2.7–3.8）。"
        ),
    },
    {
        "title": "DRG支付改革对住院医疗服务行为的影响——基于百城医保数据的DID估计",
        "authors": "陈静, 方洁, 黄彦",
        "journal": "管理世界, 2024, Vol.40(11): 120–138",
        "pub_date": "2024-11",
        "keywords": ["DRG", "住院服务", "诱导需求", "DID"],
        "url": "#",
        "abstract": (
            "本文利用国家医保局试点城市的逐笔住院结算数据，以试点启动时间为外生冲击，"
            "采用交错双重差分（Staggered DID）方法评估改革效果。主要结论：DRG改革使"
            "试点城市次均住院费用下降约8.3%（se=1.2%），平均住院日缩短0.7天（se=0.09）。"
        ),
    },
]


def step4_deepseek_enrich(sample_size: int = 10) -> None:
    """对最新日期的政策记录做小样本 DeepSeek 增强标注并回写 parquet。"""
    print(f"\n{'─' * 55}")
    print(f"  4. DeepSeek 增强分析（最新日期抽样 {sample_size} 条）")

    if not PARQUET_PATH.exists():
        print(f"  [WARN] {PARQUET_PATH.name} 不存在，跳过 step4")
        return

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("  [WARN] 未设置 DEEPSEEK_API_KEY，跳过 step4")
        return

    try:
        import pandas as pd
    except ImportError:
        print("  [WARN] pandas 未安装，跳过 step4")
        return

    try:
        from analyzer import enrich_policy_records
    except Exception as e:
        print(f"  [WARN] 无法导入 analyzer.enrich_policy_records: {e}")
        return

    df = pd.read_parquet(PARQUET_PATH)
    if df.empty:
        print("  [WARN] cleaned_policies.parquet 为空，跳过 step4")
        return

    df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce")
    latest_date = df["pub_date"].max()
    latest_df = df[df["pub_date"] == latest_date].copy()
    if latest_df.empty:
        print("  [WARN] 最新日期切片为空，跳过 step4")
        return

    sample_df = latest_df.sort_values("pub_date", ascending=False).head(sample_size).copy()
    records = sample_df.to_dict("records")
    try:
        enriched = enrich_policy_records(records, sample_size=sample_size)
    except Exception as e:
        print(f"  [WARN] Step4 调用 DeepSeek 失败: {e}")
        return
    if not enriched:
        print("  [WARN] DeepSeek 未返回可解析增强结果，保留原 parquet")
        return

    for col, default in (("llm_relevance", ""), ("llm_tags", ""), ("llm_reason", "")):
        if col not in df.columns:
            df[col] = default

    for row in enriched:
        idx = row["idx"]
        src = records[idx]
        mask = (df["link"] == src.get("link", "")) & (df["title"] == src.get("title", ""))
        if not mask.any():
            continue
        df.loc[mask, "llm_relevance"] = row.get("llm_relevance", "")
        df.loc[mask, "llm_tags"] = "、".join(row.get("llm_tags", []))
        df.loc[mask, "llm_reason"] = row.get("llm_reason", "")

    df.to_parquet(PARQUET_PATH, index=False, engine="pyarrow")
    print(f"  已回写增强结果到 {PARQUET_PATH.name}（命中 {len(enriched)} 条）")


# ── Step 5：生成 Next.js 前端 JSON 文件 ──────────────────────────────────────

PARQUET_PATH = ROOT / "output" / "cleaned_policies.parquet"
DRUG_JSON_PATH = ROOT / "data" / "drug_pipeline.json"
FRONTEND_DATA_ROOT = ROOT / "data"

TAG_COLS = [
    "tag_集采", "tag_医保", "tag_创新药", "tag_医改",
    "tag_临床试验", "tag_药监", "tag_疫苗",
]


def _write_json(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"  Wrote {len(data):4d} records → {path.relative_to(ROOT)}")


def step5_generate_frontend_json() -> None:
    """
    Step 5: 生成 Next.js 前端消费的分类 JSON 文件。

    读取:
      output/cleaned_policies.parquet  (step2 生成)
      data/drug_pipeline.json          (step3 生成)

    写入:
      data/biomedicine/china/policy_all.json
      data/biomedicine/china/policy_monthly.json
      data/biomedicine/china/news_monthly.json
      data/biomedicine/china/drugs_monthly.json
      data/biomedicine/china/academic_monthly.json
      data/biomanufacturing/china/policy_all.json
      data/biomanufacturing/china/news_monthly.json
      data/biomanufacturing/china/academic_monthly.json
    """
    try:
        import pandas as pd
    except ImportError:
        print("  [WARN] pandas 未安装，跳过 step5")
        return

    print(f"\n{'─' * 55}\n  5. Generate frontend JSON files")

    if not PARQUET_PATH.exists():
        print(f"  [WARN] {PARQUET_PATH.name} 不存在，跳过 step5（先运行 step2）")
        return

    df = pd.read_parquet(PARQUET_PATH)
    df["pub_date"] = pd.to_datetime(df["pub_date"])

    today = datetime.date.today()
    cur_year, cur_month = today.year, today.month

    def to_policy_records(df_slice: "pd.DataFrame") -> list[dict]:
        records = []
        for _, row in df_slice.iterrows():
            rec: dict = {
                "title":        str(row.get("title", "")),
                "link":         str(row.get("link", "")),
                "pub_date":     row["pub_date"].strftime("%Y-%m-%d"),
                "department":   str(row.get("department", "")),
                "policy_type":  row.get("policy_type") or None,
                "cwrq":         row.get("cwrq") or None,
                "fwzh":         row.get("fwzh") or None,
                "source_col":   row.get("source_col") or None,
                "tags_display": row.get("tags_display") or None,
            }
            for col in TAG_COLS:
                rec[col] = bool(row[col]) if col in df_slice.columns else False
            records.append(rec)
        return records

    # ── 1. Biomedicine: ALL policies ──────────────────────────────────────────
    _write_json(
        FRONTEND_DATA_ROOT / "biomedicine" / "china" / "policy_all.json",
        to_policy_records(df.sort_values("pub_date", ascending=False)),
    )

    # ── 2. Biomedicine: MONTHLY policies ─────────────────────────────────────
    monthly = df[(df["pub_date"].dt.year == cur_year) & (df["pub_date"].dt.month == cur_month)]
    if monthly.empty:
        latest = df["pub_date"].max()
        monthly = df[(df["pub_date"].dt.year == latest.year) & (df["pub_date"].dt.month == latest.month)]
    _write_json(
        FRONTEND_DATA_ROOT / "biomedicine" / "china" / "policy_monthly.json",
        to_policy_records(monthly.sort_values("pub_date", ascending=False)),
    )

    # ── 3. Biomedicine: News (mock) ───────────────────────────────────────────
    _write_json(
        FRONTEND_DATA_ROOT / "biomedicine" / "china" / "news_monthly.json",
        MOCK_NEWS,
    )

    # ── 4. Biomedicine: Drugs (copy drug_pipeline.json) ───────────────────────
    drug_records: list[dict] = []
    if DRUG_JSON_PATH.exists():
        try:
            drug_records = json.loads(DRUG_JSON_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [WARN] 读取 drug_pipeline.json 失败: {e}")
    _write_json(
        FRONTEND_DATA_ROOT / "biomedicine" / "china" / "drugs_monthly.json",
        drug_records,
    )

    # ── 5. Biomedicine: Academic (mock) ───────────────────────────────────────
    _write_json(
        FRONTEND_DATA_ROOT / "biomedicine" / "china" / "academic_monthly.json",
        MOCK_ACADEMIC,
    )

    # ── 6. Biomanufacturing: policies (工信部 OR tag_创新药) ───────────────────
    mfg_mask = df["department"].str.contains("工信部|工业和信息化", na=False)
    if "tag_创新药" in df.columns:
        mfg_mask = mfg_mask | df["tag_创新药"].astype(bool)
    df_mfg = df[mfg_mask].sort_values("pub_date", ascending=False)
    _write_json(
        FRONTEND_DATA_ROOT / "biomanufacturing" / "china" / "policy_all.json",
        to_policy_records(df_mfg),
    )

    # ── 7-8. Biomanufacturing: News + Academic stubs ──────────────────────────
    _write_json(FRONTEND_DATA_ROOT / "biomanufacturing" / "china" / "news_monthly.json", [])
    _write_json(FRONTEND_DATA_ROOT / "biomanufacturing" / "china" / "academic_monthly.json", [])

    print(f"  step5 完成 — 月度切片：{cur_year}-{cur_month:02d}")


# ── 主流程 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="医药产业信息平台 — 自动数据更新流水线")
    parser.add_argument("--skip-drugs", action="store_true", help="跳过药管线数据抓取（Step 3）")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过前端 JSON 生成（Step 5）")
    parser.add_argument("--llm-filter", action="store_true", help="启用 LLM 语义过滤（需 ANTHROPIC_API_KEY）")
    parser.add_argument("--step4-sample", type=int, default=10, help="Step4 DeepSeek 增强抽样条数（默认10）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印执行计划，不实际运行")
    args = parser.parse_args()

    print(f"\n{'#' * 55}")
    print("  自动数据更新流水线")
    print(f"{'#' * 55}")

    if args.dry_run:
        print("\n[DRY RUN] 计划执行以下步骤：")
        print("  1. 合并 data/cn/full/*.json → data/cleaned_policies.json")
        print("  2. clean_data.py → output/cleaned_policies.parquet")
        if not args.skip_drugs:
            print("  3. scraper_drugs.py → data/drug_pipeline.json")
        else:
            print("  3. [跳过] scraper_drugs.py")
        print(f"  4. DeepSeek 增强分析（抽样 {args.step4_sample} 条）")
        if not args.skip_frontend:
            print("  5. Generate frontend JSON (data/biomedicine/... data/biomanufacturing/...)")
        return

    n = step1_merge_policies()
    step2_clean_data(args.llm_filter)

    if not args.skip_drugs:
        step3_scrape_drugs()
    else:
        print("\n  [跳过] Step 3: scraper_drugs.py（--skip-drugs）")

    step4_deepseek_enrich(sample_size=args.step4_sample)

    if not args.skip_frontend:
        step5_generate_frontend_json()
    else:
        print("\n  [跳过] Step 5: frontend JSON（--skip-frontend）")

    print(f"\n{'=' * 55}")
    print(f"  流水线完成：处理 {n} 条政策记录")
    print()
    print("  下一步：提交数据文件并部署")
    print("  git add output/cleaned_policies.parquet data/")
    print("  git commit -m 'data: update policy, drug pipeline, and frontend JSON'")
    print("  git push")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
