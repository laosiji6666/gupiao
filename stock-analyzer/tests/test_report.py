import pytest
import json
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base, AnalysisResult, StockList
from src.report import generate_csv, generate_html
from pathlib import Path


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(StockList(code="600519", name="贵州茅台", industry="食品饮料", market="沪市"))
        s.add(StockList(code="000001", name="平安银行", industry="银行", market="深市"))
        s.add(AnalysisResult(
            date=date(2026, 6, 26), code="600519",
            score=85.0, signals={"technical": {"ma": "bullish"}}
        ))
        s.add(AnalysisResult(
            date=date(2026, 6, 26), code="000001",
            score=72.0, signals={"technical": {"ma": "neutral"}}
        ))
        s.commit()
        yield s


def test_generate_csv(session, tmp_path):
    output = tmp_path / "test_report.csv"
    path = generate_csv(session, date(2026, 6, 26), str(output))
    assert Path(path).exists()
    content = Path(path).read_text(encoding="utf-8")
    assert "600519" in content
    assert "85.0" in content
    assert "贵州茅台" in content


def test_generate_html(session, tmp_path):
    output = tmp_path / "test_report.html"
    path = generate_html(session, date(2026, 6, 26), str(output))
    assert Path(path).exists()
    content = Path(path).read_text(encoding="utf-8")
    assert "贵州茅台" in content
    assert "85.0" in content
    assert "600519" in content
    assert "html" in content.lower()
