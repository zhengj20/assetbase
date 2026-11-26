"""易耗品域 Schema：物料档案 / 采购 / 入库 / 领用 / 库存。"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import InSchema


# ---------- 物料档案 ----------
class ConItemIn(InSchema):
    item_code: str = Field(min_length=1, max_length=30)
    item_name: str = Field(min_length=1, max_length=200)
    spec: str | None = None
    unit: str = "个"
    category: str | None = None
    unit_price: Decimal | None = None
    status: int = 1
    remark: str | None = None


class ConItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_code: str
    item_name: str
    spec: str | None = None
    unit: str
    category: str | None = None
    unit_price: Decimal | None = None
    status: int
    create_time: datetime | None = None


class ConItemOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_code: str
    item_name: str
    spec: str | None = None
    unit: str
    unit_price: Decimal | None = None


# ---------- 采购 ----------
class ConPurchaseItemIn(BaseModel):
    item_id: int
    num: int = Field(ge=1)
    unit_price: Decimal | None = None


class ConPurchaseIn(InSchema):
    org_id: int
    apply_date: date | None = None
    supplier_id: int | None = None
    remark: str | None = None
    items: list[ConPurchaseItemIn] = Field(min_length=1)


class ConPurchaseItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    num: int
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    inbound_num: int = 0
    issued_num: int = 0
    item_name: str | None = None
    item_unit: str | None = None


class ConPurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purchase_no: str
    org_id: int
    apply_user: int
    apply_date: date | None = None
    supplier_id: int | None = None
    total_amount: Decimal | None = None
    status: int
    wf_instance_id: int | None = None
    create_time: datetime | None = None
    org_name: str | None = None
    apply_user_name: str | None = None


class ConPurchaseDetailOut(ConPurchaseOut):
    items: list[ConPurchaseItemOut] = []
    # 分配领用进度
    total_num: int = 0
    inbound_num: int = 0
    issued_num: int = 0
    remaining_num: int = 0


# ---------- 入库 ----------
class ConInboundItemIn(BaseModel):
    item_id: int
    num: int = Field(ge=1)
    unit_price: Decimal | None = None


class ConInboundIn(InSchema):
    warehouse_id: int
    purchase_id: int | None = None
    org_id: int | None = None
    in_date: date | None = None
    remark: str | None = None
    items: list[ConInboundItemIn] = Field(min_length=1)


class ConInboundItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    num: int
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    item_name: str | None = None


class ConInboundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    in_no: str
    warehouse_id: int
    purchase_id: int | None = None
    org_id: int
    in_date: date | None = None
    total_num: int
    total_amount: Decimal | None = None
    status: int
    wf_instance_id: int | None = None
    create_time: datetime | None = None
    org_name: str | None = None
    warehouse_name: str | None = None
    create_by_name: str | None = None


class ConInboundDetailOut(ConInboundOut):
    items: list[ConInboundItemOut] = []


# ---------- 领用 ----------
class ConIssueItemIn(BaseModel):
    item_id: int
    num: int = Field(ge=1)


class ConIssueIn(InSchema):
    source_type: int = 2  # 1采购直发 2库存领用
    purchase_id: int | None = None
    warehouse_id: int | None = None
    org_id: int | None = None
    receive_user: int | None = None
    receive_dept: int | None = None
    issue_date: date | None = None
    remark: str | None = None
    items: list[ConIssueItemIn] = Field(min_length=1)


class ConIssueItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    num: int
    unit_price: Decimal | None = None
    item_name: str | None = None


class ConIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_no: str
    source_type: int
    purchase_id: int | None = None
    warehouse_id: int | None = None
    org_id: int
    receive_user: int | None = None
    receive_dept: int | None = None
    issue_date: date | None = None
    total_num: int
    status: int
    wf_instance_id: int | None = None
    create_time: datetime | None = None
    org_name: str | None = None
    warehouse_name: str | None = None
    receive_user_name: str | None = None
    source_name: str | None = None


class ConIssueDetailOut(ConIssueOut):
    items: list[ConIssueItemOut] = []


# ---------- 库存 ----------
class ConStockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    warehouse_id: int
    qty: int
    unit_price: Decimal | None = None
    item_code: str | None = None
    item_name: str | None = None
    item_unit: str | None = None
    category: str | None = None
    warehouse_name: str | None = None
