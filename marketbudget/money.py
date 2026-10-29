"""Decimal business arithmetic, mirrored by web/money.mjs (policy 1)."""
from decimal import Decimal, localcontext, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING
import math

CALCULATION_VERSION="decimal_half_up_v1"

def decimal(value):
    return Decimal(str(0 if value==0 else value))

def amount(value):
    return float(decimal(value).quantize(Decimal(".01"),rounding=ROUND_HALF_UP))

def ledger(point, quantities, residuals):
    with localcontext() as context:
        context.prec=50
        prices=[decimal(p).quantize(Decimal(".000001"),rounding=ROUND_HALF_UP) for p in point]
        weights=[decimal(q) for q in quantities]
        lines=[(p*q).quantize(Decimal(".01"),rounding=ROUND_HALF_UP) for p,q in zip(prices,weights)]
        total=sum(lines)
        scenarios=[sum(max(Decimal(0),p*(1+decimal(r)))*q for p,q,r in zip(prices,weights,row)) for row in residuals]
        bounds=decimal_interval(scenarios,total)
        marginal=[decimal_interval([max(Decimal(0),p*(1+decimal(row[i]))) for row in residuals],p) for i,p in enumerate(prices)]
        return {"prices":[float(p) for p in prices],"lines":[float(v) for v in lines],"total":float(total),
                "interval":bounds,"marginal":marginal}

def decimal_interval(values, point):
    if len(values)<30:raise ValueError("At least 30 calibration scenarios required")
    ordered=sorted(values);n=len(ordered)
    low=min(point,ordered[max(0,math.floor(.1*(n+1))-1)])
    high=max(point,ordered[min(n-1,math.ceil(.9*(n+1))-1)])
    return [float(low.quantize(Decimal('.01'),rounding=ROUND_FLOOR)),
            float(high.quantize(Decimal('.01'),rounding=ROUND_CEILING))]
