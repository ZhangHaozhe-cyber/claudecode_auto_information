import anthropic, json, sys
from datetime import date
from pathlib import Path

def analyze(data_files: list[str], config: dict) -> str:
    client = anthropic.Anthropic()

    # 汇总所有抓取的数据
    all_data = {}
    for f in data_files:
        name = Path(f).stem.rsplit("_", 1)[0]
        all_data[name] = json.loads(Path(f).read_text())

    prompt = f"""
你是一位专业的信息分析师。以下是今日从多个来源抓取的内容：

{json.dumps(all_data, ensure_ascii=False, indent=2)}

报告配置：
- 语言：{config['report']['language']}
- 风格：{config['report']['tone']}
- 需要包含的章节：{', '.join(config['report']['sections'])}

请生成一份结构清晰的 Markdown 报告，包含：
1. 执行摘要（3-5句话概括今日重点）
2. 各信息源的关键内容
3. 跨源趋势分析
4. 最值得关注的 3-5 条内容（附理由）
"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

if __name__ == "__main__":
    config = json.loads(Path("config.json").read_text())
    today = date.today()
    data_files = list(Path("data").glob(f"*_{today}.json"))

    if not data_files:
        print("No data files found for today")
        sys.exit(1)

    report = analyze([str(f) for f in data_files], config)

    Path("reports").mkdir(exist_ok=True)
    out = f"reports/report_{today}.md"
    Path(out).write_text(report)
    print(f"Report saved to {out}")
