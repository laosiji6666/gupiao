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
        首次运行时补充历史日线数据（使用腾讯财经 API）。
        days: 需要回填的历史天数
        """
        import requests as req

        stocks = session.query(StockList).all()
        if not stocks:
            self._log("股票列表为空，跳过历史回填")
            return 0

        self._log(f"开始回填 {len(stocks)} 只股票的历史数据 ({days} 天)...")
        total_inserted = 0
        consecutive_failures = 0
        MAX_FAILURES = 5

        headers = {"User-Agent": "Mozilla/5.0"}
        today = date.today()

        for i, stock in enumerate(stocks):
            if consecutive_failures >= MAX_FAILURES:
                self._log(f"检测到网络不可用，跳过剩余 {len(stocks) - i} 只股票的回填", "warning")
                break

            # 确定市场前缀
            code_str = stock.code
            if code_str.startswith("6"):
                tx_symbol = f"sh{code_str}"
            elif code_str.startswith(("0", "3")):
                tx_symbol = f"sz{code_str}"
            else:
                continue  # 跳过北交所和其他市场

            try:
                url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
                params = {"param": f"{tx_symbol},day,,,{days},qfq"}
                resp = req.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()

                data = resp.json()
                if data.get("code") != 0:
                    continue

                # 解析 K 线数据
                symbol_data = data.get("data", {}).get(tx_symbol, {})
                klines = symbol_data.get("qfqday") or symbol_data.get("day")
                if not klines:
                    continue

                inserted = 0
                for kline in klines:
                    # kline format: [date, open, close, high, low, volume, {}, change%, amount, ""]
                    if len(kline) < 6 or not isinstance(kline[0], str):
                        continue
                    try:
                        quote_date = pd.to_datetime(kline[0]).date()
                        if quote_date > today:
                            continue

                        existing = session.query(DailyQuote).filter_by(
                            code=stock.code, date=quote_date
                        ).first()
                        if existing:
                            continue

                        quote = DailyQuote(
                            code=stock.code,
                            date=quote_date,
                            open=float(kline[1]),
                            close=float(kline[2]),
                            high=float(kline[3]),
                            low=float(kline[4]),
                            volume=int(float(kline[5])),
                            turnover=0.0,  # 腾讯 API 不提供换手率
                        )
                        session.add(quote)
                        inserted += 1
                    except (ValueError, TypeError, IndexError):
                        continue

                if inserted > 0:
                    session.commit()
                    total_inserted += inserted
                    consecutive_failures = 0  # 成功，重置失败计数

                if (i + 1) % 200 == 0:
                    self._log(f"  回填进度: {i+1}/{len(stocks)}, 已插入 {total_inserted} 条")

            except Exception as e:
                is_conn = any(x in str(e) for x in ["Connection", "RemoteDisconnected", "reset", "Timeout"])
                if is_conn:
                    consecutive_failures += 1
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
