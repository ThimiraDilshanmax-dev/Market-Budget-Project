import {commodities,isISODate,addDays,validateQuantities,validateBudget} from './math.mjs';
import {amount,dec,calculationVersion} from './money.mjs';

export const maxBackupRecords=500;
const text=(v,max=128)=>typeof v==='string'&&v.trim().length>0&&v.length<=max;
const numeric=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1e12;
function jsonValue(value,seen=new Set()){
 if(value===null||typeof value==='string'||typeof value==='boolean')return true;
 if(typeof value==='number')return Number.isFinite(value);
 if(!value||typeof value!=='object'||seen.has(value)||(!Array.isArray(value)&&Object.getPrototypeOf(value)!==Object.prototype&&Object.getPrototypeOf(value)!==null))return false;
 seen.add(value);const valid=Object.values(value).every(item=>jsonValue(item,seen));seen.delete(value);return valid;
}
const timestamp=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(v)&&isISODate(v.slice(0,10))&&Number.isFinite(Date.parse(v));

export function validateRecord(record) {
  try {
    if(!record||!text(record.id)||!/^[A-Za-z0-9_-]+$/.test(record.id)) throw new Error('Invalid saved basket ID.');
    if(!jsonValue(record))throw new Error('Saved records must contain finite JSON values.');
    if(!text(record.name,100)) throw new Error('Basket names must contain 1–100 characters.');
    if(!timestamp(record.saved_at)) throw new Error('Saved time must be a valid ISO timestamp with timezone.');
    const c=record.contract;
    if(!['1.0','1.1'].includes(c.schema_version)||!['historical_replay','forecast'].includes(c.status)) throw new Error('Unsupported saved forecast schema or mode.');
    const modern=c.schema_version==='1.1';
    if(modern&&c.calculation_version!==calculationVersion)throw new Error('Unsupported calculation version.');
    if(!timestamp(c.exported_at))throw new Error('Invalid exported timestamp.');
    if(c.market!=='Dambulla'||c.currency!=='LKR'||c.price_type!=='Wholesale benchmark'||c.nominal_coverage!==.8)throw new Error('Unsupported market, currency or forecast scope.');
    for(const key of ['disclaimer','issue_timing','method','weather_status'])if(!text(c[key],2000))throw new Error('Missing or invalid '+key);
    if(!Number.isInteger(c.calibration_n)||c.calibration_n<30)throw new Error('Invalid calibration count.');
    if(!isISODate(c.issue_date)||c.target_start!==addDays(c.issue_date,1)||c.target_end!==addDays(c.issue_date,7)) throw new Error('Saved planning window must be issue+1 through issue+7.');
    validateQuantities(c.quantities);validateBudget(c.budget);
    if(!numeric(c.estimate)||!Array.isArray(c.interval)||c.interval.length!==2||!c.interval.every(numeric)||c.interval[0]>c.estimate||c.interval[1]<c.estimate) throw new Error('Invalid saved estimate or planning range.');
    if(!text(c.model_version)||!text(c.contract_id)||typeof c.source_hash!=='string'||!/^[a-f0-9]{64}$/.test(c.source_hash)) throw new Error('Missing saved model or source provenance.');
    if(!Array.isArray(c.lines)||c.lines.length!==3||new Set(c.lines.map(line=>line.commodity)).size!==3||c.lines.some(line=>!commodities.includes(line.commodity))) throw new Error('Saved line items must cover all three vegetables.');
    let total=0;
    for(const line of c.lines) {
      const age=(Date.parse(c.issue_date+'T12:00:00Z')-Date.parse(line.last_price_date+'T12:00:00Z'))/86400000;
      if(!text(line.name,100)||!numeric(line.latest_price)||line.latest_price===0||typeof line.change_percent!=='number'||!numeric(Math.abs(line.change_percent))||!isISODate(line.last_price_date)||age<0||age>3)throw new Error('Invalid saved line metadata.');
      if(!Array.isArray(line.price_interval)||line.price_interval.length!==2||!line.price_interval.every(numeric)||line.price_interval[0]>line.price_per_kg||line.price_interval[1]<line.price_per_kg)throw new Error('Invalid marginal range.');
      if(line.kg!==c.quantities[line.commodity]||!numeric(line.kg)||!numeric(line.price_per_kg)||!numeric(line.line_total)||Math.abs(line.kg*line.price_per_kg-line.line_total)>.025) throw new Error('Invalid saved line item.');
      total+=line.line_total;
      if(modern&&amount(dec(line.price_per_kg).mul(line.kg))!==line.line_total)throw new Error('Saved decimal line amount is inconsistent.');
    }
    if(Math.abs(total-c.estimate)>.025) throw new Error('Saved line totals do not match the basket estimate.');
    if(modern&&!c.lines.reduce((s,line)=>s.plus(line.line_total),dec(0)).eq(c.estimate))throw new Error('Saved decimal basket total is inconsistent.');
    for(const key of commodities)if(!Number.isInteger(c.price_ages[key])||c.price_ages[key]<0||c.price_ages[key]>3)throw new Error('Invalid source age.');
    for(const key of ['budget_difference','upper_budget_difference'])if(c.budget===null?c[key]!==null:typeof c[key]!=='number'||!numeric(Math.abs(c[key])))throw new Error('Invalid budget difference.');
    return structuredClone(record);
  } catch(error) {
    if(error instanceof TypeError) throw new Error('Incomplete or malformed saved basket record.');
    throw error;
  }
}

const canonical=value=>{
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
  return JSON.stringify(value);
};

export function mergeBackup(existing,backup) {
  if(!backup||backup.schema_version!=='1.0'||!Array.isArray(backup.baskets)||backup.baskets.length>maxBackupRecords) throw new Error('Choose a MarketBudget 1.0 JSON backup with at most 500 baskets.');
  const incoming=backup.baskets.map(validateRecord),records=existing.map(validateRecord),byId=new Map(records.map(record=>[record.id,record]));
  let imported=0,skipped=0;
  for(const record of incoming) {
    const prior=byId.get(record.id);
    if(prior) {
      if(canonical(prior)!==canonical(record)) throw new Error('A basket ID conflicts with an existing record. No records were imported.');
      skipped++;
    } else {byId.set(record.id,record);imported++;}
  }
  return {records:[...byId.values()].sort((a,b)=>Date.parse(b.saved_at)-Date.parse(a.saved_at)),imported,skipped};
}
