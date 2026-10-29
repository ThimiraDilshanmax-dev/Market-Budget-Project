from copy import deepcopy
from hashlib import sha256
import importlib
import json
from pathlib import Path
import shutil
import subprocess

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from marketbudget.config import ROOT,PACKAGE_URL
from marketbudget.forecast import basket_forecast
from marketbudget.records import validate_record
from marketbudget.releases import load_release,seal_release
from marketbudget import ingest

CASES=json.loads((ROOT/'tests/fixtures/records.json').read_text())

@pytest.mark.parametrize('case',CASES,ids=lambda case:case['name'])
def test_shared_record_contract(case):
    if case['valid']:assert validate_record(case['record'])==case['record']
    else:
        with pytest.raises(ValueError):validate_record(case['record'])

@pytest.fixture
def sealed_root(tmp_path):
    for folder in ('artifacts/releases','data/processed','data/raw','web'):
        shutil.copytree(ROOT/folder,tmp_path/folder)
    for name in ('approved.json','snapshot.json','model_card.json'):
        shutil.copy2(ROOT/'artifacts'/name,tmp_path/'artifacts'/name)
    (tmp_path/'reports').mkdir();shutil.copy2(ROOT/'reports/evaluation.json',tmp_path/'reports/evaluation.json')
    shutil.copy2(ROOT/'README.md',tmp_path/'README.md')
    return tmp_path

def test_source_audit_outage_preserves_approved_corrections(sealed_root,monkeypatch):
    before={name:(sealed_root/'data/processed'/name).read_bytes() for name in ('prices.csv','corrections.json')}
    def offline(url,path):
        if url==PACKAGE_URL:return sealed_root/'data/raw/vegetablesSriLanka_1.1.0.tar.gz'
        raise ValueError('Simulated primary outage')
    monkeypatch.setattr(ingest,'fetch',offline)
    frame=ingest.prepare_prices(sealed_root)
    assert frame[frame.date==pd.Timestamp('2024-07-11')].set_index('commodity').price.to_dict()=={'beans':375,'carrot':345,'tomato':190}
    for name,content in before.items():assert (sealed_root/'data/processed'/name).read_bytes()==content
    candidate=Path(frame.attrs['candidate_directory'])
    assert json.loads((candidate/'candidate.json').read_text())['status']=='needs_review'
    assert len(json.loads((candidate/'corrections.json').read_text()))==3

def test_corrupt_release_refused(sealed_root):
    _,_,folder=load_release(sealed_root)
    (folder/'snapshot.json').write_text('{}')
    with pytest.raises(ValueError,match='integrity'):load_release(sealed_root)

def test_interrupted_release_approval_keeps_old_pointer(sealed_root,monkeypatch):
    module=importlib.import_module('marketbudget.releases')
    prior=(sealed_root/'artifacts/approved.json').read_bytes()
    def fail(*args):raise OSError('Simulated interruption')
    monkeypatch.setattr(module,'atomic_write',fail)
    with pytest.raises(OSError):seal_release(sealed_root)
    assert (sealed_root/'artifacts/approved.json').read_bytes()==prior
    load_release(sealed_root)

def test_training_failure_cannot_change_approved_release(sealed_root,monkeypatch):
    module=importlib.import_module('marketbudget.train')
    before=(sealed_root/'artifacts/approved.json').read_bytes()
    def fail(*args,**kwargs):raise RuntimeError('Simulated training failure')
    monkeypatch.setattr(module,'fit_models',fail)
    with pytest.raises(RuntimeError):module.run(sealed_root)
    assert (sealed_root/'artifacts/approved.json').read_bytes()==before
    load_release(sealed_root)

def test_build_failure_keeps_existing_site(sealed_root,monkeypatch):
    from scripts.build import build
    destination=sealed_root/'dist';destination.mkdir();(destination/'index.html').write_text('previous site')
    (sealed_root/'web/storage.mjs').unlink()
    with pytest.raises(ValueError,match='Missing application asset'):build(sealed_root)
    assert (destination/'index.html').read_text()=='previous site'

def test_api_runtime_and_exact_snapshot_bytes():
    from marketbudget.api import app
    with TestClient(app) as client:
        runtime=client.get('/runtime.json').json();response=client.get('/api/v1/snapshot')
        assert runtime['storage']=='api'
        assert sha256(response.content).hexdigest()==runtime['snapshot_sha256']

def test_api_unavailable_release_returns_503(monkeypatch):
    from marketbudget.api import app
    def fail(*args):raise ValueError('corruption')
    monkeypatch.setattr('marketbudget.api.load_release',fail)
    with TestClient(app) as client:
        assert client.get('/api/v1/health').status_code==503
        assert client.get('/runtime.json').status_code==503

@pytest.mark.parametrize('field',['exported_at','disclaimer','currency','market'])
def test_api_rejects_incomplete_export_records(tmp_path,monkeypatch,field):
    from marketbudget.api import app
    monkeypatch.setenv('MARKETBUDGET_DB',str(tmp_path/'test.sqlite3'))
    record=deepcopy(CASES[0]['record']);record['contract'].pop(field)
    with TestClient(app) as client:
        assert client.post('/api/v1/baskets/import',json={'schema_version':'1.0','baskets':[record]}).status_code==422
        assert client.get('/api/v1/baskets').json()==[]

def test_csv_protects_all_imported_metadata(tmp_path,monkeypatch):
    import csv,io
    from marketbudget.api import app
    monkeypatch.setenv('MARKETBUDGET_DB',str(tmp_path/'test.sqlite3'))
    record=deepcopy(CASES[0]['record']);record['contract']['model_version']='=1+1';record['contract']['contract_id']='@test';record['contract']['disclaimer']='+formula'
    with TestClient(app) as client:
        assert client.post('/api/v1/baskets/import',json={'schema_version':'1.0','baskets':[record]}).status_code==200
        rows=list(csv.reader(io.StringIO(client.get('/api/v1/baskets/'+record['id']+'/export.csv').text)))
        assert rows[1][1].startswith("'@") and rows[1][-1].startswith("'=") and rows[-1][1].startswith("'+")

def test_decimal_money_exact_cross_language():
    snapshot=load_release()[0]
    inputs=[{'beans':x,'carrot':0,'tomato':0} for x in (.0015,.0025,.0045,.0055,20.000001)]+[{'beans':.003,'carrot':.003,'tomato':.003}]
    script="""import fs from 'node:fs';import {calculateBasket,identifyContract} from './web/math.mjs';const x=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(await Promise.all(x.inputs.map(q=>identifyContract(calculateBasket(x.snapshot,'2026-03-10',q,20000))))));"""
    if not shutil.which('node'):pytest.skip('Node unavailable')
    result=subprocess.run(['node','--input-type=module','-e',script],cwd=ROOT,input=json.dumps({'snapshot':snapshot,'inputs':inputs}),text=True,capture_output=True,check=True)
    for q,browser in zip(inputs,json.loads(result.stdout)):
        python=basket_forecast(snapshot,'2026-03-10',q,20000)
        for field in ('estimate','interval','budget_difference','upper_budget_difference','contract_id'):
            assert python[field]==browser[field],field
        assert round(sum(line['line_total'] for line in python['lines']),2)==python['estimate']
    assert basket_forecast(snapshot,'2026-03-10',inputs[0])['estimate']==.44

def test_nonfinite_extension_metadata_is_rejected():
    record=deepcopy(CASES[0]['record']);record['extra']=float('nan')
    with pytest.raises(ValueError):validate_record(record)
