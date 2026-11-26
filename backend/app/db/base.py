from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """全局 Declarative Base"""


class CommonMixin:
    """公共字段规范（方案 6.1）：审计字段 + 软删除 + 乐观锁，所有业务表统一包含。

    id 主键统一使用 BIGINT 自增（方案注明雪花 ID 为分库分表预留项）。
    """

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    create_by: Mapped[int | None] = mapped_column(BigInteger, comment="创建人")
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, server_default=func.now(), comment="创建时间"
    )
    update_by: Mapped[int | None] = mapped_column(BigInteger, comment="更新人")
    update_time: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now,
        server_default=func.now(), comment="更新时间"
    )
    del_flag: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", comment="软删除:0正常 1已删除"
    )
    version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="乐观锁版本号"
    )
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")


class DictMixin(CommonMixin):
    """字典表等纯配置表可省略乐观锁/审计人，仍保留公共字段规范。"""
