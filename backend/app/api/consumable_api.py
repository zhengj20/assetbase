"""易耗品域 API：物料档案 / 库存 / 采购 / 入库 / 领用。

提交审批、取消、审批通过均复用通用 doc 引擎（/docs/{biz_type}/... + /approvals）。
biz_type: con_purchase / con_inbound / con_issue。
"""
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select

from app.core.deps import CurrentUser, DbDep, UserDep, require_perm
from app.core.pagination import PageData, PageParams
from app.models.archive import AssWarehouse
from app.models.consumable import (
    ConInbound,
    ConInboundItem,
    ConIssue,
    ConIssueItem,
    ConItem,
    ConPurchase,
    ConPurchaseItem,
    ConStock,
)
from app.models.sys import SysOrg, SysUser
from app.schemas.consumable import (
    ConInboundDetailOut,
    ConInboundIn,
    ConInboundItemOut,
    ConInboundOut,
    ConIssueDetailOut,
    ConIssueIn,
    ConIssueItemOut,
    ConIssueOut,
    ConItemIn,
    ConItemOption,
    ConItemOut,
    ConPurchaseDetailOut,
    ConPurchaseIn,
    ConPurchaseItemOut,
    ConPurchaseOut,
    ConStockOut,
)
from app.services.seq_service import next_doc_no

router = APIRouter()

Permitted = Annotated[CurrentUser, Depends(require_perm("con_item:list"))]


def _remaining(pi: ConPurchaseItem) -> int:
    """采购明细剩余可分配 = 采购数 - 已入库 - 已直发。"""
    return (pi.num or 0) - (pi.inbound_num or 0) - (pi.issued_num or 0)


# ==================== 物料档案 ====================
@router.get("/con/items", response_model=PageData[ConItemOut])
async def list_items(
    db: DbDep, user: UserDep, params: PageParams = Depends(),
    keyword: str | None = None, category: str | None = None, status: int | None = None,
    _p: Permitted = None,
):
    conds = [ConItem.del_flag == 0]
    if keyword:
        conds.append(func.or_(ConItem.item_name.like(f"%{keyword}%"), ConItem.item_code.like(f"%{keyword}%")))
    if category:
        conds.append(ConItem.category == category)
    if status is not None:
        conds.append(ConItem.status == status)
    total = await db.scalar(select(func.count()).select_from(ConItem).where(*conds))
    rows = (
        await db.execute(
            select(ConItem).where(*conds).order_by(ConItem.id.desc()).offset(params.offset).limit(params.limit)
        )
    ).all()
    return PageData.build(total, params, [ConItemOut.model_validate(r[0]) for r in rows])


@router.post("/con/items", response_model=ConItemOut)
async def create_item(
    body: ConItemIn, db: DbDep, user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("con_item:create"))] = None,
):
    if await db.scalar(select(ConItem.id).where(ConItem.item_code == body.item_code, ConItem.del_flag == 0)):
        raise HTTPException(400, "物料编码已存在")
    doc = ConItem(**body.model_dump(exclude_none=True), create_by=user.id)
    db.add(doc)
    await db.flush()
    return ConItemOut.model_validate(doc)


@router.get("/con/items/options", response_model=list[ConItemOption])
async def item_options(db: DbDep, user: UserDep, keyword: str | None = None, _p: Permitted = None):
    conds = [ConItem.del_flag == 0, ConItem.status == 1]
    if keyword:
        conds.append(func.or_(ConItem.item_name.like(f"%{keyword}%"), ConItem.item_code.like(f"%{keyword}%")))
    rows = (await db.execute(select(ConItem).where(*conds).order_by(ConItem.id.desc()).limit(50))).all()
    return [ConItemOption.model_validate(r[0]) for r in rows]


@router.get("/con/items/{item_id}", response_model=ConItemOut)
async def get_item(item_id: int, db: DbDep, user: UserDep, _p: Permitted = None):
    item = await db.get(ConItem, item_id)
    if not item or item.del_flag == 1:
        raise HTTPException(404, "物料不存在")
    return ConItemOut.model_validate(item)


@router.put("/con/items/{item_id}", response_model=ConItemOut)
async def update_item(
    item_id: int, body: ConItemIn, db: DbDep, user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("con_item:create"))] = None,
):
    item = await db.get(ConItem, item_id)
    if not item or item.del_flag == 1:
        raise HTTPException(404, "物料不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    item.update_by = user.id
    return ConItemOut.model_validate(item)


@router.delete("/con/items/{item_id}")
async def delete_item(
    item_id: int, db: DbDep, user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("con_item:create"))] = None,
):
    item = await db.get(ConItem, item_id)
    if not item or item.del_flag == 1:
        raise HTTPException(404, "物料不存在")
    stock_qty = await db.scalar(
        select(func.coalesce(func.sum(ConStock.qty), 0)).where(ConStock.item_id == item_id, ConStock.del_flag == 0)
    )
    if stock_qty:
        raise HTTPException(400, "该物料存在库存，不能删除")
    item.del_flag = 1
    item.update_by = user.id
    return {"ok": True}


# ==================== 库存 ====================
@router.get("/con/stock", response_model=PageData[ConStockOut])
async def list_stock(
    db: DbDep, user: UserDep, params: PageParams = Depends(),
    keyword: str | None = None, warehouse_id: int | None = None, item_id: int | None = None,
    category: str | None = None,
    _p: Annotated[CurrentUser, Depends(require_perm("con_stock:list"))] = None,
):
    conds = [ConStock.del_flag == 0]
    if warehouse_id:
        conds.append(ConStock.warehouse_id == warehouse_id)
    if item_id:
        conds.append(ConStock.item_id == item_id)
    if category:
        conds.append(ConItem.category == category)
    if keyword:
        conds.append(func.or_(ConItem.item_name.like(f"%{keyword}%"), ConItem.item_code.like(f"%{keyword}%")))
    total = await db.scalar(
        select(func.count()).select_from(ConStock).join(ConItem, ConItem.id == ConStock.item_id, isouter=True).where(*conds)
    )
    rows = (
        await db.execute(
            select(ConStock, ConItem.item_code, ConItem.item_name, ConItem.unit, ConItem.category, AssWarehouse.warehouse_name)
            .join(ConItem, ConItem.id == ConStock.item_id, isouter=True)
            .join(AssWarehouse, AssWarehouse.id == ConStock.warehouse_id, isouter=True)
            .where(*conds)
            .order_by(ConStock.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    ).all()
    records = []
    for r in rows:
        rec = ConStockOut.model_validate(r[0])
        rec.item_code, rec.item_name, rec.item_unit, rec.category, rec.warehouse_name = r[1], r[2], r[3], r[4], r[5]
        records.append(rec)
    return PageData.build(total, params, records)


# ==================== 库存统计（在库口径：qty > 0；断货 = qty <= 0，与驾驶舱断货预警同口径） ====================
@router.get("/con/stock/summary")
async def stock_summary(
    db: DbDep, user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("con_stock:list"))] = None,
):
    """库存统计：KPI 汇总 + 仓库维度 + 分类维度。明细查询复用 /con/stock 列表接口。"""
    conds = [ConStock.del_flag == 0]
    in_stock = ConStock.qty > 0
    kpi = (
        await db.execute(
            select(
                func.sum(case((in_stock, 1), else_=0)),
                func.coalesce(func.sum(case((in_stock, ConStock.qty), else_=0)), 0),
                func.coalesce(func.sum(case((in_stock, ConStock.qty * ConStock.unit_price), else_=0)), 0),
                func.sum(case((ConStock.qty <= 0, 1), else_=0)),
            ).where(*conds)
        )
    ).one()

    wh_rows = (
        await db.execute(
            select(
                ConStock.warehouse_id,
                func.sum(case((in_stock, 1), else_=0)),
                func.coalesce(func.sum(case((in_stock, ConStock.qty), else_=0)), 0),
                func.coalesce(func.sum(case((in_stock, ConStock.qty * ConStock.unit_price), else_=0)), 0),
            )
            .where(*conds)
            .group_by(ConStock.warehouse_id)
        )
    ).all()
    wh_names = {
        r.id: r.warehouse_name
        for r in await db.scalars(select(AssWarehouse).where(AssWarehouse.del_flag == 0))
    }
    warehouses = sorted(
        (
            {
                "warehouse_id": r[0],
                "warehouse_name": wh_names.get(r[0], f"仓库{r[0]}"),
                "stock_records": int(r[1] or 0),
                "total_qty": int(r[2] or 0),
                "total_amount": round(float(r[3] or 0), 2),
            }
            for r in wh_rows
            if r[1]
        ),
        key=lambda x: -x["total_qty"],
    )

    cat_rows = (
        await db.execute(
            select(
                ConItem.category,
                func.sum(case((in_stock, 1), else_=0)),
                func.coalesce(func.sum(case((in_stock, ConStock.qty), else_=0)), 0),
                func.coalesce(func.sum(case((in_stock, ConStock.qty * ConStock.unit_price), else_=0)), 0),
            )
            .select_from(ConStock)
            .join(ConItem, ConItem.id == ConStock.item_id, isouter=True)
            .where(*conds)
            .group_by(ConItem.category)
        )
    ).all()
    categories = [
        {
            "category": r[0] or "未分类",
            "stock_records": int(r[1] or 0),
            "total_qty": int(r[2] or 0),
            "total_amount": round(float(r[3] or 0), 2),
        }
        for r in sorted((c for c in cat_rows if c[1]), key=lambda x: -x[2])
    ]

    wh_count = await db.scalar(
        select(func.count())
        .select_from(AssWarehouse)
        .where(AssWarehouse.del_flag == 0, AssWarehouse.status == 1)
    )
    return {
        "summary": {
            "warehouse_count": wh_count,
            "stock_records": int(kpi[0] or 0),
            "total_qty": int(kpi[1] or 0),
            "total_amount": round(float(kpi[2] or 0), 2),
            "stockout_count": int(kpi[3] or 0),
        },
        "warehouses": warehouses,
        "categories": categories,
    }


# ==================== 采购 ====================
@router.get("/con/purchases", response_model=PageData[ConPurchaseOut])
async def list_purchases(
    db: DbDep, user: UserDep, params: PageParams = Depends(),
    status: int | None = None, keyword: str | None = None,
    _p: Annotated[CurrentUser, Depends(require_perm("con_purchase:list"))] = None,
):
    conds = [ConPurchase.del_flag == 0]
    if status is not None:
        conds.append(ConPurchase.status == status)
    if keyword:
        conds.append(ConPurchase.purchase_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(ConPurchase).where(*conds))
    rows = (
        await db.execute(
            select(ConPurchase, SysOrg.org_name, SysUser.real_name)
            .join(SysOrg, SysOrg.id == ConPurchase.org_id, isouter=True)
            .join(SysUser, SysUser.id == ConPurchase.apply_user, isouter=True)
            .where(*conds)
            .order_by(ConPurchase.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    ).all()
    records = []
    for r in rows:
        rec = ConPurchaseOut.model_validate(r[0])
        rec.org_name, rec.apply_user_name = r[1], r[2]
        records.append(rec)
    return PageData.build(total, params, records)


@router.post("/con/purchases", response_model=ConPurchaseDetailOut)
async def create_purchase(
    body: ConPurchaseIn, db: DbDep, user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("con_purchase:create"))] = None,
):
    # 校验物料存在
    item_ids = [i.item_id for i in body.items]
    found = await db.scalar(select(func.count()).select_from(ConItem).where(ConItem.id.in_(item_ids), ConItem.del_flag == 0))
    if found != len(set(item_ids)):
        raise HTTPException(400, "存在无效物料")
    total = sum((i.unit_price or 0) * i.num for i in body.items)
    doc = ConPurchase(
        purchase_no=await next_doc_no(db, "con_purchase"),
        org_id=body.org_id,
        apply_user=user.id,
        apply_date=body.apply_date or date.today(),
        supplier_id=body.supplier_id,
        total_amount=Decimal(str(total)).quantize(Decimal("0.01")),
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        db.add(
            ConPurchaseItem(
                purchase_id=doc.id, item_id=i.item_id, num=i.num, unit_price=i.unit_price,
                amount=Decimal(str((i.unit_price or 0) * i.num)).quantize(Decimal("0.01")),
            )
        )
    base = ConPurchaseOut.model_validate(doc).model_dump()
    base["apply_user_name"] = user.real_name
    return ConPurchaseDetailOut(
        **base,
        items=[], total_num=sum(i.num for i in body.items),
        inbound_num=0, issued_num=0, remaining_num=sum(i.num for i in body.items),
    )


@router.get("/con/purchases/{pid}", response_model=ConPurchaseDetailOut)
async def get_purchase(pid: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("con_purchase:list"))] = None):
    doc = await db.get(ConPurchase, pid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "采购单不存在")
    items = list(await db.scalars(select(ConPurchaseItem).where(ConPurchaseItem.purchase_id == pid).order_by(ConPurchaseItem.id)))
    base = ConPurchaseOut.model_validate(doc).model_dump()
    base["org_name"] = await db.scalar(select(SysOrg.org_name).where(SysOrg.id == doc.org_id))
    base["apply_user_name"] = await db.scalar(select(SysUser.real_name).where(SysUser.id == doc.apply_user))
    rec = ConPurchaseDetailOut(**base)
    total_num = inbound_num = issued_num = 0
    for it in items:
        item = await db.get(ConItem, it.item_id)
        total_num += it.num or 0
        inbound_num += it.inbound_num or 0
        issued_num += it.issued_num or 0
        ib = ConPurchaseItemOut.model_validate(it).model_dump()
        ib["item_name"] = item.item_name if item else None
        ib["item_unit"] = item.unit if item else None
        rec.items.append(ConPurchaseItemOut(**ib))
    rec.total_num, rec.inbound_num, rec.issued_num = total_num, inbound_num, issued_num
    rec.remaining_num = total_num - inbound_num - issued_num
    return rec


@router.delete("/con/purchases/{pid}")
async def delete_purchase(pid: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("con_purchase:create"))] = None):
    doc = await db.get(ConPurchase, pid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "采购单不存在")
    if doc.status not in (0, 3, 4):
        raise HTTPException(400, "仅草稿/已驳回/已取消可删除")
    doc.del_flag = 1
    doc.update_by = user.id
    return {"ok": True}


# ==================== 入库 ====================
@router.get("/con/inbounds", response_model=PageData[ConInboundOut])
async def list_inbounds(
    db: DbDep, user: UserDep, params: PageParams = Depends(),
    status: int | None = None, keyword: str | None = None,
    _p: Annotated[CurrentUser, Depends(require_perm("con_inbound:list"))] = None,
):
    conds = [ConInbound.del_flag == 0]
    if status is not None:
        conds.append(ConInbound.status == status)
    if keyword:
        conds.append(ConInbound.in_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(ConInbound).where(*conds))
    rows = (
        await db.execute(
            select(ConInbound, AssWarehouse.warehouse_name, SysUser.real_name)
            .join(AssWarehouse, AssWarehouse.id == ConInbound.warehouse_id, isouter=True)
            .join(SysUser, SysUser.id == ConInbound.create_by, isouter=True)
            .where(*conds)
            .order_by(ConInbound.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    ).all()
    records = []
    for r in rows:
        rec = ConInboundOut.model_validate(r[0])
        rec.warehouse_name, rec.create_by_name = r[1], r[2]
        records.append(rec)
    return PageData.build(total, params, records)


@router.post("/con/inbounds", response_model=ConInboundDetailOut)
async def create_inbound(
    body: ConInboundIn, db: DbDep, user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("con_inbound:create"))] = None,
):
    org_id = body.org_id
    if body.purchase_id:
        purchase = await db.get(ConPurchase, body.purchase_id)
        if not purchase or purchase.del_flag == 1:
            raise HTTPException(404, "关联采购单不存在")
        if purchase.status != 2:
            raise HTTPException(400, "仅审批通过的采购单可入库")
        org_id = purchase.org_id
        pi_map = {
            i.item_id: i
            for i in await db.scalars(select(ConPurchaseItem).where(ConPurchaseItem.purchase_id == body.purchase_id))
        }
        for it in body.items:
            pi = pi_map.get(it.item_id)
            if not pi:
                raise HTTPException(400, f"物料 {it.item_id} 不在该采购单上")
            if it.num > _remaining(pi):
                raise HTTPException(400, f"物料 {it.item_id} 可入库数量不足（剩余 {_remaining(pi)}）")
    if not org_id:
        raise HTTPException(400, "缺少核算公司")
    total_num = sum(i.num for i in body.items)
    total_amount = sum((i.unit_price or 0) * i.num for i in body.items)
    doc = ConInbound(
        in_no=await next_doc_no(db, "con_inbound"),
        warehouse_id=body.warehouse_id,
        purchase_id=body.purchase_id,
        org_id=org_id,
        in_date=body.in_date or date.today(),
        total_num=total_num,
        total_amount=Decimal(str(total_amount)).quantize(Decimal("0.01")),
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        db.add(
            ConInboundItem(
                in_id=doc.id, item_id=i.item_id, num=i.num, unit_price=i.unit_price,
                amount=Decimal(str((i.unit_price or 0) * i.num)).quantize(Decimal("0.01")),
            )
        )
    base = ConInboundOut.model_validate(doc).model_dump()
    base["create_by_name"] = user.real_name
    return ConInboundDetailOut(**base, items=[])


@router.get("/con/inbounds/{iid}", response_model=ConInboundDetailOut)
async def get_inbound(iid: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("con_inbound:list"))] = None):
    doc = await db.get(ConInbound, iid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "入库单不存在")
    items = list(await db.scalars(select(ConInboundItem).where(ConInboundItem.in_id == iid).order_by(ConInboundItem.id)))
    base = ConInboundOut.model_validate(doc).model_dump()
    base["warehouse_name"] = await db.scalar(select(AssWarehouse.warehouse_name).where(AssWarehouse.id == doc.warehouse_id))
    base["create_by_name"] = await db.scalar(select(SysUser.real_name).where(SysUser.id == doc.create_by))
    rec = ConInboundDetailOut(**base)
    for it in items:
        item = await db.get(ConItem, it.item_id)
        ib = ConInboundItemOut.model_validate(it).model_dump()
        ib["item_name"] = item.item_name if item else None
        rec.items.append(ConInboundItemOut(**ib))
    return rec


@router.delete("/con/inbounds/{iid}")
async def delete_inbound(iid: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("con_inbound:create"))] = None):
    doc = await db.get(ConInbound, iid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "入库单不存在")
    if doc.status not in (0, 3, 4):
        raise HTTPException(400, "仅草稿/已驳回/已取消可删除")
    doc.del_flag = 1
    doc.update_by = user.id
    return {"ok": True}


# ==================== 领用 ====================
@router.get("/con/issues", response_model=PageData[ConIssueOut])
async def list_issues(
    db: DbDep, user: UserDep, params: PageParams = Depends(),
    status: int | None = None, keyword: str | None = None, source_type: int | None = None,
    _p: Annotated[CurrentUser, Depends(require_perm("con_issue:list"))] = None,
):
    conds = [ConIssue.del_flag == 0]
    if status is not None:
        conds.append(ConIssue.status == status)
    if source_type is not None:
        conds.append(ConIssue.source_type == source_type)
    if keyword:
        conds.append(ConIssue.issue_no.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(ConIssue).where(*conds))
    rows = (
        await db.execute(
            select(ConIssue, SysUser.real_name)
            .join(SysUser, SysUser.id == ConIssue.receive_user, isouter=True)
            .where(*conds)
            .order_by(ConIssue.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    ).all()
    records = []
    for r in rows:
        rec = ConIssueOut.model_validate(r[0])
        rec.receive_user_name = r[1]
        rec.source_name = "采购直发" if rec.source_type == 1 else "库存领用"
        records.append(rec)
    return PageData.build(total, params, records)


@router.post("/con/issues", response_model=ConIssueDetailOut)
async def create_issue(
    body: ConIssueIn, db: DbDep, user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("con_issue:create"))] = None,
):
    if body.source_type == 1:
        # 采购直发：校验采购单 + 明细 + 剩余可分配
        if not body.purchase_id:
            raise HTTPException(400, "采购直发必须指定采购单")
        purchase = await db.get(ConPurchase, body.purchase_id)
        if not purchase or purchase.del_flag == 1:
            raise HTTPException(404, "采购单不存在")
        if purchase.status != 2:
            raise HTTPException(400, "仅审批通过的采购单可分配领用")
        pi_map = {
            i.item_id: i
            for i in await db.scalars(select(ConPurchaseItem).where(ConPurchaseItem.purchase_id == body.purchase_id))
        }
        for it in body.items:
            pi = pi_map.get(it.item_id)
            if not pi:
                raise HTTPException(400, f"物料 {it.item_id} 不在该采购单上")
            if it.num > _remaining(pi):
                raise HTTPException(400, f"物料 {it.item_id} 可分配数量不足（剩余 {_remaining(pi)}）")
        org_id, warehouse_id = purchase.org_id, None
    else:
        # 库存领用：校验仓库 + 库存
        if not body.warehouse_id:
            raise HTTPException(400, "库存领用必须指定仓库")
        stock_map: dict[int, Decimal | None] = {}
        for it in body.items:
            stock = (
                await db.scalars(
                    select(ConStock).where(ConStock.item_id == it.item_id, ConStock.warehouse_id == body.warehouse_id, ConStock.del_flag == 0)
                )
            ).first()
            if not stock or (stock.qty or 0) < it.num:
                cur = stock.qty if stock else 0
                raise HTTPException(400, f"物料 {it.item_id} 库存不足（现有 {cur}，领用 {it.num}）")
            stock_map[it.item_id] = stock.unit_price
        org_id, warehouse_id = body.org_id, body.warehouse_id
    if not org_id:
        raise HTTPException(400, "缺少核算公司")
    doc = ConIssue(
        issue_no=await next_doc_no(db, "con_issue"),
        source_type=body.source_type,
        purchase_id=body.purchase_id if body.source_type == 1 else None,
        warehouse_id=warehouse_id,
        org_id=org_id,
        receive_user=body.receive_user,
        receive_dept=body.receive_dept,
        issue_date=body.issue_date or date.today(),
        total_num=sum(i.num for i in body.items),
        remark=body.remark,
        create_by=user.id,
    )
    db.add(doc)
    await db.flush()
    for i in body.items:
        # 单价快照：直发取采购明细单价、库存领用取库存成本单价（金额统计依赖此列，NULL 会导致金额丢失）
        if body.source_type == 1:
            price = pi_map[i.item_id].unit_price
        else:
            price = stock_map.get(i.item_id)
        db.add(ConIssueItem(issue_id=doc.id, item_id=i.item_id, num=i.num, unit_price=price))
    base = ConIssueOut.model_validate(doc).model_dump()
    base["source_name"] = "采购直发" if body.source_type == 1 else "库存领用"
    return ConIssueDetailOut(**base, items=[])


@router.get("/con/issues/{iid}", response_model=ConIssueDetailOut)
async def get_issue(iid: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("con_issue:list"))] = None):
    doc = await db.get(ConIssue, iid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "领用单不存在")
    items = list(await db.scalars(select(ConIssueItem).where(ConIssueItem.issue_id == iid).order_by(ConIssueItem.id)))
    base = ConIssueOut.model_validate(doc).model_dump()
    base["receive_user_name"] = await db.scalar(select(SysUser.real_name).where(SysUser.id == doc.receive_user)) if doc.receive_user else None
    base["warehouse_name"] = await db.scalar(select(AssWarehouse.warehouse_name).where(AssWarehouse.id == doc.warehouse_id)) if doc.warehouse_id else None
    base["source_name"] = "采购直发" if doc.source_type == 1 else "库存领用"
    rec = ConIssueDetailOut(**base)
    for it in items:
        item = await db.get(ConItem, it.item_id)
        ib = ConIssueItemOut.model_validate(it).model_dump()
        ib["item_name"] = item.item_name if item else None
        rec.items.append(ConIssueItemOut(**ib))
    return rec


@router.delete("/con/issues/{iid}")
async def delete_issue(iid: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("con_issue:create"))] = None):
    doc = await db.get(ConIssue, iid)
    if not doc or doc.del_flag == 1:
        raise HTTPException(404, "领用单不存在")
    if doc.status not in (0, 3, 4):
        raise HTTPException(400, "仅草稿/已驳回/已取消可删除")
    doc.del_flag = 1
    doc.update_by = user.id
    return {"ok": True}
