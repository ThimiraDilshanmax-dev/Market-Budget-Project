import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {validateRecord} from '../web/records.mjs';
import {backupBatches} from '../web/storage.mjs';
import {validateSnapshot} from '../web/snapshot.mjs';
for(const fixture of JSON.parse(fs.readFileSync(new URL('./fixtures/records.json',import.meta.url)))){
 test('shared record: '+fixture.name,()=>{
  if(fixture.valid)assert.deepEqual(validateRecord(fixture.record),fixture.record);
  else assert.throws(()=>validateRecord(fixture.record));
 });
}
test('large collections export as restorable batches',()=>{
 const sample=JSON.parse(fs.readFileSync(new URL('./fixtures/records.json',import.meta.url)))[0].record;
 const records=Array.from({length:1001},(_,i)=>({...sample,id:'record-'+i}));
 assert.deepEqual(backupBatches(records).map(b=>b.length),[500,500,1]);
});
test('corrupt snapshot metadata is refused',()=>{
 const snapshot=JSON.parse(fs.readFileSync(new URL('../artifacts/snapshot.json',import.meta.url)));
 validateSnapshot(snapshot);snapshot.history[0].beans=-1;
 assert.throws(()=>validateSnapshot(snapshot));
});
test('nonfinite extension metadata is rejected without silent JSON conversion',()=>{
 const record=structuredClone(JSON.parse(fs.readFileSync(new URL('./fixtures/records.json',import.meta.url)))[0].record);
 record.extra=NaN;assert.throws(()=>validateRecord(record));
});
