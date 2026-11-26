"""基础档案域 Schema。"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_name: str
    parent_id: int
    code: str
    depreciate_month: int | None = None
    residual_rate: Decimal | None = None
    sort: int
    status: int


class CategoryIn(BaseModel):
    category_name: str = Field(max_length=100)
    parent_id: int = 0
    code: str = Field(min_length=2, max_length=10)
    depreciate_month: int | None = None
    residual_rate: Decimal | None = None
    sort: int = 0
    status: int = 1
    remark: str | None = None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_name: str
    contact: str | None = None
    phone: str | None = None
    bank_account: str | None = None
    coop_status: int
    rating: str | None = None


class SupplierIn(BaseModel):
    supplier_name: str = Field(max_length=200)
    contact: str | None = None
    phone: str | None = None
    bank_account: str | None = None
    coop_status: int = 1
    rating: str | None = None
    remark: str | None = None


class SpaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_name: str
    space_type: int
    parent_id: int
    project_id: int
    layout: str | None = None
    room_type: str | None = None
    space_status: int
    floor: str | None = None
    area: Decimal | None = None
    sort: int


class SpaceIn(BaseModel):
    space_name: str = Field(max_length=100)
    space_type: int = Field(ge=1, le=4)
    parent_id: int = 0
    project_id: int
    layout: str | None = None
    room_type: str | None = None
    space_status: int = 1
    floor: str | None = None
    area: Decimal | None = None
    sort: int = 0
    remark: str | None = None


class WarehouseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    warehouse_name: str
    warehouse_type: int
    org_id: int
    project_id: int | None = None
    space_id: int | None = None
    manager_id: int | None = None
    address: str | None = None
    status: int


class WarehouseIn(BaseModel):
    warehouse_name: str = Field(max_length=100)
    warehouse_type: int = Field(ge=1, le=3)
    org_id: int
    project_id: int | None = None
    space_id: int | None = None
    manager_id: int | None = None
    address: str | None = None
    status: int = 1
    remark: str | None = None


class OfficeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    office_name: str
    org_id: int
    project_id: int | None = None
    building: str | None = None
    floor: str | None = None
    address: str | None = None
    manager_id: int | None = None
    sort: int
    status: int


class OfficeIn(BaseModel):
    office_name: str = Field(max_length=100)
    org_id: int
    project_id: int | None = None
    building: str | None = None
    floor: str | None = None
    address: str | None = None
    manager_id: int | None = None
    sort: int = 0
    status: int = 1
    remark: str | None = None


class WarehouseStockOut(BaseModel):
    """库存台账：仓库 + 分类维度汇总。"""

    warehouse_id: int
    warehouse_name: str
    category_name: str
    total_count: int
    in_stock: int
    total_price: Decimal | None = None
