import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {calculateBasket,empiricalInterval,jointCosts,safeCSV,actualBasket,addDays} from '../web/math.mjs';

const snapshot=JSON.parse(fs.readFileSync(new URL('../artifacts/snapshot.json',import.meta.url)));
test('real historical reference basket reproduces CBSL example',()=>{
  const result=calculateBasket(snapshot,'2026-03-10',{beans:20,carrot:30,tomato:20},20000);
  assert.equal(result.estimate,14750);assert.equal(result.target_start,'2026-03-11');assert.equal(result.target_end,'2026-03-17');assert.equal(result.calibration_n,105);
  assert.equal(actualBasket(snapshot,result),null);
});
test('joint scenarios preserve offsetting commodity moves',()=>{
  const residuals=Array.from({length:60},(_,i)=>i%2?[.5,-.5,0]:[-.5,.5,0]);
  assert.deepEqual(empiricalInterval(jointCosts([100,100,100],[1,1,0],residuals),200),[200,200]);
});
test('invalid quantities, zero basket and invalid budget rejected',()=>{
  for(const beans of [-1,NaN,Infinity,10001,true,'20'])assert.throws(()=>calculateBasket(snapshot,'2026-03-10',{beans,carrot:30,tomato:20}));
  assert.throws(()=>calculateBasket(snapshot,'2026-03-10',{beans:0,carrot:0,tomato:0}));
  assert.throws(()=>calculateBasket(snapshot,'2026-03-10',{beans:20,carrot:30,tomato:20},0));
});
test('CSV escapes formula injection and embedded quotes',()=>{
  assert.equal(safeCSV([['=1+1','A "name"','hello,world']]),'"\'=1+1","A ""name""","hello,world"');
});
test('date arithmetic crosses leap days and year boundaries',()=>{
  assert.equal(addDays('2024-02-28',1),'2024-02-29');assert.equal(addDays('2025-12-29',7),'2026-01-05');
});
