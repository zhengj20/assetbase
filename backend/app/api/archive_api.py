"""基础档案 API：分类/供应商/仓库/空间（含空间树）。"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DbDep, UserDep, require_perm
from app.models.archive import AssCategory, AssOffice, AssSpace, AssSupplier, AssWarehouse
from app.models.asset import AssAsset
from app.models.doc import AssPurchaseApply, AssStockIn
from app.schemas.archive import (
    CategoryIn,
    CategoryOut,
    OfficeIn,
    OfficeOut,
    SpaceIn,
    SpaceOut,
    SupplierIn,
    SupplierOut,
    WarehouseIn,
    WarehouseOut,
)

router = APIRouter(tags=["基础档案"])


# ============ 资产分类 ============
@router.get("/categories")
async def list_categories(db: DbDep, user: UserDep):
    rows = list(
        await db.scalars(
            select(AssCategory)
            .where(AssCategory.del_flag == 0)
            .order_by(AssCategory.sort, AssCategory.id)
        )
    )
    return [CategoryOut.model_validate(r) for r in rows]


@router.post("/categories", response_model=CategoryOut)
async def create_category(
    body: CategoryIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("category:create"))],
):
    exists = await db.scalar(
        select(func.count()).select_from(AssCategory).where(AssCategory.code == body.code)
    )
    if exists:
        raise HTTPException(400, "分类代码已存在")
    c = AssCategory(**body.model_dump(), create_by=user.id)
    db.add(c)
    await db.flush()
    return c


@router.put("/categories/{cid}", response_model=CategoryOut)
async def update_category(
    cid: int,
    body: CategoryIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("category:edit"))],
):
    c = await db.get(AssCategory, cid)
    if not c or c.del_flag == 1:
        raise HTTPException(404, "分类不存在")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    c.update_by = user.id
    c.version += 1
    return c


@router.delete("/categories/{cid}")
async def delete_category(
    cid: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("category:delete"))],
):
    in_use = await db.scalar(
        select(func.count()).select_from(AssAsset).where(AssAsset.category_id == cid)
    )
    if in_use:
        raise HTTPException(400, f"分类下已有 {in_use} 项资产，无法删除")
    c = await db.get(AssCategory, cid)
    if not c or c.del_flag == 1:
        raise HTTPException(404, "分类不存在")
    c.del_flag = 1
    c.update_by = user.id
    return {"ok": True}


# ============ 供应商 ============
@router.get("/suppliers")
async def list_suppliers(db: DbDep, user: UserDep, keyword: str | None = None):
    conds = [AssSupplier.del_flag == 0]
    if keyword:
        conds.append(AssSupplier.supplier_name.contains(keyword))
    rows = await db.scalars(select(AssSupplier).where(*conds).order_by(AssSupplier.id))
    return [SupplierOut.model_validate(r) for r in rows]


@router.post("/suppliers", response_model=SupplierOut)
async def create_supplier(
    body: SupplierIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("supplier:create"))],
):
    s = AssSupplier(**body.model_dump(), create_by=user.id)
    db.add(s)
    await db.flush()
    return s


@router.put("/suppliers/{sid}", response_model=SupplierOut)
async def update_supplier(
    sid: int,
    body: SupplierIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("supplier:edit"))],
):
    s = await db.get(AssSupplier, sid)
    if not s or s.del_flag == 1:
        raise HTTPException(404, "供应商不存在")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    s.update_by = user.id
    s.version += 1
    return s


@router.delete("/suppliers/{sid}")
async def delete_supplier(
    sid: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("supplier:delete"))],
):
    s = await db.get(AssSupplier, sid)
    if not s or s.del_flag == 1:
        raise HTTPException(404, "供应商不存在")
    s.del_flag = 1
    s.update_by = user.id
    return {"ok": True}


# ============ 仓库 ============
@router.get("/warehouses")
async def list_warehouses(db: DbDep, user: UserDep, keyword: str | None = None):
    conds = [AssWarehouse.del_flag == 0]
    if keyword:
        conds.append(AssWarehouse.warehouse_name.contains(keyword))
    rows = await db.scalars(select(AssWarehouse).where(*conds).order_by(AssWarehouse.id))
    return [WarehouseOut.model_validate(r) for r in rows]


@router.post("/warehouses", response_model=WarehouseOut)
async def create_warehouse(
    body: WarehouseIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("warehouse:create"))],
):
    w = AssWarehouse(**body.model_dump(), create_by=user.id)
    db.add(w)
    await db.flush()
    return w


@router.put("/warehouses/{wid}", response_model=WarehouseOut)
async def update_warehouse(
    wid: int,
    body: WarehouseIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("warehouse:edit"))],
):
    w = await db.get(AssWarehouse, wid)
    if not w or w.del_flag == 1:
        raise HTTPException(404, "仓库不存在")
    for k, v in body.model_dump().items():
        setattr(w, k, v)
    w.update_by = user.id
    w.version += 1
    return w


@router.delete("/warehouses/{wid}")
async def delete_warehouse(
    wid: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("warehouse:delete"))],
):
    in_use = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            AssAsset.warehouse_id == wid, AssAsset.status == 1
        )
    )
    if in_use:
        raise HTTPException(400, f"仓库在库存资产 {in_use} 项，无法删除")
    w = await db.get(AssWarehouse, wid)
    if not w or w.del_flag == 1:
        raise HTTPException(404, "仓库不存在")
    w.del_flag = 1
    w.update_by = user.id
    return {"ok": True}


@router.get("/warehouses/{wid}/stock")
async def warehouse_stock(wid: int, db: DbDep, user: UserDep):
    """库存台账：仓库 + 分类维度汇总（方案模块5）。"""
    from sqlalchemy import case

    rows = await db.execute(
        select(
            AssWarehouse.id.label("warehouse_id"),
            AssWarehouse.warehouse_name,
            AssCategory.category_name,
            func.count(AssAsset.id).label("total_count"),
            func.sum(case((AssAsset.status == 1, 1), else_=0)).label("in_stock"),
            func.sum(AssAsset.price).label("total_price"),
        )
        .join(AssAsset, AssAsset.warehouse_id == AssWarehouse.id, isouter=True)
        .join(AssCategory, AssCategory.id == AssAsset.category_id, isouter=True)
        .where(AssWarehouse.id == wid, AssAsset.del_flag == 0)
        .group_by(AssWarehouse.id, AssCategory.category_name)
    )
    return [
        {
            "warehouse_id": r.warehouse_id,
            "warehouse_name": r.warehouse_name,
            "category_name": r.category_name or "未分类",
            "total_count": r.total_count,
            "in_stock": r.in_stock,
            "total_price": float(r.total_price or 0),
        }
        for r in rows
    ]


# ============ 办公地点 ============
@router.get("/offices")
async def list_offices(db: DbDep, user: UserDep, keyword: str | None = None, org_id: int | None = None):
    conds = [AssOffice.del_flag == 0]
    if keyword:
        conds.append(AssOffice.office_name.contains(keyword))
    if org_id:
        conds.append(AssOffice.org_id == org_id)
    rows = await db.scalars(select(AssOffice).where(*conds).order_by(AssOffice.sort, AssOffice.id))
    return [OfficeOut.model_validate(r) for r in rows]


@router.post("/offices", response_model=OfficeOut)
async def create_office(
    body: OfficeIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("office:create"))],
):
    o = AssOffice(**body.model_dump(), create_by=user.id)
    db.add(o)
    await db.flush()
    return o


@router.put("/offices/{oid}", response_model=OfficeOut)
async def update_office(
    oid: int,
    body: OfficeIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("office:edit"))],
):
    o = await db.get(AssOffice, oid)
    if not o or o.del_flag == 1:
        raise HTTPException(404, "办公地点不存在")
    for k, v in body.model_dump().items():
        setattr(o, k, v)
    o.update_by = user.id
    o.version += 1
    return o


@router.delete("/offices/{oid}")
async def delete_office(
    oid: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("office:delete"))],
):
    in_use = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            AssAsset.office_id == oid, AssAsset.del_flag == 0, AssAsset.status.notin_([5, 6])
        )
    )
    if in_use:
        raise HTTPException(400, f"该办公地点名下仍有 {in_use} 项资产，无法删除")
    o = await db.get(AssOffice, oid)
    if not o or o.del_flag == 1:
        raise HTTPException(404, "办公地点不存在")
    o.del_flag = 1
    o.update_by = user.id
    return {"ok": True}


# ============ 空间（售楼处/样板间四级空间树） ============
@router.get("/spaces")
async def list_spaces(db: DbDep, user: UserDep, project_id: int | None = None):
    conds = [AssSpace.del_flag == 0]
    # 数据范围（与资产同口径）：空间挂在项目（组织）下
    if user.org_ids is not None:
        if user.org_ids:
            conds.append(AssSpace.project_id.in_(user.org_ids))
        else:
            conds.append(AssSpace.create_by == user.id)
    if project_id:
        conds.append(AssSpace.project_id == project_id)
    rows = list(
        await db.scalars(select(AssSpace).where(*conds).order_by(AssSpace.sort, AssSpace.id))
    )
    # 组装森林：项目节点下的空间树
    by_parent: dict[int, list] = {}
    for r in rows:
        by_parent.setdefault(r.parent_id, []).append(r)

    def tree(parent_id: int) -> list[dict]:
        out = []
        for r in by_parent.get(parent_id, []):
            out.append(
                {
                    **SpaceOut.model_validate(r).model_dump(),
                    "children": tree(r.id),
                }
            )
        return out

    # 根节点 = parent_id 为 0 的节点（项目级空间）
    return tree(0)


@router.post("/spaces", response_model=SpaceOut)
async def create_space(
    body: SpaceIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("space:create"))],
):
    s = AssSpace(**body.model_dump(), create_by=user.id)
    db.add(s)
    await db.flush()
    return s


@router.put("/spaces/{sid}", response_model=SpaceOut)
async def update_space(
    sid: int,
    body: SpaceIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("space:edit"))],
):
    s = await db.get(AssSpace, sid)
    if not s or s.del_flag == 1:
        raise HTTPException(404, "空间不存在")
    status_changed = body.space_status != s.space_status
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    s.update_by = user.id
    s.version += 1
    if status_changed:
        # 父级状态变更：自动同步全部下级空间（下级之后仍可单独调整）
        by_parent: dict[int, list[AssSpace]] = {}
        for r in (await db.scalars(select(AssSpace).where(AssSpace.del_flag == 0))).all():
            by_parent.setdefault(r.parent_id, []).append(r)
        frontier = [sid]
        while frontier:
            nxt: list[int] = []
            for pid in frontier:
                for child in by_parent.get(pid, []):
                    child.space_status = s.space_status
                    child.update_by = user.id
                    child.version += 1
                    nxt.append(child.id)
            frontier = nxt
    return s


@router.delete("/spaces/{sid}")
async def delete_space(
    sid: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("space:delete"))],
):
    # 方案 6.3：空间关闭前校验资产已清空
    in_use = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            AssAsset.space_id == sid, AssAsset.status.notin_([5, 6]), AssAsset.del_flag == 0
        )
    )
    if in_use:
        raise HTTPException(400, f"空间内仍有 {in_use} 项资产未清理")
    s = await db.get(AssSpace, sid)
    if not s or s.del_flag == 1:
        raise HTTPException(404, "空间不存在")
    s.del_flag = 1
    s.update_by = user.id
    return {"ok": True}
