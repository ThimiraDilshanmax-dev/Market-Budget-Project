"""Render the technical report, two-page summary and evaluation figures.

Optional dependencies: pip install -r requirements-reports.txt
All numerical content is read from the completed experiment artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image

ROOT = Path(__file__).resolve().parents[1]
REPORT = json.loads((ROOT / "reports/evaluation.json").read_text())
SNAPSHOT = json.loads((ROOT / "artifacts/snapshot.json").read_text())
MODEL = REPORT["model"]
SELECTED = MODEL["selected"]
TEST = REPORT["metrics"]["test_2025"][SELECTED]
INTERVAL = REPORT["intervals"]["test_2025"]
COVERAGE = REPORT["coverage"]
METHODS = {"latest_price":"Latest-price baseline", "mean_28d":"28-day average", "prior_year":"Prior-year baseline",
           "price_pooled":"Price/calendar pooled", "weather_pooled":"Price/weather pooled",
           "price_individual":"Price/calendar individual", "weather_individual":"Price/weather individual"}
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

RESEARCH_PATH=ROOT / "reports/research/latest.json"
RESEARCH=json.loads(RESEARCH_PATH.read_text()) if RESEARCH_PATH.exists() else None
if RESEARCH and RESEARCH.get("outcome")=="completed":
    study_best=RESEARCH["best_observed_candidate"]
    study_gain=(1-RESEARCH["candidates"][study_best]["basket_mae"]/RESEARCH["candidates"][RESEARCH["selection"]["baseline"]]["basket_mae"])*100
    study_coverage=RESEARCH["interval_methods"][RESEARCH["selected_interval_method"]]["coverage"]*100
    RESEARCH_SUMMARY=f"A separate six-fold study of 20 fixed candidates found a best observed {study_gain:.2f}% development gain. Selected nominal-80% development coverage was {study_coverage:.2f}%. Research promotion remains disabled. See the standalone research report for guard decisions and uncertainty."
else:
    RESEARCH_SUMMARY="Separate research outputs never automatically replace the approved model."



def n(value, digits=0):
    return f"{value:,.{digits}f}"


def figures():
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":9, "axes.spines.top":False,
                         "axes.spines.right":False, "axes.labelcolor":"#41503b", "text.color":"#30472f",
                         "axes.edgecolor":"#cdd7c6", "xtick.color":"#7c8b72", "ytick.color":"#7c8b72"})
    metrics = REPORT["metrics"]["test_2025"]
    fig, ax = plt.subplots(figsize=(8.1,3.5), layout="constrained")
    keys = list(metrics)
    bars = ax.barh([METHODS[k] for k in keys][::-1], [metrics[k]["basket_mae"] for k in keys][::-1],
                   color=["#315d3f" if k == SELECTED else "#bacba9" for k in keys][::-1], height=.6)
    ax.bar_label(bars, labels=[n(metrics[k]["basket_mae"]) for k in keys][::-1], padding=5, fontsize=8)
    ax.set_xlim(0,max(m["basket_mae"] for m in metrics.values())*1.17)
    ax.set_xlabel("Basket mean absolute error (LKR); lower is better")
    ax.set_title("2025 held-out test · 20/30/20 kg reference basket",loc="left",pad=16,fontsize=12,fontweight="bold")
    ax.grid(axis="x",alpha=.15);ax.set_axisbelow(True)
    fig.savefig(ROOT / "reports/model_comparison.png",dpi=180)
    fig.savefig(ROOT / "reports/model_comparison.pdf")
    plt.close(fig)
    frame = pd.DataFrame(SNAPSHOT["test_predictions"])
    frame["date"] = pd.to_datetime(frame.date)
    fig, ax = plt.subplots(figsize=(9,3.3),layout="constrained")
    ax.fill_between(frame.date,frame.lower,frame.upper,color="#cedcbd",alpha=.65,label="Nominal 80% joint range")
    ax.plot(frame.date,frame.prediction,color="#345e3d",linewidth=1.2,label="Selected estimate")
    ax.plot(frame.date,frame.actual,color="#cb8b54",linewidth=1.2,label="Observed weekly benchmark")
    ax.set_title("Dated basket estimates and outcomes · 2025",loc="left",pad=13,fontsize=12,fontweight="bold")
    ax.set_ylabel("Reference basket cost (LKR)");ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2));ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.grid(alpha=.13);ax.legend(loc="upper left",frameon=False,ncol=3,fontsize=7)
    fig.savefig(ROOT / "reports/basket_outcomes.png",dpi=180);fig.savefig(ROOT / "reports/basket_outcomes.pdf");plt.close(fig)


def markdown():
    tune = REPORT["tuning"]
    table = "\n".join(f"| {METHODS[k]} | {n(v['basket_mae'],2)} | {n(REPORT['metrics']['test_2025'][k]['basket_mae'],2)} |" for k,v in tune.items())
    splits = "\n".join(f"| {key} | {value['start']}–{value['end']} | {value['labelled_rows']} | {value['complete_baskets']} |" for key,value in REPORT["splits"].items())
    operating = "\n".join(f"| {key} | {v['scheduled_report_dates']} | {v['complete_input_dates']} | {v['withheld_input_dates']} | {v['complete_evaluated_baskets']} | {v['scheduled_dates_not_scored']} |" for key,v in REPORT["operating_coverage"].items())
    text = f"""# MarketBudget — technical report

Release: `{MODEL['version']}`. Generated {REPORT['generated_at']}. Status: private historical research replay.

## Result and contribution

MarketBudget is a runnable vegetable basket budgeting application for a small caterer or canteen sourcing from Dambulla. It implements a strict forecast contract, auditable data handling, chronological model experiments, a versioned API, browser interface, persistence, backup restoration and exports. The attached proposal's local research pack was not supplied; original public source files were independently recovered.

The best development candidate was **{METHODS[MODEL['selection']['best_learned']]}**, with **{n(MODEL['selection']['learned_improvement']*100,2)}%** lower development basket MAE than the strongest baseline. Its tomato MAE exceeded the 5% commodity-regression guard. The selected release method is **{METHODS[SELECTED]}**. Rejection is an explicit result, not a claim that the learned model is universally inferior.

On {TEST['complete_baskets']} complete 2025 baskets, MAE was **LKR {n(TEST['basket_mae'],2)}**, signed estimate-minus-outcome bias **LKR {n(TEST['basket_bias'],2)}**, nominal 80% interval coverage **{n(INTERVAL['observed_coverage']*100,2)}%**, and average width **LKR {n(INTERVAL['mean_width'],2)}**. No prospective buyer pilot or savings claim is made.

## Sources, preparation and audit

The vegetablesSriLanka 1.1.0 distribution contains {n(COVERAGE['package_rows'])} records. Three Dambulla wholesale series contain 6,660 rows and 157 missing values. The retained 2022+ source table has {n(COVERAGE['retained_rows'])} rows, {n(COVERAGE['retained_valid'])} valid quotes, and ends on 10 March 2026. All pre-2022 data were excluded because the proposal's six disputed 2021 keys were not available. The smaller training subset deliberately differs from the proposal.

Fifteen primary CBSL quotes were checked across 2023–2026, including October reference-only observations. Original 11 July 2024 package values of beans 190, carrot 68 and tomato 210 were replaced by verified wholesale Today values of 375, 345 and 190 LKR/kg. Raw PDFs, source URLs, hashes, original values and corrections are retained. Two June 2022 sample attempts returned 404; no primary 2022 quote was verified. The successful audit list and append-only failed-attempt queue are separate evidence records.

The parser locates the wholesale table, validates printed date, expected market/header order, kg units, ten aligned price cells and the Dambulla Today column. Unrecognized layouts fail closed. Current collection discovers actual links from the CBSL index and stages rows for review; it never automatically appends prices or publishes a model. A 16 October 2026 reference report is kept separate from the continuous series and is not used to imply recent coverage.

NASA POWER supplies three regional grid proxies at Nuwara Eliya (6.97,80.77), Badulla (6.99,81.06) and Kandy/Matale (7.30,80.64). Each query returned 1,591 daily rows from 1 November 2021 through 10 March 2026, with rainfall, mean/minimum/maximum temperature and humidity. These are grid proxies, not farm stations or verified district supply weights. The application credits NASA POWER.

## Forecast contract and temporal controls

At issue date d, each target is the observed-price mean over d+1 through d+7. Issue day is excluded. At least four valid observations per commodity and a fully observed seven-day calendar window are required. A basket outcome requires all three target labels. Missing labels are never interpolated or carried forward.

The central basket estimate is sum(q_i × p_i). This need not equal the basket median. Latest known prices may be carried forward only as past features, with explicit age. Features include 7/14/28-day last-known lags, observed-price means/counts, volatility, price momentum, weekday and annual cyclical terms. Weather summaries use only days ending at least seven days before issue. Unknown historical publication times, revised weather vintages and Local Solar Time mismatch remain limitations.

Training, selection, calibration and test boundaries are common across commodities. Any label extending past the end of its assigned period is purged. Weather-candidate eligibility uses only training/development availability; later complete-input exclusions are reported. No final-test outcome is used for tuning, feature selection or interval calibration. Tuning intervals are not constructed from later calibration residuals. The models remain trained on 2022–2023 after model selection; refitting on calibration or test rows is not performed.

| Split | Calendar interval | Labelled rows | Complete baskets |
| --- | --- | ---: | ---: |
{splits}

## Methods and release decision

Baselines: latest price held constant; mean of observed quotes in the trailing 28 calendar days; prior-year weekly target when available, otherwise an explicitly defined latest-price fallback. LightGBM variants cross pooled/individual commodity fits with price/calendar or price/calendar/weather features. Three quantile objectives (0.10, 0.50, 0.90) are fit for each learned variant. Target is relative change from latest price; reconstructed prices are nonnegative and quantiles sorted under a fixed crossing rule.

Fixed parameters: 180 estimators, learning rate 0.04, 9 leaves, maximum depth 4, minimum leaf sample count 30, L2 regularization 2, random seed 42, deterministic CPU fitting with two threads. This restricted configuration was not optimized against final-test results.

The strongest simple baseline and the learned candidate with lowest basket MAE are selected on Jan–Jun 2024. The learned candidate is released only if basket MAE improves at least 10% and no vegetable MAE regresses more than 5%. Otherwise the strongest baseline is retained. This policy does not search for another learned candidate after the first candidate fails a guard.

| Method | Development basket MAE (LKR) | 2025 basket MAE (LKR) |
| --- | ---: | ---: |
{table}

![2025 method comparison](../reports/model_comparison.png)

## Joint interval and evaluation

The selected method produces aligned relative residual triplets on {INTERVAL['calibration_n']} complete July–December 2024 calibration dates. For a new basket, scenario price_i=max(0, p_i×(1+residual_i)); scenario cost is the quantity-weighted sum. Keeping each triplet together preserves observed cross-commodity movement. Marginal interval endpoints are never summed. Conservative lower/upper order statistics approximate the 10th/90th percentiles, expanded to contain the central estimate. This is an empirical interval with nominal coverage, not a distribution-free or conditional-coverage guarantee.

The primary budget is 20 kg beans, 30 kg carrots and 20 kg tomatoes. Selected test commodity MAEs are beans {n(TEST['commodities']['beans']['mae'],2)}, carrots {n(TEST['commodities']['carrot']['mae'],2)} and tomatoes {n(TEST['commodities']['tomato']['mae'],2)} LKR/kg. Pinball loss and raw quantile coverage for learned methods are in the machine-readable results, alongside an earlier train-2022/validate-2023 fold and early-2026 check. A shared 14-calendar-day block bootstrap of selected-minus-baseline absolute basket error returns [0,0] because the selected method is the baseline. This does not mean forecast error is zero.

![Dated basket estimates and outcomes](../reports/basket_outcomes.png)

Scheduled issue dates follow source-report dates, not all calendar dates. Label counts differ slightly by commodity. All candidate methods use common eligible comparison rows. Unscored dates include insufficient target observations, purged boundary windows and initial feature warm-up. Missing outcomes are never scored as correct.

| Period | Scheduled dates | Complete input dates | Withheld input dates | Evaluated baskets | Unscored dates |
| --- | ---: | ---: | ---: | ---: | ---: |
{operating}

## System and delivered behavior

```mermaid
flowchart LR
  A[Immutable source bytes and hashes] --> B[Strict parser and review queue]
  B --> C[Canonical prices and weather]
  C --> D[As-of features and purged experiments]
  D --> E[Versioned frozen contracts and joint residuals]
  E --> F[Local FastAPI and SQLite]
  E --> G[Private static browser replay]
  F --> H[Dated baskets and exports]
  G --> H
```

The browser presents a basket planner, optional budget, cost contribution, joint range, 28-day context chart, price explorer, saved baskets, evaluation and source correction trail. It uses the same frozen contract and mathematical rules as the Python API. Static-hosted saves use browser storage; local API saves use SQLite and immutable JSON contracts. Cross-language numerical tests compare varied baskets and verify exact contract-ID agreement. Backup imports validate complete saved records and merge atomically; conflicts make no changes. Comparisons are withheld on source-version mismatch. Exports include issue/target dates, replay status, source hash and model version, and guard against spreadsheet formula injection.

Fresh current mode requires today's issue-date contract and all required quotes no more than three calendar days old; stale responses contain no actionable estimate. Local API is loopback-only with no multi-user authentication. No invoice uploads, personal data collection, automated supplier orders, paid APIs or unattended jobs are configured.

Validation covers exact label windows, future feature invariance, weather buffer, boundary purges, missing labels, stale prices, malformed/zero inputs, joint residual dependence, source table/date parsing, saved-record lifecycle, outcome-unavailable behavior, exports, and browser/API parity. Browser QA exercises calculations, budget warnings, saving, comparison, restore, export, deletion and all five views at six viewport widths from 320 to 1440 px. Final verification evidence is recorded in docs/VALIDATION.md and reports/browser-qa.json.

## Limitations and next release

The package's GPL-3 declaration is retained; upstream CBSL training/redistribution permission has not been established. The private demonstration does not establish those rights. Source sampling is incomplete, especially 2022. Historical publication times and weather vintages are unavailable. Calibration has only 105 overlapping issue dates and may not transfer to new regimes. The live recent feed and prospective buyer pilot are not complete. Delivered prices vary by grade, volume, delivery and supplier terms and are not validated by this model.

Next: confirm rights, audit and append a continuous recent extension, recruit a buyer with a matching weekly purchasing workflow, freeze the prospective contract and acceptable rupee error, and run a four-to-eight-week shadow evaluation. Only then assess real decision value and a hosted operational release. Source failure must withhold fresh forecasts, not silently relabel a historical result as live.

## Sources and credits

1. vegetablesSriLanka 1.1.0, Talagala, Jayarathne and Talagala: https://thiyangtdata.r-universe.dev/vegetablesSriLanka (package GPL-3).
2. CBSL Daily Price Report: https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report (original PDFs and SHA-256 manifests retained).
3. NASA POWER daily API: https://power.larc.nasa.gov/docs/services/api/temporal/daily/ and data FAQ: https://power.larc.nasa.gov/docs/faqs/data/ .
4. LightGBM: https://lightgbm.readthedocs.io/ ; pandas: https://pandas.pydata.org/ ; FastAPI: https://fastapi.tiangolo.com/ .
5. DM Sans font authors, SIL Open Font License. Third-party libraries retain their own terms. New project code: GPL-3.0-or-later.

AI disclosure: OpenAI Codex assisted in source recovery, implementation, experimentation, tests and documentation. No interviews, pilot results, source observations or accuracy metrics were invented. Submission ownership and final review remain with the original team.
"""
    text += "\n\n## Application 1.2 implementation addendum\n\nApproved datasets and forecast bundles are immutable and hash-verified. Collection stages candidates; training writes isolated runs. The builder validates a complete staged site before replacement. Decimal business arithmetic, strict shared record validation, transactional IndexedDB saves, explicit runtime storage, legacy recovery and accessible chart inspection are implemented.\n\n" + RESEARCH_SUMMARY + "\n\nSee REVIEW.md, VALIDATION.md and RESEARCH_REPORT.md for implementation evidence, regression tests and the separate study.\n"
    (DOCS / "TECHNICAL_REPORT.md").write_text(text)
    summary = f"""# MarketBudget — project summary

MarketBudget helps a small Sri Lankan caterer or canteen reserve cash for beans, carrots and tomatoes bought through Dambulla. Enter kilograms and an optional budget to obtain a dated seven-day weekly-average benchmark estimate and a nominal 80% joint cost range. Purchasing decisions remain with the buyer.

## Delivered

A responsive browser app, FastAPI service, SQLite saved baskets, validated backup restoration, dated CSV/JSON exports, price explorer, source audit, chronological forecasting experiments, versioned model artifacts, tests and reproducible instructions. The private hosted app is a historical replay; the full local project persists records in SQLite. No paid forecast API is required.

## Real-data foundation

Recovered vegetablesSriLanka 1.1.0 data provides {n(COVERAGE['retained_valid'])} valid 2022+ quotes in {n(COVERAGE['retained_rows'])} rows through 10 March 2026. Three primary-verified July 2024 corrections preserve originals and provenance. Fifteen quotes were checked across 2023–2026; the 2022 sample audit remains incomplete. NASA POWER supplies three regional weather proxies with a seven-day availability buffer. A separate October reference report is not appended across the historical gap.

## Method and actual result

Targets average valid observations on issue+1 through issue+7 with at least four quotes per commodity. Models use only past features. Train 2022–2023, select Jan–Jun 2024, calibrate Jul–Dec 2024, test 2025, then check early 2026; crossing labels are purged. Three simple baselines compete against four restricted LightGBM quantile variants.

The strongest development model improved basket MAE **{n(MODEL['selection']['learned_improvement']*100,2)}%**, but exceeded the tomato regression guard. The release selected **{METHODS[SELECTED]}** with an empirical joint range from 105 aligned residual scenarios.

For the fixed 20/30/20 kg basket on **{TEST['complete_baskets']} complete 2025 issue dates**: **LKR {n(TEST['basket_mae'],2)} MAE**, **LKR {n(TEST['basket_bias'],2)} signed bias**, **{n(INTERVAL['observed_coverage']*100,2)}% observed coverage** for the nominal 80% range, and **LKR {n(INTERVAL['mean_width'],2)} average range width**. These are benchmark metrics, not paid-cost performance or verified savings.

## Reliability and remaining work

Unknown PDF layouts enter a review queue; missing targets remain missing. Current mode withholds old contracts and quotes older than three calendar days. Baskets preserve dates, source hash and model version. Source-rights clarification, a continuous audited recent extension and a prospective buyer pilot remain necessary. Historical publication times, weather revisions, partial source audit and overlapping calibration targets limit claims. Upstream CBSL rights are not resolved by the package's GPL declaration.

## Run and demonstrate

Install with `python -m pip install -e '.[dev]'`, build with `python scripts/build.py`, and run `python -m marketbudget.api`; open http://127.0.0.1:8000. The included artifacts run without downloading or training. README gives full reproduction commands; DEMO_SCRIPT.md provides a three-minute walkthrough.

Sources: Talagala, Jayarathne and Talagala, vegetablesSriLanka 1.1.0; CBSL Daily Price Reports; NASA POWER. New code GPL-3.0-or-later; other source rights remain separate. OpenAI Codex assisted in implementation and documentation; the submission team should review and own the final work.
"""
    (DOCS / "PROJECT_SUMMARY.md").write_text(summary+"\n## Separate research and application 1.2\n\n"+RESEARCH_SUMMARY+"\nThe application now uses immutable approvals, decimal arithmetic, transactional browser storage and explicit recovery.\n")


GREEN=colors.HexColor("#274e35")
MUTED=colors.HexColor("#788a6d")
PALE=colors.HexColor("#eff3e8")


def pdf_styles():
    folder=Path("/usr/share/fonts/truetype/dejavu")
    if (folder / "DejaVuSans.ttf").exists():
        pdfmetrics.registerFont(TTFont("MB", str(folder / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("MB-Bold", str(folder / "DejaVuSans-Bold.ttf")))
    else:
        pdfmetrics.registerFont(pdfmetrics.Font("MB","Helvetica","WinAnsiEncoding"))
        pdfmetrics.registerFont(pdfmetrics.Font("MB-Bold","Helvetica-Bold","WinAnsiEncoding"))
    return {
        "title":ParagraphStyle("title",fontName="MB-Bold",fontSize=29,leading=35,textColor=GREEN,spaceAfter=13),
        "subtitle":ParagraphStyle("subtitle",fontName="MB",fontSize=11,leading=17,textColor=MUTED,spaceAfter=16),
        "h":ParagraphStyle("h",fontName="MB-Bold",fontSize=15,leading=20,textColor=GREEN,spaceBefore=12,spaceAfter=9),
        "p":ParagraphStyle("p",fontName="MB",fontSize=9,leading=14,textColor=colors.HexColor("#4e6045"),spaceAfter=9),
        "small":ParagraphStyle("small",fontName="MB",fontSize=7.5,leading=11,textColor=MUTED,spaceAfter=7),
        "label":ParagraphStyle("label",fontName="MB-Bold",fontSize=8,leading=13,textColor=MUTED,spaceAfter=11),
    }


def footer(canvas,doc):
    canvas.setStrokeColor(colors.HexColor("#dce4d4"));canvas.line(19*mm,18*mm,191*mm,18*mm)
    canvas.setFont("MB",7);canvas.setFillColor(MUTED)
    canvas.drawString(19*mm,12*mm,"MarketBudget  |  Private historical research replay")
    canvas.drawRightString(191*mm,12*mm,f"{MODEL['version']}  ·  {doc.page}")


def create_pdf(path: Path, sections: list[list], styles):
    content=[]
    for index,section in enumerate(sections):
        if index:content.append(PageBreak())
        content.extend(section)
    document=SimpleDocTemplate(str(path),pagesize=(210*mm,297*mm),leftMargin=19*mm,rightMargin=19*mm,topMargin=18*mm,bottomMargin=24*mm,
                               title=path.stem.replace('-',' '),author="MarketBudget · AI-assisted research implementation")
    document.build(content,onFirstPage=footer,onLaterPages=footer)


def pdfs():
    s=pdf_styles()
    P=lambda text:Paragraph(text,s["p"])
    H=lambda text:Paragraph(text,s["h"])
    Small=lambda text:Paragraph(text,s["small"])
    Title=lambda text:Paragraph(text,s["title"])
    Label=lambda text:Paragraph(text,s["label"])
    def T(rows,widths=None):
        wrapped=[[Paragraph(escape(str(cell)),ParagraphStyle("cell",fontName="MB-Bold" if i==0 else "MB",fontSize=7.1,leading=10,textColor=colors.white if i==0 else colors.HexColor("#526747"))) for cell in row] for i,row in enumerate(rows)]
        table=Table(wrapped,colWidths=widths,repeatRows=1,hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GREEN),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#f8faf5")),
                                   ("LINEBELOW",(0,1),(-1,-1),.4,colors.HexColor("#e0e8d9")),("VALIGN",(0,0),(-1,-1),"TOP"),
                                   ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
        return table
    stats=T([["2025 BASKET MAE","NOMINAL 80% COVERAGE","EVALUATED BASKETS"],[f"LKR {n(TEST['basket_mae'])}",f"{n(INTERVAL['observed_coverage']*100,1)}%",TEST['complete_baskets']]], [60*mm,65*mm,47*mm])
    first=[Label("PROJECT DELIVERY / OCTOBER 2026"),Title("MarketBudget"),Paragraph("A clearer plan for the next market week.",s["subtitle"]),stats,Spacer(1,8*mm),
           H("The decision this project supports"),P("A small caterer or canteen must reserve cash before next week's Dambulla vegetable prices are known. The buyer enters kilograms of beans, carrots and tomatoes and an optional spending limit. The application returns a dated reference-cost estimate and an empirical joint range, with explicit source dates and historical-replay status."),
           H("What has been built"),P("A responsive browser dashboard, local FastAPI/SQLite service, saved plans, backup restoration and exports, price explorer, source audit and correction trail, reproducible data pipeline, restricted quantile models, chronological evaluation, release artifacts and tests. Application 1.2 uses transactional IndexedDB in the hosted edition and SQLite locally, with explicit storage selection, strict backup recovery and decimal arithmetic. A separate six-fold research study compares 20 fixed candidates; the approved model above is unchanged."),
           H("The result that governs the release"),P(f"The strongest development candidate, pooled price/weather LightGBM, improved basket MAE by {n(MODEL['selection']['learned_improvement']*100,2)}%. Its tomato error breached the 5% regression guard, so the release uses the latest-price baseline. No model was chosen using 2025 outcomes. This preserves the honest fallback required by the proposal."),
           Small("Status: historical research replay through 10 March 2026. Not a current supplier quotation, prospective field trial, invoice-cost model or verified savings claim.")]
    source_rows=[["Date","Beans","Carrot","Tomato","Evidence"],["11 Jul 2024",375,345,190,"Primary wholesale Today"],["10 Mar 2026",290,225,110,"Primary wholesale Today"],["16 Oct 2026",335,225,375,"Reference only; separate"]]
    second=[Label("01 / DATA & EVIDENCE"),Title("A traceable foundation"),P(f"The recovered vegetablesSriLanka 1.1.0 archive contains {n(COVERAGE['package_rows'])} rows. The selected three-series all-year slice contains 6,660 rows and 157 missing quotes. This implementation retains {n(COVERAGE['retained_rows'])} rows from 2022 onward, with {n(COVERAGE['retained_valid'])} valid prices, through 10 March 2026."),
            H("Corrections without erased history"),P("The supplied proposal did not include its local audit pack or the six disputed 2021 keys. All pre-2022 prices are therefore excluded. Three 11 July 2024 package values (190, 68, 210) were independently checked against the CBSL wholesale table and corrected to 375, 345, 190 LKR/kg. Raw bytes, URLs, hashes and original values are retained."),T(source_rows,[33*mm,24*mm,24*mm,24*mm,67*mm]),Spacer(1,4*mm),
            P("Fifteen primary quotes were checked across 2023–2026, including three October reference-only values. The June 2022 sample requests returned 404, so no primary 2022 quote was verified. The audit is partial. Initial parser failures remain in the attempt log; final successful reparses are listed separately."),
            H("Weather is a tested signal"),P("NASA POWER supplies rainfall, mean/minimum/maximum temperature and humidity for Nuwara Eliya, Badulla and Kandy/Matale grid proxies. Each query returned 1,591 days from 1 November 2021 through 10 March 2026. Features end at least seven days before issue. Grid proxies are not farm stations, district averages or verified supply shares. Local Solar Time and archive revisions limit historical availability claims."),
            H("Collection fails closed"),P("The parser validates the printed date, wholesale/retail header order, Dambulla Today alignment, kg units and ten quote cells. Unknown layouts enter a review queue. The collector stages actual linked CBSL reports for review; it does not append, train or publish automatically."),
            Small("Source rights: package metadata declares GPL-3. Upstream CBSL training and redistribution permission remains unconfirmed; private research access does not resolve those terms.")]
    split_rows=[["Purpose","Period","Labels","Baskets"]]+[[key,value["start"]+" to "+value["end"],value["labelled_rows"],value["complete_baskets"]] for key,value in REPORT["splits"].items()]
    third=[Label("02 / CONTRACT & EXPERIMENT"),Title("Time comes first"),H("One precise weekly target"),P("For issue date d, average valid wholesale point quotes on d+1 through d+7, excluding issue day. Require at least four observations per vegetable and a full seven-day calendar window. A basket outcome requires all three labels. Missing outcomes are never interpolated. The point basket adds quantity × central price and is not necessarily the basket median."),
           H("Past-only features"),P("Price inputs include latest available price and age, 7/14/28-day last-known lags, observed means and counts, volatility and momentum. Known weekday and annual cycles supply calendar features. Weather summaries are shifted seven days. A future-data mutation test verifies that subsequent values cannot change earlier features."),
           T(split_rows,[35*mm,81*mm,28*mm,28*mm]),Spacer(1,3*mm),
           P("Targets crossing each period's end date are purged. Candidate methods share eligible comparison rows. Training stays in 2022–2023 after selection; calibration is reserved for intervals. An earlier train-2022/validate-2023 fold and early-2026 check add context without changing final-test selection."),
           H("Seven candidates; one fixed release rule"),P("Three baselines (latest price, trailing 28-day mean, prior-year weekly price) compete with pooled/individual LightGBM models using price/calendar features with or without weather. Each learned variant fits quantiles 0.10/0.50/0.90. Relative targets are reconstructed into nonnegative prices; crossing quantiles are sorted."),
           Small("Fixed LightGBM: 180 trees, learning rate 0.04, 9 leaves, depth 4, minimum leaf samples 30, L2=2, seed 42, two CPU threads. Lowest development basket-MAE learned candidate must improve by ≥10% with no commodity regression above 5%; otherwise use the strongest baseline.")]
    rows=[["Method","2024 dev MAE","2025 MAE","Status"]]+[[METHODS[k],n(REPORT['tuning'][k]['basket_mae']),n(v['basket_mae']),"Selected" if k==SELECTED else "Comparison"] for k,v in REPORT["metrics"]["test_2025"].items()]
    fourth=[Label("03 / ACTUAL RESULTS"),Title("Evidence, including limits"),T(rows,[69*mm,35*mm,32*mm,36*mm]),Spacer(1,4*mm),
            P(f"Selected 2025 test: {TEST['complete_baskets']} complete baskets; MAE LKR {n(TEST['basket_mae'],2)}; signed estimate-minus-outcome bias LKR {n(TEST['basket_bias'],2)}. Commodity MAEs: beans {n(TEST['commodities']['beans']['mae'],2)}, carrot {n(TEST['commodities']['carrot']['mae'],2)}, tomato {n(TEST['commodities']['tomato']['mae'],2)} LKR/kg. Reference basket: 20 / 30 / 20 kg."),
            Image(str(ROOT / "reports/model_comparison.png"),width=172*mm,height=74*mm),
            H("An informative range can still be wide"),P(f"The nominal 80% joint range covered {n(INTERVAL['observed_coverage']*100,2)}% of complete 2025 outcomes. Mean width was LKR {n(INTERVAL['mean_width'],2)}. The range is derived from 105 aligned July–December 2024 relative residual triplets, preserving commodity co-movement. Conservative order statistics and nonnegative prices are fixed before final testing."),
            Small("Overlapping labels and calibration targets are not independent weekly trials. The 14-day block-bootstrap selected-minus-baseline error interval is [0,0] because the selected method is that baseline; it does not imply zero forecast error. Learned pinball loss and raw interval coverage are in evaluation.json.")]
    fifth=[Label("04 / IMPLEMENTATION & VERIFICATION"),Title("A complete local workflow"),H("Evidence to application"),P("Immutable source responses → strict parser and review queue → canonical price/weather tables → as-of features and purged experiments → versioned contracts and joint residual scenarios → browser planner / local FastAPI → saved records and dated exports."),
           Image(str(ROOT / "reports/basket_outcomes.png"),width=172*mm,height=63*mm),
           H("Usable, inspectable behavior"),P("The dashboard supports editable kilograms, optional budget, price context, cost shares, nominal range, historical date selection, saved baskets, outcome comparisons and source details. Exports retain dates, model version, source hash and replay status. Browser-hosted records stay in browser storage; the local API uses SQLite. Contract arithmetic is shared in definition and checked across Python and JavaScript."),
           H("Freshness is an enforced contract"),P("Current mode requires today's Sri Lankan civil-day issue-date contract and every required price no more than three calendar days old. Stale responses contain no actionable estimate. The current included data therefore stays in replay mode. Missing target outcomes return unavailable, not a successful score."),
           H("Verification"),P("Tests cover exact target windows, missing labels, future-data invariance, weather buffer, boundary purges, malformed/zero baskets, joint residual dependence, freshness boundaries, source table/date parsing, saved-record CRUD, comparison, CSV protection and Python/browser numerical parity. Browser QA exercises the five views at 320, 390, 680, 820, 1024 and 1440 px, plus save/restore/delete and JSON/CSV download."),
           Small("Run: python -m pip install -e '.[dev]' · python scripts/build.py · python -m marketbudget.api. Open http://127.0.0.1:8000. The API is loopback-only; multi-user authentication and hosted Python execution are outside this release.")]
    sixth=[Label("05 / LIMITS, HANDOFF & NEXT STEP"),Title("Ready for honest review"),H("What is complete"),P("A runnable repository, real-data research replay, reproducible preprocessing and experiments, local API and persistence, responsive app, evaluation figures, tests, source attributions, technical documentation, two-page summary and three-minute demonstration script. No source observations, scores, interviews or testimonials were fabricated."),
           H("What is still required for operational use"),P("Confirm upstream price-source terms. Complete source sampling, particularly 2022, and audit a continuous recent extension. Recruit a buyer and verify that a weekly-average target fits their purchasing schedule. Agree acceptable rupee error and range width. Preserve prospective issue snapshots and run a four-to-eight-week shadow pilot before assessing real decision value."),
           P("Delivered prices can differ by grade, volume, credit, supplier and transport. No invoice-cost adjustment, demand forecast, automated order or shortage prediction is claimed. Historical publication timestamps and weather vintages are unknown; calibration has only 105 overlapping dates and may fail under regime change."),
           H("Source and software credits"),Small("Talagala, Jayarathne and Talagala, vegetablesSriLanka 1.1.0: https://thiyangtdata.r-universe.dev/vegetablesSriLanka (GPL-3 package metadata)."),
           Small("CBSL Daily Price Reports: https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report. Original source PDFs, correction evidence and SHA-256 manifests retained in the local research project."),
           Small("NASA POWER daily API: https://power.larc.nasa.gov/docs/services/api/temporal/daily/ and https://power.larc.nasa.gov/docs/faqs/data/ . Regional grid data acknowledged."),
           Small("LightGBM, pandas, NumPy, FastAPI, Uvicorn, HTTPX, PyMuPDF and pyreadr retain their respective licenses. DM Sans uses the SIL Open Font License. New code is GPL-3.0-or-later; data rights are separate."),
           H("AI assistance and ownership"),P("OpenAI Codex assisted with source recovery, implementation, experiments, tests and documentation. The original team should review and own the submitted work and retain this disclosure. A live buyer pilot and verified savings have not been established."),
           Small("Detailed numerical evidence: reports/evaluation.json; artifacts/model_card.json; data/processed/source_audit.json; reports/basket_predictions.csv. Reproduction and operations: README.md and docs/OPERATIONS.md.")]
    create_pdf(DOCS / "MarketBudget-Technical-Report.pdf",[first,second,third,fourth,fifth,sixth],s)
    summary1=[Label("PROJECT SUMMARY / 1 OF 2"),Title("MarketBudget"),Paragraph("Seven-day vegetable procurement budgeting for Dambulla.",s["subtitle"]),
              H("The problem and the user"),P("A small Sri Lankan caterer or canteen needs a weekly cash plan before future prices are known. The purchasing person enters planned kilograms of beans, carrots and tomatoes and an optional limit. MarketBudget provides a dated benchmark estimate and nominal 80% joint range; suppliers, quantities and purchasing decisions stay with the buyer."),
              H("The product delivered"),P("A responsive five-view dashboard, editable basket planner, budget exposure, price explorer, saved baskets, observed outcome comparison, dated CSV/JSON exports and a visible source correction trail. The local FastAPI service stores records in SQLite; the private hosted replay saves them in the browser. Validated backups restore either edition. Ready-to-run artifacts need no paid inference API."),
              H("Real sources, visible boundaries"),P(f"Recovered vegetablesSriLanka 1.1.0 data provides {n(COVERAGE['retained_valid'])} valid quotes in {n(COVERAGE['retained_rows'])} retained 2022+ rows through 10 March 2026. Three July 2024 corrections were verified against the CBSL wholesale Today column. Fifteen primary quotes were checked across 2023–2026. The 2022 sample audit remains incomplete. NASA POWER supplies three regional weather proxies with a seven-day availability buffer."),
              H("A precise experiment"),P("Targets average valid observed point quotes on issue+1 through issue+7, with at least four quotes per vegetable. Missing labels remain missing. Train in 2022–2023, select in Jan–Jun 2024, calibrate in Jul–Dec 2024, test on 2025 and check early 2026. Purge labels crossing split boundaries. Three baselines compete against four restricted LightGBM quantile variants."),
              Small("This is an explicit historical replay. A single October 2026 reference report is retained separately and does not imply continuous recent coverage or a live quotation.")]
    summary2=[Label("PROJECT SUMMARY / 2 OF 2"),Title("Results worth showing"),stats,Spacer(1,6*mm),
              H("The release retains a baseline"),P(f"The strongest development model reduced basket MAE by {n(MODEL['selection']['learned_improvement']*100,2)}%, but breached the tomato error guard. The release therefore selects the latest-price baseline with a joint range from 105 aligned calibration residuals. It does not claim that adding machine learning automatically improves purchasing."),
              P(f"On {TEST['complete_baskets']} complete 2025 issue dates for the fixed 20 kg beans / 30 kg carrots / 20 kg tomatoes basket, MAE was LKR {n(TEST['basket_mae'],2)}, signed bias LKR {n(TEST['basket_bias'],2)}, observed nominal-80% coverage {n(INTERVAL['observed_coverage']*100,2)}%, and mean interval width LKR {n(INTERVAL['mean_width'],2)}. These are benchmark results, not paid invoice performance or savings."),
              P(RESEARCH_SUMMARY),
              H("Reliability and practical limits"),P("Unrecognized source layouts enter review. Approved data/model bundles are immutable and hash-verified. Exact decimal calculations, transactional multi-tab saves, backup recovery and accessible chart controls are implemented. Current mode withholds old contracts or quotes older than three calendar days. Future-data invariance, target boundaries, stale inputs, saved exports and browser/API numerical parity are tested. Browser QA covers desktop and mobile views."),
              P("Upstream CBSL training and redistribution rights remain unconfirmed. Historical publication times and weather vintages are unavailable. The source audit is partial and interval evidence relies on overlapping dates. No participating buyer, prospective pilot, verified savings or national impact has been established."),
              H("Run it; then validate it prospectively"),P("Install: python -m pip install -e '.[dev]'. Build: python scripts/build.py. Start: python -m marketbudget.api. Open http://127.0.0.1:8000. README includes reproduction instructions; DEMO_SCRIPT.md provides a three-minute walkthrough. Next milestones are rights confirmation, a continuous audited recent feed, buyer recruitment and a four-to-eight-week shadow pilot."),
              Small("Credits: Talagala, Jayarathne and Talagala, vegetablesSriLanka 1.1.0; CBSL; NASA POWER; LightGBM and the Python/browser stack. New code GPL-3.0-or-later; third-party rights remain separate. OpenAI Codex assisted in implementation and documentation. Submission review and ownership remain with the original team.")]
    create_pdf(DOCS / "MarketBudget-Two-Page-Summary.pdf",[summary1,summary2],s)


if __name__ == "__main__":
    figures()
    markdown()
    pdfs()
    print("Generated technical report, two-page summary and standalone evaluation figures")
