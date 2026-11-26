"""菜单重命名迁移（幂等，可重复执行）：审批中心 → 流程管理。

用法（backend 目录下）：
    uv run python migrate_menu_rename.py
"""
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.sys import SysMenu


async def main():
    async with AsyncSessionLocal() as db:
        menu = await db.scalar(
            select(SysMenu).where(SysMenu.path == "/approval", SysMenu.menu_name == "审批中心", SysMenu.del_flag == 0)
        )
        if not menu:
            print("菜单「审批中心」不存在或已改名，跳过")
            return
        menu.menu_name = "流程管理"
        await db.commit()
        print("已将「审批中心」重命名为「流程管理」")


if __name__ == "__main__":
    asyncio.run(main())
