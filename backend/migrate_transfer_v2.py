"""迁移脚本：调拨单支持项目空间调拨和部门调拨，添加调入后位置、责任人、责任部门字段。

幂等 + MySQL 8 兼容（按 information_schema 判断列是否已存在再 ALTER）。
项目空间调拨/部门调拨不经过仓库，故调出/调入仓库改为可空。
"""
import asyncio

from sqlalchemy import text

from app.db.session import AsyncSessionLocal


async def _column_exists(db, table: str, column: str) -> bool:
    n = await db.scalar(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    )
    return bool(n)


async def _ensure_column(db, table: str, column: str, definition: str):
    if await _column_exists(db, table, column):
        print(f"跳过：{table}.{column} 已存在")
        return
    await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
    print(f"已添加：{table}.{column}")


async def migrate():
    async with AsyncSessionLocal() as db:
        # 1. ass_transfer 新字段
        await _ensure_column(db, "ass_transfer", "out_project_id", "BIGINT COMMENT '调出项目空间(空间ID)'")
        await _ensure_column(db, "ass_transfer", "in_project_id", "BIGINT COMMENT '调入项目空间(空间ID)'")
        await _ensure_column(db, "ass_transfer", "out_dept_id", "BIGINT COMMENT '调出部门(部门调拨时)'")
        await _ensure_column(db, "ass_transfer", "in_dept_id", "BIGINT COMMENT '调入部门(部门调拨时)'")
        # 项目空间/部门调拨不经过仓库：仓库字段改可空（幂等：已是 NULL 则跳过）
        for col in ("out_warehouse_id", "in_warehouse_id"):
            is_null = await db.scalar(
                text(
                    "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ass_transfer' AND COLUMN_NAME = :c"
                ),
                {"c": col},
            )
            if is_null == "NO":
                await db.execute(
                    text(f"ALTER TABLE ass_transfer MODIFY COLUMN {col} BIGINT NULL COMMENT '调出仓库(仓库调拨时)'")
                    if col == "out_warehouse_id"
                    else text(f"ALTER TABLE ass_transfer MODIFY COLUMN {col} BIGINT NULL COMMENT '调入仓库(仓库调拨时)'")
                )
                print(f"已改可空：ass_transfer.{col}")
            else:
                print(f"跳过：ass_transfer.{col} 已可空")
        # 2. ass_transfer_item 新字段
        await _ensure_column(db, "ass_transfer_item", "use_location", "VARCHAR(200) COMMENT '调入后使用位置'")
        await _ensure_column(db, "ass_transfer_item", "use_user_id", "BIGINT COMMENT '调入后责任人'")
        await _ensure_column(db, "ass_transfer_item", "use_dept_id", "BIGINT COMMENT '调入后责任部门'")
        await db.commit()
        print("迁移完成：调拨单表结构已就绪")


if __name__ == "__main__":
    asyncio.run(migrate())
