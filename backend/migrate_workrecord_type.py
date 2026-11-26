"""工作记录表建表 + 字段迁移（幂等，可重复执行）。

用法（backend 目录下）：
    uv run python migrate_workrecord_type.py
"""
import asyncio

from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine


async def main():
    async with engine.begin() as conn:
        # 1) 检查表是否存在
        result = await conn.execute(text("SHOW TABLES LIKE 'sys_work_record'"))
        if result.fetchone() is None:
            await conn.execute(text("""
                CREATE TABLE sys_work_record (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL COMMENT '记录人',
                    title VARCHAR(200) NOT NULL COMMENT '标题',
                    content TEXT NULL COMMENT '内容',
                    record_date DATE NOT NULL COMMENT '日期',
                    rec_type SMALLINT DEFAULT 1 COMMENT '1工作记录 2提醒',
                    remind_time VARCHAR(5) DEFAULT NULL COMMENT '提醒时间 HH:mm',
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
                ) COMMENT '工作台工作记录/提醒'
            """))
            await conn.execute(text("CREATE INDEX idx_workrecord_user_date ON sys_work_record (user_id, record_date)"))
            print("已创建 sys_work_record 表（含 rec_type / remind_time）")
        else:
            # 表已存在，检查字段
            result = await conn.execute(text("SHOW COLUMNS FROM sys_work_record LIKE 'rec_type'"))
            if result.fetchone() is None:
                await conn.execute(text("ALTER TABLE sys_work_record ADD COLUMN rec_type SMALLINT DEFAULT 1 COMMENT '1工作记录 2提醒'"))
                print("已添加 rec_type 字段")
            else:
                print("rec_type 字段已存在，跳过")

            result = await conn.execute(text("SHOW COLUMNS FROM sys_work_record LIKE 'remind_time'"))
            if result.fetchone() is None:
                await conn.execute(text("ALTER TABLE sys_work_record ADD COLUMN remind_time VARCHAR(5) DEFAULT NULL COMMENT '提醒时间 HH:mm'"))
                print("已添加 remind_time 字段")
            else:
                print("remind_time 字段已存在，跳过")


if __name__ == "__main__":
    asyncio.run(main())
