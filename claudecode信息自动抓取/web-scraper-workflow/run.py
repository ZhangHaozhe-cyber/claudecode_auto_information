import json, subprocess, sys, os
from datetime import date
from pathlib import Path

# 确保工作目录为脚本所在目录
os.chdir(Path(__file__).parent)

config = json.loads(Path("config.json").read_text(encoding="utf-8"))
sources = config["sources"]

failed = 0
success = 0

print("=== Web Scraper Workflow ===")
print(f"Date: {date.today()}\n")

for source in sources:
    name = source["name"]
    print(f"Scraping: {name} ...")
    result = subprocess.run(
        [sys.executable, "scraper.py", json.dumps(source)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  {result.stdout.strip()}")
        success += 1
    else:
        print(f"  [WARN] Failed to scrape {name}, skipping.")
        print(f"  {result.stderr.strip()}")
        failed += 1

print(f"\nScraping done: {success} succeeded, {failed} failed.")

if success == 0:
    print("[ERROR] All sources failed. Aborting.")
    sys.exit(1)

print("\nRunning analyzer...")
result = subprocess.run([sys.executable, "analyzer.py"], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    print(result.stderr.strip())
    sys.exit(1)

print("\n=== Done ===")
