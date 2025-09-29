import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .db import engine, create_tables
from .routers import products, trades

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了時の処理"""
    logger.info("Starting FastAPI application")

    # DB テーブル作成
    await create_tables()
    logger.info("Database tables created/verified")

    yield

    logger.info("Shutting down FastAPI application")
    await engine.dispose()


# FastAPIアプリケーション初期化
app = FastAPI(
    title="Tanaka POS API",
    description="WebモバイルPOS システム API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限する
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# グローバル例外ハンドラー
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )


# ルーター登録
app.include_router(products.router, prefix="/api/v1", tags=["products"])
app.include_router(trades.router, prefix="/api/v1", tags=["trades"])


# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "tanaka-pos-api"}


@app.get("/")
async def root():
    return {"message": "Tanaka POS API", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )