from datetime import datetime as dt
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from decimal import Decimal


# Product関連スキーマ
class ProductBase(BaseModel):
    code: int = Field(..., description="JAN/EANコード", ge=1, le=99999999999999999999999999)
    name: str = Field(..., description="商品名", max_length=50)
    price: int = Field(..., description="税抜単価（円）", ge=0)
    tax_cd: str = Field("10", description="税区分", pattern="^(10|08|00)$")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    price: Optional[int] = Field(None, ge=0)
    tax_cd: Optional[str] = Field(None, pattern="^(10|08|00)$")


class Product(ProductBase):
    prd_id: int = Field(..., description="商品ID")

    class Config:
        from_attributes = True


# TradeLine関連スキーマ
class TradeLineCreate(BaseModel):
    prd_id: int = Field(..., description="商品ID", gt=0)
    qty: int = Field(1, description="数量", gt=0)

    @validator('qty')
    def validate_qty(cls, v):
        if v <= 0:
            raise ValueError('数量は1以上である必要があります')
        return v


class TradeLine(BaseModel):
    dtl_id: int = Field(..., description="明細連番")
    prd_id: int = Field(..., description="商品ID")
    prd_code: str = Field(..., description="商品コード")
    prd_name: str = Field(..., description="商品名")
    prd_price: int = Field(..., description="税抜単価")
    tax_cd: str = Field(..., description="税区分")
    qty: int = Field(..., description="数量")
    line_amt_ex_tax: int = Field(..., description="行税抜小計")
    line_tax: int = Field(..., description="行税額")
    line_amt: int = Field(..., description="行税込小計")

    class Config:
        from_attributes = True


# Trade関連スキーマ
class TradeCreate(BaseModel):
    emp_cd: str = Field(..., description="レジ担当者コード", max_length=10)
    store_cd: str = Field(..., description="店舗コード", max_length=5)
    pos_no: str = Field(..., description="POS機ID", max_length=3)
    trade_lines: List[TradeLineCreate] = Field(..., description="取引明細", min_items=1)

    @validator('trade_lines')
    def validate_trade_lines(cls, v):
        if not v:
            raise ValueError('取引明細は1件以上である必要があります')
        return v


class Trade(BaseModel):
    trd_id: int = Field(..., description="取引ID")
    datetime: dt = Field(..., description="取引日時")
    emp_cd: str = Field(..., description="レジ担当者コード")
    store_cd: str = Field(..., description="店舗コード")
    pos_no: str = Field(..., description="POS機ID")
    ttl_amt_ex_tax: int = Field(..., description="税抜合計")
    total_amt: int = Field(..., description="税込合計")
    trade_lines: List[TradeLine] = Field(..., description="取引明細")

    class Config:
        from_attributes = True


# レスポンス専用スキーマ
class TradeResponse(BaseModel):
    success: bool = Field(..., description="処理成功フラグ")
    trade_id: Optional[int] = Field(None, description="取引ID")
    total_amt_ex_tax: Optional[int] = Field(None, description="税抜合計")
    total_amt: Optional[int] = Field(None, description="税込合計")
    total_tax: Optional[int] = Field(None, description="税額合計")
    message: Optional[str] = Field(None, description="メッセージ")


class ProductNotFoundResponse(BaseModel):
    error: str = Field("Product not found", description="エラータイプ")
    message: str = Field("指定された商品コードは登録されていません", description="エラーメッセージ")
    code: Optional[int] = Field(None, description="検索したコード")


class ValidationErrorResponse(BaseModel):
    error: str = Field("Validation Error", description="エラータイプ")
    message: str = Field(..., description="エラーメッセージ")
    details: Optional[List[dict]] = Field(None, description="バリデーションエラー詳細")


class InternalServerErrorResponse(BaseModel):
    error: str = Field("Internal Server Error", description="エラータイプ")
    message: str = Field("サーバー内部エラーが発生しました", description="エラーメッセージ")


# 税計算ユーティリティクラス
class TaxCalculator:
    """税計算ロジック"""

    TAX_RATES = {
        "10": 0.10,  # 標準税率10%
        "08": 0.08,  # 軽減税率8%
        "00": 0.00,  # 非課税0%
    }

    @classmethod
    def calculate_line_amounts(cls, price: int, qty: int, tax_cd: str) -> tuple[int, int, int]:
        """
        行小計、税額、税込小計を計算

        Args:
            price: 税抜単価
            qty: 数量
            tax_cd: 税区分

        Returns:
            tuple: (税抜小計, 税額, 税込小計)
        """
        if tax_cd not in cls.TAX_RATES:
            raise ValueError(f"無効な税区分: {tax_cd}")

        line_amt_ex_tax = price * qty
        tax_rate = cls.TAX_RATES[tax_cd]
        line_tax = int(line_amt_ex_tax * tax_rate)  # 切り捨て
        line_amt = line_amt_ex_tax + line_tax

        return line_amt_ex_tax, line_tax, line_amt

    @classmethod
    def calculate_trade_totals(cls, trade_lines: List[dict]) -> tuple[int, int, int]:
        """
        取引全体の合計を計算

        Args:
            trade_lines: 取引明細リスト

        Returns:
            tuple: (税抜合計, 税額合計, 税込合計)
        """
        total_amt_ex_tax = sum(line["line_amt_ex_tax"] for line in trade_lines)
        total_tax = sum(line["line_tax"] for line in trade_lines)
        total_amt = sum(line["line_amt"] for line in trade_lines)

        return total_amt_ex_tax, total_tax, total_amt