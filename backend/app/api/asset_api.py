"""资产核心 API：档案 CRUD / 履历 / 二维码补打 / 图片上传 / 导入导出 / 折旧计提 / 全局搜索查询构建。"""
import io
import uuid
from pathlib import Path
from datetime import date as _date
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import load_workbook
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbDep, UserDep, require_perm
from app.core.pagination import PageData, PageParams
from app.models.archive import AssCategory, AssOffice, AssSpace, AssSupplier, AssWarehouse
from app.models.asset import AssAsset, AssAssetImage, AssAssetLog
from app.models.check import AssDepreciation
from app.models.sys import SysOrg, SysUser
from app.schemas.asset import (
    AssetIn,
    AssetListRow,
    AssetLogOut,
    AssetOut,
    AssetUpdateIn,
)
from app.services.asset_log_service import (
    ACTION_MODIFY,
    ACTION_REPAIR,
    ACTION_STOCK_IN,
    snapshot,
    write_log,
)
from app.services.depreciation_service import calculate as dep_calculate
from app.services.depreciation_service import reverse as dep_reverse
from app.services.excel_service import build_excel
from app.services.seq_service import next_asset_code

router = APIRouter(tags=["资产档案"])


def build_asset_conditions(
    user,
    keyword: str | None = None,
    asset_code: str | None = None,
    status: int | None = None,
    category_id: int | None = None,
    org_id: int | None = None,
    project_id: int | None = None,
    warehouse_id: int | None = None,
    space_id: int | None = None,
    use_user_id: int | None = None,
    use_dept_id: int | None = None,
    is_high_value: int | None = None,
) -> list:
    """统一查询条件构建：数据权限 + 组合筛选 + 关键词检索（列表/导出/搜索共用）。"""
    conds = [AssAsset.del_flag == 0]

    # 数据权限（方案 1.2 五档）
    if user.org_ids is None:
        pass  # 全部数据
    elif not user.org_ids:  # 仅本人
        conds.append(
            or_(AssAsset.use_user_id == user.id, AssAsset.create_by == user.id)
        )
    else:
        conds.append(
            or_(
                AssAsset.org_id.in_(user.org_ids),
                AssAsset.project_id.in_(user.org_ids),
            )
        )

    if keyword:
        kw = keyword.strip()
        if kw:
            # 全局搜索（方案要求）：FULLTEXT ngram 全文匹配 + 编码前缀/位置包含组合
            ft = text(
                "MATCH(asset_name, spec, brand, model) AGAINST(:kw_ft IN BOOLEAN MODE)"
            ).bindparams(kw_ft=f"+{kw}")
            conds.append(
                or_(
                    ft,
                    AssAsset.asset_code.like(f"{kw}%"),
                    AssAsset.location_detail.contains(kw),
                    AssAsset.asset_name.contains(kw),
                )
            )
    if asset_code:
        conds.append(AssAsset.asset_code.like(f"{asset_code}%"))
    if status is not None:
        conds.append(AssAsset.status == status)
    if category_id:
        conds.append(
            or_(
                AssAsset.category_id == category_id,
                AssAsset.category_id.in_(
                    select(AssCategory.id).where(AssCategory.parent_id == category_id)
                ),
            )
        )
    if org_id:
        conds.append(AssAsset.org_id == org_id)
    if project_id:
        conds.append(AssAsset.project_id == project_id)
    if warehouse_id:
        conds.append(AssAsset.warehouse_id == warehouse_id)
    if space_id:
        conds.append(AssAsset.space_id == space_id)
    if use_user_id:
        conds.append(AssAsset.use_user_id == use_user_id)
    if use_dept_id:
        conds.append(AssAsset.use_dept_id == use_dept_id)
    if is_high_value is not None:
        conds.append(AssAsset.is_high_value == is_high_value)
    return conds


_USE_DEPT = aliased(SysOrg, name="use_dept")
_PROJ = aliased(SysOrg, name="proj")

_LIST_COLS = (
    AssAsset.id,
    AssAsset.asset_code,
    AssAsset.asset_name,
    AssAsset.spec,
    AssAsset.brand,
    AssAsset.status,
    AssAsset.is_high_value,
    AssAsset.price,
    AssAsset.net_value,
    AssAsset.buy_date,
    AssAsset.create_time,
    AssCategory.category_name,
    SysOrg.org_name,
    AssOffice.office_name,
    AssWarehouse.warehouse_name,
    AssSpace.space_name,
    SysUser.real_name,
    _USE_DEPT.org_name,
    _PROJ.org_name,
    AssAsset.qrcode,
)


def _row_dict(r) -> dict:
    return {
        "id": r[0],
        "asset_code": r[1],
        "asset_name": r[2],
        "spec": r[3],
        "brand": r[4],
        "status": r[5],
        "is_high_value": r[6],
        "price": r[7],
        "net_value": r[8],
        "buy_date": r[9],
        "create_time": r[10],
        "category_name": r[11],
        "org_name": r[12],
        "office_name": r[13],
        "warehouse_name": r[14],
        "space_name": r[15],
        "use_user_name": r[16],
        "use_dept_name": r[17],
        "project_name": r[18],
        "qrcode": r[19],
    }


def _list_query(conds: list):
    return (
        select(*_LIST_COLS)
        .join(AssCategory, AssCategory.id == AssAsset.category_id, isouter=True)
        .join(SysOrg, SysOrg.id == AssAsset.org_id, isouter=True)
        .join(AssOffice, AssOffice.id == AssAsset.office_id, isouter=True)
        .join(AssWarehouse, AssWarehouse.id == AssAsset.warehouse_id, isouter=True)
        .join(AssSpace, AssSpace.id == AssAsset.space_id, isouter=True)
        .join(SysUser, SysUser.id == AssAsset.use_user_id, isouter=True)
        .join(_USE_DEPT, _USE_DEPT.id == AssAsset.use_dept_id, isouter=True)
        .join(_PROJ, _PROJ.id == AssAsset.project_id, isouter=True)
        .where(*conds)
    )


@router.get("/assets", response_model=PageData[AssetListRow])
async def list_assets(
    db: DbDep,
    user: UserDep,
    params: PageParams = Depends(),
    keyword: str | None = None,
    asset_code: str | None = None,
    status: int | None = None,
    category_id: int | None = None,
    org_id: int | None = None,
    project_id: int | None = None,
    warehouse_id: int | None = None,
    space_id: int | None = None,
    use_user_id: int | None = None,
    use_dept_id: int | None = None,
    is_high_value: int | None = None,
):
    conds = build_asset_conditions(
        user, keyword, asset_code, status, category_id, org_id, project_id,
        warehouse_id, space_id, use_user_id, use_dept_id, is_high_value,
    )
    total = await db.scalar(
        select(func.count()).select_from(AssAsset).where(*conds)
    )
    rows = await db.execute(
        _list_query(conds).order_by(AssAsset.id.desc()).offset(params.offset).limit(params.limit)
    )
    return PageData.build(
        total, params, [AssetListRow.model_validate(_row_dict(r)) for r in rows]
    )


@router.get("/assets/export")
async def export_assets(
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:export"))],
    keyword: str | None = None,
    asset_code: str | None = None,
    status: int | None = None,
    category_id: int | None = None,
    org_id: int | None = None,
    project_id: int | None = None,
    warehouse_id: int | None = None,
    space_id: int | None = None,
    use_user_id: int | None = None,
    use_dept_id: int | None = None,
    is_high_value: int | None = None,
):
    """资产清单导出（流式分批处理，避免大数据量OOM）。"""
    conds = build_asset_conditions(
        user, keyword, asset_code, status, category_id, org_id, project_id,
        warehouse_id, space_id, use_user_id, use_dept_id, is_high_value,
    )
    STATUS = {0: "待入库", 1: "在库", 2: "领用中", 3: "维修中", 4: "调拨中", 5: "已报废", 6: "已处置", 7: "借用中"}
    BATCH_SIZE = 1000  # 每批处理1000条

    async def rows_generator():
        """分批查询生成器，避免一次性加载全部数据到内存。"""
        offset = 0
        while True:
            batch = (
                await db.execute(
                    _list_query(conds).order_by(AssAsset.id).offset(offset).limit(BATCH_SIZE)
                )
            ).all()
            if not batch:
                break
            for r in batch:
                d = _row_dict(r)
                yield [
                    d["asset_code"], d["asset_name"], d["category_name"], d["spec"],
                    d["brand"], STATUS.get(d["status"], str(d["status"])),
                    "是" if d["is_high_value"] else "否",
                    float(d["price"] or 0), float(d["net_value"] or 0),
                    str(d["buy_date"] or ""), d["org_name"] or "", d["office_name"] or "",
                    d["warehouse_name"] or "", d["space_name"] or "",
                    d["use_user_name"] or "", d["use_dept_name"] or "", str(d["create_time"] or ""),
                ]
            offset += BATCH_SIZE
            # 如果本批不足 BATCH_SIZE，说明已经是最后一批
            if len(batch) < BATCH_SIZE:
                break

    buf = build_excel(
        headers=["资产编码", "资产名称", "分类", "规格", "品牌", "状态", "高值",
                 "原值", "净值", "购置日期", "核算公司", "办公地点", "仓库", "空间位置",
                 "领用人", "责任部门", "建档时间"],
        rows=rows_generator(),
        sheet_name="资产清单",
        col_widths=[18, 24, 14, 18, 12, 8, 6, 12, 12, 12, 16, 16, 14, 16, 10, 12, 20],
    )
    filename = f"资产清单_{datetime.now():%Y%m%d%H%M%S}.xlsx"
    from urllib.parse import quote

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


_IMPORT_HEADERS = [
    "资产名称", "分类", "规格", "品牌", "型号", "单位", "原值", "购置日期",
    "核算公司", "责任部门", "领用人", "详细位置", "高值", "仓库", "供应商",
]


@router.get("/assets/import-template")
async def import_template(user: UserDep):
    """导入模板下载：首行为表头，第二行为示例。"""
    buf = await build_excel(
        headers=_IMPORT_HEADERS,
        rows=[["示例：办公电脑", "笔记本电脑", "i7/16G/512G", "联想", "ThinkPad", "台", 8999,
               "2026-01-01", "", "", "", "综合管理部", "否", "", ""]],
        sheet_name="资产导入模板",
        col_widths=[18, 14, 16, 12, 14, 8, 12, 12, 18, 14, 10, 18, 8, 14, 16],
    )
    from urllib.parse import quote

    filename = "资产导入模板.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ================= 资产维度统计（集团→公司→项目→部门层级，资产归口最深层级节点） =================

# 归口节点：每项资产只计入一个组织节点（使用部门 > 业务项目 > 核算公司），保证树形合计不重不漏
_ATTR_NODE = func.coalesce(AssAsset.use_dept_id, AssAsset.project_id, AssAsset.org_id)


async def _visible_orgs(db, user) -> list:
    """数据权限内的组织节点（与 /orgs 同口径）。"""
    if user.org_ids is None:
        return list(await db.scalars(select(SysOrg).where(SysOrg.del_flag == 0)))
    return list(
        await db.scalars(
            select(SysOrg).where(SysOrg.del_flag == 0, SysOrg.id.in_(user.org_ids))
        )
    )


@router.get("/assets/stats/tree")
async def asset_stats_tree(db: DbDep, user: UserDep):
    """维度统计：汇总卡 + 组织树（节点值 = 本节点及全部下级的归口资产合计）。"""
    conds = build_asset_conditions(user)
    orgs = await _visible_orgs(db, user)
    by_id = {o.id: o for o in orgs}

    rows = (
        await db.execute(
            select(
                _ATTR_NODE,
                func.count(AssAsset.id),
                func.coalesce(func.sum(AssAsset.price), 0),
                func.coalesce(func.sum(AssAsset.net_value), 0),
                func.sum(case((AssAsset.is_high_value == 1, 1), else_=0)),
            )
            .where(*conds)
            .group_by(_ATTR_NODE)
        )
    ).all()

    # 归口节点聚合
    agg: dict[int, list] = {}
    for r in rows:
        if r[0] is None:
            continue
        a = agg.setdefault(r[0], [0, 0.0, 0.0, 0])
        a[0] += r[1]
        a[1] += float(r[2])
        a[2] += float(r[3])
        a[3] += int(r[4] or 0)

    # 沿祖先链上卷（组织树很小，O(节点数×深度) 可接受）
    roll: dict[int, list] = {}
    for nid, vals in agg.items():
        cur = by_id.get(nid)
        while cur is not None:
            t = roll.setdefault(cur.id, [0, 0.0, 0.0, 0])
            t[0] += vals[0]
            t[1] += vals[1]
            t[2] += vals[2]
            t[3] += vals[3]
            cur = by_id.get(cur.parent_id) if cur.parent_id else None

    def build(parent_id: int) -> list:
        kids = sorted(
            (o for o in orgs if o.parent_id == parent_id),
            key=lambda o: (o.org_type, o.id),
        )
        out = []
        for o in kids:
            v = roll.get(o.id, [0, 0.0, 0.0, 0])
            out.append(
                {
                    "id": o.id,
                    "key": f"o{o.id}",
                    "org_name": o.org_name,
                    "org_type": o.org_type,
                    "count": v[0],
                    "value": v[1],
                    "net_value": v[2],
                    "high_value": v[3],
                    "children": build(o.id),
                }
            )
        return out

    return {
        "summary": {
            "count": sum(v[0] for v in agg.values()),
            "orig_value": round(sum(v[1] for v in agg.values()), 2),
            "net_value": round(sum(v[2] for v in agg.values()), 2),
            "high_value": sum(v[3] for v in agg.values()),
        },
        "tree": build(0),
    }


def _visible_space_ids(spaces: list, user) -> set[int]:
    """数据权限内的空间ID（空间按其所属项目判断可见性）。"""
    if user.org_ids is None:
        return {s.id for s in spaces}
    return {s.id for s in spaces if s.project_id in set(user.org_ids)}


async def _space_stats(db, user):
    """空间维度聚合：返回 (space_by_id, roll: space_id->[count,原值,净值,高值] 含全部下级, 可见空间列表)。"""
    conds = build_asset_conditions(user)
    spaces = list(await db.scalars(select(AssSpace).where(AssSpace.del_flag == 0)))
    visible = _visible_space_ids(spaces, user)
    vis = [s for s in spaces if s.id in visible]
    by_id = {s.id: s for s in vis}

    rows = (
        await db.execute(
            select(
                AssAsset.space_id,
                func.count(AssAsset.id),
                func.coalesce(func.sum(AssAsset.price), 0),
                func.coalesce(func.sum(AssAsset.net_value), 0),
                func.sum(case((AssAsset.is_high_value == 1, 1), else_=0)),
            )
            .where(*conds, AssAsset.space_id.isnot(None))
            .group_by(AssAsset.space_id)
        )
    ).all()

    agg: dict[int, list] = {}
    for r in rows:
        if r[0] not in visible:
            continue
        a = agg.setdefault(r[0], [0, 0.0, 0.0, 0])
        a[0] += r[1]
        a[1] += float(r[2])
        a[2] += float(r[3])
        a[3] += int(r[4] or 0)

    roll: dict[int, list] = {}
    for sid, vals in agg.items():
        cur = by_id.get(sid)
        while cur is not None:
            t = roll.setdefault(cur.id, [0, 0.0, 0.0, 0])
            for i in range(4):
                t[i] += vals[i]
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return by_id, roll, vis


def _space_node(s, by_id, roll, vis) -> dict:
    """空间树节点：兼容组织维度树（含 org_name 供标签、node_type=space 供前端识别路由明细）。

    id=真实空间ID（供明细路由）；key=带前缀唯一键（供 el-tree，避免与组织/项目ID撞号）。
    """
    v = roll.get(s.id, [0, 0.0, 0.0, 0])
    kids = sorted((x for x in vis if x.parent_id == s.id), key=lambda x: x.id)
    return {
        "id": s.id,
        "key": f"s{s.id}",
        "org_name": s.space_name,
        "name": s.space_name,
        "node_type": "space",
        "count": v[0],
        "value": round(v[1], 2),
        "net_value": round(v[2], 2),
        "high_value": v[3],
        "children": [_space_node(k, by_id, roll, vis) for k in kids],
    }


@router.get("/assets/stats/detail", response_model=PageData[AssetListRow])
async def asset_stats_detail(
    db: DbDep,
    user: UserDep,
    node_id: int | None = None,
    space_id: int | None = None,
    space_project_id: int | None = None,
    params: PageParams = Depends(),
    keyword: str | None = None,
    status: int | None = None,
):
    """节点明细：组织节点子树 或 空间节点子树 内的资产，与对应树的合计口径一致。

    node_id 缺省 = 当前数据权限范围内的全部资产。
    """
    conds = build_asset_conditions(user, keyword=keyword, status=status)
    if node_id is not None:
        orgs = await _visible_orgs(db, user)
        by_id = {o.id: o for o in orgs}
        if node_id not in by_id:
            raise HTTPException(404, "组织不存在或无权限")
        closure = {node_id}
        frontier = [node_id]
        while frontier:
            nxt = [o.id for o in orgs if o.parent_id in frontier]
            if not nxt:
                break
            closure.update(nxt)
            frontier = nxt
        conds.append(_ATTR_NODE.in_(closure))
    elif space_id is not None or space_project_id is not None:
        spaces = list(await db.scalars(select(AssSpace).where(AssSpace.del_flag == 0)))
        visible = _visible_space_ids(spaces, user)
        if space_id is not None:
            if space_id not in visible:
                raise HTTPException(404, "空间不存在或无权限")
            closure = {space_id}
            frontier = [space_id]
            while frontier:
                nxt = [s.id for s in spaces if s.parent_id in frontier]
                if not nxt:
                    break
                closure.update(nxt)
                frontier = nxt
            conds.append(AssAsset.space_id.in_(closure))
        else:
            ids = {s.id for s in spaces if s.project_id == space_project_id and s.id in visible}
            if not ids:
                raise HTTPException(404, "项目不存在或无权限")
            conds.append(AssAsset.space_id.in_(ids))
    total = await db.scalar(
        select(func.count()).select_from(AssAsset).where(*conds)
    )
    rows = (
        await db.execute(
            _list_query(conds)
            .order_by(AssAsset.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
    )
    return PageData.build(
        total, params, [AssetListRow.model_validate(_row_dict(r)) for r in rows]
    )


@router.get("/assets/stats/space-tree")
async def asset_stats_space_tree(db: DbDep, user: UserDep):
    """空间维度统计：项目 → 售楼处/样板间 → 房间。

    节点值 = 挂靠在该空间（含全部下级房间）的资产合计；未挂靠空间的资产不计入树，
    但计入 summary 总盘。
    """
    orgs = await _visible_orgs(db, user)
    org_by_id = {o.id: o for o in orgs}
    by_id, roll, vis = await _space_stats(db, user)

    roots_all = [s for s in vis if not s.parent_id]

    # 所属项目节点上卷（= 该项目下各顶级空间之和）
    proj_roll: dict[int, list] = {}
    for s in roots_all:
        v = roll.get(s.id, [0, 0.0, 0.0, 0])
        t = proj_roll.setdefault(s.project_id, [0, 0.0, 0.0, 0])
        for i in range(4):
            t[i] += v[i]

    tree = []
    for pid in sorted({s.project_id for s in vis}):
        pv = proj_roll.get(pid, [0, 0.0, 0.0, 0])
        roots = sorted((s for s in vis if s.project_id == pid and not s.parent_id), key=lambda x: x.id)
        tree.append(
            {
                "id": pid,
                "key": f"p{pid}",
                "name": org_by_id.get(pid).org_name if pid in org_by_id else f"项目{pid}",
                "node_type": "project",
                "count": pv[0],
                "value": round(pv[1], 2),
                "net_value": round(pv[2], 2),
                "high_value": pv[3],
                "children": [_space_node(s, by_id, roll, vis) for s in roots],
            }
        )

    # summary：全部顶级空间之和（= 已挂靠空间的全部资产）
    tot = [0, 0.0, 0.0, 0]
    for s in roots_all:
        v = roll.get(s.id, [0, 0.0, 0.0, 0])
        for i in range(4):
            tot[i] += v[i]
    return {
        "summary": {
            "count": tot[0],
            "orig_value": round(tot[1], 2),
            "net_value": round(tot[2], 2),
            "high_value": tot[3],
        },
        "tree": tree,
    }


# ================= 仓库库存统计（在库口径：绑定仓库 且 状态=在库，与仓库删除校验/驾驶舱同口径） =================
@router.get("/warehouse-stock/summary")
async def warehouse_stock_summary(db: DbDep, user: UserDep):
    """仓库库存统计：KPI 汇总 + 仓库维度 + 分类维度。库存明细查询复用 /assets 列表接口。"""
    conds = build_asset_conditions(user) + [
        AssAsset.warehouse_id.isnot(None),
        AssAsset.status == 1,
    ]
    kpi = (
        await db.execute(
            select(
                func.count(AssAsset.id),
                func.coalesce(func.sum(AssAsset.price), 0),
                func.coalesce(func.sum(AssAsset.net_value), 0),
                func.sum(case((AssAsset.is_high_value == 1, 1), else_=0)),
            ).where(*conds)
        )
    ).one()

    wh_rows = (
        await db.execute(
            select(
                AssAsset.warehouse_id,
                func.count(AssAsset.id),
                func.coalesce(func.sum(AssAsset.price), 0),
                func.coalesce(func.sum(AssAsset.net_value), 0),
                func.sum(case((AssAsset.is_high_value == 1, 1), else_=0)),
            )
            .where(*conds)
            .group_by(AssAsset.warehouse_id)
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
                "in_stock_count": r[1],
                "in_stock_price": round(float(r[2]), 2),
                "in_stock_net": round(float(r[3]), 2),
                "high_value": int(r[4] or 0),
            }
            for r in wh_rows
        ),
        key=lambda x: -x["in_stock_count"],
    )

    cat_rows = (
        await db.execute(
            select(
                AssCategory.id,
                AssCategory.category_name,
                func.count(AssAsset.id),
                func.coalesce(func.sum(AssAsset.price), 0),
                func.coalesce(func.sum(AssAsset.net_value), 0),
            )
            .select_from(AssAsset)
            .join(AssCategory, AssCategory.id == AssAsset.category_id, isouter=True)
            .where(*conds)
            .group_by(AssCategory.id, AssCategory.category_name)
        )
    ).all()
    categories = [
        {
            "category_id": r[0],
            "category_name": r[1] or "未分类",
            "in_stock_count": r[2],
            "in_stock_price": round(float(r[3]), 2),
            "in_stock_net": round(float(r[4]), 2),
        }
        for r in sorted(cat_rows, key=lambda x: -x[2])
    ]

    wh_count = await db.scalar(
        select(func.count())
        .select_from(AssWarehouse)
        .where(AssWarehouse.del_flag == 0, AssWarehouse.status == 1)
    )
    return {
        "summary": {
            "warehouse_count": wh_count,
            "in_stock_count": int(kpi[0] or 0),
            "in_stock_price": round(float(kpi[1]), 2),
            "in_stock_net": round(float(kpi[2]), 2),
            "high_value": int(kpi[3] or 0),
        },
        "warehouses": warehouses,
        "categories": categories,
    }


@router.get("/assets/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: int, db: DbDep, user: UserDep):
    a = await db.get(AssAsset, asset_id)
    if not a or a.del_flag == 1:
        raise HTTPException(404, "资产不存在")
    _check_asset_scope(user, a)
    return a


@router.get("/assets/{asset_id}/logs", response_model=list[AssetLogOut])
async def asset_logs(asset_id: int, db: DbDep, user: UserDep):
    """资产履历时间线（方案 P0-3）。"""
    a = await db.get(AssAsset, asset_id)
    if not a or a.del_flag == 1:
        raise HTTPException(404, "资产不存在")
    _check_asset_scope(user, a)
    rows = await db.scalars(
        select(AssAssetLog)
        .where(AssAssetLog.asset_id == asset_id)
        .order_by(AssAssetLog.operate_time.desc(), AssAssetLog.id.desc())
        .limit(200)
    )
    return [AssetLogOut.model_validate(r) for r in rows]


def _check_asset_scope(user, a: AssAsset) -> None:
    """单资产数据范围校验（详情/履历/改删共用），越权按 404 处理不泄露存在性。"""
    if user.org_ids is None:
        return
    if not user.org_ids:
        if a.create_by != user.id:
            raise HTTPException(404, "资产不存在")
        return
    if a.org_id not in user.org_ids:
        raise HTTPException(404, "资产不存在")


def _asset_scope_conds(user) -> list:
    """资产数据范围 SQL 条件（None=全部；[]=仅本人创建；否则按组织）。"""
    if user.org_ids is None:
        return []
    if not user.org_ids:
        return [AssAsset.create_by == user.id]
    return [AssAsset.org_id.in_(user.org_ids)]


@router.post("/assets", response_model=AssetOut)
async def create_asset(
    body: AssetIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:create"))],
):
    """手工建档（存量初始化/盘盈补录）。编码按附录A规则原子发号。"""
    cat = await db.get(AssCategory, body.category_id)
    if not cat or cat.del_flag == 1:
        raise HTTPException(400, "资产分类不存在")
    org = await db.get(SysOrg, body.org_id)
    if not org:
        raise HTTPException(400, "核算公司不存在")

    code = await next_asset_code(db, org.org_code, cat.code)
    a = AssAsset(
        **body.model_dump(exclude={"is_high_value", "is_reusable"}),
        is_high_value=1 if body.is_high_value else 0,
        is_reusable=1 if body.is_reusable else 0,
        asset_code=code,
        qrcode=uuid.uuid4().hex,
        net_value=body.price,
        create_by=user.id,
    )
    db.add(a)
    await db.flush()
    await write_log(db, a, ACTION_MODIFY, biz_type="manual", operator_id=user.id)
    return a


@router.put("/assets/{asset_id}", response_model=AssetOut)
async def update_asset(
    asset_id: int,
    body: AssetUpdateIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:edit"))],
):
    a = await db.get(AssAsset, asset_id)
    if not a or a.del_flag == 1:
        raise HTTPException(404, "资产不存在")
    _check_asset_scope(user, a)
    if a.status in (5, 6):
        raise HTTPException(400, "已报废/处置资产不可修改")
    before = snapshot(a)
    # exclude_unset：允许显式传 null 清空归属/位置/日期等可空字段（方案 4.x 领用归还）
    data = body.model_dump(exclude_unset=True)
    if "is_high_value" in data:
        data["is_high_value"] = 1 if data["is_high_value"] else 0
    if "is_reusable" in data:
        data["is_reusable"] = 1 if data["is_reusable"] else 0
    for k, v in data.items():
        setattr(a, k, v)
    a.update_by = user.id
    a.version += 1
    await db.flush()
    await write_log(db, a, ACTION_MODIFY, biz_type="manual", before=before, operator_id=user.id)
    return a


class BatchUpdateIn(BaseModel):
    """批量变更入参。"""
    asset_ids: list[int] = Field(min_length=1, max_length=500, description="资产ID列表（最多500）")
    use_user_id: int | None = None
    use_dept_id: int | None = None
    warehouse_id: int | None = None
    project_id: int | None = None
    space_id: int | None = None
    location_detail: str | None = None


@router.post("/assets/batch-update")
async def batch_update_assets(
    body: BatchUpdateIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:edit"))],
):
    """批量变更资产台账信息（使用人、使用部门、仓库、项目、空间、位置等）。"""
    # 查询所有要变更的资产（限数据范围内，越权项直接报错）
    assets = list(
        await db.scalars(
            select(AssAsset)
            .where(AssAsset.id.in_(body.asset_ids), AssAsset.del_flag == 0, *_asset_scope_conds(user))
            .with_for_update()
        )
    )
    if len(assets) != len(set(body.asset_ids)):
        raise HTTPException(403, f"{len(set(body.asset_ids)) - len(assets)} 项资产不存在或不在您的数据范围内")
    
    # 检查是否有已报废/处置的资产
    invalid_assets = [a for a in assets if a.status in (5, 6)]
    if invalid_assets:
        codes = [a.asset_code for a in invalid_assets[:5]]
        raise HTTPException(400, f"以下资产已报废/处置，不可修改：{', '.join(codes)}")
    
    # 构建变更数据（只包含非None的字段）
    update_data = {}
    if body.use_user_id is not None:
        update_data["use_user_id"] = body.use_user_id
    if body.use_dept_id is not None:
        update_data["use_dept_id"] = body.use_dept_id
    if body.warehouse_id is not None:
        update_data["warehouse_id"] = body.warehouse_id
    if body.project_id is not None:
        update_data["project_id"] = body.project_id
    if body.space_id is not None:
        update_data["space_id"] = body.space_id
    if body.location_detail is not None:
        update_data["location_detail"] = body.location_detail
    
    if not update_data:
        raise HTTPException(400, "请至少选择一项要变更的字段")
    
    # 批量更新
    updated_count = 0
    for a in assets:
        before = snapshot(a)
        for k, v in update_data.items():
            setattr(a, k, v)
        a.update_by = user.id
        a.version += 1
        await write_log(
            db, a, ACTION_MODIFY, biz_type="batch_update",
            before=before, operator_id=user.id
        )
        updated_count += 1
    
    await db.flush()
    return {"ok": True, "updated": updated_count}


@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:delete"))],
):
    a = await db.get(AssAsset, asset_id)
    if not a or a.del_flag == 1:
        raise HTTPException(404, "资产不存在")
    _check_asset_scope(user, a)
    if a.status not in (5, 6, 0):
        raise HTTPException(400, "仅待入库/已报废/已处置资产可删除")
    a.del_flag = 1
    a.update_by = user.id
    return {"ok": True}


@router.post("/assets/{asset_id}/reprint-qrcode")
async def reprint_qrcode(
    asset_id: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:edit"))],
):
    """标签补打（方案附录B）：旧码作废、新码绑定同一资产ID。"""
    a = await db.get(AssAsset, asset_id)
    if not a or a.del_flag == 1:
        raise HTTPException(404, "资产不存在")
    before = snapshot(a)
    a.qrcode = uuid.uuid4().hex
    a.update_by = user.id
    a.version += 1
    await write_log(db, a, ACTION_MODIFY, biz_type="reprint_qrcode", before=before, operator_id=user.id)
    return {"qrcode": a.qrcode}


# ================= 资产图片（上传 + 服务端压缩） =================
def _upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _compress_image(data: bytes) -> bytes:
    """服务端压缩：最长边 1600px，统一转 RGB，JPEG 质量 80。"""
    img = Image.open(io.BytesIO(data))
    img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    max_edge = 1600
    w, h = img.size
    if max(w, h) > max_edge:
        if w >= h:
            img = img.resize((max_edge, max(1, round(h * max_edge / w))), Image.LANCZOS)
        else:
            img = img.resize((max(1, round(w * max_edge / h)), max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 原始上传上限 20MB


@router.post("/assets/{asset_id}/images")
async def upload_asset_image(
    asset_id: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:edit"))],
    file: UploadFile = File(...),
):
    """上传图片：服务端压缩后落盘，资产首张图自动设为主图。"""
    a = await db.get(AssAsset, asset_id)
    if not a or a.del_flag == 1:
        raise HTTPException(404, "资产不存在")
    _check_asset_scope(user, a)
    data = await file.read()
    if not data:
        raise HTTPException(400, "文件为空")
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "图片超过 20MB 限制")
    try:
        compressed = _compress_image(data)
    except Exception:
        raise HTTPException(400, "仅支持图片文件（jpg/png/webp/gif 等）")
    fname = f"{uuid.uuid4().hex}.jpg"
    sub = _upload_root() / "assets" / str(asset_id)
    sub.mkdir(parents=True, exist_ok=True)
    (sub / fname).write_bytes(compressed)
    url = f"/api/v1/uploads/assets/{asset_id}/{fname}"
    img = AssAssetImage(
        asset_id=asset_id,
        image_type=1,
        image_url=url,
        upload_time=datetime.now(),
        create_by=user.id,
    )
    db.add(img)
    if not a.image_cover:
        a.image_cover = url
        a.update_by = user.id
    return {"url": url, "size": len(compressed)}


@router.get("/assets/{asset_id}/images")
async def list_asset_images(asset_id: int, db: DbDep, user: UserDep):
    a = await db.get(AssAsset, asset_id)
    if not a or a.del_flag == 1:
        raise HTTPException(404, "资产不存在")
    _check_asset_scope(user, a)
    rows = await db.scalars(
        select(AssAssetImage)
        .where(AssAssetImage.asset_id == asset_id, AssAssetImage.del_flag == 0)
        .order_by(AssAssetImage.id)
    )
    return [
        {
            "id": r.id,
            "image_url": r.image_url,
            "image_type": r.image_type,
            "upload_time": r.upload_time,
        }
        for r in rows
    ]


@router.delete("/assets/{asset_id}/images/{image_id}")
async def delete_asset_image(
    asset_id: int,
    image_id: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:edit"))],
):
    a = await db.get(AssAsset, asset_id)
    if not a or a.del_flag == 1:
        raise HTTPException(404, "资产不存在")
    _check_asset_scope(user, a)
    img = await db.get(AssAssetImage, image_id)
    if not img or img.del_flag == 1 or img.asset_id != asset_id:
        raise HTTPException(404, "图片不存在")
    img.del_flag = 1
    img.update_by = user.id
    if img.image_url:
        try:
            p = _upload_root() / img.image_url.split("/uploads/", 1)[1]
            if p.exists():
                p.unlink()
        except Exception:
            pass
    if a.image_cover == img.image_url:
        nxt = await db.scalar(
            select(AssAssetImage)
            .where(
                AssAssetImage.asset_id == asset_id,
                AssAssetImage.del_flag == 0,
                AssAssetImage.id != image_id,
            )
            .order_by(AssAssetImage.id)
            .limit(1)
        )
        a.image_cover = nxt.image_url if nxt else None
        a.update_by = user.id
    return {"ok": True}


# ================= 维修流程（状态 3 维修中 闭环） =================

class RepairIn(BaseModel):
    note: str | None = Field(None, max_length=500, description="维修说明")


@router.post("/assets/{asset_id}/repair")
async def asset_repair(
    asset_id: int,
    body: RepairIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:repair"))],
):
    """报修：资产转入「维修中」，记录维修前状态供完成后恢复。"""
    a = list(
        await db.scalars(
            select(AssAsset)
            .where(AssAsset.id == asset_id, AssAsset.del_flag == 0, *_asset_scope_conds(user))
            .with_for_update()
        )
    )
    if not a:
        raise HTTPException(404, "资产不存在")
    a = a[0]
    if a.status in (5, 6):
        raise HTTPException(400, "已报废/处置资产不可报修")
    if a.status == 3:
        raise HTTPException(400, "该资产已在维修中")
    before = snapshot(a)
    a.pre_repair_status = a.status
    a.status = 3
    a.update_by = user.id
    a.version += 1
    await write_log(db, a, ACTION_REPAIR, biz_type="repair", before=before, operator_id=user.id)
    return {"ok": True, "status": 3, "note": body.note}


@router.post("/assets/{asset_id}/repair-done")
async def asset_repair_done(
    asset_id: int,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:repair"))],
):
    """维修完成：恢复维修前状态。"""
    a = list(
        await db.scalars(
            select(AssAsset)
            .where(AssAsset.id == asset_id, AssAsset.del_flag == 0, *_asset_scope_conds(user))
            .with_for_update()
        )
    )
    if not a:
        raise HTTPException(404, "资产不存在")
    a = a[0]
    if a.status != 3:
        raise HTTPException(400, "该资产不在维修中")
    before = snapshot(a)
    a.status = a.pre_repair_status or 1
    a.pre_repair_status = None
    a.update_by = user.id
    a.version += 1
    await write_log(db, a, ACTION_REPAIR, biz_type="repair_done", before=before, operator_id=user.id)
    return {"ok": True, "status": a.status}


# ================= Excel 批量导入（方案第八章存量初始化） =================

def _cell(row: tuple, idx: int | None):
    if idx is None or idx >= len(row) or row[idx] is None:
        return ""
    return str(row[idx]).strip()


def _parse_money(v: str) -> Decimal | None:
    if not v:
        return None
    try:
        return Decimal(v.replace(",", "").replace("¥", "").replace("元", ""))
    except Exception:
        raise ValueError(f"原值格式不正确: {v}")


def _parse_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, _date):
        return v
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"日期格式不正确: {v}（应为 YYYY-MM-DD）")


@router.post("/assets/import")
async def import_assets(
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("asset:create"))],
    file: UploadFile = File(...),
):
    """Excel 批量导入（存量初始化/盘盈补录）。逐行校验，失败行不影响成功行。"""
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "请上传 .xlsx 格式的 Excel 文件")
    data = await file.read()
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(400, "Excel 文件无法解析，请使用系统模板")
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(400, "Excel 内容为空")
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    col = {name: i for i, name in enumerate(header) if name}
    if "资产名称" not in col or "分类" not in col:
        raise HTTPException(400, "缺少必需列：资产名称、分类（请下载模板）")

    cats = {r.category_name: r for r in (
        await db.scalars(select(AssCategory).where(AssCategory.del_flag == 0))
    )}
    cats_by_code = {r.code: r for r in cats.values()}
    orgs = {r.org_name: r for r in (
        await db.scalars(select(SysOrg).where(SysOrg.del_flag == 0))
    )}
    users = {r.real_name: r for r in (
        await db.scalars(select(SysUser).where(SysUser.del_flag == 0, SysUser.status == 1))
    )}
    depts = {r.org_name: r for r in (
        await db.scalars(select(SysOrg).where(SysOrg.del_flag == 0, SysOrg.org_type == 4))
    )}
    warehouses = {r.warehouse_name: r for r in (
        await db.scalars(select(AssWarehouse).where(AssWarehouse.del_flag == 0))
    )}
    suppliers = {r.supplier_name: r for r in (
        await db.scalars(select(AssSupplier).where(AssSupplier.del_flag == 0))
    )}

    ok = 0
    errors: list[dict] = []
    codes: list[str] = []
    for idx, row in enumerate(rows[1:], start=2):
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        try:
            name = _cell(row, col["资产名称"])
            if not name:
                raise ValueError("资产名称为空")
            cat_key = _cell(row, col.get("分类"))
            if not cat_key:
                raise ValueError("分类为空")
            cat = cats.get(cat_key) or cats_by_code.get(cat_key)
            if not cat:
                raise ValueError(f"分类不存在: {cat_key}")
            org_key = _cell(row, col.get("核算公司"))
            if org_key:
                org = orgs.get(org_key)
                if not org:
                    raise ValueError(f"核算公司不存在: {org_key}")
            else:
                org = await db.get(SysOrg, user.org_id)
                if not org:
                    raise ValueError("未填写核算公司且当前用户无所属公司")
            spec = _cell(row, col.get("规格")) or None
            brand = _cell(row, col.get("品牌")) or None
            model = _cell(row, col.get("型号")) or None
            unit = _cell(row, col.get("单位")) or "件"
            price = _parse_money(_cell(row, col.get("原值")))
            buy_date = _parse_date(_cell(row, col.get("购置日期")))
            use_user_name = _cell(row, col.get("领用人"))
            use_dept_name = _cell(row, col.get("责任部门", col.get("使用部门")))
            location_detail = _cell(row, col.get("详细位置")) or None
            high = 1 if _cell(row, col.get("高值")) in ("是", "1", "Y", "yes", "Yes") else 0
            warehouse_name = _cell(row, col.get("仓库"))
            supplier_name = _cell(row, col.get("供应商"))
            use_user_id = None
            if use_user_name:
                if use_user_name not in users:
                    raise ValueError(f"领用人不存在: {use_user_name}")
                use_user_id = users[use_user_name].id
            use_dept_id = None
            if use_dept_name:
                if use_dept_name not in depts:
                    raise ValueError(f"责任部门不存在: {use_dept_name}")
                use_dept_id = depts[use_dept_name].id
            warehouse_id = None
            if warehouse_name:
                if warehouse_name not in warehouses:
                    raise ValueError(f"仓库不存在: {warehouse_name}")
                warehouse_id = warehouses[warehouse_name].id
            supplier_id = None
            if supplier_name:
                if supplier_name not in suppliers:
                    raise ValueError(f"供应商不存在: {supplier_name}")
                supplier_id = suppliers[supplier_name].id

            code = await next_asset_code(db, org.org_code, cat.code)
            a = AssAsset(
                asset_code=code, asset_name=name, category_id=cat.id,
                spec=spec, brand=brand, model=model, unit=unit,
                org_id=org.id, location_detail=location_detail,
                use_user_id=use_user_id, use_dept_id=use_dept_id,
                warehouse_id=warehouse_id, supplier_id=supplier_id,
                status=1, is_high_value=high, is_reusable=0,
                price=price, buy_date=buy_date,
                net_value=price, accum_depreciation=Decimal(0), dep_status=0,
                qrcode=uuid.uuid4().hex, create_by=user.id,
            )
            db.add(a)
            await db.flush()
            await write_log(db, a, ACTION_STOCK_IN, biz_type="import", operator_id=user.id)
            ok += 1
            codes.append(code)
        except ValueError as e:
            errors.append({"row": idx, "msg": str(e)})

    if ok:
        await db.flush()
    return {"ok": ok, "failed": len(errors), "errors": errors[:200], "codes": codes[:200]}


# ================= 折旧按月计提（方案 6.7） =================

PermDep = Annotated[CurrentUser, Depends(require_perm("depreciation:edit"))]


class DepIn(BaseModel):
    period: str | None = None  # YYYYMM，默认当月


@router.get("/depreciations")
async def list_depreciations(
    db: DbDep, user: UserDep, params: PageParams = Depends(), period: str | None = None,
):
    """计提记录（按期间倒序）。"""
    base = (
        select(AssDepreciation, AssAsset.asset_code, AssAsset.asset_name)
        .join(AssAsset, AssAsset.id == AssDepreciation.asset_id, isouter=True)
    )
    if period:
        base = base.where(AssDepreciation.period == period)
    if user.org_ids is not None:
        if not user.org_ids:
            base = base.where(AssAsset.create_by == user.id)
        else:
            base = base.where(AssAsset.org_id.in_(user.org_ids))
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(AssDepreciation.period.desc(), AssDepreciation.id.desc())
            .offset(params.offset).limit(params.limit)
        )
    ).all()
    records = [
        {
            "id": r[0].id, "period": r[0].period,
            "asset_id": r[0].asset_id, "asset_code": r[1], "asset_name": r[2],
            "orig_value": float(r[0].orig_value or 0),
            "monthly_dep": float(r[0].monthly_dep or 0),
            "accum_dep": float(r[0].accum_dep or 0),
            "net_value": float(r[0].net_value or 0),
            "voucher_no": r[0].voucher_no, "status": r[0].status,
            "create_time": r[0].create_time,
        }
        for r in rows
    ]
    return PageData.build(total, params, records)


@router.post("/depreciations/calculate")
async def depreciation_calculate(body: DepIn, db: DbDep, user: UserDep):
    """按月计提（平均年限法），生成未结账记录并回写资产累计折旧/净值。"""
    return await dep_calculate(db, user, body.period)


@router.post("/depreciations/reverse/{period}")
async def depreciation_reverse(period: str, db: DbDep, user: UserDep):
    """反结账：冲回指定期间全部未结账记录。"""
    return await dep_reverse(db, user, period)


@router.post("/depreciations/lock/{period}")
async def depreciation_lock(period: str, db: DbDep, user: UserDep):
    """结账：指定期间全部记录置为已结账（锁定，不可再反冲）。"""
    if not (len(period) == 6 and period.isdigit()):
        raise HTTPException(400, "期间格式应为 YYYYMM")
    records = list((await db.execute(
        select(AssDepreciation).where(AssDepreciation.period == period)
    )).scalars())
    if not records:
        raise HTTPException(400, f"期间 {period} 无计提记录")
    n = 0
    for r in records:
        if r.status != 1:
            r.status = 1
            n += 1
    return {"period": period, "count": n, "total": len(records)}


@router.post("/depreciations/unlock/{period}")
async def depreciation_unlock(period: str, db: DbDep, user: UserDep, _p: PermDep):
    """反结账（解锁）：已结账记录恢复为未结账，之后可用冲回接口撤销。"""
    if not (len(period) == 6 and period.isdigit()):
        raise HTTPException(400, "期间格式应为 YYYYMM")
    records = list((await db.execute(
        select(AssDepreciation).where(AssDepreciation.period == period, AssDepreciation.status == 1)
    )).scalars())
    if not records:
        raise HTTPException(400, f"期间 {period} 无已结账记录")
    for r in records:
        r.status = 0
    return {"period": period, "count": len(records)}
