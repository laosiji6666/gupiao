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

    return templates.TemplateResponse(request, "stock_detail.html", {
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

    return templates.TemplateResponse(request, "index.html", {
        "rankings": rankings,
        "date": target_date.isoformat(),
        "today": date.today().isoformat(),
        "avg_score": sum(scores) / len(scores) if scores else None,
        "max_score": max(scores) if scores else None,
    })
