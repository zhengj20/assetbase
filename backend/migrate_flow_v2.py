"""流程引擎三期迁移（幂等，可重复执行）。

- wf_definition：+flow_key/flow_name/condition_json/priority；
  唯一键 (biz_type,version) → (flow_key,version)；purchase_high 并入 purchase 高额条件流程
- wf_instance：+flow_name/initiator_id/finish_time/finish_by/finish_note
- wf_task：+node_key/sign_from

用法（backend 目录下）：
    uv run python migrate_flow_v2.py
"""
import asyncio
import re

from sqlalchemy import inspect, select, text

from app.db.session import AsyncSessionLocal, engine
from app.models.check import WfDefinition
from app.models.doc import (
    AssPurchaseApply,
    AssScrap,
    AssStockIn,
    AssStockOut,
    AssTransfer,
)

# biz_type → 发起人列（旧实例回填 initiator_id 用）
_INITIATOR_COL = {
    "purchase": AssPurchaseApply.apply_user,
    "stock_in": AssStockIn.create_by,
    "stock_out": AssStockOut.create_by,
    "transfer": AssTransfer.apply_user,
    "scrap": AssScrap.apply_user,
}


async def _table_cols(table: str) -> set[str]:
    def _cols(sync_conn):
        return {c["name"] for c in inspect(sync_conn).get_columns(table)}

    async with engine.connect() as conn:
        return await conn.run_sync(_cols)


async def _table_indexes(table: str) -> set[str]:
    def _idx(sync_conn):
        return {i["name"] for i in inspect(sync_conn).get_indexes(table)}

    async with engine.connect() as conn:
        return await conn.run_sync(_idx)


async def main():
    # ---------- 1) wf_definition ----------
    cols = await _table_cols("wf_definition")
    adds = []
    if "flow_key" not in cols:
        adds.append("ADD COLUMN flow_key VARCHAR(50) NOT NULL DEFAULT '' COMMENT '流程稳定标识(同流程各版本共享)'")
    if "flow_name" not in cols:
        adds.append("ADD COLUMN flow_name VARCHAR(100) NULL COMMENT '流程名称(不含版本)'")
    if "condition_json" not in cols:
        adds.append("ADD COLUMN condition_json TEXT NULL COMMENT '分支条件JSON;空=兜底'")
    if "priority" not in cols:
        adds.append("ADD COLUMN priority INT NOT NULL DEFAULT 100 COMMENT '匹配优先级,越小越先'")
    if adds:
        async with engine.begin() as conn:
            await conn.execute(text(f"ALTER TABLE wf_definition {', '.join(adds)}"))
        print("wf_definition 新字段就绪")

    # 回填 flow_key（唯一）与 flow_name（此时旧唯一键仍在，不动 biz_type）
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(WfDefinition))).all()
        changed = False
        for d in rows:
            if not d.flow_key:
                d.flow_key = f"fl_d{d.id}"
                changed = True
            if not d.flow_name:
                d.flow_name = re.sub(r"\s*v\d+$", "", d.def_name or "")
                changed = True
        if changed:
            await db.commit()
            print(f"已回填 {len(rows)} 条流程定义（flow_key/flow_name）")
        else:
            print("流程定义已回填，跳过")

    # 唯一键切换（须先于 purchase_high→purchase 回填，避免旧唯一键冲突）
    indexes = await _table_indexes("wf_definition")
    if "uk_wf_def_biz_ver" in indexes and "uk_wf_def_flow_ver" not in indexes:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE wf_definition DROP INDEX uk_wf_def_biz_ver"))
            await conn.execute(
                text("ALTER TABLE wf_definition ADD UNIQUE uk_wf_def_flow_ver (flow_key, version)")
            )
        print("唯一键已切换为 (flow_key, version)")

    # 高额采购并入 purchase：金额>5万 走该条件流程
    async with AsyncSessionLocal() as db:
        highs = (
            await db.scalars(select(WfDefinition).where(WfDefinition.biz_type == "purchase_high"))
        ).all()
        if highs:
            for d in highs:
                d.biz_type = "purchase"
                d.condition_json = '{"field": "total_amount", "op": "gt", "value": 50000}'
                d.priority = d.priority or 100
            await db.commit()
            print(f"已合并 purchase_high → purchase 条件流程（{len(highs)} 条）")
        else:
            print("无 purchase_high 待合并")

    # ---------- 2) wf_instance ----------
    cols = await _table_cols("wf_instance")
    adds = []
    if "flow_name" not in cols:
        adds.append("ADD COLUMN flow_name VARCHAR(100) NULL COMMENT '发起时流程名称快照'")
    if "initiator_id" not in cols:
        adds.append("ADD COLUMN initiator_id BIGINT NULL COMMENT '发起人'")
    if "finish_time" not in cols:
        adds.append("ADD COLUMN finish_time DATETIME NULL COMMENT '结束时间'")
    if "finish_by" not in cols:
        adds.append("ADD COLUMN finish_by BIGINT NULL COMMENT '结束操作人'")
    if "finish_note" not in cols:
        adds.append("ADD COLUMN finish_note VARCHAR(500) NULL COMMENT '结束备注'")
    if adds:
        async with engine.begin() as conn:
            await conn.execute(text(f"ALTER TABLE wf_instance {', '.join(adds)}"))
        print("wf_instance 新字段就绪")

    indexes = await _table_indexes("wf_instance")
    if "idx_wfi_initiator" not in indexes:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE wf_instance ADD INDEX idx_wfi_initiator (initiator_id)"))
        print("wf_instance 增加 idx_wfi_initiator")

    # 旧实例回填 initiator_id
    async with AsyncSessionLocal() as db:
        for biz_type, user_col in _INITIATOR_COL.items():
            sql = (
                f"UPDATE wf_instance i JOIN {user_col.table.name} d ON i.biz_id = d.id "
                f"SET i.initiator_id = d.{user_col.key} "
                f"WHERE i.biz_type = '{biz_type}' AND i.initiator_id IS NULL AND d.del_flag = 0"
            )
            r = await db.execute(text(sql))
            if r.rowcount:
                print(f"wf_instance 回填 initiator_id（{biz_type}）：{r.rowcount} 条")
        await db.commit()

    # ---------- 3) wf_task ----------
    cols = await _table_cols("wf_task")
    adds = []
    if "node_key" not in cols:
        adds.append("ADD COLUMN node_key VARCHAR(30) NULL COMMENT '节点标识(flow_json node id)'")
    if "sign_from" not in cols:
        adds.append("ADD COLUMN sign_from BIGINT NULL COMMENT '加签来源任务ID'")
    if adds:
        async with engine.begin() as conn:
            await conn.execute(text(f"ALTER TABLE wf_task {', '.join(adds)}"))
        print("wf_task 新字段就绪")

    print("迁移完成")


if __name__ == "__main__":
    asyncio.run(main())
