from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, CHAR, TIMESTAMP,
    ForeignKey, CheckConstraint, UniqueConstraint, Index,
    text, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Product(Base):
    """商品マスタ"""
    __tablename__ = "products"

    prd_id = Column(Integer, primary_key=True, autoincrement=True, comment="商品一意ID")
    code = Column(BigInteger, nullable=False, comment="JAN/EANコード（25桁まで）")
    name = Column(String(50), nullable=False, comment="商品名")
    price = Column(Integer, nullable=False, comment="税抜単価（円）")
    tax_cd = Column(CHAR(2), nullable=False, default="10", comment="税区分")

    # 制約
    __table_args__ = (
        UniqueConstraint("code", name="uq_products_code"),
        CheckConstraint("tax_cd IN ('10','08','00')", name="chk_products_tax_cd"),
        Index("idx_products_name", "name"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}
    )

    # リレーション
    trade_lines = relationship("TradeLine", back_populates="product")

    def __repr__(self):
        return f"<Product(prd_id={self.prd_id}, code={self.code}, name='{self.name}')>"


class Trade(Base):
    """取引"""
    __tablename__ = "trades"

    trd_id = Column(Integer, primary_key=True, autoincrement=True, comment="取引一意ID")
    datetime = Column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="取引日時"
    )
    emp_cd = Column(CHAR(10), nullable=False, comment="レジ担当者コード")
    store_cd = Column(CHAR(5), nullable=False, comment="店舗コード")
    pos_no = Column(CHAR(3), nullable=False, comment="POS機ID")
    ttl_amt_ex_tax = Column(Integer, nullable=False, default=0, comment="取引税抜合計")
    total_amt = Column(Integer, nullable=False, default=0, comment="取引税込合計")

    # 制約
    __table_args__ = (
        Index("idx_trades_datetime", "datetime"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}
    )

    # リレーション
    trade_lines = relationship(
        "TradeLine",
        back_populates="trade",
        passive_deletes=True  # 親削除時はDBのFKでRESTRICT
    )

    def __repr__(self):
        return f"<Trade(trd_id={self.trd_id}, datetime={self.datetime}, total_amt={self.total_amt})>"


class TradeLine(Base):
    """取引明細"""
    __tablename__ = "trade_lines"

    trd_id = Column(Integer, ForeignKey("trades.trd_id", ondelete="RESTRICT", onupdate="RESTRICT"),
                   primary_key=True, comment="取引ID")
    dtl_id = Column(Integer, primary_key=True, comment="取引内連番（1..n）")
    prd_id = Column(Integer, ForeignKey("products.prd_id", ondelete="RESTRICT", onupdate="RESTRICT"),
                   nullable=False, comment="商品ID")
    prd_code = Column(CHAR(13), nullable=False, comment="冗長：商品コードスナップショット")
    prd_name = Column(String(50), nullable=False, comment="冗長：商品名スナップショット")
    prd_price = Column(Integer, nullable=False, comment="税抜単価スナップショット")
    tax_cd = Column(CHAR(2), nullable=False, comment="税区分")
    qty = Column(Integer, nullable=False, default=1, comment="数量")
    line_amt_ex_tax = Column(Integer, nullable=False, default=0, comment="行税抜小計")
    line_tax = Column(Integer, nullable=False, default=0, comment="行税額")
    line_amt = Column(Integer, nullable=False, default=0, comment="行税込小計")

    # 制約
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}
    )

    # リレーション
    trade = relationship("Trade", back_populates="trade_lines")
    product = relationship("Product", back_populates="trade_lines")

    def __repr__(self):
        return f"<TradeLine(trd_id={self.trd_id}, dtl_id={self.dtl_id}, prd_name='{self.prd_name}', qty={self.qty})>"