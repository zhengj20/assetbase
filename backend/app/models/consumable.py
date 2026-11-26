"""易耗品域（低值易耗品/办公用品）：库存型管理，独立于固定资产。

台账 = 物料档案(con_item) + 库存余额(con_stock) + 流水(采购/入库/领用)。
领用两条路径：①采购后直接分配领用(直发，不进库存) ②从库存领用。
状态机沿用单据通用：0草稿 → 1审批中 → 2已通过 → 3已驳回 → 4已取消。
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    Index,
    Integer,
    Numeric as SaDecimal,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CommonMixin


class ConItem(CommonMixin, Base):
    """易耗品物料档案。"""

    __tablename__ = "con_item"

    item_code: Mapped[str] = mapped_column(String(30), unique=True, comment="物料编码")
    item_name: Mapped[str] = mapped_column(String(200), comment="物料名称")
    spec: Mapped[str | None] = mapped_column(String(200), comment="规格")
    unit: Mapped[str] = mapped_column(String(20), default="个", comment="计量单位")
    category: Mapped[str | None] = mapped_column(String(100), comment="分类")
    unit_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="默认/最新单价")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")

    __table_args__ = (Index("idx_con_item_name", "item_name"),)


class ConStock(CommonMixin, Base):
    """易耗品库存余额（物料 × 仓库 一行）。"""

    __tablename__ = "con_stock"

    item_id: Mapped[int] = mapped_column(BigInteger, comment="物料")
    warehouse_id: Mapped[int] = mapped_column(BigInteger, comment="仓库")
    qty: Mapped[int] = mapped_column(Integer, default=0, comment="现有数量")
    unit_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="成本单价")

    __table_args__ = (Index("uq_con_stock", "item_id", "warehouse_id", unique=True),)


class ConPurchase(CommonMixin, Base):
    """易耗品采购单（审批）。"""

    __tablename__ = "con_purchase"

    purchase_no: Mapped[str] = mapped_column(String(30), unique=True, comment="采购单号")
    org_id: Mapped[int] = mapped_column(BigInteger, comment="核算公司")
    apply_user: Mapped[int] = mapped_column(BigInteger, comment="申请人")
    apply_date: Mapped[date | None] = mapped_column(Date, comment="申请日期")
    supplier_id: Mapped[int | None] = mapped_column(BigInteger, comment="供应商")
    total_amount: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="总金额")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (
        Index("idx_con_p_org_status", "org_id", "status"),
        Index("idx_con_p_user", "apply_user"),
    )


class ConPurchaseItem(CommonMixin, Base):
    """易耗品采购明细（num - inbound_num - issued_num = 剩余可分配）。"""

    __tablename__ = "con_purchase_item"

    purchase_id: Mapped[int] = mapped_column(BigInteger, comment="采购单")
    item_id: Mapped[int] = mapped_column(BigInteger, comment="物料")
    num: Mapped[int] = mapped_column(Integer, comment="采购数量")
    unit_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="单价")
    amount: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="金额")
    inbound_num: Mapped[int] = mapped_column(Integer, default=0, comment="已入库数量")
    issued_num: Mapped[int] = mapped_column(Integer, default=0, comment="已直发领用数量")

    __table_args__ = (Index("idx_con_pi_purchase", "purchase_id"), Index("idx_con_pi_item", "item_id"))


class ConInbound(CommonMixin, Base):
    """易耗品入库单（审批，通过后库存 +）。"""

    __tablename__ = "con_inbound"

    in_no: Mapped[str] = mapped_column(String(30), unique=True, comment="入库单号")
    warehouse_id: Mapped[int] = mapped_column(BigInteger, comment="入库仓库")
    purchase_id: Mapped[int | None] = mapped_column(BigInteger, comment="关联采购单")
    org_id: Mapped[int] = mapped_column(BigInteger, comment="核算公司")
    in_date: Mapped[date | None] = mapped_column(Date, comment="入库日期")
    total_num: Mapped[int] = mapped_column(Integer, default=0, comment="总数量")
    total_amount: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="总金额")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (Index("idx_con_i_wh_status", "warehouse_id", "status"),)


class ConInboundItem(CommonMixin, Base):
    """易耗品入库明细。"""

    __tablename__ = "con_inbound_item"

    in_id: Mapped[int] = mapped_column(BigInteger, comment="入库单")
    item_id: Mapped[int] = mapped_column(BigInteger, comment="物料")
    num: Mapped[int] = mapped_column(Integer, comment="数量")
    unit_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="单价")
    amount: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="金额")

    __table_args__ = (Index("idx_con_ii_in", "in_id"), Index("idx_con_ii_item", "item_id"))


class ConIssue(CommonMixin, Base):
    """易耗品领用单（审批）。source_type: 1采购直发 2库存领用。"""

    __tablename__ = "con_issue"

    issue_no: Mapped[str] = mapped_column(String(30), unique=True, comment="领用单号")
    source_type: Mapped[int] = mapped_column(SmallInteger, default=2, comment="1采购直发 2库存领用")
    purchase_id: Mapped[int | None] = mapped_column(BigInteger, comment="采购单(直发时)")
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, comment="仓库(库存领用时)")
    org_id: Mapped[int] = mapped_column(BigInteger, comment="核算公司")
    receive_user: Mapped[int | None] = mapped_column(BigInteger, comment="领用人")
    receive_dept: Mapped[int | None] = mapped_column(BigInteger, comment="领用部门")
    issue_date: Mapped[date | None] = mapped_column(Date, comment="领用日期")
    total_num: Mapped[int] = mapped_column(Integer, default=0, comment="总数量")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (Index("idx_con_is_org_status", "org_id", "status"),)


class ConIssueItem(CommonMixin, Base):
    """易耗品领用明细。"""

    __tablename__ = "con_issue_item"

    issue_id: Mapped[int] = mapped_column(BigInteger, comment="领用单")
    item_id: Mapped[int] = mapped_column(BigInteger, comment="物料")
    num: Mapped[int] = mapped_column(Integer, comment="数量")
    unit_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="单价")

    __table_args__ = (Index("idx_con_isi_issue", "issue_id"), Index("idx_con_isi_item", "item_id"))
