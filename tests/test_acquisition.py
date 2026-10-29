from hashlib import sha256
import json

import httpx
import pytest

from marketbudget import ingest


def test_download_cache_reuses_only_matching_verified_bytes(tmp_path,monkeypatch):
    source="https://example.test/report"
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return httpx.Response(200,content=b"original source",request=httpx.Request("GET",url))
    monkeypatch.setattr(ingest.httpx,"get",get)
    path=tmp_path/"report.pdf"
    ingest.fetch(source,path);ingest.fetch(source,path)
    assert calls == [source]
    manifest=json.loads(path.with_suffix(".pdf.source.json").read_text())
    assert manifest["sha256"] == sha256(b"original source").hexdigest()
    with pytest.raises(ValueError,match="URL"):
        ingest.fetch("https://example.test/different",path)
    path.write_bytes(b"altered")
    with pytest.raises(ValueError,match="hash"):
        ingest.fetch(source,path)


def test_unmanifested_bytes_are_never_blessed(tmp_path):
    path=tmp_path/"partial.pdf";path.write_bytes(b"partial")
    with pytest.raises(ValueError,match="manifest missing"):
        ingest.fetch("https://example.test/report",path)
    assert not path.with_suffix(".pdf.source.json").exists()


def test_interrupted_atomic_write_leaves_no_partial_target(tmp_path,monkeypatch):
    path=tmp_path/"source.pdf"
    def fail(*args):
        raise OSError("Simulated disk failure")
    monkeypatch.setattr(ingest.os,"replace",fail)
    with pytest.raises(OSError):
        ingest.atomic_write(path,b"complete response")
    assert list(tmp_path.iterdir()) == []


def test_permanent_http_error_is_not_retried(tmp_path,monkeypatch):
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return httpx.Response(404,request=httpx.Request("GET",url))
    monkeypatch.setattr(ingest.httpx,"get",get)
    with pytest.raises(httpx.HTTPStatusError):
        ingest.fetch("https://example.test/missing",tmp_path/"missing")
    assert len(calls) == 1


def test_actual_link_variants_and_invalid_dates():
    html='<a href="/price_report_20261016_e_0.pdf">Revised filename</a><a href="/price_report_20261399_e.pdf">Invalid date</a>'
    assert ingest.discover_reports(html) == [("2026-10-16","https://www.cbsl.gov.lk/price_report_20261016_e_0.pdf")]
