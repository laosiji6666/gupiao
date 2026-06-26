import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base
from src.web.database import get_db
from src.web.app import create_app


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


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
