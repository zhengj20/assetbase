"""归还单流程迁移（幂等，可重复执行）：归还表 + 菜单 + 闭环演示数据。

用法（backend 目录下）：
    uv run python migrate_return.py
"""
import asyncio
from datetime import date

from sqlalchemy import func, select

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.asset import AssAsset
from app.models.doc import (
    AssBorrow,
    AssBorrowItem,
    AssReturn,
    AssReturnItem,
)
from app.models.sys import SysMenu, SysRoleMenu, SysUser
from app.services import workflow_service as wf
from app.services.seq_service import next_doc_no

MENUS = [
    # menu_name, parent_path, perm, path, icon, sort
    ("归还管理", "/doc", "return:list", "/doc/return", "Refresh", 6),
    ("发起归还", "/doc/return", "return:create", None, None, 1),
]


async def _seed(db):
    """闭环演示数据：借用中资产 + 草稿/审批中/已通过的归还单（各 1 单）。"""
    # 幂等：已有归还单则不重复 seed
    exist_returns = await db.scalar(select(func.count()).select_from(AssReturn).where(AssReturn.del_flag == 0))
    if exist_returns:
        print(f"seed：已存在 {exist_returns} 张归还单，跳过演示数据")
        return

    # 借用中(7)资产不足 3 个则从在库资产补充（形成可演示的闭环起点）
    borrowed = await db.scalar(select(func.count()).select_from(AssAsset).where(AssAsset.status == 7, AssAsset.del_flag == 0))
    need = max(0, 3 - (borrowed or 0))
    if need:
        in_stock = list(
            await db.scalars(
                select(AssAsset).where(AssAsset.status == 1, AssAsset.del_flag == 0)
                .order_by(AssAsset.id).limit(need)
            )
        )
        if in_stock:
            borrow_user = 3  # zhangwei
            b = AssBorrow(
                borrow_no=await next_doc_no(db, "borrow"),
                org_id=in_stock[0].org_id, apply_user=1, borrow_user=borrow_user,
                borrow_date=date.today(), expected_return_date=date.today(),
                status=2, create_by=1,
            )
            db.add(b)
            await db.flush()
            for a in in_stock:
                db.add(AssBorrowItem(borrow_id=b.id, asset_id=a.id,
                                     src_warehouse_id=a.warehouse_id, return_status=0))
                a.status = 7
                a.use_user_id = borrow_user
                a.version = (a.version or 0) + 1
            print(f"seed：{len(in_stock)} 项资产转为「借用中」（借用单 {b.borrow_no}）")

    # 借用中资产
    borrowed_assets = list(
        await db.scalars(
            select(AssAsset).where(AssAsset.status == 7, AssAsset.del_flag == 0)
            .order_by(AssAsset.id).limit(3)
        )
    )
    if not borrowed_assets:
        print("seed：无借用中资产，跳过归还单演示数据")
        return

    async def _borrow_item(aid):
        return (
            await db.scalars(
                select(AssBorrowItem).where(
                    AssBorrowItem.asset_id == aid, AssBorrowItem.return_status == 0
                ).order_by(AssBorrowItem.id.desc())
            )
        ).first()

    async def _mk_return(label, assets, status):
        doc = AssReturn(
            return_no=await next_doc_no(db, "return"),
            org_id=assets[0].org_id, apply_user=1,
            return_date=date.today(), remark=label,
            status=status, create_by=1,
        )
        db.add(doc)
        await db.flush()
        for a in assets:
            bi = await _borrow_item(a.id)
            db.add(AssReturnItem(
                return_id=doc.id, asset_id=a.id,
                borrow_id=bi.borrow_id if bi else None,
                target_warehouse_id=(bi.src_warehouse_id if bi else a.warehouse_id),
            ))
        return doc

    a0, a1, a2 = borrowed_assets[0], borrowed_assets[1], (borrowed_assets[2] if len(borrowed_assets) > 2 else borrowed_assets[0])

    # 1) 草稿
    d0 = await _mk_return("演示-草稿", [a0], 0)
    await db.flush()
    print(f"seed：归还单(草稿) {d0.return_no}")

    # 2) 审批中
    d1 = await _mk_return("演示-审批中", [a1], 1)
    inst = await wf.start_instance(db, "return", d1.id, d1, 1)
    if inst:
        d1.wf_instance_id = inst.id
        d1.status = 1
    await db.flush()
    print(f"seed：归还单(审批中) {d1.return_no}（instance={d1.wf_instance_id}）")

    # 3) 已通过（资产回库）
    d2 = await _mk_return("演示-已通过", [a2], 2)
    inst2 = await wf.start_instance(db, "return", d2.id, d2, 1)
    if inst2:
        inst2.status = 2
        d2.wf_instance_id = inst2.id
    a2.status = 1
    a2.use_user_id = None
    a2.version = (a2.version or 0) + 1
    bi2 = await _borrow_item(a2.id)
    if bi2:
        bi2.return_status = 1
        bi2.return_date = date.today()
    await db.flush()
    print(f"seed：归还单(已通过) {d2.return_no}，资产 {a2.asset_code} 已回库")


async def main():
    # 建表（create_all 只补缺失表）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("归还相关表已创建/确认")

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
                role_ids = list(range(2, 7))
            for rid in role_ids:
                db.add(SysRoleMenu(role_id=rid, menu_id=m.id))
            print(f"已创建「{name}」（授权角色：{role_ids}）")

        # 闭环演示数据
        await _seed(db)

        # 修复：审批中但无流程实例的归还单（早期流程未配置时产生的孤儿单）
        orphans = list(
            await db.scalars(
                select(AssReturn).where(
                    AssReturn.status == 1,
                    AssReturn.wf_instance_id.is_(None),
                    AssReturn.del_flag == 0,
                )
            )
        )
        for doc in orphans:
            inst = await wf.start_instance(db, "return", doc.id, doc, 1)
            if inst:
                doc.wf_instance_id = inst.id
                await db.flush()
                print(f"修复：归还单 {doc.return_no} 补建流程实例 {inst.id}")

        await db.commit()
    print("归还单迁移完成")


if __name__ == "__main__":
    asyncio.run(main())
