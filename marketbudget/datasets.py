"""Dataset approval is explicit and switches one verified immutable pointer."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import argparse
import pandas as pd
import numpy as np
from .config import COMMODITIES,ROOT
from .ingest import atomic_write

FILES=("prices.csv","weather.csv","corrections.json","coverage.json","source_audit.json")

def validate_dataset(folder: Path):
    prices=pd.read_csv(folder/"prices.csv",parse_dates=["date"])
    if set(prices.commodity)!=set(COMMODITIES) or prices.duplicated(["date","commodity"]).any() or (prices.price.dropna()<=0).any() or np.isinf(prices.price).any():
        raise ValueError("Invalid canonical prices")
    for correction in json.loads((folder/"corrections.json").read_text()):
        rows=prices[(prices.date==pd.Timestamp(correction["date"]))&(prices.commodity==correction["commodity"])]
        if len(rows)!=1 or rows.iloc[0].price!=correction["price"]:
            raise ValueError("A verified correction was lost")
    return prices

def approve(folder: Path,root:Path=ROOT) -> dict:
    validate_dataset(folder)
    if (folder/"candidate.json").exists():
        decision=json.loads((folder/"candidate.json").read_text())
        if decision.get("review_decision")!="approved":
            raise ValueError("Record review_decision=approved in candidate.json after reviewing all failures and correction evidence")
    contents={name:(folder/name).read_bytes() for name in FILES}
    corrections=json.loads(contents['corrections.json'])
    for correction in corrections:
        if not correction.get('source_sha256'):
            evidence=root/'data/raw'/correction['source'];meta=json.loads(evidence.with_suffix(evidence.suffix+'.source.json').read_text())
            digest=sha256(evidence.read_bytes()).hexdigest()
            if digest!=meta['sha256'] or meta['url']!=correction['source_url']:raise ValueError('Correction evidence integrity failed')
            correction.update({'source_sha256':digest,'status':'primary_verified'})
    contents['corrections.json']=json.dumps(corrections,indent=2).encode()
    manifest={name:sha256(content).hexdigest() for name,content in contents.items()}
    identifier="data-"+sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:16]
    parent=root/"data/approved";parent.mkdir(parents=True,exist_ok=True);target=parent/identifier
    with tempfile.TemporaryDirectory(dir=parent,prefix=".approve-") as temporary:
        stage=Path(temporary)
        for name,content in contents.items():(stage/name).write_bytes(content)
        (stage/"manifest.json").write_text(json.dumps({"id":identifier,"files":manifest},indent=2))
        if not target.exists():stage.rename(target)
    pointer={"id":identifier,"manifest_sha256":sha256((target/"manifest.json").read_bytes()).hexdigest()}
    dataset_directory(root,pointer)
    atomic_write(root/"data/approved.json",json.dumps(pointer,indent=2).encode())
    return pointer

def dataset_directory(root:Path=ROOT,pointer:dict|None=None)->Path:
    path=root/"data/approved.json"
    if pointer is None and not path.exists():return root/"data/processed"
    pointer=pointer or json.loads(path.read_text())
    if Path(pointer["id"]).name!=pointer["id"]:raise ValueError("Invalid dataset identifier")
    folder=root/"data/approved"/pointer["id"];raw=(folder/"manifest.json").read_bytes()
    if sha256(raw).hexdigest()!=pointer["manifest_sha256"]:raise ValueError("Dataset manifest changed")
    manifest=json.loads(raw)
    if set(manifest["files"])!=set(FILES):raise ValueError("Dataset files missing")
    for name,digest in manifest["files"].items():
        if sha256((folder/name).read_bytes()).hexdigest()!=digest:raise ValueError(f"Approved dataset changed: {name}")
    validate_dataset(folder)
    return folder

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("directory",type=Path);args=parser.parse_args()
    print(json.dumps(approve(args.directory),indent=2))
