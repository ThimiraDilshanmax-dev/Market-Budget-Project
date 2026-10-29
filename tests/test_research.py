import json
import numpy as np
import pandas as pd
import pytest
from marketbudget.config import ROOT,COMMODITIES
from marketbudget.research import folds,candidate_ids,select_candidate,joint_intervals,prepare_frame,block_confidence
from marketbudget.features import split

def test_frozen_development_folds_and_boundaries():
    assert len(folds())==6
    assert folds()[0]['train_end']=='2022-09-30'
    assert folds()[-1]['validation_end']=='2024-06-30'
    for fold in folds():
        assert fold['train_end']<fold['calibration_start']<=fold['calibration_end']<fold['validation_start']
    assert len(candidate_ids())==20

def test_selection_checks_all_qualifying_candidates_first():
    def metric(mae,crop,folds):return {'basket_mae':mae,'commodities':{c:{'mae':crop} for c in COMMODITIES},'fold_mae':folds}
    results={name:metric(100,10,[100]*6) for name in ('latest_price','mean_28d','prior_year','ewma_7d')}
    results['bad-best']=metric(70,15,[70]*6)
    results['qualified-second']=metric(80,9,[80]*6)
    selected=select_candidate(results,6)
    assert selected['selected']=='qualified-second'
    assert not selected['guards']['bad-best']['qualified']
    assert select_candidate(results,3)['selected'] in ('latest_price','mean_28d','prior_year','ewma_7d')

def test_joint_additive_scenarios_preserve_offsetting_moves():
    cal=np.tile([[100.,100.,100.]],(40,1));actual=cal+np.tile([[10.,-10.,0.],[-10.,10.,0.]],(20,1))
    # Reference weights differ, so create offsets in quantity-weighted units.
    actual[:,1]=100-(actual[:,0]-100)*20/30
    bounds=joint_intervals(actual,cal,np.array([[100.,100.,100.]]),'additive')
    assert bounds[0,0]==pytest.approx(7000)
    assert bounds[0,1]==pytest.approx(7000)

def test_research_ewma_does_not_see_future_prices():
    dates=pd.date_range('2022-01-01',periods=90)
    data=pd.DataFrame([{'date':d,'commodity':c,'price':100+i} for i,d in enumerate(dates) for c in COMMODITIES])
    changed=data.copy();changed.loc[changed.date>'2022-02-15','price']=9999
    left,right=prepare_frame(data,None),prepare_frame(changed,None)
    np.testing.assert_allclose(left.loc[left.date<='2022-02-15','ewma7'],right.loc[right.date<='2022-02-15','ewma7'])

def test_research_results_are_isolated_and_historical_checks_labelled():
    report=json.loads((ROOT/'reports/research/latest.json').read_text())
    assert report['status']=='research_only'
    assert report['promotion']=='disabled_pending_new_uninspected_outcomes'
    assert all(v['evidence']=='previously_inspected_exploratory' for v in report['historical_checks'].values())
    assert len(report['folds'])==6 and report['confidence_95']['draws']==2000
    assert report['interval_guard_passed']==any(m['coverage']>=.75 for m in report['interval_methods'].values())

def test_insufficient_calibration_does_not_create_interval():
    with pytest.raises(ValueError):joint_intervals(np.ones((5,3)),np.ones((5,3)),np.ones((2,3)),'relative')

def test_perfect_baseline_is_retained_without_dividing_by_zero():
    metric={'basket_mae':0.,'commodities':{c:{'mae':0.} for c in COMMODITIES},'fold_mae':[0.]*6}
    results={name:metric for name in ('latest_price','mean_28d','prior_year','ewma_7d','learned')}
    assert select_candidate(results,6)['selected']!='learned'

def test_research_protocol_and_model_digests_match():
    from hashlib import sha256
    report=json.loads((ROOT/'reports/research/latest.json').read_text())
    assert sha256(json.dumps(report['protocol'],sort_keys=True).encode()).hexdigest()==report['protocol_sha256']
    folder=ROOT/'reports/research'/report['run_id']/'models'
    assert len(report['research_model_artifacts'])==24
    for name,meta in report['research_model_artifacts'].items():assert sha256((folder/name).read_bytes()).hexdigest()==meta['sha256']
