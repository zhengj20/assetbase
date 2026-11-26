"""工作台菜单迁移（幂等，可重复执行）：插入「工作台」顶级菜单，排序 0（最前）。

用法（backend 目录下）：
    uv run python migrate_workbench_menu.py
"""
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.sys import SysMenu, SysRole, SysRoleMenu


async def main():
    async with AsyncSessionLocal() as db:
        exists = await db.scalar(
            select(SysMenu.id).where(SysMenu.path == "/workbench", SysMenu.del_flag == 0)
        )
        if exists:
            print("「工作台」菜单已存在，跳过")
            return

        m = SysMenu(
            menu_name="工作台", parent_id=0, menu_type=2,
            perm_code=None, path="/workbench", icon="HomeFilled",
            sort=0, status=1, create_by=1,
        )
        db.add(m)
        await db.flush()

        all_roles = (await db.scalars(select(SysRole).where(SysRole.del_flag == 0))).all()
        for r in all_roles:
            db.add(SysRoleMenu(role_id=r.id, menu_id=m.id))

        await db.commit()
        print(f"已创建「工作台」菜单（sort=0），授权角色：{[r.id for r in all_roles]}")


if __name__ == "__main__":
    asyncio.run(main())
