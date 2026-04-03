---
title: 中国医药产业政策分析仪表板
emoji: 💊
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.32.0
app_file: app.py
pinned: false
license: mit
---

# 中国医药产业政策分析仪表板

面向集采政策 DID 实证研究的可视化工具，涵盖国务院、国家医保局等主要部委的医药产业政策数据。

## 数据来源

| 部委 | 数据量 | 说明 |
|------|--------|------|
| 国务院 | 192 条 | 2010–2026 年全量政策文件 |
| 国家医保局 | 45 条 | 政策法规与集采专栏 |

## 功能

- **年度趋势图**：按部门分色的政策发文量折线图
- **政策主题实施时间线**：集采、医保、创新药等 7 个主题的热力图
- **多部门 Tab 浏览**：国务院展示文号/成文日期，医保局展示来源栏目
- **数据筛选**：年份、部门、政策主题、关键词多维过滤
- **CSV 导出**：Excel 兼容（UTF-8 BOM 编码）

## 本地运行

```bash
pip install -r requirements.txt
python -X utf8 scripts/clean_data.py   # 生成 parquet
streamlit run app.py
```

## 数据更新

```bash
python pipeline/run_full_pipeline.py [--llm-filter]
```
