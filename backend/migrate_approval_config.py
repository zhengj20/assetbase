"""单据审批方式配置迁移（幂等，可重复执行）：新增 wf_biz_approval_config 表。

用法（backend 目录下）：
    uv run python migrate_approval_config.py
"""
import asyncio

from app.db.base import Base
from app.db.session import engine


async def main():
    # 建表（create_all 只补缺失表，不改动已有表）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("wf_biz_approval_config 表已创建/确认")


if __name__ == "__main__":
    asyncio.run(main())
