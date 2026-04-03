import argparse, json, subprocess, sys, os
from datetime import date
from pathlib import Path

# 强制子进程使用 UTF-8，解决 Windows 下中文乱码
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

os.chdir(Path(__file__).parent)

parser = argparse.ArgumentParser(description="Medical Policy Workflow")
parser.add_argument("--country", default="cn", help="Country code (cn/us/jp/kr/de/uk/ch/fr)")
parser.add_argument("--mode", choices=["daily", "weekly"], default=None)
parser.add_argument("--dry-run", action="store_true", help="Only scrape, skip analysis")
args = parser.parse_args()

config_path = Path(f"config/{args.country}.json")
if not config_path.exists():
    print(f"[ERROR] Config not found: {config_path}")
    sys.exit(1)

config = json.loads(config_path.read_text(encoding="utf-8"))
sources = config.get("sources", [])
mode = args.mode or config["report"].get("mode", "daily")
country = config["country"]

if not sources:
    print(f"[ERROR] No sources configured for country '{country}'. Please fill in config/{args.country}.json.")
    sys.exit(1)

# 确保数据和报告目录存在
Path(f"data/{country}").mkdir(parents=True, exist_ok=True)
Path(f"reports/{country}/{mode}").mkdir(parents=True, exist_ok=True)

print(f"=== Medical Policy Workflow ===")
print(f"Country : {config['country_name']} ({country})")
print(f"Mode    : {mode}")
print(f"Date    : {date.today()}\n")

failed = 0
success = 0

for source in sources:
    name = source["name"]
    print(f"Scraping: {name} ({source.get('department', '')}) ...")
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "scraper.py", json.dumps(source, ensure_ascii=False), "--country", country],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode == 0:
        print(f"  {result.stdout.strip()}")
        success += 1
    else:
        print(f"  [WARN] Failed to scrape {name}, skipping.")
        stderr = (result.stderr or "").strip()
        if stderr:
            print(f"  {stderr}")
        failed += 1

print(f"\nScraping done: {success} succeeded, {failed} failed.")

if success == 0:
    print("[ERROR] All sources failed. Aborting.")
    sys.exit(1)

if args.dry_run:
    print("\n[DRY RUN] Skipping analysis.")
    sys.exit(0)

print("\nRunning analyzer...")
result = subprocess.run(
    [sys.executable, "-X", "utf8", "analyzer.py", "--country", country, "--mode", mode],
    capture_output=True, text=True, encoding="utf-8", errors="replace"
)
print(result.stdout.strip())
if result.returncode != 0:
    print(result.stderr.strip())
    sys.exit(1)

print("\n=== Done ===")
