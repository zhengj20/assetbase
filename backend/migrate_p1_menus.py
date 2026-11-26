"""P1 菜单迁移（幂等，可重复执行）：消息中心 + 组合包。

用法（backend 目录下）：
    uv run python migrate_p1_menus.py
"""
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.sys import SysMenu, SysRoleMenu

MIGRATIONS = [
    # menu_name, parent_path, perm, path, icon, sort
    ("消息中心", None, "message:list", "/messages", "Bell", 8),
    ("组合包", "/asset", "group:list", "/asset/group", "Box", 3),
]


async def main():
    async with AsyncSessionLocal() as db:
        for name, parent_path, perm, path, icon, sort in MIGRATIONS:
            exists = await db.scalar(
                select(SysMenu.id).where(SysMenu.path == path, SysMenu.del_flag == 0)
            )
            if exists:
                print(f"「{name}」菜单已存在，跳过")
                continue
            parent_id = 0
            if parent_path:
                parent_id = (
                    await db.scalar(
                        select(SysMenu.id).where(SysMenu.path == parent_path, SysMenu.del_flag == 0)
                    )
                    or 0
                )
            m = SysMenu(
                menu_name=name, parent_id=parent_id, menu_type=2,
                perm_code=perm, path=path, icon=icon, sort=sort, create_by=1,
            )
            db.add(m)
            await db.flush()
            if parent_id:
                role_ids = (
                    (await db.scalars(
                        select(SysRoleMenu.role_id).where(SysRoleMenu.menu_id == parent_id)
                    )).all()
                )
            else:
                # 顶级菜单：授权给所有非 admin 角色
                role_ids = [rid for rid in range(2, 7)]
            for rid in role_ids:
                db.add(SysRoleMenu(role_id=rid, menu_id=m.id))
            print(f"已创建「{name}」菜单（授权角色：{role_ids}）")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
