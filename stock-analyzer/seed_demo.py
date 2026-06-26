"""生成演示数据，以便展示 Web 界面"""
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base, StockList, DailyQuote, Fundamental, AnalysisResult

DB_URL = "sqlite:///data/stock_analyzer.db"
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)

stocks = [
    ("600519", "贵州茅台", "食品饮料", "沪市"),
    ("000858", "五粮液", "食品饮料", "深市"),
    ("600036", "招商银行", "银行", "沪市"),
    ("601166", "兴业银行", "银行", "沪市"),
    ("000333", "美的集团", "家用电器", "深市"),
    ("000651", "格力电器", "家用电器", "深市"),
    ("600276", "恒瑞医药", "医药生物", "沪市"),
    ("300750", "宁德时代", "电力设备", "深市"),
    ("000001", "平安银行", "银行", "深市"),
    ("002415", "海康威视", "计算机", "深市"),
    ("601318", "中国平安", "非银金融", "沪市"),
    ("600887", "伊利股份", "食品饮料", "沪市"),
    ("000725", "京东方A", "电子", "深市"),
    ("600309", "万华化学", "基础化工", "沪市"),
    ("002594", "比亚迪", "汽车", "深市"),
]

with Session(engine) as session:
    # 清空旧数据
    session.query(AnalysisResult).delete()
    session.query(Fundamental).delete()
    session.query(DailyQuote).delete()
    session.query(StockList).delete()
    session.commit()

    # 插入股票列表
    for code, name, industry, market in stocks:
        session.add(StockList(code=code, name=name, industry=industry, market=market))
    session.commit()
    print(f"已插入 {len(stocks)} 只股票基本信息")

    # 生成 30 天日线行情
    base_date = date(2026, 6, 26)
    import random
    random.seed(42)
    base_prices = {
        "600519": 1500, "000858": 140, "600036": 38, "601166": 18,
        "000333": 65, "000651": 40, "600276": 45, "300750": 220,
        "000001": 12, "002415": 35, "601318": 52, "600887": 28,
        "000725": 4.5, "600309": 85, "002594": 260,
    }
    count_quotes = 0
    for code, _, _, _ in stocks:
        price = base_prices[code]
        for i in range(60):
            d = base_date - timedelta(days=59 - i)
            if d.weekday() >= 5:
                continue  # skip weekends
            change = random.gauss(0, price * 0.02)
            close = price + change
            high = close * (1 + abs(random.gauss(0, 0.01)))
            low = close * (1 - abs(random.gauss(0, 0.01)))
            session.add(DailyQuote(
                code=code, date=d,
                open=close * (1 + random.gauss(0, 0.005)),
                close=round(close, 2),
                high=round(high, 2),
                low=round(low, 2),
                volume=random.randint(100000, 5000000),
                turnover=round(random.uniform(0.5, 5), 2),
            ))
            price = close
            count_quotes += 1
    session.commit()
    print(f"已插入 {count_quotes} 条日线行情")

    # 插入基本面数据
    fundamentals = [
        ("600519", 25, 6, 30.0, 15.0),
        ("000858", 20, 5, 25.0, 12.0),
        ("600036", 8, 1.2, 16.0, 8.0),
        ("601166", 6, 0.8, 14.0, 6.0),
        ("000333", 14, 3, 22.0, 10.0),
        ("000651", 12, 2.5, 20.0, 5.0),
        ("600276", 55, 8, 18.0, 20.0),
        ("300750", 35, 7, 28.0, 35.0),
        ("000001", 7, 0.9, 12.0, 3.0),
        ("002415", 25, 5, 24.0, 15.0),
        ("601318", 10, 1.5, 18.0, 8.0),
        ("600887", 22, 4, 26.0, 11.0),
        ("000725", 40, 1.8, 8.0, 2.0),
        ("600309", 18, 3.5, 20.0, 14.0),
        ("002594", 30, 6, 15.0, 25.0),
    ]
    for code, pe, pb, roe, npg in fundamentals:
        session.add(Fundamental(
            code=code, date=base_date,
            pe=pe, pb=pb, roe=roe, net_profit_growth=npg,
        ))
    session.commit()
    print(f"已插入 {len(fundamentals)} 条基本面数据")

    # 插入 7 天分析结果
    for days_back in range(7, -1, -1):
        d = base_date - timedelta(days=days_back)
        if d.weekday() >= 5:
            continue
        for code, _, _, _ in stocks:
            score = round(random.uniform(40, 95), 1)
            signals = {"ma": random.choice(["bullish", "bearish", "neutral"])}
            session.add(AnalysisResult(
                date=d, code=code, score=score,
                signals={"technical": signals},
            ))
    session.commit()
    print("已插入分析结果数据")

print("\n✅ 演示数据生成完成！")
print(f"运行: cd stock-analyzer && python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000")
