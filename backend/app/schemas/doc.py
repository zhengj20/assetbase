"""业务单据域 Schema：采购/入库/出库/调拨/报废 + 审批。"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.base import InSchema


# ---------- 采购申请 ----------
class PurchaseItemIn(BaseModel):
    category_id: int | None = None
    asset_name: str = Field(max_length=200)
    spec: str | None = None
    num: int = Field(ge=1)
    unit_price: Decimal | None = None
    purpose: int | None = None
    group_id: int | None = None


class PurchaseIn(InSchema):
    org_id: int
    project_id: int | None = None
    apply_date: date | None = None
    budget_item: str | None = None
    cost_subject: str | None = None
    supplier_id: int | None = None
    contract_no: str | None = None
    remark: str | None = None
    items: list[PurchaseItemIn] = Field(min_length=1)


class PurchaseItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int | None = None
    asset_name: str
    spec: str | None = None
    num: int
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    purpose: int | None = None


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    apply_no: str
    org_id: int
    project_id: int | None = None
    apply_user: int
    apply_date: date | None = None
    total_amount: Decimal | None = None
    budget_item: str | None = None
    cost_subject: str | None = None
    supplier_id: int | None = None
    contract_no: str | None = None
    wf_instance_id: int | None = None
    status: int
    create_time: datetime
    org_name: str | None = None


class PurchaseDetailOut(PurchaseOut):
    items: list[PurchaseItemOut] = []
    apply_user_name: str | None = None
    org_name: str | None = None


# ---------- 入库 ----------
class StockInItemIn(BaseModel):
    category_id: int | None = None
    asset_name: str = Field(max_length=200)
    spec: str | None = None
    num: int = Field(ge=1)
    unit_price: Decimal | None = None


class StockInIn(InSchema):
    warehouse_id: int
    in_type: int = Field(ge=1, le=5, description="1采购入库 2调拨入库 3退库入库 4盘盈入库 5直接入库")
    purchase_id: int | None = None
    supplier_id: int | None = None
    in_date: date | None = None
    org_id: int | None = None
    remark: str | None = None
    items: list[StockInItemIn] = Field(min_length=1)


class StockInItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int | None = None
    category_id: int | None = None
    asset_name: str | None = None
    num: int
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class StockInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    in_no: str
    warehouse_id: int | None = None  # 盘盈入库（差异闭环自动生成）无仓库
    in_type: int
    purchase_id: int | None = None
    supplier_id: int | None = None
    in_date: date | None = None
    total_num: int
    total_price: Decimal | None = None
    wf_instance_id: int | None = None
    status: int
    create_time: datetime


class StockInDetailOut(StockInOut):
    items: list[StockInItemOut] = []
    warehouse_name: str | None = None


# ---------- 出库（领用） ----------
class StockOutItemIn(BaseModel):
    asset_id: int
    use_location: str | None = None


class StockOutIn(InSchema):
    warehouse_id: int
    out_type: int = Field(ge=1, le=4, description="1领用出库 2调拨出库 3报废出库 4盘亏出库")
    receive_user: int | None = None
    out_date: date | None = None
    org_id: int | None = None
    remark: str | None = None
    items: list[StockOutItemIn] = Field(min_length=1)


class StockOutItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    num: int
    use_location: str | None = None


class StockOutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    out_no: str
    warehouse_id: int
    out_type: int
    receive_user: int | None = None
    out_date: date | None = None
    total_num: int
    wf_instance_id: int | None = None
    status: int
    create_time: datetime


class StockOutDetailOut(StockOutOut):
    items: list[StockOutItemOut] = []
    warehouse_name: str | None = None
    receive_user_name: str | None = None


# ---------- 调拨 ----------
class TransferItemIn(BaseModel):
    asset_id: int
    group_id: int | None = None
    use_location: str | None = Field(default=None, max_length=200, description="调入后使用位置")
    use_user_id: int | None = Field(default=None, description="调入后责任人")
    use_dept_id: int | None = Field(default=None, description="调入后责任部门")


class TransferIn(InSchema):
    out_warehouse_id: int | None = Field(default=None, description="调出仓库（仓库调拨时必填）")
    in_warehouse_id: int | None = Field(default=None, description="调入仓库（仓库调拨时必填）")
    out_org_id: int | None = None
    in_org_id: int | None = None
    transfer_date: date | None = None
    transfer_type: int = Field(ge=1, le=4, description="1仓库调拨 2项目空间调拨 4部门调拨")
    out_project_id: int | None = Field(default=None, description="调出项目空间-空间ID（项目空间调拨时必填）")
    in_project_id: int | None = Field(default=None, description="调入项目空间-空间ID（项目空间调拨时必填）")
    out_dept_id: int | None = Field(default=None, description="调出部门（部门调拨时必填）")
    in_dept_id: int | None = Field(default=None, description="调入部门（部门调拨时必填）")
    remark: str | None = None
    items: list[TransferItemIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_transfer_type_fields(self) -> "TransferIn":
        if self.transfer_type == 1:
            if not self.out_warehouse_id or not self.in_warehouse_id:
                raise ValueError("仓库调拨必须选择调出和调入仓库")
            if self.out_warehouse_id == self.in_warehouse_id:
                raise ValueError("调入调出仓库不能相同")
        if self.transfer_type == 2:
            if not self.out_project_id or not self.in_project_id:
                raise ValueError("项目空间调拨必须选择调出和调入项目空间")
            if self.out_project_id == self.in_project_id:
                raise ValueError("调入调出项目空间不能相同")
        if self.transfer_type == 4:
            if not self.out_dept_id or not self.in_dept_id:
                raise ValueError("部门调拨必须选择调出和调入部门")
            if self.out_dept_id == self.in_dept_id:
                raise ValueError("调入调出部门不能相同")
        return self


class TransferItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    group_id: int | None = None
    num: int
    use_location: str | None = None
    use_user_id: int | None = None
    use_user_name: str | None = None
    use_dept_id: int | None = None
    use_dept_name: str | None = None


class TransferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transfer_no: str
    out_warehouse_id: int | None = None
    in_warehouse_id: int | None = None
    out_org_id: int | None = None
    in_org_id: int | None = None
    apply_user: int
    transfer_date: date | None = None
    transfer_type: int
    out_project_id: int | None = None
    in_project_id: int | None = None
    out_dept_id: int | None = None
    in_dept_id: int | None = None
    wf_instance_id: int | None = None
    status: int
    create_time: datetime
    out_warehouse_name: str | None = None
    in_warehouse_name: str | None = None
    out_space_name: str | None = None
    in_space_name: str | None = None
    out_dept_name: str | None = None
    in_dept_name: str | None = None


class TransferDetailOut(TransferOut):
    items: list[TransferItemOut] = []
    apply_user_name: str | None = None


# ---------- 借用 ----------
class BorrowItemIn(BaseModel):
    asset_id: int
    use_location: str | None = Field(default=None, max_length=200, description="借用后使用位置")


class BorrowIn(InSchema):
    org_id: int | None = None
    borrow_user: int | None = Field(default=None, description="借用人")
    borrow_date: date | None = None
    expected_return_date: date | None = None
    remark: str | None = None
    items: list[BorrowItemIn] = Field(min_length=1)


class BorrowItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    src_warehouse_id: int | None = None
    src_warehouse_name: str | None = None
    return_status: int
    return_date: date | None = None
    return_note: str | None = None


class BorrowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    borrow_no: str
    org_id: int | None = None
    org_name: str | None = None
    apply_user: int
    borrow_user: int | None = None
    borrow_date: date | None = None
    expected_return_date: date | None = None
    wf_instance_id: int | None = None
    status: int
    create_time: datetime


class BorrowDetailOut(BorrowOut):
    items: list[BorrowItemOut] = []
    apply_user_name: str | None = None
    borrow_user_name: str | None = None
    returned_num: int = 0


class ReturnIn(BaseModel):
    asset_ids: list[int] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=200, description="归还备注")


# ---------- 归还单（独立单据，走审批闭环） ----------
class ReturnItemIn(BaseModel):
    asset_id: int


class ReturnDocIn(InSchema):
    org_id: int | None = None
    return_date: date | None = None
    remark: str | None = None
    items: list[ReturnItemIn] = Field(min_length=1)


class ReturnItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    borrow_id: int | None = None
    target_warehouse_id: int | None = None
    target_warehouse_name: str | None = None


class ReturnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    return_no: str
    org_id: int | None = None
    org_name: str | None = None
    apply_user: int
    return_date: date | None = None
    remark: str | None = None
    wf_instance_id: int | None = None
    status: int
    create_time: datetime


class ReturnDetailOut(ReturnOut):
    items: list[ReturnItemOut] = []
    apply_user_name: str | None = None


# ---------- 报废处置 ----------
class ScrapItemIn(BaseModel):
    asset_id: int
    evaluate_amount: Decimal | None = None


class ScrapIn(InSchema):
    org_id: int | None = None
    scrap_date: date | None = None
    scrap_reason: str | None = Field(default=None, max_length=50)
    dispose_type: int = Field(ge=1, le=3, description="1报废 2变卖 3捐赠")
    dispose_income: Decimal | None = None
    remark: str | None = None
    items: list[ScrapItemIn] = Field(min_length=1)


class ScrapItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    net_value: Decimal | None = None
    evaluate_amount: Decimal | None = None


class ScrapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scrap_no: str
    org_id: int | None = None
    apply_user: int
    scrap_date: date | None = None
    scrap_reason: str | None = None
    dispose_type: int
    dispose_income: Decimal | None = None
    profit_loss: Decimal | None = None
    wf_instance_id: int | None = None
    status: int
    create_time: datetime


class ScrapDetailOut(ScrapOut):
    items: list[ScrapItemOut] = []
    apply_user_name: str | None = None


# ---------- 审批 ----------
class ApproveIn(BaseModel):
    action: int = Field(ge=1, le=5, description="1通过 2驳回 4加签 5退回")
    comment: str | None = Field(default=None, max_length=500)
    sign_to: int | None = Field(default=None, description="加签目标用户ID（action=4 必填）")
    target_node: int | None = Field(default=None, ge=0, le=7, description="退回目标节点下标0起（action=5 必填，须早于当前节点）")


class ManualApproveIn(BaseModel):
    comment: str | None = Field(default=None, max_length=500, description="审批意见")


class DelegateIn(BaseModel):
    to_user: int = Field(description="委托目标用户ID")
    comment: str | None = Field(default=None, max_length=500)


class ApprovalTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instance_id: int
    node_name: str
    node_order: int
    assignee_id: int
    action: int | None = None
    sign_from: int | None = None
    comment: str | None = None
    arrive_time: datetime | None = None
    done_time: datetime | None = None


class ApprovalTodoOut(BaseModel):
    task: ApprovalTaskOut
    biz_type: str
    biz_no: str
    biz_id: int
    apply_user_name: str | None = None


class TerminateIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500, description="终止原因")
