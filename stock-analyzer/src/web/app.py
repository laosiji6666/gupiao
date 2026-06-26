from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.web.database import init_db
from src.web.routers import rankings as rankings_router
from src.web.routers import stocks as stocks_router
from src.web.routers import pages as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库"""
    from utils.config import load_config
    config = load_config()
    init_db(config["database"]["url"])
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Stock Analyzer", version="1.0.0", lifespan=lifespan)
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
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=8000, reload=True)
