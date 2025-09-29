import logging
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..db import get_db
from ..models import Product
from ..schemas import (
    Product as ProductSchema,
    ProductNotFoundResponse,
    InternalServerErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
    code: int = Path(..., description="商品コード/JANコード", ge=1, le=99999999999999999999999999),
    db: AsyncSession = Depends(get_db)
):
    """
    商品検索API

    Args:
        code: 商品コード/JANコード（1-25桁）
        db: データベースセッション

    Returns:
        ProductSchema: 商品情報

    Raises:
        HTTPException: 商品未登録（404）、サーバーエラー（500）
    """
    try:
        logger.info(f"商品検索開始: code={code}")

        # 商品検索クエリ実行
        stmt = select(Product).where(Product.code == code)
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            logger.warning(f"商品未登録: code={code}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Product not found",
                    "message": "指定された商品コードは登録されていません",
                    "code": code
                }
            )

        logger.info(f"商品検索成功: prd_id={product.prd_id}, name={product.name}")
        return ProductSchema.from_orm(product)

    except HTTPException:
        # HTTPExceptionは再スロー
        raise

    except SQLAlchemyError as e:
        logger.error(f"データベースエラー（商品検索）: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database Error",
                "message": "データベース処理中にエラーが発生しました"
            }
        )

    except Exception as e:
        logger.error(f"予期しないエラー（商品検索）: {str(e)}", exc_info=True)
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