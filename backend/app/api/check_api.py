"""盘点模块 API（方案 6.5 + P0-2/P1-2）：

- 任务创建时冻结账面快照（check_item 账面状态/位置）
- 执行记录实盘（正常/盘盈/盘亏/位置异常）
- 完成时自动比对差异并计算差异率（>2% 标记需复盘）
- 差异闭环：盘盈→盘盈入库单；盘亏→盘亏出库销账
- 三类报表导出：明细表 / 差异表 / 汇总表
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select

from app.core.deps import CurrentUser, DbDep, UserDep, require_perm
from app.core.pagination import PageData, PageParams
from app.models.archive import AssCategory
from app.models.asset import AssAsset
from app.models.check import AssCheckItem, AssCheckTask
from app.models.doc import AssStockIn, AssStockInItem
from app.schemas.check import (
    CheckItemOut,
    CheckItemRow,
    CheckRecordIn,
    CheckTaskIn,
    CheckTaskOut,
    CheckTaskSummary,
    SurplusIn,
)
from app.services.asset_log_service import ACTION_CHECK, snapshot, write_log
from app.services.excel_service import build_excel
from app.services.seq_service import next_asset_code, next_doc_no

router = APIRouter(tags=["盘点管理"])

PermCheck = Annotated[CurrentUser, Depends(require_perm("check:edit"))]

SCOPE_LABEL = {1: "公司", 2: "项目", 3: "仓库", 4: "空间", 5: "部门"}
TYPE_LABEL = {1: "定期盘点", 2: "临时盘点", 3: "清盘专项"}
RESULT_LABEL = {1: "正常", 2: "盘盈", 3: "盘亏", 4: "位置异常"}
STATUS_LABEL = {0: "待执行", 1: "执行中", 2: "差异处理", 3: "已完成"}


def _scope_asset_conds(scope_type: int, scope_id: int):
    """按盘点范围筛选账面资产。"""
    return {
        1: [AssAsset.org_id == scope_id],
        2: [AssAsset.project_id == scope_id],
        3: [AssAsset.warehouse_id == scope_id],
        4: [AssAsset.space_id == scope_id],
        5: [AssAsset.use_dept_id == scope_id],
    }[scope_type]


def _task_scope_conds(user) -> list:
    """盘点任务数据范围：创建人 / 盘点人 / 范围对象在本组织内。"""
    if user.org_ids is None:
        return []
    if not user.org_ids:
        return [AssCheckTask.create_by == user.id]
    return [
        (
            (AssCheckTask.create_by == user.id)
            | (
                (AssCheckTask.scope_type.in_([1, 2, 5])) & (AssCheckTask.scope_id.in_(user.org_ids))
            )
            | AssCheckTask.checker_ids.like(f"%{user.id}%")
        )
    ]


@router.get("/check-tasks", response_model=PageData[CheckTaskOut])
async def list_check_tasks(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    status: int | None = None,
    check_type: int | None = None,
    keyword: str | None = None,
):
    conds = [AssCheckTask.del_flag == 0]
    if status is not None:
        conds.append(AssCheckTask.status == status)
    if check_type is not None:
        conds.append(AssCheckTask.check_type == check_type)
    if keyword:
        conds.append(
            AssCheckTask.task_no.like(f"%{keyword}%")
            | AssCheckTask.task_name.contains(keyword)
        )
    total = await db.scalar(
        select(func.count()).select_from(AssCheckTask).where(*conds)
    )
    rows = await db.scalars(
        select(AssCheckTask).where(*conds).order_by(AssCheckTask.id.desc())
        .offset(params.offset).limit(params.limit)
    )
    return PageData.build(total, params, [CheckTaskOut.model_validate(r) for r in rows])


@router.post("/check-tasks", response_model=CheckTaskOut)
async def create_check_task(
    body: CheckTaskIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("check:create"))],
):
    """创建盘点任务：冻结范围内在管资产账面快照。"""
    conds = [AssAsset.del_flag == 0, AssAsset.status.notin_([5, 6])] + _scope_asset_conds(
        body.scope_type, body.scope_id
    )
    assets = list(await db.scalars(select(AssAsset).where(*conds)))
    if not assets:
        raise HTTPException(400, "盘点范围内无在管资产")

    task = AssCheckTask(
        task_no=await next_doc_no(db, "check"),
        task_name=body.task_name,
        check_type=body.check_type,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        plan_start=body.plan_start,
        plan_end=body.plan_end,
        checker_ids=body.checker_ids or str(user.id),
        status=1,  # 有账面明细即进入执行中
        book_total=len(assets),
        create_by=user.id,
    )
    db.add(task)
    await db.flush()

    for a in assets:
        db.add(
            AssCheckItem(
                task_id=task.id,
                asset_id=a.id,
                space_id=a.space_id,
                book_status=a.status,
                book_location=a.location_detail or "",
            )
        )
    return task


@router.get("/check-tasks/{task_id}", response_model=CheckTaskOut)
async def get_check_task(task_id: int, db: DbDep, user: UserDep):
    task = await db.get(AssCheckTask, task_id)
    if not task or task.del_flag == 1:
        raise HTTPException(404, "盘点任务不存在")
    return task


@router.get("/check-tasks/{task_id}/items", response_model=PageData[CheckItemRow])
async def list_check_items(
    task_id: int,
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    check_result: int | None = None,
    only_unchecked: bool = False,
    only_checked: bool = False,
    keyword: str | None = None,
):
    """明细列表。only_checked=仅已盘（按盘点时间倒序，供「最近盘点记录」）。"""
    conds = [AssCheckItem.task_id == task_id, AssCheckItem.del_flag == 0]
    if check_result is not None:
        conds.append(AssCheckItem.check_result == check_result)
    if only_unchecked:
        conds.append(AssCheckItem.check_result.is_(None))
    if only_checked:
        conds.append(AssCheckItem.check_time.isnot(None))
    if keyword:
        conds.append(
            AssAsset.asset_code.like(f"{keyword}%") | AssAsset.asset_name.contains(keyword)
        )
    total = await db.scalar(
        select(func.count())
        .select_from(AssCheckItem)
        .join(AssAsset, AssAsset.id == AssCheckItem.asset_id, isouter=True)
        .where(*conds)
    )
    order = (
        [AssCheckItem.check_time.desc(), AssCheckItem.id.desc()]
        if only_checked
        else [AssCheckItem.id]
    )
    rows = await db.execute(
        select(
            AssCheckItem,
            AssAsset.asset_code,
            AssAsset.asset_name,
            AssCategory.category_name,
        )
        .join(AssAsset, AssAsset.id == AssCheckItem.asset_id, isouter=True)
        .join(AssCategory, AssCategory.id == AssAsset.category_id, isouter=True)
        .where(*conds)
        .order_by(*order)
        .offset(params.offset)
        .limit(params.limit)
    )
    records = []
    for item, code, name, cat_name in rows:
        d = CheckItemOut.model_validate(item).model_dump()
        d.update(
            asset_code=code, asset_name=name or item.surplus_name, category_name=cat_name
        )
        records.append(CheckItemRow(**d))
    return PageData.build(total, params, records)


@router.get("/check-tasks/{task_id}/scan")
async def scan_item(task_id: int, qrcode: str, db: DbDep, user: UserDep):
    """移动端扫码定位：二维码 → 资产 → 本任务明细。

    404=资产不存在（可登记盘盈）；409=资产不在本任务范围。
    """
    task = await db.get(AssCheckTask, task_id)
    if not task or task.del_flag == 1:
        raise HTTPException(404, "盘点任务不存在")
    if task.status in (2, 3):
        raise HTTPException(400, "任务已完成，不可再盘点")
    if not qrcode:
        raise HTTPException(400, "二维码内容为空")
    # 兼容两种码内容：二维码令牌 或 资产编码（标签印刷值）
    asset = (
        await db.execute(
            select(AssAsset).where(AssAsset.qrcode == qrcode, AssAsset.del_flag == 0)
        )
    ).scalar_one_or_none()
    if not asset:
        asset = (
            await db.execute(
                select(AssAsset).where(AssAsset.asset_code == qrcode, AssAsset.del_flag == 0)
            )
        ).scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "未找到该二维码对应的资产，可登记为盘盈")
    item = (
        await db.execute(
            select(AssCheckItem).where(
                AssCheckItem.task_id == task_id, AssCheckItem.asset_id == asset.id,
                AssCheckItem.del_flag == 0,
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(409, f"资产 {asset.asset_code} 不在本任务范围内")
    return {
        **CheckItemOut.model_validate(item).model_dump(),
        "asset_code": asset.asset_code,
        "asset_name": asset.asset_name,
        "book_status": item.book_status,
        "book_location": item.book_location,
    }


@router.post("/check-items/{item_id}/record")
async def record_check_item(
    item_id: int, body: CheckRecordIn, db: DbDep, user: UserDep, _p: PermCheck
):
    """盘点执行：记录实盘结果（移动端扫码后调用同一接口）。"""
    item = await db.get(AssCheckItem, item_id)
    if not item or item.del_flag == 1:
        raise HTTPException(404, "盘点明细不存在")
    task = await db.get(AssCheckTask, item.task_id)
    if task.status in (2, 3):
        raise HTTPException(400, "任务已完成差异比对，不可再记录")
    if item.check_result is not None:
        raise HTTPException(409, "该明细已盘过")
    if item.asset_id is None:
        raise HTTPException(400, "盘盈行不支持此操作")

    item.check_result = body.check_result
    item.actual_status = body.actual_status
    item.actual_location = body.actual_location
    item.check_user = user.id
    item.check_time = datetime.now()

    # 盘点联动：更新资产最近盘点时间（方案 ass_asset.last_check_time）
    asset = await db.get(AssAsset, item.asset_id)
    if asset:
        asset.last_check_time = datetime.now()
        await write_log(db, asset, ACTION_CHECK, "check", item.task_id, operator_id=user.id)

    if task.status == 0:
        task.status = 1
    return CheckItemOut.model_validate(item)


@router.post("/check-tasks/{task_id}/surplus")
async def add_surplus(
    task_id: int, body: SurplusIn, db: DbDep, user: UserDep, _p: PermCheck
):
    """登记盘盈实物（账外资产，完成后走盘盈入库闭环）。"""
    task = await db.get(AssCheckTask, task_id)
    if not task or task.del_flag == 1:
        raise HTTPException(404, "盘点任务不存在")
    if task.status in (2, 3):
        raise HTTPException(400, "任务已完成差异比对，不可再登记")
    item = AssCheckItem(
        task_id=task_id,
        surplus_name=body.surplus_name,
        surplus_category_id=body.surplus_category_id,
        surplus_price=body.surplus_price,
        check_result=2,  # 盘盈
        actual_location=body.actual_location,
        check_user=user.id,
        check_time=datetime.now(),
    )
    db.add(item)
    await db.flush()
    return CheckItemOut.model_validate(item)


@router.post("/check-tasks/{task_id}/finish")
async def finish_check_task(task_id: int, db: DbDep, user: UserDep, _p: PermCheck):
    """完成任务：自动比对账实、计算差异率；>2% 标记复盘（方案 P1-2）。"""
    task = list(
        await db.scalars(
            select(AssCheckTask).where(AssCheckTask.id == task_id).with_for_update()
        )
    )
    if not task or task[0].del_flag == 1:
        raise HTTPException(404, "盘点任务不存在")
    task = task[0]
    if task.status in (2, 3):
        raise HTTPException(400, "任务已完成")
    if task.status == 0:
        raise HTTPException(400, "任务未开始")

    result = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(func.ifnull(AssCheckItem.check_result == 1, 0)).label("normal"),
                func.sum(func.ifnull(AssCheckItem.check_result == 2, 0)).label("surplus"),
                func.sum(func.ifnull(AssCheckItem.check_result == 3, 0)).label("loss"),
                func.sum(func.ifnull(AssCheckItem.check_result == 4, 0)).label("pos_diff"),
            ).where(AssCheckItem.task_id == task_id, AssCheckItem.del_flag == 0)
        )
    ).one()
    total, normal, surplus, loss, pos_diff = result

    if total == 0 or (normal or 0) + (surplus or 0) + (loss or 0) + (pos_diff or 0) < total:
        raise HTTPException(400, f"尚有 {total - ((normal or 0) + (surplus or 0) + (loss or 0) + (pos_diff or 0))} 项未盘点")

    book_total = task.book_total or 1
    # 差异率 = (盘盈 + 盘亏) / 账面总数
    diff_rate = Decimal((surplus or 0) + (loss or 0)) / Decimal(book_total)
    task.diff_rate = diff_rate.quantize(Decimal("0.0001"))
    task.status = 2 if ((surplus or 0) + (loss or 0)) > 0 else 3
    task.finish_time = datetime.now()
    task.update_by = user.id
    return {
        "total": total,
        "normal": normal or 0,
        "surplus": surplus or 0,
        "loss": loss or 0,
        "position_diff": pos_diff or 0,
        "diff_rate": float(task.diff_rate),
        "need_review": float(task.diff_rate) > 0.02,
        "status": task.status,
    }


@router.post("/check-tasks/{task_id}/handle-diff")
async def handle_diff(task_id: int, db: DbDep, user: UserDep, _p: PermCheck):
    """差异闭环（方案 5.4）：盘盈→自动生成盘盈入库单（即刻生效）；
    盘亏→生成盘亏出库并销账。处理后任务完成。"""
    # 行锁串行化，防止并发重复生成盘盈资产/入库单
    task = list(
        await db.scalars(
            select(AssCheckTask).where(AssCheckTask.id == task_id).with_for_update()
        )
    )
    if not task or task[0].del_flag == 1:
        raise HTTPException(404, "盘点任务不存在")
    task = task[0]
    if task.status != 2:
        raise HTTPException(400, "任务不在差异处理状态")

    items = list(
        await db.scalars(
            select(AssCheckItem).where(
                AssCheckItem.task_id == task_id,
                AssCheckItem.check_result.in_([2, 3, 4]),
                AssCheckItem.diff_handle_status == 0,
            )
        )
    )
    import uuid as _uuid

    surplus_items = [i for i in items if i.check_result == 2]
    loss_items = [i for i in items if i.check_result == 3]
    pos_diff_items = [i for i in items if i.check_result == 4]

    # 盘盈 → 盘盈入库单（自动通过）
    if surplus_items:
        in_doc = AssStockIn(
            in_no=await next_doc_no(db, "stock_in"),
            warehouse_id=None,  # 盘盈入库无仓库约束
            in_type=4,
            in_date=datetime.now().date(),
            total_num=len(surplus_items),
            remark=f"盘点 {task.task_no} 盘盈自动入库",
            status=2,
            create_by=user.id,
        )
        db.add(in_doc)
        await db.flush()
        org = await _task_org(db, task)
        for it in surplus_items:
            cat = await db.get(AssCategory, it.surplus_category_id) if it.surplus_category_id else None
            if cat is None:
                # 盘盈未指定分类 → 归入「其他」根类（F01），无则取首个根类
                cat = await db.scalar(
                    select(AssCategory).where(
                        AssCategory.code == "F01", AssCategory.del_flag == 0
                    )
                )
            if cat is None:
                cat = (
                    await db.scalars(
                        select(AssCategory)
                        .where(AssCategory.parent_id == 0, AssCategory.del_flag == 0)
                        .order_by(AssCategory.id)
                    )
                ).first()
            if cat is None:
                raise HTTPException(400, "缺少资产分类档案，无法为盘盈资产建档")

            code = await next_asset_code(db, org.org_code if org else "GD", cat.code)
            asset = AssAsset(
                asset_code=code,
                asset_name=it.surplus_name or "盘盈资产",
                category_id=cat.id,
                org_id=org.id if org else None,
                status=1,
                price=it.surplus_price,
                net_value=it.surplus_price,
                location_detail=it.actual_location,
                qrcode=_uuid.uuid4().hex,
                create_by=user.id,
            )
            db.add(asset)
            await db.flush()
            await write_log(db, asset, ACTION_CHECK, "check", task_id, operator_id=user.id)
            db.add(
                AssStockInItem(
                    in_id=in_doc.id, asset_id=asset.id,
                    category_id=cat.id,
                    asset_name=it.surplus_name, num=1, unit_price=it.surplus_price,
                    amount=it.surplus_price,
                )
            )
            it.diff_handle_status = 1
            it.diff_handle_note = "盘盈入库"

    # 盘亏 → 销账（出库）
    if loss_items:
        for it in loss_items:
            asset = await db.get(AssAsset, it.asset_id) if it.asset_id else None
            if asset and asset.status not in (5, 6):
                before = snapshot(asset)
                asset.status = 5
                asset.warehouse_id = None
                asset.version += 1
                await write_log(
                    db, asset, ACTION_CHECK, "check_loss", task_id,
                    before=before, operator_id=user.id,
                )
            it.diff_handle_status = 1
            it.diff_handle_note = "盘亏销账"

    # 位置异常 → 更新资产账面位置
    if pos_diff_items:
        for it in pos_diff_items:
            asset = await db.get(AssAsset, it.asset_id) if it.asset_id else None
            if asset and it.actual_location:
                before = snapshot(asset)
                asset.location_detail = it.actual_location
                asset.version += 1
                await write_log(
                    db, asset, ACTION_CHECK, "check_location", task_id,
                    before=before, operator_id=user.id,
                )
            it.diff_handle_status = 1
            it.diff_handle_note = "位置更新"

    task.status = 3
    task.update_by = user.id
    return {
        "ok": True,
        "surplus_handled": len(surplus_items),
        "loss_handled": len(loss_items),
        "pos_diff_handled": len(pos_diff_items),
    }


async def _task_org(db, task):
    """取盘点任务的核算公司（盘盈入库建档用）。"""
    from app.models.sys import SysOrg

    if task.scope_type == 1:
        return await db.get(SysOrg, task.scope_id)
    conds = [AssAsset.del_flag == 0] + _scope_asset_conds(task.scope_type, task.scope_id)
    org_id = (await db.execute(select(AssAsset.org_id).where(*conds).limit(1))).scalar()
    if org_id:
        return await db.get(SysOrg, org_id)
    return None


# ============================================================
# 盘点报表输出（用户新增核心需求）：明细表 / 差异表 / 汇总表
# ============================================================
ASSET_STATUS = {0: "待入库", 1: "在库", 2: "领用中", 3: "维修中", 4: "调拨中", 5: "已报废", 6: "已处置", 7: "借用中"}


def _task_title_rows(task, scope_name: str) -> list[list]:
    return [
        [f"盘点报表（{task.task_name}）", ""],
        [f"任务编号：{task.task_no}", f"盘点类型：{TYPE_LABEL.get(task.check_type, task.check_type)}"],
        [f"盘点范围：{scope_name}", f"状态：{STATUS_LABEL.get(task.status, task.status)}"],
        [
            f"计划期间：{task.plan_start or ''} ~ {task.plan_end or ''}",
            f"账面总数：{task.book_total}",
        ],
        [
            f"差异率：{float(task.diff_rate) * 100:.2f}%" if task.diff_rate is not None else "差异率：未完成",
            f"导出时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        ],
        [],
    ]


@router.get("/check-tasks/{task_id}/export")
async def export_check_report(task_id: int, db: DbDep, user: UserDep, type: str = "detail"):
    """type=detail 盘点明细表 / diff 差异表 / summary 汇总表。"""
    task = await db.get(AssCheckTask, task_id)
    if not task or task.del_flag == 1:
        raise HTTPException(404, "盘点任务不存在")
    scope_name = await _scope_name(db, task)

    conds = [AssCheckItem.task_id == task_id, AssCheckItem.del_flag == 0]
    if type == "diff":
        conds.append(AssCheckItem.check_result.in_([2, 3, 4]))
    q = (
        select(
            AssCheckItem,
            AssAsset.asset_code,
            AssAsset.asset_name,
            AssCategory.category_name,
            AssAsset.price,
        )
        .join(AssAsset, AssAsset.id == AssCheckItem.asset_id, isouter=True)
        .join(AssCategory, AssCategory.id == AssAsset.category_id, isouter=True)
        .where(*conds)
        .order_by(AssCheckItem.id)
    )

    # 聚合统计（单条查询，不全量加载）
    stat = (
        await db.execute(
            select(
                func.count().label("n_total"),
                func.sum(func.ifnull(AssCheckItem.check_result == 1, 0)).label("n_normal"),
                func.sum(func.ifnull(AssCheckItem.check_result == 2, 0)).label("n_surplus"),
                func.sum(func.ifnull(AssCheckItem.check_result == 3, 0)).label("n_loss"),
                func.sum(func.ifnull(AssCheckItem.check_result == 4, 0)).label("n_pos"),
                func.sum(func.ifnull(AssCheckItem.check_result.is_(None), 0)).label("n_unchecked"),
                func.coalesce(
                    func.sum(case((AssCheckItem.check_result == 3, AssAsset.price), else_=0)), 0
                ).label("loss_amount"),
                func.coalesce(
                    func.sum(case((AssCheckItem.check_result == 2, AssCheckItem.surplus_price), else_=0)), 0
                ).label("surplus_amount"),
            )
            .select_from(AssCheckItem)
            .join(AssAsset, AssAsset.id == AssCheckItem.asset_id, isouter=True)
            .where(*conds)
        )
    ).one()
    n_total = stat.n_total or 0
    n_normal = stat.n_normal or 0
    n_surplus = stat.n_surplus or 0
    n_loss = stat.n_loss or 0
    n_pos = stat.n_pos or 0
    n_unchecked = stat.n_unchecked or 0
    loss_amount = float(stat.loss_amount or 0)
    surplus_amount = float(stat.surplus_amount or 0)

    BATCH_SIZE = 2000

    async def rows_generator():
        """分批查询流式导出，避免一次性全量加载。"""
        offset = 0
        while True:
            batch = (await db.execute(q.offset(offset).limit(BATCH_SIZE))).all()
            if not batch:
                break
            for r in batch:
                yield fmt_row(r)
            if len(batch) < BATCH_SIZE:
                break
            offset += BATCH_SIZE

    def fmt_row(r) -> list:
        item, code, name, cat_name, price = r
        result = RESULT_LABEL.get(item.check_result, "未盘")
        return [
            code or "（盘盈）",
            name or item.surplus_name or "",
            cat_name or "",
            ASSET_STATUS.get(item.book_status, "") if item.book_status is not None else "",
            item.book_location or "",
            result,
            ASSET_STATUS.get(item.actual_status, "") if item.actual_status is not None else "",
            item.actual_location or "",
            str(item.check_time or "")[:19],
            float(item.surplus_price if item.surplus_price is not None else (price or 0)),
            "已处理" if item.diff_handle_status else ("待处理" if item.check_result in (2, 3, 4) else ""),
            item.diff_handle_note or "",
        ]

    headers = [
        "资产编码", "资产名称", "分类", "账面状态", "账面位置", "盘点结果",
        "实盘状态", "实盘位置", "盘点时间", "价值(元)", "差异处理", "处理说明",
    ]
    col_widths = [18, 22, 14, 10, 16, 10, 10, 16, 19, 12, 10, 16]

    title = _task_title_rows(task, scope_name)
    if type == "summary":
        buf = await build_excel(
            headers=["统计项", "数量(项)", "金额(元)", "说明"],
            rows=[
                ["账面总数", task.book_total, "", "任务创建时冻结的快照"],
                ["已盘数", n_total, "", "含盘盈登记"],
                ["正常", n_normal, "", "账实一致"],
                ["盘盈", n_surplus, surplus_amount, "账外资产，待盘盈入库"],
                ["盘亏", n_loss, loss_amount, "待差异审批销账/赔偿"],
                ["位置异常", n_pos, "", "实物在但位置与账面不符"],
                ["未盘", n_unchecked, "", ""],
                [
                    "差异率",
                    f"{float(task.diff_rate) * 100:.2f}%" if task.diff_rate is not None else "-",
                    "",
                    "差异率 = (盘盈+盘亏)/账面总数，>2% 需复盘（方案 P1-2）",
                ],
                ["盘点结论",
                 "",
                 "",
                 "账实一致" if n_surplus + n_loss == 0 and n_pos == 0 else "存在差异，需按差异表闭环处理"],
            ],
            sheet_name="盘点汇总表",
            col_widths=[14, 12, 14, 46],
            title_rows=title,
        )
        filename = f"盘点汇总表_{task.task_no}.xlsx"
    elif type == "diff":
        buf = await build_excel(
            headers=headers,
            rows=rows_generator(),
            sheet_name="盘盈盘亏差异表",
            col_widths=col_widths,
            title_rows=title + [
                [f"盘盈 {n_surplus} 项（估值 ¥{surplus_amount:,.2f}）",
                 f"盘亏 {n_loss} 项（账面 ¥{loss_amount:,.2f}）"],
                [],
            ],
        )
        filename = f"盘盈盘亏差异表_{task.task_no}.xlsx"
    else:
        buf = await build_excel(
            headers=headers,
            rows=rows_generator(),
            sheet_name="盘点明细表",
            col_widths=col_widths,
            title_rows=title + [
                [f"正常 {n_normal} / 盘盈 {n_surplus} / 盘亏 {n_loss} / 位置异常 {n_pos} / 未盘 {n_unchecked}"],
                [],
            ],
        )
        filename = f"盘点明细表_{task.task_no}.xlsx"

    from urllib.parse import quote

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/check-tasks/{task_id}/summary", response_model=CheckTaskSummary)
async def check_task_summary(task_id: int, db: DbDep, user: UserDep):
    """盘点汇总数据（前端页面展示）。"""
    task = await db.get(AssCheckTask, task_id)
    if not task or task.del_flag == 1:
        raise HTTPException(404, "盘点任务不存在")
    result = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(func.ifnull(AssCheckItem.check_result == 1, 0)).label("normal"),
                func.sum(func.ifnull(AssCheckItem.check_result == 2, 0)).label("surplus"),
                func.sum(func.ifnull(AssCheckItem.check_result == 3, 0)).label("loss"),
                func.sum(func.ifnull(AssCheckItem.check_result == 4, 0)).label("pos"),
            ).where(AssCheckItem.task_id == task_id, AssCheckItem.del_flag == 0)
        )
    ).one()
    total, normal, surplus, loss, pos = result
    checked = (normal or 0) + (surplus or 0) + (loss or 0) + (pos or 0)
    loss_amount = await db.scalar(
        select(func.coalesce(func.sum(AssAsset.price), 0))
        .join(AssCheckItem, AssCheckItem.asset_id == AssAsset.id)
        .where(AssCheckItem.task_id == task_id, AssCheckItem.check_result == 3)
    )
    surplus_amount = await db.scalar(
        select(func.coalesce(func.sum(AssCheckItem.surplus_price), 0))
        .where(AssCheckItem.task_id == task_id, AssCheckItem.check_result == 2)
    )
    return CheckTaskSummary(
        task_id=task.id,
        task_no=task.task_no,
        task_name=task.task_name,
        check_type=task.check_type,
        status=task.status,
        book_total=task.book_total,
        checked=checked,
        normal=normal or 0,
        surplus=surplus or 0,
        loss=loss or 0,
        position_diff=pos or 0,
        unchecked=total - checked,
        diff_rate=task.diff_rate if task.diff_rate is not None else Decimal(0),
        loss_amount=Decimal(loss_amount or 0),
        surplus_amount=Decimal(surplus_amount or 0),
    )


async def _scope_name(db, task) -> str:
    if task.scope_type == 1:
        from app.models.sys import SysOrg

        org = await db.get(SysOrg, task.scope_id)
        return f"公司 / {org.org_name if org else task.scope_id}"
    if task.scope_type == 2:
        from app.models.sys import SysOrg

        org = await db.get(SysOrg, task.scope_id)
        return f"项目 / {org.org_name if org else task.scope_id}"
    if task.scope_type == 3:
        from app.models.archive import AssWarehouse

        wh = await db.get(AssWarehouse, task.scope_id)
        return f"仓库 / {wh.warehouse_name if wh else task.scope_id}"
    if task.scope_type == 4:
        from app.models.archive import AssSpace

        sp = await db.get(AssSpace, task.scope_id)
        return f"空间 / {sp.space_name if sp else task.scope_id}"
    if task.scope_type == 5:
        from app.models.sys import SysOrg

        org = await db.get(SysOrg, task.scope_id)
        return f"部门 / {org.org_name if org else task.scope_id}"
    return str(task.scope_id)
