import csv
import io
from copy import deepcopy
import uuid

from fastapi.testclient import TestClient
import pytest

from marketbudget.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETBUDGET_DB", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        yield client


def request_body(**changes):
    return {"issue_date":"2025-06-16", "quantities":{"beans":20,"carrot":30,"tomato":20}, "budget":30000, **changes}


def test_end_to_end_save_compare_export_delete(client):
    response = client.post("/api/v1/baskets", json={**request_body(),"name":"Canteen weekly basket"})
    assert response.status_code == 201
    record = response.json()
    assert record["contract"]["status"] == "historical_replay"
    saved_id = record["id"]
    assert client.get("/api/v1/baskets").json()[0]["id"] == saved_id
    comparison = client.get(f"/api/v1/baskets/{saved_id}/comparison").json()
    assert comparison["status"] == "historical_outcome"
    assert comparison["actual_benchmark"] > 0
    exported = client.get(f"/api/v1/baskets/{saved_id}/export.csv")
    assert exported.status_code == 200
    rows = list(csv.reader(io.StringIO(exported.text)))
    assert rows[0][6] == "commodity"
    assert {rows[i][6] for i in (1,2,3)} == {"beans", "carrot", "tomato"}
    assert rows[-1][0] == "scope"
    assert client.delete(f"/api/v1/baskets/{saved_id}").status_code == 204
    assert client.get(f"/api/v1/baskets/{saved_id}").status_code == 404


@pytest.mark.parametrize("quantities", [
    {"beans":-1,"carrot":30,"tomato":20}, {"beans":0,"carrot":0,"tomato":0},
    {"beans":10001,"carrot":30,"tomato":20}, {"beans":True,"carrot":30,"tomato":20},
    {"beans":20,"carrot":30}, {"beans":20,"carrot":30,"tomato":20,"potato":10}])
def test_malformed_basket_rejected(client, quantities):
    assert client.post("/api/v1/forecast",json=request_body(quantities=quantities)).status_code == 422


def test_stale_mode_is_withheld_and_cannot_be_saved(client):
    assert client.post("/api/v1/forecast",json=request_body(replay=False)).json()["status"] == "withheld"
    assert client.post("/api/v1/baskets",json={**request_body(replay=False),"name":"Stale"}).status_code == 409


def test_outcome_unavailable_never_scored_as_correct(client):
    record = client.post("/api/v1/baskets",json={**request_body(issue_date="2026-03-10"),"name":"Unobserved week"}).json()
    result = client.get(f'/api/v1/baskets/{record["id"]}/comparison').json()
    assert result["status"] == "outcome_unavailable"
    assert "signed_error" not in result


def test_csv_formula_and_html_stored_as_plain_text(client):
    record = client.post("/api/v1/baskets",json={**request_body(),"name":"=HYPERLINK(\"bad\")"}).json()
    output = client.get(f'/api/v1/baskets/{record["id"]}/export.csv').text
    assert next(csv.reader(io.StringIO(output.splitlines()[1])))[0].startswith("'=")


def test_blank_name_and_unknown_date_rejected(client):
    assert client.post("/api/v1/baskets",json={**request_body(),"name":"   "}).status_code == 422
    assert client.post("/api/v1/forecast",json=request_body(issue_date="2030-12-01")).status_code == 422


def test_health_discloses_replay(client):
    result=client.get("/api/v1/health").json()
    assert result["status"] == "ok"
    assert result["actionable_forecasts"] is False
    assert client.get("/").status_code == 200


def test_backup_restore_preserves_original_contract_and_skips_duplicates(client):
    record=client.post("/api/v1/baskets",json={**request_body(),"name":"Portable plan"}).json()
    client.delete(f'/api/v1/baskets/{record["id"]}')
    backup={"schema_version":"1.0","baskets":[record]}
    restored=client.post("/api/v1/baskets/import",json=backup)
    assert restored.status_code == 200
    assert restored.json() == {"imported":1,"skipped":0,"total":1}
    assert client.get(f'/api/v1/baskets/{record["id"]}').json() == record
    assert client.post("/api/v1/baskets/import",json=backup).json()["skipped"] == 1


def test_backup_conflict_rolls_back_every_insert(client):
    prior=client.post("/api/v1/baskets",json={**request_body(),"name":"Original"}).json()
    fresh=deepcopy(prior);fresh["id"]=str(uuid.uuid4())
    conflicting=deepcopy(prior);conflicting["name"]="Altered"
    response=client.post("/api/v1/baskets/import",json={"schema_version":"1.0","baskets":[fresh,conflicting]})
    assert response.status_code == 409
    assert client.get("/api/v1/baskets").json() == [prior]


@pytest.mark.parametrize("field,value", [("estimate",-1),("issue_date","2025-02-30"),("target_end","2025-06-22"),("source_hash","missing"),("interval",[99999,100000])])
def test_invalid_backup_changes_nothing(client,field,value):
    record=client.post("/api/v1/baskets",json={**request_body(),"name":"Original"}).json()
    invalid=deepcopy(record);invalid["contract"][field]=value
    assert client.post("/api/v1/baskets/import",json={"schema_version":"1.0","baskets":[invalid]}).status_code == 422
    assert client.get("/api/v1/baskets").json() == [record]


def test_comparison_refuses_changed_source_snapshot(client,monkeypatch):
    from marketbudget.api import snapshot
    record=client.post("/api/v1/baskets",json={**request_body(),"name":"Old source"}).json()
    changed={**snapshot(),"source_hash":"0"*64}
    monkeypatch.setattr("marketbudget.api.snapshot",lambda:changed)
    result=client.get(f'/api/v1/baskets/{record["id"]}/comparison').json()
    assert result["status"] == "source_version_mismatch"
    assert "signed_error" not in result
