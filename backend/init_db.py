"""建表 + 种子数据初始化。

用法（backend 目录下）：
    uv run python init_db.py           # 建表；若库为空则写入种子数据
    uv run python init_db.py --reset   # 删除所有表后重建（仅开发环境！）

种子内容：组织/用户/角色/菜单/字典 + 基础档案 + 60+ 演示资产 + 一条已完成盘点任务。
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models import (
    AssAsset,
    AssAssetLog,
    AssCategory,
    AssCheckItem,
    AssCheckTask,
    AssOffice,
    AssSpace,
    AssSupplier,
    AssWarehouse,
    SysCodeSeq,
    SysDictData,
    SysDictType,
    SysMenu,
    SysOrg,
    SysRole,
    SysRoleMenu,
    SysUser,
    SysUserRole,
)

NOW = datetime.now()
YM = NOW.strftime("%y%m")


async def create_all(reset: bool):
    async with engine.begin() as conn:
        if reset:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


# ---------- 系统域 ----------
async def seed_sys(db):
    orgs = [
        ("固鼎置业集团", 1, 0, "GD", True),
        ("华东区域公司", 2, 1, "HD", False),
        ("云锦雅苑项目部", 3, 2, "YJ", True),
        ("江南星城项目部", 3, 2, "JN", True),
        ("综合管理部", 4, 1, "ZH", False),
        ("财务部", 4, 1, "CW", False),
    ]
    for name, otype, parent, code, acct in orgs:
        db.add(SysOrg(org_name=name, org_type=otype, parent_id=parent,
                      org_code=code, is_accounting=acct))
    await db.flush()

    roles = [
        ("admin", "集团管理员", 1), ("region_asset", "区域资产岗", 2),
        ("project_asset", "项目资产专员", 3), ("finance", "财务岗", 1),
        ("employee", "普通员工", 5), ("approver", "审批领导", 2),
    ]
    for code, name, scope in roles:
        db.add(SysRole(role_name=name, role_code=code, data_scope=scope))
    await db.flush()

    pwd = hash_password("admin123")
    users = [
        ("admin", "系统管理员", 1), ("wangqiang", "王强", 2),
        ("zhangwei", "张威", 3), ("liuyan", "刘燕", 3),
        ("lifang", "李芳", 6), ("zhaomin", "赵敏", 2),
    ]
    for uname, rname, org_id in users:
        db.add(SysUser(username=uname, password=pwd, real_name=rname, org_id=org_id))
    await db.flush()

    for uid, rid in [(1, 1), (2, 2), (2, 6), (3, 3), (4, 5), (5, 4), (6, 6)]:
        db.add(SysUserRole(user_id=uid, role_id=rid))

    # 菜单（与前端路由一一对应；type: 1目录 2菜单 3按钮）
    menus = [
        # key, name, parent_key, type, perm, path, icon, sort
        ("workbench", "工作台", None, 2, None, "/workbench", "HomeFilled", 0),
        ("dashboard", "驾驶舱", None, 2, None, "/dashboard", "Odometer", 1),
        ("my_approval", "我的审批", None, 2, "approval:list", "/doc/approval", "Stamp", 2),
        ("my_approval_approve", "审批通过/驳回", "my_approval", 3, "approval:approve", None, None, 1),
        ("my_approval_delegate", "转办审批", "my_approval", 3, "approval:delegate", None, None, 2),
        ("asset", "资产管理", None, 1, None, "/asset", "Box", 3),
        ("asset_list", "资产台账", "asset", 2, "asset:list", "/asset/list", "List", 1),
        ("asset_list_create", "新增资产", "asset_list", 3, "asset:create", None, None, 1),
        ("asset_list_edit", "编辑资产", "asset_list", 3, "asset:edit", None, None, 2),
        ("asset_list_delete", "删除资产", "asset_list", 3, "asset:delete", None, None, 3),
        ("asset_list_export", "导出台账", "asset_list", 3, "asset:export", None, None, 4),
        ("asset_dep", "折旧管理", "asset", 2, "depreciation:list", "/asset/depreciation", "Money", 2),
        ("asset_group", "组合包", "asset", 2, "group:list", "/asset/group", "Box", 3),
        ("asset_search", "全局搜索", "asset", 2, "asset:search", "/search", "Search", 4),
        ("asset_stats", "资产统计", "asset", 2, "asset:stats", "/asset/stats", "DataAnalysis", 5),
        ("asset_whstock", "仓库库存", "asset", 2, "warehouse_stock:list", "/asset/warehouse-stock", "Goods", 6),
        ("doc", "业务单据", None, 1, None, "/doc", "Document", 4),
        ("doc_purchase", "采购申请", "doc", 2, "purchase:list", "/doc/purchase", "ShoppingCart", 1),
        ("doc_purchase_create", "新增采购申请", "doc_purchase", 3, "purchase:create", None, None, 1),
        ("doc_stock_in", "入库管理", "doc", 2, "stockin:list", "/doc/stock-in", "Download", 2),
        ("doc_stock_in_create", "新增入库", "doc_stock_in", 3, "stockin:create", None, None, 1),
        ("doc_stock_out", "出库管理", "doc", 2, "stockout:list", "/doc/stock-out", "Upload", 3),
        ("doc_stock_out_create", "新增出库", "doc_stock_out", 3, "stockout:create", None, None, 1),
        ("doc_transfer", "调拨管理", "doc", 2, "transfer:list", "/doc/transfer", "Sort", 4),
        ("doc_transfer_create", "新增调拨", "doc_transfer", 3, "transfer:create", None, None, 1),
        ("doc_borrow", "借用管理", "doc", 2, "borrow:list", "/doc/borrow", "Switch", 5),
        ("doc_borrow_create", "新增借用", "doc_borrow", 3, "borrow:create", None, None, 1),
        ("doc_borrow_return", "资产归还", "doc_borrow", 3, "borrow:return", None, None, 2),
        ("doc_return", "归还管理", "doc", 2, "return:list", "/doc/return", "Refresh", 6),
        ("doc_return_create", "发起归还", "doc_return", 3, "return:create", None, None, 1),
        ("doc_scrap", "报废处置", "doc", 2, "scrap:list", "/doc/scrap", "Delete", 7),
        ("doc_scrap_create", "新增报废处置", "doc_scrap", 3, "scrap:create", None, None, 1),
        ("check", "盘点管理", None, 1, None, "/check", "ScaleToOriginal", 5),
        ("check_task", "盘点任务", "check", 2, "check:list", "/check/task", "Tickets", 1),
        ("check_task_create", "新建盘点任务", "check_task", 3, "check:create", None, None, 1),
        ("archive", "基础档案", None, 1, None, "/archive", "Files", 6),
        ("archive_category", "资产分类", "archive", 2, "category:list", "/archive/category", "Grid", 1),
        ("archive_category_create", "新增分类", "archive_category", 3, "category:create", None, None, 1),
        ("archive_category_edit", "编辑分类", "archive_category", 3, "category:edit", None, None, 2),
        ("archive_category_delete", "删除分类", "archive_category", 3, "category:delete", None, None, 3),
        ("archive_supplier", "供应商", "archive", 2, "supplier:list", "/archive/supplier", "OfficeBuilding", 2),
        ("archive_supplier_create", "新增供应商", "archive_supplier", 3, "supplier:create", None, None, 1),
        ("archive_supplier_edit", "编辑供应商", "archive_supplier", 3, "supplier:edit", None, None, 2),
        ("archive_supplier_delete", "删除供应商", "archive_supplier", 3, "supplier:delete", None, None, 3),
        ("archive_warehouse", "仓库管理", "archive", 2, "warehouse:list", "/archive/warehouse", "House", 3),
        ("archive_warehouse_create", "新增仓库", "archive_warehouse", 3, "warehouse:create", None, None, 1),
        ("archive_warehouse_edit", "编辑仓库", "archive_warehouse", 3, "warehouse:edit", None, None, 2),
        ("archive_warehouse_delete", "删除仓库", "archive_warehouse", 3, "warehouse:delete", None, None, 3),
        ("archive_space", "项目空间", "archive", 2, "space:list", "/archive/space", "MapLocation", 4),
        ("archive_space_create", "新增空间", "archive_space", 3, "space:create", None, None, 1),
        ("archive_space_edit", "编辑空间", "archive_space", 3, "space:edit", None, None, 2),
        ("archive_space_delete", "删除空间", "archive_space", 3, "space:delete", None, None, 3),
        ("archive_office", "办公地点", "archive", 2, "office:list", "/archive/office", "Location", 5),
        ("archive_office_create", "新增办公地点", "archive_office", 3, "office:create", None, None, 1),
        ("archive_office_edit", "编辑办公地点", "archive_office", 3, "office:edit", None, None, 2),
        ("archive_office_delete", "删除办公地点", "archive_office", 3, "office:delete", None, None, 3),
        ("approval_center", "流程管理", None, 1, None, "/approval", "Stamp", 7),
        ("flow_config", "流程配置", "approval_center", 2, "flow:config", "/doc/flow", "Connection", 1),
        ("flow_monitor", "流程监控", "approval_center", 2, "approval:monitor", "/approval/monitor", "Monitor", 2),
        ("message_center", "消息中心", None, 2, "message:list", "/messages", "Bell", 8),
        ("system", "系统管理", None, 1, None, "/system", "Setting", 9),
        ("sys_org", "组织架构", "system", 2, "sys:org", "/system/org", "Share", 1),
        ("sys_user", "用户管理", "system", 2, "sys:user", "/system/user", "User", 2),
        ("sys_role", "角色管理", "system", 2, "sys:role", "/system/role", "Avatar", 3),
        ("sys_menu", "菜单管理", "system", 2, "sys:menu", "/system/menu", "Menu", 4),
        ("sys_dict", "字典管理", "system", 2, "sys:dict", "/system/dict", "Collection", 5),
        ("sys_log", "操作日志", "system", 2, "sys:log", "/system/log", "Notebook", 6),
    ]
    key2id: dict[str, int] = {}
    for key, name, parent_key, mtype, perm, path, icon, sort in menus:
        m = SysMenu(menu_name=name, parent_id=key2id.get(parent_key, 0), menu_type=mtype,
                    perm_code=perm, path=path, icon=icon, sort=sort)
        db.add(m)
        await db.flush()
        key2id[key] = m.id

    # 角色-菜单：admin 走通配，其余角色演示环境给全部菜单
    for rid in range(2, 7):
        for mid in key2id.values():
            db.add(SysRoleMenu(role_id=rid, menu_id=mid))

    dicts = {
        "asset_status": ("资产状态", ["待入库", "在库", "领用中", "维修中", "调拨中", "已报废", "已处置", "借用中"]),
        "warehouse_type": ("仓库类型", ["总部总仓", "项目临时仓", "样板间周转仓"]),
        "space_type": ("空间类型", ["售楼处", "样板间", "办公室", "仓库"]),
        "space_status": ("空间状态", ["筹备中", "开放中", "已关闭", "已清盘"]),
        "check_type": ("盘点类型", ["定期盘点", "临时盘点", "清盘专项"]),
        "check_result": ("盘点结果", ["正常", "盘盈", "盘亏", "位置异常"]),
        "dispose_type": ("处置方式", ["报废", "变卖", "捐赠"]),
        "depreciate_method": ("折旧方式", ["平均年限法", "工作量法"]),
        "purpose": ("用途", ["办公", "样板间", "项目"]),
    }
    for code, (dname, labels) in dicts.items():
        dt = SysDictType(dict_name=dname, dict_code=code)
        db.add(dt)
        await db.flush()
        for i, label in enumerate(labels):
            db.add(SysDictData(dict_id=dt.id, label=label, value=str(i), sort=i))
    await db.flush()


# ---------- 基础档案 ----------
async def seed_archive(db):
    roots = [
        ("A01", "办公设备类", 60, 5), ("B01", "办公家具类", 60, 5),
        ("C01", "家电类", 60, 5), ("D01", "软装家具类", 48, 0),
        ("E01", "装饰摆件类", 36, 0), ("F01", "其他", 60, 5),
    ]
    leaves = {
        "A01": [("A0101", "笔记本电脑"), ("A0102", "台式电脑"), ("A0103", "打印一体机"),
                ("A0104", "投影仪"), ("A0105", "会议室平板")],
        "B01": [("B0101", "办公桌"), ("B0102", "办公椅"), ("B0103", "会议桌")],
        "C01": [("C0101", "电冰箱"), ("C0102", "滚筒洗衣机"), ("C0103", "挂式空调"),
                ("C0104", "液晶电视")],
        "D01": [("D0101", "布艺沙发"), ("D0102", "实木床"), ("D0103", "餐桌椅"),
                ("D0104", "床头柜"), ("D0105", "茶几"), ("D0106", "装饰画")],
        "E01": [("E0101", "花艺摆件"), ("E0102", "工艺雕塑")],
        "F01": [("F0101", "其他物资")],
    }
    code2id: dict[str, int] = {}
    for code, name, months, residual in roots:
        c = AssCategory(category_name=name, parent_id=0, code=code,
                        depreciate_month=months, residual_rate=Decimal(str(residual)))
        db.add(c)
        await db.flush()
        code2id[code] = c.id
    for root_code, items in leaves.items():
        for code, name in items:
            c = AssCategory(category_name=name, parent_id=code2id[root_code], code=code)
            db.add(c)
            await db.flush()
            code2id[code] = c.id

    for name, contact, phone, rating in [
        ("南京世纪办公设备有限公司", "周经理", "025-83331234", "A"),
        ("苏州美诺家具有限公司", "吴经理", "0512-66778899", "A"),
        ("青岛海慧电器有限公司", "高经理", "0532-88996677", "B"),
        ("杭州艺境软装设计工程有限公司", "林设计", "0571-87654321", "A"),
    ]:
        db.add(AssSupplier(supplier_name=name, contact=contact, phone=phone, rating=rating))
    await db.flush()

    for name, wtype, org_id, project_id in [
        ("集团总仓", 1, 1, None),
        ("云锦项目临时仓", 2, 3, 3),
        ("江南星城临时仓", 2, 4, 4),
        ("云锦样板间周转仓", 3, 3, 3),
    ]:
        db.add(AssWarehouse(warehouse_name=name, warehouse_type=wtype,
                            org_id=org_id, project_id=project_id))
    await db.flush()

    for name, org_id, building, floor, address in [
        ("集团总部办公区", 1, "A座", "15F", "南京·河西总部大厦"),
        ("华东区域办公区", 2, "B座", "8F", "南京·江东中路200号"),
        ("云锦项目部办公室", 3, "售楼处", "2F", "云锦雅苑项目现场"),
    ]:
        db.add(AssOffice(office_name=name, org_id=org_id,
                         building=building, floor=floor, address=address))
    await db.flush()

    # 空间树：售楼处 → 样板间(户型) → 房间
    def add_space(name, stype, parent_id, project_id, status=2, layout=None, room=None):
        s = AssSpace(space_name=name, space_type=stype, parent_id=parent_id,
                     project_id=project_id, layout=layout, room_type=room,
                     space_status=status)
        db.add(s)
        return s

    yj_sales = add_space("云锦雅苑售楼处", 1, 0, 3)
    jn_sales = add_space("江南星城售楼处", 1, 0, 4)
    await db.flush()
    yj89 = add_space("89㎡样板间", 2, yj_sales.id, 3, layout="89㎡")
    yj120 = add_space("120㎡样板间", 2, yj_sales.id, 3, layout="120㎡")
    jn110 = add_space("110㎡样板间", 2, jn_sales.id, 4, layout="110㎡", status=4)  # 已清盘
    await db.flush()
    for parent in (yj89, yj120, jn110):
        for r in ["客厅", "主卧", "次卧", "餐厅", "厨房", "卫生间"]:
            add_space(r, 2, parent.id, parent.project_id, room=r)
    await db.flush()
    return code2id, {"yj89": yj89, "yj120": yj120, "jn110": jn110,
                     "yj_sales": yj_sales, "jn_sales": jn_sales}


# ---------- 资产 ----------
ASSETS: list[tuple] = []


def _a(cat, name, spec, brand, price, status, org, project, place,
       high=0, reusable=0, model=None):
    ASSETS.append((cat, name, spec, brand, model, price, status, org, project,
                   place, high, reusable))


def _init_asset_spec():
    # --- 云锦 89㎡样板间 ---
    _a("D0101", "布艺沙发（三人位）", "2100×900×850mm", "顾家家居", 12999, 2, 3, 3, "89:客厅")
    _a("C0104", "液晶电视 65寸", "1650×950mm", "海信", 7999, 2, 3, 3, "89:客厅")
    _a("D0105", "岩板茶几", "1200×600mm", "林氏木业", 2599, 2, 3, 3, "89:客厅")
    _a("E0101", "花艺摆件", "陶瓷高瓶", "艺境软装", 899, 2, 3, 3, "89:客厅")
    _a("D0106", "装饰画（三联）", "1500×800mm", "艺境软装", 1599, 2, 3, 3, "89:客厅")
    _a("D0102", "实木床 1.8m", "1800×2000mm", "源氏木语", 8999, 2, 3, 3, "89:主卧")
    _a("D0104", "床头柜", "500×400×450mm", "源氏木语", 1299, 2, 3, 3, "89:主卧")
    _a("C0103", "挂式空调 1.5匹", "KFR-35GW", "格力", 4599, 2, 3, 3, "89:主卧")
    _a("D0102", "实木床 1.5m", "1500×2000mm", "源氏木语", 6999, 2, 3, 3, "89:次卧")
    _a("C0103", "挂式空调 1匹", "KFR-26GW", "格力", 3999, 2, 3, 3, "89:次卧")
    _a("C0101", "电冰箱 452L", "BCD-452WD", "海尔", 5699, 2, 3, 3, "89:厨房")
    _a("C0102", "滚筒洗衣机 10kg", "XQG100", "小天鹅", 4299, 2, 3, 3, "89:厨房")
    # --- 云锦 120㎡样板间 ---
    _a("D0101", "真皮沙发（1+2+3）", "组合", "顾家家居", 15999, 2, 3, 3, "120:客厅", high=1)
    _a("C0104", "液晶电视 75寸", "1890×1080mm", "TCL", 9999, 2, 3, 3, "120:客厅")
    _a("D0105", "大理石茶几", "1300×700mm", "林氏木业", 3299, 2, 3, 3, "120:客厅")
    _a("D0102", "实木床 1.8m（白蜡木）", "1800×2000mm", "源氏木语", 11999, 2, 3, 3, "120:主卧", high=1)
    _a("C0103", "挂式空调 1.5匹", "KFR-35GW", "格力", 4599, 2, 3, 3, "120:主卧")
    _a("D0103", "餐桌椅六件套", "岩板1.4m", "林氏木业", 7599, 2, 3, 3, "120:餐厅")
    _a("C0101", "电冰箱 502L", "BCD-502W", "海尔", 6499, 2, 3, 3, "120:厨房")
    _a("C0102", "滚筒洗衣机 10kg", "XQG100-B", "小天鹅", 4699, 2, 3, 3, "120:厨房")
    # --- 云锦售楼处 ---
    _a("A0103", "打印一体机", "M2729dw", "惠普", 5499, 2, 3, 3, "sales")
    _a("A0104", "投影仪", "H5", "极米", 8999, 2, 3, 3, "sales")
    _a("A0105", "会议室平板 86寸", "MAXHUB", "视源", 12999, 2, 3, 3, "sales", high=1)
    _a("B0103", "会议桌（12人）", "3600×1400mm", "美诺家具", 6999, 2, 3, 3, "sales")
    # --- 云锦临时仓（在库）---
    for _ in range(3):
        _a("A0101", "笔记本电脑 ThinkPad", "T14 I5/16G/512G", "联想", 4999, 1, 3, 3, "wh:2", reusable=1)
    for _ in range(2):
        _a("A0102", "台式电脑", "I5/16G/1T", "联想", 3699, 1, 3, 3, "wh:2", reusable=1)
    for _ in range(2):
        _a("B0101", "升降办公桌", "1400×700mm", "美诺家具", 2199, 1, 3, 3, "wh:2", reusable=1)
    for _ in range(4):
        _a("B0102", "人体工学椅", "网面", "美诺家具", 899, 1, 3, 3, "wh:2", reusable=1)
    for _ in range(2):
        _a("C0103", "挂式空调 1.5匹", "KFR-35GW", "格力", 3999, 1, 3, 3, "wh:2", reusable=1)
    # --- 云锦领用中 ---
    _a("A0101", "笔记本电脑 ThinkPad", "T14 I5/16G/512G", "联想", 4999, 2, 3, 3, "user:3")
    _a("A0101", "笔记本电脑 ThinkPad", "T14 I7/16G/1T", "联想", 5999, 2, 3, 3, "user:4")
    _a("A0103", "激光打印机", "P2206nw", "惠普", 3299, 2, 3, 3, "user:4")
    # --- 云锦维修 / 报废 ---
    _a("A0103", "打印一体机", "M227fdw", "惠普", 4599, 3, 3, 3, "wh:2")
    _a("B0102", "人体工学椅", "网面", "美诺家具", 899, 5, 3, 3, "wh:2")
    # --- 江南星城 110㎡样板间（已清盘，待处置）---
    _a("D0101", "布艺沙发（三人位）", "2000×880mm", "顾家家居", 9999, 1, 4, 4, "110:客厅", reusable=1)
    _a("C0104", "液晶电视 65寸", "1650×950mm", "小米", 6999, 1, 4, 4, "110:客厅", reusable=1)
    _a("D0102", "实木床 1.8m", "1800×2000mm", "源氏木语", 8999, 1, 4, 4, "110:主卧", reusable=1)
    _a("D0103", "餐桌椅六件套", "岩板1.4m", "林氏木业", 5999, 1, 4, 4, "110:餐厅", reusable=1)
    _a("C0103", "挂式空调 1.5匹", "KFR-35GW", "格力", 3999, 1, 4, 4, "110:客厅", reusable=1)
    _a("E0101", "花艺摆件", "玻璃高瓶", "艺境软装", 699, 1, 4, 4, "110:客厅", reusable=1)
    # --- 江南星城临时仓（在库）---
    for _ in range(2):
        _a("A0101", "笔记本电脑 ThinkPad", "E14 I5/16G/512G", "联想", 4299, 1, 4, 4, "wh:3", reusable=1)
    for _ in range(3):
        _a("B0102", "弓形办公椅", "网面", "美诺家具", 799, 1, 4, 4, "wh:3", reusable=1)
    _a("C0103", "挂式空调 1匹", "KFR-26GW", "格力", 3599, 1, 4, 4, "wh:3", reusable=1)
    _a("D0105", "岩板茶几", "1100×600mm", "林氏木业", 1899, 1, 4, 4, "wh:3", reusable=1)
    # --- 集团总仓（在库）---
    for _ in range(5):
        _a("A0101", "笔记本电脑 ThinkPad", "T14 I5/16G/512G", "联想", 5299, 1, 1, None, "wh:1", reusable=1)
    for _ in range(3):
        _a("B0101", "实木办公桌", "1400×700mm", "美诺家具", 2399, 1, 1, None, "wh:1", reusable=1)
    for _ in range(2):
        _a("A0103", "打印一体机", "M2729dw", "惠普", 3299, 1, 1, None, "wh:1", reusable=1)
    _a("B0103", "会议桌（10人）", "3200×1400mm", "美诺家具", 8999, 1, 1, None, "wh:1", reusable=1)


async def seed_assets(db, code2id, spaces):
    _init_asset_spec()

    # 房间名 → space id
    room_map: dict[tuple[str, str], int] = {}
    for s in list(await db.scalars(select(AssSpace))):
        if s.room_type:
            proj = "yj" if s.project_id == 3 else "jn"
            room_map[(f"{proj}:{s.parent_id}", s.room_type)] = s.id
    yj89, yj120, jn110 = spaces["yj89"], spaces["yj120"], spaces["jn110"]

    def resolve_place(place):
        """返回 (warehouse_id, space_id, use_user_id)。"""
        if place.startswith("user:"):
            return None, None, int(place[5:])
        if place.startswith("wh:"):
            return int(place[3:]), None, None
        if place == "sales":
            return None, spaces["yj_sales"].id, None
        layout, room = place.split(":")
        parent_key = {"89": f"yj:{yj89.id}", "120": f"yj:{yj120.id}",
                      "110": f"jn:{jn110.id}"}[layout]
        return None, room_map[(parent_key, room)], None

    org_codes = {1: "GD", 3: "YJ", 4: "JN"}
    seq_counter: dict[str, int] = {}
    assets = []

    for idx, (cat_code, name, spec, brand, model, price, status, org_id, project_id,
              place, high, reusable) in enumerate(ASSETS):
        buy_date = NOW.date() - timedelta(days=(idx * 5) % 300 + 5)
        ym = buy_date.strftime("%y%m")
        org_code = org_codes[org_id]
        seq_key = f"asset:{org_code}:{cat_code}:{ym}"
        seq_counter[seq_key] = seq_counter.get(seq_key, 0) + 1
        asset_code = f"{org_code}-{cat_code}-{ym}-{seq_counter[seq_key]:04d}"

        wh_id, sp_id, use_user = resolve_place(place)
        price_d = Decimal(str(price))
        months = (NOW.year - buy_date.year) * 12 + NOW.month - buy_date.month
        accum = min(price_d * Decimal("0.95") / 60 * months, price_d * Decimal("0.95"))

        a = AssAsset(
            asset_code=asset_code, asset_name=name, category_id=code2id[cat_code],
            spec=spec, brand=brand, model=model,
            unit="台" if cat_code.startswith("A") else "件",
            org_id=org_id, project_id=project_id, warehouse_id=wh_id, space_id=sp_id,
            location_detail=place if sp_id else None,
            use_user_id=use_user,
            status=status, is_high_value=high, is_reusable=reusable,
            price=price_d, buy_date=buy_date,
            warranty_end=buy_date + timedelta(days=730),
            supplier_id=(idx % 4) + 1,
            depreciation_method=1, accum_depreciation=accum,
            net_value=(price_d - accum).quantize(Decimal("0.01")),
            dep_status=1 if status in (1, 2) else 0,
            create_by=1,
        )
        db.add(a)
        await db.flush()
        assets.append(a)

        db.add(AssAssetLog(
            asset_id=a.id, action_type=1, biz_type="stock_in",
            after_snapshot=json.dumps(
                {"asset_code": asset_code, "asset_name": name,
                 "price": float(price_d), "status": status}, ensure_ascii=False),
            operator_id=1, operate_time=datetime.combine(buy_date, datetime.min.time()),
            create_by=1,
        ))

    for key, val in seq_counter.items():
        db.add(SysCodeSeq(seq_key=key, seq_value=val))
    await db.flush()
    return assets


# ---------- 盘点演示任务 ----------
async def seed_check_task(db, assets):
    yj_assets = [a for a in assets if a.project_id == 3][:20]
    task = AssCheckTask(
        task_no=f"PD{YM}-0001", task_name="云锦雅苑项目年中固定资产盘点",
        check_type=1, scope_type=2, scope_id=3,
        plan_start=NOW.date() - timedelta(days=20),
        plan_end=NOW.date() - timedelta(days=13),
        checker_ids="3,4", status=3,
        book_total=len(yj_assets),
        diff_rate=Decimal("0.1000"),
        finish_time=NOW - timedelta(days=12), create_by=3,
    )
    db.add(task)
    await db.flush()
    # 硬编码单号 PD{YM}-0001 需同步初始化发号计数，否则首次发号会与之重号
    db.add(SysCodeSeq(seq_key=f"doc:check:{YM}", seq_value=1))

    for i, a in enumerate(yj_assets):
        r = 3 if i == 5 else (4 if i == 11 else 1)  # 1 盘亏 + 1 位置异常
        db.add(AssCheckItem(
            task_id=task.id, asset_id=a.id, space_id=a.space_id,
            book_status=a.status, book_location=a.location_detail or "",
            actual_status=a.status if r != 3 else None,
            actual_location=(a.location_detail or "") if r == 1 else
            ("B2 临时库房" if r == 3 else "样板间走廊展位"),
            check_result=r, check_user=3, check_time=NOW - timedelta(days=14),
            diff_handle_status=1 if r in (3, 4) else 0,
            diff_handle_note="已按盘亏流程销账处理" if r == 3 else
                             ("已核对搬移记录，账面位置已更新" if r == 4 else None),
        ))
    db.add(AssCheckItem(  # 盘盈 1 条
        task_id=task.id, asset_id=None, surplus_name="小米空气净化器（账外）",
        surplus_price=Decimal("1299"),
        check_result=2, check_user=4, check_time=NOW - timedelta(days=14),
        diff_handle_status=1, diff_handle_note="已走盘盈入库流程",
    ))
    await db.flush()


async def main():
    reset = "--reset" in sys.argv
    try:
        print("正在建表..." + ("（含删库重建）" if reset else ""))
        await create_all(reset)

        async with AsyncSessionLocal() as db:
            user_count = (await db.execute(
                select(func.count()).select_from(SysUser))).scalar()
        if user_count:
            print("库中已有数据，跳过种子。如需重建请执行: uv run python init_db.py --reset")
            return

        print("写入种子数据...")
        async with AsyncSessionLocal() as db:
            await seed_sys(db)
            code2id, spaces = await seed_archive(db)
            assets = await seed_assets(db, code2id, spaces)
            await seed_check_task(db, assets)
            await db.commit()
        print(f"完成：组织/用户/角色/菜单/字典 + {len(assets)} 项演示资产 + 盘点演示任务")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
