"""Validated immutable forecast releases; research runs never change this pointer."""
from __future__ import annotations

from datetime import date, datetime, timezone,timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import tempfile

from .config import COMMODITIES, ROOT
from .ingest import atomic_write


def _number(value, positive=False):
    return (not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def validate_snapshot(state: dict) -> dict:
    """Validate every structure consumed by the calculator and dashboard."""
    try:
        json.dumps(state,allow_nan=False)
        if state["schema_version"] != "1.0" or state["mode"] != "historical_replay":
            raise ValueError("Unsupported snapshot schema or mode")
        if len(state["source_hash"]) != 64 or any(c not in "0123456789abcdef" for c in state["source_hash"]):
            raise ValueError("Invalid source fingerprint")
        if state["evaluation"]["model"] != state["model"] or state["evaluation"]["coverage"] != state["coverage"]:
            raise ValueError("Snapshot model, coverage and evaluation do not agree")
        residuals = state["residual_scenarios"]
        if len(residuals) < 30 or len(residuals) != len(state["calibration_dates"]):
            raise ValueError("Insufficient aligned calibration scenarios")
        if any(not isinstance(row, list) or len(row) != 3 or any(not isinstance(v, (int,float)) or isinstance(v,bool) or not math.isfinite(v) or v < -1 for v in row) for row in residuals):
            raise ValueError("Invalid residual scenarios")
        calibration = [date.fromisoformat(d) for d in state["calibration_dates"]]
        if calibration != sorted(set(calibration)):
            raise ValueError("Calibration dates must be ordered and unique")
        if any(d+timedelta(days=7)>date.fromisoformat(state['model']['calibration_end']) for d in calibration):
            raise ValueError('Calibration targets cross their boundary')
        issue_dates = []
        for row in state["forecasts"]:
            issue = date.fromisoformat(row["date"]);issue_dates.append(issue)
            if max(calibration) >= issue:
                raise ValueError("Calibration must precede forecast issue dates")
            for c in COMMODITIES:
                if not _number(row["point"][c]) or not _number(row["latest"][c], True):
                    raise ValueError("Invalid forecast/source prices")
                age = (issue - date.fromisoformat(row["last_price_dates"][c])).days
                if not 0 <= age <= 3:
                    raise ValueError("Invalid price freshness in forecast contract")
                actual = row["actual"][c]
                if actual is not None and (not _number(actual, True) or row["label_counts"][c] < 4):
                    raise ValueError("Invalid weekly outcome")
        if not issue_dates or issue_dates != sorted(set(issue_dates)):
            raise ValueError("Forecast issue dates must be nonempty, ordered and unique")
        history_dates = []
        for row in state["history"]:
            history_dates.append(date.fromisoformat(row["date"]))
            if any(row[c] is not None and not _number(row[c], True) for c in COMMODITIES):
                raise ValueError("Invalid observed price history")
        if not history_dates or history_dates != sorted(set(history_dates)):
            raise ValueError("History dates must be ordered and unique")
        if max(history_dates).isoformat() != state["coverage"]["end"]:
            raise ValueError("Coverage end does not match price history")
        evaluated=state['test_predictions'];tested=[]
        for row in evaluated:
            tested.append(date.fromisoformat(row['date']))
            if row['period']!='test_2025' or not _number(row['actual'],True) or not all(_number(row[k]) for k in ('prediction','lower','upper')) or not row['lower']<=row['prediction']<=row['upper']:
                raise ValueError('Invalid evaluated basket outcomes')
        if not tested or tested!=sorted(set(tested)) or any(d.year!=2025 for d in tested):raise ValueError('Invalid test outcome dates')
        evaluation=state['evaluation'];selected=state['model']['selected']
        if selected not in evaluation['metrics']['test_2025'] or evaluation['intervals']['test_2025']['n']!=len(evaluated):raise ValueError('Evaluation counts or method mismatch')
        for period in ('tuning','test_2025','later_2026'):
            for result in evaluation['metrics'][period].values():
                if not _number(result['basket_mae']) or not math.isfinite(result['basket_bias']) or result['complete_baskets']<=0:raise ValueError('Invalid evaluation metrics')
                for c in COMMODITIES:
                    if not _number(result['commodities'][c]['mae']):raise ValueError('Invalid commodity metrics')
        for correction in state['corrections']:
            date.fromisoformat(correction['date'])
            if correction['commodity'] not in COMMODITIES or not _number(correction['price'],True) or not _number(correction['original_price'],True) or not correction['source_url'].startswith('https://www.cbsl.gov.lk/'):
                raise ValueError('Invalid correction provenance')
        if not isinstance(state['source_audit'],list):raise ValueError('Missing source audit')
        return state
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("Incomplete forecast snapshot") from error


def seal_release(root: Path = ROOT) -> dict:
    """Explicitly seal existing reviewed outputs. Never invoked by training."""
    state = validate_snapshot(json.loads((root / "artifacts/snapshot.json").read_text()))
    report = json.loads((root / "reports/evaluation.json").read_text())
    if report != state["evaluation"]:
        raise ValueError("Evaluation file differs from the frozen snapshot")
    card = json.loads((root / "artifacts/model_card.json").read_text())
    if card != state["model"]:
        raise ValueError("Model card differs from snapshot")
    artifacts = root / "artifacts";folder = artifacts / "releases";folder.mkdir(parents=True,exist_ok=True)
    release_id = "release-" + sha256((artifacts / "snapshot.json").read_bytes()).hexdigest()[:16]
    target = folder / release_id
    with tempfile.TemporaryDirectory(dir=folder, prefix=".sealing-") as temporary:
        stage = Path(temporary)
        for source, name in [(artifacts/"snapshot.json","snapshot.json"),(root/"reports/evaluation.json","evaluation.json"),(artifacts/"model_card.json","model_card.json"),(root/"data/processed/corrections.json","corrections.json")]:
            shutil.copy2(source,stage/name)
        manifest = {"release_id":release_id,"sealed_at":datetime.now(timezone.utc).isoformat(),
                    "model_version":state["model"]["version"],"files":{p.name:sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}}
        (stage/"manifest.json").write_text(json.dumps(manifest,indent=2))
        if not target.exists():
            stage.rename(target)
    pointer = {"release_id":release_id,"directory":f"releases/{release_id}",
               "manifest_sha256":sha256((target/"manifest.json").read_bytes()).hexdigest()}
    # Validate before the only approval mutation: replacing a small pointer.
    load_release(root,pointer)
    atomic_write(artifacts/"approved.json",json.dumps(pointer,indent=2).encode())
    return pointer


def load_release(root: Path = ROOT, pointer: dict | None = None) -> tuple[dict,dict,Path]:
    artifacts = root/"artifacts"
    pointer = pointer or json.loads((artifacts/"approved.json").read_text())
    folder = (artifacts/pointer["directory"]).resolve()
    if not folder.is_relative_to((artifacts/"releases").resolve()):
        raise ValueError("Release path must stay within the immutable release store")
    raw = (folder/"manifest.json").read_bytes()
    if sha256(raw).hexdigest() != pointer["manifest_sha256"]:
        raise ValueError("Release manifest integrity check failed")
    manifest = json.loads(raw)
    if manifest["release_id"] != pointer["release_id"]:
        raise ValueError("Release pointer identity mismatch")
    for name, expected in manifest["files"].items():
        if Path(name).name != name or sha256((folder/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Release file integrity check failed: {name}")
    state = validate_snapshot(json.loads((folder/"snapshot.json").read_text()))
    if json.loads((folder/"evaluation.json").read_text()) != state["evaluation"] or json.loads((folder/"model_card.json").read_text()) != state["model"]:
        raise ValueError("Release metadata is inconsistent")
    return state,manifest,folder


if __name__ == "__main__":
    print(json.dumps(seal_release(),indent=2))
