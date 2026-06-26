from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from src.web.routers import rankings as rankings_router
from src.web.routers import stocks as stocks_router
from src.web.routers import pages as pages_router


def create_app() -> FastAPI:
    app = FastAPI(title="Stock Analyzer", version="1.0.0")
    app.include_router(rankings_router.router)
    app.include_router(stocks_router.router)
    app.include_router(pages_router.router)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    return app


# 为 uvicorn 直接运行创建的实例
app = create_app()

if __name__ == "__main__":
    import uvicorn
    from src.web.database import init_db
    from utils.config import load_config

    config = load_config()
    init_db(config["database"]["url"])
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=8000, reload=True)
