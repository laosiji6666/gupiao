import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base, StockList, DailyQuote, Fundamental
from src.fetcher import Fetcher


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def fetcher():
    return Fetcher({"database": {"url": "sqlite:///:memory:"}})


def test_detect_market_sh(fetcher):
    assert fetcher._detect_market("600519") == "沪市"


def test_detect_market_sz(fetcher):
    assert fetcher._detect_market("000001") == "深市"


def test_detect_market_bj(fetcher):
    assert fetcher._detect_market("830000") == "北市"


@patch("src.fetcher.ak.stock_info_a_code_name")
def test_fetch_stock_list(mock_stock_list, fetcher, session):
    mock_stock_list.return_value = pd.DataFrame([
        {"code": "600519", "name": "贵州茅台"},
        {"code": "000001", "name": "平安银行"},
    ])
    count = fetcher.fetch_stock_list(session)
    assert count == 2
    assert session.query(StockList).count() == 2


def test_fetch_stock_list_dedup(fetcher, session):
    session.add(StockList(code="600519", name="贵州茅台", industry="", market="沪市"))
    session.commit()
    with patch("src.fetcher.ak.stock_info_a_code_name") as mock:
        mock.return_value = pd.DataFrame([
            {"code": "600519", "name": "贵州茅台"},
            {"code": "000001", "name": "平安银行"},
        ])
        count = fetcher.fetch_stock_list(session)
    assert count == 1  # only new one
    assert session.query(StockList).count() == 2


@patch("src.fetcher.ak.stock_zh_a_hist")
def test_fetch_daily_quotes(mock_daily, fetcher, session):
    mock_daily.return_value = pd.DataFrame([
        {"code": "600519", "开盘": 1500.0, "收盘": 1510.0, "最高": 1520.0,
         "最低": 1490.0, "成交量": 5000000, "换手率": 0.5},
    ])
    trade_date = date(2026, 6, 26)
    count = fetcher.fetch_daily_quotes(session, trade_date)
    assert count == 1
    assert session.query(DailyQuote).count() == 1
    q = session.query(DailyQuote).first()
    assert q.code == "600519"
    assert q.close == 1510.0


@patch("src.fetcher.ak.stock_zh_a_hist")
def test_fetch_daily_quotes_dedup(mock_daily, fetcher, session):
    """Existing records should not be duplicated."""
    trade_date = date(2026, 6, 26)
    session.add(DailyQuote(
        code="600519", date=trade_date,
        open=1500.0, close=1510.0, high=1520.0, low=1490.0,
        volume=5000000, turnover=0.5,
    ))
    session.commit()
    mock_daily.return_value = pd.DataFrame([
        {"code": "600519", "开盘": 1500.0, "收盘": 1510.0, "最高": 1520.0,
         "最低": 1490.0, "成交量": 5000000, "换手率": 0.5},
    ])
    count = fetcher.fetch_daily_quotes(session, trade_date)
    assert count == 0
    assert session.query(DailyQuote).count() == 1


@patch("src.fetcher.ak.stock_a_lg_indicator", create=True)
def test_fetch_fundamentals(mock_fund, fetcher, session):
    mock_fund.return_value = pd.DataFrame([
        {"code": "600519", "pe": 25.0, "pb": 6.0, "roe": 30.0, "净利润增长率": 15.0},
    ])
    trade_date = date(2026, 6, 26)
    count = fetcher.fetch_fundamentals(session, trade_date)
    assert count == 1
    assert session.query(Fundamental).count() == 1
    f = session.query(Fundamental).first()
    assert f.code == "600519"
    assert f.roe == 30.0


@patch("src.fetcher.ak.stock_a_lg_indicator", create=True)
def test_fetch_fundamentals_failure(mock_fund, fetcher, session):
    """If the akshare call raises, we should get 0 and not crash."""
    mock_fund.side_effect = Exception("API error")
    trade_date = date(2026, 6, 26)
    count = fetcher.fetch_fundamentals(session, trade_date)
    assert count == 0


def test_log_without_logger(fetcher, capsys):
    """_log should print when no logger is configured."""
    fetcher._log("hello", "info")
    captured = capsys.readouterr()
    assert "[INFO] hello" in captured.out


def test_log_with_logger(fetcher):
    """_log should call the logger when one is provided."""
    mock_logger = MagicMock()
    fetcher.logger = mock_logger
    fetcher._log("test message", "warning")
    mock_logger.warning.assert_called_once_with("test message")
