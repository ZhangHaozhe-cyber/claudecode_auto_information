# Web Scraping Workflow

## 任务目标
自动抓取 config.json 中配置的信息源，清洗数据，调用 AI 分析并生成报告。

## 执行流程
1. 读取 config.json 获取抓取目标列表
2. 对每个目标运行 scraper.py 抓取内容
3. 将原始数据保存到 data/{source_name}_{date}.json
4. 运行 analyzer.py 对所有今日数据进行分析
5. 在 reports/ 目录生成 Markdown 报告

## 错误处理
- 单个目标抓取失败时跳过并记录，不终止整体流程
- 若所有目标均失败则报错退出
- 报告中注明抓取失败的源

## 工具调用
- 使用 Python 运行脚本
- 使用 Anthropic API 进行内容分析
- 报告文件名格式：report_{YYYY-MM-DD}.md
