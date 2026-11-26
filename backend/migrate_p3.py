"""P3 迁移（幂等，可重复执行）：审批中心菜单调整。

- 「我的审批」提升为顶级菜单（驾驶舱下方）
- 新增顶级目录「审批中心」：「流程配置」移入 + 新增「流程监控」
- 顶级顺序：驾驶舱1 我的审批2 资产管理3 业务单据4 审批中心5 盘点管理6 基础档案7 系统管理9
- 非 admin 角色（2-6）授予新菜单

用法（backend 目录下）：
    uv run python migrate_p3.py
"""
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.sys import SysMenu, SysRole, SysRoleMenu


async def get_menu(db, path: str) -> SysMenu | None:
    rows = list(await db.scalars(select(SysMenu).where(SysMenu.path == path, SysMenu.del_flag == 0)))
    return rows[0] if rows else None


async def set_sort(db, path: str, parent_id: int | None, sort: int) -> None:
    m = await get_menu(db, path)
    if not m:
        print(f"跳过：菜单 {path} 不存在")
        return
    if parent_id is not None and m.parent_id != parent_id:
        m.parent_id = parent_id
        print(f"「{m.menu_name}」parent_id -> {parent_id}")
    if m.sort != sort:
        m.sort = sort
        print(f"「{m.menu_name}」sort -> {sort}")


async def main():
    async with AsyncSessionLocal() as db:
        # 1) 我的审批 → 顶级（驾驶舱下方）
        await set_sort(db, "/doc/approval", 0, 2)
        # 2) 顶级顺序让位
        await set_sort(db, "/asset", 0, 3)
        await set_sort(db, "/doc", 0, 4)
        await set_sort(db, "/check", 0, 6)
        await set_sort(db, "/archive", 0, 7)

        # 3) 审批中心目录
        center = await get_menu(db, "/approval")
        if center:
            print("「审批中心」目录已存在，跳过创建")
        else:
            center = SysMenu(
                menu_name="审批中心", parent_id=0, menu_type=1,
                perm_code=None, path="/approval", icon="Monitor",
                sort=5, status=1, create_by=1,
            )
            db.add(center)
            await db.flush()
            print("已创建「审批中心」目录")

        # 4) 流程配置移入审批中心
        await set_sort(db, "/doc/flow", center.id, 1)

        # 5) 流程监控（新）
        monitor = await get_menu(db, "/approval/monitor")
        if monitor:
            print("「流程监控」菜单已存在，跳过创建")
        else:
            monitor = SysMenu(
                menu_name="流程监控", parent_id=center.id, menu_type=2,
                perm_code="approval:monitor", path="/approval/monitor",
                icon="DataLine", sort=2, status=1, create_by=1,
            )
            db.add(monitor)
            await db.flush()
            print("已创建「流程监控」菜单")

        # 6) 非 admin 角色授权（与 init_db 全量授权模式一致）
        role_ids = list(
            await db.scalars(select(SysRole.id).where(SysRole.id >= 2, SysRole.del_flag == 0))
        )
        granted = []
        for rid in role_ids:
            for mid in (center.id, monitor.id):
                exists = await db.scalar(
                    select(SysRoleMenu).where(SysRoleMenu.role_id == rid, SysRoleMenu.menu_id == mid)
                )
                if not exists:
                    db.add(SysRoleMenu(role_id=rid, menu_id=mid))
                    granted.append((rid, mid))
        print(f"已授权角色-菜单：{granted or '（均已存在）'}")
        await db.commit()
        print("P3 菜单迁移完成")


if __name__ == "__main__":
    asyncio.run(main())
