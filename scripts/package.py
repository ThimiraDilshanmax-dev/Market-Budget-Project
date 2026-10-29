"""Create a portable project bundle without credentials, Git history or user data."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "deliverables"
OUTPUT.mkdir(exist_ok=True)
archive = OUTPUT / "MarketBudget-project.zip"
excluded_parts = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".openai"}
paths=[]
for path in sorted(ROOT.rglob("*")):
    relative=path.relative_to(ROOT)
    if not path.is_file() or any(p in excluded_parts for p in relative.parts):
        continue
    if any(p.endswith(".egg-info") for p in relative.parts):
        continue
    if relative.parts[:2] == ("dist", "downloads") or ".sqlite3" in path.name or path.suffix == ".pyc":
        continue
    paths.append(path)
with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
    for path in paths:
        bundle.write(path,"MarketBudget/"+path.relative_to(ROOT).as_posix())
manifest={"file":archive.name,"bytes":archive.stat().st_size,"sha256":sha256(archive.read_bytes()).hexdigest(),
          "files":len(paths),"note":"Contains code, research source data, artifacts and docs. Excludes hosting identity, credentials, Git history and user database."}
(OUTPUT / "MarketBudget-project.manifest.json").write_text(json.dumps(manifest,indent=2))
for name in ("MarketBudget-Technical-Report.pdf","MarketBudget-Two-Page-Summary.pdf"):
    shutil.copy2(ROOT / "docs" / name,OUTPUT / name)
# The hosted private replay offers the exact same downloadable source bundle.
downloads=ROOT / "dist/downloads"
downloads.mkdir(parents=True,exist_ok=True)
shutil.copy2(archive,downloads / archive.name)
for name in ("MarketBudget-Technical-Report.pdf","MarketBudget-Two-Page-Summary.pdf"):
    shutil.copy2(OUTPUT / name, downloads / name)
shutil.copy2(OUTPUT / "MarketBudget-project.manifest.json", downloads / "MarketBudget-project.manifest.json")
for name in ("MarketBudget-Research-Report.pdf","RESEARCH_REPORT.md"):
    source=ROOT/"docs"/name
    if source.exists():
        shutil.copy2(source,OUTPUT/name)
        shutil.copy2(source,downloads/name)
research=ROOT/"reports/research/latest.json"
if research.exists():shutil.copy2(research,downloads/"MarketBudget-research-results.json")
if (ROOT / "docs/REVIEW.md").exists():
    shutil.copy2(ROOT / "docs/REVIEW.md", downloads / "MarketBudget-Review.md")
print(json.dumps(manifest,indent=2))
