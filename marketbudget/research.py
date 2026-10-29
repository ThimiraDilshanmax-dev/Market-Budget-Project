"""Frozen, CPU-only study. Research output never promotes a buyer-facing model.

Run python -m marketbudget.research. The protocol is saved before any model fit.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
from importlib.metadata import version
import numpy as np
import pandas as pd

from .config import ROOT,COMMODITIES,REFERENCE_BASKET
from .datasets import dataset_directory
from .features import make_features,split,PRICE_FEATURES
from .train import fit_models,predict,PARAMETERS
from .forecast import interval
from .ingest import atomic_write

WEIGHTS=np.array([REFERENCE_BASKET[c] for c in COMMODITIES])
BASELINES=("latest_price","mean_28d","prior_year","ewma_7d")
FAMILIES=("price_pooled","weather_pooled","price_individual","weather_individual")
BLENDS=(.25,.5,.75,1.)

def folds():
    result=[]
    for start in pd.date_range("2023-01-01","2024-04-01",freq="QS"):
        calibration_start=start-pd.DateOffset(months=3)
        result.append({"id":f"{start.year}Q{start.quarter}","train_start":"2022-01-01",
                       "train_end":(calibration_start-pd.Timedelta(days=1)).date().isoformat(),
                       "calibration_start":calibration_start.date().isoformat(),
                       "calibration_end":(start-pd.Timedelta(days=1)).date().isoformat(),
                       "validation_start":start.date().isoformat(),
                       "validation_end":(start+pd.DateOffset(months=3)-pd.Timedelta(days=1)).date().isoformat()})
    return result

def prepare_frame(prices,weather):
    frame=make_features(prices,weather)
    for c in COMMODITIES:
        valid=prices[(prices.commodity==c)&prices.price.notna()].set_index("date").sort_index().price
        ewma=valid.ewm(halflife="7D",times=valid.index,adjust=True).mean()
        rows=frame.commodity==c
        frame.loc[rows,"ewma7"]=ewma.reindex(pd.DatetimeIndex(frame.loc[rows,"date"]),method="ffill").to_numpy()
    return frame

def complete(frame):
    dates=frame.groupby("date").commodity.nunique()
    return frame[frame.date.isin(dates[dates==3].index)].copy()

def matrix(frame,column):
    return frame.pivot(index="date",columns="commodity",values=column).reindex(columns=COMMODITIES).to_numpy()

def candidate_ids(weather_enabled=True):
    families=[f for f in FAMILIES if weather_enabled or not f.startswith('weather')]
    return list(BASELINES)+[f"{f}@{weight:g}" for f in families for weight in BLENDS]

def candidate_points(name,frame,models):
    if name in BASELINES:
        column={"latest_price":"latest","mean_28d":"mean28","prior_year":"seasonal","ewma_7d":"ewma7"}[name]
        return matrix(frame,column)
    family,weight=name.split('@');weight=float(weight)
    point=predict(family,frame,models)[:,1]
    temporary=frame.assign(prediction=point*weight+frame.latest.to_numpy()*(1-weight))
    return matrix(temporary,"prediction")

def model_bundles(training,wx,weather_enabled):
    models={}
    for family in FAMILIES:
        if family.startswith('weather') and not weather_enabled:continue
        models[family]=fit_models(training,PRICE_FEATURES+(wx if family.startswith('weather') else []),family.endswith('pooled'))
    return models

def metrics(actual,point,lower=None,upper=None):
    error=(point-actual)@WEIGHTS
    result={"basket_mae":float(np.abs(error).mean()),"basket_bias":float(error.mean()),"n":len(error),
            "commodities":{c:{"mae":float(np.abs(point[:,i]-actual[:,i]).mean()),"bias":float((point[:,i]-actual[:,i]).mean())} for i,c in enumerate(COMMODITIES)}}
    if lower is not None:
        outcome=actual@WEIGHTS;width=upper-lower
        result.update({"coverage":float(np.mean((outcome>=lower)&(outcome<=upper))),"mean_width":float(width.mean()),
                       "interval_score":float(np.mean(width+10*np.maximum(lower-outcome,0)+10*np.maximum(outcome-upper,0)))})
    return result

def joint_intervals(cal_actual,cal_point,point,method):
    if len(cal_actual)<30:raise ValueError("Insufficient complete calibration baskets")
    if method=='relative' and (cal_point<=0).any():raise ValueError("Relative scenarios require positive calibration predictions")
    residual=cal_actual/cal_point-1 if method=='relative' else cal_actual-cal_point
    bounds=[]
    for p in point:
        scenarios=np.maximum(0,p[None,:]*(1+residual)) if method=='relative' else np.maximum(0,p[None,:]+residual)
        bounds.append(interval(scenarios@WEIGHTS,float(p@WEIGHTS)))
    return np.array(bounds)

def select_candidate(results,fold_count):
    baseline=min(BASELINES,key=lambda c:(results[c]['basket_mae'],c))
    qualified=[];guards={}
    for candidate,value in results.items():
        if candidate in BASELINES:continue
        base_error=results[baseline]['basket_mae']
        gain=1-value['basket_mae']/base_error if base_error>0 else 0.
        commodity_ok=all(value['commodities'][c]['mae']<=1.05*results[baseline]['commodities'][c]['mae'] for c in COMMODITIES)
        improved=sum(a<b for a,b in zip(value['fold_mae'],results[baseline]['fold_mae']))
        passed=fold_count>=4 and gain>=.1 and commodity_ok and improved>=4
        guards[candidate]={"gain":gain,"commodity_guard":commodity_ok,"improved_folds":improved,"qualified":passed}
        if passed:qualified.append(candidate)
    selected=min(qualified,key=lambda c:(results[c]['basket_mae'],c)) if qualified else baseline
    return {"baseline":baseline,"selected":selected,"qualified":qualified,"guards":guards}

def block_confidence(actual,point,baseline,lower,upper,dates,fold_ids,draws=2000):
    error=np.abs((point-actual)@WEIGHTS);base=np.abs((baseline-actual)@WEIGHTS)
    covered=((actual@WEIGHTS>=lower)&(actual@WEIGHTS<=upper)).astype(float)
    blocks=np.array([f"{fold}:{(pd.Timestamp(day)-pd.Timestamp('2022-01-01')).days//14}" for day,fold in zip(dates,fold_ids)])
    groups=[np.where(blocks==value)[0] for value in np.unique(blocks)]
    rng=np.random.default_rng(42);samples=[]
    for _ in range(draws):
        indices=np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))])
        denominator=base[indices].mean()
        samples.append([error[indices].mean(),covered[indices].mean(),1-error[indices].mean()/denominator if denominator>0 else 0.])
    bounds=np.quantile(samples,[.025,.975],axis=0)
    return {"draws":draws,"block_calendar_days":14,"blocks":len(groups),"seed":42,
            **{key:[float(x) for x in bounds[:,i]] for i,key in enumerate(('basket_mae','coverage','gain'))}}

def volatility(frame):
    latest=matrix(frame,'latest');vol=matrix(frame,'vol28')
    return (vol*latest*WEIGHTS).sum(axis=1)/(latest@WEIGHTS)

def execute(root:Path=ROOT):
    inputs=dataset_directory(root)
    protocol={"version":"research-1","status":"research_only","seed":42,"folds":folds(),"parameters":PARAMETERS,
              "target":{"calendar_days_after_issue":7,"minimum_observed_quotes":4},"ewma_half_life_calendar_days":7,
              "candidate_families":list(FAMILIES),"blends":BLENDS,"baselines":BASELINES,"reference_basket":REFERENCE_BASKET,
              "minimum_calibration_baskets":30,"minimum_validation_baskets":30,"minimum_folds":4,
              "selection_rule":{"basket_gain":.1,"max_commodity_regression":.05,"improved_folds":4},
              "interval_methods":["relative","additive"],"interval_coverage_floor":.75,"bootstrap_draws":2000,
              "dataset_files":{name:sha256((inputs/name).read_bytes()).hexdigest() for name in ('prices.csv','weather.csv')},
              "code":{name:sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('research.py','features.py','train.py','config.py','forecast.py')},
              "packages":{p:version(p) for p in ('numpy','pandas','lightgbm')},
              "historical_checks":"2025 and early 2026 have been inspected previously. They are exploratory, not fresh confirmation.",
              "promotion":"disabled: require a separately frozen study on new uninspected outcomes"}
    digest=sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest();run_id='study-'+digest[:16]
    parent=root/'reports/research';output=parent/run_id;output.mkdir(parents=True,exist_ok=True)
    frozen=output/'protocol.json'
    if frozen.exists() and json.loads(frozen.read_text())!=json.loads(json.dumps(protocol)):raise ValueError('Frozen protocol mismatch')
    atomic_write(frozen,json.dumps(protocol,indent=2).encode())
    # No outcome has been read by this run before the protocol is committed above.
    prices=pd.read_csv(inputs/'prices.csv',parse_dates=['date'])
    weather=pd.read_csv(inputs/'weather.csv',index_col='date',parse_dates=True)
    frame=prepare_frame(prices,weather);wx=[c for c in frame if c.startswith('wx_')]
    development=split(frame,'2022-01-01','2024-06-30')
    weather_enabled=bool(wx) and development[wx].notna().all().all()
    candidates=candidate_ids(weather_enabled)
    predictions={c:[] for c in candidates};actuals=[];dates=[];fold_ids=[];regimes=[];fold_reports=[]
    raw_bounds={c:{m:[] for m in ('relative','additive')} for c in candidates};csv_rows=[]
    for fold in protocol['folds']:
        parts={part:complete(split(frame,fold[part+'_start'],fold[part+'_end'])) for part in ('train','calibration','validation')}
        if weather_enabled:
            parts={key:complete(value[value[wx].notna().all(axis=1)]) for key,value in parts.items()}
        training,calibration,validation=(parts[key] for key in ('train','calibration','validation'))
        cal_y=matrix(calibration,'target');val_y=matrix(validation,'target')
        summary={**fold,"training_labels":len(training),"calibration_baskets":len(cal_y),"validation_baskets":len(val_y)}
        if len(cal_y)<30 or len(val_y)<30 or training.empty:
            summary['status']='insufficient_data';fold_reports.append(summary);continue
        models=model_bundles(training,wx,weather_enabled)
        thresholds=np.quantile(volatility(complete(training)),[1/3,2/3])
        regime=np.digitize(volatility(validation),thresholds)
        fold_dates=sorted(validation.date.unique())
        summary.update({"status":"evaluated","volatility_thresholds":thresholds.tolist(),"candidate_mae":{}})
        for candidate in candidates:
            cal_p=candidate_points(candidate,calibration,models);val_p=candidate_points(candidate,validation,models)
            predictions[candidate].append(val_p);summary['candidate_mae'][candidate]=metrics(val_y,val_p)['basket_mae']
            for method in ('relative','additive'):
                raw_bounds[candidate][method].append(joint_intervals(cal_y,cal_p,val_p,method))
            for i,day in enumerate(fold_dates):
                csv_rows.append({"fold":fold['id'],"date":pd.Timestamp(day).date().isoformat(),"candidate":candidate,
                                 "actual":float(val_y[i]@WEIGHTS),"prediction":float(val_p[i]@WEIGHTS)})
        actuals.append(val_y);dates.extend(fold_dates);fold_ids.extend([fold['id']]*len(fold_dates));regimes.extend(regime.tolist());fold_reports.append(summary)
        print(f"Evaluated {fold['id']}: {len(val_y)} complete baskets",flush=True)
    valid_folds=[f for f in fold_reports if f['status']=='evaluated']
    if len(valid_folds)<4:
        report={"status":"research_only","outcome":"insufficient_evidence","run_id":run_id,"protocol_sha256":digest,"folds":fold_reports}
    else:
        actual=np.concatenate(actuals);points={c:np.concatenate(v) for c,v in predictions.items()}
        results={c:{**metrics(actual,point),"fold_mae":[f['candidate_mae'][c] for f in valid_folds]} for c,point in points.items()}
        selection=select_candidate(results,len(valid_folds));selected=selection['selected'];baseline=selection['baseline']
        interval_results={};intervals={}
        for method in ('relative','additive'):
            bounds=np.concatenate(raw_bounds[selected][method]);intervals[method]=bounds
            interval_results[method]=metrics(actual,points[selected],bounds[:,0],bounds[:,1])
        eligible=[m for m,v in interval_results.items() if v['coverage']>=.75]
        interval_method=min(eligible,key=lambda m:(interval_results[m]['interval_score'],m)) if eligible else 'relative'
        selected_bounds=intervals[interval_method]
        confidence=block_confidence(actual,points[selected],points[baseline],selected_bounds[:,0],selected_bounds[:,1],dates,fold_ids)
        best_observed=min(results,key=lambda c:(results[c]['basket_mae'],c))
        best_bounds=np.concatenate(raw_bounds[best_observed]['relative'])
        best_confidence=block_confidence(actual,points[best_observed],points[baseline],best_bounds[:,0],best_bounds[:,1],dates,fold_ids)
        segments={}
        for name,mask in [(f"volatility_{label}",np.array(regimes)==i) for i,label in enumerate(('low','medium','high'))]+[(f"quarter_{f['id']}",np.array(fold_ids)==f['id']) for f in valid_folds]:
            segments[name]=metrics(actual[mask],points[selected][mask],selected_bounds[mask,0],selected_bounds[mask,1]) if mask.any() else {"n":0}
        # Freeze the winner above, then refit once for explicitly exploratory checks.
        final_train=complete(split(frame,'2022-01-01','2024-06-30'))
        final_cal=complete(split(frame,'2024-07-01','2024-12-31'))
        final_models=model_bundles(final_train,wx,weather_enabled)
        model_folder=output/'models';model_folder.mkdir(exist_ok=True)
        model_manifest={}
        for family,bundle in final_models.items():
            for (commodity,alpha),model in bundle['models'].items():
                filename=f'{family}_{commodity}_{alpha:.1f}.txt'
                model.booster_.save_model(str(model_folder/filename))
                model_manifest[filename]={'sha256':sha256((model_folder/filename).read_bytes()).hexdigest(),'features':bundle['features']}
        checks={}
        for name,start,end in [('2025','2025-01-01','2025-12-31'),('early_2026','2026-01-01','2026-03-10')]:
            test=complete(split(frame,start,end))
            if weather_enabled:test=complete(test[test[wx].notna().all(axis=1)])
            y=matrix(test,'target');p=candidate_points(selected,test,final_models)
            bounds=joint_intervals(matrix(final_cal,'target'),candidate_points(selected,final_cal,final_models),p,interval_method)
            checks[name]={"evidence":"previously_inspected_exploratory",**metrics(y,p,bounds[:,0],bounds[:,1]),
                          "baseline":metrics(y,candidate_points(baseline,test,final_models))}
        report={"status":"research_only","outcome":"completed","run_id":run_id,"protocol_sha256":digest,
                "generated_at":datetime.now(timezone.utc).isoformat(),"protocol":protocol,"folds":fold_reports,
                "weather_enabled":bool(weather_enabled),"candidates":results,"selection":selection,
                "interval_methods":interval_results,"selected_interval_method":interval_method,"interval_guard_passed":bool(eligible),
                "confidence_95":confidence,"segments":segments,"historical_checks":checks,
                "best_observed_candidate":best_observed,"best_observed_confidence_95":best_confidence,
                "research_model_artifacts":model_manifest,
                "promotion":"disabled_pending_new_uninspected_outcomes",
                "notes":["Development folds choose candidates and interval method; their scores are selection evidence.",
                         "Overlapping targets are dependent. Block intervals describe uncertainty, not guaranteed coverage.",
                         "Buyer-facing approved forecast and original historical evaluation remain unchanged."]}
    atomic_write(output/'results.json',json.dumps(report,indent=2,allow_nan=False).encode())
    pd.DataFrame(csv_rows).to_csv(output/'development_predictions.csv',index=False)
    atomic_write(parent/'latest.json',json.dumps(report,indent=2,allow_nan=False).encode())
    print(json.dumps({"run_id":run_id,"status":report['outcome'],"selection":report.get('selection',{}).get('selected'),"directory":str(output)}))
    return report

if __name__=='__main__':execute()
