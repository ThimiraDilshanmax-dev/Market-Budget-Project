import argparse
import json

from .config import ROOT
from .forecast import basket_forecast
from .releases import load_release

parser = argparse.ArgumentParser(description="Calculate a traceable historical basket budget")
parser.add_argument("--date", default=None)
parser.add_argument("--beans", type=float, default=20)
parser.add_argument("--carrot", type=float, default=30)
parser.add_argument("--tomato", type=float, default=20)
parser.add_argument("--budget", type=float, default=None)
parser.add_argument("--current", action="store_true", help="Enforce today's date and freshness; stale replay is withheld")
args = parser.parse_args()
state = load_release()[0]
try:
    output = basket_forecast(state, args.date or state["forecasts"][-1]["date"],
                             {"beans": args.beans, "carrot": args.carrot, "tomato": args.tomato}, args.budget,
                             replay=not args.current)
except ValueError as error:
    parser.error(str(error))
print(json.dumps(output, indent=2, allow_nan=False))
