# 股票分析工具 Phase 3 — Web 界面实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为股票分析工具添加 Web 界面，用于查看每日选股排行榜、个股历史评分走势和各指标信号明细。

**Architecture:** FastAPI 提供 RESTful API，Jinja2 模板 + Chart.js 前端展示。Web 服务独立运行，读取现有 SQLite 数据库（data/stock_analyzer.db），不修改已有分析流程。

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, Jinja2, Chart.js (CDN), SQLAlchemy (已有), SQLite

## Global Constraints

- 不修改现有 src/ 下的业务逻辑代码（fetcher、analyzer、report、models）
- 数据库使用现有的 SQLite（data/stock_analyzer.db）
- Web 页面使用 Jinja2 服务端模板 + Chart.js CDN，不引入前端构建工具
- API 路径统一前缀 /api/v1
- 所有新代码放在 src/web/ 目录下
- 测试放在 tests/test_web.py

---

## File Structure

```
stock-analyzer/
└── src/web/
    ├── __init__.py
    ├── app.py              # FastAPI 应用入口
    ├── database.py         # 数据库依赖注入
    ├── routers/
    │   ├── __init__.py
    │   ├── rankings.py     # 排行榜 API
    │   ├── stocks.py       # 个股详情 API
    │   └── pages.py        # 页面路由（Jinja2 模板）
    └── templates/
        ├── base.html        # 基础布局模板
        ├── index.html       # 首页/排行榜
        ├── stock_detail.html # 个股详情页
        └── signals.html     # 信号明细页
```

---

### Task 1: FastAPI 应用骨架 + 数据库依赖

**Files:**
- Create: `stock-analyzer/src/web/__init__.py`
- Create: `stock-analyzer/src/web/app.py`
- Create: `stock-analyzer/src/web/database.py`
- Create: `stock-analyzer/src/web/routers/__init__.py`

**Interfaces:**
- Consumes: `src/models.py` (SQLAlchemy models), `utils/config.py`
- Produces: `get_db()` — FastAPI 依赖项，提供数据库 session
- Produces: FastAPI `app` — ASGI 应用实例

- [ ] **Step 1: 写测试**

```python
# tests/test_web.py
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
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_web.py::test_app_created -v
```

Expected: ImportError — 模块还不存在

- [ ] **Step 3: 创建 Web 应用骨架**

```python
# src/web/__init__.py
``` 

```python
# src/web/database.py
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from src.models import Base


engine = None


def init_db(db_url: str):
    global engine
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)


def get_db():
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    with Session(engine) as session:
        yield session
```

```python
# src/web/app.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path


def create_app() -> FastAPI:
    app = FastAPI(title="Stock Analyzer", version="1.0.0")

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    return app


# 为 uvicorn 直接运行创建的实例
app = create_app()
```

```python
# src/web/routers/__init__.py
``` 

- [ ] **Step 4: 运行测试验证通过**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_web.py::test_app_created tests/test_web.py::test_health_endpoint -v
```

Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(web): add FastAPI app skeleton with health endpoint"
```

---

### Task 2: 排行榜 API（今日选股）

**Files:**
- Create: `stock-analyzer/src/web/routers/rankings.py`
- Modify: `stock-analyzer/src/web/app.py` (注册路由)

**Interfaces:**
- Produces: `GET /api/v1/rankings/today` — 返回当日分析结果，按评分降序
- Produces: `GET /api/v1/rankings/history?date=YYYY-MM-DD` — 返回指定日期结果
- Response: `{ "date": "...", "count": N, "rankings": [{ "rank": 1, "code": "...", "name": "...", "industry": "...", "score": ..., "signals": {...} }, ...] }`

- [ ] **Step 1: 写测试**

```python
# tests/test_web.py — 追加到文件末尾
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
    resp = client.get("/api/v1/rankings/today")
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
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_web.py::test_rankings_today -v
```

Expected: 404 — 路由还没注册

- [ ] **Step 3: 创建排行榜路由**

```python
# src/web/routers/rankings.py
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from src.models import AnalysisResult, StockList
from src.web.database import get_db

router = APIRouter(prefix="/api/v1/rankings", tags=["rankings"])


def _build_ranking(session: Session, target_date: date) -> dict:
    results = (
        session.query(AnalysisResult)
        .filter_by(date=target_date)
        .order_by(AnalysisResult.score.desc())
        .all()
    )
    rankings = []
    for i, ar in enumerate(results, 1):
        stock = session.query(StockList).filter_by(code=ar.code).first()
        rankings.append({
            "rank": i,
            "code": ar.code,
            "name": stock.name if stock else None,
            "industry": stock.industry if stock else None,
            "score": ar.score,
            "signals": ar.signals,
        })
    return {
        "date": target_date.isoformat(),
        "count": len(rankings),
        "rankings": rankings,
    }


@router.get("/today")
def today_ranking(session: Session = Depends(get_db)):
    """获取今日选股排行榜"""
    return _build_ranking(session, date.today())


@router.get("/history")
def history_ranking(
    date_str: str = Query(alias="date"),
    session: Session = Depends(get_db),
):
    """获取指定日期排行榜"""
    target_date = date.fromisoformat(date_str)
    return _build_ranking(session, target_date)
```

```python
# 在 src/web/app.py 中注册路由
from src.web.routers import rankings as rankings_router

def create_app() -> FastAPI:
    app = FastAPI(title="Stock Analyzer", version="1.0.0")
    app.include_router(rankings_router.router)
    ...
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_web.py -v
```

Expected: 5 passed (2 from Task 1 + 3 from Task 2)

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(web): add rankings API (today + history)"
```

---

### Task 3: 个股详情 + 历史评分 API

**Files:**
- Create: `stock-analyzer/src/web/routers/stocks.py`
- Modify: `stock-analyzer/src/web/app.py` (注册路由)

**Interfaces:**
- Produces: `GET /api/v1/stocks/{code}/history` — 返回个股历史评分走势
- Produces: `GET /api/v1/stocks/{code}` — 返回个股基本信息 + 最近评分
- Response (history): `{ "code": "...", "name": "...", "scores": [{ "date": "...", "score": ... }, ...] }`

- [ ] **Step 1: 写测试**

```python
# tests/test_web.py — 追加
from datetime import date, timedelta


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
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_web.py::test_stock_detail -v
```

Expected: 404

- [ ] **Step 3: 创建个股路由**

```python
# src/web/routers/stocks.py
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.models import StockList, AnalysisResult
from src.web.database import get_db

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


@router.get("/{code}")
def stock_detail(code: str, session: Session = Depends(get_db)):
    """获取个股基本信息"""
    stock = session.query(StockList).filter_by(code=code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    latest = (
        session.query(AnalysisResult)
        .filter_by(code=code)
        .order_by(AnalysisResult.date.desc())
        .first()
    )

    return {
        "code": stock.code,
        "name": stock.name,
        "industry": stock.industry,
        "market": stock.market,
        "latest_score": latest.score if latest else None,
        "latest_date": latest.date.isoformat() if latest else None,
    }


@router.get("/{code}/history")
def stock_history(code: str, session: Session = Depends(get_db)):
    """获取个股历史评分走势"""
    stock = session.query(StockList).filter_by(code=code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    results = (
        session.query(AnalysisResult)
        .filter_by(code=code)
        .order_by(AnalysisResult.date.asc())
        .all()
    )

    return {
        "code": code,
        "name": stock.name,
        "scores": [
            {"date": ar.date.isoformat(), "score": ar.score}
            for ar in results
        ],
    }
```

- [ ] **Step 4: 注册路由并运行测试**

```python
# 在 app.py 中追加
from src.web.routers import stocks as stocks_router
app.include_router(stocks_router.router)
```

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_web.py -v
```

Expected: 9 passed (2 + 3 + 4)

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(web): add stock detail and history API"
```

---

### Task 4: Jinja2 模板 + 排行榜页面

**Files:**
- Create: `stock-analyzer/src/web/routers/pages.py`
- Create: `stock-analyzer/src/web/templates/base.html`
- Create: `stock-analyzer/src/web/templates/index.html`
- Modify: `stock-analyzer/src/web/app.py` (注册模板、静态文件、页面路由)

**Interfaces:**
- Consumes: rankings API data
- Produces: `GET /` — 今日排行榜页面
- Produces: `GET /rankings?date=YYYY-MM-DD` — 历史排行榜页面

- [ ] **Step 1: 创建 Jinja2 模板**

```html
{# src/web/templates/base.html #}
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}股票分析系统{% endblock %}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; color: #333; }
        .nav { background: #1a1a2e; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 24px; }
        .nav a { color: #ccc; text-decoration: none; font-size: 14px; }
        .nav a:hover { color: white; }
        .nav a.active { color: #4fc3f7; font-weight: 600; }
        .nav h1 { font-size: 18px; margin-right: 16px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }
        th { background: #f5f5f5; font-weight: 600; color: #666; }
        tr:hover { background: #f8faff; }
        .score { font-weight: 700; color: #e67e22; }
        .rank-1 { color: #d4af37; }
        .rank-2 { color: #a8a8a8; }
        .rank-3 { color: #cd7f32; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
        .badge-bullish { background: #e8f5e9; color: #2e7d32; }
        .badge-bearish { background: #ffebee; color: #c62828; }
        .badge-neutral { background: #e3f2fd; color: #1565c0; }
        .footer { text-align: center; color: #999; font-size: 12px; padding: 24px; }
        .date-picker { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
        .date-picker input { padding: 6px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
        .date-picker button { padding: 6px 16px; background: #1a1a2e; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .date-picker button:hover { background: #2a2a4e; }
        .summary { display: flex; gap: 16px; margin-bottom: 16px; }
        .summary .stat { background: white; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; text-align: center; }
        .summary .stat .value { font-size: 28px; font-weight: 700; color: #1a1a2e; }
        .summary .stat .label { font-size: 12px; color: #999; margin-top: 4px; }
        @media (max-width: 768px) { .summary { flex-direction: column; } }
        a { color: #1976d2; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <nav class="nav">
        <h1>📊 股票分析系统</h1>
        <a href="/" class="{% block nav_rankings %}{% endblock %}">排行榜</a>
    </nav>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
    <div class="footer">由自动化股票分析工具生成 · 数据仅供参考</div>
</body>
</html>
```

```html
{# src/web/templates/index.html #}
{% extends "base.html" %}
{% block nav_rankings %}active{% endblock %}
{% block title %}选股排行榜 - 股票分析系统{% endblock %}
{% block content %}
<div class="card">
    <h2 style="margin-bottom: 12px;">📈 选股排行榜</h2>
    <div class="date-picker">
        <form method="get" action="/rankings">
            <label>日期：</label>
            <input type="date" name="date" value="{{ date }}">
            <button type="submit">查看</button>
        </form>
    </div>
    {% if date != today %}
    <p style="color: #999; margin-bottom: 12px;">← <a href="/">返回今日排行榜</a></p>
    {% endif %}
</div>

<div class="summary">
    <div class="stat">
        <div class="value">{{ rankings|length }}</div>
        <div class="label">筛选股票</div>
    </div>
    <div class="stat">
        <div class="value">{{ "%.1f"|format(avg_score) if avg_score else "—" }}</div>
        <div class="label">平均评分</div>
    </div>
    <div class="stat">
        <div class="value">{{ "%.0f"|format(max_score) if max_score else "—" }}</div>
        <div class="label">最高评分</div>
    </div>
</div>

<div class="card">
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>代码</th>
                <th>名称</th>
                <th>行业</th>
                <th>综合评分</th>
                <th>技术信号</th>
            </tr>
        </thead>
        <tbody>
            {% for item in rankings %}
            <tr>
                <td class="rank-{{ item.rank if item.rank <= 3 else '' }}">
                    {% if item.rank == 1 %}🥇
                    {% elif item.rank == 2 %}🥈
                    {% elif item.rank == 3 %}🥉
                    {% else %}{{ item.rank }}{% endif %}
                </td>
                <td><a href="/stocks/{{ item.code }}">{{ item.code }}</a></td>
                <td><a href="/stocks/{{ item.code }}">{{ item.name }}</a></td>
                <td>{{ item.industry or "—" }}</td>
                <td class="score">{{ "%.1f"|format(item.score) }}</td>
                <td>
                    {% if item.signals and item.signals.technical %}
                        {% for k, v in item.signals.technical.items() %}
                            <span class="badge badge-{{ v }}">{{ k.upper() }}: {{ v }}</span>
                        {% endfor %}
                    {% else %}
                        —
                    {% endif %}
                </td>
            </tr>
            {% else %}
            <tr><td colspan="6" style="text-align:center;color:#999;padding:40px;">暂无数据</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

```python
# src/web/routers/pages.py
from datetime import date
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from src.models import AnalysisResult, StockList
from src.web.database import get_db

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")
router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def index_page(request: Request, session: Session = Depends(get_db)):
    """今日排行榜首页"""
    return _render_rankings(request, session, date.today())


@router.get("/rankings", response_class=HTMLResponse)
def rankings_page(
    request: Request,
    date_str: str = Query(default=None, alias="date"),
    session: Session = Depends(get_db),
):
    """指定日期排行榜"""
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    return _render_rankings(request, session, target_date)


def _render_rankings(request: Request, session: Session, target_date: date):
    results = (
        session.query(AnalysisResult)
        .filter_by(date=target_date)
        .order_by(AnalysisResult.score.desc())
        .all()
    )
    rankings = []
    scores = []
    for i, ar in enumerate(results, 1):
        stock = session.query(StockList).filter_by(code=ar.code).first()
        rankings.append({
            "rank": i,
            "code": ar.code,
            "name": stock.name if stock else ar.code,
            "industry": stock.industry if stock else None,
            "score": ar.score,
            "signals": ar.signals,
        })
        if ar.score is not None:
            scores.append(ar.score)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "rankings": rankings,
        "date": target_date.isoformat(),
        "today": date.today().isoformat(),
        "avg_score": sum(scores) / len(scores) if scores else None,
        "max_score": max(scores) if scores else None,
    })
```

- [ ] **Step 2: 在 app.py 中注册页面路由和模板目录**

```python
# 在 app.py 中
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from src.web.routers import pages as pages_router

def create_app() -> FastAPI:
    app = FastAPI(title="Stock Analyzer", version="1.0.0")
    app.include_router(rankings_router.router)
    app.include_router(stocks_router.router)
    app.include_router(pages_router.router)
    return app
```

- [ ] **Step 3: 添加页面路由测试**

```python
# tests/test_web.py — 追加
def test_index_page_renders(client, session):
    seed_test_data(session)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "贵州茅台" in resp.text
    assert "600519" in resp.text


def test_rankings_page_empty(client, session):
    resp = client.get("/rankings?date=2025-01-01")
    assert resp.status_code == 200
    assert "暂无数据" in resp.text
```

- [ ] **Step 4: 运行测试**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_web.py -v
```

Expected: 11 passed

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(web): add Jinja2 templates and rankings page"
```

---

### Task 5: 个股详情页（评分走势图）

**Files:**
- Create: `stock-analyzer/src/web/templates/stock_detail.html`
- Modify: `stock-analyzer/src/web/routers/pages.py` (添加个股页面路由)

- [ ] **Step 1: 创建个股详情模板**

```html
{# src/web/templates/stock_detail.html #}
{% extends "base.html" %}
{% block nav_rankings %}{% endblock %}
{% block title %}{{ stock.name }} ({{ stock.code }}) - 股票分析系统{% endblock %}
{% block content %}
<div class="card">
    <h2>
        {{ stock.name }}
        <span style="font-weight:400;color:#999;font-size:16px;">{{ stock.code }}</span>
        {% if stock.industry %}
        <span class="badge badge-neutral" style="font-size:12px;vertical-align:middle;">{{ stock.industry }}</span>
        {% endif %}
    </h2>
    <p style="color:#666;margin-top:8px;">
        {{ stock.market or "—" }} ·
        {% if stock.latest_score is not none %}
            最新评分: <strong class="score">{{ "%.1f"|format(stock.latest_score) }}</strong>
            ({{ stock.latest_date }})
        {% else %}
            暂无评分数据
        {% endif %}
    </p>
</div>

<div class="card">
    <h3 style="margin-bottom:16px;">📈 历史评分走势</h3>
    <canvas id="scoreChart" height="80"></canvas>
</div>

<div class="card">
    <h3 style="margin-bottom:16px;">📋 评分明细</h3>
    <table>
        <thead>
            <tr>
                <th>日期</th>
                <th>评分</th>
            </tr>
        </thead>
        <tbody>
            {% for s in scores %}
            <tr>
                <td>{{ s.date }}</td>
                <td class="score">{{ "%.1f"|format(s.score) }}</td>
            </tr>
            {% else %}
            <tr><td colspan="2" style="text-align:center;color:#999;padding:40px;">暂无数据</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<p><a href="/">← 返回排行榜</a></p>

<script>
const ctx = document.getElementById('scoreChart').getContext('2d');
new Chart(ctx, {
    type: 'line',
    data: {
        labels: [{% for s in scores %}'{{ s.date }}',{% endfor %}],
        datasets: [{
            label: '综合评分',
            data: [{% for s in scores %}{{ s.score }},{% endfor %}],
            borderColor: '#1976d2',
            backgroundColor: 'rgba(25, 118, 210, 0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 3,
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, max: 100 },
            x: { ticks: { maxTicksLimit: 15 } }
        }
    }
});
</script>
{% endblock %}
```

- [ ] **Step 2: 添加个股页面路由**

```python
# 在 src/web/routers/pages.py 中追加

@router.get("/stocks/{code}", response_class=HTMLResponse)
def stock_detail_page(
    request: Request,
    code: str,
    session: Session = Depends(get_db),
):
    """个股详情页"""
    stock = session.query(StockList).filter_by(code=code).first()
    if not stock:
        return HTMLResponse("股票未找到", status_code=404)

    results = (
        session.query(AnalysisResult)
        .filter_by(code=code)
        .order_by(AnalysisResult.date.asc())
        .all()
    )

    latest = results[-1] if results else None

    return templates.TemplateResponse("stock_detail.html", {
        "request": request,
        "stock": {
            "code": stock.code,
            "name": stock.name,
            "industry": stock.industry,
            "market": stock.market,
            "latest_score": latest.score if latest else None,
            "latest_date": latest.date.isoformat() if latest else None,
        },
        "scores": [
            {"date": ar.date.isoformat(), "score": ar.score}
            for ar in results
        ],
    })
```

- [ ] **Step 3: 添加测试**

```python
# tests/test_web.py — 追加
def test_stock_detail_page(client, session):
    seed_test_data(session)
    resp = client.get("/stocks/600519")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "贵州茅台" in resp.text
    assert "评分走势" in resp.text


def test_stock_detail_page_not_found(client, session):
    resp = client.get("/stocks/999999")
    assert resp.status_code == 404
```

- [ ] **Step 4: 运行测试**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/ -v
```

Expected: All existing tests + 2 new = 24 passed

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(web): add stock detail page with Chart.js score chart"
```

---

### Task 6: Web 启动入口 + main.py 集成

**Files:**
- Modify: `stock-analyzer/src/web/app.py` (添加独立运行支持)
- Modify: `stock-analyzer/main.py` (添加 Web 启动选项)
- Modify: `stock-analyzer/requirements.txt` (添加 FastAPI/uvicorn)

- [ ] **Step 1: 更新 app.py 支持 uvicorn 直接运行**

```python
# 在 src/web/app.py 末尾添加
if __name__ == "__main__":
    import uvicorn
    from src.web.database import init_db
    from utils.config import load_config

    config = load_config()
    init_db(config["database"]["url"])
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: 更新 requirements.txt**

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
jinja2>=3.1.0
python-multipart>=0.0.9
```

- [ ] **Step 3: 在 main.py 中添加 Web 启动选项**

```python
# 在 main.py 末尾添加
def start_web():
    """启动 Web 服务"""
    import uvicorn
    from src.web.database import init_db as init_web_db
    from src.web.app import app

    config = load_config()
    init_web_db(config["database"]["url"])
    logger = setup_logger()
    logger.info("Web 服务启动于 http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        start_web()
    else:
        main()
```

- [ ] **Step 4: 运行全量测试**

```bash
cd d:/AI/superpowers/stock-analyzer
pip install fastapi uvicorn jinja2 python-multipart 2>&1 | tail -3
python -m pytest tests/ -v
```

Expected: 24 passed

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(web): add uvicorn startup and main.py web command"
```
