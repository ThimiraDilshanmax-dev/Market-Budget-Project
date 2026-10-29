/* Complete browser verification for API and IndexedDB editions.
 * Run with CHROMIUM_PATH=/usr/bin/chromium if using system Chromium.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const base=process.env.MARKETBUDGET_URL||'http://127.0.0.1:8000';
const name='QA plan '+Date.now();
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:1050}}),page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const runtime=await (await context.request.get(base+'/runtime.json')).json(),isAPI=runtime.storage==='api';
 const checks=[];
 const open=async(p,view='planner')=>{await p.goto(base+'/#'+view);await p.waitForSelector('#view-'+view+':not(.hidden)');};
 const save=async(p,label)=>{await p.locator('#save-basket').click();await p.locator('#basket-name').fill(label);await p.locator('#save-form button[type=submit]').click();await p.waitForFunction(()=>!document.querySelector('#save-dialog').open);};
 await open(page);assert.equal(await page.locator('#estimate-value').textContent(),'14,750');
 await page.locator('#quantity-beans').fill('0.0015');await page.locator('#quantity-carrot').fill('0');await page.locator('#quantity-tomato').fill('0');
 const csvWait=page.waitForEvent('download');await page.locator('#export-basket').click();const csvDownload=await csvWait;const csv=fs.readFileSync(await csvDownload.path(),'utf8');assert.match(csv,/0\.44/);
 await page.locator('#quantity-beans').fill('');assert.equal(await page.locator('#save-basket').isDisabled(),true);assert.equal(await page.locator('#estimate-value').textContent(),'—');
 await page.locator('#reset-basket').click();await page.locator('#budget').fill('1000');assert.match(await page.locator('#budget-status').textContent(),/above your limit/);await page.locator('#reset-basket').click();
 checks.push('decimal boundary export','blank input pauses estimate','budget warning');
 await page.locator('#issue-date').selectOption('2025-06-16');await save(page,name);await open(page,'saved');
 let card=page.locator('.saved-card').filter({hasText:name});assert.equal(await card.count(),1);assert.match(await card.textContent(),/Observed weekly benchmark/);
 const backupWait=page.waitForEvent('download');await page.locator('#backup-baskets').click();const backup=await backupWait;
 const data=JSON.parse(fs.readFileSync(await backup.path(),'utf8'));data.baskets=data.baskets.filter(r=>r.name===name);assert.equal(data.baskets.length,1);
 await card.locator('[data-delete]').click();await page.locator('#confirm-delete').click();await page.waitForFunction(()=>!document.querySelector('#delete-dialog').open);
 const file={name:'backup.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))};
 await page.locator('#backup-file').setInputFiles(file);await page.waitForFunction(label=>[...document.querySelectorAll('.saved-card')].some(el=>el.textContent.includes(label)),name);
 await page.locator('#backup-file').setInputFiles(file);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('0 baskets restored'));
 await page.reload();await page.waitForSelector('#view-saved:not(.hidden)');assert.equal(await page.locator('.saved-card').filter({hasText:name}).count(),1);
 card=page.locator('.saved-card').filter({hasText:name});await card.locator('[data-load]').click();assert.equal(await page.locator('#issue-date').inputValue(),'2025-06-16');
 await open(page,'saved');card=page.locator('.saved-card').filter({hasText:name});await card.locator('[data-delete]').click();await page.locator('#confirm-delete').click();await page.waitForFunction(()=>!document.querySelector('#delete-dialog').open);
 checks.push('save and historical comparison','backup restore','duplicate import skipped','reload persistence','planner restore','delete');
 await open(page,'performance');await page.waitForSelector('#research-content tbody tr');assert.equal(await page.locator('#research-content tbody tr').count(),20);
 assert.match(await page.locator('#research-content').textContent(),/promotion is disabled/);
 const chart=page.locator('#evaluation-chart');await chart.focus();const before=await chart.locator('.chart-selection').textContent();await page.keyboard.press('ArrowLeft');assert.notEqual(await chart.locator('.chart-selection').textContent(),before);await page.keyboard.press('ArrowDown');
 assert.equal(await chart.locator('circle[tabindex="0"]').count(),0);await chart.locator('summary').click();assert.equal(await chart.locator('tbody tr').count(),201);
 checks.push('separate research comparison','keyboard chart navigation','complete accessible data table');
 if(!isAPI){
  const other=await context.newPage();await open(page);await open(other);
  await Promise.all([save(page,'Concurrent A'),save(other,'Concurrent B')]);
  const records=await page.evaluate(async()=>{const {BrowserStore}=await import('./storage.mjs');return new BrowserStore().list();});
  assert.ok(records.some(r=>r.name==='Concurrent A'));assert.ok(records.some(r=>r.name==='Concurrent B'));
  checks.push('simultaneous tabs retain both plans');
  const fixtures=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../tests/fixtures/records.json')));
  const legacy=structuredClone(fixtures.find(f=>f.name==='complete-legacy').record);legacy.id='legacy-migration';
  const legacyContext=await browser.newContext();await legacyContext.addInitScript(record=>{if(!localStorage.getItem('qa-seeded')){localStorage.setItem('marketbudget.baskets.v1',JSON.stringify([record]));localStorage.setItem('qa-seeded','yes');}},legacy);
  const legacyPage=await legacyContext.newPage();await open(legacyPage,'saved');await legacyPage.waitForSelector('.saved-card');
  const migrated=await legacyPage.evaluate(async()=>{const {BrowserStore}=await import('./storage.mjs');return new BrowserStore().list();});assert.deepEqual(migrated,[legacy]);
  assert.deepEqual(JSON.parse(await legacyPage.evaluate(()=>localStorage.getItem('marketbudget.baskets.v1'))),[legacy]);await legacyContext.close();
  const brokenContext=await browser.newContext();await brokenContext.addInitScript(()=>{if(!localStorage.getItem('qa-seeded')){localStorage.setItem('marketbudget.baskets.v1','{"damaged":true}');localStorage.setItem('qa-seeded','yes');}});
  const broken=await brokenContext.newPage();await open(broken,'saved');await broken.waitForSelector('#saved-warning:not(.hidden)');
  const rawWait=broken.waitForEvent('download');await broken.locator('#backup-baskets').click();const raw=await rawWait;assert.equal(fs.readFileSync(await raw.path(),'utf8'),'{"damaged":true}');
  await broken.locator('#recover-browser').click();await broken.locator('#confirm-recovery').click();await broken.waitForSelector('#saved-warning',{state:'hidden'});assert.equal(await broken.evaluate(()=>localStorage.getItem('marketbudget.baskets.v1')),'{"damaged":true}');
  await open(broken);await save(broken,'Recovered plan');await open(broken,'saved');assert.equal(await broken.locator('.saved-card').filter({hasText:'Recovered plan'}).count(),1);await brokenContext.close();
  checks.push('legacy migration retains values and original','corrupt data export','explicit recovery and archive');
  const bulkContext=await browser.newContext();const bulkPage=await bulkContext.newPage();await open(bulkPage,'saved');
  await bulkPage.evaluate(async record=>{const {BrowserStore}=await import('./storage.mjs');const store=new BrowserStore();const records=Array.from({length:501},(_,i)=>({...record,id:'bulk-'+i,name:'Bulk '+i}));await store.import({schema_version:'1.0',baskets:records.slice(0,500)});await store.import({schema_version:'1.0',baskets:records.slice(500)});},fixtures[0].record);
  await bulkPage.reload();await bulkPage.waitForSelector('#backup-batch:not(.hidden)');await bulkPage.locator('#backup-batch').selectOption('1');const bulkWait=bulkPage.waitForEvent('download');await bulkPage.locator('#backup-baskets').click();const bulk=await bulkWait;const contents=JSON.parse(fs.readFileSync(await bulk.path(),'utf8'));assert.equal(contents.baskets.length,1);await bulkContext.close();checks.push('large collection restorable backup batches');
 }else{
  const outage=await context.newPage();await outage.route('**/api/v1/snapshot',route=>route.fulfill({status:503,body:'unavailable'}));await outage.goto(base);await outage.waitForSelector('#load-error:not(.hidden)');assert.match(await outage.locator('#storage-label').textContent(),/SQLite/);await outage.close();
  await open(page);await page.route('**/api/v1/baskets',route=>route.request().method()==='GET'?route.fulfill({status:503,contentType:'application/json',body:'{"detail":"temporary list outage"}'}):route.continue());await save(page,'Committed once');assert.match(await page.locator('#toast').textContent(),/do not repeat the save/);await page.unroute('**/api/v1/baskets');
  const rows=await (await context.request.get(base+'/api/v1/baskets')).json();const committed=rows.filter(r=>r.name==='Committed once');assert.equal(committed.length,1);await context.request.delete(base+'/api/v1/baskets/'+committed[0].id);
  checks.push('API outage never switches storage','committed save survives list refresh failure');
 }
 for(const width of [1440,1024,820,680,390,320]){
  await page.setViewportSize({width,height:950});
  for(const view of ['planner','prices','saved','performance','sources']){await open(page,view);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow ${width}/${view}`);}
 }
 checks.push('all five views at six viewport widths');assert.deepEqual(errors,[]);
 const reportDir=path.resolve(__dirname,'../reports');await page.setViewportSize({width:1440,height:1050});await open(page);await page.evaluate(()=>document.querySelector('#toast').classList.add('hidden'));await page.screenshot({path:path.join(reportDir,'dashboard-desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(reportDir,'dashboard-mobile.png'),fullPage:true});
 await open(page,'performance');await page.screenshot({path:path.join(reportDir,'research-mobile.png'),fullPage:true});
 const result={status:'passed',url:base,storage:runtime.storage,checks,javascript_errors:errors};fs.writeFileSync(path.join(reportDir,'browser-qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
