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
