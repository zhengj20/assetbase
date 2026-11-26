"""借用流程迁移（幂等，可重复执行）：借用表 + 菜单 + 资产状态字典。

用法（backend 目录下）：
    uv run python migrate_borrow.py
"""
import asyncio

from sqlalchemy import func, select

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.sys import SysDictData, SysDictType, SysMenu, SysRoleMenu

MENUS = [
    # menu_name, parent_path, perm, path, icon, sort
    ("借用管理", "/doc", "borrow:list", "/doc/borrow", "Switch", 5),
    ("新增借用", "/doc/borrow", "borrow:create", None, None, 1),
    ("资产归还", "/doc/borrow", "borrow:return", None, None, 2),
]


async def main():
    # 建表（create_all 只补缺失表，不改动已有表）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("借用相关表已创建/确认")

    async with AsyncSessionLocal() as db:
        for name, parent_path, perm, path, icon, sort in MENUS:
            exists = await db.scalar(
                select(SysMenu.id).where(SysMenu.perm_code == perm, SysMenu.del_flag == 0)
            )
            if exists:
                print(f"「{name}」已存在，跳过")
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
                menu_name=name, parent_id=parent_id,
                menu_type=3 if path is None else 2,
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
                role_ids = [rid for rid in range(2, 7)]
            for rid in role_ids:
                db.add(SysRoleMenu(role_id=rid, menu_id=m.id))
            print(f"已创建「{name}」（授权角色：{role_ids}）")

        dict_id = await db.scalar(
            select(SysDictType.id).where(SysDictType.dict_code == "asset_status", SysDictType.del_flag == 0)
        )
        if dict_id:
            has = await db.scalar(
                select(SysDictData.id).where(
                    SysDictData.dict_id == dict_id, SysDictData.label == "借用中",
                    SysDictData.del_flag == 0,
                )
            )
            if not has:
                cur_max = (
                    await db.scalar(
                        select(func.max(SysDictData.value)).where(SysDictData.dict_id == dict_id)
                    )
                    or 0
                )
                nxt = int(cur_max) + 1
                db.add(SysDictData(dict_id=dict_id, label="借用中", value=str(nxt), sort=nxt))
                print("asset_status 字典已补充「借用中」")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
