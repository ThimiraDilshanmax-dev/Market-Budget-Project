import Decimal from './vendor/decimal.mjs';
export const MoneyDecimal=Decimal.clone({precision:50,rounding:Decimal.ROUND_HALF_UP});
export const calculationVersion='decimal_half_up_v1';
export const dec=value=>new MoneyDecimal(value===0?0:String(value));
export const amount=value=>dec(value).toDecimalPlaces(2,Decimal.ROUND_HALF_UP).toNumber();
function bounds(values,point){
  if(values.length<30)throw new Error('At least 30 calibration scenarios required.');
  const sorted=[...values].sort((a,b)=>a.cmp(b)),n=sorted.length;
  return [MoneyDecimal.min(point,sorted[Math.max(0,Math.floor(.1*(n+1))-1)]).toDecimalPlaces(2,Decimal.ROUND_FLOOR).toNumber(),MoneyDecimal.max(point,sorted[Math.min(n-1,Math.ceil(.9*(n+1))-1)]).toDecimalPlaces(2,Decimal.ROUND_CEIL).toNumber()];
}
export function ledger(point,quantities,residuals){
 const prices=point.map(p=>dec(p).toDecimalPlaces(6)),weights=quantities.map(dec);
 const lines=prices.map((p,i)=>p.mul(weights[i]).toDecimalPlaces(2)),total=lines.reduce((s,v)=>s.plus(v),dec(0));
 const scenarios=residuals.map(row=>prices.reduce((s,p,i)=>s.plus(MoneyDecimal.max(0,p.mul(dec(row[i]).plus(1))).mul(weights[i])),dec(0)));
 return {prices:prices.map(p=>p.toNumber()),lines:lines.map(v=>v.toNumber()),total:total.toNumber(),interval:bounds(scenarios,total),marginal:prices.map((p,i)=>bounds(residuals.map(row=>MoneyDecimal.max(0,p.mul(dec(row[i]).plus(1)))),p))};
}
