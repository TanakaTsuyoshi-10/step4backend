import os
import ssl
import logging
import certifi
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import SQLAlchemyError

from .models import Base

logger = logging.getLogger(__name__)

# 環境変数からDB接続文字列を取得
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://tech0gen10student:vY7JZNfU@rdbs-002-gen10-step3-1-oshima1.mysql.database.azure.com:3306/tanaka_pos?charset=utf8mb4"
)

# SSL接続設定（厳密構成）
def create_ssl_context():
    """
    Azure Database for MySQL用の厳密なSSL設定を作成

    Returns:
        ssl.SSLContext: 設定済みSSLコンテキスト
    """
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    ssl_context.check_hostname = False  # Azure MySQLでは通常False
    ssl_context.verify_mode = ssl.CERT_REQUIRED  # 証明書検証は必須
    return ssl_context

# 非同期SQLAlchemyエンジン作成（厳密構成版）
engine = create_async_engine(
    DATABASE_URL,
    echo=bool(os.getenv("SQL_ECHO", "false").lower() == "true"),
    pool_pre_ping=True,
    pool_recycle=3600,
    poolclass=NullPool,
    connect_args={
        "charset": "utf8mb4",
        "autocommit": False,
        "ssl": create_ssl_context(),  # 厳密なSSL設定
    }
)

# 非同期セッションファクトリー
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False
)