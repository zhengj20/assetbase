"""依赖注入：当前用户 / 权限校验 / 数据范围。"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.sys import SysMenu, SysOrg, SysRole, SysRoleMenu, SysUser, SysUserRole

bearer_scheme = HTTPBearer(auto_error=False)

# scope="function"：session 在接口函数返回后立即提交（先于响应发送），
# 保证客户端收到响应时写入已可见，杜绝「写后立读 404」竞态。
DbDep = Annotated[AsyncSession, Depends(get_db, scope="function")]


class CurrentUser:
    def __init__(
        self,
        user: SysUser,
        roles: list[SysRole],
        perms: set[str],
        org_ids: list[int] | None,  # None = 全部数据
    ):
        self.id = user.id
        self.username = user.username
        self.real_name = user.real_name
        self.org_id = user.org_id
        self.user = user
        self.roles = roles
        self.perms = perms
        self.org_ids = org_ids
        self.is_admin = any(r.role_code == "admin" for r in roles)

    def has_perm(self, code: str) -> bool:
        return "*" in self.perms or code in self.perms


async def _collect_org_ids(db: AsyncSession, user: SysUser, scope: int) -> list[int] | None:
    """数据权限范围（方案 1.2：五档）。返回 None 表示不过滤（全部数据）。"""
    if scope == 1:
        return None
    if scope == 5:
        return []

    # 找到用户所属的「公司」节点：从部门/点位向上溯到最近的公司级组织(org_type<=3)
    node = await db.get(SysOrg, user.org_id)
    company_id = user.org_id
    while node and node.org_type > 3:
        if not node.parent_id:
            break
        node = await db.get(SysOrg, node.parent_id)
        if node:
            company_id = node.id

    if scope == 2:  # 本公司及下级
        ids = [company_id]
        frontier = [company_id]
        while frontier:
            rows = await db.scalars(
                select(SysOrg.id).where(SysOrg.parent_id.in_(frontier))
            )
            frontier = list(rows)
            ids.extend(frontier)
        return ids
    if scope == 3:  # 本公司
        return [company_id]
    if scope == 4:  # 本部门（含下级部门）
        ids = [user.org_id]
        frontier = [user.org_id]
        while frontier:
            rows = await db.scalars(
                select(SysOrg.id).where(SysOrg.parent_id.in_(frontier))
            )
            frontier = list(rows)
            ids.extend(frontier)
        return ids
    return []


async def get_current_user(
    request: Request,
    db: DbDep,
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    # EventSource 无法携带 Authorization 头，SSE 端点允许 ?token= 回退
    token: str | None = cred.credentials if cred is not None else None
    if token is None:
        token = request.query_params.get("token") or None
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效")
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效凭证")

    user = await db.get(SysUser, user_id)
    if not user or user.del_flag == 1:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    if user.status != 1:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")

    roles = list(
        await db.scalars(
            select(SysRole)
            .join(SysUserRole, SysUserRole.role_id == SysRole.id)
            .where(SysUserRole.user_id == user.id, SysRole.status == 1)
        )
    )
    if not roles:
        roles = []

    # 权限集合：角色 → 菜单 perm_code；admin 拥有全部
    role_ids = [r.id for r in roles]
    if any(r.role_code == "admin" for r in roles):
        perms: set[str] = {"*"}
    elif role_ids:
        rows = await db.scalars(
            select(SysMenu.perm_code)
            .join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id)
            .where(SysRoleMenu.role_id.in_(role_ids), SysMenu.status == 1)
        )
        perms = {p for p in rows if p}
    else:
        perms = set()

    # 数据范围取用户多角色中最宽的一档
    best_scope = min((r.data_scope for r in roles), default=5)
    org_ids = await _collect_org_ids(db, user, best_scope)

    cu = CurrentUser(user, roles, perms, org_ids)
    request.state.current_user = cu
    return cu


UserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_perm(code: str):
    """按钮/接口级权限校验依赖。"""

    async def _check(user: UserDep) -> CurrentUser:
        if not user.has_perm(code):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"无操作权限: {code}")
        return user

    return _check
