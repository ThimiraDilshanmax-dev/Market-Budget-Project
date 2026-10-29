"""Explicit acquisition, immutable responses, strict validation and a review queue.

No network request runs at import time. Unknown CBSL layouts fail closed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
import time
from urllib.parse import urljoin, urlparse

import fitz
import httpx
import numpy as np
import pandas as pd
import pyreadr

from .config import CBSL_INDEX, COMMODITIES, GRIDS, PACKAGE_URL, ROOT


def fetch(url: str, path: Path) -> Path:
    """Cache exact source bytes; preserve a SHA-256 manifest for each response."""
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = path.with_suffix(path.suffix + ".source.json")
    if path.exists():
        # Never assign new provenance to an orphaned or altered cached response.
        if not meta.exists():
            raise ValueError(f"Source manifest missing: {path.name}; review or reacquire the orphaned file")
        manifest = json.loads(meta.read_text())
        if manifest.get("url") != url:
            raise ValueError(f"Source URL differs from its manifest: {path.name}")
        if manifest.get("sha256") != sha256(path.read_bytes()).hexdigest() or manifest.get("bytes") != path.stat().st_size:
            raise ValueError(f"Source hash or byte count changed: {path.name}")
        return path
    if meta.exists():
        raise ValueError(f"Source bytes missing for existing manifest: {path.name}; review before reacquiring")
    if not path.exists():
        for attempt in range(3):
            try:
                response = httpx.get(url, follow_redirects=True, timeout=60)
                response.raise_for_status()
                if not response.content:
                    raise ValueError("Empty response")
                manifest = {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            "sha256": sha256(response.content).hexdigest(), "bytes": len(response.content),
                            "note": "Retrieval metadata records this acquisition; not historical publication time."}
                atomic_write(path, response.content)
                atomic_write(meta, json.dumps(manifest, indent=2).encode())
                break
            except (httpx.HTTPError, ValueError) as error:
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code not in (408,429,500,502,503,504):
                    raise
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
    return path


def atomic_write(path: Path, content: bytes) -> None:
    """Replace only after the complete response reaches the filesystem."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".acquire-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def parse_cbsl(path: Path, expected_date: str) -> list[dict]:
    """Read only the validated wholesale Dambulla Today table.

    Require the table title, matching printed date, correct market/header order,
    kg units, ten aligned price cells and positive point quotes. Retail narrative
    and Yesterday cells are never used. A new layout requires parser review.
    """
    day = pd.Timestamp(expected_date)
    document = fitz.open(path)
    for page in document:
        text = page.get_text(sort=True)
        if "Wholesale and Retail Prices:" not in text:
            continue
        normalized = re.sub(r"\s+", " ", text)
        date_match = re.search(r"Selected Food Commodities\s*-\s*(\d{1,2}\s+[A-Za-z]+,?\s+\d{4})", normalized)
        if not date_match or pd.Timestamp(date_match.group(1)) != day:
            raise ValueError("Printed report date does not match expected issue date")
        words = page.get_text("words")
        today = sorted([w for w in words if w[4] == "Today" and w[1] < 105], key=lambda w: w[0])
        markets = sorted([w for w in words if w[4] in {"Pettah", "Dambulla", "Narahenpita"} and w[1] < 90], key=lambda w: w[0])
        wholesale = [w for w in words if w[4] == "Wholesale" and w[0] > 140 and w[1] < 90]
        retail = [w for w in words if w[4] == "Retail" and w[0] > 300 and w[1] < 90]
        if len(today) != 5 or [w[4] for w in markets] != ["Pettah", "Dambulla", "Pettah", "Dambulla", "Narahenpita"]:
            raise ValueError("Unrecognized price table columns")
        if len(wholesale) != 1 or len(retail) != 1 or wholesale[0][0] >= markets[1][0] or retail[0][0] <= markets[1][0]:
            raise ValueError("Wholesale/retail header alignment changed")
        records = []
        for item in ("Beans", "Carrot", "Tomato"):
            labels = [w for w in words if w[4] == item and w[0] < 100]
            if len(labels) != 1:
                raise ValueError(f"Missing or duplicate {item} row")
            y = labels[0][1]
            row = sorted([w for w in words if abs(w[1] - y) < 2], key=lambda w: w[0])
            if not any(w[4] == "Rs./kg" for w in row):
                raise ValueError("Unexpected units")
            cells = [w for w in row if re.fullmatch(r"[\d,]+\.\d{2}|n\.a\.", w[4])]
            if len(cells) != 10:
                raise ValueError("Unrecognized row cell count")
            target = cells[3]
            if abs(target[0] - today[1][0]) > 20:
                raise ValueError("Dambulla Today alignment changed")
            value = None if target[4] == "n.a." else float(target[4].replace(",", ""))
            if value is not None and (not np.isfinite(value) or value <= 0):
                raise ValueError("Nonpositive or nonfinite quote")
            records.append({"date": day.date().isoformat(), "commodity": item.lower(), "price": value,
                            "market": "Dambulla", "type": "Wholesale", "unit": "LKR/kg", "source": path.name})
        return records
    raise ValueError("Recognized wholesale table not found; manual review required")


def discover_reports(html: str, base: str = CBSL_INDEX) -> list[tuple[str, str]]:
    reports = []
    for href in re.findall(r'href=[\"\']([^\"\']+)[\"\']', html):
        url = urljoin(base, href.replace("&amp;", "&"))
        # Actual linked files only; do not assume that a guessed URL exists.
        match = re.search(r"price_report_(\d{8})_e(?:_\d+)?\.pdf(?:\?.*)?$", url)
        if match and urlparse(url).hostname == "www.cbsl.gov.lk":
            try:
                date = pd.to_datetime(match.group(1), format="%Y%m%d").date().isoformat()
            except ValueError:
                continue
            reports.append((date, url))
    return sorted(set(reports))


def review(error: Exception, source: str, root: Path = ROOT) -> None:
    path = root / "data/processed/review_queue.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps({"source": source, "error": str(error), "at": datetime.now(timezone.utc).isoformat()}) + "\n")


def prepare_prices(root: Path = ROOT) -> pd.DataFrame:
    raw = root / "data/raw"
    archive = fetch(PACKAGE_URL, raw / "vegetablesSriLanka_1.1.0.tar.gz")
    with tarfile.open(fileobj=io.BytesIO(archive.read_bytes())) as tar:
        for member in ("data/vegetables.srilanka.rda", "DESCRIPTION"):
            content = tar.extractfile("vegetablesSriLanka/" + member).read()
            (raw / Path(member).name).write_bytes(content)
    all_prices = next(iter(pyreadr.read_r(str(raw / "vegetables.srilanka.rda")).values()))
    data = all_prices[(all_prices.Market == "Dambulla") & (all_prices.Type == "Wholesale") & all_prices.Item.isin(["Beans", "Carrot", "Tomato"])].copy()
    data = data.rename(columns={"Date": "date", "Item": "commodity", "Price": "price"})[["date", "commodity", "price"]]
    data["date"] = pd.to_datetime(data.date)
    data["commodity"] = data.commodity.str.lower()
    if data.duplicated(["date", "commodity"]).any():
        raise ValueError("Duplicate source date/commodity keys")
    if ((data.price <= 0) | np.isinf(data.price)).any():
        raise ValueError("Invalid source price")
    data["original_price"] = data.price
    data["source"] = "vegetablesSriLanka 1.1.0"
    audit, corrections, recent, failures = [], [], [], []
    from .datasets import dataset_directory
    prior_directory=dataset_directory(root)
    approved_corrections = json.loads((prior_directory/"corrections.json").read_text()) if (prior_directory/"corrections.json").exists() else []
    # Sample every retained year, verify the known 2024 conflict and the proposal's
    # two illustrative dates. This is a sample audit, never a full audit claim.
    for compact in ("20220616", "20230615", "20240711", "20250616", "20260310", "20261016"):
        date = pd.to_datetime(compact, format="%Y%m%d")
        url = f"https://www.cbsl.gov.lk/sites/default/files/cbslweb_documents/statistics/pricerpt/price_report_{compact}_e.pdf"
        try:
            pdf = fetch(url, raw / f"cbsl_{compact}.pdf")
            parsed = parse_cbsl(pdf, date.date().isoformat())
            for record in parsed:
                mask = (data.date == date) & (data.commodity == record["commodity"])
                original = float(data.loc[mask, "price"].iloc[0]) if mask.any() else None
                audit.append({**record, "package_price": original, "source_url": url, "matches": original == record["price"] if mask.any() else None})
                if mask.any() and original != record["price"]:
                    corrections.append({**record, "original_price": original, "source_url": url,
                                        "status":"primary_verified", "source_sha256":sha256(pdf.read_bytes()).hexdigest()})
                    data.loc[mask, "price"] = record["price"]
                    data.loc[mask, "source"] = url
                if not mask.any():
                    recent.append({**record, "source_url": url})
        except Exception as error:
            review(error, url, root)
            failures.append({"source":url,"error":str(error)})
    # Retain reviewed replacements even if a subsequent collection attempt fails.
    # Candidates remain separate; a failure cannot modify approved canonical data.
    for prior in approved_corrections:
        if any(c["date"]==prior["date"] and c["commodity"]==prior["commodity"] for c in corrections):
            continue
        mask=(data.date==pd.Timestamp(prior["date"])) & (data.commodity==prior["commodity"])
        if mask.any():
            data.loc[mask,"price"]=prior["price"];data.loc[mask,"source"]=prior["source_url"]
            evidence=raw/prior["source"]
            digest=prior.get("source_sha256")
            evidence_meta=evidence.with_suffix(evidence.suffix+'.source.json')
            if not digest and evidence.exists() and evidence_meta.exists():
                meta=json.loads(evidence_meta.read_text());actual_digest=sha256(evidence.read_bytes()).hexdigest()
                if meta.get('sha256')==actual_digest and meta.get('url')==prior['source_url']:digest=actual_digest
            corrections.append({**prior,"status":"retained_approved", "source_sha256":digest})
    # No research pack identifying six unresolved 2021 conflicts was attached.
    # Exclude the entire year instead of assuming which records are disputed.
    selected = data[data.date >= "2022-01-01"].sort_values(["date", "commodity"])
    candidate_id="prices-"+sha256(selected.to_csv(index=False).encode()).hexdigest()[:12]+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    output = root / "data/candidates" / candidate_id
    output.mkdir(parents=True, exist_ok=True)
    selected.to_csv(output / "prices.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(recent).to_csv(output / "recent_reference_only.csv", index=False)
    (output / "corrections.json").write_text(json.dumps(corrections, indent=2))
    (output / "source_audit.json").write_text(json.dumps(audit, indent=2))
    coverage = {"package_rows": len(all_prices), "selected_all_year_rows": len(data),
                "selected_missing": int(data.price.isna().sum()), "retained_rows": len(selected),
                "retained_valid": int(selected.price.notna().sum()), "start": str(selected.date.min().date()),
                "end": str(selected.date.max().date()), "corrections": len(corrections),
                "primary_quotes_checked": len(audit),
                "sample_audit_years": sorted({int(r["date"][:4]) for r in audit}),
                "audit_limit": "2022 sample report URL returned 404. No primary 2022 quote verified. Parser failures and failed retrieval attempts remain in the review log; successful reparses are listed in source_audit.json.",
                "excluded": "All data before 2022; disputed 2021 keys unavailable",
                "recent_extension": "Single October reference date kept separate; not appended to model history",
                "licence": "Package declares GPL-3; upstream CBSL reuse terms require confirmation before external operational use."}
    (output / "coverage.json").write_text(json.dumps(coverage, indent=2))
    (output/"candidate.json").write_text(json.dumps({"id":candidate_id,"status":"needs_review","failures":failures,
        "correction_status":"retained_or_primary_verified","note":"No approved records were changed. Review evidence and explicitly approve a complete dataset before training."},indent=2))
    selected.attrs["candidate_directory"]=str(output)
    return selected


def prepare_weather(root: Path = ROOT, output: Path | None = None) -> pd.DataFrame:
    def one(entry):
        name, (lat, lon) = entry
        url = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M,T2M_MIN,T2M_MAX,RH2M"
               f"&community=AG&longitude={lon}&latitude={lat}&start=20211101&end=20260310&format=JSON&time-standard=LST")
        path = fetch(url, root / f"data/raw/weather_{name}.json")
        payload = json.loads(path.read_text())
        parameters = payload["properties"]["parameter"]
        frame = pd.DataFrame(parameters)
        frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
        frame.index.name = "date"
        frame = frame.replace(payload.get("header", {}).get("fill_value", -999), np.nan)
        frame = frame.rename(columns=lambda column: f"{name}_{column.lower()}")
        return frame
    with ThreadPoolExecutor(max_workers=3) as pool:
        frames = list(pool.map(one, GRIDS.items()))
    weather = pd.concat(frames, axis=1).sort_index()
    output = output or root/"data/candidates"/("weather-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    output.mkdir(parents=True,exist_ok=True)
    weather.to_csv(output / "weather.csv", date_format="%Y-%m-%d")
    return weather


def refresh(root: Path = ROOT) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    index = fetch(CBSL_INDEX, root / f"data/raw/cbsl_index_{stamp}.html")
    reports = discover_reports(index.read_text())
    accepted = []
    for date, url in reports[-10:]:
        try:
            path = fetch(url, root / f"data/raw/cbsl_{date.replace('-', '')}.pdf")
            accepted.extend(parse_cbsl(path, date))
        except Exception as error:
            review(error, url, root)
    pd.DataFrame(accepted).to_csv(root / f"data/processed/staged_prices_{stamp}.csv", index=False)
    return {"discovered": len(reports), "staged_quotes": len(accepted),
            "status": "staged_for_review", "note": "Collection never appends to approved training data automatically."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "refresh"])
    args = parser.parse_args()
    if args.command == "refresh":
        print(json.dumps(refresh(), indent=2))
    else:
        prices = prepare_prices()
        try:
            weather = prepare_weather(output=Path(prices.attrs["candidate_directory"]))
            print(f"Staged {len(prices)} prices and {len(weather)} weather days at {prices.attrs['candidate_directory']}. Approved data unchanged.")
        except Exception as error:
            review(error, "NASA POWER")
            print(f"Prepared {len(prices)} prices. Weather unavailable: {error}. Price-only model remains available.")


if __name__ == "__main__":
    main()
