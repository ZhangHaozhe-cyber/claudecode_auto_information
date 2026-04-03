"""
新药研发进度数据抓取器

Pydantic 模型：DrugRecord（drug_name, institution, target, current_phase, event_date）
数据来源：占位 — Phase 3 接入 NMPA/CDE 真实数据源
输出：data/drug_pipeline.json

用法：
  python scripts/scraper_drugs.py          # 生成示例数据（骨架模式）
  python scripts/scraper_drugs.py --live   # 未来接入真实源时启用（Phase 3）
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

ROOT = Path(__file__).parent.parent
OUTPUT_PATH = ROOT / "data" / "drug_pipeline.json"

# ── 数据模型 ─────────────────────────────────────────────────────────────────

PhaseType = Literal["临床I期", "临床II期", "临床III期", "NDA申请", "已上市"]

class DrugRecord(BaseModel):
    """新药研发管线记录。"""
    drug_name: str
    institution: str
    target: str
    current_phase: PhaseType
    event_date: date
    source_url: str = ""
    notes: Optional[str] = None

    model_config = {"str_strip_whitespace": True}

    @field_validator("drug_name", "institution", "target")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("字段不能为空")
        return v

# ── 示例数据（Phase 3 前的占位数据） ─────────────────────────────────────────

MOCK_RECORDS: list[dict] = [
    {
        "drug_name": "阿达木单抗生物类似药（HLX03）",
        "institution": "复宏汉霖",
        "target": "TNF-α",
        "current_phase": "已上市",
        "event_date": "2024-11-01",
        "source_url": "https://www.nmpa.gov.cn",
        "notes": "国内首批获批生物类似药，适应症：类风湿关节炎、强直性脊柱炎",
    },
    {
        "drug_name": "伊努西单抗（IBI318）",
        "institution": "信达生物",
        "target": "PD-1/PD-L1",
        "current_phase": "临床III期",
        "event_date": "2026-01-15",
        "source_url": "https://www.chinadrugtrials.org.cn",
        "notes": "PD-1/PD-L1双特异性抗体，联合化疗用于晚期非小细胞肺癌",
    },
    {
        "drug_name": "格来雷塞（Glecirasib）",
        "institution": "加科思药业",
        "target": "KRAS G12C",
        "current_phase": "临床II期",
        "event_date": "2025-11-20",
        "source_url": "https://www.chinadrugtrials.org.cn",
        "notes": "国内首个进入II期的KRAS G12C抑制剂，适应症：结直肠癌",
    },
    {
        "drug_name": "马西莫德（Mazdutide）",
        "institution": "华东医药",
        "target": "GLP-1R/GIPR",
        "current_phase": "临床III期",
        "event_date": "2026-02-01",
        "source_url": "https://www.chinadrugtrials.org.cn",
        "notes": "GLP-1/GIP双受体激动剂，用于2型糖尿病及肥胖症，III期入组完毕",
    },
    {
        "drug_name": "奥布替尼（Orelabrutinib）",
        "institution": "诺诚健华",
        "target": "BTK",
        "current_phase": "NDA申请",
        "event_date": "2026-03-01",
        "source_url": "https://www.nmpa.gov.cn",
        "notes": "高选择性二代BTK抑制剂，慢淋/套细胞淋巴瘤NDA已受理",
    },
    {
        "drug_name": "瑞卡西单抗（Recaticimab）",
        "institution": "君实生物",
        "target": "PCSK9",
        "current_phase": "临床I期",
        "event_date": "2025-08-10",
        "source_url": "https://www.chinadrugtrials.org.cn",
        "notes": "PCSK9单抗生物类似药，用于高胆固醇血症，I期安全性研究进行中",
    },
]

# ── 异步爬虫骨架（Phase 3 实现） ─────────────────────────────────────────────

async def fetch_nmpa_approvals() -> list[DrugRecord]:
    """
    占位：从 NMPA 官网抓取新药批件信息。
    Phase 3 实现时使用 Playwright + stealth 绕过 412 防爬机制。
    目标 URL：https://www.nmpa.gov.cn/yaowen/ypyw/index.html
    """
    # TODO: implement with playwright + stealth_async
    return []


async def fetch_cde_clinical_trials() -> list[DrugRecord]:
    """
    占位：从药物临床试验登记与信息公示平台抓取在研临床数据。
    Phase 3 实现时使用 aiohttp + BeautifulSoup。
    目标 URL：https://www.chinadrugtrials.org.cn
    """
    # TODO: implement with aiohttp + BeautifulSoup
    return []


async def scrape_all() -> list[DrugRecord]:
    """聚合所有数据源，去重后返回 DrugRecord 列表。"""
    results = await asyncio.gather(
        fetch_nmpa_approvals(),
        fetch_cde_clinical_trials(),
        return_exceptions=True,
    )
    records: list[DrugRecord] = []
    seen: set[str] = set()
    for batch in results:
        if isinstance(batch, Exception):
            print(f"  [WARN] 数据源抓取失败: {batch}")
            continue
        for r in batch:
            key = f"{r.drug_name}|{r.institution}|{r.current_phase}"
            if key not in seen:
                seen.add(key)
                records.append(r)
    return records


# ── 入口 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="新药研发进度数据抓取器")
    parser.add_argument("--live", action="store_true", help="接入真实数据源（Phase 3 启用）")
    args = parser.parse_args()

    print("=== 新药研发进度数据抓取 ===")

    if args.live:
        print("[LIVE] 调用真实数据源（当前为骨架，返回空列表）")
        records = asyncio.run(scrape_all())
    else:
        records = []

    if not records:
        print("[INFO] 无真实抓取数据，使用 MOCK_RECORDS（示例数据）")
        from pydantic import TypeAdapter
        ta: TypeAdapter[list[DrugRecord]] = TypeAdapter(list[DrugRecord])
        records = ta.validate_python(MOCK_RECORDS)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump(mode="json") for r in records]
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"已保存 {len(records)} 条记录 → {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
