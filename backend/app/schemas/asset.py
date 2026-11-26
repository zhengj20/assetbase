"""资产核心域 Schema。"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import InSchema


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_code: str
    asset_name: str
    category_id: int
    spec: str | None = None
    brand: str | None = None
    model: str | None = None
    unit: str
    qrcode: str | None = None
    org_id: int
    project_id: int | None = None
    office_id: int | None = None
    warehouse_id: int | None = None
    space_id: int | None = None
    location_detail: str | None = None
    use_user_id: int | None = None
    use_dept_id: int | None = None
    status: int
    is_high_value: int
    is_reusable: int
    group_id: int | None = None
    price: Decimal | None = None
    buy_date: date | None = None
    warranty_end: date | None = None
    supplier_id: int | None = None
    invoice_no: str | None = None
    depreciation_method: int | None = None
    residual_value: Decimal | None = None
    accum_depreciation: Decimal | None = None
    net_value: Decimal | None = None
    dep_status: int
    last_check_time: datetime | None = None
    image_cover: str | None = None
    create_time: datetime
    version: int


class AssetListRow(BaseModel):
    """列表行：携带关联名称冗余，减少前端二次查询。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_code: str
    asset_name: str
    qrcode: str | None = None
    category_name: str | None = None
    spec: str | None = None
    brand: str | None = None
    org_name: str | None = None
    project_name: str | None = None
    office_name: str | None = None
    warehouse_name: str | None = None
    space_name: str | None = None
    use_user_name: str | None = None
    use_dept_name: str | None = None
    status: int
    is_high_value: int
    price: Decimal | None = None
    net_value: Decimal | None = None
    buy_date: date | None = None
    create_time: datetime


class AssetIn(InSchema):
    asset_name: str = Field(max_length=200)
    category_id: int
    spec: str | None = None
    brand: str | None = None
    model: str | None = None
    unit: str = "件"
    org_id: int
    project_id: int | None = None
    office_id: int | None = None
    warehouse_id: int | None = None
    space_id: int | None = None
    location_detail: str | None = None
    use_user_id: int | None = None
    use_dept_id: int | None = None
    status: int = 1
    is_high_value: bool = False
    is_reusable: bool = False
    price: Decimal | None = None
    buy_date: date | None = None
    warranty_end: date | None = None
    supplier_id: int | None = None
    invoice_no: str | None = None
    depreciation_method: int | None = None
    remark: str | None = None


class AssetUpdateIn(InSchema):
    asset_name: str | None = Field(default=None, max_length=200)
    spec: str | None = None
    brand: str | None = None
    model: str | None = None
    project_id: int | None = None
    office_id: int | None = None
    location_detail: str | None = None
    use_user_id: int | None = None
    use_dept_id: int | None = None
    price: Decimal | None = None
    buy_date: date | None = None
    warranty_end: date | None = None
    supplier_id: int | None = None
    invoice_no: str | None = None
    is_high_value: bool | None = None
    is_reusable: bool | None = None
    remark: str | None = None


class AssetLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    action_type: int
    biz_type: str | None = None
    biz_id: int | None = None
    before_snapshot: str | None = None
    after_snapshot: str | None = None
    operator_id: int | None = None
    operate_time: datetime
