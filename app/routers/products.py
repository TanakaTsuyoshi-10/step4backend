import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import urlparse

from ..db import get_db
from ..models import Product
from ..schemas import (
    Product as ProductSchema,
    ProductNotFoundResponse,
    InternalServerErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()

# DB接続情報のマスク表示
def mask_database_url() -> str:
    """DATABASE_URLをマスクして安全に表示"""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return "Not configured"

    try:
        parsed = urlparse(db_url)
        # ホスト名とDB名のみ表示、他はマスク
        host = parsed.hostname or "unknown"
        db_name = parsed.path.lstrip('/') if parsed.path else "unknown"
        return f"Host: {host}, DB: {db_name}"
    except Exception:
        return f"URL format: {db_url[:25]}..."


@router.get(
    "/products/{code}",
    response_model=ProductSchema,
    responses={
        404: {"model": ProductNotFoundResponse, "description": "商品未登録"},
        500: {"model": InternalServerErrorResponse, "description": "サーバーエラー"}
    },
    summary="商品検索",
    description="JANコードまたは商品コードで商品マスタを検索します。"
)
async def get_product_by_code(
    code: str = Path(..., description="商品コード/JANコード（8-25桁）", regex=r"^[0-9]{8,25}$"),
    db: AsyncSession = Depends(get_db)
):
    """
    商品検索API

    Args:
        code: 商品コード/JANコード（8-25桁の文字列）
        db: データベースセッション

    Returns:
        ProductSchema: 商品情報

    Raises:
        HTTPException: 商品未登録（404）、サーバーエラー（500）
    """
    try:
        # デバッグログ：受け取ったcodeとその型
        logger.info(f"[BARCODE_LOOKUP] Received code='{code}' (type={type(code).__name__})")

        # DB接続先情報をログ出力
        logger.info(f"[BARCODE_LOOKUP] {mask_database_url()}")

        # 前後空白の除去
        code = code.strip()

        logger.info(f"[BARCODE_LOOKUP] Executing query with code='{code}'")

        # 商品検索クエリ実行
        stmt = select(Product).where(Product.code == code)
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()

        # ヒット件数をログ出力
        hit_count = 1 if product else 0
        logger.info(f"[BARCODE_LOOKUP] Query result: {hit_count} hit(s)")

        if not product:
            logger.warning(f"[BARCODE_LOOKUP] Product not found for code='{code}'")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Product not found",
                    "message": f"未登録商品です（コード: {code}）",
                    "code": code
                }
            )

        logger.info(f"[BARCODE_LOOKUP] Found product: {product.name} (ID: {product.prd_id})")
        return ProductSchema.from_orm(product)

    except HTTPException:
        # HTTPExceptionは再スロー
        raise

    except SQLAlchemyError as e:
        logger.error(f"[BARCODE_LOOKUP] Database error for code='{code}': {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database Error",
                "message": "商品データの取得中にエラーが発生しました"
            }
        )

    except Exception as e:
        logger.error(f"[BARCODE_LOOKUP] Unexpected error for code='{code}': {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "サーバー内部エラーが発生しました"
            }
        )


@router.get(
    "/products",
    response_model=list[ProductSchema],
    summary="商品一覧取得",
    description="商品マスタの一覧を取得します（開発・テスト用）。"
)
async def get_products(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    商品一覧取得API（開発・テスト用）

    Args:
        limit: 取得件数上限（デフォルト100）
        offset: オフセット（デフォルト0）
        db: データベースセッション

    Returns:
        List[ProductSchema]: 商品一覧

    Raises:
        HTTPException: サーバーエラー（500）
    """
    try:
        logger.info(f"商品一覧取得開始: limit={limit}, offset={offset}")

        # 商品一覧取得クエリ実行
        stmt = select(Product).limit(limit).offset(offset).order_by(Product.prd_id)
        result = await db.execute(stmt)
        products = result.scalars().all()

        logger.info(f"商品一覧取得成功: 件数={len(products)}")
        return [ProductSchema.from_orm(product) for product in products]

    except SQLAlchemyError as e:
        logger.error(f"データベースエラー（商品一覧取得）: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database Error",
                "message": "データベース処理中にエラーが発生しました"
            }
        )

    except Exception as e:
        logger.error(f"予期しないエラー（商品一覧取得）: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "サーバー内部エラーが発生しました"
            }
        )