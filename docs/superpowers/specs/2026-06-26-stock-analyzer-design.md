# 自动化股票分析工具 — 设计文档

## 概述

每晚自动从 AkShare 获取 A 股交易数据，结合技术面和基本面分析方法筛选有投资价值的股票，通过多通道通知推送结果，并提供 Web 界面查看历史分析。

## 架构概览

```
┌──────────────────────────────────────────────────┐
│                  scheduler                        │
│          (APScheduler - 每晚定时触发)              │
└──────────┬──────────────┬────────────┬───────────┘
           │              │            │
     ┌─────▼──────┐ ┌────▼────┐ ┌────▼──────┐
     │ data-fetcher│ │analyzer │ │ notifier   │
     │ (AkShare)   │ │(TA-Lib +│ │(push alerts)│
     │             │ │ 基本面)  │ │            │
     └─────┬──────┘ └────┬────┘ └────┬──────┘
           │              │            │
           └──────────────┼────────────┘
                          ▼
                   ┌──────────────┐
                   │     DB       │
                   │  (SQLite →   │
                   │  PostgreSQL) │
                   └──────────────┘
                          ▲
                   ┌──────┴───────┐
                   │    web       │
                   │  (FastAPI    │
                   │   + 简单前端) │
                   └──────────────┘
```

## 分阶段路线

| 阶段 | 模块 | 产出 |
|---|---|---|
| 阶段 1 | data-fetcher + analyzer | 每日拉取→分析→生成报告 |
| 阶段 2 | notifier | 推送分析结果到钉钉/邮件等 |
| 阶段 3 | web | 浏览器查看历史分析、筛选记录 |

## 数据库设计

### stock_list — 股票基本信息

| 字段 | 类型 | 说明 |
|---|---|---|
| code | TEXT PK | 股票代码 |
| name | TEXT | 股票名称 |
| industry | TEXT | 所属行业 |
| market | TEXT | 市场（沪/深/北） |

### daily_quotes — 日线行情

| 字段 | 类型 | 说明 |
|---|---|---|
| code | TEXT | 股票代码 |
| date | DATE | 交易日 |
| open | DECIMAL | 开盘价 |
| close | DECIMAL | 收盘价 |
| high | DECIMAL | 最高价 |
| low | DECIMAL | 最低价 |
| volume | BIGINT | 成交量 |
| turnover | DECIMAL | 换手率 |
| PK | (code, date) | |

### fundamentals — 基本面快照

| 字段 | 类型 | 说明 |
|---|---|---|
| code | TEXT | 股票代码 |
| date | DATE | 数据日期 |
| pe | DECIMAL | 市盈率 |
| pb | DECIMAL | 市净率 |
| roe | DECIMAL | 净资产收益率 |
| net_profit_growth | DECIMAL | 净利润增长率 |
| PK | (code, date) | |

### analysis_results — 分析结果

| 字段 | 类型 | 说明 |
|---|---|---|
| id | SERIAL PK | 自增主键 |
| date | DATE | 分析日期 |
| code | TEXT | 股票代码 |
| score | DECIMAL | 综合评分 |
| signals | JSON | 各指标信号明细 |
| created_at | TIMESTAMP | 创建时间 |

## 模块设计

### data-fetcher

每晚 18:00 通过 AkShare 获取：
1. A 股全量股票列表（代码、名称、行业）
2. 个股日线行情（开盘/收盘/最高/最低/成交量/换手率）
3. 基本面指标（PE、PB、ROE、净利润增长率等）

写入数据库（追加当天数据，避免重复）。

### analyzer — 分析引擎

#### 技术面分析（TA-Lib）

| 指标 | 说明 |
|---|---|
| 均线系统 | MA5/MA10/MA20/MA60，判断多头/空头排列 |
| MACD | 金叉/死叉信号 |
| RSI | 超买(>70)/超卖(<30)判断 |
| KDJ | 随机指标信号 |
| 成交量变化率 | 量价配合分析 |

每个指标输出独立信号值（±1），汇总为技术面得分。

#### 基本面筛选

可配置阈值打分：

| 指标 | 打分逻辑 |
|---|---|
| PE | 低于行业平均加分 |
| PB | 合理范围内加分 |
| ROE | >15% 加分 |
| 净利润增长率 | 正增长加分 |

各指标权重和阈值在 `config.yaml` 中配置，无需改代码即可调整。

#### 综合评分

```
总分 = 技术面得分 × 技术面权重 + 基本面得分 × 基本面权重
```

结果写入 `analysis_results` 表。

### notifier — 通知模块

插件式架构，基于 `BaseNotifier` 抽象类：

- 钉钉机器人（Webhook）
- 企业微信机器人（Webhook）
- 邮件通知（SMTP）

阶段 2 实现，可同时启用多个渠道。

### web — Web 展示层（阶段 3）

- 后端：FastAPI
- 前端：HTML + Chart.js
- 页面：选股排行榜、个股历史评分、信号明细

## 项目目录结构

```
stock-analyzer/
├── config.yaml              # 全局配置
├── main.py                  # 入口（调度器）
├── requirements.txt
├── data/
│   └── stock_analyzer.db    # SQLite 数据库
├── src/
│   ├── fetcher.py           # 数据获取 (AkShare)
│   ├── analyzer.py          # 分析引擎
│   ├── models.py            # 数据库模型
│   ├── notifier/
│   │   ├── __init__.py
│   │   ├── base.py          # BaseNotifier 抽象类
│   │   ├── dingtalk.py      # 钉钉通知
│   │   └── email.py         # 邮件通知
│   └── web/
│       ├── app.py           # FastAPI app
│       └── templates/       # HTML 模板
└── utils/
    ├── config.py            # 配置加载
    └── logger.py            # 日志
```

## 技术栈

| 组件 | 技术 |
|---|---|
| 语言 | Python 3.10+ |
| 数据获取 | akshare |
| 数据分析 | pandas, TA-Lib |
| 数据库 | SQLite（阶段 1）→ PostgreSQL（阶段 3 可选）|
| ORM | SQLAlchemy |
| 调度 | APScheduler |
| Web | FastAPI |
| 通知 | 钉钉/企业微信 Webhook, SMTP |
