"""盘点与折旧域（方案 6.2-5）+ 工作流域（方案 6.2-6）。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Numeric as SaDecimal,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CommonMixin


class AssCheckTask(CommonMixin, Base):
    """盘点任务表（方案 P0-2 新增）。"""

    __tablename__ = "ass_check_task"

    task_no: Mapped[str] = mapped_column(String(30), unique=True, comment="任务编号")
    task_name: Mapped[str] = mapped_column(String(200), comment="任务名称")
    check_type: Mapped[int] = mapped_column(
        SmallInteger, comment="1定期盘点 2临时盘点 3清盘专项"
    )
    scope_type: Mapped[int] = mapped_column(
        SmallInteger, comment="1公司 2项目 3仓库 4空间 5部门"
    )
    scope_id: Mapped[int] = mapped_column(BigInteger, comment="范围对象ID")
    plan_start: Mapped[date | None] = mapped_column(Date, comment="计划开始")
    plan_end: Mapped[date | None] = mapped_column(Date, comment="计划结束")
    checker_ids: Mapped[str | None] = mapped_column(String(500), comment="盘点人ID逗号分隔,高值双人")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=0, comment="0待执行 1执行中 2差异处理 3已完成"
    )
    diff_rate: Mapped[Decimal | None] = mapped_column(
        SaDecimal(6, 4), comment="差异率(小数,如0.0235=2.35%)"
    )
    book_total: Mapped[int] = mapped_column(Integer, default=0, comment="账面总数")
    finish_time: Mapped[datetime | None] = mapped_column(DateTime, comment="完成时间")

    __table_args__ = (
        Index("idx_ct_scope", "scope_type", "scope_id"),
        Index("idx_ct_status", "status"),
    )


class AssCheckItem(CommonMixin, Base):
    """盘点明细表：任务创建时冻结账面快照；盘盈行 asset_id 为空。"""

    __tablename__ = "ass_check_item"

    task_id: Mapped[int] = mapped_column(BigInteger, comment="任务ID")
    asset_id: Mapped[int | None] = mapped_column(BigInteger, comment="资产卡片(盘盈为空)")
    surplus_name: Mapped[str | None] = mapped_column(String(200), comment="盘盈资产名称")
    surplus_category_id: Mapped[int | None] = mapped_column(BigInteger, comment="盘盈分类")
    surplus_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="盘盈估值")
    space_id: Mapped[int | None] = mapped_column(BigInteger, comment="账面空间")
    book_status: Mapped[int | None] = mapped_column(SmallInteger, comment="账面状态")
    book_location: Mapped[str | None] = mapped_column(String(200), comment="账面位置")
    actual_status: Mapped[int | None] = mapped_column(SmallInteger, comment="实盘状态")
    actual_location: Mapped[str | None] = mapped_column(String(200), comment="实盘位置")
    check_result: Mapped[int | None] = mapped_column(
        SmallInteger, comment="1正常 2盘盈 3盘亏 4位置异常"
    )
    check_user: Mapped[int | None] = mapped_column(BigInteger, comment="盘点人")
    check_time: Mapped[datetime | None] = mapped_column(DateTime, comment="盘点时间")
    diff_handle_status: Mapped[int] = mapped_column(
        SmallInteger, default=0, comment="0待处理 1已处理"
    )
    diff_handle_note: Mapped[str | None] = mapped_column(String(500), comment="差异处理说明")

    __table_args__ = (
        Index("idx_ci_task_result", "task_id", "check_result"),
        Index("idx_ci_asset", "asset_id"),
    )


class AssDepreciation(CommonMixin, Base):
    __tablename__ = "ass_depreciation"

    period: Mapped[str] = mapped_column(String(6), comment="会计期间YYYYMM")
    asset_id: Mapped[int] = mapped_column(BigInteger, comment="资产")
    orig_value: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="原值")
    monthly_dep: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="本月计提")
    accum_dep: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="累计折旧")
    net_value: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="期末净值")
    voucher_no: Mapped[str | None] = mapped_column(String(50), comment="财务凭证号")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="0未结账 1已结账")

    __table_args__ = (
        UniqueConstraint("period", "asset_id", name="uk_dep_period_asset"),
        Index("idx_dep_period", "period"),
    )


class WfDefinition(CommonMixin, Base):
    """流程定义：flow_json 为节点数组（v2：{version:2, nodes:[{id,name,mode,approvers}]}）。

    同一 flow_key 表示同一流程的不同版本；同 biz_type 可有多条启用流程，
    发起时按 priority + condition_json 匹配（无条件的兜底）。
    """

    __tablename__ = "wf_definition"

    flow_key: Mapped[str] = mapped_column(String(50), default="", comment="流程稳定标识(同流程各版本共享)")
    def_name: Mapped[str] = mapped_column(String(100), comment="流程名称(含版本)")
    flow_name: Mapped[str | None] = mapped_column(String(100), comment="流程名称(不含版本)")
    biz_type: Mapped[str] = mapped_column(String(50), comment="关联单据类型")
    condition_json: Mapped[str | None] = mapped_column(
        Text, comment="分支条件JSON,如{\"field\":\"total_amount\",\"op\":\"gt\",\"value\":50000};空=兜底"
    )
    priority: Mapped[int] = mapped_column(Integer, default=100, comment="匹配优先级,越小越先")
    flow_json: Mapped[str | None] = mapped_column(Text, comment="流程节点定义JSON")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")

    __table_args__ = (
        UniqueConstraint("flow_key", "version", name="uk_wf_def_flow_ver"),
        Index("idx_wfd_biz", "biz_type", "status"),
    )


class WfInstance(CommonMixin, Base):
    __tablename__ = "wf_instance"

    def_id: Mapped[int] = mapped_column(BigInteger, comment="流程定义")
    def_version: Mapped[int] = mapped_column(Integer, default=1, comment="定义版本")
    flow_name: Mapped[str | None] = mapped_column(String(100), comment="发起时流程名称快照")
    biz_type: Mapped[str] = mapped_column(String(50), comment="业务类型")
    biz_id: Mapped[int] = mapped_column(BigInteger, comment="业务单据ID")
    initiator_id: Mapped[int | None] = mapped_column(BigInteger, comment="发起人")
    current_node: Mapped[str | None] = mapped_column(String(100), comment="当前节点")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, comment="1审批中 2已通过 3已驳回 4已撤销 5已终止"
    )
    finish_time: Mapped[datetime | None] = mapped_column(DateTime, comment="结束时间")
    finish_by: Mapped[int | None] = mapped_column(BigInteger, comment="结束操作人")
    finish_note: Mapped[str | None] = mapped_column(String(500), comment="结束备注(驳回意见/撤销/终止原因)")

    __table_args__ = (
        Index("idx_wfi_biz", "biz_type", "biz_id"),
        Index("idx_wfi_status", "status"),
        Index("idx_wfi_initiator", "initiator_id"),
    )


class WfBizApprovalConfig(CommonMixin, Base):
    """单据审批方式配置：按单据类型开关审批流。

    flow_enabled=1 启用审批流（走流程审批）；flow_enabled=0 关闭审批流（在单据页手动审批通过）。
    无记录时默认启用（保留既有行为）。
    """

    __tablename__ = "wf_biz_approval_config"

    biz_type: Mapped[str] = mapped_column(String(50), unique=True, comment="单据类型")
    flow_enabled: Mapped[int] = mapped_column(
        SmallInteger, default=1, comment="1启用审批流 0手动审批"
    )

    __table_args__ = (Index("idx_wbac_biz", "biz_type"),)


class WfTask(CommonMixin, Base):
    __tablename__ = "wf_task"

    instance_id: Mapped[int] = mapped_column(BigInteger, comment="流程实例")
    node_key: Mapped[str | None] = mapped_column(String(30), comment="节点标识(flow_json node id)")
    node_name: Mapped[str] = mapped_column(String(100), comment="节点名称")
    node_order: Mapped[int] = mapped_column(Integer, default=1, comment="节点顺序")
    assignee_id: Mapped[int] = mapped_column(BigInteger, comment="审批人")
    action: Mapped[int | None] = mapped_column(
        SmallInteger, comment="1通过 2驳回 4加签(加签产生的任务) 5退回(退回产生的重审任务)"
    )
    sign_from: Mapped[int | None] = mapped_column(BigInteger, comment="加签来源任务ID(空=普通任务)")
    comment: Mapped[str | None] = mapped_column(String(500), comment="审批意见")
    arrive_time: Mapped[datetime | None] = mapped_column(DateTime, comment="到达时间")
    done_time: Mapped[datetime | None] = mapped_column(DateTime, comment="处理时间")
    timeout_flag: Mapped[int] = mapped_column(SmallInteger, default=0, comment="超时标记")

    __table_args__ = (
        Index("idx_wft_assignee_status", "assignee_id", "action"),
        Index("idx_wft_instance", "instance_id"),
    )
