import numpy as np
import pandas as pd
from typing import Optional
from sqlalchemy.orm import Session
from src.models import DailyQuote, Fundamental


def calculate_technical(
    df: pd.DataFrame, config: dict
) -> dict:
    """
    计算技术面指标信号。

    df: 包含某只股票日线行情（按日期升序）的 DataFrame
    返回: 各指标信号和综合技术评分(0-100)
    """
    signals = {}
    total_score = 50.0  # 基准分

    indicators = config.get("indicators", {})

    # 均线系统
    if indicators.get("ma", {}).get("enabled", True):
        windows = indicators["ma"].get("windows", [5, 10, 20, 60])
        for w in windows:
            col = f"ma{w}"
            df[col] = df["close"].rolling(window=w).mean()

        latest = df.iloc[-1]
        # 多头排列判断: MA5 > MA10 > MA20 > MA60
        ma_values = [latest.get(f"ma{w}") for w in windows]
        if all(ma_values):
            is_bullish = all(ma_values[i] > ma_values[i + 1] for i in range(len(ma_values) - 1))
            is_bearish = all(ma_values[i] < ma_values[i + 1] for i in range(len(ma_values) - 1))
            if is_bullish:
                signals["ma"] = "bullish"
                total_score += 15
            elif is_bearish:
                signals["ma"] = "bearish"
                total_score -= 15
            else:
                signals["ma"] = "neutral"

    # MACD
    if indicators.get("macd", {}).get("enabled", True):
        fast = indicators["macd"].get("fast", 12)
        slow = indicators["macd"].get("slow", 26)
        signal = indicators["macd"].get("signal", 9)

        exp12 = df["close"].ewm(span=fast, adjust=False).mean()
        exp26 = df["close"].ewm(span=slow, adjust=False).mean()
        macd_line = exp12 - exp26
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        if len(histogram) >= 2:
            # 金叉: MACD 上穿信号线
            if histogram.iloc[-2] < 0 and histogram.iloc[-1] >= 0:
                signals["macd"] = "golden_cross"
                total_score += 15
            elif histogram.iloc[-2] > 0 and histogram.iloc[-1] <= 0:
                signals["macd"] = "dead_cross"
                total_score -= 15
            else:
                signals["macd"] = "neutral"

    # RSI
    if indicators.get("rsi", {}).get("enabled", True):
        period = indicators["rsi"].get("period", 14)
        overbought = indicators["rsi"].get("overbought", 70)
        oversold = indicators["rsi"].get("oversold", 30)

        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta.where(delta < 0, 0.0))
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        latest_rsi = rsi.iloc[-1]
        if latest_rsi > overbought:
            signals["rsi"] = "overbought"
            total_score -= 10
        elif latest_rsi < oversold:
            signals["rsi"] = "oversold"
            total_score += 10
        else:
            signals["rsi"] = "normal"

    # KDJ
    if indicators.get("kdj", {}).get("enabled", True):
        low_n = df["low"].rolling(window=9).min()
        high_n = df["high"].rolling(window=9).max()
        rsv = (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d

        if len(k) >= 2:
            if k.iloc[-2] < d.iloc[-2] and k.iloc[-1] > d.iloc[-1]:
                signals["kdj"] = "golden_cross"
                total_score += 10
            elif k.iloc[-2] > d.iloc[-2] and k.iloc[-1] < d.iloc[-1]:
                signals["kdj"] = "dead_cross"
                total_score -= 10
            else:
                signals["kdj"] = "neutral"

    # 钳制分数到 0-100
    total_score = max(0, min(100, total_score))

    return {
        "signals": signals,
        "score": round(total_score, 2),
    }


def calculate_fundamental(
    fundamental: Fundamental, config: dict
) -> dict:
    """计算基本面评分"""
    f_cfg = config.get("fundamental", {})
    pe_max = f_cfg.get("pe_max", 50)
    pb_max = f_cfg.get("pb_max", 10)
    roe_min = f_cfg.get("roe_min", 15)
    npg_min = f_cfg.get("net_profit_growth_min", 10)

    pe_score = 1 if (fundamental.pe is not None and 0 < fundamental.pe <= pe_max) else 0
    pb_score = 1 if (fundamental.pb is not None and 0 < fundamental.pb <= pb_max) else 0
    roe_score = 1 if (fundamental.roe is not None and fundamental.roe >= roe_min) else 0
    npg_score = 1 if (fundamental.net_profit_growth is not None and fundamental.net_profit_growth >= npg_min) else 0

    total = pe_score + pb_score + roe_score + npg_score

    return {
        "pe_score": pe_score,
        "pb_score": pb_score,
        "roe_score": roe_score,
        "net_profit_growth_score": npg_score,
        "total": total,
        "max": 4,
    }


def calculate_score(
    technical: dict, fundamental: dict, config: dict
) -> float:
    """综合评分 (0-100)"""
    tw = config.get("technical_weight", 0.5)
    fw = config.get("fundamental_weight", 0.5)

    tech_norm = technical["score"] / 100.0
    fund_norm = fundamental["total"] / fundamental["max"] if fundamental["max"] > 0 else 0

    score = (tech_norm * tw + fund_norm * fw) * 100
    return round(score, 2)


def run_analysis(session: Session, config: dict, logger=None) -> list:
    """
    对当日所有有数据的股票运行分析。
    返回: AnalysisResult 对象列表
    """
    from src.models import AnalysisResult
    from datetime import date

    today = date.today()

    # 获取所有有行情数据的股票
    stocks = session.query(DailyQuote.code).distinct().all()
    results = []

    for (code,) in stocks:
        # 获取日线数据（用于技术面）
        quotes = (
            session.query(DailyQuote)
            .filter_by(code=code)
            .order_by(DailyQuote.date)
            .all()
        )
        if len(quotes) < 20:  # 至少 20 个交易日才有意义
            continue

        df = pd.DataFrame(
            [(q.date, q.open, q.close, q.high, q.low, q.volume, q.turnover)
             for q in quotes],
            columns=["date", "open", "close", "high", "low", "volume", "turnover"],
        )

        technical = calculate_technical(df, config)

        # 获取基本面数据
        fundamental_row = (
            session.query(Fundamental)
            .filter_by(code=code)
            .order_by(Fundamental.date.desc())
            .first()
        )

        if fundamental_row:
            fundamental = calculate_fundamental(fundamental_row, config)
        else:
            fundamental = {"total": 0, "max": 4}

        score = calculate_score(technical, fundamental, config)

        result = AnalysisResult(
            date=today,
            code=code,
            score=score,
            signals={
                "technical": technical["signals"],
                "fundamental": fundamental if fundamental_row else None,
            },
        )
        session.add(result)
        results.append(result)

    session.commit()
    if logger:
        logger.info(f"分析完成: {len(results)} 只股票")
    return results
