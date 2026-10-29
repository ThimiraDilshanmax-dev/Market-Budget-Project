"""Local FastAPI service. Start on loopback: python -m marketbudget.api."""
from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
import io
import json
import os
from pathlib import Path
import sqlite3
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .config import ROOT
from . import __version__
from .forecast import basket_forecast
from .records import MAX_BACKUP_RECORDS, validate_record
from .releases import load_release

app = FastAPI(title="MarketBudget", version=__version__, description="Dambulla wholesale basket research replay. All prices in LKR/kg.")


def snapshot() -> dict:
    try:return load_release()[0]
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise HTTPException(503,"The approved forecast release is unavailable or failed validation. Restore a verified release; research outputs are not a fallback.") from error

@app.get("/runtime.json")
def runtime():
    snapshot()
    _,manifest,_=load_release()
    return {"storage":"api","release_id":manifest["release_id"],"snapshot_sha256":manifest["files"]["snapshot.json"]}

@app.get("/api/v1/research/latest")
def research_latest():
    path=ROOT/"reports/research/latest.json"
    if not path.exists():raise HTTPException(404,"No completed research study")
    try:
        report=json.loads(path.read_text())
        if report.get('status')!='research_only':raise ValueError('Not a research-only artifact')
        return report
    except (OSError,ValueError,TypeError) as error:raise HTTPException(503,'Research results failed validation. Approved forecasts are unaffected.') from error


@contextmanager
def database():
    path = Path(os.environ.get("MARKETBUDGET_DB", str(ROOT / "data/marketbudget.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS baskets (id TEXT PRIMARY KEY, name TEXT NOT NULL, saved_at TEXT NOT NULL, contract TEXT NOT NULL)")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


class Quantities(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    beans: float = Field(ge=0, le=10000)
    carrot: float = Field(ge=0, le=10000)
    tomato: float = Field(ge=0, le=10000)


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    issue_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    quantities: Quantities
    budget: float | None = Field(default=None, gt=0, le=1e9)
    replay: bool = True


class SaveRequest(ForecastRequest):
    name: str = Field(min_length=1, max_length=100)


class BackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1.0"]
    exported_at: str | None = None
    baskets: list[dict] = Field(max_length=MAX_BACKUP_RECORDS)


def calculate(request: ForecastRequest) -> dict:
    try:
        return basket_forecast(snapshot(), request.issue_date, request.quantities.model_dump(), request.budget, replay=request.replay)
    except (ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/v1/health")
def health():
    state = snapshot()
    return {"status": "ok", "mode": "historical_replay", "persistence": "sqlite", "version": state["model"]["version"],
            "latest_price_date": state["coverage"]["end"], "actionable_forecasts": False}


@app.get("/api/v1/snapshot")
def get_snapshot():
    snapshot()
    _,_,folder=load_release()
    return Response((folder/"snapshot.json").read_bytes(),media_type="application/json")


@app.get("/api/v1/evaluation")
def evaluation():
    return snapshot()["evaluation"]


@app.post("/api/v1/forecast")
def forecast(request: ForecastRequest):
    return calculate(request)


@app.post("/api/v1/baskets", status_code=201)
def save_basket(request: SaveRequest):
    contract = calculate(request)
    if contract["status"] == "withheld":
        raise HTTPException(409, contract["reason"])
    name = request.name.strip()
    if not name:
        raise HTTPException(422, "Enter a basket name")
    record = {"id": str(uuid.uuid4()), "name": name, "saved_at": datetime.now(timezone.utc).isoformat(), "contract": contract}
    with database() as conn:
        conn.execute("INSERT INTO baskets VALUES (?, ?, ?, ?)", (record["id"], name, record["saved_at"], json.dumps(contract, allow_nan=False)))
    return record


@app.get("/api/v1/baskets")
def list_baskets():
    with database() as conn:
        rows = conn.execute("SELECT * FROM baskets ORDER BY saved_at DESC").fetchall()
    return [{"id": row["id"], "name": row["name"], "saved_at": row["saved_at"], "contract": json.loads(row["contract"])} for row in rows]


@app.post("/api/v1/baskets/import")
def import_baskets(request: BackupRequest):
    try:
        incoming = [validate_record(record) for record in request.baskets]
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    imported = skipped = 0
    # Validate the entire backup first; any conflicting ID rolls back all inserts.
    with database() as conn:
        for record in incoming:
            prior = conn.execute("SELECT * FROM baskets WHERE id = ?", (record["id"],)).fetchone()
            if prior:
                existing = {"id": prior["id"], "name": prior["name"], "saved_at": prior["saved_at"], "contract": json.loads(prior["contract"])}
                if existing != record:
                    raise HTTPException(409, "A basket ID conflicts with an existing record. No records were imported.")
                skipped += 1
            else:
                conn.execute("INSERT INTO baskets VALUES (?, ?, ?, ?)", (record["id"], record["name"], record["saved_at"], json.dumps(record["contract"], allow_nan=False)))
                imported += 1
        total = conn.execute("SELECT COUNT(*) FROM baskets").fetchone()[0]
    return {"imported": imported, "skipped": skipped, "total": total}


def get_record(basket_id: str) -> dict:
    with database() as conn:
        row = conn.execute("SELECT * FROM baskets WHERE id = ?", (basket_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Basket not found")
    return {"id": row["id"], "name": row["name"], "saved_at": row["saved_at"], "contract": json.loads(row["contract"])}


@app.get("/api/v1/baskets/{basket_id}")
def get_basket(basket_id: str):
    return get_record(basket_id)


@app.delete("/api/v1/baskets/{basket_id}", status_code=204)
def delete_basket(basket_id: str):
    get_record(basket_id)
    with database() as conn:
        conn.execute("DELETE FROM baskets WHERE id = ?", (basket_id,))
    return Response(status_code=204)


@app.get("/api/v1/baskets/{basket_id}/comparison")
def comparison(basket_id: str):
    contract = get_record(basket_id)["contract"]
    if contract["source_hash"] != snapshot()["source_hash"]:
        return {"status": "source_version_mismatch", "note": "This basket was saved against a different source snapshot. Its estimate is preserved; comparison is withheld."}
    row = next((row for row in snapshot()["forecasts"] if row["date"] == contract["issue_date"]), None)
    if row is None or any(row["actual"][commodity] is None for commodity in contract["quantities"]):
        return {"status": "outcome_unavailable", "note": "A complete seven-day label with at least four observations per vegetable is required."}
    actual = sum(row["actual"][c] * q for c, q in contract["quantities"].items())
    return {"status": "historical_outcome", "actual_benchmark": round(actual, 2),
            "prediction": contract["estimate"], "signed_error": round(contract["estimate"] - actual, 2),
            "in_interval": contract["interval"][0] <= actual <= contract["interval"][1],
            "note": "Historical replay comparison; not a prospectively issued forecast or paid invoice."}


def safe_csv(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


@app.get("/api/v1/baskets/{basket_id}/export.csv")
def export_csv(basket_id: str):
    record = get_record(basket_id)
    contract = record["contract"]
    stream = io.StringIO()
    writer = csv.writer(stream)
    def write(row):
        writer.writerow([safe_csv(v) if isinstance(v,str) else v for v in row])
    write(["basket", "contract_id", "mode", "issue_date", "target_start", "target_end", "commodity", "kg", "LKR_per_kg", "line_total_LKR", "model_version"])
    for line in contract["lines"]:
        write([safe_csv(record["name"]), contract["contract_id"], contract["status"], contract["issue_date"],
                         contract["target_start"], contract["target_end"], line["commodity"], line["kg"], line["price_per_kg"],
                         line["line_total"], contract["model_version"]])
    write(["basket_estimate_LKR", contract["estimate"]])
    write(["nominal_80pct_basket_lower_LKR", contract["interval"][0]])
    write(["nominal_80pct_basket_upper_LKR", contract["interval"][1]])
    write(["calculation_version", contract.get("calculation_version","legacy_policy_not_stored")])
    write(["exported_at", contract["exported_at"]])
    write(["source_hash", contract["source_hash"]])
    write(["scope", contract["disclaimer"]])
    return Response(stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="marketbudget-{basket_id}.csv"'})


web = ROOT / "dist"
if web.exists():
    app.mount("/", StaticFiles(directory=web, html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("marketbudget.api:app", host="127.0.0.1", port=8000)
