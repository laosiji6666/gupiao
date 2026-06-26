import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base
from src.web.database import get_db
from src.web.app import create_app


@pytest.fixture
def engine():
    return create_engine(
        "sqlite+pysqlite:///file::memory:?cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(engine, session):
    app = create_app()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_app_created(client):
    """应用创建成功"""
    assert client is not None


def test_health_endpoint(client):
    """健康检查"""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ── 排行榜 API 测试（Task 2） ──────────────────────────────
from datetime import date
from src.models import StockList, AnalysisResult


def seed_test_data(session):
    """插入测试数据"""
    session.add(StockList(code="600519", name="贵州茅台", industry="食品饮料", market="沪市"))
    session.add(StockList(code="000001", name="平安银行", industry="银行", market="深市"))
    session.add(AnalysisResult(
        date=date(2026, 6, 26), code="600519",
        score=85.0, signals={"technical": {"ma": "bullish"}}
    ))
    session.add(AnalysisResult(
        date=date(2026, 6, 26), code="000001",
        score=72.0, signals={"technical": {"ma": "neutral"}}
    ))
    session.add(AnalysisResult(
        date=date(2026, 6, 25), code="600519",
        score=80.0, signals={}
    ))
    session.commit()


def test_rankings_today(client, session):
    seed_test_data(session)
    resp = client.get("/api/v1/rankings/today?date=2026-06-26")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-06-26"
    assert data["count"] == 2
    assert data["rankings"][0]["code"] == "600519"
    assert data["rankings"][0]["score"] == 85.0
    assert data["rankings"][0]["name"] == "贵州茅台"


def test_rankings_history(client, session):
    seed_test_data(session)
    resp = client.get("/api/v1/rankings/history?date=2026-06-25")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["rankings"][0]["code"] == "600519"


def test_rankings_no_data(client, session):
    resp = client.get("/api/v1/rankings/today")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["rankings"] == []


# ── 个股详情 + 历史评分 API 测试（Task 3） ───────────────────


def test_stock_detail(client, session):
    seed_test_data(session)
    resp = client.get("/api/v1/stocks/600519")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "600519"
    assert data["name"] == "贵州茅台"


def test_stock_not_found(client, session):
    resp = client.get("/api/v1/stocks/999999")
    assert resp.status_code == 404


def test_stock_history(client, session):
    seed_test_data(session)
    # Add more historical data
    from datetime import timedelta
    for days_back in range(5, 0, -1):
        d = date(2026, 6, 20 + days_back)
        session.add(AnalysisResult(
            date=d, code="600519",
            score=float(80 + days_back),
            signals={},
        ))
    session.commit()

    resp = client.get("/api/v1/stocks/600519/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "600519"
    assert len(data["scores"]) >= 6  # 1 from seed + 5 new
    # Should be sorted by date ascending
    dates = [s["date"] for s in data["scores"]]
    assert dates == sorted(dates)


def test_stock_history_empty(client, session):
    resp = client.get("/api/v1/stocks/999999/history")
    assert resp.status_code == 404


# ── 页面路由测试（Task 4） ──────────────────────────────


def test_index_page_renders(client, session):
    seed_test_data(session)
    resp = client.get("/rankings?date=2026-06-26")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "贵州茅台" in resp.text
    assert "600519" in resp.text


def test_rankings_page_empty(client, session):
    resp = client.get("/rankings?date=2025-01-01")
    assert resp.status_code == 200
    assert "暂无数据" in resp.text
