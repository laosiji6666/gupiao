from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path


def create_app() -> FastAPI:
    app = FastAPI(title="Stock Analyzer", version="1.0.0")

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    return app


# 为 uvicorn 直接运行创建的实例
app = create_app()
