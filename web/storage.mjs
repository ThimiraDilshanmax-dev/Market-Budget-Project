import {validateRecord,mergeBackup} from './records.mjs';
const legacyKey='marketbudget.baskets.v1';
const request=req=>new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
const complete=tx=>new Promise((resolve,reject)=>{tx.oncomplete=()=>resolve();tx.onabort=()=>reject(tx.error||new Error('Storage transaction cancelled.'));tx.onerror=()=>{};});

export class BrowserStore {
 constructor(){this.database=null;this.recovery=null;this.channel=typeof BroadcastChannel==='function'?new BroadcastChannel('marketbudget.baskets.v2'):null;}
 async open(){
  if(this.database)return this.database;
  const req=indexedDB.open('marketbudget',1);
  req.onupgradeneeded=()=>{req.result.createObjectStore('baskets',{keyPath:'id'});req.result.createObjectStore('metadata');};
  this.database=await request(req);this.database.onversionchange=()=>{this.database.close();this.database=null;};return this.database;
 }
 async transaction(action){
  const db=await this.open(),tx=db.transaction(['baskets','metadata'],'readwrite'),done=complete(tx);
  try{const result=await action(tx.objectStore('baskets'),tx.objectStore('metadata'));await done;this.channel?.postMessage('changed');return result;}
  catch(error){try{tx.abort();}catch{}await done.catch(()=>{});throw error;}
 }
 async initialize(){
  const db=await this.open(),tx=db.transaction('metadata','readonly');
  const prior=await request(tx.objectStore('metadata').get('legacy_migration'));
  let raw;try{raw=localStorage.getItem(legacyKey);}catch{throw new Error('Legacy browser storage is unavailable. Saved data has not been changed.');}
  if(prior?.raw===raw){this.recovery=null;return;}
  let records=[];
  try{
   const parsed=raw===null?[]:JSON.parse(raw);if(!Array.isArray(parsed))throw new Error('Invalid legacy storage.');
   records=parsed.map(validateRecord);
  }catch{
   let partial=[];try{const parsed=JSON.parse(raw);if(Array.isArray(parsed))for(const item of parsed){try{partial.push(validateRecord(item));}catch{}}}catch{}
   this.recovery={raw,records:partial};return;
  }
  await this.transaction(async(store,meta)=>{
   let merged=await request(store.getAll());
   for(let i=0;i<records.length;i+=500)merged=mergeBackup(merged,{schema_version:'1.0',baskets:records.slice(i,i+500)}).records;
   for(const record of merged)store.put(record);
   meta.put({raw,migrated_at:new Date().toISOString()},'legacy_migration');
  });
  this.recovery=null;
 }
 async list(){
  await this.initialize();const db=await this.open();const tx=db.transaction('baskets','readonly');
  return (await request(tx.objectStore('baskets').getAll())).map(validateRecord).sort((a,b)=>Date.parse(b.saved_at)-Date.parse(a.saved_at));
 }
 async import(backup){
  await this.initialize();if(this.recovery)throw new Error('Recover or archive the unreadable saved data first.');
  return this.transaction(async(store)=>{
   const merged=mergeBackup(await request(store.getAll()),backup);
   for(const record of merged.records)store.put(record);
   return {imported:merged.imported,skipped:merged.skipped,total:merged.records.length};
  });
 }
 async save(record){return this.import({schema_version:'1.0',baskets:[record]});}
 async remove(id){
  await this.initialize();if(this.recovery)throw new Error('Recover unreadable saved data before deleting records.');
  await this.transaction(async store=>{store.delete(id);});
 }
 async recover(){
  await this.initialize();if(!this.recovery)return;
  const recovery=this.recovery;
  await this.transaction(async(store,meta)=>{
   const current=await request(store.getAll());
   // Manual recovery can exceed one import batch; each legacy record is already validated.
   let records=current;
   for(let i=0;i<recovery.records.length;i+=500)records=mergeBackup(records,{schema_version:'1.0',baskets:recovery.records.slice(i,i+500)}).records;
   for(const record of records)store.put(record);
   meta.put({raw:recovery.raw,archived_at:new Date().toISOString()},'recovery-'+crypto.randomUUID());
   meta.put({raw:recovery.raw,migrated_at:new Date().toISOString()},'legacy_migration');
  });
  this.recovery=null;
 }
 onChange(callback){if(this.channel)this.channel.onmessage=callback;window.addEventListener('storage',event=>{if(event.key===legacyKey)callback();});}
}

export function backupBatches(records){
 const batches=[];let batch=[],bytes=200;
 const size=record=>new TextEncoder().encode(JSON.stringify(record)).length+1;
 for(const record of records){
  const length=size(record);
  if(length+200>5*1024*1024)throw new Error('One saved record exceeds the 5 MB backup limit.');
  if(batch.length===500||bytes+length>5*1024*1024){batches.push(batch);batch=[];bytes=200;}
  batch.push(record);bytes+=length;
 }
 if(batch.length||!batches.length)batches.push(batch);return batches;
}
