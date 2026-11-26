"""业务单据 API：采购/入库/出库/调拨/报废 + 审批待办。

状态机（方案 6.3 单据引擎）：0草稿 → 1审批中 → 2已通过 / 3已驳回 / 4已取消。
并发安全：审批与资产状态流转均用 SELECT ... FOR UPDATE 行锁串行化，
配合单据状态前置校验，杜绝重复审批/重复扣减。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, or_, select

from app.core.deps import CurrentUser, DbDep, UserDep, require_perm
from app.core.pagination import PageData, PageParams
from app.models.archive import AssCategory, AssSpace, AssWarehouse
from app.models.asset import AssAsset
from app.models.check import WfInstance, WfTask
from app.models.doc import (
    AssBorrow,
    AssBorrowItem,
    AssPurchaseApply,
    AssPurchaseApplyItem,
    AssReturn,
    AssReturnItem,
    AssScrap,
    AssScrapItem,
    AssStockIn,
    AssStockInItem,
    AssStockOut,
    AssStockOutItem,
    AssTransfer,
    AssTransferItem,
)
from app.models.consumable import (
    ConInbound,
    ConInboundItem,
    ConIssue,
    ConIssueItem,
    ConPurchase,
    ConPurchaseItem,
    ConStock,
)
from app.models.sys import SysOrg, SysUser
from app.schemas.doc import (
    ApproveIn,
    ApprovalTaskOut,
    ApprovalTodoOut,
    BorrowDetailOut,
    BorrowIn,
    BorrowItemOut,
    BorrowOut,
    DelegateIn,
    ManualApproveIn,
    PurchaseDetailOut,
    PurchaseIn,
    PurchaseItemOut,
    PurchaseOut,
    ReturnDetailOut,
    ReturnDocIn,
    ReturnIn,
    ReturnItemOut,
    ReturnOut,
    ScrapDetailOut,
    ScrapIn,
    ScrapOut,
    StockInDetailOut,
    StockInIn,
    StockInOut,
    StockOutDetailOut,
    StockOutIn,
    StockOutOut,
    TerminateIn,
    TransferDetailOut,
    TransferIn,
    TransferItemOut,
    TransferOut,
)
from app.services.asset_log_service import (
    ACTION_BORROW,
    ACTION_RECEIVE,
    ACTION_RETURN,
    ACTION_SCRAP,
    ACTION_STOCK_IN,
    ACTION_TRANSFER,
    snapshot,
    write_log,
)
from app.services.seq_service import next_asset_code, next_doc_no, peek_doc_no
from app.services import message_service as msg
from app.services import workflow_service as wf

router = APIRouter(tags=["业务单据"])

DOC_STATUS = {0: "草稿", 1: "审批中", 2: "已通过", 3: "已驳回", 4: "已取消"}


def _scope_cond(user, org_col, user_col=None):
    """单据列表数据权限。「仅本人」档未传 user_col 时回退 create_by，避免拼入布尔 False。"""
    if user.org_ids is None:
        return None
    if not user.org_ids:
        if user_col is None:
            user_col = org_col.table.c.create_by
        return user_col == user.id
    return org_col.in_(user.org_ids)


# ============================================================
# 采购申请
# ============================================================
@router.get("/purchases", response_model=PageData[PurchaseOut])
async def list_purchases(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    status: int | None = None,
    keyword: str | None = None,
):
    conds = [AssPurchaseApply.del_flag == 0]
    sc = _scope_cond(user, AssPurchaseApply.org_id, AssPurchaseApply.apply_user)
    if sc is not None:
        conds.append(sc)
    if status is not None:
        conds.append(AssPurchaseApply.status == status)
    if keyword:
        conds.append(AssPurchaseApply.apply_no.like(f"%{keyword}%"))
    total = await db.scalar(
        select(func.count()).select_from(AssPurchaseApply).where(*conds)
    )
    # 关联查询组织名称
    from app.models.sys import SysOrg
    rows = (
        await db.execute(
            select(AssPurchaseApply, SysOrg.org_name)
            .join(SysOrg, SysOrg.id == AssPurchaseApply.org_id, isouter=True)
            .where(*conds)
            .order_by(AssPurchaseApply.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    ).all()
    records = []
    for r in rows:
        rec = PurchaseOut.model_validate(r[0])
        rec.org_name = r[1]  # 组织名称
        records.append(rec)
    iids = await _instance_ids(db, "purchase", [r[0].id for r in rows])
    for rec in records:
        rec.wf_instance_id = iids.get(rec.id)
    return PageData.build(total, params, records)


@router.post("/purchases", response_model=PurchaseDetailOut)
async def create_purchase(body: PurchaseIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("purchase:create"))]):
    total = sum(
        (i.unit_price or 0) * i.num for i in body.items
    )
    doc = AssPurchaseApply(
        apply_no=await next_doc_no(db, "purchase"),
        org_id=body.org_id,
        project_id=body.project_id,
        apply_user=user.id,
        apply_date=body.apply_date or date.today(),
        total_amount=Decimal(str(total)).quantize(Decimal("0.01")),
        budget_item=body.budget_item,
        cost_subject=body.cost_subject,
        supplier_id=body.supplier_id,
        contract_no=body.contract_no,
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        db.add(
            AssPurchaseApplyItem(
                apply_id=doc.id,
                category_id=i.category_id,
                asset_name=i.asset_name,
                spec=i.spec,
                num=i.num,
                unit_price=i.unit_price,
                amount=Decimal(str((i.unit_price or 0) * i.num)).quantize(Decimal("0.01")),
                purpose=i.purpose,
                group_id=i.group_id,
            )
        )
    return PurchaseDetailOut(
        **PurchaseOut.model_validate(doc).model_dump(),
        items=[],
        apply_user_name=user.real_name,
    )


@router.get("/purchases/approved")
async def list_approved_purchases(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    keyword: str | None = None,
    org_id: int | None = None,
):
    """查询审批通过的采购申请列表（供入库单关联选择）。"""
    conds = [AssPurchaseApply.del_flag == 0, AssPurchaseApply.status == 2]
    sc = _scope_cond(user, AssPurchaseApply.org_id, AssPurchaseApply.apply_user)
    if sc is not None:
        conds.append(sc)
    if keyword:
        conds.append(AssPurchaseApply.apply_no.like(f"%{keyword}%"))
    if org_id:
        conds.append(AssPurchaseApply.org_id == org_id)
    
    # 子查询：计算每个采购申请已入库的总数
    inbound_subq = (
        select(
            AssStockInItem.in_id,
            func.coalesce(func.sum(AssStockInItem.num), 0).label("inbound_num")
        )
        .join(AssStockIn, AssStockIn.id == AssStockInItem.in_id)
        .where(AssStockIn.del_flag == 0, AssStockIn.status == 2)
        .group_by(AssStockInItem.in_id)
    ).subquery()
    
    # 查询采购申请及其已入库数量
    query = (
        select(
            AssPurchaseApply,
            func.coalesce(inbound_subq.c.inbound_num, 0).label("inbound_num"),
            SysOrg.org_name,
        )
        .join(SysOrg, SysOrg.id == AssPurchaseApply.org_id, isouter=True)
        .outerjoin(inbound_subq, inbound_subq.c.in_id == AssPurchaseApply.id)
        .where(*conds)
        .order_by(AssPurchaseApply.id.desc())
    )
    
    total = await db.scalar(
        select(func.count()).select_from(AssPurchaseApply).where(*conds)
    )
    
    rows = (await db.execute(query.offset(params.offset).limit(params.limit))).all()
    
    records = []
    for r in rows:
        doc = r[0]
        inbound_num = r[1]
        org_name = r[2]
        
        # 计算采购总数
        items = list(await db.scalars(
            select(AssPurchaseApplyItem).where(AssPurchaseApplyItem.apply_id == doc.id)
        ))
        total_num = sum(i.num for i in items)
        
        # 判断是否已全部入库
        fully_inbound = inbound_num >= total_num and total_num > 0
        
        # 手动构建返回数据
        records.append({
            "id": doc.id,
            "apply_no": doc.apply_no,
            "org_id": doc.org_id,
            "project_id": doc.project_id,
            "apply_user": doc.apply_user,
            "apply_date": doc.apply_date,
            "total_amount": doc.total_amount,
            "budget_item": doc.budget_item,
            "cost_subject": doc.cost_subject,
            "supplier_id": doc.supplier_id,
            "contract_no": doc.contract_no,
            "wf_instance_id": doc.wf_instance_id,
            "status": doc.status,
            "create_time": doc.create_time,
            "org_name": org_name,
            "total_num": total_num,
            "inbound_num": inbound_num,
            "remaining_num": max(0, total_num - inbound_num),
            "fully_inbound": fully_inbound,
        })
    
    return PageData.build(total, params, records)


@router.get("/purchases/{pid}", response_model=PurchaseDetailOut)
async def get_purchase(pid: int, db: DbDep, user: UserDep):
    doc = await db.get(AssPurchaseApply, pid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "采购单不存在")
    items = await db.scalars(
        select(AssPurchaseApplyItem).where(AssPurchaseApplyItem.apply_id == pid)
    )
    apply_user = await db.get(SysUser, doc.apply_user)
    return PurchaseDetailOut(
        **PurchaseOut.model_validate(doc).model_dump(),
        items=[PurchaseItemOut.model_validate(i) for i in items],
        apply_user_name=apply_user.real_name if apply_user else None,
    )


@router.delete("/purchases/{pid}")
async def delete_purchase(
    pid: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("purchase:delete"))],
):
    doc = await db.get(AssPurchaseApply, pid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "采购单不存在")
    if doc.status != 0:
        raise HTTPException(400, "仅草稿可删除")
    if not user.is_admin and doc.apply_user != user.id:
        raise HTTPException(403, "只能删除自己创建的草稿")
    doc.del_flag = 1
    doc.update_by = user.id
    return {"ok": True}


@router.get("/purchases/{pid}/items-for-inbound")
async def purchase_items_for_inbound(pid: int, db: DbDep, user: UserDep):
    """查询采购申请的可入库明细（排除已全部入库的行）。"""
    doc = await db.get(AssPurchaseApply, pid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "采购单不存在")
    if doc.status != 2:
        raise HTTPException(400, "采购单未审批通过")
    
    # 查询所有明细
    items = list(await db.scalars(
        select(AssPurchaseApplyItem).where(AssPurchaseApplyItem.apply_id == pid)
    ))
    
    # 查询已入库数量
    inbound_result = (
        await db.execute(
            select(
                AssStockInItem.asset_name,
                func.coalesce(func.sum(AssStockInItem.num), 0).label("inbound_num")
            )
            .join(AssStockIn, AssStockIn.id == AssStockInItem.in_id)
            .where(
                AssStockIn.del_flag == 0,
                AssStockIn.status == 2,
                AssStockIn.purchase_id == pid
            )
            .group_by(AssStockInItem.asset_name)
        )
    ).all()
    
    inbound_map = {r[0]: r[1] for r in inbound_result}
    
    # 过滤出可入库的明细（未全部入库）
    result_items = []
    for item in items:
        inbound_num = inbound_map.get(item.asset_name, 0)
        remaining = max(0, item.num - inbound_num)
        if remaining > 0:
            result_items.append({
                "id": item.id,
                "category_id": item.category_id,
                "asset_name": item.asset_name,
                "spec": item.spec,
                "num": remaining,
                "unit_price": item.unit_price,
                "amount": (item.unit_price or 0) * remaining,
                "total_num": item.num,
                "inbound_num": inbound_num,
            })
    
    return {
        "purchase_id": doc.id,
        "apply_no": doc.apply_no,
        "org_id": doc.org_id,
        "supplier_id": doc.supplier_id,
        "items": result_items,
    }


# ============================================================
# 入库单
# ============================================================
@router.get("/stock-ins", response_model=PageData[StockInOut])
async def list_stock_ins(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    status: int | None = None,
    keyword: str | None = None,
    warehouse_id: int | None = None,
):
    conds = [AssStockIn.del_flag == 0]
    sc = _scope_cond(user, AssStockIn.org_id)
    if sc is not None:
        conds.append(sc)
    if status is not None:
        conds.append(AssStockIn.status == status)
    if warehouse_id:
        conds.append(AssStockIn.warehouse_id == warehouse_id)
    if keyword:
        conds.append(AssStockIn.in_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(AssStockIn).where(*conds))
    rows = list(
        await db.scalars(
            select(AssStockIn).where(*conds).order_by(AssStockIn.id.desc())
            .offset(params.offset).limit(params.limit)
        )
    )
    records = [StockInOut.model_validate(r) for r in rows]
    iids = await _instance_ids(db, "stock_in", [r.id for r in rows])
    for rec in records:
        rec.wf_instance_id = iids.get(rec.id)
    return PageData.build(total, params, records)


@router.post("/stock-ins", response_model=StockInDetailOut)
async def create_stock_in(body: StockInIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("stockin:create"))]):
    wh = await db.get(AssWarehouse, body.warehouse_id)
    if not wh or wh.status != 1:
        raise HTTPException(400, "仓库不存在或已停用")
    
    # 采购入库必须关联采购申请
    if body.in_type == 1:
        if not body.purchase_id:
            raise HTTPException(400, "采购入库必须选择采购申请")
        # 行锁串行化同一采购单的并发入库，防止超采购量入库
        purchase = (
            await db.scalars(
                select(AssPurchaseApply)
                .where(AssPurchaseApply.id == body.purchase_id)
                .with_for_update()
            )
        ).first()
        if not purchase or purchase.del_flag == 1:
            raise HTTPException(400, "采购申请不存在")
        if purchase.status != 2:
            raise HTTPException(400, "采购申请未审批通过")
        # 校验采购申请的可入库数量
        for item in body.items:
            # 查询该资产名称在采购申请中的数量和已入库数量
            purchase_items = list(await db.scalars(
                select(AssPurchaseApplyItem).where(
                    AssPurchaseApplyItem.apply_id == body.purchase_id,
                    AssPurchaseApplyItem.asset_name == item.asset_name
                )
            ))
            if not purchase_items:
                raise HTTPException(400, f"资产「{item.asset_name}」不在采购申请中")
            total_purchase_num = sum(p.num for p in purchase_items)
            inbound_result = await db.scalar(
                select(func.coalesce(func.sum(AssStockInItem.num), 0))
                .join(AssStockIn, AssStockIn.id == AssStockInItem.in_id)
                .where(
                    AssStockIn.del_flag == 0,
                    AssStockIn.status == 2,
                    AssStockIn.purchase_id == body.purchase_id,
                    AssStockInItem.asset_name == item.asset_name
                )
            )
            inbound_num = inbound_result or 0
            if inbound_num + item.num > total_purchase_num:
                raise HTTPException(400, f"资产「{item.asset_name}」入库数量超出采购数量（可入库{total_purchase_num - inbound_num}）")
    
    total_num = sum(i.num for i in body.items)
    total_price = sum((i.unit_price or 0) * i.num for i in body.items)
    doc = AssStockIn(
        in_no=await next_doc_no(db, "stock_in"),
        warehouse_id=body.warehouse_id,
        in_type=body.in_type,
        purchase_id=body.purchase_id,
        supplier_id=body.supplier_id,
        in_date=body.in_date or date.today(),
        total_num=total_num,
        total_price=Decimal(str(total_price)).quantize(Decimal("0.01")),
        org_id=body.org_id or wh.org_id,
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        db.add(
            AssStockInItem(
                in_id=doc.id,
                category_id=i.category_id,
                asset_name=i.asset_name,
                num=i.num,
                unit_price=i.unit_price,
                amount=Decimal(str((i.unit_price or 0) * i.num)).quantize(Decimal("0.01")),
            )
        )
    return StockInDetailOut(**StockInOut.model_validate(doc).model_dump(), items=[])


@router.get("/stock-ins/{iid}", response_model=StockInDetailOut)
async def get_stock_in(iid: int, db: DbDep, user: UserDep):
    doc = await db.get(AssStockIn, iid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "入库单不存在")
    items = await db.scalars(select(AssStockInItem).where(AssStockInItem.in_id == iid))
    wh = await db.get(AssWarehouse, doc.warehouse_id)
    return StockInDetailOut(
        **StockInOut.model_validate(doc).model_dump(),
        items=list(items),
        warehouse_name=wh.warehouse_name if wh else None,
    )


# ============================================================
# 出库单（领用）
# ============================================================
@router.get("/stock-outs", response_model=PageData[StockOutOut])
async def list_stock_outs(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    status: int | None = None,
    keyword: str | None = None,
):
    conds = [AssStockOut.del_flag == 0]
    sc = _scope_cond(user, AssStockOut.org_id)
    if sc is not None:
        conds.append(sc)
    if status is not None:
        conds.append(AssStockOut.status == status)
    if keyword:
        conds.append(AssStockOut.out_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(AssStockOut).where(*conds))
    rows = list(
        await db.scalars(
            select(AssStockOut).where(*conds).order_by(AssStockOut.id.desc())
            .offset(params.offset).limit(params.limit)
        )
    )
    records = [StockOutOut.model_validate(r) for r in rows]
    iids = await _instance_ids(db, "stock_out", [r.id for r in rows])
    for rec in records:
        rec.wf_instance_id = iids.get(rec.id)
    return PageData.build(total, params, records)


@router.post("/stock-outs", response_model=StockOutDetailOut)
async def create_stock_out(body: StockOutIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("stockout:create"))]):
    if body.out_type == 1 and not body.receive_user:
        raise HTTPException(400, "领用出库必须指定领用人")
    asset_ids = [i.asset_id for i in body.items]
    assets = dict(
        (a.id, a)
        for a in await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(asset_ids)).with_for_update()
        )
    )
    for aid in asset_ids:
        a = assets.get(aid)
        if not a:
            raise HTTPException(400, f"资产 {aid} 不存在")
        if a.status != 1:
            raise HTTPException(400, f"资产 {a.asset_code} 非在库状态，无法出库")
        if a.warehouse_id != body.warehouse_id:
            raise HTTPException(400, f"资产 {a.asset_code} 不属于该仓库")

    doc = AssStockOut(
        out_no=await next_doc_no(db, "stock_out"),
        warehouse_id=body.warehouse_id,
        out_type=body.out_type,
        receive_user=body.receive_user,
        out_date=body.out_date or date.today(),
        total_num=len(asset_ids),
        org_id=body.org_id,
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        db.add(
            AssStockOutItem(
                out_id=doc.id, asset_id=i.asset_id, num=1, use_location=i.use_location
            )
        )
    return StockOutDetailOut(**StockOutOut.model_validate(doc).model_dump(), items=[])


@router.get("/stock-outs/{oid}", response_model=StockOutDetailOut)
async def get_stock_out(oid: int, db: DbDep, user: UserDep):
    doc = await db.get(AssStockOut, oid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "出库单不存在")
    items = await db.scalars(select(AssStockOutItem).where(AssStockOutItem.out_id == oid))
    wh = await db.get(AssWarehouse, doc.warehouse_id)
    ru = await db.get(SysUser, doc.receive_user) if doc.receive_user else None
    return StockOutDetailOut(
        **StockOutOut.model_validate(doc).model_dump(),
        items=list(items),
        warehouse_name=wh.warehouse_name if wh else None,
        receive_user_name=ru.real_name if ru else None,
    )


# ============================================================
# 调拨单
# ============================================================
@router.get("/transfers", response_model=PageData[TransferOut])
async def list_transfers(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    status: int | None = None,
    keyword: str | None = None,
):
    conds = [AssTransfer.del_flag == 0]
    sc = _scope_cond(user, AssTransfer.out_org_id)
    if sc is not None:
        # 新建调拨不再填写调出/调入公司（字段为空）：范围用户额外可见自己发起的调拨单
        conds.append(or_(sc, AssTransfer.apply_user == user.id))
    if status is not None:
        conds.append(AssTransfer.status == status)
    if keyword:
        conds.append(AssTransfer.transfer_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(AssTransfer).where(*conds))
    rows = list(
        await db.scalars(
            select(AssTransfer).where(*conds).order_by(AssTransfer.id.desc())
            .offset(params.offset).limit(params.limit)
        )
    )
    records = [TransferOut.model_validate(r) for r in rows]
    # 批量补位置名称（仓库/项目空间/部门，按调拨类型取用）
    wh_ids = {x for r in rows for x in (r.out_warehouse_id, r.in_warehouse_id) if x}
    sp_ids = {x for r in rows for x in (r.out_project_id, r.in_project_id) if x}
    dp_ids = {x for r in rows for x in (r.out_dept_id, r.in_dept_id) if x}
    wh_names = {
        w.id: w.warehouse_name
        for w in await db.scalars(select(AssWarehouse).where(AssWarehouse.id.in_(wh_ids)))
    } if wh_ids else {}
    sp_names = {
        s.id: s.space_name
        for s in await db.scalars(select(AssSpace).where(AssSpace.id.in_(sp_ids)))
    } if sp_ids else {}
    dp_names = {
        o.id: o.org_name
        for o in await db.scalars(select(SysOrg).where(SysOrg.id.in_(dp_ids)))
    } if dp_ids else {}
    iids = await _instance_ids(db, "transfer", [r.id for r in rows])
    for rec in records:
        rec.wf_instance_id = iids.get(rec.id)
        rec.out_warehouse_name = wh_names.get(rec.out_warehouse_id)
        rec.in_warehouse_name = wh_names.get(rec.in_warehouse_id)
        rec.out_space_name = sp_names.get(rec.out_project_id)
        rec.in_space_name = sp_names.get(rec.in_project_id)
        rec.out_dept_name = dp_names.get(rec.out_dept_id)
        rec.in_dept_name = dp_names.get(rec.in_dept_id)
    return PageData.build(total, params, records)


@router.post("/transfers", response_model=TransferDetailOut)
async def create_transfer(body: TransferIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("transfer:create"))]):
    # 按调拨类型校验调出/调入维度
    if body.transfer_type == 1:
        out_wh = await db.get(AssWarehouse, body.out_warehouse_id)
        in_wh = await db.get(AssWarehouse, body.in_warehouse_id)
        if not out_wh or out_wh.status != 1:
            raise HTTPException(400, "调出仓库不存在或已停用")
        if not in_wh or in_wh.status != 1:
            raise HTTPException(400, "调入仓库不存在或已停用")
    elif body.transfer_type == 2:
        out_space = await db.get(AssSpace, body.out_project_id)
        in_space = await db.get(AssSpace, body.in_project_id)
        if not out_space or out_space.del_flag == 1:
            raise HTTPException(400, "调出项目空间不存在")
        if not in_space or in_space.del_flag == 1:
            raise HTTPException(400, "调入项目空间不存在")
    else:  # 4 部门调拨
        out_dept = await db.get(SysOrg, body.out_dept_id)
        in_dept = await db.get(SysOrg, body.in_dept_id)
        if not out_dept or out_dept.status != 1:
            raise HTTPException(400, "调出部门不存在或已停用")
        if not in_dept or in_dept.status != 1:
            raise HTTPException(400, "调入部门不存在或已停用")

    # 资产资格：按调出维度过滤
    # 仓库调拨：限在库(1)且在调出仓库
    # 项目空间调拨：限在库(1)/领用中(2)且在调出空间
    # 部门调拨：限在库(1)/领用中(2)且使用部门为调出部门
    asset_ids = [i.asset_id for i in body.items]
    assets = dict(
        (a.id, a)
        for a in await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(asset_ids)).with_for_update()
        )
    )
    for aid in asset_ids:
        a = assets.get(aid)
        if not a:
            raise HTTPException(400, f"资产 {aid} 不存在")
        if body.transfer_type == 1:
            if a.status != 1:
                raise HTTPException(400, f"资产 {a.asset_code} 非在库状态，无法调拨")
            if a.warehouse_id != body.out_warehouse_id:
                raise HTTPException(400, f"资产 {a.asset_code} 不在调出仓库")
        elif body.transfer_type == 2:
            if a.status not in (1, 2):
                raise HTTPException(400, f"资产 {a.asset_code} 非在库/领用中状态，无法调拨")
            if a.space_id != body.out_project_id:
                raise HTTPException(400, f"资产 {a.asset_code} 不在调出项目空间")
        else:
            if a.status not in (1, 2):
                raise HTTPException(400, f"资产 {a.asset_code} 非在库/领用中状态，无法调拨")
            if a.use_dept_id != body.out_dept_id:
                raise HTTPException(400, f"资产 {a.asset_code} 不属于调出部门")

    doc = AssTransfer(
        transfer_no=await next_doc_no(db, "transfer"),
        out_warehouse_id=body.out_warehouse_id,
        in_warehouse_id=body.in_warehouse_id,
        out_org_id=body.out_org_id,
        in_org_id=body.in_org_id,
        apply_user=user.id,
        transfer_date=body.transfer_date or date.today(),
        transfer_type=body.transfer_type,
        out_project_id=body.out_project_id,
        in_project_id=body.in_project_id,
        out_dept_id=body.out_dept_id,
        in_dept_id=body.in_dept_id,
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        db.add(
            AssTransferItem(
                transfer_id=doc.id,
                asset_id=i.asset_id,
                group_id=i.group_id,
                num=1,
                use_location=i.use_location,
                use_user_id=i.use_user_id,
                use_dept_id=i.use_dept_id,
            )
        )
    return TransferDetailOut(**TransferOut.model_validate(doc).model_dump(), items=[])


@router.get("/transfers/{tid}", response_model=TransferDetailOut)
async def get_transfer(tid: int, db: DbDep, user: UserDep):
    doc = await db.get(AssTransfer, tid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "调拨单不存在")
    items = list(
        await db.scalars(select(AssTransferItem).where(AssTransferItem.transfer_id == tid))
    )
    uw_names = {
        u.id: u.real_name
        for u in await db.scalars(
            select(SysUser).where(SysUser.id.in_({i.use_user_id for i in items if i.use_user_id}))
        )
    }
    dept_names = {
        o.id: o.org_name
        for o in await db.scalars(
            select(SysOrg).where(SysOrg.id.in_({i.use_dept_id for i in items if i.use_dept_id}))
        )
    }
    item_outs = [
        TransferItemOut.model_validate(i).model_copy(
            update={"use_user_name": uw_names.get(i.use_user_id), "use_dept_name": dept_names.get(i.use_dept_id)}
        )
        for i in items
    ]
    ow = await db.get(AssWarehouse, doc.out_warehouse_id) if doc.out_warehouse_id else None
    iw = await db.get(AssWarehouse, doc.in_warehouse_id) if doc.in_warehouse_id else None
    os_ = await db.get(AssSpace, doc.out_project_id) if doc.out_project_id else None
    is_ = await db.get(AssSpace, doc.in_project_id) if doc.in_project_id else None
    od = await db.get(SysOrg, doc.out_dept_id) if doc.out_dept_id else None
    id_ = await db.get(SysOrg, doc.in_dept_id) if doc.in_dept_id else None
    au = await db.get(SysUser, doc.apply_user)
    data = TransferOut.model_validate(doc).model_dump()
    data.update(
        {
            "out_warehouse_name": ow.warehouse_name if ow else None,
            "in_warehouse_name": iw.warehouse_name if iw else None,
            "out_space_name": os_.space_name if os_ else None,
            "in_space_name": is_.space_name if is_ else None,
            "out_dept_name": od.org_name if od else None,
            "in_dept_name": id_.org_name if id_ else None,
        }
    )
    return TransferDetailOut(**data, items=list(items), apply_user_name=au.real_name if au else None)


# ============================================================
# 借用单
# ============================================================
@router.get("/borrows", response_model=PageData[BorrowOut])
async def list_borrows(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    status: int | None = None,
    keyword: str | None = None,
):
    conds = [AssBorrow.del_flag == 0]
    sc = _scope_cond(user, AssBorrow.org_id)
    if sc is not None:
        conds.append(or_(sc, AssBorrow.apply_user == user.id))
    if status is not None:
        conds.append(AssBorrow.status == status)
    if keyword:
        conds.append(AssBorrow.borrow_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(AssBorrow).where(*conds))
    rows = list(
        await db.scalars(
            select(AssBorrow).where(*conds).order_by(AssBorrow.id.desc())
            .offset(params.offset).limit(params.limit)
        )
    )
    records = [BorrowOut.model_validate(r) for r in rows]
    org_names = {
        o.id: o.org_name
        for o in await db.scalars(
            select(SysOrg).where(SysOrg.id.in_({r.org_id for r in rows if r.org_id}))
        )
    }
    iids = await _instance_ids(db, "borrow", [r.id for r in rows])
    for rec in records:
        rec.wf_instance_id = iids.get(rec.id)
        rec.org_name = org_names.get(rec.org_id)
    return PageData.build(total, params, records)


@router.post("/borrows", response_model=BorrowDetailOut)
async def create_borrow(body: BorrowIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("borrow:create"))]):
    if not body.borrow_user:
        raise HTTPException(400, "请选择借用人")
    bu = await db.get(SysUser, body.borrow_user)
    if not bu or bu.status != 1 or bu.del_flag == 1:
        raise HTTPException(400, "借用人不存在或已停用")
    if body.borrow_date and body.expected_return_date and body.expected_return_date < body.borrow_date:
        raise HTTPException(400, "预计归还日期不能早于借用日期")

    asset_ids = [i.asset_id for i in body.items]
    assets = dict(
        (a.id, a)
        for a in await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(asset_ids)).with_for_update()
        )
    )
    for aid in asset_ids:
        a = assets.get(aid)
        if not a:
            raise HTTPException(400, f"资产 {aid} 不存在")
        if a.status != 1:
            raise HTTPException(400, f"资产 {a.asset_code} 非在库状态，无法借用")

    doc = AssBorrow(
        borrow_no=await next_doc_no(db, "borrow"),
        org_id=body.org_id,
        apply_user=user.id,
        borrow_user=body.borrow_user,
        borrow_date=body.borrow_date or date.today(),
        expected_return_date=body.expected_return_date,
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        a = assets[i.asset_id]
        db.add(
            AssBorrowItem(
                borrow_id=doc.id,
                asset_id=i.asset_id,
                src_warehouse_id=a.warehouse_id,
                return_status=0,
            )
        )
    return BorrowDetailOut(**BorrowOut.model_validate(doc).model_dump(), items=[])


@router.get("/borrows/{bid}", response_model=BorrowDetailOut)
async def get_borrow(bid: int, db: DbDep, user: UserDep):
    doc = await db.get(AssBorrow, bid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "借用单不存在")
    items = list(
        await db.scalars(select(AssBorrowItem).where(AssBorrowItem.borrow_id == bid))
    )
    wh_names = {
        w.id: w.warehouse_name
        for w in await db.scalars(
            select(AssWarehouse).where(
                AssWarehouse.id.in_({i.src_warehouse_id for i in items if i.src_warehouse_id})
            )
        )
    }
    item_outs = [
        BorrowItemOut.model_validate(i).model_copy(
            update={"src_warehouse_name": wh_names.get(i.src_warehouse_id)}
        )
        for i in items
    ]
    au = await db.get(SysUser, doc.apply_user)
    bu = await db.get(SysUser, doc.borrow_user) if doc.borrow_user else None
    org = await db.get(SysOrg, doc.org_id) if doc.org_id else None
    data = BorrowOut.model_validate(doc).model_dump()
    data["org_name"] = org.org_name if org else None
    return BorrowDetailOut(
        **data,
        items=item_outs,
        apply_user_name=au.real_name if au else None,
        borrow_user_name=bu.real_name if bu else None,
        returned_num=sum(1 for i in items if i.return_status == 1),
    )


def _is_asset_admin(user: CurrentUser) -> bool:
    """管理员或资产管理员（可代他人归还）。"""
    return user.is_admin or any(r.role_code == "project_asset" for r in user.roles)


@router.post("/borrows/{bid}/return")
async def return_borrow(bid: int, body: ReturnIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("borrow:return"))]):
    """归还：已通过借用单上的资产 → 回库（原仓库），资产状态 7→1。"""
    doc = await db.get(AssBorrow, bid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "借用单不存在")
    if doc.status != 2:
        raise HTTPException(400, "仅审批通过的借用单可归还")
    if not _is_asset_admin(user) and doc.borrow_user != user.id:
        raise HTTPException(403, "只能归还自己名下的借用资产（管理员/资产管理员可代还）")
    items = {
        i.asset_id: i
        for i in await db.scalars(select(AssBorrowItem).where(AssBorrowItem.borrow_id == bid))
    }
    for aid in body.asset_ids:
        it = items.get(aid)
        if not it:
            raise HTTPException(400, f"资产 {aid} 不在该借用单上")
        if it.return_status == 1:
            raise HTTPException(400, f"资产 {aid} 已归还，请勿重复操作")
    assets = list(
        await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(body.asset_ids)).with_for_update()
        )
    )
    today = date.today()
    for a in assets:
        if a.status != 7:
            raise HTTPException(400, f"资产 {a.asset_code} 非借用中状态，无法归还")
        it = items[a.id]
        before = snapshot(a)
        a.status = 1
        a.warehouse_id = it.src_warehouse_id
        a.use_user_id = None
        a.version += 1
        it.return_status = 1
        it.return_date = today
        it.return_note = body.note
        await write_log(
            db, a, ACTION_RETURN, "borrow", doc.id, before=before, operator_id=user.id
        )
    return {"ok": True, "returned": len(body.asset_ids)}


# ============================================================
# 归还单（独立单据，走审批闭环）
# ============================================================
@router.get("/returns", response_model=PageData[ReturnOut])
async def list_returns(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    status: int | None = None,
    keyword: str | None = None,
):
    conds = [AssReturn.del_flag == 0]
    sc = _scope_cond(user, AssReturn.org_id)
    if sc is not None:
        conds.append(or_(sc, AssReturn.apply_user == user.id))
    if status is not None:
        conds.append(AssReturn.status == status)
    if keyword:
        conds.append(AssReturn.return_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(AssReturn).where(*conds))
    rows = list(
        await db.scalars(
            select(AssReturn).where(*conds).order_by(AssReturn.id.desc())
            .offset(params.offset).limit(params.limit)
        )
    )
    records = [ReturnOut.model_validate(r) for r in rows]
    org_names = {
        o.id: o.org_name
        for o in await db.scalars(
            select(SysOrg).where(SysOrg.id.in_({r.org_id for r in rows if r.org_id}))
        )
    }
    iids = await _instance_ids(db, "return", [r.id for r in rows])
    for rec in records:
        rec.wf_instance_id = iids.get(rec.id)
        rec.org_name = org_names.get(rec.org_id)
    return PageData.build(total, params, records)


@router.post("/returns", response_model=ReturnDetailOut)
async def create_return(
    body: ReturnDocIn, db: DbDep, user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("return:create"))],
):
    """发起归还：借用中(7)资产 → 走审批，通过后回原仓库。"""
    asset_ids = [i.asset_id for i in body.items]
    assets = dict(
        (a.id, a)
        for a in await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(asset_ids)).with_for_update()
        )
    )
    for aid in asset_ids:
        a = assets.get(aid)
        if not a:
            raise HTTPException(400, f"资产 {aid} 不存在")
        if a.status != 7:
            raise HTTPException(400, f"资产 {a.asset_code} 非借用中状态，无法发起归还")
        if not _is_asset_admin(user) and a.use_user_id != user.id:
            raise HTTPException(403, f"资产 {a.asset_code} 非您名下借用，无法归还（仅管理员/资产管理员可代还）")

    doc = AssReturn(
        return_no=await next_doc_no(db, "return"),
        org_id=body.org_id,
        apply_user=user.id,
        return_date=body.return_date or date.today(),
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for aid in asset_ids:
        # 关联该资产最近一条未归还借用明细（取原借出仓库与借用单）
        bi = (
            await db.scalars(
                select(AssBorrowItem)
                .where(AssBorrowItem.asset_id == aid, AssBorrowItem.return_status == 0)
                .order_by(AssBorrowItem.id.desc())
            )
        ).first()
        db.add(
            AssReturnItem(
                return_id=doc.id,
                asset_id=aid,
                borrow_id=bi.borrow_id if bi else None,
                target_warehouse_id=bi.src_warehouse_id if bi else assets[aid].warehouse_id,
            )
        )
    au = await db.get(SysUser, doc.apply_user)
    return ReturnDetailOut(
        **ReturnOut.model_validate(doc).model_dump(),
        items=[],
        apply_user_name=au.real_name if au else None,
    )


@router.get("/returns/{rid}", response_model=ReturnDetailOut)
async def get_return(rid: int, db: DbDep, user: UserDep):
    doc = await db.get(AssReturn, rid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "归还单不存在")
    items = list(
        await db.scalars(select(AssReturnItem).where(AssReturnItem.return_id == rid))
    )
    wh_names = {
        w.id: w.warehouse_name
        for w in await db.scalars(
            select(AssWarehouse).where(
                AssWarehouse.id.in_({i.target_warehouse_id for i in items if i.target_warehouse_id})
            )
        )
    }
    item_outs = [
        ReturnItemOut.model_validate(i).model_copy(
            update={"target_warehouse_name": wh_names.get(i.target_warehouse_id)}
        )
        for i in items
    ]
    au = await db.get(SysUser, doc.apply_user)
    org = await db.get(SysOrg, doc.org_id) if doc.org_id else None
    data = ReturnOut.model_validate(doc).model_dump()
    data["org_name"] = org.org_name if org else None
    return ReturnDetailOut(
        **data,
        items=item_outs,
        apply_user_name=au.real_name if au else None,
    )


# ============================================================
# 报废处置单
# ============================================================
@router.get("/scraps", response_model=PageData[ScrapOut])
async def list_scraps(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    status: int | None = None,
    keyword: str | None = None,
):
    conds = [AssScrap.del_flag == 0]
    sc = _scope_cond(user, AssScrap.org_id)
    if sc is not None:
        conds.append(sc)
    if status is not None:
        conds.append(AssScrap.status == status)
    if keyword:
        conds.append(AssScrap.scrap_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(AssScrap).where(*conds))
    rows = list(
        await db.scalars(
            select(AssScrap).where(*conds).order_by(AssScrap.id.desc())
            .offset(params.offset).limit(params.limit)
        )
    )
    records = [ScrapOut.model_validate(r) for r in rows]
    iids = await _instance_ids(db, "scrap", [r.id for r in rows])
    for rec in records:
        rec.wf_instance_id = iids.get(rec.id)
    return PageData.build(total, params, records)


@router.post("/scraps", response_model=ScrapDetailOut)
async def create_scrap(body: ScrapIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("scrap:create"))]):
    asset_ids = [i.asset_id for i in body.items]
    assets = dict(
        (a.id, a)
        for a in await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(asset_ids)).with_for_update()
        )
    )
    for aid in asset_ids:
        a = assets.get(aid)
        if not a:
            raise HTTPException(400, f"资产 {aid} 不存在")
        if a.status in (5, 6):
            raise HTTPException(400, f"资产 {a.asset_code} 已报废/处置")

    doc = AssScrap(
        scrap_no=await next_doc_no(db, "scrap"),
        org_id=body.org_id,
        apply_user=user.id,
        scrap_date=body.scrap_date or date.today(),
        scrap_reason=body.scrap_reason,
        dispose_type=body.dispose_type,
        dispose_income=body.dispose_income,
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        a = assets[i.asset_id]
        db.add(
            AssScrapItem(
                scrap_id=doc.id,
                asset_id=i.asset_id,
                net_value=a.net_value,
                evaluate_amount=i.evaluate_amount,
            )
        )
    return ScrapDetailOut(**ScrapOut.model_validate(doc).model_dump(), items=[])


@router.get("/scraps/{sid}", response_model=ScrapDetailOut)
async def get_scrap(sid: int, db: DbDep, user: UserDep):
    doc = await db.get(AssScrap, sid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "报废单不存在")
    items = await db.scalars(select(AssScrapItem).where(AssScrapItem.scrap_id == sid))
    au = await db.get(SysUser, doc.apply_user)
    return ScrapDetailOut(
        **ScrapOut.model_validate(doc).model_dump(),
        items=list(items),
        apply_user_name=au.real_name if au else None,
    )


# ============================================================
# 单据提交 / 撤销（通用）
# ============================================================
_DOC_MODELS = {
    "purchase": AssPurchaseApply,
    "stock_in": AssStockIn,
    "stock_out": AssStockOut,
    "transfer": AssTransfer,
    "borrow": AssBorrow,
    "return": AssReturn,
    "scrap": AssScrap,
    "con_purchase": ConPurchase,
    "con_inbound": ConInbound,
    "con_issue": ConIssue,
}
_DOC_PREFIX_URL = {
    "purchase": "purchases", "stock_in": "stock-ins",
    "stock_out": "stock-outs", "transfer": "transfers", "borrow": "borrows",
    "return": "returns", "scrap": "scraps",
}  # 前端路由映射参考


async def _get_doc(db, biz_type: str, doc_id: int, for_update: bool = False):
    model = _DOC_MODELS.get(biz_type)
    if not model:
        raise HTTPException(400, f"未知单据类型: {biz_type}")
    doc = await db.get(model, doc_id)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "单据不存在")
    if for_update:
        await db.execute(select(model).where(model.id == doc_id).with_for_update())
    return doc


# 业务类型 → 权限码（submit/cancel 按 biz_type 动态校验）
_BIZ_PERM = {
    "purchase": "purchase:list", "purchase_high": "purchase:list",
    "stock_in": "stockin:list", "stock_out": "stockout:list",
    "transfer": "transfer:list", "borrow": "borrow:list", "scrap": "scrap:list",
    "con_purchase": "con_purchase:list", "con_inbound": "con_inbound:list",
    "con_issue": "con_issue:list",
}


def _check_biz_perm(biz_type: str, user: "CurrentUser") -> None:
    code = _BIZ_PERM.get(biz_type)
    if code and not user.has_perm(code):
        raise HTTPException(403, f"无操作权限: {code}")


async def _instance_ids(db, biz_type: str, doc_ids: list[int]) -> dict[int, int]:
    """单据ID -> 最新审批实例ID（列表页「进度」入口）。"""
    if not doc_ids:
        return {}
    rows = (
        await db.execute(
            select(WfInstance.biz_id, func.max(WfInstance.id))
            .where(WfInstance.biz_type == biz_type, WfInstance.biz_id.in_(doc_ids))
            .group_by(WfInstance.biz_id)
        )
    ).all()
    return {b: i for b, i in rows}


@router.get("/docs/{biz_type}/next-no")
async def next_doc_number(biz_type: str, db: DbDep, user: UserDep):
    """预览下一单据编号（只读，不消耗流水），供新建单据页展示。"""
    if biz_type not in _DOC_MODELS:
        raise HTTPException(400, f"未知单据类型: {biz_type}")
    return {"next_no": await peek_doc_no(db, biz_type)}


@router.post("/docs/{biz_type}/{doc_id}/submit")
async def submit_doc(biz_type: str, doc_id: int, db: DbDep, user: UserDep):
    _check_biz_perm(biz_type, user)
    # 行锁防并发双提交
    doc = await _get_doc(db, biz_type, doc_id, for_update=True)
    if doc.status != 0:
        raise HTTPException(400, "仅草稿状态可提交审批")
    creator = getattr(doc, "apply_user", None)
    if creator is None:
        creator = doc.create_by
    if not user.is_admin and creator != user.id:
        raise HTTPException(403, "仅单据创建人可提交审批")
    amount = float(doc.total_amount) if hasattr(doc, "total_amount") and doc.total_amount else None

    # 调拨提交即锁定资产为「调拨中」（在途可视化，方案 6.4）
    # 仓库调拨资产必在库(1)→锁定(4)；项目空间/部门调拨允许领用中(2)资产，不锁定
    if biz_type == "transfer":
        items = await db.scalars(
            select(AssTransferItem).where(AssTransferItem.transfer_id == doc_id)
        )
        ids = [i.asset_id for i in items]
        if ids:
            assets = list(
                await db.scalars(
                    select(AssAsset).where(AssAsset.id.in_(ids)).with_for_update()
                )
            )
            for a in assets:
                if a.status == 1:
                    a.status = 4
                    a.version += 1
                    await write_log(db, a, ACTION_TRANSFER, "transfer", doc_id, operator_id=user.id)
                elif a.status == 2 and doc.transfer_type in (2, 4):
                    continue
                else:
                    raise HTTPException(400, f"资产 {a.asset_code} 状态已变化，无法调拨")

    # 借用提交即锁定资产为「借用中」（在途可视化）
    elif biz_type == "borrow":
        items = await db.scalars(
            select(AssBorrowItem).where(AssBorrowItem.borrow_id == doc_id)
        )
        ids = [i.asset_id for i in items]
        if ids:
            assets = list(
                await db.scalars(
                    select(AssAsset).where(AssAsset.id.in_(ids)).with_for_update()
                )
            )
            for a in assets:
                if a.status == 1:
                    a.status = 7
                    a.version += 1
                    await write_log(db, a, ACTION_BORROW, "borrow", doc_id, operator_id=user.id)
                else:
                    raise HTTPException(400, f"资产 {a.asset_code} 状态已变化，无法借用")

    # 单据类型可关闭审批流（流程配置页开关）：关闭时不生成流程实例，走单据页「手动审批通过」
    flow_on = await wf.is_flow_enabled(db, biz_type)
    instance = None
    if flow_on:
        instance = await wf.start_instance(db, biz_type, doc.id, doc, user.id)
        if instance is None:
            raise HTTPException(500, "未配置审批流，请联系管理员")
        doc.wf_instance_id = instance.id
    doc.status = 1
    doc.update_by = user.id

    if instance:
        # 消息通知：新待办推送审批人（方案模块7）
        no = await _doc_no(db, biz_type, doc_id)
        au = await _apply_user_id(db, biz_type, doc_id)
        au_name = (await db.scalar(select(SysUser.real_name).where(SysUser.id == au))) if au else ""
        for t in (
            await db.scalars(
                select(WfTask).where(WfTask.instance_id == instance.id, WfTask.assignee_id.isnot(None))
            )
        ).all():
            if t.assignee_id and t.assignee_id != user.id:
                await _notify(
                    db, t.assignee_id, biz_type, doc_id,
                    f"【审批待办】{_BIZ_NAME.get(biz_type, '单据')} {no}",
                    f"{au_name or '用户'} 提交的单据待您审批",
                )
    return {
        "ok": True,
        "wf_instance_id": instance.id if instance else None,
        "manual": not flow_on,
    }


@router.post("/docs/{biz_type}/{doc_id}/manual-approve")
async def manual_approve(
    biz_type: str,
    doc_id: int,
    body: ManualApproveIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("approval:approve"))],
):
    """手动审批通过（单据类型在流程配置页关闭审批流时使用）：单据→已通过并生效，不经过流程实例。"""
    _check_biz_perm(biz_type, user)
    if await wf.is_flow_enabled(db, biz_type):
        raise HTTPException(400, "该单据类型已启用审批流，请在「我的审批」中审批")
    doc = await _get_doc(db, biz_type, doc_id, for_update=True)
    if doc.status != 1:
        raise HTTPException(400, "仅审批中的单据可手动审批通过")
    doc.status = 2
    doc.update_by = user.id
    effect = _EFFECTS.get(biz_type)
    if effect:
        await effect(db, doc, user)
    no = await _doc_no(db, biz_type, doc_id)
    au = await _apply_user_id(db, biz_type, doc_id)
    await _notify(
        db, au, biz_type, doc_id,
        f"【审批结果】{_BIZ_NAME.get(biz_type, '单据')} {no} 已通过",
        f"由 {user.real_name or '—'} 手动审批通过，单据已生效",
    )
    return {"ok": True}


async def _rollback_transfer(db, doc):
    """调拨未生效（驳回/撤销/终止）→ 资产恢复在库。"""
    items = await db.scalars(
        select(AssTransferItem).where(AssTransferItem.transfer_id == doc.id)
    )
    ids = [i.asset_id for i in items]
    if ids:
        for a in await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(ids), AssAsset.status == 4)
        ):
            a.status = 1
            a.version += 1


async def _rollback_borrow(db, doc):
    """借用未生效（驳回/撤销/终止）→ 资产恢复在库。"""
    items = await db.scalars(
        select(AssBorrowItem).where(AssBorrowItem.borrow_id == doc.id)
    )
    ids = [i.asset_id for i in items]
    if ids:
        for a in await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(ids), AssAsset.status == 7)
        ):
            a.status = 1
            a.version += 1


async def _rollback_lock(db, biz_type: str, doc):
    """按单据类型回滚提交时锁定的资产（调拨中4 / 借用中7 → 在库）。"""
    if biz_type == "transfer":
        await _rollback_transfer(db, doc)
    elif biz_type == "borrow":
        await _rollback_borrow(db, doc)


def _is_initiator(inst: WfInstance, doc, user) -> bool:
    """发起人判定：优先实例发起人；旧数据回退单据创建人。"""
    if inst.initiator_id is not None:
        return inst.initiator_id == user.id
    return getattr(doc, "create_by", None) == user.id


@router.post("/docs/{biz_type}/{doc_id}/cancel")
async def cancel_doc(biz_type: str, doc_id: int, db: DbDep, user: UserDep):
    """撤销：草稿限创建人；审批中限发起人（管理员均可）。单据→已取消。"""
    _check_biz_perm(biz_type, user)
    doc = await _get_doc(db, biz_type, doc_id)
    if doc.status not in (0, 1):
        raise HTTPException(400, "当前状态不可撤销")
    if doc.status == 1:
        inst = await db.get(WfInstance, doc.wf_instance_id) if doc.wf_instance_id else None
        if inst and inst.status == 1:
            if not _is_initiator(inst, doc, user) and not user.is_admin:
                raise HTTPException(403, "仅发起人或管理员可撤销")
            inst.status = 4
            inst.finish_time = datetime.now()
            inst.finish_by = user.id
            inst.finish_note = f"{user.real_name or ''} 撤销申请"
        doc.status = 4
        await _rollback_lock(db, biz_type, doc)
    else:
        if doc.create_by != user.id and not user.is_admin:
            raise HTTPException(403, "仅创建人或管理员可撤销")
        doc.status = 4
    doc.update_by = user.id
    return {"ok": True}


# ============================================================
# 审批待办 / 审批操作
# ============================================================
_BIZ_DOC_NO = {
    "purchase": (AssPurchaseApply, AssPurchaseApply.apply_no, AssPurchaseApply.apply_user),
    "stock_in": (AssStockIn, AssStockIn.in_no, AssStockIn.create_by),
    "stock_out": (AssStockOut, AssStockOut.out_no, AssStockOut.create_by),
    "transfer": (AssTransfer, AssTransfer.transfer_no, AssTransfer.apply_user),
    "borrow": (AssBorrow, AssBorrow.borrow_no, AssBorrow.apply_user),
    "scrap": (AssScrap, AssScrap.scrap_no, AssScrap.apply_user),
    "con_purchase": (ConPurchase, ConPurchase.purchase_no, ConPurchase.apply_user),
    "con_inbound": (ConInbound, ConInbound.in_no, ConInbound.org_id),
    "con_issue": (ConIssue, ConIssue.issue_no, ConIssue.receive_user),
}
_BIZ_NAME = {
    "purchase": "采购申请单", "stock_in": "入库单", "stock_out": "领用出库单",
    "transfer": "调拨单", "borrow": "借用单", "return": "归还单", "scrap": "报废处置单",
    "con_purchase": "易耗品采购单", "con_inbound": "易耗品入库单", "con_issue": "易耗品领用单",
}


async def _doc_no(db, biz_type: str, doc_id: int) -> str:
    meta = _BIZ_DOC_NO.get(biz_type)
    if not meta:
        return str(doc_id)
    model, no_col, _ = meta
    return (await db.scalar(select(no_col).where(model.id == doc_id))) or str(doc_id)


async def _apply_user_id(db, biz_type: str, doc_id: int) -> int | None:
    meta = _BIZ_DOC_NO.get(biz_type)
    if not meta:
        return None
    model, _, user_col = meta
    return await db.scalar(select(user_col).where(model.id == doc_id))


async def _notify(db, receiver_id, biz_type: str, doc_id: int, title: str, content: str):
    """站内信通知（方案模块7），失败不影响主流程。"""
    try:
        await msg.send(db, receiver_id, title, content, 1, biz_type, doc_id)
    except Exception:
        logging.getLogger(__name__).warning(
            "站内信通知失败 receiver=%s biz=%s/%s", receiver_id, biz_type, doc_id, exc_info=True
        )


async def _biz_meta_map(db, insts: list) -> dict:
    """批量回填 (biz_type, biz_id) → (单据编号, 申请人姓名)，每类单据仅一条查询。"""
    by_type: dict[str, set[int]] = {}
    for inst in insts:
        if inst.biz_type in _BIZ_DOC_NO:
            by_type.setdefault(inst.biz_type, set()).add(inst.biz_id)
    result: dict = {}
    for biz_type, biz_ids in by_type.items():
        model, no_col, user_col = _BIZ_DOC_NO[biz_type]
        rows = (
            await db.execute(
                select(model.id, no_col, user_col, SysUser.real_name)
                .join(SysUser, SysUser.id == user_col, isouter=True)
                .where(model.id.in_(list(biz_ids)))
            )
        ).all()
        for bid, no, _uid, name in rows:
            result[(biz_type, bid)] = (no or "", name)
    return result


@router.get("/approvals/todos", response_model=list[ApprovalTodoOut])
async def my_todos(db: DbDep, user: UserDep):
    """我的待办（方案 wf_task: assignee_id+status 索引）。"""
    rows = (
        await db.execute(
            select(WfTask, WfInstance)
            .join(WfInstance, WfInstance.id == WfTask.instance_id)
            .where(
                WfTask.assignee_id == user.id,
                WfTask.action.is_(None),
                WfInstance.status == 1,
            )
            .order_by(WfTask.arrive_time)
        )
    ).all()
    meta_map = await _biz_meta_map(db, [inst for _, inst in rows])
    out = []
    for task, inst in rows:
        biz_no, apply_user_name = meta_map.get((inst.biz_type, inst.biz_id), ("", None))
        out.append(
            ApprovalTodoOut(
                task=ApprovalTaskOut.model_validate(task),
                biz_type=inst.biz_type,
                biz_no=biz_no,
                biz_id=inst.biz_id,
                apply_user_name=apply_user_name,
            )
        )
    return out


@router.get("/approvals/dones", response_model=list[ApprovalTodoOut])
async def my_dones(db: DbDep, user: UserDep):
    """我的已办（action 已落库；按处理时间倒序）。"""
    rows = (
        await db.execute(
            select(WfTask, WfInstance)
            .join(WfInstance, WfInstance.id == WfTask.instance_id)
            .where(WfTask.assignee_id == user.id, WfTask.action.isnot(None))
            .order_by(WfTask.done_time.desc(), WfTask.arrive_time.desc())
        )
    ).all()
    meta_map = await _biz_meta_map(db, [inst for _, inst in rows])
    out = []
    for task, inst in rows:
        biz_no, apply_user_name = meta_map.get((inst.biz_type, inst.biz_id), ("", None))
        out.append(
            ApprovalTodoOut(
                task=ApprovalTaskOut.model_validate(task),
                biz_type=inst.biz_type,
                biz_no=biz_no,
                biz_id=inst.biz_id,
                apply_user_name=apply_user_name,
            )
        )
    return out


async def _instance_rows_out(db, insts: list[WfInstance]) -> list[dict]:
    """实例列表行：补单据编号/申请人/发起人/结束人名称。"""
    uids = {u for r in insts for u in (r.initiator_id, r.finish_by) if u}
    user_names = (
        {u.id: u.real_name for u in await db.scalars(select(SysUser).where(SysUser.id.in_(list(uids))))}
        if uids
        else {}
    )
    meta_map = await _biz_meta_map(db, insts)
    records = []
    for r in insts:
        biz_no, apply_user_name = meta_map.get((r.biz_type, r.biz_id), ("", None))
        records.append(
            {
                "id": r.id,
                "status": r.status,
                "status_label": INSTANCE_STATUS.get(r.status, str(r.status)),
                "flow_name": r.flow_name,
                "biz_type": r.biz_type,
                "biz_label": _BIZ_NAME.get(r.biz_type, "单据"),
                "biz_id": r.biz_id,
                "biz_no": biz_no,
                "apply_user_name": apply_user_name,
                "initiator_id": r.initiator_id,
                "initiator_name": user_names.get(r.initiator_id),
                "current_node": r.current_node,
                "start_time": r.create_time,
                "finish_time": r.finish_time,
                "finish_by_name": user_names.get(r.finish_by) if r.finish_by else None,
                "finish_note": r.finish_note,
            }
        )
    return records


@router.get("/approvals/mine")
async def my_inits(db: DbDep, user: UserDep, params: PageParams = Depends(), status: int | None = None):
    """我发起的流程实例（分页；status 可选过滤）。"""
    conds = [WfInstance.del_flag == 0, WfInstance.initiator_id == user.id]
    if status is not None:
        conds.append(WfInstance.status == status)
    total = await db.scalar(select(func.count()).select_from(WfInstance).where(*conds)) or 0
    if not total:
        return PageData.build(0, params, [])
    insts = list(
        await db.scalars(
            select(WfInstance).where(*conds).order_by(WfInstance.id.desc()).offset(params.offset).limit(params.limit)
        )
    )
    records = await _instance_rows_out(db, insts)
    return PageData.build(total, params, records)


async def _apply_stock_in_effect(db, doc, user):
    """入库生效（方案 6.2）：逐件生成资产卡片 + 唯一编码 + 二维码 + 首条履历。"""
    import uuid as _uuid

    items = list(
        await db.scalars(select(AssStockInItem).where(AssStockInItem.in_id == doc.id))
    )
    wh = await db.get(AssWarehouse, doc.warehouse_id) if doc.warehouse_id else None
    if wh is None:
        raise HTTPException(400, "入库单关联的仓库不存在，无法生效")
    org = await db.get(SysOrg, doc.org_id or wh.org_id)
    if org is None:
        raise HTTPException(400, "入库单缺少核算公司，无法生效")
    for it in items:
        cat = await db.get(AssCategory, it.category_id) if it.category_id else None
        if cat is None or cat.del_flag == 1:
            raise HTTPException(400, f"明细「{it.asset_name}」的资产分类不存在，无法生效")
        for _ in range(it.num):
            code = await next_asset_code(db, org.org_code, cat.code)
            a = AssAsset(
                asset_code=code,
                asset_name=it.asset_name,
                category_id=it.category_id,
                org_id=org.id,
                project_id=wh.project_id,
                warehouse_id=doc.warehouse_id,
                status=1,
                price=it.unit_price,
                net_value=it.unit_price,
                buy_date=doc.in_date,
                supplier_id=doc.supplier_id,
                qrcode=_uuid.uuid4().hex,
                create_by=user.id,
            )
            db.add(a)
            await db.flush()
            await write_log(db, a, ACTION_STOCK_IN, "stock_in", doc.id, operator_id=user.id)
    doc.total_num = sum(i.num for i in items)


async def _apply_stock_out_effect(db, doc, user):
    """领用出库生效：资产 → 领用中，绑定领用人。"""
    items = list(
        await db.scalars(select(AssStockOutItem).where(AssStockOutItem.out_id == doc.id))
    )
    ids = [i.asset_id for i in items]
    assets = list(
        await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(ids)).with_for_update()
        )
    )
    receiver = await db.get(SysUser, doc.receive_user) if doc.receive_user else None
    for a in assets:
        if a.status != 1:
            raise HTTPException(409, f"资产 {a.asset_code} 状态已变化，出库失败")
        before = snapshot(a)
        a.status = 2
        a.warehouse_id = None
        a.use_user_id = doc.receive_user
        if receiver:
            a.use_dept_id = receiver.org_id
            a.org_id = a.org_id  # 财务核算维度不变（方案双维度归属）
        a.version += 1
        await write_log(
            db, a, ACTION_RECEIVE, "stock_out", doc.id, before=before, operator_id=user.id
        )


async def _apply_transfer_effect(db, doc, user):
    """调拨生效：根据调拨类型处理资产迁移。

    调拨类型：
    1 - 仓库调拨：资产在调出仓库（在库）→ 迁入调入仓库
    2 - 项目空间调拨：资产在调出空间（房间级）→ 迁入调入空间，同步业务项目
    4 - 部门调拨：资产使用部门为调出部门 → 改为调入部门
    提交时锁定的资产（4调拨中）生效回「在库」；领用中(2)资产保持原状态。
    """
    items = list(
        await db.scalars(select(AssTransferItem).where(AssTransferItem.transfer_id == doc.id))
    )
    ids = [i.asset_id for i in items]
    assets = list(
        await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(ids)).with_for_update()
        )
    )

    item_map = {i.asset_id: i for i in items}
    in_space = (
        await db.get(AssSpace, doc.in_project_id) if doc.transfer_type == 2 and doc.in_project_id else None
    )

    for a in assets:
        if a.status not in (1, 2, 4):
            raise HTTPException(409, f"资产 {a.asset_code} 状态已变化，调拨失败")
        before = snapshot(a)
        if a.status == 4:
            a.status = 1  # 解除调拨中锁定，回到在库
        # 领用中(2)资产保持领用中（位置变更不改变使用状态）

        if doc.transfer_type == 1:
            a.warehouse_id = doc.in_warehouse_id
        elif doc.transfer_type == 2:
            if not in_space:
                raise HTTPException(409, "调入项目空间不存在")
            a.space_id = doc.in_project_id
            a.project_id = in_space.project_id
            a.warehouse_id = doc.in_warehouse_id if doc.in_warehouse_id else None
        elif doc.transfer_type == 4:
            a.use_dept_id = doc.in_dept_id

        # 更新调入后的使用信息
        transfer_item = item_map.get(a.id)
        if transfer_item:
            if transfer_item.use_location:
                a.location_detail = transfer_item.use_location
            if transfer_item.use_user_id:
                a.use_user_id = transfer_item.use_user_id
            if transfer_item.use_dept_id and doc.transfer_type != 4:
                a.use_dept_id = transfer_item.use_dept_id

        a.version += 1
        await write_log(
            db, a, ACTION_TRANSFER, "transfer", doc.id, before=before, operator_id=user.id
        )


async def _apply_borrow_effect(db, doc, user):
    """借用生效：资产 → 借用中，绑定借用人，离库。"""
    items = list(
        await db.scalars(select(AssBorrowItem).where(AssBorrowItem.borrow_id == doc.id))
    )
    ids = [i.asset_id for i in items]
    assets = list(
        await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(ids)).with_for_update()
        )
    )
    borrow_user = await db.get(SysUser, doc.borrow_user) if doc.borrow_user else None
    for a in assets:
        if a.status not in (1, 7):
            raise HTTPException(409, f"资产 {a.asset_code} 状态已变化，借用失败")
        before = snapshot(a)
        a.status = 7
        a.warehouse_id = None
        if doc.borrow_user:
            a.use_user_id = doc.borrow_user
        if borrow_user and borrow_user.org_id:
            a.use_dept_id = borrow_user.org_id
        a.version += 1
        await write_log(
            db, a, ACTION_BORROW, "borrow", doc.id, before=before, operator_id=user.id
        )


async def _apply_return_effect(db, doc, user):
    """归还生效：借用中资产 → 回原仓库，状态 7→1，解除借用人，标记借用明细已归还。"""
    items = list(
        await db.scalars(select(AssReturnItem).where(AssReturnItem.return_id == doc.id))
    )
    ids = [i.asset_id for i in items]
    if not ids:
        return
    assets = list(
        await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(ids)).with_for_update()
        )
    )
    item_by_asset = {i.asset_id: i for i in items}
    today = date.today()
    for a in assets:
        if a.status != 7:
            raise HTTPException(409, f"资产 {a.asset_code} 非借用中状态，归还失败")
        before = snapshot(a)
        it = item_by_asset.get(a.id)
        a.status = 1
        a.warehouse_id = it.target_warehouse_id if it else None
        a.use_user_id = None
        a.version += 1
        if it and it.borrow_id:
            bi = (
                await db.scalars(
                    select(AssBorrowItem).where(
                        AssBorrowItem.borrow_id == it.borrow_id,
                        AssBorrowItem.asset_id == a.id,
                    )
                )
            ).first()
            if bi and bi.return_status != 1:
                bi.return_status = 1
                bi.return_date = today
        await write_log(
            db, a, ACTION_RETURN, "return", doc.id, before=before, operator_id=user.id
        )


async def _apply_scrap_effect(db, doc, user):
    """报废处置生效（方案 6.6）：销账 + 损益计算。"""
    items = list(
        await db.scalars(select(AssScrapItem).where(AssScrapItem.scrap_id == doc.id))
    )
    ids = [i.asset_id for i in items]
    assets = list(
        await db.scalars(
            select(AssAsset).where(AssAsset.id.in_(ids)).with_for_update()
        )
    )
    new_status = 6 if doc.dispose_type in (2, 3) else 5
    total_net = Decimal("0")
    for a in assets:
        if a.status in (5, 6):
            raise HTTPException(409, f"资产 {a.asset_code} 已报废/处置")
        before = snapshot(a)
        a.status = new_status
        a.warehouse_id = None
        a.version += 1
        total_net += a.net_value or 0
        await write_log(
            db, a, ACTION_SCRAP, "scrap", doc.id, before=before, operator_id=user.id
        )
    if doc.dispose_type == 2 and doc.dispose_income is not None:
        doc.profit_loss = (doc.dispose_income - total_net).quantize(Decimal("0.01"))


async def _apply_con_inbound_effect(db, doc, user):
    """易耗品入库生效：库存 + 数量；若关联采购单，回写已入库数。"""
    items = list(
        await db.scalars(select(ConInboundItem).where(ConInboundItem.in_id == doc.id))
    )
    for it in items:
        stock = (
            await db.scalars(
                select(ConStock)
                .where(
                    ConStock.item_id == it.item_id,
                    ConStock.warehouse_id == doc.warehouse_id,
                )
                .with_for_update()
            )
        ).first()
        if not stock:
            stock = ConStock(
                item_id=it.item_id, warehouse_id=doc.warehouse_id, qty=0, create_by=user.id
            )
            db.add(stock)
            await db.flush()
        stock.qty = (stock.qty or 0) + it.num
        if it.unit_price is not None:
            stock.unit_price = it.unit_price
        if doc.purchase_id:
            pi = (
                await db.scalars(
                    select(ConPurchaseItem)
                    .where(
                        ConPurchaseItem.purchase_id == doc.purchase_id,
                        ConPurchaseItem.item_id == it.item_id,
                    )
                    .with_for_update()
                )
            ).first()
            if pi:
                pi.inbound_num = (pi.inbound_num or 0) + it.num


async def _apply_con_issue_effect(db, doc, user):
    """易耗品领用生效：采购直发扣采购已直发数；库存领用扣库存。"""
    items = list(
        await db.scalars(select(ConIssueItem).where(ConIssueItem.issue_id == doc.id))
    )
    for it in items:
        if doc.source_type == 1:
            if not doc.purchase_id:
                continue
            pi = (
                await db.scalars(
                    select(ConPurchaseItem)
                    .where(
                        ConPurchaseItem.purchase_id == doc.purchase_id,
                        ConPurchaseItem.item_id == it.item_id,
                    )
                    .with_for_update()
                )
            ).first()
            if pi:
                pi.issued_num = (pi.issued_num or 0) + it.num
        else:
            stock = (
                await db.scalars(
                    select(ConStock)
                    .where(
                        ConStock.item_id == it.item_id,
                        ConStock.warehouse_id == doc.warehouse_id,
                    )
                    .with_for_update()
                )
            ).first()
            if not stock:
                raise HTTPException(409, f"物料 {it.item_id} 无库存，领用失败")
            if (stock.qty or 0) < it.num:
                raise HTTPException(
                    409, f"物料 {it.item_id} 库存不足（现有 {stock.qty}，领用 {it.num}）"
                )
            stock.qty = stock.qty - it.num


_EFFECTS = {
    "stock_in": _apply_stock_in_effect,
    "stock_out": _apply_stock_out_effect,
    "transfer": _apply_transfer_effect,
    "borrow": _apply_borrow_effect,
    "return": _apply_return_effect,
    "scrap": _apply_scrap_effect,
    "con_inbound": _apply_con_inbound_effect,
    "con_issue": _apply_con_issue_effect,
}


async def _reject_instance(db, instance: WfInstance, doc, user, comment: str | None):
    """驳回：实例→3，单据→已驳回，调拨资产回滚，通知申请人。"""
    now = datetime.now()
    instance.status = 3
    instance.finish_time = now
    instance.finish_by = user.id
    instance.finish_note = f"驳回：{comment or '无意见'}"
    doc.status = 3
    doc.update_by = user.id
    await _rollback_lock(db, instance.biz_type, doc)
    no = await _doc_no(db, instance.biz_type, doc.id)
    au = await _apply_user_id(db, instance.biz_type, doc.id)
    await _notify(
        db, au, instance.biz_type, doc.id,
        f"【审批结果】{_BIZ_NAME.get(instance.biz_type, '单据')} {no} 已被驳回",
        f"审批人 {user.real_name or '—'} 的驳回意见：{comment or '无'}",
    )


async def _cancel_instance(db, instance: WfInstance, doc, user, note: str):
    """撤销/终止：实例→4或5，单据→已取消，调拨资产回滚，通知发起人。"""
    now = datetime.now()
    instance.finish_time = now
    instance.finish_by = user.id
    instance.finish_note = note
    doc.status = 4
    doc.update_by = user.id
    await _rollback_lock(db, instance.biz_type, doc)
    no = await _doc_no(db, instance.biz_type, doc.id)
    au = await _apply_user_id(db, instance.biz_type, doc.id)
    verb = "终止" if instance.status == 5 else "撤销"
    await _notify(
        db, au, instance.biz_type, doc.id,
        f"【审批结果】{_BIZ_NAME.get(instance.biz_type, '单据')} {no} 已{verb}",
        note or f"操作人：{user.real_name or '—'}",
    )


async def _complete_instance(db, instance: WfInstance, doc, user):
    """全部节点通过：实例→2，单据生效，通知申请人。"""
    instance.status = 2
    instance.finish_time = datetime.now()
    instance.finish_by = user.id
    doc.status = 2
    doc.update_by = user.id
    effect = _EFFECTS.get(instance.biz_type)
    if effect:
        await effect(db, doc, user)
    no = await _doc_no(db, instance.biz_type, doc.id)
    au = await _apply_user_id(db, instance.biz_type, doc.id)
    await _notify(
        db, au, instance.biz_type, doc.id,
        f"【审批结果】{_BIZ_NAME.get(instance.biz_type, '单据')} {no} 已通过",
        "全部节点审批完成，单据已生效",
    )


@router.post("/approvals/{task_id}")
async def approve(task_id: int, body: ApproveIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("approval:approve"))]):
    """审批操作：1通过 / 2驳回 / 4加签。行锁 + 状态前置校验，并发安全。"""
    task = (
        await db.execute(select(WfTask).where(WfTask.id == task_id).with_for_update())
    ).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "审批任务不存在")
    if task.action is not None:
        raise HTTPException(409, "该任务已处理")
    is_owner = task.assignee_id == user.id
    if not is_owner and not user.is_admin:
        raise HTTPException(403, "非该节点审批人")

    instance = (
        await db.execute(
            select(WfInstance).where(WfInstance.id == task.instance_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not instance or instance.status != 1:
        raise HTTPException(400, "流程已结束")

    doc = await _get_doc(db, instance.biz_type, instance.biz_id)
    if doc.status != 1:
        raise HTTPException(400, "单据状态异常")

    nodes = await wf.get_instance_nodes(db, instance, doc)
    node = next((n for n in nodes if n["name"] == task.node_name), None)
    if node and task.node_key and node.get("id") != task.node_key:
        node = next((n for n in nodes if n.get("id") == task.node_key), None)

    if body.action == 4:  # 加签：当前节点追加一名必审人（后加签）
        if not body.sign_to:
            raise HTTPException(400, "请选择加签审批人")
        if body.sign_to == user.id:
            raise HTTPException(400, "不能加签给自己")
        target = await db.get(SysUser, body.sign_to)
        if not target or target.status != 1 or target.del_flag == 1:
            raise HTTPException(400, "加签审批人不存在或已停用")
        if node:
            for p in await wf.pending_tasks(db, instance, node):
                if p.assignee_id == body.sign_to:
                    raise HTTPException(400, "该用户在本节点已有待办任务")
        db.add(
            WfTask(
                instance_id=instance.id,
                node_key=task.node_key,
                node_name=task.node_name,
                node_order=task.node_order,
                assignee_id=body.sign_to,
                sign_from=task.id,
                comment=f"{user.real_name or ''} 加签",
                arrive_time=datetime.now(),
            )
        )
        no = await _doc_no(db, instance.biz_type, doc.id)
        await _notify(
            db, body.sign_to, instance.biz_type, doc.id,
            f"【审批待办】{_BIZ_NAME.get(instance.biz_type, '单据')} {no}",
            f"{user.real_name or '—'} 在节点「{task.node_name}」加签给您",
        )
        return {"ok": True, "result": "countersigned"}

    if body.action == 5:  # 退回：回退到任意前置节点重新审批
        if not node:
            raise HTTPException(400, "无法定位当前节点")
        idx = nodes.index(node)
        if body.target_node is None or not (0 <= body.target_node < idx):
            raise HTTPException(400, "请选择要退回的前置节点")
        for p in await wf.pending_tasks(db, instance, node):
            if p.id != task.id:
                p.action = 1
                p.comment = f"流程退回自动完成（{user.real_name or '—'} 退回）"
                p.done_time = datetime.now()
        task.action = 5
        task.comment = body.comment
        task.done_time = datetime.now()
        tgt = nodes[body.target_node]
        new_tasks = await wf.activate_node(db, instance, nodes, body.target_node)
        no = await _doc_no(db, instance.biz_type, doc.id)
        for t in new_tasks:
            if t.assignee_id and t.assignee_id != user.id:
                await _notify(
                    db, t.assignee_id, instance.biz_type, doc.id,
                    f"【审批待办】{_BIZ_NAME.get(instance.biz_type, '单据')} {no}",
                    f"{user.real_name or '—'} 将流程退回到节点「{tgt['name']}」，待您审批",
                )
        return {"ok": True, "result": "sent_back"}

    task.action = body.action
    task.comment = body.comment
    task.done_time = datetime.now()
    task.assignee_id = user.id if not is_owner else task.assignee_id

    if body.action == 2:  # 驳回
        await _reject_instance(db, instance, doc, user, body.comment)
        return {"ok": True, "result": "rejected"}

    # 通过：或签→其余任务自动完成；会签/单签→全部通过后流转
    if node and node.get("mode") == "any":
        for p in (await wf.pending_tasks(db, instance, node)):
            if p.id != task.id:
                p.action = 1
                p.comment = f"或签自动完成（{user.real_name or '—'} 先通过）"
                p.done_time = datetime.now()
    if node and (await wf.pending_tasks(db, instance, node)):
        return {"ok": True, "result": "waiting"}  # 会签中，等待其余审批人
    if node:
        idx = nodes.index(node)
        if idx + 1 < len(nodes):
            nxt = nodes[idx + 1]
            new_tasks = await wf.activate_node(db, instance, nodes, idx + 1)
            no = await _doc_no(db, instance.biz_type, doc.id)
            for t in new_tasks:
                if t.assignee_id:
                    await _notify(
                        db, t.assignee_id, instance.biz_type, doc.id,
                        f"【审批待办】{_BIZ_NAME.get(instance.biz_type, '单据')} {no}",
                        f"节点「{nxt['name']}」待您审批",
                    )
            return {"ok": True, "result": "next_node"}
    # 流程完成 → 单据生效
    await _complete_instance(db, instance, doc, user)
    return {"ok": True, "result": "approved"}


@router.post("/approvals/{task_id}/delegate")
async def delegate(task_id: int, body: DelegateIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("approval:delegate"))]):
    """委托转办：把待办任务改派给其他审批人（Flowable delegation）。"""
    task = (
        await db.execute(select(WfTask).where(WfTask.id == task_id).with_for_update())
    ).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "审批任务不存在")
    if task.action is not None:
        raise HTTPException(409, "该任务已处理")
    if task.assignee_id != user.id and not user.is_admin:
        raise HTTPException(403, "非该任务审批人")
    if body.to_user == user.id or body.to_user == task.assignee_id:
        raise HTTPException(400, "不能委托给自己或当前审批人")
    target = await db.get(SysUser, body.to_user)
    if not target or target.status != 1 or target.del_flag == 1:
        raise HTTPException(400, "委托对象不存在或已停用")
    instance = (
        await db.execute(
            select(WfInstance).where(WfInstance.id == task.instance_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not instance or instance.status != 1:
        raise HTTPException(400, "流程已结束")
    doc = await _get_doc(db, instance.biz_type, instance.biz_id)
    task.assignee_id = body.to_user
    task.arrive_time = datetime.now()
    task.update_by = user.id
    no = await _doc_no(db, instance.biz_type, doc.id)
    await _notify(
        db, body.to_user, instance.biz_type, doc.id,
        f"【审批待办】{_BIZ_NAME.get(instance.biz_type, '单据')} {no}",
        f"{user.real_name or '—'} 将节点「{task.node_name}」的任务委托给您",
    )
    return {"ok": True, "task_id": task.id, "assignee_id": body.to_user}


# ============================================================
# 审批进度 / 撤销 / 终止
# ============================================================
INSTANCE_STATUS = {1: "审批中", 2: "已通过", 3: "已驳回", 4: "已撤销", 5: "已终止"}


@router.get("/instances/{instance_id}")
async def instance_progress(instance_id: int, db: DbDep, user: UserDep):
    """审批进度：流程节点 + 各任务（审批人/动作/意见/时间）+ 当前用户可执行操作。"""
    inst = await db.get(WfInstance, instance_id)
    if not inst:
        raise HTTPException(404, "流程实例不存在")
    _check_biz_perm(inst.biz_type, user)

    nodes = await wf.get_instance_nodes(db, inst)
    tasks = list(
        await db.scalars(
            select(WfTask)
            .where(WfTask.instance_id == instance_id)
            .order_by(WfTask.arrive_time, WfTask.id)
        )
    )
    meta = _BIZ_DOC_NO.get(inst.biz_type)
    biz_no, apply_user = "", None
    if meta:
        model, no_col, user_col = meta
        row = (
            await db.execute(
                select(no_col, user_col).where(model.id == inst.biz_id)
            )
        ).first()
        if row:
            biz_no, apply_user = row[0], row[1]
    user_names = {
        u.id: u.real_name
        for u in await db.scalars(
            select(SysUser).where(
                SysUser.id.in_(
                    [t.assignee_id for t in tasks]
                    + [inst.initiator_id, inst.finish_by, apply_user]
                )
            )
        )
    }

    def task_out(t: WfTask) -> dict:
        return {
            **ApprovalTaskOut.model_validate(t).model_dump(mode="json"),
            "assignee_name": user_names.get(t.assignee_id) or "系统",
            "sign_from_user": (
                user_names.get(
                    next((x.assignee_id for x in tasks if x.id == t.sign_from), 0)
                )
                if t.sign_from else None
            ),
        }

    for n in nodes:
        n["tasks"] = [
            task_out(t)
            for t in tasks
            if (t.node_key and t.node_key == n.get("id")) or t.node_name == n["name"]
        ]
    # 未匹配到节点的遗留任务（旧数据）
    matched = {t["id"] for n in nodes for t in n["tasks"]}
    orphan = [t for t in tasks if t.id not in matched]

    my_task = next((t for t in tasks if t.action is None and t.assignee_id == user.id), None)
    doc = await _get_doc(db, inst.biz_type, inst.biz_id)
    users = [
        {"id": u.id, "real_name": u.real_name}
        for u in await db.scalars(
            select(SysUser).where(SysUser.del_flag == 0, SysUser.status == 1).order_by(SysUser.id)
        )
    ]
    return {
        "instance": {
            "id": inst.id,
            "status": inst.status,
            "status_label": INSTANCE_STATUS.get(inst.status, str(inst.status)),
            "flow_name": inst.flow_name,
            "current_node": inst.current_node,
            "start_time": inst.create_time,
            "finish_time": inst.finish_time,
            "finish_by_name": user_names.get(inst.finish_by) if inst.finish_by else None,
            "finish_note": inst.finish_note,
        },
        "initiator_name": user_names.get(inst.initiator_id) if inst.initiator_id else None,
        "biz": {
            "type": inst.biz_type,
            "label": _BIZ_NAME.get(inst.biz_type, "单据"),
            "id": inst.biz_id,
            "no": biz_no,
            "apply_user_name": user_names.get(apply_user) if apply_user else None,
            "doc_status": doc.status,
        },
        "nodes": nodes,
        "orphan_tasks": [task_out(t) for t in orphan],
        "users": users,
        "my_task_id": my_task.id if (inst.status == 1 and my_task) else None,
        "can_withdraw": bool(
            inst.status == 1 and (_is_initiator(inst, doc, user) or user.is_admin)
        ),
        "can_terminate": bool(inst.status == 1 and user.is_admin),
    }


@router.post("/instances/{instance_id}/withdraw")
async def withdraw_instance(instance_id: int, db: DbDep, user: UserDep):
    """发起人撤销审批中的流程（管理员亦可）。单据→已取消。"""
    inst = (
        await db.execute(
            select(WfInstance).where(WfInstance.id == instance_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not inst:
        raise HTTPException(404, "流程实例不存在")
    _check_biz_perm(inst.biz_type, user)
    if inst.status != 1:
        raise HTTPException(400, "流程不在审批中，无需撤销")
    doc = await _get_doc(db, inst.biz_type, inst.biz_id)
    if doc.status != 1:
        raise HTTPException(400, "单据状态异常")
    if not _is_initiator(inst, doc, user) and not user.is_admin:
        raise HTTPException(403, "仅发起人或管理员可撤销")
    inst.status = 4
    await _cancel_instance(db, inst, doc, user, f"{user.real_name or ''} 撤销申请")
    return {"ok": True, "instance_status": 4}


@router.post("/instances/{instance_id}/terminate")
async def terminate_instance(
    instance_id: int, body: TerminateIn, db: DbDep, user: UserDep
):
    """管理员终止审批中的流程。单据→已取消。"""
    if not user.is_admin:
        raise HTTPException(403, "仅管理员可终止流程")
    inst = (
        await db.execute(
            select(WfInstance).where(WfInstance.id == instance_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not inst:
        raise HTTPException(404, "流程实例不存在")
    _check_biz_perm(inst.biz_type, user)
    if inst.status != 1:
        raise HTTPException(400, "流程不在审批中，无需终止")
    doc = await _get_doc(db, inst.biz_type, inst.biz_id)
    if doc.status != 1:
        raise HTTPException(400, "单据状态异常")
    inst.status = 5
    await _cancel_instance(db, inst, doc, user, f"{user.real_name or '管理员'} 终止：{body.reason or '无'}")
    return {"ok": True, "instance_status": 5}


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: int, db: DbDep, user: UserDep):
    """管理员删除审批中的实例：单据作废 + 实例记录隐藏（软删），进度页仍可按原链接查看。"""
    if not user.is_admin:
        raise HTTPException(403, "仅管理员可删除流程实例")
    inst = (
        await db.execute(
            select(WfInstance).where(WfInstance.id == instance_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not inst:
        raise HTTPException(404, "流程实例不存在")
    _check_biz_perm(inst.biz_type, user)
    if inst.status != 1:
        raise HTTPException(400, "仅审批中的实例可删除")
    doc = await _get_doc(db, inst.biz_type, inst.biz_id)
    if doc.status != 1:
        raise HTTPException(400, "单据状态异常")
    inst.status = 5
    inst.del_flag = 1
    inst.update_by = user.id
    await _cancel_instance(db, inst, doc, user, f"管理员删除：{user.real_name or '—'}")
    return {"ok": True, "deleted": instance_id}


# ============================================================
# 流程监控（审批中心）
# ============================================================
@router.get("/monitor/instances")
async def monitor_instances(
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("approval:monitor"))],
    params: PageParams = Depends(),
    status: int | None = None,
    biz_type: str | None = None,
    keyword: str | None = None,
):
    """全部审批实例汇总（分页；可按状态/单据类型/单据编号过滤）。"""
    conds = [WfInstance.del_flag == 0]
    if status is not None:
        conds.append(WfInstance.status == status)
    if biz_type:
        conds.append(WfInstance.biz_type == biz_type)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        pairs: list[tuple[str, int]] = []
        for bt, (model, no_col, _u) in _BIZ_DOC_NO.items():
            ids = list(
                await db.scalars(
                    select(model.id).where(model.del_flag == 0, no_col.like(kw)).limit(50)
                )
            )
            pairs += [(bt, i) for i in ids]
        if not pairs:
            return PageData.build(0, params, [])
        conds.append(or_(*[and_(WfInstance.biz_type == bt, WfInstance.biz_id == i) for bt, i in pairs[:200]]))
    total = await db.scalar(select(func.count()).select_from(WfInstance).where(*conds)) or 0
    if not total:
        return PageData.build(0, params, [])
    insts = list(
        await db.scalars(
            select(WfInstance).where(*conds).order_by(WfInstance.id.desc()).offset(params.offset).limit(params.limit)
        )
    )
    records = await _instance_rows_out(db, insts)
    return PageData.build(total, params, records)


@router.get("/monitor/stats")
async def monitor_stats(db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("approval:monitor"))]):
    """监控汇总：按状态 / 单据类型统计实例数。"""
    by_status = {
        s: n
        for s, n in (
            await db.execute(
                select(WfInstance.status, func.count())
                .where(WfInstance.del_flag == 0)
                .group_by(WfInstance.status)
            )
        ).all()
    }
    by_biz = {
        b: n
        for b, n in (
            await db.execute(
                select(WfInstance.biz_type, func.count())
                .where(WfInstance.del_flag == 0)
                .group_by(WfInstance.biz_type)
            )
        ).all()
    }
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "by_biz": by_biz,
        "status_labels": INSTANCE_STATUS,
    }

