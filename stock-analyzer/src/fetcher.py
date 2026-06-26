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

    def _safe_float(self, row: pd.Series, keys: list) -> Optional[float]:
        """Try multiple column names to extract a float value from a row."""
        for key in keys:
            val = row.get(key)
            if val is not None:
                try:
                    v = float(val)
                    if not pd.isna(v):
                        return v
                except (ValueError, TypeError):
                    pass
        return None

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
        """获取A股实时行情数据（作为日线行情使用）"""
        self._log(f"正在获取 {trade_date} 实时行情...")
        df = ak.stock_zh_a_spot_em()
        count = 0
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            if not code:
                continue
            existing = session.query(DailyQuote).filter_by(
                code=code, date=trade_date
            ).first()
            if not existing:
                quote = DailyQuote(
                    code=code,
                    date=trade_date,
                    open=float(row.get("今开", 0) or 0),
                    close=float(row.get("最新价", 0) or 0),
                    high=float(row.get("最高", 0) or 0),
                    low=float(row.get("最低", 0) or 0),
                    volume=int(row.get("成交量", 0) or 0),
                    turnover=float(row.get("成交额", 0) or 0),
                )
                session.add(quote)
                count += 1
        session.commit()
        self._log(f"新增行情记录 {count} 条")
        return count

    def fetch_fundamentals(self, session: Session, trade_date: date) -> int:
        """获取A股基本面数据"""
        self._log(f"正在获取 {trade_date} 基本面数据...")
        try:
            # Try stock_a_all_pb() first for valuation data.
            try:
                df = ak.stock_a_all_pb()
            except Exception:
                df = ak.stock_zh_a_spot_em()

            # stock_a_all_pb() returns market-level data without per-stock codes.
            # Fall back to stock_zh_a_spot_em() for per-stock PE/PB data.
            if "代码" not in df.columns and "code" not in df.columns:
                df = ak.stock_zh_a_spot_em()

            count = 0
            for _, row in df.iterrows():
                code = str(row.get("代码", row.get("code", "")))
                if not code:
                    continue
                existing = session.query(Fundamental).filter_by(
                    code=code, date=trade_date
                ).first()
                if not existing:
                    f = Fundamental(
                        code=code,
                        date=trade_date,
                        pe=self._safe_float(row, ["市盈率-动态", "市盈率", "pe"]),
                        pb=self._safe_float(row, ["市净率", "pb"]),
                        roe=self._safe_float(row, ["净资产收益率", "roe"]),
                        net_profit_growth=self._safe_float(
                            row, ["净利润增长率", "net_profit_growth"]
                        ),
                    )
                    session.add(f)
                    count += 1
            session.commit()
            self._log(f"新增基本面记录 {count} 条")
            return count
        except Exception as e:
            self._log(f"获取基本面数据失败: {e}", "warning")
            return 0
