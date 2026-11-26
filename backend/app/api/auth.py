"""认证 API：登录（含失败锁定）/ 当前用户 / 刷新令牌 / 修改密码。"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import DbDep, UserDep
from app.core.security import (
    check_login_lock,
    clear_login_fail,
    create_access_token,
    create_refresh_token,
    hash_password,
    record_login_fail,
    verify_password,
    verify_refresh_token,
)
from app.models.sys import SysMenu, SysRole, SysRoleMenu, SysUser, SysUserRole
from app.schemas.common import LoginIn, LoginOut, RefreshIn, UserInfo
from app.schemas.sys import MenuOut

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn, db: DbDep):
    lock = await check_login_lock(body.username)
    if lock > 0:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"账号已锁定，请 {lock} 秒后重试",
        )

    user = (
        await db.execute(
            select(SysUser).where(SysUser.username == body.username, SysUser.del_flag == 0)
        )
    ).scalar_one_or_none()

    if not user or not verify_password(body.password, user.password):
        await record_login_fail(body.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")

    if user.status != 1:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")

    await clear_login_fail(body.username)

    roles = list(
        await db.scalars(
            select(SysRole)
            .join(SysUserRole, SysUserRole.role_id == SysRole.id)
            .where(SysUserRole.user_id == user.id, SysRole.status == 1)
        )
    )
    if any(r.role_code == "admin" for r in roles):
        perms = ["*"]
    else:
        role_ids = [r.id for r in roles]
        rows = await db.scalars(
            select(SysMenu.perm_code)
            .join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id)
            .where(SysRoleMenu.role_id.in_(role_ids), SysMenu.status == 1)
        )
        perms = sorted({p for p in rows if p})

    token = create_access_token(user.id, user.username)
    return LoginOut(
        token=token,
        refresh_token=create_refresh_token(user.id, user.username),
        user=UserInfo.model_validate(user),
        perms=perms,
    )


@router.post("/refresh")
async def refresh(body: RefreshIn, db: DbDep):
    """用刷新令牌换新访问令牌（7 天有效），前端 access 过期后自动调用。"""
    payload = verify_refresh_token(body.refresh_token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "刷新令牌无效或已过期，请重新登录")
    user = await db.get(SysUser, int(payload["sub"]))
    if not user or user.del_flag == 1 or user.status != 1:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不存在或已停用")
    return {
        "token": create_access_token(user.id, user.username),
        "refresh_token": create_refresh_token(user.id, user.username),
    }


@router.get("/me")
async def me(user: UserDep):
    return {
        "user": UserInfo.model_validate(user.user),
        "perms": sorted(user.perms),
        "roles": [
            {"id": r.id, "role_name": r.role_name, "role_code": r.role_code}
            for r in user.roles
        ],
    }


@router.get("/menus")
async def my_menus(user: UserDep, db: DbDep):
    """当前用户可见菜单树（前端侧边栏）。"""
    if user.is_admin:
        menus = list(
            await db.scalars(
                select(SysMenu)
                .where(SysMenu.status == 1, SysMenu.menu_type.in_([1, 2]))
                .order_by(SysMenu.sort)
            )
        )
    else:
        menus = list(
            await db.scalars(
                select(SysMenu)
                .join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id)
                .join(SysUserRole, SysUserRole.role_id == SysRoleMenu.role_id)
                .where(
                    SysUserRole.user_id == user.id,
                    SysMenu.status == 1,
                    SysMenu.menu_type.in_([1, 2]),
                )
                .order_by(SysMenu.sort)
            )
        )
    # 多角色用户 JOIN 会产出重复菜单行，按 id 去重（保留顺序），避免前端重复 key 渲染异常
    seen: set[int] = set()
    unique = []
    for m in menus:
        if m.id not in seen:
            seen.add(m.id)
            unique.append(m)
    return [MenuOut.model_validate(m) for m in unique]


class ChangePasswordIn(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=50)


@router.put("/password")
async def change_password(body: ChangePasswordIn, user: UserDep, db: DbDep):
    """修改当前用户密码。"""
    db_user = await db.get(SysUser, user.id)
    if not db_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if not verify_password(body.old_password, db_user.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码错误")
    db_user.password = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
