# Medical Policy Workflow

## 任务目标

自动抓取全球主要创新药研发国家（中国、美国、日本、韩国、德国、英国、瑞士、法国）各监管机构的医药产业政策文件，调用 Claude API 分析并生成 Markdown 格式的日报或周报，用于支撑集采政策影响的 DID 实证研究。

## 执行方式

```bash
# 中国政策日报（默认）
python run.py --country cn --mode daily

# 中国政策周报
python run.py --country cn --mode weekly

# 仅抓取，不生成报告（测试用）
python run.py --country cn --dry-run
```

## 执行流程

1. 读取 `config/{country}.json` 获取数据源列表
2. 对每个数据源运行 `scraper.py` 抓取内容
3. 将原始数据保存到 `data/{country}/{source_name}_{date}.json`
4. 运行 `analyzer.py` 对当日（或本周）数据按部委分组分析
5. 在 `reports/{country}/daily/` 或 `reports/{country}/weekly/` 生成 Markdown 报告

## 目录结构

```
config/         各国数据源配置（china.json 已实现，其余为第二阶段占位）
data/{country}/ 抓取的原始 JSON 数据
reports/        生成的报告
scraper.py      通用抓取器（支持 web / rss 两种类型）
analyzer.py     Claude API 分析模块
run.py          主编排脚本
```

## 错误处理

- 单个数据源抓取失败时跳过并记录，不终止整体流程
- 若所有数据源均失败则报错退出
- 报告的"数据抓取质量说明"章节会注明各源状态

## 依赖安装

```bash
pip install httpx beautifulsoup4 feedparser anthropic
```

## 环境变量

需设置 `ANTHROPIC_API_KEY`。

## 扩展其他国家

在 `config/` 目录下对应国家的 JSON 文件（如 `us.json`）中填入数据源配置，
字段格式参考 `china.json`。
