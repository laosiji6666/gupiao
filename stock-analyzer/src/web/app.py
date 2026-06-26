from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from src.web.routers import rankings as rankings_router


def create_app() -> FastAPI:
    app = FastAPI(title="Stock Analyzer", version="1.0.0")
    app.include_router(rankings_router.router)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    return app


# 为 uvicorn 直接运行创建的实例
app = create_app()
