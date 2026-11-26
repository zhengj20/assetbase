"""盘点域 Schema。"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import InSchema


class CheckTaskIn(InSchema):
    task_name: str = Field(max_length=200)
    check_type: int = Field(ge=1, le=3, description="1定期 2临时 3清盘专项")
    scope_type: int = Field(ge=1, le=5, description="1公司 2项目 3仓库 4空间 5部门")
    scope_id: int
    plan_start: date | None = None
    plan_end: date | None = None
    checker_ids: str | None = None
    remark: str | None = None


class CheckTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_no: str
    task_name: str
    check_type: int
    scope_type: int
    scope_id: int
    plan_start: date | None = None
    plan_end: date | None = None
    checker_ids: str | None = None
    status: int
    diff_rate: Decimal | None = None
    book_total: int
    finish_time: datetime | None = None
    create_time: datetime


class CheckItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    asset_id: int | None = None
    surplus_name: str | None = None
    surplus_category_id: int | None = None
    surplus_price: Decimal | None = None
    space_id: int | None = None
    book_status: int | None = None
    book_location: str | None = None
    actual_status: int | None = None
    actual_location: str | None = None
    check_result: int | None = None
    check_user: int | None = None
    check_time: datetime | None = None
    diff_handle_status: int
    diff_handle_note: str | None = None


class CheckItemRow(CheckItemOut):
    """列表行冗余：资产编码/名称/分类。"""

    asset_code: str | None = None
    asset_name: str | None = None
    category_name: str | None = None


class CheckRecordIn(BaseModel):
    check_result: int = Field(ge=1, le=4, description="1正常 2盘盈 3盘亏 4位置异常")
    actual_status: int | None = None
    actual_location: str | None = None


class SurplusIn(BaseModel):
    surplus_name: str = Field(max_length=200)
    surplus_category_id: int | None = None
    surplus_price: Decimal | None = None
    actual_location: str | None = None


class CheckTaskSummary(BaseModel):
    """盘点汇总。"""

    task_id: int
    task_no: str
    task_name: str
    check_type: int
    status: int
    book_total: int
    checked: int
    normal: int
    surplus: int
    loss: int
    position_diff: int
    unchecked: int
    diff_rate: Decimal
    loss_amount: Decimal
    surplus_amount: Decimal
