import pytest
from sqlalchemy import create_engine
from src.models import Base, StockList, DailyQuote, Fundamental, AnalysisResult


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


def test_create_tables(engine):
    Base.metadata.create_all(engine)
    # Verify no exception means tables created
    assert True


def test_stock_list_model(engine):
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    with Session(engine) as session:
        stock = StockList(code="600519", name="贵州茅台", industry="食品饮料", market="沪市")
        session.add(stock)
        session.commit()
        retrieved = session.query(StockList).filter_by(code="600519").first()
        assert retrieved is not None
        assert retrieved.name == "贵州茅台"


def test_daily_quote_model(engine):
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    from datetime import date
    with Session(engine) as session:
        quote = DailyQuote(
            code="600519", date=date(2026, 6, 26),
            open=1500.0, close=1510.0, high=1520.0, low=1490.0,
            volume=5000000, turnover=0.5
        )
        session.add(quote)
        session.commit()
        q = session.query(DailyQuote).filter_by(code="600519").first()
        assert q.close == 1510.0


def test_fundamental_model(engine):
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    from datetime import date
    with Session(engine) as session:
        f = Fundamental(
            code="600519", date=date(2026, 6, 26),
            pe=25.0, pb=6.0, roe=30.0, net_profit_growth=15.0
        )
        session.add(f)
        session.commit()
        r = session.query(Fundamental).first()
        assert r.roe == 30.0


def test_analysis_result_model(engine):
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    from datetime import date
    with Session(engine) as session:
        ar = AnalysisResult(
            date=date(2026, 6, 26), code="600519",
            score=85.0, signals={"ma": "bullish", "macd": "golden_cross"}
        )
        session.add(ar)
        session.commit()
        r = session.query(AnalysisResult).first()
        assert r.score == 85.0
        assert r.signals["macd"] == "golden_cross"
