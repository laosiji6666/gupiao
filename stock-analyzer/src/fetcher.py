from datetime import date
from typing import Optional
import akshare as ak
import pandas as pd
from sqlalchemy.orm import Session
from src.models import StockList, DailyQuote, Fundamental


class Fetcher:
    """AkShare 数据获取器"""

    def __init__(self, config: dict, logger=None):
        self.config = config
        self.logger = logger

    def _log(self, msg: str, level: str = "info"):
        if self.logger:
            getattr(self.logger, level)(msg)
        else:
            print(f"[{level.upper()}] {msg}")

    def fetch_stock_list(self, session: Session) -> int:
        """获取 A 股股票列表"""
        self._log("正在获取股票列表...")
        df = ak.stock_info_a_code_name()
        count = 0
        for _, row in df.iterrows():
            existing = session.query(StockList).filter_by(code=row["code"]).first()
            if not existing:
                stock = StockList(
                    code=row["code"],
                    name=row["name"],
                    industry=row.get("industry", ""),
                    market=self._detect_market(row["code"]),
                )
                session.add(stock)
                count += 1
        session.commit()
        self._log(f"新增股票 {count} 只")
        return count

    def _detect_market(self, code: str) -> str:
        code_str = str(code)
        if code_str.startswith("6"):
            return "沪市"
        elif code_str.startswith("0") or code_str.startswith("3"):
            return "深市"
        elif code_str.startswith("8") or code_str.startswith("4"):
            return "北市"
        return "其他"

    def fetch_daily_quotes(self, session: Session, trade_date: date) -> int:
        """获取指定交易日行情数据"""
        self._log(f"正在获取 {trade_date} 日线行情...")
        date_str = trade_date.strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(trade_date=date_str)
        count = 0
        for _, row in df.iterrows():
            existing = session.query(DailyQuote).filter_by(
                code=row["code"], date=trade_date
            ).first()
            if not existing:
                quote = DailyQuote(
                    code=row["code"],
                    date=trade_date,
                    open=float(row.get("开盘", 0)),
                    close=float(row.get("收盘", 0)),
                    high=float(row.get("最高", 0)),
                    low=float(row.get("最低", 0)),
                    volume=int(row.get("成交量", 0)),
                    turnover=float(row.get("换手率", 0)),
                )
                session.add(quote)
                count += 1
        session.commit()
        self._log(f"新增行情记录 {count} 条")
        return count

    def fetch_fundamentals(self, session: Session, trade_date: date) -> int:
        """获取基本面数据"""
        self._log(f"正在获取 {trade_date} 基本面数据...")
        try:
            df = ak.stock_a_lg_indicator()
            count = 0
            for _, row in df.iterrows():
                existing = session.query(Fundamental).filter_by(
                    code=row["code"], date=trade_date
                ).first()
                if not existing:
                    f = Fundamental(
                        code=row["code"],
                        date=trade_date,
                        pe=float(row.get("pe", 0)) if row.get("pe") else None,
                        pb=float(row.get("pb", 0)) if row.get("pb") else None,
                        roe=float(row.get("roe", 0)) if row.get("roe") else None,
                        net_profit_growth=float(row.get("净利润增长率", 0)) if row.get("净利润增长率") else None,
                    )
                    session.add(f)
                    count += 1
            session.commit()
            self._log(f"新增基本面记录 {count} 条")
            return count
        except Exception as e:
            self._log(f"获取基本面数据失败: {e}", "warning")
            return 0
