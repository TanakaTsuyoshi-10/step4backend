import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
import jwt
from jwt.exceptions import InvalidTokenError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .db import engine, create_tables
from .routers import products, trades

# 構造化ログ設定
class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def info(self, message: str, correlation_id: str = None, **kwargs):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "message": message,
            "correlation_id": correlation_id,
            **kwargs
        }
        self.logger.info(log_data)

    def error(self, message: str, correlation_id: str = None, error: Exception = None, **kwargs):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "message": message,
            "correlation_id": correlation_id,
            "error": str(error) if error else None,
            **kwargs
        }
        self.logger.error(log_data, exc_info=error is not None)

    def warning(self, message: str, correlation_id: str = None, **kwargs):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "WARNING",
            "message": message,
            "correlation_id": correlation_id,
            **kwargs
        }
        self.logger.warning(log_data)

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = StructuredLogger(__name__)

# JWT設定
JWT_SECRET_KEY = "your-secret-key-change-in-production"  # 本番環境では環境変数から取得
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "tanaka-pos-api"
JWT_AUDIENCE = "pos-frontend"

# レート制限設定
limiter = Limiter(key_func=get_remote_address)
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了時の処理"""
    logger.info("Starting FastAPI application", service="tanaka-pos-api")

    # DB テーブル作成
    await create_tables()
    logger.info("Database tables created/verified", service="tanaka-pos-api")

    yield

    logger.info("Shutting down FastAPI application", service="tanaka-pos-api")
    await engine.dispose()


# FastAPIアプリケーション初期化
app = FastAPI(
    title="Tanaka POS API",
    description="WebモバイルPOS システム API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定 - 本番環境用に制限
allowed_origins = [
    "https://app-002-gen10-step3-2-py-oshima13.azurewebsites.net",  # 本番フロントエンド
    "https://app-002-gen10-step3-1-node-oshima30.azurewebsites.net",  # 新フロントエンド
    "https://app-002-gen10-step3-1-py-oshima30.azurewebsites.net",  # 新バックエンド（同一オリジン）
    "http://localhost:3000",  # 開発環境
    "http://127.0.0.1:3000",  # 開発環境
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# レート制限ミドルウェア
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# JWT検証関数
async def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE
        )
        return payload
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# 相関IDミドルウェア
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Correlation-ID"] = correlation_id

    logger.info(
        f"Request processed",
        correlation_id=correlation_id,
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time=f"{process_time:.4f}s"
    )

    return response

# グローバル例外ハンドラー
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.error(
        f"Unhandled exception: {str(exc)}",
        correlation_id=correlation_id,
        error=exc,
        method=request.method,
        url=str(request.url)
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "correlation_id": correlation_id
        }
    )


# ルーター登録
app.include_router(products.router, prefix="/api/v1", tags=["products"])
app.include_router(trades.router, prefix="/api/v1", tags=["trades"])


# ヘルスチェックエンドポイント
@app.get("/health")
@limiter.limit("30/minute")
async def health_check(request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.info("Health check requested", correlation_id=correlation_id)
    return {
        "status": "healthy",
        "service": "tanaka-pos-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id
    }


@app.get("/")
@limiter.limit("10/minute")
async def root(request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return {
        "message": "Tanaka POS API",
        "version": "1.0.0",
        "correlation_id": correlation_id
    }

# 認証が必要なエンドポイントの例（管理者用）
@app.get("/api/v1/admin/stats")
@limiter.limit("5/minute")
async def admin_stats(request: Request, token_data: dict = Depends(verify_jwt_token)):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.info(
        "Admin stats requested",
        correlation_id=correlation_id,
        user=token_data.get("sub")
    )
    return {
        "total_sales": 156750,
        "total_products": 247,
        "total_transactions": 89,
        "correlation_id": correlation_id
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )