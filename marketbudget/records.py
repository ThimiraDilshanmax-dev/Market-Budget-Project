"""Validate portable saved records without recalculating their historical values."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import math
import re
import json

from .config import COMMODITIES
from .forecast import validate_quantities
from .money import amount,decimal,CALCULATION_VERSION

MAX_BACKUP_RECORDS = 500

def timestamp(value):
    if not isinstance(value,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)",value):
        raise ValueError("Timestamp must be an ISO date and time with timezone")
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError("Timestamp must include timezone")
    return parsed


def validate_record(record: dict) -> dict:
    def text(value, limit=128):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= limit
    def numeric(value, *, positive=False):
        return (not isinstance(value, bool) and isinstance(value, (int, float)) and
                math.isfinite(value) and (value > 0 if positive else value >= 0) and value <= 1e12)
    def calendar(value):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Saved calendar dates must use YYYY-MM-DD")
        return date.fromisoformat(value)
    try:
        if not isinstance(record, dict) or not text(record.get("id")) or not re.fullmatch(r"[A-Za-z0-9_-]+", record["id"]):
            raise ValueError("Invalid saved basket ID")
        json.dumps(record,allow_nan=False)
        if not text(record.get("name"), 100):
            raise ValueError("Basket names must contain 1–100 characters")
        timestamp(record["saved_at"])
        contract = record["contract"]
        if contract["schema_version"] not in ("1.0","1.1") or contract["status"] not in ("historical_replay", "forecast"):
            raise ValueError("Unsupported saved forecast schema or mode")
        modern=contract["schema_version"]=="1.1"
        if modern and contract["calculation_version"]!=CALCULATION_VERSION:raise ValueError("Unsupported calculation version")
        timestamp(contract["exported_at"])
        if contract["market"]!="Dambulla" or contract["currency"]!="LKR" or contract["price_type"]!="Wholesale benchmark" or contract["nominal_coverage"]!=.8:
            raise ValueError("Unsupported market, currency or forecast scope")
        for key in ("disclaimer","issue_timing","method","weather_status"):
            if not text(contract[key],2000):raise ValueError(f"Missing or invalid {key}")
        if isinstance(contract["calibration_n"],bool) or not isinstance(contract["calibration_n"],int) or contract["calibration_n"]<30:
            raise ValueError("Invalid calibration count")
        issue = calendar(contract["issue_date"])
        if (calendar(contract["target_start"]) != issue + timedelta(days=1) or
                calendar(contract["target_end"]) != issue + timedelta(days=7)):
            raise ValueError("Saved planning window must be issue+1 through issue+7")
        quantities = validate_quantities(contract["quantities"])
        budget = contract["budget"]
        if budget is not None and (not numeric(budget, positive=True) or budget > 1e9):
            raise ValueError("Invalid saved spending limit")
        estimate, bounds = contract["estimate"], contract["interval"]
        if not numeric(estimate) or not isinstance(bounds, list) or len(bounds) != 2 or not all(numeric(v) for v in bounds) or not bounds[0] <= estimate <= bounds[1]:
            raise ValueError("Invalid saved estimate or planning range")
        if not text(contract["model_version"]) or not text(contract["contract_id"]) or not re.fullmatch(r"[a-f0-9]{64}", contract["source_hash"]):
            raise ValueError("Missing saved model or source provenance")
        lines = contract["lines"]
        if not isinstance(lines, list) or len(lines) != 3 or {line["commodity"] for line in lines} != set(COMMODITIES):
            raise ValueError("Saved line items must cover all three vegetables")
        total = 0
        for line in lines:
            if not text(line["name"],100) or not numeric(line["latest_price"],positive=True) or isinstance(line["change_percent"],bool) or not numeric(abs(line["change_percent"])):
                raise ValueError("Missing line metadata")
            calendar(line["last_price_date"])
            if not 0 <= (issue-calendar(line["last_price_date"])).days <=3:
                raise ValueError("Invalid saved source date")
            pi=line["price_interval"]
            if not isinstance(pi,list) or len(pi)!=2 or not all(numeric(v) for v in pi) or not pi[0]<=line["price_per_kg"]<=pi[1]:raise ValueError("Invalid marginal range")
            if (line["kg"] != quantities[line["commodity"]] or not numeric(line["kg"]) or
                    not numeric(line["price_per_kg"]) or not numeric(line["line_total"])):
                raise ValueError("Invalid saved line item")
            if abs(line["price_per_kg"] * line["kg"] - line["line_total"]) > .025:
                raise ValueError("Saved line item does not match its quantity and price")
            if modern and amount(decimal(line["price_per_kg"])*decimal(line["kg"]))!=line["line_total"]:
                raise ValueError("Saved decimal line amount is inconsistent")
            total += line["line_total"]
        if abs(total - estimate) > .025:
            raise ValueError("Saved line totals do not match the basket estimate")
        if modern and sum(decimal(line["line_total"]) for line in lines)!=decimal(estimate):raise ValueError("Saved decimal basket total is inconsistent")
        for c in COMMODITIES:
            if isinstance(contract["price_ages"][c],bool) or not isinstance(contract["price_ages"][c],int) or not 0<=contract["price_ages"][c]<=3:raise ValueError("Invalid source age")
        for key in ("budget_difference","upper_budget_difference"):
            if budget is None:
                if contract[key] is not None:raise ValueError("Unexpected budget difference")
            elif not numeric(abs(contract[key])):raise ValueError("Invalid budget difference")
        return deepcopy(record)
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError("Incomplete or malformed saved basket record") from error
