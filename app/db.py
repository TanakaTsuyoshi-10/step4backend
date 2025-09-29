import os
import logging
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

# 非同期SQLAlchemyエンジン作成
engine = create_async_engine(
    DATABASE_URL,
    echo=bool(os.getenv("SQL_ECHO", "false").lower() == "true"),  # SQL実行ログ出力
    pool_pre_ping=True,  # 接続チェック
    pool_recycle=3600,   # 1時間で接続をリサイクル
    poolclass=NullPool,  # Azure Database for MySQLとの相性を考慮
    connect_args={
        "charset": "utf8mb4",
        "autocommit": False,
        "ssl": True,  # Azure Database for MySQL requires SSL/TLS
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


async def create_tables():
    """
    データベーステーブルを作成
    本番環境ではAlembicを使用することを推奨
    """
    try:
        async with engine.begin() as conn:
            # 開発環境でのみテーブル作成
            # await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables creation skipped (use Alembic in production)")
    except SQLAlchemyError as e:
        logger.error(f"Database table creation failed: {str(e)}")
        raise


async def get_db():
    """
    データベースセッション依存性注入
    FastAPIのDependency Injectionで使用
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            await session.close()


async def get_db_session():
    """
    データベースセッションを直接取得（ユーティリティ関数）
    """
    return AsyncSessionLocal()


class DatabaseManager:
    """データベース操作のヘルパークラス"""

    @staticmethod
    async def test_connection() -> bool:
        """
        データベース接続テスト

        Returns:
            bool: 接続成功時True、失敗時False
        """
        try:
            async with engine.connect() as conn:
                await conn.execute("SELECT 1")
                logger.info("Database connection test successful")
                return True
        except SQLAlchemyError as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False

    @staticmethod
    async def execute_raw_sql(sql: str, params: dict = None):
        """
        生SQLを実行

        Args:
            sql: 実行するSQL文
            params: SQLパラメータ

        Returns:
            実行結果
        """
        try:
            async with engine.connect() as conn:
                result = await conn.execute(sql, params or {})
                return result
        except SQLAlchemyError as e:
            logger.error(f"Raw SQL execution failed: {str(e)}")
            raise

    @staticmethod
    async def get_table_info(table_name: str):
        """
        テーブル情報を取得

        Args:
            table_name: テーブル名

        Returns:
            テーブル情報
        """
        try:
            sql = f"DESCRIBE {table_name}"
            async with engine.connect() as conn:
                result = await conn.execute(sql)
                return result.fetchall()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get table info for {table_name}: {str(e)}")
            raise


# デバッグ用: 接続文字列をマスクして表示
def get_masked_database_url() -> str:
    """
    パスワードをマスクしたデータベースURL取得

    Returns:
        マスク済みのDATABASE_URL
    """
    if "://" in DATABASE_URL and "@" in DATABASE_URL:
        protocol, rest = DATABASE_URL.split("://", 1)
        if "@" in rest:
            credentials, host_and_db = rest.split("@", 1)
            username = credentials.split(":", 1)[0] if ":" in credentials else credentials
            return f"{protocol}://{username}:***@{host_and_db}"
    return "***"


# 起動時にマスク済みURLをログ出力
logger.info(f"Database URL: {get_masked_database_url()}")