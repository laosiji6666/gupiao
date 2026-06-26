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
def today_ranking(
    date_str: str = Query(default=None, alias="date"),
    session: Session = Depends(get_db),
):
    """获取选股排行榜，默认今日"""
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    return _build_ranking(session, target_date)


@router.get("/history")
def history_ranking(
    date_str: str = Query(alias="date"),
    session: Session = Depends(get_db),
):
    """获取指定日期排行榜"""
    target_date = date.fromisoformat(date_str)
    return _build_ranking(session, target_date)
