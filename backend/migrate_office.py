"""办公地点功能迁移（幂等，可重复执行）。

针对已有数据的环境：init_db.py 的种子仅在空库时写入，
本脚本补齐 ass_office 表、ass_asset.office_id 字段、"办公地点"菜单与角色授权。

用法（backend 目录下）：
    uv run python migrate_office.py
"""
import asyncio

from sqlalchemy import func, inspect, select, text

from app.db.session import AsyncSessionLocal, engine
from app.models import AssOffice
from app.models.sys import SysMenu, SysRoleMenu


async def main():
    # 1) ass_office 表（create_all 只建不 ALTER）
    async with engine.begin() as conn:
        await conn.run_sync(AssOffice.metadata.create_all)
    print("ass_office 表就绪")

    # 2) ass_asset.office_id 字段
    async with engine.connect() as conn:
        def _cols(sync_conn):
            return {c["name"] for c in inspect(sync_conn).get_columns("ass_asset")}

        cols = await conn.run_sync(_cols)
    if "office_id" not in cols:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "ALTER TABLE ass_asset "
                    "ADD COLUMN office_id BIGINT NULL COMMENT '办公地点', "
                    "ADD INDEX idx_asset_office (office_id)"
                )
            )
        print("已添加 ass_asset.office_id")
    else:
        print("ass_asset.office_id 已存在，跳过")

    # 3) "办公地点"菜单 + 角色授权（授权给已有"基础档案"目录的角色）
    async with AsyncSessionLocal() as db:
        exists = await db.scalar(
            select(SysMenu.id).where(SysMenu.path == "/archive/office", SysMenu.del_flag == 0)
        )
        if not exists:
            parent = await db.scalar(
                select(SysMenu.id).where(SysMenu.path == "/archive", SysMenu.del_flag == 0)
            )
            m = SysMenu(
                menu_name="办公地点", parent_id=parent or 0, menu_type=2,
                perm_code="office:list", path="/archive/office", icon="Location",
                sort=5, create_by=1,
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
            print(f"已创建\"办公地点\"菜单（授权角色：{role_ids}）")
        else:
            print("\"办公地点\"菜单已存在，跳过")

        # 4) 办公地点演示数据（仅空表时写入）
        n = await db.scalar(select(func.count()).select_from(AssOffice))
        if not n:
            for name, org_id, building, floor, address in [
                ("集团总部办公区", 1, "A座", "15F", "南京·河西总部大厦"),
                ("华东区域办公区", 2, "B座", "8F", "南京·江东中路200号"),
                ("云锦项目部办公室", 3, "售楼处", "2F", "云锦雅苑项目现场"),
            ]:
                db.add(AssOffice(office_name=name, org_id=org_id,
                                building=building, floor=floor, address=address,
                                create_by=1))
            await db.commit()
            print("已写入 3 条办公地点演示数据")
        else:
            print(f"办公地点已有数据（{n} 条），跳过")

    print("迁移完成")


if __name__ == "__main__":
    asyncio.run(main())
