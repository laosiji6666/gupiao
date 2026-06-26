from datetime import date, datetime, timezone
from sqlalchemy import (
    Column, String, Date, DateTime, Integer, Float, JSON,
    PrimaryKeyConstraint
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class StockList(Base):
    __tablename__ = "stock_list"

    code = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    industry = Column(String(50))
    market = Column(String(10))

    def __repr__(self):
        return f"<StockList(code={self.code}, name={self.name})>"


class DailyQuote(Base):
    __tablename__ = "daily_quotes"

    code = Column(String(10), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Integer)
    turnover = Column(Float)

    __table_args__ = (
        PrimaryKeyConstraint("code", "date"),
    )


class Fundamental(Base):
    __tablename__ = "fundamentals"

    code = Column(String(10), nullable=False)
    date = Column(Date, nullable=False)
    pe = Column(Float)
    pb = Column(Float)
    roe = Column(Float)
    net_profit_growth = Column(Float)

    __table_args__ = (
        PrimaryKeyConstraint("code", "date"),
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    code = Column(String(10), nullable=False)
    score = Column(Float)
    signals = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db(engine):
    Base.metadata.create_all(engine)
