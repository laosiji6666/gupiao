# 股票分析工具 Phase 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现每晚自动从 AkShare 获取 A 股数据、运行技术面和基本面分析、生成 CSV/HTML 报告的核心链路。

**Architecture:** 分层模块化设计，data-fetcher 负责数据获取与入库，analyzer 负责指标计算与评分，二者通过 SQLite 数据库解耦。APScheduler 每晚定时触发全流程。

**Tech Stack:** Python 3.10+, akshare, pandas, TA-Lib, SQLAlchemy, APScheduler, SQLite

## Global Constraints

- 数据库使用 SQLite（data/stock_analyzer.db）
- 所有配置集中在 config.yaml，运行时通过 utils/config.py 加载
- 技术面指标使用 TA-Lib 计算
- 数据源为 akshare（A 股）
- 日志输出到控制台 + 文件 logs/analyzer.log
- 所有代码放在 src/ 目录下，测试放在 tests/ 目录下

---

## File Structure

```
stock-analyzer/
├── config.yaml                    # 全局配置
├── main.py                        # 入口（调度器）
├── requirements.txt
├── data/
│   └── stock_analyzer.db          # SQLite 数据库（运行时自动创建）
├── logs/
│   └── analyzer.log               # 运行日志（运行时自动创建）
├── src/
│   ├── __init__.py
│   ├── models.py                  # SQLAlchemy 数据库模型
│   ├── fetcher.py                 # AkShare 数据获取
│   ├── analyzer.py                # 技术面+基本面分析引擎
│   └── report.py                  # 报告生成（CSV + HTML）
├── utils/
│   ├── __init__.py
│   ├── config.py                  # YAML 配置加载
│   └── logger.py                  # 日志配置
└── tests/
    ├── __init__.py
    ├── test_fetcher.py
    ├── test_analyzer.py
    ├── test_models.py
    └── test_report.py
```

---

### Task 1: 项目初始化与环境配置

**Files:**
- Create: `stock-analyzer/requirements.txt`
- Create: `stock-analyzer/config.yaml`
- Create: `stock-analyzer/src/__init__.py`
- Create: `stock-analyzer/utils/__init__.py`
- Create: `stock-analyzer/utils/config.py`
- Create: `stock-analyzer/utils/logger.py`

**Interfaces:**
- Consumes: (none — bootstrapping)
- Produces: `load_config() -> dict` — 返回解析后的配置字典
- Produces: `setup_logger(name: str) -> logging.Logger` — 返回配置好的 logger 实例

- [ ] **Step 1: 创建项目目录结构**

```bash
cd d:/AI/superpowers
mkdir -p stock-analyzer/{src,utils,tests,data,logs}
```

- [ ] **Step 2: 创建 requirements.txt**

```text
akshare>=1.16.0
pandas>=2.0.0
numpy>=1.24.0
SQLAlchemy>=2.0.0
PyYAML>=6.0
APScheduler>=3.10.0
TA-Lib>=0.4.28
```

- [ ] **Step 3: 创建配置文件和加载模块**

```yaml
# config.yaml
database:
  url: "sqlite:///data/stock_analyzer.db"

schedule:
  hour: 18
  minute: 0

analyzer:
  technical_weight: 0.4
  fundamental_weight: 0.6
  indicators:
    ma:
      enabled: true
      windows: [5, 10, 20, 60]
    macd:
      enabled: true
      fast: 12
      slow: 26
      signal: 9
    rsi:
      enabled: true
      period: 14
      overbought: 70
      oversold: 30
    kdj:
      enabled: true
  fundamental:
    pe_max: 50
    pb_max: 10
    roe_min: 15
    net_profit_growth_min: 10

report:
  top_n: 30
  output_dir: "reports"
```

```python
# utils/config.py
import yaml
from pathlib import Path


def load_config(path: str = "config.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path.resolve()}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

```python
# utils/logger.py
import logging
from pathlib import Path


def setup_logger(name: str = "stock-analyzer") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / "analyzer.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
```

- [ ] **Step 4: 验证配置加载**

```bash
cd d:/AI/superpowers/stock-analyzer
python -c "from utils.config import load_config; cfg = load_config('config.yaml'); print(cfg['database'])"
```

Expected: `{'url': 'sqlite:///data/stock_analyzer.db'}`

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "chore: initialize project structure and config"
```

---

### Task 2: 数据库模型

**Files:**
- Create: `stock-analyzer/src/models.py`
- Create: `stock-analyzer/tests/__init__.py`
- Create: `stock-analyzer/tests/test_models.py`

**Interfaces:**
- Consumes: `load_config()` from utils/config
- Produces: `Base`, `StockList`, `DailyQuote`, `Fundamental`, `AnalysisResult` — SQLAlchemy 模型类
- Produces: `init_db(engine) -> None` — 创建所有表

- [ ] **Step 1: 写测试（TDD）**

```python
# tests/test_models.py
import pytest
from sqlalchemy import create_engine
from src.models import Base, StockList, DailyQuote, Fundamental, AnalysisResult


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


def test_create_tables(engine):
    Base.metadata.create_all(engine)
    # Verify no exception means tables created
    assert True


def test_stock_list_model(engine):
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    with Session(engine) as session:
        stock = StockList(code="600519", name="贵州茅台", industry="食品饮料", market="沪市")
        session.add(stock)
        session.commit()
        retrieved = session.query(StockList).filter_by(code="600519").first()
        assert retrieved is not None
        assert retrieved.name == "贵州茅台"


def test_daily_quote_model(engine):
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    from datetime import date
    with Session(engine) as session:
        quote = DailyQuote(
            code="600519", date=date(2026, 6, 26),
            open=1500.0, close=1510.0, high=1520.0, low=1490.0,
            volume=5000000, turnover=0.5
        )
        session.add(quote)
        session.commit()
        q = session.query(DailyQuote).filter_by(code="600519").first()
        assert q.close == 1510.0


def test_fundamental_model(engine):
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    from datetime import date
    with Session(engine) as session:
        f = Fundamental(
            code="600519", date=date(2026, 6, 26),
            pe=25.0, pb=6.0, roe=30.0, net_profit_growth=15.0
        )
        session.add(f)
        session.commit()
        r = session.query(Fundamental).first()
        assert r.roe == 30.0


def test_analysis_result_model(engine):
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    from datetime import date
    with Session(engine) as session:
        ar = AnalysisResult(
            date=date(2026, 6, 26), code="600519",
            score=85.0, signals={"ma": "bullish", "macd": "golden_cross"}
        )
        session.add(ar)
        session.commit()
        r = session.query(AnalysisResult).first()
        assert r.score == 85.0
        assert r.signals["macd"] == "golden_cross"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_models.py -v
```

Expected: ImportError/ModuleNotFoundError 因为模型还没创建

- [ ] **Step 3: 创建数据库模型**

```python
# src/models.py
from datetime import date, datetime
from sqlalchemy import (
    Column, String, Date, DateTime, Integer, Float, JSON,
    create_engine, PrimaryKeyConstraint
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class StockList(Base):
    __tablename__ = "stock_list"

    code = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    industry = Column(String(50))
    market = Column(String(10))

    def __repr__(self):
        return f"<StockList(code={self.code}, name={self.name})>"


class DailyQuote(Base):
    __tablename__ = "daily_quotes"

    code = Column(String(10), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Integer)
    turnover = Column(Float)

    __table_args__ = (
        PrimaryKeyConstraint("code", "date"),
    )


class Fundamental(Base):
    __tablename__ = "fundamentals"

    code = Column(String(10), nullable=False)
    date = Column(Date, nullable=False)
    pe = Column(Float)
    pb = Column(Float)
    roe = Column(Float)
    net_profit_growth = Column(Float)

    __table_args__ = (
        PrimaryKeyConstraint("code", "date"),
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    code = Column(String(10), nullable=False)
    score = Column(Float)
    signals = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db(engine):
    Base.metadata.create_all(engine)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_models.py -v
```

Expected: 5 tests passed

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: add database models"
```

---

### Task 3: 数据获取模块（data-fetcher）

**Files:**
- Create: `stock-analyzer/src/fetcher.py`
- Create: `stock-analyzer/tests/test_fetcher.py`

**Interfaces:**
- Consumes: `StockList`, `DailyQuote`, `Fundamental` from src.models; `load_config()`; `setup_logger()`
- Consumes: `init_db(engine)` from src.models
- Produces: `fetch_stock_list(session) -> int` — 获取股票列表并入库，返回数量
- Produces: `fetch_daily_quotes(session, trade_date) -> int` — 获取指定日期行情，返回数量
- Produces: `fetch_fundamentals(session, trade_date) -> int` — 获取基本面数据，返回数量
- Produces: `Fetcher` — 封装上述三个操作的类，构造函数接收 `config` 和 `logger`

- [ ] **Step 1: 创建 fetcher 模块**

```python
# src/fetcher.py
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
```

- [ ] **Step 2: 创建测试（mock akshare）**

```python
# tests/test_fetcher.py
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base, StockList, DailyQuote, Fundamental
from src.fetcher import Fetcher


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def fetcher():
    return Fetcher({"database": {"url": "sqlite:///:memory:"}})


def test_detect_market_sh(fetcher):
    assert fetcher._detect_market("600519") == "沪市"


def test_detect_market_sz(fetcher):
    assert fetcher._detect_market("000001") == "深市"


def test_detect_market_bj(fetcher):
    assert fetcher._detect_market("830000") == "北市"


@patch("src.fetcher.ak.stock_info_a_code_name")
def test_fetch_stock_list(mock_stock_list, fetcher, session):
    mock_stock_list.return_value = pd.DataFrame([
        {"code": "600519", "name": "贵州茅台"},
        {"code": "000001", "name": "平安银行"},
    ])
    count = fetcher.fetch_stock_list(session)
    assert count == 2
    assert session.query(StockList).count() == 2


def test_fetch_stock_list_dedup(fetcher, session):
    session.add(StockList(code="600519", name="贵州茅台", industry="", market="沪市"))
    session.commit()
    with patch("src.fetcher.ak.stock_info_a_code_name") as mock:
        mock.return_value = pd.DataFrame([
            {"code": "600519", "name": "贵州茅台"},
            {"code": "000001", "name": "平安银行"},
        ])
        count = fetcher.fetch_stock_list(session)
    assert count == 1  # only new one
    assert session.query(StockList).count() == 2
```

- [ ] **Step 3: 运行测试**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_fetcher.py -v
```

Expected: Tests pass

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: add A-share data fetcher via akshare"
```

---

### Task 4: 分析引擎（analyzer）— 技术面指标

**Files:**
- Create: `stock-analyzer/src/analyzer.py`
- Create: `stock-analyzer/tests/test_analyzer.py`

**Interfaces:**
- Consumes: `DailyQuote` from src.models; `config["analyzer"]` from config; `setup_logger()`
- Produces: `calculate_technical(session, code, config) -> dict` — 返回技术面信号字典
- Produces: `calculate_fundamental(fundamental_row, config) -> dict` — 返回基本面评分字典
- Produces: `calculate_score(technical, fundamental, config) -> float` — 综合评分

- [ ] **Step 1: 写测试（TDD）**

```python
# tests/test_analyzer.py
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base, DailyQuote, Fundamental
from src.analyzer import (
    calculate_technical,
    calculate_fundamental,
    calculate_score,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def config():
    return {
        "technical_weight": 0.4,
        "fundamental_weight": 0.6,
        "indicators": {
            "ma": {"enabled": True, "windows": [5, 10, 20, 60]},
            "macd": {"enabled": True, "fast": 12, "slow": 26, "signal": 9},
            "rsi": {"enabled": True, "period": 14, "overbought": 70, "oversold": 30},
            "kdj": {"enabled": True},
        },
        "fundamental": {
            "pe_max": 50,
            "pb_max": 10,
            "roe_min": 15,
            "net_profit_growth_min": 10,
        },
    }


def test_calculate_fundamental_all_good(config):
    """所有基本面指标达标"""
    f = MagicMock()
    f.pe = 20.0
    f.pb = 3.0
    f.roe = 25.0
    f.net_profit_growth = 20.0
    result = calculate_fundamental(f, config)
    assert result["pe_score"] == 1
    assert result["pb_score"] == 1
    assert result["roe_score"] == 1
    assert result["net_profit_growth_score"] == 1
    assert result["total"] == 4.0


def test_calculate_fundamental_all_bad(config):
    """所有基本面指标不达标"""
    f = MagicMock()
    f.pe = 100.0
    f.pb = 20.0
    f.roe = 5.0
    f.net_profit_growth = -10.0
    result = calculate_fundamental(f, config)
    assert result["pe_score"] == 0
    assert result["pb_score"] == 0
    assert result["roe_score"] == 0
    assert result["net_profit_growth_score"] == 0
    assert result["total"] == 0.0


def test_calculate_score(config):
    technical = {"score": 80.0}
    fundamental = {"total": 3.0}
    score = calculate_score(technical, fundamental, config)
    # technical_weight=0.4, fundamental_weight=0.6
    # technical: 80/100 * 0.4 = 0.32
    # fundamental: 3/4 * 0.6 = 0.45
    # total: 0.77 * 100 = 77
    assert abs(score - 77.0) < 0.01
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_analyzer.py -v
```

Expected: ImportError — analyzer.py 还不存在

- [ ] **Step 3: 创建分析引擎模块**

```python
# src/analyzer.py
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
```

- [ ] **Step 4: 运行测试**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_analyzer.py -v
```

Expected: Tests pass

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: add analysis engine with technical and fundamental scoring"
```

---

### Task 5: 报告生成模块

**Files:**
- Create: `stock-analyzer/src/report.py`
- Create: `stock-analyzer/tests/test_report.py`

**Interfaces:**
- Consumes: `AnalysisResult`, `StockList` from src.models; `load_config()`; `setup_logger()`
- Produces: `generate_csv(session, date, output_path) -> str` — 生成 CSV 报告，返回文件路径
- Produces: `generate_html(session, date, config, output_path) -> str` — 生成 HTML 报告，返回文件路径

- [ ] **Step 1: 写测试**

```python
# tests/test_report.py
import pytest
import json
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models import Base, AnalysisResult, StockList
from src.report import generate_csv, generate_html
from pathlib import Path


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(StockList(code="600519", name="贵州茅台", industry="食品饮料", market="沪市"))
        s.add(StockList(code="000001", name="平安银行", industry="银行", market="深市"))
        s.add(AnalysisResult(
            date=date(2026, 6, 26), code="600519",
            score=85.0, signals={"technical": {"ma": "bullish"}}
        ))
        s.add(AnalysisResult(
            date=date(2026, 6, 26), code="000001",
            score=72.0, signals={"technical": {"ma": "neutral"}}
        ))
        s.commit()
        yield s


def test_generate_csv(session, tmp_path):
    output = tmp_path / "test_report.csv"
    path = generate_csv(session, date(2026, 6, 26), str(output))
    assert Path(path).exists()
    content = Path(path).read_text(encoding="utf-8")
    assert "600519" in content
    assert "85.0" in content
    assert "贵州茅台" in content


def test_generate_html(session, tmp_path):
    output = tmp_path / "test_report.html"
    path = generate_html(session, date(2026, 6, 26), str(output))
    assert Path(path).exists()
    content = Path(path).read_text(encoding="utf-8")
    assert "贵州茅台" in content
    assert "85.0" in content
    assert "600519" in content
    assert "html" in content.lower()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_report.py -v
```

Expected: ImportError — report.py 还不存在

- [ ] **Step 3: 创建报告生成模块**

```python
# src/report.py
from datetime import date
from pathlib import Path
from sqlalchemy.orm import Session
from src.models import AnalysisResult, StockList


def generate_csv(
    session: Session, report_date: date, output_path: str
) -> str:
    """生成 CSV 格式的选股报告"""
    results = _get_results(session, report_date)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["排名", "股票代码", "股票名称", "行业", "综合评分"])
        for i, (ar, stock) in enumerate(results, 1):
            writer.writerow([
                i, ar.code, stock.name if stock else "",
                stock.industry if stock else "", ar.score,
            ])

    return str(path)


def generate_html(
    session: Session, report_date: date, output_path: str,
    top_n: int = 30,
) -> str:
    """生成 HTML 格式的选股报告"""
    results = _get_results(session, report_date)
    results = results[:top_n]

    rows_html = ""
    for i, (ar, stock) in enumerate(results, 1):
        signals = ar.signals or {}
        tech = signals.get("technical", {})
        signal_str = " | ".join(
            f"{k}: {v}" for k, v in tech.items()
        ) if tech else "—"
        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>{ar.code}</td>
            <td>{stock.name if stock else '—'}</td>
            <td>{stock.industry if stock else '—'}</td>
            <td class="score">{ar.score}</td>
            <td>{signal_str}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>股票分析报告 - {report_date}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #4a90d9; color: white; }}
        tr:hover {{ background: #f0f7ff; }}
        .score {{ font-weight: bold; color: #e67e22; }}
        .footer {{ margin-top: 20px; color: #999; font-size: 12px; text-align: center; }}
    </style>
</head>
<body>
    <h1>📊 股票分析报告</h1>
    <p>报告日期: {report_date} | 共 {len(results)} 只股票</p>
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>代码</th>
                <th>名称</th>
                <th>行业</th>
                <th>综合评分</th>
                <th>技术信号</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    <div class="footer">由自动化股票分析工具生成</div>
</body>
</html>"""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


def _get_results(session: Session, report_date: date) -> list:
    """获取某日分析结果，按评分降序排列"""
    results = (
        session.query(AnalysisResult)
        .filter_by(date=report_date)
        .order_by(AnalysisResult.score.desc())
        .all()
    )
    output = []
    for ar in results:
        stock = session.query(StockList).filter_by(code=ar.code).first()
        output.append((ar, stock))
    return output
```

- [ ] **Step 4: 运行测试**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/test_report.py -v
```

Expected: Tests pass

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: add CSV and HTML report generation"
```

---

### Task 6: 定时调度入口

**Files:**
- Create: `stock-analyzer/main.py`

**Interfaces:**
- Consumes: 所有模块
- Produces: 可运行的入口点

- [ ] **Step 1: 创建 main.py**

```python
# main.py
"""
股票分析工具 — 入口点

每晚定时执行:
  1. 获取股票列表（首次运行）
  2. 获取当日行情
  3. 获取基本面数据
  4. 运行分析
  5. 生成报告
"""
from datetime import date, datetime
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from utils.config import load_config
from utils.logger import setup_logger
from src.models import init_db
from src.fetcher import Fetcher
from src.analyzer import run_analysis
from src.report import generate_csv, generate_html


def run_pipeline(config: dict, logger):
    """执行一次完整的数据获取→分析→报告流程"""
    logger.info("=" * 50)
    logger.info("开始每日分析流程")
    logger.info("=" * 50)

    db_url = config["database"]["url"]
    engine = create_engine(db_url)
    init_db(engine)

    fetcher = Fetcher(config, logger)
    today = date.today()

    with Session(engine) as session:
        # 1. 获取股票列表（仅首次运行补数据）
        from src.models import StockList
        stock_count = session.query(StockList).count()
        if stock_count == 0:
            fetcher.fetch_stock_list(session)

        # 2. 获取日线行情
        logger.info(f"拉取 {today} 行情数据...")
        fetcher.fetch_daily_quotes(session, today)

        # 3. 获取基本面数据
        logger.info("拉取基本面数据...")
        fetcher.fetch_fundamentals(session, today)

    # 4. 运行分析（另开 session 避免过期数据）
    with Session(engine) as session:
        logger.info("运行分析引擎...")
        results = run_analysis(session, config, logger)
        logger.info(f"分析完成: {len(results)} 只股票")

    # 5. 生成报告
    with Session(engine) as session:
        report_dir = config.get("report", {}).get("output_dir", "reports")
        top_n = config.get("report", {}).get("top_n", 30)
        date_str = today.strftime("%Y%m%d")

        csv_path = generate_csv(session, today, f"{report_dir}/{date_str}_ranking.csv")
        html_path = generate_html(session, today, f"{report_dir}/{date_str}_ranking.html", top_n)
        logger.info(f"报告已生成: {csv_path}")
        logger.info(f"报告已生成: {html_path}")

    logger.info("每日分析流程完成 ✓")


def main():
    config = load_config()
    logger = setup_logger()

    logger.info("股票分析工具启动")
    logger.info(f"调度时间: 每日 {config['schedule']['hour']}:{config['schedule']['minute']:02d}")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        "cron",
        hour=config["schedule"]["hour"],
        minute=config["schedule"]["minute"],
        args=[config, logger],
    )

    # 首次启动立即执行一次
    run_pipeline(config, logger)

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("调度器已停止")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 手动测试运行**

```bash
cd d:/AI/superpowers/stock-analyzer
python main.py
```

Expected: 程序运行，打印日志，生成 data/stock_analyzer.db 和 reports/ 下的报告

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: add scheduler and main entry point"
```

---

### Task 7: 安装依赖和最终验证

**Files:** (无需创建，只需运行命令)

- [ ] **Step 1: 安装 Python 依赖**

```bash
cd d:/AI/superpowers/stock-analyzer
pip install -r requirements.txt
```

- [ ] **Step 2: 运行完整测试**

```bash
cd d:/AI/superpowers/stock-analyzer
python -m pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 3: 运行完整流程**

```bash
cd d:/AI/superpowers/stock-analyzer
python main.py
```

Expected: 程序成功运行，输出日志，生成报告文件

- [ ] **Step 4: 最终提交**

```bash
git add -A && git commit -m "chore: finalize phase 1 setup"
```
