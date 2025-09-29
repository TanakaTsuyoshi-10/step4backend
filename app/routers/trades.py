import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from ..db import get_db
from ..models import Product, Trade, TradeLine
from ..schemas import (
    TradeCreate,
    TradeResponse,
    TaxCalculator,
    ValidationErrorResponse,
    InternalServerErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/trades",
    response_model=TradeResponse,
    responses={
        400: {"model": ValidationErrorResponse, "description": "バリデーションエラー"},
        500: {"model": InternalServerErrorResponse, "description": "サーバーエラー"}
    },
    summary="取引登録",
    description="取引と取引明細を一括登録し、税計算を含む合計金額を返します。"
)
async def create_trade(
    trade_data: TradeCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    取引登録API

    Args:
        trade_data: 取引データ（ヘッダ情報＋明細リスト）
        db: データベースセッション

    Returns:
        TradeResponse: 取引登録結果と合計金額

    Raises:
        HTTPException: バリデーションエラー（400）、サーバーエラー（500）
    """
    try:
        logger.info(f"取引登録開始: emp_cd={trade_data.emp_cd}, store_cd={trade_data.store_cd}, 明細件数={len(trade_data.trade_lines)}")

        # 1. 商品マスタの存在確認と情報取得
        product_ids = [line.prd_id for line in trade_data.trade_lines]
        stmt = select(Product).where(Product.prd_id.in_(product_ids))
        result = await db.execute(stmt)
        products = {p.prd_id: p for p in result.scalars().all()}

        # 存在しない商品IDチェック
        missing_product_ids = set(product_ids) - set(products.keys())
        if missing_product_ids:
            logger.warning(f"存在しない商品ID: {missing_product_ids}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Validation Error",
                    "message": f"存在しない商品IDが指定されています: {list(missing_product_ids)}",
                    "details": [{"field": "prd_id", "missing_ids": list(missing_product_ids)}]
                }
            )

        # 2. 取引ヘッダ作成
        trade = Trade(
            datetime=datetime.now(),
            emp_cd=trade_data.emp_cd,
            store_cd=trade_data.store_cd,
            pos_no=trade_data.pos_no,
            ttl_amt_ex_tax=0,  # 後で計算して更新
            total_amt=0        # 後で計算して更新
        )
        db.add(trade)
        await db.flush()  # IDを取得するためフラッシュ

        logger.info(f"取引ヘッダ作成: trd_id={trade.trd_id}")

        # 3. 取引明細作成と税計算
        trade_lines_data = []
        dtl_id = 1

        for line_data in trade_data.trade_lines:
            product = products[line_data.prd_id]

            # 税計算実行
            line_amt_ex_tax, line_tax, line_amt = TaxCalculator.calculate_line_amounts(
                price=product.price,
                qty=line_data.qty,
                tax_cd=product.tax_cd
            )

            # 取引明細作成
            trade_line = TradeLine(
                trd_id=trade.trd_id,
                dtl_id=dtl_id,
                prd_id=product.prd_id,
                prd_code=str(product.code),
                prd_name=product.name,
                prd_price=product.price,
                tax_cd=product.tax_cd,
                qty=line_data.qty,
                line_amt_ex_tax=line_amt_ex_tax,
                line_tax=line_tax,
                line_amt=line_amt
            )
            db.add(trade_line)

            # レスポンス用データ保存
            trade_lines_data.append({
                "line_amt_ex_tax": line_amt_ex_tax,
                "line_tax": line_tax,
                "line_amt": line_amt
            })

            logger.info(f"取引明細作成: dtl_id={dtl_id}, prd_name={product.name}, qty={line_data.qty}, line_amt={line_amt}")
            dtl_id += 1

        # 4. 取引合計計算
        total_amt_ex_tax, total_tax, total_amt = TaxCalculator.calculate_trade_totals(trade_lines_data)

        # 取引ヘッダに合計金額を更新
        trade.ttl_amt_ex_tax = total_amt_ex_tax
        trade.total_amt = total_amt

        # 5. データベースコミット
        await db.commit()

        logger.info(f"取引登録成功: trd_id={trade.trd_id}, total_amt_ex_tax={total_amt_ex_tax}, total_amt={total_amt}")

        return TradeResponse(
            success=True,
            trade_id=trade.trd_id,
            total_amt_ex_tax=total_amt_ex_tax,
            total_amt=total_amt,
            total_tax=total_tax,
            message="取引登録が完了しました"
        )

    except HTTPException:
        # HTTPExceptionは再スロー
        await db.rollback()
        raise

    except IntegrityError as e:
        await db.rollback()
        logger.error(f"整合性制約エラー（取引登録）: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Integrity Error",
                "message": "データ整合性エラーが発生しました",
                "details": [{"error": str(e.orig)}]
            }
        )

    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"データベースエラー（取引登録）: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database Error",
                "message": "データベース処理中にエラーが発生しました"
            }
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"予期しないエラー（取引登録）: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "サーバー内部エラーが発生しました"
            }
        )


@router.get(
    "/trades/{trade_id}",
    summary="取引取得",
    description="指定されたIDの取引情報を取得します（開発・テスト用）。"
)
async def get_trade(
    trade_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    取引取得API（開発・テスト用）

    Args:
        trade_id: 取引ID
        db: データベースセッション

    Returns:
        取引情報（ヘッダ＋明細）

    Raises:
        HTTPException: 取引未登録（404）、サーバーエラー（500）
    """
    try:
        logger.info(f"取引取得開始: trade_id={trade_id}")

        # 取引ヘッダ取得
        stmt = select(Trade).where(Trade.trd_id == trade_id)
        result = await db.execute(stmt)
        trade = result.scalar_one_or_none()

        if not trade:
            logger.warning(f"取引未登録: trade_id={trade_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Trade not found",
                    "message": "指定された取引IDは登録されていません",
                    "trade_id": trade_id
                }
            )

        # 取引明細取得
        stmt = select(TradeLine).where(TradeLine.trd_id == trade_id).order_by(TradeLine.dtl_id)
        result = await db.execute(stmt)
        trade_lines = result.scalars().all()

        logger.info(f"取引取得成功: trade_id={trade_id}, 明細件数={len(trade_lines)}")

        return {
            "trade": {
                "trd_id": trade.trd_id,
                "datetime": trade.datetime,
                "emp_cd": trade.emp_cd,
                "store_cd": trade.store_cd,
                "pos_no": trade.pos_no,
                "ttl_amt_ex_tax": trade.ttl_amt_ex_tax,
                "total_amt": trade.total_amt
            },
            "trade_lines": [
                {
                    "dtl_id": line.dtl_id,
                    "prd_id": line.prd_id,
                    "prd_code": line.prd_code,
                    "prd_name": line.prd_name,
                    "prd_price": line.prd_price,
                    "tax_cd": line.tax_cd,
                    "qty": line.qty,
                    "line_amt_ex_tax": line.line_amt_ex_tax,
                    "line_tax": line.line_tax,
                    "line_amt": line.line_amt
                }
                for line in trade_lines
            ]
        }

    except HTTPException:
        raise

    except SQLAlchemyError as e:
        logger.error(f"データベースエラー（取引取得）: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database Error",
                "message": "データベース処理中にエラーが発生しました"
            }
        )

    except Exception as e:
        logger.error(f"予期しないエラー（取引取得）: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "サーバー内部エラーが発生しました"
            }
        )