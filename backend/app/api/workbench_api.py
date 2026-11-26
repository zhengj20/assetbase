"""工作台 API：聚合待办/消息/日历/工作记录。"""
import calendar
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import false, func, or_, select

from app.core.deps import DbDep, UserDep
from app.models.check import WfInstance, WfTask
from app.models.doc import (
    AssBorrow,
    AssBorrowItem,
    AssPurchaseApply,
    AssReturn,
    AssScrap,
    AssStockIn,
    AssStockOut,
    AssTransfer,
)
from app.models.sys import SysMessage, SysUser, SysWorkRecord

router = APIRouter(prefix="/workbench", tags=["工作台"])


class WorkRecordIn(BaseModel):
    title: str = Field(..., max_length=200)
    content: str | None = None
    record_date: date
    rec_type: int = 1  # 1工作记录 2提醒
    remind_time: str | None = None  # "HH:mm"


class WorkRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str | None
    record_date: date
    rec_type: int = 1
    remind_time: str | None = None


class CalendarEventOut(BaseModel):
    date: date
    type: str  # doc | record | reminder | due
    label: str
    remind_time: str | None = None
    biz_type: str | None = None
    biz_id: int | None = None
    record_id: int | None = None


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start, end


def _visible(user: UserDep, org_col=None, user_col=None) -> list:
    """按当前用户数据范围过滤：本人创建 或 属于其可见组织。org_ids=None 表示全部数据。"""
    if user.org_ids is None:
        return []
    parts = []
    if user_col is not None:
        parts.append(user_col == user.id)
    if org_col is not None:
        parts.append(org_col.in_(user.org_ids or []))
    return [or_(*parts)] if parts else [false()]


@router.get("/summary")
async def summary(db: DbDep, user: UserDep):
    """工作台聚合：我的待办 + 最近消息 + 未读数。"""
    # 1) 我的待办（未完成的任务，关联实例取业务信息 + 发起人姓名）
    todo_rows = await db.execute(
        select(
            WfTask.id,
            WfInstance.biz_type,
            WfTask.node_name,
            WfTask.arrive_time,
            SysUser.real_name.label("initiator_name"),
        )
        .join(WfInstance, WfTask.instance_id == WfInstance.id)
        .join(SysUser, WfInstance.initiator_id == SysUser.id)
        .where(
            WfTask.assignee_id == user.id,
            WfTask.action.is_(None),
            WfTask.del_flag == 0,
            WfInstance.del_flag == 0,
        )
        .order_by(WfTask.arrive_time.desc())
        .limit(10)
    )
    todos = [
        {
            "task_id": r[0],
            "biz_type": r[1],
            "node_name": r[2],
            "arrive_time": r[3],
            "initiator_name": r[4],
        }
        for r in todo_rows.all()
    ]

    # 2) 最近 5 条消息
    msg_rows = await db.scalars(
        select(SysMessage)
        .where(SysMessage.receiver_id == user.id, SysMessage.del_flag == 0)
        .order_by(SysMessage.create_time.desc())
        .limit(5)
    )
    messages = [
        {
            "id": m.id,
            "msg_type": m.msg_type,
            "title": m.title,
            "is_read": m.is_read,
            "send_time": m.send_time or m.create_time,
        }
        for m in msg_rows
    ]

    # 3) 未读消息数
    unread_count = await db.scalar(
        select(func.count())
        .select_from(SysMessage)
        .where(SysMessage.receiver_id == user.id, SysMessage.is_read == 0, SysMessage.del_flag == 0)
    )

    return {"todos": todos, "messages": messages, "unread_count": unread_count or 0}


# 单据日历映射：(模型, 业务日期列, 单号列, 标签前缀, biz_type, 组织列, 用户列)
_DOC_DEFS = [
    (AssPurchaseApply, AssPurchaseApply.apply_date, AssPurchaseApply.apply_no, "采购申请", "purchase_apply", AssPurchaseApply.org_id, AssPurchaseApply.apply_user),
    (AssStockIn, AssStockIn.in_date, AssStockIn.in_no, "入库", "stock_in", AssStockIn.org_id, None),
    (AssStockOut, AssStockOut.out_date, AssStockOut.out_no, "出库", "stock_out", AssStockOut.org_id, None),
    (AssTransfer, AssTransfer.transfer_date, AssTransfer.transfer_no, "调拨", "transfer", None, AssTransfer.apply_user),
    (AssBorrow, AssBorrow.borrow_date, AssBorrow.borrow_no, "借用", "borrow", AssBorrow.org_id, AssBorrow.apply_user),
    (AssScrap, AssScrap.scrap_date, AssScrap.scrap_no, "报废", "scrap", AssScrap.org_id, AssScrap.apply_user),
    (AssReturn, AssReturn.return_date, AssReturn.return_no, "归还", "return", AssReturn.org_id, AssReturn.apply_user),
]


@router.get("/calendar", response_model=list[CalendarEventOut])
async def calendar_events(
    db: DbDep,
    user: UserDep,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    """某月日历事件：单据 / 借用归还截止 / 工作记录，按日期排序。"""
    start, end = _month_range(year, month)
    events: list[CalendarEventOut] = []

    # 1) 单据事件
    for model, date_col, no_col, prefix, biz_type, org_col, user_col in _DOC_DEFS:
        conds = [
            date_col.is_not(None),
            date_col.between(start, end),
            model.del_flag == 0,
            *_visible(user, org_col, user_col),
        ]
        rows = await db.scalars(select(model).where(*conds))
        for r in rows:
            d = getattr(r, date_col.name)
            no = getattr(r, no_col.name)
            events.append(
                CalendarEventOut(
                    date=d, type="doc", label=f"{prefix} {no}",
                    biz_type=biz_type, biz_id=r.id,
                )
            )

    # 2) 借用归还截止事件（预计归还日在本月 且 存在未归还明细）
    not_returned = select(AssBorrowItem.borrow_id).where(AssBorrowItem.return_status == 0)
    due_rows = await db.scalars(
        select(AssBorrow)
        .where(
            AssBorrow.expected_return_date.is_not(None),
            AssBorrow.expected_return_date.between(start, end),
            AssBorrow.del_flag == 0,
            AssBorrow.id.in_(not_returned),
            *_visible(user, AssBorrow.org_id, AssBorrow.apply_user),
        )
        .distinct()
    )
    for r in due_rows:
        events.append(
            CalendarEventOut(
                date=r.expected_return_date, type="due",
                label=f"借用归还截止 {r.expected_return_date.isoformat()}",
                biz_type="borrow", biz_id=r.id,
            )
        )

    # 3) 工作记录/提醒事件
    rec_rows = await db.scalars(
        select(SysWorkRecord)
        .where(
            SysWorkRecord.user_id == user.id,
            SysWorkRecord.record_date.between(start, end),
        )
    )
    for r in rec_rows:
        evt_type = "reminder" if r.rec_type == 2 else "record"
        lbl = r.remind_time + " " + r.title if r.remind_time else r.title
        events.append(
            CalendarEventOut(date=r.record_date, type=evt_type, label=lbl, remind_time=r.remind_time, record_id=r.id)
        )

    events.sort(key=lambda e: e.date)
    return events


@router.get("/calendar-range", response_model=list[CalendarEventOut])
async def calendar_range(
    db: DbDep,
    user: UserDep,
    start: date = Query(...),
    end: date = Query(...),
):
    """任意日期范围日历事件（用于周视图等）。"""
    events: list[CalendarEventOut] = []

    for model, date_col, no_col, prefix, biz_type, org_col, user_col in _DOC_DEFS:
        conds = [
            date_col.is_not(None),
            date_col.between(start, end),
            model.del_flag == 0,
            *_visible(user, org_col, user_col),
        ]
        rows = await db.scalars(select(model).where(*conds))
        for r in rows:
            d = getattr(r, date_col.name)
            no = getattr(r, no_col.name)
            events.append(
                CalendarEventOut(date=d, type="doc", label=f"{prefix} {no}", biz_type=biz_type, biz_id=r.id)
            )

    not_returned = select(AssBorrowItem.borrow_id).where(AssBorrowItem.return_status == 0)
    due_rows = await db.scalars(
        select(AssBorrow)
        .where(
            AssBorrow.expected_return_date.is_not(None),
            AssBorrow.expected_return_date.between(start, end),
            AssBorrow.del_flag == 0,
            AssBorrow.id.in_(not_returned),
            *_visible(user, AssBorrow.org_id, AssBorrow.apply_user),
        )
        .distinct()
    )
    for r in due_rows:
        events.append(
            CalendarEventOut(
                date=r.expected_return_date, type="due",
                label=f"借用归还截止 {r.expected_return_date.isoformat()}",
                biz_type="borrow", biz_id=r.id,
            )
        )

    rec_rows = await db.scalars(
        select(SysWorkRecord)
        .where(
            SysWorkRecord.user_id == user.id,
            SysWorkRecord.record_date.between(start, end),
        )
    )
    for r in rec_rows:
        evt_type = "reminder" if r.rec_type == 2 else "record"
        lbl = r.remind_time + " " + r.title if r.remind_time else r.title
        events.append(
            CalendarEventOut(date=r.record_date, type=evt_type, label=lbl, remind_time=r.remind_time, record_id=r.id)
        )

    events.sort(key=lambda e: e.date)
    return events


@router.get("/work-records", response_model=list[WorkRecordOut])
async def list_work_records(
    db: DbDep,
    user: UserDep,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    """当前用户某月的工作记录，按日期升序。"""
    start, end = _month_range(year, month)
    rows = await db.scalars(
        select(SysWorkRecord)
        .where(
            SysWorkRecord.user_id == user.id,
            SysWorkRecord.record_date.between(start, end),
        )
        .order_by(SysWorkRecord.record_date)
    )
    return [WorkRecordOut.model_validate(r) for r in rows]


@router.post("/work-records", response_model=WorkRecordOut)
async def create_work_record(body: WorkRecordIn, db: DbDep, user: UserDep):
    """新增一条工作记录/提醒。"""
    rec = SysWorkRecord(
        user_id=user.id,
        title=body.title,
        content=body.content,
        record_date=body.record_date,
        rec_type=body.rec_type,
        remind_time=body.remind_time,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return WorkRecordOut.model_validate(rec)


@router.delete("/work-records/{rec_id}")
async def delete_work_record(rec_id: int, db: DbDep, user: UserDep):
    """删除本人的一条工作记录。"""
    rec = await db.get(SysWorkRecord, rec_id)
    if not rec or rec.user_id != user.id:
        raise HTTPException(404, "记录不存在")
    await db.delete(rec)
    await db.commit()
    return {"ok": True}
