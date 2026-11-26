"""仓库库存菜单迁移（幂等，可重复执行）。

针对已有数据的环境：init_db.py 的种子仅在空库时写入，
本脚本为"资产管理"目录补齐"仓库库存"菜单并授权给已有该目录的角色。

用法（backend 目录下）：
    uv run python migrate_whstock_menu.py
"""
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.sys import SysMenu, SysRoleMenu


async def main():
    async with AsyncSessionLocal() as db:
        exists = await db.scalar(
            select(SysMenu.id).where(SysMenu.path == "/asset/warehouse-stock", SysMenu.del_flag == 0)
        )
        if exists:
            print("「仓库库存」菜单已存在，跳过")
            return
        parent = await db.scalar(
            select(SysMenu.id).where(SysMenu.path == "/asset", SysMenu.del_flag == 0)
        )
        m = SysMenu(
            menu_name="仓库库存", parent_id=parent or 0, menu_type=2,
            perm_code="warehouse_stock:list", path="/asset/warehouse-stock", icon="Goods",
            sort=6, create_by=1,
        )
        db.add(m)
        await db.flush()
        role_ids = (
            (await db.scalars(
                select(SysRoleMenu.role_id).where(SysRoleMenu.menu_id == parent)
            )).all()
            if parent
            else []
        )
        for rid in role_ids:
            db.add(SysRoleMenu(role_id=rid, menu_id=m.id))
        await db.commit()
        print(f"已创建「仓库库存」菜单（授权角色：{role_ids}）")


if __name__ == "__main__":
    asyncio.run(main())
