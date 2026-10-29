import {commodities,names,methodNames,addDays,calculateBasket,actualBasket,safeCSV,identifyContract as identify} from './math.mjs';
import {validateRecord,mergeBackup} from './records.mjs';
import {BrowserStore,backupBatches} from './storage.mjs';
import {readVerifiedSnapshot} from './snapshot.mjs';

const $=(selector,root=document)=>root.querySelector(selector);
const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];
const number=(v,digits=0)=>new Intl.NumberFormat('en-LK',{maximumFractionDigits:digits,minimumFractionDigits:0}).format(v);
const money=(v,digits=2)=>'LKR '+number(v,digits);
const formatDate=(value,year=true)=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',...(year?{year:'numeric'}:{}),timeZone:'UTC'}).format(new Date(value+'T12:00:00Z'));
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors={beans:'#789579',carrot:'#d69b58',tomato:'#c77e6c'};
const state={snapshot:null,issueDate:null,quantities:{beans:20,carrot:30,tomato:20},budget:20000,result:null,saved:[],api:false,priceDays:28,visiblePrices:[],deleteId:null,valid:true,storageBlocked:false};
const browserStore=new BrowserStore();
const iconPaths={basket:'<path d="M3 8h18l-2 12H5L3 8Z"/><path d="m7 8 5-6 5 6M9 12v4m6-4v4"/>',chart:'<path d="M4 3v17h17M8 14l4-5 4 3 5-7"/>',bookmark:'<path d="M6 3h12v18l-6-4-6 4V3Z"/>',pulse:'<path d="M2 12h5l3-8 4 16 3-8h5"/>',database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4m0 3h.01"/>',history:'<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6M12 7v5l3 2"/>',pin:'<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/>',reset:'<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6"/>',spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/>',download:'<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',shield:'<path d="m12 2 8 4v6c0 6-8 10-8 10S4 18 4 12V6l8-4Z"/><path d="m8 12 3 3 5-6"/>',calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2"/>',layers:'<path d="m12 3 10 5-10 5L2 8l10-5ZM2 12l10 5 10-5M2 16l10 5 10-5"/>',check:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>'};
const icon=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name]||iconPaths.info}</svg>`;
function hydrateIcons(root=document){$$('[data-icon]',root).forEach(el=>{el.innerHTML=icon(el.dataset.icon);});}

const vegetables={
  beans:`<svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><path d="M12 35c5-2 9-10 12-17 2-5 7-9 11-11-4 5-3 11-8 18-4 6-9 10-15 10Z" fill="#7e9b58"/><path d="M16 38c6-2 11-8 15-15 3-5 6-6 7-6-1 8-7 17-14 20-3 2-6 2-8 1Z" fill="#a1b96e"/><path d="M12 35c9-6 12-15 21-26M17 37c7-2 14-11 19-18" stroke="#507b3d" stroke-width="1" stroke-linecap="round"/><path d="m34 8 1-4m2 14 3-2" stroke="#668344" stroke-width="1.5" stroke-linecap="round"/><path d="M20 22c2-5 4-9 7-12-5 3-9 7-11 12-3 5-4 9-5 12 3-2 6-7 9-12Z" fill="#8fad65"/><path d="M11 34c4-7 8-15 15-23" stroke="#75974a" stroke-width="1"/></svg>`,
  carrot:`<svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><path d="M27 15c-8 4-16 18-19 26 9-3 23-11 27-19 2-6-3-9-8-7Z" fill="#e6a15b"/><path d="M29 19C22 27 14 35 8 41c10-4 22-12 26-19 1-2 0-3-1-4Z" fill="#d78a43"/><path d="m31 16 3-10 3 2-3 9m0-1 8-7 1 3-7 7m-2-5 3-12 3 2-4 12" fill="#7d9a59"/><path d="m21 22 4 3m-9 4 4 2m-7 3 3 2m11-18 4 3" stroke="#c67f3d" stroke-width="1.4" stroke-linecap="round"/><path d="M27 17c-5 5-12 15-16 21" stroke="#efb67b" stroke-width="1.5" stroke-linecap="round"/></svg>`,
  tomato:`<svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><path d="M24 13c12-5 22 7 17 18-3 7-13 11-22 8C7 37 4 27 9 19c3-5 9-7 15-6Z" fill="#d77f68"/><path d="M34 16c12 11 1 25-12 24 12 4 24-3 22-13-1-5-5-9-10-11Z" fill="#bd6651"/><path d="m24 16-10-3 8-1 1-6 3 6 8-2-5 5 5 5-9-3-6 4 2-5" fill="#7e9255"/><path d="M26 12c-1-5 0-7 2-9" stroke="#687e43" stroke-width="2" stroke-linecap="round"/><path d="M13 22c-2 3-1 7 1 9" stroke="#e9a088" stroke-width="2.5" stroke-linecap="round"/></svg>`
};

function toast(message){const el=$('#toast');el.textContent=message;el.classList.remove('hidden');clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.add('hidden'),3800);}
function download(filename,content,type='application/json'){
  const blob=new Blob([type==='text/csv'?'\uFEFF':'',content],{type:type+';charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
}
function csvContract(contract,name='Weekly basket'){
  const rows=[['basket','contract_id','mode','issue_date','target_start','target_end','commodity','kg','LKR_per_kg','line_total_LKR','model_version'],...contract.lines.map(line=>[name,contract.contract_id,contract.status,contract.issue_date,contract.target_start,contract.target_end,line.commodity,line.kg,line.price_per_kg,line.line_total,contract.model_version]),['basket_estimate_LKR',contract.estimate],['nominal_80pct_basket_lower_LKR',contract.interval[0]],['nominal_80pct_basket_upper_LKR',contract.interval[1]],['source_hash',contract.source_hash],['calculation_version',contract.calculation_version||'legacy_policy_not_stored'],['exported_at',contract.exported_at],['scope',contract.disclaimer]];
  return safeCSV(rows);
}

function renderRows(){
  const row=state.snapshot.forecasts.find(r=>r.date===state.issueDate);
  $('#vegetable-rows').innerHTML=commodities.map(c=>`<div class="vegetable-row"><div class="vegetable-identity"><span class="vegetable-illustration ${c}">${vegetables[c]}</span><div><strong>${names[c]}</strong><small>Dambulla wholesale</small></div></div><div class="row-price">${number(row.latest[c],2)}<small>LKR / kg</small></div><label class="quantity-field"><input id="quantity-${c}" aria-label="${names[c]} quantity in kilograms" type="number" inputmode="decimal" min="0" max="10000" step="any" value="${state.quantities[c]}"><span>kg</span></label><strong class="row-cost" id="cost-${c}">—</strong></div>`).join('');
  commodities.forEach(c=>$('#quantity-'+c).addEventListener('input',()=>updateEstimate()));
}

function updateEstimate(){
  const start=addDays(state.issueDate,1),end=addDays(state.issueDate,7);
  $('#planning-window').textContent=`${formatDate(start,false)} – ${formatDate(end,false)}`;
  $('#estimate-date').textContent=`${formatDate(start,false)} – ${formatDate(end)} · 7 calendar days`;
  try{
    commodities.forEach(c=>{const input=$('#quantity-'+c);input.removeAttribute('aria-invalid');if(input.value.trim()===''||input.validity.badInput){input.setAttribute('aria-invalid','true');throw new Error(`Enter kilograms for ${names[c].toLowerCase()}. Use 0 to omit it.`);}});
    if($('#budget').validity.badInput)throw new Error('Enter a valid spending limit or leave it empty.');
    const quantities=Object.fromEntries(commodities.map(c=>[c,Number($('#quantity-'+c).value)]));
    const budget=$('#budget').value.trim()===''?null:Number($('#budget').value);
    const result=calculateBasket(state.snapshot,state.issueDate,quantities,budget);
    state.quantities=quantities;state.budget=budget;state.result=result;state.valid=true;
    $('#form-error').classList.add('hidden');$('.cost-breakdown').classList.remove('hidden');$('#save-basket').disabled=false;$('#export-basket').disabled=false;
    $('#estimate-value').textContent=number(result.estimate,2);
    $('#estimate-date').textContent=`${formatDate(result.target_start,false)} – ${formatDate(result.target_end)} · 7 calendar days`;
    $('#planning-window').textContent=`${formatDate(result.target_start,false)} – ${formatDate(result.target_end,false)}`;
    $('#range-lower').textContent=money(result.interval[0]);$('#range-upper').textContent=money(result.interval[1]);
    const width=result.interval[1]-result.interval[0],position=width?((result.estimate-result.interval[0])/width)*100:50;
    $('.range-track>span').style.left=Math.max(3,Math.min(97,position))+'%';
    $('#total-weight').textContent=number(Object.values(quantities).reduce((a,b)=>a+b,0),6)+' kg';
    const items=Object.values(quantities).filter(v=>v>0).length;$('#basket-item-count').textContent=items+(items===1?' vegetable':' vegetables');
    const total=result.lines.reduce((sum,line)=>sum+line.line_total,0);
    result.lines.forEach(line=>{$('#cost-'+line.commodity).textContent=number(line.line_total,2);});
    $('#breakdown-bar').innerHTML=result.lines.map(line=>`<span style="width:${total?line.line_total/total*100:0}%;background:${colors[line.commodity]}" title="${line.name}: ${money(line.line_total)}"></span>`).join('');
    $('#breakdown-lines').innerHTML=result.lines.map(line=>`<div class="breakdown-line"><i style="background:${colors[line.commodity]}"></i><span>${line.name}</span><strong>${money(line.line_total)}</strong><small>${total?number(line.line_total/total*100):0}%</small></div>`).join('');
    const status=$('#budget-status');status.classList.toggle('over',budget!==null&&result.upper_budget_difference<0);
    if(budget===null) status.innerHTML=icon('info')+'<div><strong>A spending limit adds context</strong><small>Set an optional limit to see your budget headroom.</small></div>';
    else if(result.budget_difference<0) status.innerHTML=icon('info')+`<div><strong>${money(-result.budget_difference)} above your limit</strong><small>Estimate vs ${money(budget)} limit. Review quantities or reserve more cash.</small></div>`;
    else if(result.upper_budget_difference<0) status.innerHTML=icon('info')+`<div><strong>${money(result.budget_difference)} below your limit</strong><small>The upper range is ${money(-result.upper_budget_difference)} above your ${money(budget)} limit.</small></div>`;
    else status.innerHTML=icon('check')+`<div><strong>${money(result.budget_difference)} below your limit</strong><small>Even the upper range leaves ${money(result.upper_budget_difference)} of headroom.</small></div>`;
    const coverage=state.snapshot.evaluation.intervals.test_2025.observed_coverage;
    $('#method-note').textContent=`${methodNames[result.method]}. The nominal 80% range covered ${number(coverage*100,1)}% of complete 2025 test baskets for the 20/30/20 kg reference basket. Coverage for other quantities has not been established.`;
    const dates=[...new Set(result.lines.map(line=>line.last_price_date))].sort();
    $('#context-freshness').textContent=dates.length===1?`Quotes dated ${formatDate(dates[0],false)}`:`Quote dates ${formatDate(dates[0],false)} – ${formatDate(dates.at(-1),false)}`;
    return true;
  }catch(error){
    state.valid=false;state.result=null;$('#form-error').textContent=error.message;$('#form-error').classList.remove('hidden');$('#save-basket').disabled=true;$('#export-basket').disabled=true;$('#estimate-value').textContent='—';$('#range-lower').textContent='—';$('#range-upper').textContent='—';$('#total-weight').textContent='—';commodities.forEach(c=>$('#cost-'+c).textContent='—');$('.cost-breakdown').classList.add('hidden');$('#budget-status').innerHTML=icon('info')+'<div><strong>Update your basket inputs</strong><small>The estimate is paused until your quantities and optional limit are valid.</small></div>';return false;
  }
}

function priceChart(target,rows,{height=195,comparison=false}={}){
  const el=$(target);el.replaceChildren();
  if(!rows.length){el.innerHTML='<p class="no-chart">No observations in this window. Try another date.</p>';return;}
  const width=760,pad={left:45,right:17,top:16,bottom:29};
  const plotW=width-pad.left-pad.right,plotH=height-pad.top-pad.bottom;
  const start=Date.parse(rows[0].date+'T12:00:00Z'),end=Date.parse(rows.at(-1).date+'T12:00:00Z');
  const series=comparison?[{key:'prediction',label:'Estimate',color:'#527248'},{key:'actual',label:'Observed benchmark',color:'#d29a63'}]:commodities.map(c=>({key:c,label:names[c],color:colors[c]}));
  const values=rows.flatMap(row=>[...series.map(s=>row[s.key]),...(comparison?[row.upper,row.lower]:[])]).filter(v=>v!==null&&Number.isFinite(v));
  if(!values.length){el.innerHTML='<p class="no-chart">No valid quotes in this window.</p>';return;}
  const max=Math.max(...values)*1.12,min=comparison?Math.max(0,Math.min(...values)*.85):Math.max(0,Math.floor(Math.min(...values)*.5/50)*50),range=max-min||1;
  const x=date=>pad.left+((Date.parse(date+'T12:00:00Z')-start)/(end-start||1))*plotW;
  const y=value=>pad.top+plotH-(value-min)/range*plotH;
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${comparison?'Basket estimates, nominal 80 percent interval and observed weekly costs':'Observed Dambulla wholesale price history in LKR per kilogram'}"><title>${comparison?'2025 test basket outcomes':'Historical wholesale price observations'}</title>`;
  for(let i=0;i<5;i++){
    const value=min+range*i/4,py=y(value);
    svg+=`<line x1="${pad.left}" y1="${py}" x2="${width-pad.right}" y2="${py}" class="chart-grid"/><text x="${pad.left-9}" y="${py+3}" text-anchor="end" class="chart-label">${number(value)}</text>`;
  }
  for(let i=0;i<5;i++){
    const idx=Math.round((rows.length-1)*i/4),px=x(rows[idx].date);
    svg+=`<text x="${px}" y="${height-7}" text-anchor="${i===0?'start':i===4?'end':'middle'}" class="chart-label">${formatDate(rows[idx].date,false)}</text>`;
  }
  if(comparison){
    const top=rows.map(r=>`${x(r.date)},${y(r.upper)}`).join(' '),bottom=[...rows].reverse().map(r=>`${x(r.date)},${y(r.lower)}`).join(' ');
    svg+=`<polygon points="${top} ${bottom}" fill="#b9cda5" fill-opacity=".26"/>`;
  }
  series.forEach((s,seriesIndex)=>{
    // Missing values break the path; coordinates come only from observations.
    let path='',open=false;
    rows.forEach(r=>{const v=r[s.key];if(v===null||!Number.isFinite(v)){open=false;return;}path+=(open?' L':' M')+x(r.date).toFixed(2)+','+y(v).toFixed(2);open=true;});
    svg+=`<path d="${path}" fill="none" stroke="${s.color}" stroke-width="${comparison?1.7:2}" stroke-linecap="round" stroke-linejoin="round"/>`;
    rows.forEach((r,dateIndex)=>{
      const v=r[s.key];if(v===null||!Number.isFinite(v))return;
      const label=`${s.label} · ${formatDate(r.date)} · ${money(v,2)}`;
      svg+=`<circle cx="${x(r.date)}" cy="${y(v)}" r="${rows.length>80?1.6:2.7}" fill="${s.color}" aria-hidden="true" data-series="${seriesIndex}" data-index="${dateIndex}" data-tip="${escape(label)}"><title>${escape(label)}</title></circle>`;
    });
  });
  svg+='</svg>';el.innerHTML=svg;
  el.tabIndex=0;el.setAttribute('role','group');el.setAttribute('aria-label','Interactive price observations');
  const instructions=document.createElement('p');instructions.className='chart-instructions';instructions.id=el.id+'-instructions';instructions.textContent='Use Left/Right to move through dates, Up/Down to change series, and Home/End for the first/last observation. Tap a point to inspect it.';el.append(instructions);el.setAttribute('aria-describedby',instructions.id);
  const readout=document.createElement('p');readout.className='chart-selection';readout.setAttribute('aria-live','polite');el.append(readout);
  let selectedDate=rows.length-1,selectedSeries=0;
  const inspect=()=>{const row=rows[selectedDate],s=series[selectedSeries],value=row[s.key];readout.textContent=formatDate(row.date)+' · '+s.label+' · '+(value===null||!Number.isFinite(value)?'Not reported':money(value,2));};inspect();
  el.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key))return;event.preventDefault();if(event.key==='ArrowLeft')selectedDate=Math.max(0,selectedDate-1);if(event.key==='ArrowRight')selectedDate=Math.min(rows.length-1,selectedDate+1);if(event.key==='ArrowUp')selectedSeries=(selectedSeries+series.length-1)%series.length;if(event.key==='ArrowDown')selectedSeries=(selectedSeries+1)%series.length;if(event.key==='Home')selectedDate=0;if(event.key==='End')selectedDate=rows.length-1;inspect();};
  el.onpointerdown=event=>{const dot=event.target.closest?.('circle[data-index]');if(dot){selectedDate=Number(dot.dataset.index);selectedSeries=Number(dot.dataset.series);inspect();}};
  const details=document.createElement('details');details.className='chart-data';
  const columns=[...series,...(comparison?[{key:'lower',label:'Range lower'},{key:'upper',label:'Range upper'}]:[])];
  details.innerHTML='<summary>View all observations as a table</summary><div class="table-scroll"><table><caption>All displayed observations · LKR</caption><thead><tr><th>Date</th>'+columns.map(c=>'<th>'+escape(c.label)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr><td>'+formatDate(r.date)+'</td>'+columns.map(c=>'<td>'+(r[c.key]===null?'Not reported':number(r[c.key],2))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';el.append(details);

  const tooltip=document.createElement('div');tooltip.className='chart-tooltip hidden';el.append(tooltip);
  $$('circle[data-tip]',el).forEach(dot=>{
    const show=()=>{tooltip.textContent=dot.dataset.tip;tooltip.classList.remove('hidden');const box=el.getBoundingClientRect(),p=dot.getBoundingClientRect();tooltip.style.left=Math.max(5,Math.min(box.width-200,p.left-box.left-50))+'px';tooltip.style.top=Math.max(0,p.top-box.top-39)+'px';};
    dot.addEventListener('mouseenter',show);dot.addEventListener('focus',show);dot.addEventListener('mouseleave',()=>tooltip.classList.add('hidden'));dot.addEventListener('blur',()=>tooltip.classList.add('hidden'));
  });
}
function plannerChart(){const start=addDays(state.issueDate,-28),rows=state.snapshot.history.filter(r=>r.date>=start&&r.date<=state.issueDate);priceChart('#planner-chart',rows);}

function renderPrices(){
  let end=$('#price-end').value||state.snapshot.coverage.end;
  const min=state.snapshot.history[0].date,max=state.snapshot.coverage.end;
  if(end<min||end>max){end=end<min?min:max;$('#price-end').value=end;toast('Showing a date within the available source history.');}
  const start=addDays(end,-state.priceDays);
  const rows=state.snapshot.history.filter(r=>r.date>=start&&r.date<=end);state.visiblePrices=rows;
  $('#price-source-end').textContent=formatDate(max);
  $('#price-stat-cards').innerHTML=commodities.map(c=>{
    const valid=rows.filter(r=>r[c]!==null),last=valid.at(-1),first=valid[0],change=last&&first?(last[c]/first[c]-1)*100:0;
    return `<div class="stat-card"><div class="stat-title">${names[c]}<span class="color-dot" style="background:${colors[c]}"></span></div><div class="stat-value">${last?number(last[c],2):'—'}<small>LKR / kg</small></div><p>${last?`${formatDate(last.date,false)} · ${change>0?'+':''}${number(change,1)}% over this window`:'No published quote in this window'}</p></div>`;
  }).join('');
  priceChart('#explorer-chart',rows,{height:265});
  $('#price-table').innerHTML=rows.slice(-15).reverse().map(r=>`<tr><td>${formatDate(r.date)}</td>${commodities.map(c=>`<td>${r[c]===null?'Not reported':number(r[c],2)}</td>`).join('')}<td>Dambulla · wholesale</td></tr>`).join('')||'<tr><td colspan="5">No observations in this window.</td></tr>';
}

function renderPerformance(){
  const evaluation=state.snapshot.evaluation,selected=state.snapshot.model.selected,selection=state.snapshot.model.selection;
  const best=selection.best_learned,tuning=evaluation.tuning;
  const regressions=commodities.filter(c=>tuning[best].commodities[c].mae>1.05*tuning[selection.best_baseline].commodities[c].mae);
  const explanation=selected===selection.best_baseline?`The strongest development candidate improved basket MAE by ${number(selection.learned_improvement*100,1)}%, but ${regressions.length?regressions.map(c=>names[c].toLowerCase()).join(', ')+' exceeded the 5% commodity-error regression limit':'the full release criteria were not met'}. The selected method stays with the strongest baseline.`:`The selected model passed the 10% development basket improvement goal and the 5% commodity regression guard.`;
  $('#selection-explanation').innerHTML=icon('shield')+`<div><strong>Selected method: ${methodNames[selected]}</strong><p>${escape(explanation)}</p></div>`;
  const metrics=evaluation.metrics.test_2025[selected],intervals=evaluation.intervals.test_2025;
  $('#evaluation-stats').innerHTML=`<div class="stat-card"><div class="stat-title">2025 basket error · MAE</div><div class="stat-value">${number(metrics.basket_mae)}<small>LKR</small></div><p>20 / 30 / 20 kg reference basket</p></div><div class="stat-card"><div class="stat-title">Nominal 80% range · observed coverage</div><div class="stat-value">${number(intervals.observed_coverage*100,1)}<small>%</small></div><p>Mean range width: ${money(intervals.mean_width)}</p></div><div class="stat-card"><div class="stat-title">Complete evaluated baskets</div><div class="stat-value">${metrics.complete_baskets}</div><p>2025 issue dates · overlapping weekly targets</p></div>`;
  const labels={train:'Model training',tuning:'Model selection',calibration:'Interval calibration',test_2025:'Final test',later_2026:'Later check'};
  const periods={train:'2022 – 2023',tuning:'Jan – Jun 2024',calibration:'Jul – Dec 2024',test_2025:'2025',later_2026:'Early 2026'};
  $('#split-timeline').innerHTML=Object.entries(evaluation.splits).map(([key,value])=>`<div class="split-block ${key}"><strong>${labels[key]}</strong><span>${periods[key]}</span><small>${value.labelled_rows} labels · ${value.complete_baskets} baskets</small></div>`).join('');
  const period=$('#evaluation-period').value;
  $('#evaluation-table').innerHTML=Object.entries(evaluation.metrics[period]).map(([method,value])=>`<tr class="${method===selected?'selected-row':''}"><td>${methodNames[method]}${method===selected?'<span class="selected-pill">SELECTED</span>':''}</td><td>${number(value.basket_mae)}</td>${commodities.map(c=>`<td>${number(value.commodities[c].mae,1)}</td>`).join('')}<td>${value.complete_baskets}</td></tr>`).join('');
  $('#calibration-description').textContent=`The basket range uses ${state.snapshot.residual_scenarios.length} complete calibration dates from July–December 2024. On the 2025 test, ${number(intervals.observed_coverage*100,1)}% of ${intervals.n} observed basket costs fell within the nominal 80% range. Its mean width was ${money(intervals.mean_width)}.`;
  priceChart('#evaluation-chart',state.snapshot.test_predictions,{height:270,comparison:true});
  renderResearch();
}

let researchPromise;
async function renderResearch(){
 const el=$('#research-content');
 try{
  researchPromise??=fetch(state.api?'/api/v1/research/latest':'./data/research.json').then(r=>{if(!r.ok)throw new Error('Research results are unavailable.');return r.json();});
  const report=await researchPromise;
  if(report.status!=='research_only'||report.outcome!=='completed'){el.innerHTML='<p>No complete research comparison is available yet. The approved replay remains selected.</p>';return;}
  const selected=report.selection.selected,base=report.selection.baseline,best=report.best_observed_candidate;
  const label=id=>{const [family,weight]=id.split('@');return (methodNames[family]||({ewma_7d:'7-day EWMA'}[family])||family)+(weight&&weight!=='1'?' · '+number(Number(weight)*100)+'% model blend':'');};
  const selectedMetrics=report.candidates[selected],range=report.interval_methods[report.selected_interval_method];
  el.innerHTML=`<div class="decision-banner"><div><strong>${report.selection.qualified.length?'Research candidate: '+escape(label(selected)):'No learned candidate passed all release guards'}</strong><p>The best observed point-error improvement was ${number((1-report.candidates[best].basket_mae/report.candidates[base].basket_mae)*100,1)}%. The required improvement is 10%, with commodity and fold-stability guards. Model promotion is disabled.</p></div></div><div class="stat-cards"><div class="stat-card"><div class="stat-title">Development baskets</div><div class="stat-value">${selectedMetrics.n}</div><p>${report.folds.filter(f=>f.status==='evaluated').length} chronological folds · 2023 Q1 to 2024 Q2</p></div><div class="stat-card"><div class="stat-title">Selected development basket MAE</div><div class="stat-value">${number(selectedMetrics.basket_mae)}<small>LKR</small></div><p>95% block interval: ${number(report.confidence_95.basket_mae[0])}–${number(report.confidence_95.basket_mae[1])}</p></div><div class="stat-card"><div class="stat-title">Nominal 80% interval · development coverage</div><div class="stat-value">${number(range.coverage*100,1)}<small>%</small></div><p>${report.interval_guard_passed?'Passed':'Failed'} the 75% minimum coverage guard</p></div></div><p><strong>Best observed candidate:</strong> ${escape(label(best))}. Its improvement interval is ${number(report.best_observed_confidence_95.gain[0]*100,1)}% to ${number(report.best_observed_confidence_95.gain[1]*100,1)}%. These development results were used for selection.</p><div class="table-scroll"><table><caption>All fixed research candidates, ordered by development basket error</caption><thead><tr><th>Candidate</th><th>Basket MAE · LKR</th><th>Improved folds</th><th>Qualified</th></tr></thead><tbody>${Object.entries(report.candidates).sort((a,b)=>a[1].basket_mae-b[1].basket_mae).map(([id,m])=>`<tr><td>${escape(label(id))}</td><td>${number(m.basket_mae)}</td><td>${report.selection.guards[id]?.improved_folds??'Baseline'}</td><td>${report.selection.guards[id]?.qualified?'Yes':id===selected?'Selected baseline':'No'}</td></tr>`).join('')}</tbody></table></div><h3>Intervals and market conditions</h3><p>Relative joint-residual coverage: ${number(report.interval_methods.relative.coverage*100,1)}%; additive coverage: ${number(report.interval_methods.additive.coverage*100,1)}%. Quarter and volatility diagnostics, confidence intervals and frozen settings are in the full report.</p><p><strong>Historical checks:</strong> the 2025 and early-2026 outcomes have been inspected previously. They are exploratory checks, not fresh confirmation. New uninspected outcomes are required before promotion.</p><a class="text-link" href="./data/research.json" download>Download full research results ↗</a><p class="small muted">${escape(report.run_id)} · 2,000 bootstrap draws · 14-day calendar blocks</p>`;
 }catch(error){el.textContent=error.message;researchPromise=null;}
}

function renderSources(){
  const snapshot=state.snapshot,coverage=snapshot.coverage;
  $('#source-status-cards').innerHTML=`<div class="stat-card"><div class="stat-title">Historical price history ends</div><div class="stat-value" style="font-size:22px">${formatDate(coverage.end,false)}<small>2026</small></div><p>Historical replay · current forecasts withheld</p></div><div class="stat-card"><div class="stat-title">Retained source price quotes</div><div class="stat-value">${number(coverage.retained_valid)}</div><p>${number(coverage.retained_rows)} rows including missing reports</p></div><div class="stat-card"><div class="stat-title">Primary-source quotes checked</div><div class="stat-value">${coverage.primary_quotes_checked}</div><p>${coverage.corrections} corrections · sample audit only</p></div>`;
  $('#price-coverage-description').textContent=`The full package has ${number(coverage.package_rows)} rows. This build retains ${number(coverage.retained_rows)} Dambulla wholesale records from ${formatDate(coverage.start)} through ${formatDate(coverage.end)}, including ${coverage.retained_rows-coverage.retained_valid} missing quotes. Missing outcomes are not interpolated.`;
  $('#weather-description').textContent=`The experiment ${snapshot.evaluation.weather_available?'successfully evaluated weather variants alongside price-only models':'used price-only models because complete weather features were unavailable'}. Selected method: ${methodNames[snapshot.model.selected]}. Weather status: ${snapshot.model.weather_status.toLowerCase()}.`;
  $('#corrections-table').innerHTML=snapshot.corrections.map(r=>`<tr><td>${formatDate(r.date)}</td><td>${names[r.commodity]}</td><td>${number(r.original_price)}</td><td>${number(r.price)}</td><td><a href="${escape(r.source_url)}" target="_blank" rel="noreferrer">CBSL wholesale table ↗</a></td></tr>`).join('');
}

async function fetchAPI(path,options={}){
  const response=await fetch('/api/v1/'+path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  if(!response.ok){let message='The local service could not complete this request.';try{const body=await response.json();message=typeof body.detail==='string'?body.detail:message;}catch{}throw new Error(message);}
  return response.status===204?null:response.json();
}
async function loadSaved(){
  if(state.api)state.saved=(await fetchAPI('baskets')).map(validateRecord);
  else state.saved=await browserStore.list();
  state.storageBlocked=!!browserStore.recovery;
  $('#saved-warning').classList.toggle('hidden',!state.storageBlocked);
  $('#recover-browser').classList.toggle('hidden',!state.storageBlocked);
  if(state.storageBlocked)$('#saved-warning').textContent='Some legacy saved data is unreadable. Its original value is preserved. Download the original data, or open recovery to keep valid plans and archive the unreadable value.';
  $('#saved-count').textContent=state.saved.length;
  updateBackupBatches();
}
function updateBackupBatches(){
  const select=$('#backup-batch');if(!select)return;
  const previous=Number(select.value)||0;
  const batches=backupBatches(state.saved);
  select.innerHTML=batches.map((batch,i)=>`<option value="${i}">Backup ${i+1} of ${batches.length} · ${batch.length} plans</option>`).join('');
  select.value=String(Math.min(previous,batches.length-1));
  select.classList.toggle('hidden',batches.length<=1);
}
async function refreshSavedAfterWrite(message){
  try{await loadSaved();renderSaved();toast(message);}
  catch{toast(message+' The saved list could not refresh. Reload to retry; do not repeat the save.');}
}
async function saveCurrent(name){
  if(!updateEstimate())return;
  const button=$('#save-form button[type="submit"]');button.disabled=true;
  try{
    if(state.api)await fetchAPI('baskets',{method:'POST',body:JSON.stringify({name,issue_date:state.issueDate,quantities:state.quantities,budget:state.budget,replay:true})});
    else{
      const contract=await identify({...state.result,exported_at:new Date().toISOString()});
      const record={id:crypto.randomUUID(),name,saved_at:new Date().toISOString(),contract};
      await browserStore.save(record);
    }
    $('#save-dialog').close();await refreshSavedAfterWrite('Basket saved with its issue date and source version.');
  }catch(error){toast(error.message);}finally{button.disabled=false;}
}
function renderSaved(){
  const el=$('#saved-baskets');
  if(!state.saved.length){el.innerHTML=`<div class="empty-state"><div class="empty-illustration">✳</div><h1>A little planning goes a long way.</h1><p>Save your first basket to keep its quantities, estimate and source version together. When an observed outcome is available, you’ll see the comparison here.</p><a href="#planner" class="button primary">Build your first basket ↗</a></div>`;return;}
  el.innerHTML='<div class="saved-grid">'+state.saved.map(record=>{
    const contract=record.contract,actual=actualBasket(state.snapshot,contract),error=actual===null?null:contract.estimate-actual,sourceMatch=contract.source_hash===state.snapshot.source_hash;
    const outcome=!sourceMatch?'Source version differs from this workspace. Use the exported record for the original estimate.':actual===null?'The full seven-day outcome is not available in this source snapshot.':`Observed weekly benchmark: <strong>${money(actual)}</strong><br>Estimate ${error>=0?'above':'below'} outcome by ${money(Math.abs(error))} · ${actual>=contract.interval[0]&&actual<=contract.interval[1]?'within':'outside'} the saved range.`;
    return `<article class="saved-card"><div class="saved-card-header"><div><h2>${escape(record.name)}</h2><p class="saved-date">Replay issued ${formatDate(contract.issue_date)} · saved ${formatDate(record.saved_at.slice(0,10))}</p></div><button class="icon-button" data-delete="${escape(record.id)}" aria-label="Delete ${escape(record.name)}">${icon('trash')}</button></div><div class="saved-amount"><span>LKR</span>${number(contract.estimate)}</div><p class="saved-range">Nominal 80% range · ${money(contract.interval[0])} – ${money(contract.interval[1])}</p><div class="saved-quantities">${commodities.map(c=>`<span>${names[c]} ${number(contract.quantities[c],2)} kg</span>`).join('')}</div><div class="saved-outcome">${outcome}</div><div class="saved-card-actions"><button class="button secondary" data-load="${escape(record.id)}">Open in planner ↗</button><button class="text-button" data-export="${escape(record.id)}">Export JSON ${icon('download')}</button></div><div class="saved-source">Historical replay · ${escape(contract.model_version)} · ${escape(contract.contract_id||record.id)}</div></article>`;
  }).join('')+'</div>';
  $$('[data-load]',el).forEach(button=>button.addEventListener('click',()=>{
    const record=state.saved.find(r=>r.id===button.dataset.load),contract=record.contract;
    if(!state.snapshot.forecasts.some(r=>r.date===contract.issue_date)){toast('This date is unavailable in the current snapshot. Export the saved record instead.');return;}
    state.issueDate=contract.issue_date;state.quantities={...contract.quantities};state.budget=contract.budget;$('#issue-date').value=state.issueDate;$('#budget').value=state.budget??'';renderRows();updateEstimate();plannerChart();location.hash='planner';
    if(contract.source_hash!==state.snapshot.source_hash)toast('Recalculated using the current snapshot. Your saved record remains unchanged.');
  }));
  $$('[data-delete]',el).forEach(button=>button.addEventListener('click',()=>{state.deleteId=button.dataset.delete;$('#delete-dialog').showModal();}));
  $$('[data-export]',el).forEach(button=>button.addEventListener('click',()=>{const record=state.saved.find(r=>r.id===button.dataset.export);download(`marketbudget-${record.contract.issue_date}-${record.id.slice(0,8)}.json`,JSON.stringify(record,null,2));toast('Saved record exported.');}));
}

function route(){
  if(!state.snapshot)return;
  const requested=location.hash.slice(1)||'planner',view=['planner','prices','saved','performance','sources'].includes(requested)?requested:'planner';
  $$('.view').forEach(el=>el.classList.toggle('hidden',el.id!=='view-'+view));
  $$('.nav-link').forEach(el=>{el.classList.toggle('active',el.dataset.view===view);if(el.dataset.view===view)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
  const titles={planner:'Basket planner',prices:'Price explorer',saved:'Saved baskets',performance:'Model performance',sources:'Data & methodology'};
  $('#breadcrumb-current').textContent=titles[view];document.title=`${titles[view]} · MarketBudget`;
  if(view==='prices')renderPrices();if(view==='saved')renderSaved();if(view==='performance')renderPerformance();if(view==='sources')renderSources();
  window.scrollTo({top:0,behavior:'instant'});
}

function bind(){
  window.addEventListener('hashchange',route);
  $('#issue-date').addEventListener('change',()=>{state.issueDate=$('#issue-date').value;renderRows();updateEstimate();plannerChart();});
  $('#basket-form').addEventListener('submit',event=>{event.preventDefault();if(updateEstimate())toast('Estimate updated for your basket.');});
  $('#budget').addEventListener('input',updateEstimate);
  $('#reset-basket').addEventListener('click',()=>{state.quantities={beans:20,carrot:30,tomato:20};state.budget=20000;$('#budget').value=20000;renderRows();updateEstimate();toast('Reference basket restored.');});
  $('#how-button').addEventListener('click',()=>$('#info-dialog').showModal());
  $$('dialog').forEach(dialog=>{
    $$('.dialog-close,.dialog-done',dialog).forEach(button=>button.addEventListener('click',()=>dialog.close()));
    dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  });
  $('#save-basket').addEventListener('click',()=>{if(!updateEstimate())return;$('#basket-name').value='Weekly basket · '+formatDate(state.issueDate,false);$('#save-dialog').showModal();$('#basket-name').focus();$('#basket-name').select();});
  $('#save-form').addEventListener('submit',event=>{event.preventDefault();const name=$('#basket-name').value.trim();if(!name){$('#basket-name').setCustomValidity('Enter a name for this basket.');$('#basket-name').reportValidity();return;}$('#basket-name').setCustomValidity('');saveCurrent(name);});
  $('#basket-name').addEventListener('input',()=>$('#basket-name').setCustomValidity(''));
  $('#export-basket').addEventListener('click',async()=>{if(!updateEstimate())return;try{const contract=await identify({...state.result,exported_at:new Date().toISOString()});download(`marketbudget-${state.issueDate}.csv`,csvContract(contract),'text/csv');toast('Dated estimate exported as CSV.');}catch{toast('Export could not be prepared. Please try again.');}});
  $('#confirm-delete').addEventListener('click',async()=>{
    const button=$('#confirm-delete');button.disabled=true;
    try{
      if(state.api)await fetchAPI('baskets/'+encodeURIComponent(state.deleteId),{method:'DELETE'});
      else await browserStore.remove(state.deleteId);
      $('#delete-dialog').close();await refreshSavedAfterWrite('Saved basket deleted.');
    }catch(error){toast(error.message);}finally{button.disabled=false;}
  });
  $('#backup-baskets').addEventListener('click',async()=>{
    try{
      if(state.storageBlocked){download('marketbudget-original-saved-data.txt',browserStore.recovery.raw||'');toast('Original stored data exported without alteration.');return;}
      await loadSaved();const batches=backupBatches(state.saved),index=Number($('#backup-batch').value)||0;
      download('marketbudget-baskets-backup-'+(index+1)+'.json',JSON.stringify({schema_version:'1.0',exported_at:new Date().toISOString(),baskets:batches[index]}));toast('Basket backup exported.');
    }catch(error){toast(error.message);}
  });
  $('#recover-browser').addEventListener('click',()=>{$('#recovery-description').textContent=`Recovery will keep ${browserStore.recovery?.records.length||0} readable legacy plans and all existing database plans. The unreadable original will be archived unchanged. No source estimates will be recalculated.`;$('#recovery-dialog').showModal();});
  $('#confirm-recovery').addEventListener('click',async()=>{try{await browserStore.recover();$('#recovery-dialog').close();await refreshSavedAfterWrite('Readable plans recovered; original data archived.');}catch(error){toast(error.message);}});
  $('#restore-baskets').addEventListener('click',()=>$('#backup-file').click());
  $('#backup-file').addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    const button=$('#restore-baskets');button.disabled=true;
    try{
      if(file.size>5*1024*1024)throw new Error('Choose a JSON backup smaller than 5 MB.');
      const payload=JSON.parse(await file.text());
      const backup=payload?.contract?{schema_version:'1.0',baskets:[payload]}:payload;
      mergeBackup(state.saved,backup);
      let result;
      if(state.api)result=await fetchAPI('baskets/import',{method:'POST',body:JSON.stringify(backup)});
      else result=await browserStore.import(backup);
      await refreshSavedAfterWrite(`${result.imported} basket${result.imported===1?'':'s'} restored; ${result.skipped} already saved.`);
    }catch(error){toast(error instanceof SyntaxError?'This file is not valid JSON. No saved baskets were changed.':error.message);}
    finally{button.disabled=false;event.target.value='';}
  });
  $('#price-period').addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;state.priceDays=Number(button.dataset.days);$$('button',$('#price-period')).forEach(b=>b.classList.toggle('active',b===button));renderPrices();});
  $('#price-end').addEventListener('change',renderPrices);
  $('#export-prices').addEventListener('click',()=>{const rows=[['date','beans_LKR_per_kg','carrot_LKR_per_kg','tomato_LKR_per_kg','market','type'],...state.visiblePrices.map(r=>[r.date,r.beans,r.carrot,r.tomato,'Dambulla','Wholesale'])];download('marketbudget-visible-price-history.csv',safeCSV(rows),'text/csv');});
  $('#evaluation-period').addEventListener('change',renderPerformance);
}

async function start(){
  hydrateIcons();
  try{
    const runtimeResponse=await fetch('./runtime.json',{cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(!runtimeResponse.ok)throw new Error('The application runtime is unavailable. Retry without switching storage.');
    const runtime=await runtimeResponse.json();
    if(!['api','browser'].includes(runtime.storage)||!runtime.snapshot_sha256)throw new Error('Invalid application runtime.');
    state.api=runtime.storage==='api';
    if(state.api){$('#storage-label').textContent='Saved in local SQLite';$('#saved-storage-note').textContent='Baskets are stored by your local API in SQLite. Export a JSON backup for a portable copy.';$('#save-location').textContent='Saved to the local SQLite database.';}else $('#storage-label').textContent='Browser database · IndexedDB';
    const response=await fetch(state.api?'/api/v1/snapshot':'./data/snapshot.json',{cache:'no-store'});
    state.snapshot=await readVerifiedSnapshot(response,runtime.snapshot_sha256);
    state.issueDate=state.snapshot.forecasts.at(-1).date;
    $('#issue-date').innerHTML=[...state.snapshot.forecasts].reverse().map(row=>`<option value="${row.date}">${formatDate(row.date)}</option>`).join('');
    $('#price-end').value=state.issueDate;$('#price-end').min=state.snapshot.history[0].date;$('#price-end').max=state.snapshot.coverage.end;

    try{await loadSaved();}catch(error){$('#saved-warning').textContent='Saved baskets could not be loaded. Retry after restoring the selected storage service. '+error.message;$('#saved-warning').classList.remove('hidden');toast('Saved baskets unavailable. Storage has not changed.');}
    if(!state.api)browserStore.onChange(()=>loadSaved().then(()=>{if(location.hash==='#saved')renderSaved();}).catch(error=>toast(error.message)));
    renderRows();updateEstimate();plannerChart();bind();$('#loading').classList.add('hidden');route();
  }catch(error){console.error('MarketBudget initialization:',error);$('#load-error p').textContent=error.message+' Your selected storage has not changed.';$('#loading').classList.add('hidden');$('#load-error').classList.remove('hidden');}
}
start();
