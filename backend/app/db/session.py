from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# 多并发支撑：
# 1. async engine + aiomysql 全链路异步 I/O
# 2. 连接池 pool_size + max_overflow，按 200 并发用户规划
# 3. pool_pre_ping 防止长连接被 MySQL wait_timeout 掐断
# 4. pool_recycle 定期回收，均衡负载
engine: AsyncEngine = create_async_engine(
    settings.db_url,
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
