"""易耗品模块迁移（幂等，可重复执行）：8 张 con_* 表 + 菜单 + 权限授权 + 演示物料。

用法（backend 目录下）：
    uv run python migrate_consumable.py
"""
import asyncio

from sqlalchemy import func, select

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.archive import AssWarehouse
from app.models.consumable import ConItem, ConStock
from app.models.sys import SysMenu, SysRoleMenu
from migrate_con_menu_move import place_con_menu

# 授权角色（对齐业务单据/资产管理）
GRANT_ROLE_IDS = [2, 3, 4, 5, 6]

# (菜单名, 上级菜单名, menu_type, perm_code, path, icon, sort)
MENUS = [
    ("易耗品", None, 1, None, "/con", "ShoppingBag", 10),
    ("物料档案", "易耗品", 2, "con_item:list", "/con/item", "Goods", 1),
    ("物料维护", "物料档案", 3, "con_item:create", None, None, 1),
    ("采购管理", "易耗品", 2, "con_purchase:list", "/con/purchase", "ShoppingCart", 2),
    ("发起采购", "采购管理", 3, "con_purchase:create", None, None, 1),
    ("易耗入库", "易耗品", 2, "con_inbound:list", "/con/inbound", "Box", 3),
    ("发起入库", "易耗入库", 3, "con_inbound:create", None, None, 1),
    ("领用管理", "易耗品", 2, "con_issue:list", "/con/issue", "Tickets", 4),
    ("发起领用", "领用管理", 3, "con_issue:create", None, None, 1),
    ("库存查询", "易耗品", 2, "con_stock:list", "/con/stock", "PieChart", 5),
]

# 演示物料（item_code, item_name, spec, unit, category, unit_price）
DEMO_ITEMS = [
    ("YH-A4", "A4复印纸", "70g 500张/包", "包", "办公用品", 22.00),
    ("YH-PEN", "中性签字笔", "0.5mm 黑色", "支", "办公用品", 2.50),
    ("YH-INK", "激光硒鼓", "HP 88A", "个", "打印耗材", 380.00),
    ("YH-CUP", "一次性纸杯", "200ml 50只/包", "包", "办公耗材", 8.00),
    ("YH-CLEAN", "工业洗手液", "500ml", "瓶", "清洁用品", 15.00),
]


async def _seed(db):
    """演示物料 + 少量库存（幂等：已有物料则跳过）。"""
    exist = await db.scalar(select(func.count()).select_from(ConItem).where(ConItem.del_flag == 0))
    if exist:
        print(f"seed：已存在 {exist} 个物料，跳过演示数据")
        return

    wh_id = (await db.scalar(select(AssWarehouse.id).where(AssWarehouse.del_flag == 0).order_by(AssWarehouse.id))) or 1
    for code, name, spec, unit, cat, price in DEMO_ITEMS:
        item = ConItem(
            item_code=code, item_name=name, spec=spec, unit=unit,
            category=cat, unit_price=price, status=1, create_by=1,
        )
        db.add(item)
        await db.flush()
        # 前 3 个物料给点初始库存，便于演示「库存领用」
        if code in ("YH-A4", "YH-PEN", "YH-INK"):
            qty = {"YH-A4": 200, "YH-PEN": 500, "YH-INK": 20}[code]
            db.add(ConStock(item_id=item.id, warehouse_id=wh_id, qty=qty, unit_price=price, create_by=1))
    print(f"seed：已创建 {len(DEMO_ITEMS)} 个演示物料，其中 3 个有初始库存（仓库 id={wh_id}）")


async def main():
    # 1) 建表（create_all 只补缺失表）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("易耗品相关表已创建/确认")

    async with AsyncSessionLocal() as db:
        # 2) 菜单 + 权限
        name_to_id: dict[str, int] = {}
        for name, parent_name, menu_type, perm, path, icon, sort in MENUS:
            exists = await db.scalar(select(SysMenu.id).where(SysMenu.menu_name == name, SysMenu.del_flag == 0))
            if exists:
                name_to_id[name] = exists
                continue
            parent_id = name_to_id.get(parent_name, 0) if parent_name else 0
            m = SysMenu(
                menu_name=name, parent_id=parent_id, menu_type=menu_type,
                perm_code=perm, path=path, icon=icon, sort=sort, create_by=1,
            )
            db.add(m)
            await db.flush()
            name_to_id[name] = m.id
            for rid in GRANT_ROLE_IDS:
                db.add(SysRoleMenu(role_id=rid, menu_id=m.id))
            print(f"已创建菜单「{name}」（type={menu_type} perm={perm}）→ 角色 {GRANT_ROLE_IDS}")

        # 2.1) 「易耗品」作为顶级菜单排在「盘点管理」之后（与 migrate_con_menu_move.py 同一逻辑）
        await place_con_menu(db)

        # 3) 演示数据
        await _seed(db)

        await db.commit()
    print("易耗品模块迁移完成")


if __name__ == "__main__":
    asyncio.run(main())
