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

        # 2. 首次运行：补充历史日线数据（让 TA-Lib 指标有足够数据计算）
        from src.models import DailyQuote
        quote_count = session.query(DailyQuote).count()
        if quote_count == 0:
            logger.info("检测到无历史数据，开始回填...")
            backfill_days = config.get("backfill", {}).get("days", 60)
            fetcher.backfill_history(session, days=backfill_days)

        # 3. 获取当日行情（覆盖最新数据）
        logger.info(f"拉取 {today} 行情数据...")
        fetcher.fetch_daily_quotes(session, today)

        # 4. 获取基本面数据
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

    logger.info("每日分析流程完成 ")


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


def start_web():
    """启动 Web 服务"""
    import uvicorn
    from src.web.database import init_db as init_web_db
    from src.web.app import app

    config = load_config()
    init_web_db(config["database"]["url"])
    logger = setup_logger()
    logger.info("Web 服务启动于 http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        start_web()
    else:
        main()
