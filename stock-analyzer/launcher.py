"""
Stock Analyzer - 便携启动器
打包为 exe 后，双击直接启动 Web 服务并打开浏览器
"""
import sys
import os
import webbrowser
import threading
import time
from pathlib import Path

# 确保能找到项目模块
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
os.chdir(str(BASE_DIR))


def ensure_dirs():
    """确保运行时目录存在"""
    for d in ["data", "logs", "reports"]:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)


def run_pipeline():
    """在后台线程中运行数据分析"""
    import logging
    logging.basicConfig(level=logging.INFO)

    try:
        from utils.config import load_config
        from utils.logger import setup_logger
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from src.models import StockList
        from src.fetcher import Fetcher
        from src.analyzer import run_analysis
        from src.report import generate_csv, generate_html
        from datetime import date

        config = load_config()
        logger = setup_logger()
        engine = create_engine(config["database"]["url"])

        with Session(engine) as session:
            from src.models import StockList, DailyQuote

            fetcher = Fetcher(config, logger)
            stock_count = session.query(StockList).count()
            if stock_count == 0:
                fetcher.fetch_stock_list(session)

            # 首次运行：补充历史日线
            quote_count = session.query(DailyQuote).count()
            if quote_count == 0:
                backfill_days = config.get("backfill", {}).get("days", 60)
                fetcher.backfill_history(session, days=backfill_days)

            # 获取当日行情
            today = date.today()
            fetcher.fetch_daily_quotes(session, today)
            fetcher.fetch_fundamentals(session, today)

        # 运行分析
        with Session(engine) as session:
            results = run_analysis(session, config, logger)
            if results:
                report_dir = config.get("report", {}).get("output_dir", "reports")
                date_str = today.strftime("%Y%m%d")
                generate_csv(session, today, f"{report_dir}/{date_str}_ranking.csv")
                generate_html(session, today, f"{report_dir}/{date_str}_ranking.html",
                              config.get("report", {}).get("top_n", 30))
                logger.info(f"分析完成: {len(results)} 只股票")
    except Exception as e:
        logging.warning(f"数据获取跳过: {e}")


def start_server():
    """启动 Web 服务"""
    import uvicorn
    from src.web.app import app
    from utils.config import load_config
    from src.web.database import init_db

    ensure_dirs()

    # 初始化数据库
    config = load_config()
    init_db(config["database"]["url"])

    # 启动服务器
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


def open_browser():
    """延迟打开浏览器"""
    time.sleep(2)
    webbrowser.open("http://localhost:8080/dashboard")


if __name__ == "__main__":
    print("=" * 50)
    print("  Stock Analyzer - Starting...")
    print("=" * 50)
    print()

    # 后台获取数据（首次运行自动拉取）
    threading.Thread(target=run_pipeline, daemon=True).start()

    # 延迟打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动服务器
    start_server()
