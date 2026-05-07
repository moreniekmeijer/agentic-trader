import pandas as pd
import pytest

from agentic_trader.services.market_data.feature_builder import FeatureBuilder


def test_build_raises_for_empty_dataframe():
    builder = FeatureBuilder()

    with pytest.raises(ValueError, match="insufficient market data"):
        builder.build(pd.DataFrame(), "GOOGL")


def test_build_raises_for_single_row_dataframe():
    builder = FeatureBuilder()
    df = pd.DataFrame([{"close": 1.0, "rsi": 50.0}])

    with pytest.raises(ValueError, match="insufficient market data"):
        builder.build(df, "GOOGL")
