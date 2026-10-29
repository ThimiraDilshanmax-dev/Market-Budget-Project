import {commodities,isISODate} from './math.mjs';
export function validateSnapshot(s){
 const number=(v,positive=false)=>typeof v==='number'&&Number.isFinite(v)&&(positive?v>0:v>=0);
 if(s.schema_version!=='1.0'||s.mode!=='historical_replay'||!/^[a-f0-9]{64}$/.test(s.source_hash))throw new Error('Unsupported snapshot identity.');
 if(JSON.stringify(s.model)!==JSON.stringify(s.evaluation.model)||JSON.stringify(s.coverage)!==JSON.stringify(s.evaluation.coverage))throw new Error('Snapshot metadata does not agree.');
 if(!Array.isArray(s.residual_scenarios)||s.residual_scenarios.length<30||s.residual_scenarios.length!==s.calibration_dates.length||s.residual_scenarios.some(row=>row.length!==3||row.some(v=>!Number.isFinite(v)||v< -1)))throw new Error('Invalid joint calibration scenarios.');
 const ordered=dates=>dates.length&&dates.every((d,i)=>isISODate(d)&&(i===0||dates[i-1]<d));
 if(!ordered(s.calibration_dates)||!ordered(s.forecasts.map(r=>r.date))||!ordered(s.history.map(r=>r.date)))throw new Error('Snapshot dates must be valid, ordered and unique.');
 if(s.calibration_dates.some(d=>Date.parse(d)+7*86400000>Date.parse(s.model.calibration_end)))throw new Error('Calibration targets cross their boundary.');
 for(const row of s.forecasts)for(const c of commodities){
  const age=(Date.parse(row.date)-Date.parse(row.last_price_dates[c]))/86400000;
  if(s.calibration_dates.at(-1)>=row.date||!isISODate(row.last_price_dates[c])||age<0||age>3||!number(row.point[c])||!number(row.latest[c],true)||(row.actual[c]!==null&&(!number(row.actual[c],true)||row.label_counts[c]<4)))throw new Error('Invalid forecast contract in snapshot.');
 }
 if(s.history.some(row=>commodities.some(c=>row[c]!==null&&!number(row[c],true)))||s.history.at(-1).date!==s.coverage.end)throw new Error('Invalid observed price history.');
 if(!ordered(s.test_predictions.map(r=>r.date))||s.test_predictions.some(r=>r.period!=='test_2025'||!r.date.startsWith('2025-')||!number(r.actual,true)||!['prediction','lower','upper'].every(k=>number(r[k]))||r.lower>r.prediction||r.upper<r.prediction)||s.evaluation.intervals.test_2025.n!==s.test_predictions.length)throw new Error('Invalid evaluated basket outcomes.');
 if(!s.evaluation.metrics.test_2025[s.model.selected])throw new Error('Evaluation method mismatch.');
 for(const period of ['tuning','test_2025','later_2026'])for(const r of Object.values(s.evaluation.metrics[period]))if(!number(r.basket_mae)||!Number.isFinite(r.basket_bias)||r.complete_baskets<=0||commodities.some(c=>!number(r.commodities[c].mae)))throw new Error('Invalid evaluation metrics.');
 if(!Array.isArray(s.source_audit)||!Array.isArray(s.corrections)||s.corrections.some(c=>!isISODate(c.date)||!commodities.includes(c.commodity)||!number(c.price,true)||!number(c.original_price,true)||!c.source_url.startsWith('https://www.cbsl.gov.lk/')))throw new Error('Invalid correction provenance.');
 return s;
}
export async function readVerifiedSnapshot(response,expected){
 if(!response.ok)throw new Error('Approved snapshot is unavailable.');
 const bytes=await response.arrayBuffer();const hash=await crypto.subtle.digest('SHA-256',bytes);
 const actual=[...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,'0')).join('');
 if(actual!==expected)throw new Error('Snapshot integrity failed. Reload a verified deployment.');
 return validateSnapshot(JSON.parse(new TextDecoder().decode(bytes)));
}
