"""P2 迁移（幂等，可重复执行）：种子流程定义 + 流程配置菜单。

用法（backend 目录下）：
    uv run python migrate_p2.py
"""
import asyncio
import json

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.check import WfDefinition
from app.models.sys import SysMenu, SysRoleMenu
from app.services.workflow_service import DEFAULT_FLOWS

FLOW_LABELS = {
    "purchase": "采购申请（≤5万）",
    "purchase_high": "采购申请（>5万）",
    "stock_in": "资产入库",
    "stock_out": "领用出库",
    "transfer": "资产调拨",
    "scrap": "报废处置",
}


async def main():
    async with AsyncSessionLocal() as db:
        # 1) 流程定义种子（仅当该 biz_type 无任何定义时写入）
        for key, nodes in DEFAULT_FLOWS.items():
            n = await db.scalar(
                select(WfDefinition.id).where(
                    WfDefinition.biz_type == key, WfDefinition.del_flag == 0
                )
            )
            if n:
                continue
            d = WfDefinition(
                def_name=f"{FLOW_LABELS[key]} v1",
                biz_type=key,
                flow_json=json.dumps(nodes, ensure_ascii=False),
                version=1,
                status=1,
                create_by=1,
            )
            db.add(d)
            print(f"已种子流程定义: {key}")

        # 2) 流程配置菜单（业务单据目录下）
        exists = await db.scalar(
            select(SysMenu.id).where(SysMenu.path == "/doc/flow", SysMenu.del_flag == 0)
        )
        if exists:
            print("「流程配置」菜单已存在，跳过")
        else:
            parent = await db.scalar(
                select(SysMenu.id).where(SysMenu.path == "/doc", SysMenu.del_flag == 0)
            )
            m = SysMenu(
                menu_name="流程配置", parent_id=parent or 0, menu_type=2,
                perm_code="flow:config", path="/doc/flow", icon="Connection",
                sort=7, create_by=1,
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
            print(f"已创建「流程配置」菜单（授权角色：{role_ids}）")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
