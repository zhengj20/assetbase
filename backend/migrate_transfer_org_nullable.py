"""迁移脚本：调拨单去掉调入/调出公司必填，两字段改为可空。"""
import asyncio

from sqlalchemy import text

from app.db.session import AsyncSessionLocal


async def migrate():
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                """
                ALTER TABLE ass_transfer
                MODIFY COLUMN out_org_id BIGINT NULL COMMENT '调出公司',
                MODIFY COLUMN in_org_id BIGINT NULL COMMENT '调入公司'
                """
            )
        )
        await db.commit()
        print("迁移完成：ass_transfer.out_org_id / in_org_id 已改为可空")


if __name__ == "__main__":
    asyncio.run(migrate())
