"""菜单调整迁移（幂等，可重复执行）：「易耗品」作为顶级菜单，排在「盘点管理」之后（平级）。

用法（backend 目录下）：
    uv run python migrate_con_menu_move.py
"""
import asyncio

from sqlalchemy import or_, select, update

from app.db.session import AsyncSessionLocal
from app.models.sys import SysMenu


async def place_con_menu(db) -> None:
    """把「易耗品」放到「盘点管理」之后的顶级菜单位置（幂等）。"""
    con_dir = await db.scalar(
        select(SysMenu).where(SysMenu.path == "/con", SysMenu.menu_type == 1, SysMenu.del_flag == 0)
    )
    check_dir = await db.scalar(
        select(SysMenu).where(SysMenu.path == "/check", SysMenu.menu_type == 1, SysMenu.del_flag == 0)
    )
    if not con_dir or not check_dir:
        print("未找到「易耗品」或「盘点管理」目录菜单，跳过")
        return

    target_sort = check_dir.sort + 1
    if con_dir.parent_id in (0, None) and con_dir.sort == target_sort:
        print("「易耗品」已在「盘点管理」之后的顶级位置，跳过")
        return

    con_dir.parent_id = 0
    # 把「盘点管理」之后的其他顶级菜单顺延一位，腾出 target_sort
    await db.execute(
        update(SysMenu)
        .where(
            or_(SysMenu.parent_id == 0, SysMenu.parent_id.is_(None)),
            SysMenu.id.notin_([con_dir.id, check_dir.id]),
            SysMenu.sort > check_dir.sort,
            SysMenu.del_flag == 0,
        )
        .values(sort=SysMenu.sort + 1)
    )
    con_dir.sort = target_sort
    print(f"已将「易耗品」(id={con_dir.id}) 设为顶级菜单，sort={target_sort}（紧随「盘点管理」sort={check_dir.sort}）")


async def main():
    async with AsyncSessionLocal() as db:
        await place_con_menu(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
