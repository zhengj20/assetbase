"""资产组合包 API（方案 P1-4：整包调拨 / 拆包 / 合包）。"""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.core.deps import CurrentUser, DbDep, UserDep, require_perm
from app.core.pagination import PageData, PageParams
from app.models.asset import AssAsset, AssAssetGroup
from app.services.asset_log_service import ACTION_MODIFY, snapshot, write_log

router = APIRouter(tags=["资产组合包"])

PermGroup = Annotated[CurrentUser, Depends(require_perm("group:edit"))]


def _scope_asset_conds(user) -> list:
    """资产数据范围条件（None=全部；[]=仅本人创建；否则按组织）。"""
    if user.org_ids is None:
        return []
    if not user.org_ids:
        return [AssAsset.create_by == user.id]
    return [AssAsset.org_id.in_(user.org_ids)]


class GroupIn(BaseModel):
    group_name: str
    asset_ids: list[int] = []
    total_price: Decimal | None = None
    project_id: int | None = None
    remark: str | None = None


class GroupAdjustIn(BaseModel):
    add_asset_ids: list[int] = []
    remove_asset_ids: list[int] = []


async def _load_group(gid: int, db) -> AssAssetGroup:
    g = await db.get(AssAssetGroup, gid)
    if not g or g.del_flag == 1:
        raise HTTPException(404, "组合包不存在")
    return g


async def _group_assets(db, gid: int) -> list[AssAsset]:
    return list(
        await db.scalars(
            select(AssAsset).where(AssAsset.group_id == gid, AssAsset.del_flag == 0)
            .order_by(AssAsset.asset_code)
        )
    )


@router.get("/asset-groups")
async def list_groups(
    db: DbDep, user: UserDep, params: PageParams = Depends(), keyword: str | None = None
):
    """组合包列表（含资产数与名称预览）。"""
    base = select(AssAssetGroup).where(AssAssetGroup.del_flag == 0)
    if user.org_ids is not None:
        # 数据范围：包自身项目或任一成员资产在范围内
        if not user.org_ids:
            sub = (
                select(AssAsset.group_id)
                .where(AssAsset.del_flag == 0, AssAsset.create_by == user.id)
                .subquery()
            )
            base = base.where(or_(AssAssetGroup.project_id.is_(None), AssAssetGroup.id.in_(sub)))
        else:
            sub = (
                select(AssAsset.group_id)
                .where(AssAsset.del_flag == 0, AssAsset.org_id.in_(user.org_ids))
                .subquery()
            )
            base = base.where(or_(AssAssetGroup.project_id.in_(user.org_ids), AssAssetGroup.id.in_(sub)))
    if keyword:
        base = base.where(AssAssetGroup.group_name.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = list(
        (
            await db.execute(base.order_by(AssAssetGroup.id.desc())
            .offset(params.offset).limit(params.limit))
        ).scalars()
    )
    ids = [g.id for g in rows]
    name_map: dict = {}
    if ids:
        for gid, name in (
            await db.execute(
                select(AssAsset.group_id, AssAsset.asset_name)
                .where(AssAsset.group_id.in_(ids), AssAsset.del_flag == 0)
                .order_by(AssAsset.asset_code)
            )
        ).all():
            name_map.setdefault(gid, []).append(name)
    records = [
        {
            "id": g.id,
            "group_name": g.group_name,
            "project_id": g.project_id,
            "space_id": g.space_id,
            "total_price": float(g.total_price or 0),
            "status": g.status,
            "remark": g.remark,
            "asset_count": len(name_map.get(g.id, [])),
            "asset_names": "、".join(name_map.get(g.id, []))[:200],
            "create_time": g.create_time,
        }
        for g in rows
    ]
    return PageData.build(total, params, records)


@router.get("/asset-groups/{gid}")
async def get_group(gid: int, db: DbDep, user: UserDep):
    g = await _load_group(gid, db)
    assets = await _group_assets(db, gid)
    return {
        "id": g.id, "group_name": g.group_name, "project_id": g.project_id,
        "space_id": g.space_id, "total_price": float(g.total_price or 0),
        "status": g.status, "remark": g.remark, "create_time": g.create_time,
        "assets": [
            {"id": a.id, "asset_code": a.asset_code, "asset_name": a.asset_name,
             "category_id": a.category_id, "price": float(a.price or 0),
             "status": a.status, "warehouse_id": a.warehouse_id, "org_id": a.org_id}
            for a in assets
        ],
    }


async def _scoped_assets(db, user, ids: list[int]) -> list[AssAsset]:
    """按数据范围加载资产（行锁防并发拆合包竞态）；越权/不存在直接 403。"""
    assets = list(
        await db.scalars(
            select(AssAsset)
            .where(AssAsset.id.in_(ids), *_scope_asset_conds(user))
            .with_for_update()
        )
    )
    missing = set(ids) - {a.id for a in assets}
    if missing:
        raise HTTPException(403, f"{len(missing)} 项资产不存在或不在您的数据范围内")
    return assets


@router.post("/asset-groups")
async def create_group(body: GroupIn, db: DbDep, user: UserDep, _p: PermGroup):
    """建包：将资产归入新组合包（合包 = 把已在别的包的资产选进来）。"""
    if not body.group_name.strip():
        raise HTTPException(400, "组合包名称不能为空")
    g = AssAssetGroup(
        group_name=body.group_name.strip(),
        project_id=body.project_id,
        total_price=body.total_price,
        status=1,
        remark=body.remark,
        create_by=user.id,
    )
    db.add(g)
    await db.flush()
    if body.asset_ids:
        assets = await _scoped_assets(db, user, body.asset_ids)
        for a in assets:
            if a.del_flag == 1 or a.status in (5, 6):
                raise HTTPException(400, f"资产 {a.asset_code} 已删除或报废，不能入包")
            a.group_id = g.id
            a.version += 1
            await write_log(db, a, ACTION_MODIFY, biz_type="group", before=snapshot(a), operator_id=user.id)
    if not g.total_price:
        g.total_price = sum((a.price or 0) for a in await _group_assets(db, g.id))
    return {"id": g.id}


@router.put("/asset-groups/{gid}")
async def adjust_group(gid: int, body: GroupAdjustIn, db: DbDep, user: UserDep, _p: PermGroup):
    """拆包/合包：移出（group_id 置空）或加入（含从其他包转入）。"""
    g = await _load_group(gid, db)
    if g.status != 1:
        raise HTTPException(400, "组合包已解散")
    if body.remove_asset_ids:
        assets = await _scoped_assets(db, user, body.remove_asset_ids)
        for a in assets:
            if a.group_id != gid:
                continue
            a.group_id = None
            a.version += 1
            await write_log(db, a, ACTION_MODIFY, biz_type="group", before=snapshot(a), operator_id=user.id)
    if body.add_asset_ids:
        assets = await _scoped_assets(db, user, body.add_asset_ids)
        for a in assets:
            if a.del_flag == 1 or a.status in (5, 6):
                raise HTTPException(400, f"资产 {a.asset_code} 已删除或报废，不能入包")
            a.group_id = gid
            a.version += 1
            await write_log(db, a, ACTION_MODIFY, biz_type="group", before=snapshot(a), operator_id=user.id)
    g.total_price = sum((a.price or 0) for a in await _group_assets(db, gid))
    return {"ok": True}


@router.delete("/asset-groups/{gid}")
async def dissolve_group(gid: int, db: DbDep, user: UserDep, _p: PermGroup):
    """解散组合包：成员资产清空包归属（资产本身保留）。"""
    g = await _load_group(gid, db)
    assets = list(
        await db.scalars(select(AssAsset).where(AssAsset.group_id == gid))
    )
    for a in assets:
        a.group_id = None
        a.version += 1
        await write_log(db, a, ACTION_MODIFY, biz_type="group", before=snapshot(a), operator_id=user.id)
    g.status = 0
    g.update_by = user.id
    return {"ok": True, "released": len(assets)}
