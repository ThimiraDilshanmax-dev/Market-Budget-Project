from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMODITIES = ("beans", "carrot", "tomato")
NAMES = {"beans": "Beans", "carrot": "Carrots", "tomato": "Tomatoes"}
REFERENCE_BASKET = {"beans": 20.0, "carrot": 30.0, "tomato": 20.0}
HORIZON_DAYS = 7
MIN_OBSERVATIONS = 4
MAX_PRICE_AGE = 3
WEATHER_BUFFER = 7
GRIDS = {"nuwara_eliya": (6.97, 80.77), "badulla": (6.99, 81.06), "kandy_matale": (7.30, 80.64)}
CBSL_INDEX = "https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report"
PACKAGE_URL = "https://thiyangtdata.r-universe.dev/src/contrib/vegetablesSriLanka_1.1.0.tar.gz"

