"""P0 权限迁移（幂等，可重复执行）：
1. 新增 5 个按钮级权限菜单：asset:repair / depreciation:edit / group:edit / purchase:delete / check:edit
   —— 授权给所有已拥有父菜单的角色（与 init_db 的演示授权口径一致）
2. ass_asset 表补 pre_repair_status 列（维修前状态，维修完成时恢复）

用法（backend 目录下）：
    uv run python migrate_p0_perms.py
"""
import asyncio

from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal
from app.models.sys import SysMenu, SysRoleMenu

# 菜单名, 父菜单 path, 权限码, 排序
PERM_MIGRATIONS = [
    ("维修登记", "/asset/list", "asset:repair", 5),
    ("折旧计算", "/asset/depreciation", "depreciation:edit", 1),
    ("组合包调整", "/asset/group", "group:edit", 1),
    ("删除采购申请", "/doc/purchase", "purchase:delete", 2),
    ("盘点处理", "/check/task", "check:edit", 2),
]


async def main():
    async with AsyncSessionLocal() as db:
        # ---- 1. 按钮级权限菜单 ----
        for name, parent_path, perm, sort in PERM_MIGRATIONS:
            exists = await db.scalar(
                select(SysMenu.id).where(SysMenu.perm_code == perm, SysMenu.del_flag == 0)
            )
            if exists:
                print(f"「{name}」（{perm}）已存在，跳过")
                continue
            parent = await db.scalar(
                select(SysMenu).where(SysMenu.path == parent_path, SysMenu.del_flag == 0)
            )
            if not parent:
                print(f"!! 父菜单 {parent_path} 不存在，跳过「{name}」")
                continue
            m = SysMenu(
                menu_name=name, parent_id=parent.id, menu_type=3,
                perm_code=perm, path=None, icon=None, sort=sort, create_by=1,
            )
            db.add(m)
            await db.flush()
            role_ids = (
                await db.scalars(
                    select(SysRoleMenu.role_id).where(SysRoleMenu.menu_id == parent.id)
                )
            ).all()
            for rid in role_ids:
                db.add(SysRoleMenu(role_id=rid, menu_id=m.id))
            print(f"已创建「{name}」（{perm}，父菜单={parent.menu_name}，授权角色：{role_ids}）")

        # ---- 2. ass_asset.pre_repair_status 列 ----
        cols = await db.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ass_asset' "
            "AND COLUMN_NAME = 'pre_repair_status'"
        ))
        if cols.first():
            print("ass_asset.pre_repair_status 列已存在，跳过")
        else:
            await db.execute(text(
                "ALTER TABLE ass_asset ADD COLUMN pre_repair_status SMALLINT NULL "
                "COMMENT '维修前状态(维修完成时恢复,维修中为原状态)'"
            ))
            print("已添加 ass_asset.pre_repair_status 列")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
