from datetime import date, timedelta
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
        df = ak.stock_zh_a_spot()
        count = 0
        for _, row in df.iterrows():
            raw_code = str(row["代码"])
            code = raw_code
            for prefix in ["sh", "sz", "bj"]:
                if raw_code.startswith(prefix):
                    code = raw_code[len(prefix):]
                    break
            if not code:
                continue
            existing = session.query(DailyQuote).filter_by(
                code=code, date=trade_date
            ).first()
            if not existing:
                quote = DailyQuote(
                    code=code,
                    date=trade_date,
                    open=float(row["今开"] or 0),
                    close=float(row["最新价"] or 0),
                    high=float(row["最高"] or 0),
                    low=float(row["最低"] or 0),
                    volume=int(row["成交量"] or 0),
                    turnover=0.0,  # Sina doesn't provide turnover rate
                )
                session.add(quote)
                count += 1
        session.commit()
        self._log(f"新增行情记录 {count} 条")
        return count

    def backfill_history(self, session: Session, days: int = 60) -> int:
        """
        首次运行时补充历史日线数据。
        遍历所有股票，用 stock_zh_a_hist 获取历史 K 线。
        days: 需要回填的历史天数（实际会多拉一些以覆盖周末）
        """
        stocks = session.query(StockList).all()
        if not stocks:
            self._log("股票列表为空，跳过历史回填")
            return 0

        end_date = date.today()
        start_date = end_date - timedelta(days=int(days * 1.5))  # 多拉一些避开周末
        date_str_start = start_date.strftime("%Y%m%d")
        date_str_end = end_date.strftime("%Y%m%d")

        self._log(f"开始回填 {len(stocks)} 只股票的历史数据 ({days} 天)...")
        total_inserted = 0

        for i, stock in enumerate(stocks):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=stock.code,
                    start_date=date_str_start,
                    end_date=date_str_end,
                    adjust="",
                )
                if df is None or df.empty:
                    continue

                inserted = 0
                for _, row in df.iterrows():
                    try:
                        # stock_zh_a_hist 返回的列：日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                        quote_date = row["日期"]
                        if isinstance(quote_date, str):
                            quote_date = pd.to_datetime(quote_date).date()

                        existing = session.query(DailyQuote).filter_by(
                            code=stock.code, date=quote_date
                        ).first()
                        if existing:
                            continue

                        quote = DailyQuote(
                            code=stock.code,
                            date=quote_date,
                            open=float(row.get("开盘", 0) or 0),
                            close=float(row.get("收盘", 0) or 0),
                            high=float(row.get("最高", 0) or 0),
                            low=float(row.get("最低", 0) or 0),
                            volume=int(row.get("成交量", 0) or 0),
                            turnover=float(row.get("换手率", 0) or 0),
                        )
                        session.add(quote)
                        inserted += 1
                    except (ValueError, TypeError) as e:
                        self._log(f"  行解析错误 ({stock.code}): {e}", "debug")
                        continue

                if inserted > 0:
                    session.commit()
                    total_inserted += inserted

                if (i + 1) % 200 == 0:
                    self._log(f"  回填进度: {i+1}/{len(stocks)}, 已插入 {total_inserted} 条")

            except Exception as e:
                self._log(f"  回填 {stock.code} 失败: {e}", "warning")
                session.rollback()
                continue

        self._log(f"历史回填完成: 共 {total_inserted} 条记录 ({len(stocks)} 只股票)")
        return total_inserted

    def fetch_fundamentals(self, session: Session, trade_date: date) -> int:
        """获取A股基本面数据"""
        self._log(f"正在获取 {trade_date} 基本面数据...")
        try:
            date_str = trade_date.strftime("%Y%m%d")
            df = ak.stock_yjbb_em(date=date_str)

            code_col = "股票代码"
            roe_col = "净资产收益率"
            npg_col = "净利润-同比增长"

            count = 0
            for _, row in df.iterrows():
                code = str(row[code_col]).strip()
                if not code:
                    continue

                existing = session.query(Fundamental).filter_by(
                    code=code, date=trade_date
                ).first()
                if not existing:
                    roe_val = None
                    npg_val = None
                    try:
                        v = row[roe_col]
                        if v is not None and not (isinstance(v, float) and pd.isna(v)):
                            roe_val = float(v)
                    except (ValueError, TypeError):
                        pass
                    try:
                        v = row[npg_col]
                        if v is not None and not (isinstance(v, float) and pd.isna(v)):
                            npg_val = float(v)
                    except (ValueError, TypeError):
                        pass

                    f = Fundamental(
                        code=code,
                        date=trade_date,
                        pe=None,
                        pb=None,
                        roe=roe_val,
                        net_profit_growth=npg_val,
                    )
                    session.add(f)
                    count += 1

            # PE/PB supplement not available from Sina API
            session.commit()
            self._log(f"新增基本面记录 {count} 条")
            return count
        except Exception as e:
            self._log(f"获取基本面数据失败: {e}", "warning")
            return 0
