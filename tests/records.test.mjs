import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {calculateBasket,identifyContract,actualBasket,addDays} from '../web/math.mjs';
import {validateRecord,mergeBackup} from '../web/records.mjs';
const snapshot=JSON.parse(fs.readFileSync(new URL('../artifacts/snapshot.json',import.meta.url)));
const contract=await identifyContract(calculateBasket(snapshot,'2025-06-16',{beans:20,carrot:30,tomato:20},30000));
const record={id:'portable-1',name:'Portable basket',saved_at:'2026-10-26T05:00:00Z',contract};
test('portable backup round-trip preserves original values and skips duplicates',()=>{
  const first=mergeBackup([],{schema_version:'1.0',baskets:[record]});
  assert.deepEqual(first.records,[record]);assert.equal(first.imported,1);
  const second=mergeBackup(first.records,{schema_version:'1.0',baskets:[record]});
  assert.equal(second.skipped,1);assert.equal(second.imported,0);
});
test('conflicts reject the whole merge without modifying existing records',()=>{
  const existing=[structuredClone(record)],fresh={...record,id:'portable-2'};
  assert.throws(()=>mergeBackup(existing,{schema_version:'1.0',baskets:[fresh,{...record,name:'Changed'}]}),/conflicts/);
  assert.deepEqual(existing,[record]);
});
test('corrupted nested values and impossible dates are rejected',()=>{
  for(const [field,value] of [['estimate',NaN],['interval',[99999,100000]],['source_hash','missing'],['issue_date','2025-02-30']]){
    const invalid=structuredClone(record);invalid.contract[field]=value;
    assert.throws(()=>validateRecord(invalid));
  }
  assert.throws(()=>addDays('2025-02-30',1));
});
test('comparisons require the original source snapshot',()=>{
  assert.notEqual(actualBasket(snapshot,contract),null);
  assert.equal(actualBasket({...snapshot,source_hash:'0'.repeat(64)},contract),null);
});
test('identity normalizes numeric inputs and ignores save time',async()=>{
  const again=await identifyContract({...contract,exported_at:'later',quantities:{tomato:20,carrot:30,beans:20}});
  assert.equal(again.contract_id,contract.contract_id);
  const forecast=await identifyContract({...contract,status:'forecast'});
  assert.notEqual(forecast.contract_id,contract.contract_id);
});
