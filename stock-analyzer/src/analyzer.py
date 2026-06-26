import numpy as np
import pandas as pd
import talib
from sqlalchemy.orm import Session
from src.models import DailyQuote, Fundamental


def calculate_technical(df: pd.DataFrame, config: dict) -> dict:
    signals = {}
    total_score = 50.0

    # Read from config["analyzer"]["indicators"]
    analyzer_cfg = config.get("analyzer", config)  # support both structures
    indicators = analyzer_cfg.get("indicators", {})

    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)

    # MA
    ma_cfg = indicators.get("ma", {})
    if ma_cfg.get("enabled", True):
        windows = ma_cfg.get("windows", [5, 10, 20, 60])
        ma_values = []
        for w in windows:
            ma = talib.SMA(close, timeperiod=w)
            ma_values.append(ma[-1] if not np.isnan(ma[-1]) else None)

        valid = [v for v in ma_values if v is not None]
        if len(valid) == len(windows):
            is_bullish = all(valid[i] > valid[i+1] for i in range(len(valid)-1))
            is_bearish = all(valid[i] < valid[i+1] for i in range(len(valid)-1))
            if is_bullish:
                signals["ma"] = "bullish"
                total_score += 15
            elif is_bearish:
                signals["ma"] = "bearish"
                total_score -= 15
            else:
                signals["ma"] = "neutral"
        else:
            signals["ma"] = "neutral"

    # MACD - using signal-line crossover (not histogram zero-crossing)
    macd_cfg = indicators.get("macd", {})
    if macd_cfg.get("enabled", True):
        macd_line, signal_line, hist = talib.MACD(
            close,
            fastperiod=macd_cfg.get("fast", 12),
            slowperiod=macd_cfg.get("slow", 26),
            signalperiod=macd_cfg.get("signal", 9),
        )
        if len(macd_line) >= 2 and not np.isnan(macd_line[-1]) and not np.isnan(macd_line[-2]):
            # Golden cross: MACD line crosses ABOVE signal line
            prev_diff = macd_line[-2] - signal_line[-2]
            curr_diff = macd_line[-1] - signal_line[-1]
            if prev_diff < 0 and curr_diff >= 0:
                signals["macd"] = "golden_cross"
                total_score += 15
            elif prev_diff > 0 and curr_diff <= 0:
                signals["macd"] = "dead_cross"
                total_score -= 15
            else:
                signals["macd"] = "neutral"
        else:
            signals["macd"] = "neutral"

    # RSI
    rsi_cfg = indicators.get("rsi", {})
    if rsi_cfg.get("enabled", True):
        rsi = talib.RSI(close, timeperiod=rsi_cfg.get("period", 14))
        latest_rsi = rsi[-1]
        if not np.isnan(latest_rsi):
            overbought = rsi_cfg.get("overbought", 70)
            oversold = rsi_cfg.get("oversold", 30)
            if latest_rsi > overbought:
                signals["rsi"] = "overbought"
                total_score -= 10
            elif latest_rsi < oversold:
                signals["rsi"] = "oversold"
                total_score += 10
            else:
                signals["rsi"] = "normal"
        else:
            signals["rsi"] = "neutral"

    # KDJ (Stochastic)
    kdj_cfg = indicators.get("kdj", {})
    if kdj_cfg.get("enabled", True):
        slowk, slowd = talib.STOCH(
            high, low, close,
            fastk_period=9,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )
        if len(slowk) >= 2 and not np.isnan(slowk[-1]) and not np.isnan(slowk[-2]):
            if slowk[-2] < slowd[-2] and slowk[-1] > slowd[-1]:
                signals["kdj"] = "golden_cross"
                total_score += 10
            elif slowk[-2] > slowd[-2] and slowk[-1] < slowd[-1]:
                signals["kdj"] = "dead_cross"
                total_score -= 10
            else:
                signals["kdj"] = "neutral"
        else:
            signals["kdj"] = "neutral"

    total_score = max(0, min(100, total_score))
    return {"signals": signals, "score": round(total_score, 2)}


def calculate_fundamental(
    fundamental: Fundamental, config: dict
) -> dict:
    """计算基本面评分"""
    analyzer_cfg = config.get("analyzer", config)
    f_cfg = analyzer_cfg.get("fundamental", {})
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
    analyzer_cfg = config.get("analyzer", config)
    tw = analyzer_cfg.get("technical_weight", 0.5)
    fw = analyzer_cfg.get("fundamental_weight", 0.5)

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
        if len(quotes) < 1:  # 至少有 1 天数据即可分析
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
