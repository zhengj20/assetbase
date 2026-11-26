"""全局搜索 API（用户新增核心需求）：顶栏快速检索。"""
from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import DbDep, UserDep
from app.models.archive import AssCategory
from app.models.asset import AssAsset
from app.models.sys import SysUser

from app.api.asset_api import build_asset_conditions

router = APIRouter(prefix="/search", tags=["全局搜索"])


@router.get("/quick")
async def quick_search(
    db: DbDep,
    user: UserDep,
    keyword: str,
    limit: int = 10,
):
    """顶栏全局搜索：资产编码/名称/规格/品牌/型号/位置，返回前 N 条。"""
    kw = keyword.strip()
    if not kw:
        return []
    conds = build_asset_conditions(user, keyword=kw)
    rows = await db.execute(
        select(
            AssAsset.id,
            AssAsset.asset_code,
            AssAsset.asset_name,
            AssAsset.spec,
            AssAsset.status,
            AssAsset.is_high_value,
            AssCategory.category_name,
            SysUser.real_name,
        )
        .join(AssCategory, AssCategory.id == AssAsset.category_id, isouter=True)
        .join(SysUser, SysUser.id == AssAsset.use_user_id, isouter=True)
        .where(*conds)
        .order_by(AssAsset.id.desc())
        .limit(min(max(limit, 1), 20))
    )
    return [
        {
            "id": r[0],
            "asset_code": r[1],
            "asset_name": r[2],
            "spec": r[3],
            "status": r[4],
            "is_high_value": r[5],
            "category_name": r[6],
            "use_user_name": r[7],
        }
        for r in rows
    ]


@router.get("/assets")
async def search_assets(
    db: DbDep,
    user: UserDep,
    keyword: str,
    status: int | None = None,
    category_id: int | None = None,
    org_id: int | None = None,
    warehouse_id: int | None = None,
    space_id: int | None = None,
    is_high_value: int | None = None,
    limit: int = 50,
):
    """全局搜索完整结果（与资产列表同条件构建，数据权限生效）。"""
    kw = keyword.strip()
    if not kw:
        return {"total": 0, "records": []}
    conds = build_asset_conditions(
        user, keyword=kw, status=status, category_id=category_id, org_id=org_id,
        warehouse_id=warehouse_id, space_id=space_id, is_high_value=is_high_value,
    )
    total = await db.scalar(select(func.count()).select_from(AssAsset).where(*conds))
    rows = await db.execute(
        select(AssAsset)
        .where(*conds)
        .order_by(AssAsset.id.desc())
        .limit(min(max(limit, 1), 200))
    )
    return {
        "total": total,
        "records": [
            {
                "id": a.id,
                "asset_code": a.asset_code,
                "asset_name": a.asset_name,
                "spec": a.spec,
                "brand": a.brand,
                "status": a.status,
                "is_high_value": a.is_high_value,
                "price": float(a.price or 0),
                "location_detail": a.location_detail,
            }
            for a in rows.scalars()
        ],
    }
