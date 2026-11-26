"""系统管理 API：组织/用户/角色/菜单/字典/操作日志。"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select

from app.core.deps import CurrentUser, DbDep, UserDep, require_perm
from app.core.pagination import PageData, PageParams
from app.core.security import hash_password
from app.models.asset import AssAsset
from app.models.sys import (
    SysDictData,
    SysDictType,
    SysMenu,
    SysOperationLog,
    SysOrg,
    SysRole,
    SysRoleMenu,
    SysUser,
    SysUserRole,
)
from app.schemas.sys import (
    DictDataIn,
    DictDataOut,
    DictTypeIn,
    DictTypeOut,
    LogOut,
    MenuIn,
    MenuOut,
    OrgIn,
    OrgOut,
    RoleIn,
    RoleOut,
    UserIn,
    UserOut,
)
from app.services import message_service as msg

router = APIRouter(tags=["系统管理"])


# ============ 组织架构 ============
@router.get("/orgs")
async def list_orgs(db: DbDep, user: UserDep):
    """扁平列表（含 parent_id，前端自行建树）：全应用组织下拉均按此口径消费。"""
    if user.org_ids is not None:
        nodes = list(
            await db.scalars(
                select(SysOrg).where(SysOrg.del_flag == 0, SysOrg.id.in_(user.org_ids))
            )
        )
    else:
        nodes = list(await db.scalars(select(SysOrg).where(SysOrg.del_flag == 0)))
    return [OrgOut.model_validate(n).model_dump() for n in nodes]


@router.post("/orgs", response_model=OrgOut)
async def create_org(body: OrgIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:org"))]):
    org = SysOrg(**body.model_dump(), create_by=user.id)
    db.add(org)
    await db.flush()
    return org


@router.put("/orgs/{org_id}", response_model=OrgOut)
async def update_org(org_id: int, body: OrgIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:org"))]):
    org = await db.get(SysOrg, org_id)
    if not org or org.del_flag == 1:
        raise HTTPException(404, "组织不存在")
    for k, v in body.model_dump().items():
        setattr(org, k, v)
    org.update_by = user.id
    org.version += 1
    return org


@router.delete("/orgs/{org_id}")
async def delete_org(org_id: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:org"))]):
    org = await db.get(SysOrg, org_id)
    if not org or org.del_flag == 1:
        raise HTTPException(404, "组织不存在")
    children = await db.scalar(
        select(func.count()).select_from(SysOrg).where(
            SysOrg.parent_id == org_id, SysOrg.del_flag == 0
        )
    )
    if children:
        raise HTTPException(400, "存在下级组织，无法删除")
    # 方案 1.1：组织注销前校验名下资产是否已清空
    assets = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            AssAsset.org_id == org_id, AssAsset.del_flag == 0,
            AssAsset.status.notin_([5, 6]),
        )
    )
    if assets:
        raise HTTPException(400, f"该组织名下仍有 {assets} 项资产未清理，无法注销")
    org.del_flag = 1
    org.update_by = user.id
    return {"ok": True}


# ============ 用户管理 ============
@router.get("/users", response_model=PageData[UserOut])
async def list_users(
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("sys:user"))],
    params: PageParams = Depends(),
    keyword: str | None = None,
    org_id: int | None = None,
    status: int | None = None,
):
    conds = [SysUser.del_flag == 0]
    if keyword:
        conds.append(
            or_(SysUser.username.contains(keyword), SysUser.real_name.contains(keyword))
        )
    if org_id:
        conds.append(SysUser.org_id == org_id)
    if status is not None:
        conds.append(SysUser.status == status)

    total = await db.scalar(
        select(func.count()).select_from(SysUser).where(*conds)
    )
    rows = list(
        await db.scalars(
            select(SysUser)
            .where(*conds)
            .order_by(SysUser.id)
            .offset(params.offset)
            .limit(params.limit)
        )
    )
    user_ids = [u.id for u in rows]
    roles_by_user: dict[int, list[int]] = {}
    if user_ids:
        ur_rows = await db.execute(
            select(SysUserRole.user_id, SysUserRole.role_id).where(
                SysUserRole.user_id.in_(user_ids)
            )
        )
        for uid, rid in ur_rows:
            roles_by_user.setdefault(uid, []).append(rid)
    return PageData.build(
        total,
        params,
        [
            UserOut.model_validate(u).model_copy(
                update={"role_ids": roles_by_user.get(u.id, [])}
            )
            for u in rows
        ],
    )


@router.post("/users", response_model=UserOut)
async def create_user(body: UserIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:user"))]):
    exists = await db.scalar(
        select(func.count()).select_from(SysUser).where(SysUser.username == body.username)
    )
    if exists:
        raise HTTPException(400, "账号已存在")
    u = SysUser(
        username=body.username,
        password=hash_password(body.password or "123456"),
        real_name=body.real_name,
        org_id=body.org_id,
        phone=body.phone,
        email=body.email,
        status=body.status,
        create_by=user.id,
    )
    db.add(u)
    await db.flush()
    for rid in body.role_ids:
        db.add(SysUserRole(user_id=u.id, role_id=rid))
    return UserOut.model_validate(u)


async def _role_user_ids(db, role_code: str) -> list[int]:
    return list(
        await db.scalars(
            select(SysUser.id)
            .join(SysUserRole, SysUserRole.user_id == SysUser.id)
            .join(SysRole, SysRole.id == SysUserRole.role_id)
            .where(SysRole.role_code == role_code, SysUser.status == 1, SysUser.del_flag == 0)
            .order_by(SysUser.id)
        )
    )


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UserIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:user"))]):
    u = await db.get(SysUser, user_id)
    if not u or u.del_flag == 1:
        raise HTTPException(404, "用户不存在")
    was_active = u.status
    u.real_name = body.real_name
    u.org_id = body.org_id
    u.phone = body.phone
    u.email = body.email
    u.status = body.status
    u.update_by = user.id
    u.version += 1
    if body.password:
        u.password = hash_password(body.password)
    await db.execute(
        SysUserRole.__table__.delete().where(SysUserRole.user_id == user_id)
    )
    for rid in body.role_ids:
        db.add(SysUserRole(user_id=user_id, role_id=rid))

    # 人事离职联动（方案模块7）：账号停用视为离职，名下领用中资产发归还提醒
    if was_active == 1 and body.status == 0:
        held = [
            (r[0], r[1])
            for r in (
                await db.execute(
                    select(AssAsset.asset_code, AssAsset.asset_name)
                    .where(AssAsset.use_user_id == user_id, AssAsset.status == 2, AssAsset.del_flag == 0)
                    .order_by(AssAsset.asset_code)
                )
            ).all()
        ]
        if held:
            names = "、".join(f"{c}({n})" for c, n in held[:10])
            if len(held) > 10:
                names += f"…等 {len(held)} 项"
            receivers = await _role_user_ids(db, "project_asset") or await _role_user_ids(db, "admin")
            for rid in receivers:
                if rid == user_id:
                    continue
                await msg.send(
                    db, rid,
                    f"【资产归还提醒】{u.real_name or u.username} 已离职，名下仍有 {len(held)} 项领用中资产",
                    f"请安排归还或移交：{names}", 3,
                )
    return UserOut.model_validate(u)


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:user"))]):
    if user_id == user.id:
        raise HTTPException(400, "不能删除自己")
    u = await db.get(SysUser, user_id)
    if not u or u.del_flag == 1:
        raise HTTPException(404, "用户不存在")
    # 方案 P1-3：删除前冻结/校验名下资产
    assets = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            AssAsset.use_user_id == user_id, AssAsset.status == 2
        )
    )
    if assets:
        raise HTTPException(400, f"该用户名下有 {assets} 项领用中资产，需先完成归还/移交")
    pending = await db.scalar(
        select(func.count()).select_from(WfTask).where(
            WfTask.del_flag == 0, WfTask.assignee_id == user_id, WfTask.action.is_(None)
        )
    )
    if pending:
        raise HTTPException(400, f"该用户名下有 {pending} 个待审批任务，需先处理完成")
    u.del_flag = 1
    u.status = 0
    u.update_by = user.id
    return {"ok": True}


# ============ 角色管理 ============
@router.get("/roles")
async def list_roles(db: DbDep, user: UserDep):
    roles = list(
        await db.scalars(
            select(SysRole).where(SysRole.del_flag == 0).order_by(SysRole.id)
        )
    )
    return [RoleOut.model_validate(r) for r in roles]


@router.post("/roles", response_model=RoleOut)
async def create_role(body: RoleIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:role"))]):
    exists = await db.scalar(
        select(func.count()).select_from(SysRole).where(SysRole.role_code == body.role_code)
    )
    if exists:
        raise HTTPException(400, "角色编码已存在")
    r = SysRole(**body.model_dump(exclude={"menu_ids"}), create_by=user.id)
    db.add(r)
    await db.flush()
    for mid in body.menu_ids:
        db.add(SysRoleMenu(role_id=r.id, menu_id=mid))
    return RoleOut.model_validate(r)


@router.put("/roles/{role_id}", response_model=RoleOut)
async def update_role(role_id: int, body: RoleIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:role"))]):
    r = await db.get(SysRole, role_id)
    if not r or r.del_flag == 1:
        raise HTTPException(404, "角色不存在")
    for k, v in body.model_dump(exclude={"menu_ids"}).items():
        setattr(r, k, v)
    r.update_by = user.id
    r.version += 1
    await db.execute(
        SysRoleMenu.__table__.delete().where(SysRoleMenu.role_id == role_id)
    )
    for mid in body.menu_ids:
        db.add(SysRoleMenu(role_id=role_id, menu_id=mid))
    return RoleOut.model_validate(r)


@router.get("/roles/{role_id}/menu-ids")
async def role_menu_ids(role_id: int, db: DbDep, user: UserDep):
    ids = await db.scalars(
        select(SysRoleMenu.menu_id).where(SysRoleMenu.role_id == role_id)
    )
    return list(ids)


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:role"))]):
    in_use = await db.scalar(
        select(func.count()).select_from(SysUserRole).where(SysUserRole.role_id == role_id)
    )
    if in_use:
        raise HTTPException(400, "角色已分配用户，无法删除")
    r = await db.get(SysRole, role_id)
    if not r or r.del_flag == 1:
        raise HTTPException(404, "角色不存在")
    r.del_flag = 1
    r.update_by = user.id
    return {"ok": True}


# ============ 菜单管理 ============
@router.get("/menus")
async def list_menus(db: DbDep, user: UserDep):
    menus = list(
        await db.scalars(
            select(SysMenu)
            .where(SysMenu.del_flag == 0, SysMenu.status == 1)
            .order_by(SysMenu.sort)
        )
    )

    def tree(parent_id=0):
        out = []
        for m in menus:
            if m.parent_id == parent_id:
                out.append(
                    {
                        **MenuOut.model_validate(m).model_dump(),
                        "children": tree(m.id),
                    }
                )
        return out

    return tree()


@router.post("/menus", response_model=MenuOut)
async def create_menu(body: MenuIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:menu"))]):
    m = SysMenu(**body.model_dump(), create_by=user.id)
    db.add(m)
    await db.flush()
    return m


@router.put("/menus/{menu_id}", response_model=MenuOut)
async def update_menu(menu_id: int, body: MenuIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:menu"))]):
    m = await db.get(SysMenu, menu_id)
    if not m or m.del_flag == 1:
        raise HTTPException(404, "菜单不存在")
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    m.update_by = user.id
    m.version += 1
    return m


@router.delete("/menus/{menu_id}")
async def delete_menu(menu_id: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:menu"))]):
    m = await db.get(SysMenu, menu_id)
    if not m or m.del_flag == 1:
        raise HTTPException(404, "菜单不存在")
    children = await db.scalar(
        select(func.count()).select_from(SysMenu).where(
            SysMenu.parent_id == menu_id, SysMenu.del_flag == 0
        )
    )
    if children:
        raise HTTPException(400, "存在下级菜单，无法删除")
    m.del_flag = 1
    m.update_by = user.id
    return {"ok": True}


# ============ 字典管理 ============
@router.get("/dict-types")
async def list_dict_types(db: DbDep, user: UserDep):
    rows = list(
        await db.scalars(
            select(SysDictType).where(SysDictType.del_flag == 0).order_by(SysDictType.id)
        )
    )
    return [DictTypeOut.model_validate(r) for r in rows]


@router.post("/dict-types", response_model=DictTypeOut)
async def create_dict_type(body: DictTypeIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:dict"))]):
    exists = await db.scalar(
        select(func.count()).select_from(SysDictType).where(
            SysDictType.dict_code == body.dict_code
        )
    )
    if exists:
        raise HTTPException(400, "字典编码已存在")
    t = SysDictType(**body.model_dump(), create_by=user.id)
    db.add(t)
    await db.flush()
    return t


@router.put("/dict-types/{type_id}", response_model=DictTypeOut)
async def update_dict_type(type_id: int, body: DictTypeIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:dict"))]):
    t = await db.get(SysDictType, type_id)
    if not t or t.del_flag == 1:
        raise HTTPException(404, "字典类型不存在")
    t.dict_name = body.dict_name
    t.status = body.status
    t.update_by = user.id
    t.version += 1
    return t


@router.get("/dicts/{dict_code}")
async def get_dict(db: DbDep, user: UserDep, dict_code: str):
    """按编码取字典数据（前端下拉框自动渲染）。"""
    t = (
        await db.execute(
            select(SysDictType).where(SysDictType.dict_code == dict_code)
        )
    ).scalar_one_or_none()
    if not t or t.status != 1:
        return []
    rows = await db.scalars(
        select(SysDictData)
        .where(SysDictData.dict_id == t.id, SysDictData.del_flag == 0)
        .order_by(SysDictData.sort)
    )
    return [DictDataOut.model_validate(r) for r in rows]


@router.get("/dict-datas")
async def list_dict_datas(db: DbDep, user: UserDep, dict_id: int):
    rows = await db.scalars(
        select(SysDictData)
        .where(SysDictData.dict_id == dict_id, SysDictData.del_flag == 0)
        .order_by(SysDictData.sort)
    )
    return [DictDataOut.model_validate(r) for r in rows]


@router.post("/dict-datas", response_model=DictDataOut)
async def create_dict_data(body: DictDataIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:dict"))]):
    d = SysDictData(**body.model_dump(), create_by=user.id)
    db.add(d)
    await db.flush()
    return d


@router.put("/dict-datas/{data_id}", response_model=DictDataOut)
async def update_dict_data(data_id: int, body: DictDataIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:dict"))]):
    d = await db.get(SysDictData, data_id)
    if not d or d.del_flag == 1:
        raise HTTPException(404, "字典数据不存在")
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    d.update_by = user.id
    d.version += 1
    return d


@router.delete("/dict-datas/{data_id}")
async def delete_dict_data(data_id: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("sys:dict"))]):
    d = await db.get(SysDictData, data_id)
    if not d or d.del_flag == 1:
        raise HTTPException(404, "字典数据不存在")
    d.del_flag = 1
    d.update_by = user.id
    return {"ok": True}


# ============ 操作日志 ============
@router.get("/logs", response_model=PageData[LogOut])
async def list_logs(
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("sys:log"))],
    params: PageParams = Depends(),
    module: str | None = None,
    user_id: int | None = None,
):
    conds = []
    if module:
        conds.append(SysOperationLog.module == module)
    if user_id:
        conds.append(SysOperationLog.user_id == user_id)
    q = select(func.count()).select_from(SysOperationLog)
    total = await db.scalar(q.where(*conds) if conds else q)
    rows = await db.scalars(
        select(SysOperationLog)
        .where(*conds)
        .order_by(SysOperationLog.log_id.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    return PageData.build(total, params, [LogOut.model_validate(r) for r in rows])
