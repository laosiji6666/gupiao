import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base, DailyQuote, Fundamental
from src.analyzer import (
    calculate_technical,
    calculate_fundamental,
    calculate_score,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def config():
    return {
        "analyzer": {
            "technical_weight": 0.4,
            "fundamental_weight": 0.6,
            "indicators": {
                "ma": {"enabled": True, "windows": [5, 10, 20, 60]},
                "macd": {"enabled": True, "fast": 12, "slow": 26, "signal": 9},
                "rsi": {"enabled": True, "period": 14, "overbought": 70, "oversold": 30},
                "kdj": {"enabled": True},
            },
            "fundamental": {
                "pe_max": 50,
                "pb_max": 10,
                "roe_min": 15,
                "net_profit_growth_min": 10,
            },
        }
    }


def test_calculate_fundamental_all_good(config):
    """所有基本面指标达标"""
    f = MagicMock()
    f.pe = 20.0
    f.pb = 3.0
    f.roe = 25.0
    f.net_profit_growth = 20.0
    result = calculate_fundamental(f, config)
    assert result["pe_score"] == 1
    assert result["pb_score"] == 1
    assert result["roe_score"] == 1
    assert result["net_profit_growth_score"] == 1
    assert result["total"] == 4.0


def test_calculate_fundamental_all_bad(config):
    """所有基本面指标不达标"""
    f = MagicMock()
    f.pe = 100.0
    f.pb = 20.0
    f.roe = 5.0
    f.net_profit_growth = -10.0
    result = calculate_fundamental(f, config)
    assert result["pe_score"] == 0
    assert result["pb_score"] == 0
    assert result["roe_score"] == 0
    assert result["net_profit_growth_score"] == 0
    assert result["total"] == 0.0


def test_calculate_score(config):
    technical = {"score": 80.0}
    fundamental = {"total": 3.0, "max": 4}
    score = calculate_score(technical, fundamental, config)
    # technical_weight=0.4, fundamental_weight=0.6
    # technical: 80/100 * 0.4 = 0.32
    # fundamental: 3/4 * 0.6 = 0.45
    # total: 0.77 * 100 = 77
    assert abs(score - 77.0) < 0.01


def test_calculate_technical_basic(config):
    """Test that calculate_technical returns expected structure"""
    dates = pd.date_range(end="2026-06-26", periods=100, freq="B")
    np.random.seed(42)
    n = len(dates)
    # Generate realistic price data
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    close = np.maximum(close, 10)  # floor
    df = pd.DataFrame({
        "date": dates,
        "open": close * 0.99,
        "close": close,
        "high": close * 1.02,
        "low": close * 0.98,
        "volume": np.random.randint(100000, 1000000, n),
        "turnover": np.random.rand(n) * 5,
    })

    result = calculate_technical(df, config)
    assert "signals" in result
    assert "score" in result
    assert 0 <= result["score"] <= 100
    assert isinstance(result["signals"], dict)
