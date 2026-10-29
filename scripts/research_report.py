"""Publish a standalone research report from the frozen study; no model promotion."""
from pathlib import Path
from html import escape
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,PageBreak,Spacer,Image
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
import make_reports

ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'reports/research/latest.json').read_text());selected=r['selection']['selected'];base=r['selection']['baseline'];best=r['best_observed_candidate']
point=r['candidates'][selected];interval=r['interval_methods'][r['selected_interval_method']]
name=lambda value:value.replace('_',' ').replace('@',' · model weight ')
n=lambda value,d=2:f'{value:,.{d}f}'
best_gain=(1-r['candidates'][best]['basket_mae']/r['candidates'][base]['basket_mae'])*100
out=ROOT/'reports/research'/r['run_id']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.spines.top':False,'axes.spines.right':False})
rows=sorted(r['candidates'].items(),key=lambda item:item[1]['basket_mae'],reverse=True)
fig,ax=plt.subplots(figsize=(9,7),layout='constrained');bars=ax.barh([name(k) for k,v in rows],[v['basket_mae'] for k,v in rows],color=['#315d3f' if k==selected else '#c79558' if k==best else '#c2d2ae' for k,v in rows]);ax.bar_label(bars,labels=[n(v['basket_mae'],0) for k,v in rows],padding=4,fontsize=7);ax.set_xlim(0,max(v['basket_mae'] for k,v in rows)*1.12);ax.set_xlabel('Development basket MAE (LKR); lower is better');ax.set_title('Fixed research comparison · 300 baskets · six chronological folds',loc='left',fontsize=12,pad=15);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True);fig.savefig(out/'candidate_comparison.png',dpi=180);fig.savefig(out/'candidate_comparison.pdf');plt.close(fig)
styles=make_reports.pdf_styles();P=lambda x:Paragraph(x,styles['p']);H=lambda x:Paragraph(x,styles['h']);L=lambda x:Paragraph(x,styles['label']);T=lambda x:Paragraph(x,styles['title'])
def table(rows,widths):
 data=[[Paragraph(escape(str(cell)),ParagraphStyle('cell',fontName='MB-Bold' if i==0 else 'MB',fontSize=7,leading=10,textColor=colors.white if i==0 else colors.HexColor('#4f6244'))) for cell in row] for i,row in enumerate(rows)]
 t=Table(data,colWidths=widths,repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#274e35')),('BACKGROUND',(0,1),(-1,-1),colors.HexColor('#f4f7ed')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dce4d2')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));return t
foldtable=[['Validation','Train through','Calibration','Cal baskets','Validation baskets']]+[[f['id'],f['train_end'],f['calibration_start']+' to '+f['calibration_end'],f['calibration_baskets'],f['validation_baskets']] for f in r['folds']]
sections=[[
 L('MARKETBUDGET 1.2 / RESEARCH ONLY'),T('A stricter forecasting study'),P('This study is separate from the approved buyer-facing replay. The protocol was written before fitting, candidates and rules were fixed, and no model can promote itself into the application.'),
 H('The point-error result'),P(f'The strongest observed candidate was {escape(name(best))}, with a {n(best_gain)}% pooled development basket MAE improvement over {escape(name(base))}. It did not meet the required 10% improvement. No learned candidate passed every guard, so the research selection remains the latest-price baseline.'),
 H('The interval result'),P(f'The selected relative joint-residual range covered {n(interval["coverage"]*100)}% of development outcomes for a nominal 80% range. The additive range covered {n(r["interval_methods"]["additive"]["coverage"]*100)}%. Neither reached the predefined 75% minimum coverage guard. The study is not eligible for promotion.'),
 H('Chronological design'),table(foldtable,[25*mm,30*mm,66*mm,25*mm,26*mm]),Spacer(1,4*mm),P('Six quarterly validation windows cover 2023 Q1–2024 Q2. The preceding quarter is reserved for interval calibration; earlier 2022+ data train the model. Seven-day targets crossing any boundary are purged. Each fold requires at least 30 complete calibration baskets and 30 validation baskets; at least four usable folds are required.'),P('Target: the average observed wholesale point price in issue+1 through issue+7, with at least four quotes per vegetable. Reference basket: 20 kg beans, 30 kg carrots and 20 kg tomatoes. Weather features end seven days before issue.')],
 [L('01 / FIXED CANDIDATES'),T('What was compared'),P('Four baselines: latest price, 28-day observed mean, feasible prior-year weekly price, and an observed-price EWMA with a seven-calendar-day half-life. Four existing LightGBM price/weather pooled/individual families are evaluated at model weights 0.25, 0.50, 0.75 and 1.0, blended with the latest price. This produces 20 candidates. LightGBM complexity settings remain unchanged.'),table([['Candidate','Basket MAE · LKR','Crop guard','Improved folds']]+[[name(k),n(v['basket_mae']),('Pass' if r['selection']['guards'][k]['commodity_guard'] else 'Fail') if k in r['selection']['guards'] else 'Baseline',r['selection']['guards'][k]['improved_folds'] if k in r['selection']['guards'] else '—'] for k,v in sorted(r['candidates'].items(),key=lambda item:item[1]['basket_mae'])],[88*mm,32*mm,25*mm,27*mm]),Spacer(1,3*mm),P('All qualifying candidates are considered before selecting the lowest-error candidate. Qualification requires at least 10% lower pooled basket MAE than the strongest development baseline, no vegetable MAE regression above 5%, and improvement in at least four folds. The baseline is retained if none qualifies.')],
 [L('02 / UNCERTAINTY AND STABILITY'),T('Show the weak spots'),P(f'Selected development basket MAE: LKR {n(point["basket_mae"])} across {point["n"]} baskets. Its 95% block-bootstrap interval is LKR {n(r["confidence_95"]["basket_mae"][0])}–{n(r["confidence_95"]["basket_mae"][1])}. Relative range coverage is {n(interval["coverage"]*100)}%, with a 95% block interval of {n(r["confidence_95"]["coverage"][0]*100)}%–{n(r["confidence_95"]["coverage"][1]*100)}%.'),P(f'The best observed candidate\'s gain interval is {n(r["best_observed_confidence_95"]["gain"][0]*100)}% to {n(r["best_observed_confidence_95"]["gain"][1]*100)}%. It includes no improvement. Results are development selection evidence, not independent confirmation of a winner.'),table([['Segment','Baskets','Basket MAE · LKR','Coverage','Mean width · LKR']]+[[key.replace('_',' '),v['n'],n(v['basket_mae']),n(v['coverage']*100)+'%',n(v['mean_width'])] for key,v in r['segments'].items()],[49*mm,20*mm,37*mm,25*mm,41*mm]),Spacer(1,3*mm),P('Volatility regimes use training-only thresholds of a quantity- and latest-cost-weighted trailing 28-day coefficient of variation. No future prices define a regime. Intervals preserve aligned commodity residuals rather than adding marginal endpoints.'),P(f'Bootstrap: 2,000 resamples, seed 42, shared 14-calendar-day blocks within folds ({r["confidence_95"]["blocks"]} blocks). Overlapping weekly targets remain dependent; these intervals are not conditional-coverage guarantees. Interval methods are ranked by interval score subject to the development coverage guard.')],
 [L('03 / HISTORICAL CHECKS AND HANDOFF'),T('Keep research separate'),table([['Previously inspected period','Baskets','Basket MAE · LKR','Coverage']]+[[period,v['n'],n(v['basket_mae']),n(v['coverage']*100)+'%'] for period,v in r['historical_checks'].items()],[62*mm,27*mm,44*mm,39*mm]),Spacer(1,5*mm),P('The 2025 and early-2026 results were already inspected during previous project work. They are labelled exploratory historical checks. They cannot establish fresh generalization for this study. A new protocol and new uninspected outcomes are required before any model promotion.'),H('Implementation and reproduction'),P('Run python -m marketbudget.research. The immutable run directory contains protocol.json, results.json and development_predictions.csv. The current study is exposed in a separate research panel and through GET /api/v1/research/latest. Research runs never write the approved forecast pointer or published evaluation.'),H('Current limitations'),P('The source series ends on 10 March 2026. The primary-source sample audit is partial, especially 2022. Source publication times and historical weather vintages are unknown. CBSL upstream reuse terms remain unconfirmed. There is no completed buyer pilot, invoice-cost validation or verified savings claim.'),H('Provenance'),P('Study ID: '+r['run_id']),P('Frozen protocol SHA-256: '+r['protocol_sha256']),P('Inputs: vegetablesSriLanka 1.1.0 CBSL-derived Dambulla wholesale observations, retained 2022+; NASA POWER regional proxies. Dataset hashes, code hashes, package versions, folds, parameters and selection rules are preserved in the protocol.'),P('OpenAI Codex assisted in implementation, research execution and reporting. The original submission team should review and own the result. This report documents unsuccessful guards as well as promising comparisons.')],
 [L('04 / RESEARCH FIGURE'),T('All candidate errors'),Image(str(out/'candidate_comparison.png'),width=172*mm,height=134*mm),P('Green: selected baseline. Orange: lowest observed development error. No learned candidate cleared the full qualification rule. The displayed errors share the same complete-basket issue dates within each fold.')]
]
story=[]
for i,section in enumerate(sections):
 if i:story.append(PageBreak())
 story.extend(section)
def footer(canvas,doc):
 canvas.setFont('MB',7);canvas.setFillColor(colors.HexColor('#788a6d'));canvas.drawString(19*mm,12*mm,'MarketBudget · research only · '+r['run_id']);canvas.drawRightString(191*mm,12*mm,str(doc.page))
doc=SimpleDocTemplate(str(ROOT/'docs/MarketBudget-Research-Report.pdf'),pagesize=(210*mm,297*mm),leftMargin=19*mm,rightMargin=19*mm,topMargin=17*mm,bottomMargin=23*mm,title='MarketBudget research study',author='MarketBudget · AI-assisted research implementation');doc.build(story,onFirstPage=footer,onLaterPages=footer)
md=f'''# MarketBudget 1.2 research study

**Research only. No model promotion.** Run `{r['run_id']}`; frozen protocol SHA-256 `{r['protocol_sha256']}`.

Six chronological validation quarters (2023 Q1–2024 Q2) evaluated 20 fixed candidates on {point['n']} complete reference baskets. Earlier 2022+ observations train each fold, the immediately preceding quarter calibrates intervals, and crossing seven-day targets are purged.

The best observed candidate, **{best}**, reduced development basket MAE by **{n(best_gain)}%**. Its 95% gain interval is **{n(r['best_observed_confidence_95']['gain'][0]*100)}% to {n(r['best_observed_confidence_95']['gain'][1]*100)}%**. It did not meet the 10% improvement guard. No learned candidate passed every guard; the research selection is **{selected}**.

The relative nominal 80% range covered **{n(interval['coverage']*100)}%** of development outcomes; the additive range covered **{n(r['interval_methods']['additive']['coverage']*100)}%**. Neither met the 75% minimum. The approved application's original replay and evaluation are unchanged.

| Candidate | Basket MAE (LKR) | Crop guard | Improved folds |
| --- | ---: | --- | ---: |
'''
for k,v in sorted(r['candidates'].items(),key=lambda item:item[1]['basket_mae']):
 g=r['selection']['guards'].get(k);md+=f"| {k} | {n(v['basket_mae'])} | {('pass' if g['commodity_guard'] else 'fail') if g else 'baseline'} | {g['improved_folds'] if g else '—'} |\n"
md+='\nThe 2025/early-2026 comparisons are previously inspected exploratory checks. New uninspected outcomes and a separately frozen study are required before promotion. Full quarter/volatility diagnostics, 2,000-draw block uncertainty intervals and all settings are in results.json. Reproduce with `python -m marketbudget.research`. No paid inference API or automated model promotion is involved.\n'
(ROOT/'docs/RESEARCH_REPORT.md').write_text(md)
print('Generated research PDF, Markdown and standalone figure')
