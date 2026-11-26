"""业务单据域（方案 6.2-4）：采购/入库/出库/调拨/报废，全部主表+明细表。"""
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    Numeric as SaDecimal,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CommonMixin

# 单据通用状态机：0草稿 → 1审批中 → 2已通过 → 3已驳回 → 4已取消
DOC_STATUS_DRAFT = 0
DOC_STATUS_APPROVING = 1
DOC_STATUS_APPROVED = 2
DOC_STATUS_REJECTED = 3
DOC_STATUS_CANCELED = 4


class AssPurchaseApply(CommonMixin, Base):
    __tablename__ = "ass_purchase_apply"

    apply_no: Mapped[str] = mapped_column(String(30), unique=True, comment="申请单号")
    org_id: Mapped[int] = mapped_column(BigInteger, comment="申请公司")
    project_id: Mapped[int | None] = mapped_column(BigInteger, comment="业务项目")
    apply_user: Mapped[int] = mapped_column(BigInteger, comment="申请人")
    apply_date: Mapped[date | None] = mapped_column(Date, comment="申请日期")
    total_amount: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="总金额")
    budget_item: Mapped[str | None] = mapped_column(String(100), comment="预算项")
    cost_subject: Mapped[str | None] = mapped_column(String(100), comment="成本科目")
    supplier_id: Mapped[int | None] = mapped_column(BigInteger, comment="供应商")
    contract_no: Mapped[str | None] = mapped_column(String(100), comment="合同编号")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (
        Index("idx_pa_org_status", "org_id", "status"),
        Index("idx_pa_user", "apply_user"),
    )


class AssPurchaseApplyItem(CommonMixin, Base):
    __tablename__ = "ass_purchase_apply_item"

    apply_id: Mapped[int] = mapped_column(BigInteger, comment="申请单ID")
    category_id: Mapped[int | None] = mapped_column(BigInteger, comment="分类")
    asset_name: Mapped[str] = mapped_column(String(200), comment="资产名称")
    spec: Mapped[str | None] = mapped_column(String(200), comment="规格")
    num: Mapped[int] = mapped_column(Integer, comment="数量")
    unit_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="单价")
    amount: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="金额")
    purpose: Mapped[int | None] = mapped_column(SmallInteger, comment="1办公 2样板间 3项目")
    group_id: Mapped[int | None] = mapped_column(BigInteger, comment="软装包ID")

    __table_args__ = (Index("idx_pai_apply", "apply_id"),)


class AssStockIn(CommonMixin, Base):
    __tablename__ = "ass_stock_in"

    in_no: Mapped[str] = mapped_column(String(30), unique=True, comment="入库单号")
    # 盘盈入库（账外资产）无仓库来源，允许为空
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, comment="入库仓库")
    in_type: Mapped[int] = mapped_column(
        SmallInteger, comment="1采购入库 2调拨入库 3退库入库 4盘盈入库"
    )
    purchase_id: Mapped[int | None] = mapped_column(BigInteger, comment="来源采购单")
    supplier_id: Mapped[int | None] = mapped_column(BigInteger, comment="供应商")
    in_date: Mapped[date | None] = mapped_column(Date, comment="入库日期")
    total_num: Mapped[int] = mapped_column(Integer, default=0, comment="总数量")
    total_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="总金额")
    org_id: Mapped[int | None] = mapped_column(BigInteger, comment="核算公司")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (Index("idx_si_wh_status", "warehouse_id", "status"),)


class AssStockInItem(CommonMixin, Base):
    __tablename__ = "ass_stock_in_item"

    in_id: Mapped[int] = mapped_column(BigInteger, comment="入库单ID")
    asset_id: Mapped[int | None] = mapped_column(BigInteger, comment="资产卡片")
    category_id: Mapped[int | None] = mapped_column(BigInteger, comment="分类")
    asset_name: Mapped[str | None] = mapped_column(String(200), comment="资产名称快照")
    num: Mapped[int] = mapped_column(Integer, default=1, comment="数量")
    unit_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="单价")
    amount: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="金额")

    __table_args__ = (Index("idx_sii_in", "in_id"), Index("idx_sii_asset", "asset_id"))


class AssStockOut(CommonMixin, Base):
    __tablename__ = "ass_stock_out"

    out_no: Mapped[str] = mapped_column(String(30), unique=True, comment="出库单号")
    warehouse_id: Mapped[int] = mapped_column(BigInteger, comment="出库仓库")
    out_type: Mapped[int] = mapped_column(
        SmallInteger, comment="1领用出库 2调拨出库 3报废出库 4盘亏出库"
    )
    receive_user: Mapped[int | None] = mapped_column(BigInteger, comment="领用人")
    out_date: Mapped[date | None] = mapped_column(Date, comment="出库日期")
    total_num: Mapped[int] = mapped_column(Integer, default=0, comment="总数量")
    org_id: Mapped[int | None] = mapped_column(BigInteger, comment="核算公司")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (Index("idx_so_wh_status", "warehouse_id", "status"),)


class AssStockOutItem(CommonMixin, Base):
    __tablename__ = "ass_stock_out_item"

    out_id: Mapped[int] = mapped_column(BigInteger, comment="出库单ID")
    asset_id: Mapped[int] = mapped_column(BigInteger, comment="资产卡片")
    num: Mapped[int] = mapped_column(Integer, default=1, comment="数量")
    use_location: Mapped[str | None] = mapped_column(String(200), comment="使用地点")

    __table_args__ = (Index("idx_soi_out", "out_id"), Index("idx_soi_asset", "asset_id"))


class AssTransfer(CommonMixin, Base):
    __tablename__ = "ass_transfer"

    transfer_no: Mapped[str] = mapped_column(String(30), unique=True, comment="调拨单号")
    out_warehouse_id: Mapped[int | None] = mapped_column(BigInteger, comment="调出仓库（仓库调拨时）")
    in_warehouse_id: Mapped[int | None] = mapped_column(BigInteger, comment="调入仓库（仓库调拨时）")
    out_org_id: Mapped[int | None] = mapped_column(BigInteger, comment="调出公司")
    in_org_id: Mapped[int | None] = mapped_column(BigInteger, comment="调入公司")
    apply_user: Mapped[int] = mapped_column(BigInteger, comment="申请人")
    transfer_date: Mapped[date | None] = mapped_column(Date, comment="调拨日期")
    transfer_type: Mapped[int] = mapped_column(
        SmallInteger, comment="1仓库调拨 2项目空间调拨 4部门调拨"
    )
    out_project_id: Mapped[int | None] = mapped_column(BigInteger, comment="调出项目空间(空间ID，项目空间调拨时)")
    in_project_id: Mapped[int | None] = mapped_column(BigInteger, comment="调入项目空间(空间ID，项目空间调拨时)")
    out_dept_id: Mapped[int | None] = mapped_column(BigInteger, comment="调出部门（部门调拨时）")
    in_dept_id: Mapped[int | None] = mapped_column(BigInteger, comment="调入部门（部门调拨时）")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (Index("idx_tr_org", "out_org_id", "in_org_id", "status"),)


class AssTransferItem(CommonMixin, Base):
    __tablename__ = "ass_transfer_item"

    transfer_id: Mapped[int] = mapped_column(BigInteger, comment="调拨单ID")
    asset_id: Mapped[int] = mapped_column(BigInteger, comment="资产卡片")
    group_id: Mapped[int | None] = mapped_column(BigInteger, comment="整包调拨组合包")
    num: Mapped[int] = mapped_column(Integer, default=1, comment="数量")
    use_location: Mapped[str | None] = mapped_column(String(200), comment="调入后使用位置")
    use_user_id: Mapped[int | None] = mapped_column(BigInteger, comment="调入后责任人")
    use_dept_id: Mapped[int | None] = mapped_column(BigInteger, comment="调入后责任部门")

    __table_args__ = (Index("idx_ti_transfer", "transfer_id"), Index("idx_ti_asset", "asset_id"))


class AssBorrow(CommonMixin, Base):
    __tablename__ = "ass_borrow"

    borrow_no: Mapped[str] = mapped_column(String(30), unique=True, comment="借用单号")
    org_id: Mapped[int | None] = mapped_column(BigInteger, comment="核算公司")
    apply_user: Mapped[int] = mapped_column(BigInteger, comment="申请人")
    borrow_user: Mapped[int | None] = mapped_column(BigInteger, comment="借用人")
    borrow_date: Mapped[date | None] = mapped_column(Date, comment="借用日期")
    expected_return_date: Mapped[date | None] = mapped_column(Date, comment="预计归还日期")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (
        Index("idx_bj_org_status", "org_id", "status"),
        Index("idx_bj_user", "apply_user"),
    )


class AssBorrowItem(CommonMixin, Base):
    __tablename__ = "ass_borrow_item"

    borrow_id: Mapped[int] = mapped_column(BigInteger, comment="借用单ID")
    asset_id: Mapped[int] = mapped_column(BigInteger, comment="资产卡片")
    src_warehouse_id: Mapped[int | None] = mapped_column(BigInteger, comment="借出时所在仓库")
    return_status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="0未归还 1已归还")
    return_date: Mapped[date | None] = mapped_column(Date, comment="实际归还日期")
    return_note: Mapped[str | None] = mapped_column(String(200), comment="归还备注")

    __table_args__ = (Index("idx_bi_borrow", "borrow_id"), Index("idx_bi_asset", "asset_id"))


class AssReturn(CommonMixin, Base):
    __tablename__ = "ass_return"

    return_no: Mapped[str] = mapped_column(String(30), unique=True, comment="归还单号")
    org_id: Mapped[int | None] = mapped_column(BigInteger, comment="核算公司")
    apply_user: Mapped[int] = mapped_column(BigInteger, comment="归还申请人")
    return_date: Mapped[date | None] = mapped_column(Date, comment="归还日期")
    remark: Mapped[str | None] = mapped_column(String(200), comment="备注")
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (
        Index("idx_rt_org_status", "org_id", "status"),
        Index("idx_rt_user", "apply_user"),
    )


class AssReturnItem(CommonMixin, Base):
    __tablename__ = "ass_return_item"

    return_id: Mapped[int] = mapped_column(BigInteger, comment="归还单ID")
    asset_id: Mapped[int] = mapped_column(BigInteger, comment="资产卡片")
    borrow_id: Mapped[int | None] = mapped_column(BigInteger, comment="关联借用单")
    target_warehouse_id: Mapped[int | None] = mapped_column(BigInteger, comment="归还目标仓库（原借出仓库）")

    __table_args__ = (Index("idx_ri_return", "return_id"), Index("idx_ri_asset", "asset_id"))


class AssScrap(CommonMixin, Base):
    __tablename__ = "ass_scrap"

    scrap_no: Mapped[str] = mapped_column(String(30), unique=True, comment="报废单号")
    org_id: Mapped[int | None] = mapped_column(BigInteger, comment="核算公司")
    apply_user: Mapped[int] = mapped_column(BigInteger, comment="申请人")
    scrap_date: Mapped[date | None] = mapped_column(Date, comment="报废日期")
    scrap_reason: Mapped[str | None] = mapped_column(String(50), comment="处置原因")
    dispose_type: Mapped[int] = mapped_column(
        SmallInteger, comment="1报废 2变卖 3捐赠"
    )
    dispose_income: Mapped[Decimal | None] = mapped_column(
        SaDecimal(14, 2), comment="处置收入"
    )
    profit_loss: Mapped[Decimal | None] = mapped_column(
        SaDecimal(14, 2), comment="处置损益"
    )
    wf_instance_id: Mapped[int | None] = mapped_column(BigInteger, comment="流程实例")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="单据状态")

    __table_args__ = (Index("idx_sc_org_status", "org_id", "status"),)


class AssScrapItem(CommonMixin, Base):
    __tablename__ = "ass_scrap_item"

    scrap_id: Mapped[int] = mapped_column(BigInteger, comment="报废单ID")
    asset_id: Mapped[int] = mapped_column(BigInteger, comment="资产卡片")
    net_value: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="资产净值")
    evaluate_amount: Mapped[Decimal | None] = mapped_column(
        SaDecimal(14, 2), comment="评估/变卖金额"
    )

    __table_args__ = (Index("idx_sci_scrap", "scrap_id"), Index("idx_sci_asset", "asset_id"))
