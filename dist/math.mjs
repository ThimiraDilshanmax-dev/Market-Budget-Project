import {ledger,amount,dec,calculationVersion} from './money.mjs';
export const commodities = ['beans', 'carrot', 'tomato'];
export const names = {beans:'Beans',carrot:'Carrots',tomato:'Tomatoes'};
export const methodNames = {latest_price:'Latest-price baseline',mean_28d:'28-day average',prior_year:'Prior-year baseline',price_pooled:'Price + calendar · pooled',weather_pooled:'Price + weather · pooled',price_individual:'Price + calendar · individual',weather_individual:'Price + weather · individual'};

export function addDays(value, count) {
  if(!isISODate(value)) throw new Error('Use a valid calendar date in YYYY-MM-DD format.');
  const date = new Date(value + 'T12:00:00Z');
  date.setUTCDate(date.getUTCDate() + count);
  return date.toISOString().slice(0,10);
}

export function isISODate(value) {
  return typeof value==='string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number(value.slice(0,4))>0 && Number.isFinite(Date.parse(value+'T12:00:00Z')) && new Date(value+'T12:00:00Z').toISOString().slice(0,10)===value;
}

export function validateQuantities(quantities) {
  if(!quantities || typeof quantities!=='object' || Object.keys(quantities).length!==3 || commodities.some(c=>!Object.hasOwn(quantities,c))) throw new Error('Provide kilograms for all three vegetables. Use zero to omit one.');
  const q=commodities.map(c=>quantities[c]);
  if(q.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0||v>10000)) throw new Error('Enter kilograms between 0 and 10,000 for each vegetable.');
  if(q.reduce((a,b)=>a+b,0)===0) throw new Error('Add at least one vegetable to your basket.');
  return q;
}

export function validateBudget(budget) {
  if(budget!==null && (typeof budget!=='number'||!Number.isFinite(budget)||budget<=0||budget>1e9)) throw new Error('Enter a spending limit above zero and no more than LKR 1 billion, or leave it empty.');
}

export async function identifyContract(contract) {
  const bits=value=>{
    const buffer=new ArrayBuffer(8);new DataView(buffer).setFloat64(0,value===0?0:value,false);
    return [...new Uint8Array(buffer)].map(v=>v.toString(16).padStart(2,'0')).join('');
  };
  const modern=contract.calculation_version===calculationVersion;
  const payload=[modern?'marketbudget-contract-v3':'marketbudget-contract-v2',contract.issue_date,contract.status,contract.model_version,contract.source_hash,commodities.map(c=>bits(contract.quantities[c])),contract.budget===null?null:bits(contract.budget)];
  if(modern)payload.push(calculationVersion);
  const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(payload)));
  return {...contract,contract_id:(modern?'mb3-':'mb2-')+[...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,'0')).join('').slice(0,16)};
}

export function jointCosts(point, quantities, residuals) {
  return residuals.map(row => row.reduce((sum, residual, i) => sum + Math.max(0,point[i] * (1 + residual)) * quantities[i],0));
}

export function empiricalInterval(values, point) {
  if(values.length < 30 || values.some(v => !Number.isFinite(v))) throw new Error('At least 30 valid complete calibration baskets are required.');
  const sorted = [...values].sort((a,b)=>a-b), n=sorted.length;
  return [Math.min(point,sorted[Math.max(0,Math.floor(.1*(n+1))-1)]),Math.max(point,sorted[Math.min(n-1,Math.ceil(.9*(n+1))-1)])];
}

export function calculateBasket(snapshot, issueDate, quantities, budget=null) {
  const q=validateQuantities(quantities);validateBudget(budget);
  if(!isISODate(issueDate)) throw new Error('Choose a valid historical issue date.');
  const row=snapshot.forecasts.find(f=>f.date===issueDate);
  if(!row) throw new Error('No approved forecast exists for this replay date.');
  const ages=Object.fromEntries(commodities.map(c=>[c,Math.round((new Date(issueDate+'T12:00:00Z')-new Date(row.last_price_dates[c]+'T12:00:00Z'))/86400000)]));
  if(commodities.some(c=>!isISODate(row.last_price_dates[c]))||Object.values(ages).some(age=>!Number.isFinite(age)||age<0||age>3)) throw new Error('A required price is stale or has an invalid date. Choose another historical issue date.');
  const point=commodities.map(c=>row.point[c]);
  if(point.some(p=>!Number.isFinite(p)||p<0)||commodities.some(c=>!Number.isFinite(row.latest[c])||row.latest[c]<=0)) throw new Error('Invalid forecast or source price. Reload the verified snapshot.');
  const residuals=snapshot.residual_scenarios;
  if(!Array.isArray(residuals)||residuals.some(r=>r.length!==3||r.some(v=>!Number.isFinite(v)))) throw new Error('Invalid calibration record. Reload the verified snapshot.');
  const calculated=ledger(point,q,residuals),estimate=calculated.total,range=calculated.interval;
  const lines=commodities.map((c,i)=>({commodity:c,name:names[c],kg:q[i],price_per_kg:calculated.prices[i],latest_price:row.latest[c],line_total:calculated.lines[i],change_percent:amount(dec(calculated.prices[i]).div(row.latest[c]).minus(1).mul(100)),price_interval:calculated.marginal[i],last_price_date:row.last_price_dates[c]}));
  return {schema_version:'1.1',calculation_version:calculationVersion,status:'historical_replay',issue_date:issueDate,target_start:addDays(issueDate,1),target_end:addDays(issueDate,7),exported_at:new Date().toISOString(),issue_timing:'Historical replay after assumed report availability; original publication times unknown.',market:'Dambulla',price_type:'Wholesale benchmark',currency:'LKR',quantities:{...quantities},budget,estimate,interval:range,nominal_coverage:.8,calibration_n:residuals.length,lines,model_version:snapshot.model.version,method:snapshot.model.selected,budget_difference:budget===null?null:amount(dec(budget).minus(estimate)),upper_budget_difference:budget===null?null:amount(dec(budget).minus(range[1])),price_ages:ages,weather_status:snapshot.model.weather_status,source_hash:snapshot.source_hash,disclaimer:'Weekly average reference cost, excluding delivery and supplier terms. Nominal 80% range is empirical, not a guarantee.'};
}

export function actualBasket(snapshot, contract) {
  if(contract.source_hash!==snapshot.source_hash) return null;
  const row=snapshot.forecasts.find(f=>f.date===contract.issue_date);
  if(!row || commodities.some(c=>row.actual[c]===null||!Number.isFinite(row.actual[c]))) return null;
  return commodities.reduce((sum,c)=>sum+row.actual[c]*contract.quantities[c],0);
}

export function safeCSV(rows) {
  return rows.map(row=>row.map(value=>{
    let text=String(value??'');
    if(/^\s*[=+@\-\t\r]/.test(text)) text="'"+text;
    return '"'+text.replaceAll('"','""')+'"';
  }).join(',')).join('\r\n');
}
