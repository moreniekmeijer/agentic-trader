SECTOR_BASELINES = {
    "Technology": {
        "pe": 25,
        "de_ratio": 0.8,
        "profit_margin": 0.15,
        "roe": 0.15,
    },
    "Healthcare": {
        "pe": 20,
        "de_ratio": 1.0,
        "profit_margin": 0.12,
        "roe": 0.12,
    },
    "Financial Services": {
        "pe": 12,
        "de_ratio": 2.5,
        "profit_margin": 0.20,
        "roe": 0.10,
    },
    "Utilities": {
        "pe": 15,
        "de_ratio": 2.0,
        "profit_margin": 0.10,
        "roe": 0.08,
    },
    "Consumer Cyclical": {
        "pe": 18,
        "de_ratio": 1.2,
        "profit_margin": 0.10,
        "roe": 0.12,
    },
}

DEFAULT_BASELINE = {
    "pe": 20,
    "de_ratio": 1.0,
    "profit_margin": 0.10,
    "roe": 0.10,
}


def get_baseline(sector: str | None) -> dict:
    if not sector:
        return DEFAULT_BASELINE
    return SECTOR_BASELINES.get(sector, DEFAULT_BASELINE)
