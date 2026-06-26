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
