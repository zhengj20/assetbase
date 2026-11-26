"""基础档案域（方案 6.2-2）：分类/供应商/空间/仓库。"""
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CommonMixin


class AssCategory(CommonMixin, Base):
    """资产分类表：二级树，每级可配折旧年限与残值率。"""

    __tablename__ = "ass_category"

    category_name: Mapped[str] = mapped_column(String(100), comment="分类名称")
    parent_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="上级分类，0为根")
    code: Mapped[str] = mapped_column(
        String(10), unique=True, comment="分类代码(如A0201,编码规则段)"
    )
    depreciate_month: Mapped[int | None] = mapped_column(Integer, comment="折旧年限(月)")
    residual_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), comment="残值率默认值(%)"
    )
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")


class AssSupplier(CommonMixin, Base):
    __tablename__ = "ass_supplier"

    supplier_name: Mapped[str] = mapped_column(String(200), comment="供应商名称")
    contact: Mapped[str | None] = mapped_column(String(50), comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(20), comment="电话")
    bank_account: Mapped[str | None] = mapped_column(String(100), comment="银行账户")
    coop_status: Mapped[int] = mapped_column(
        SmallInteger, default=1, comment="1合作中 2暂停 3终止"
    )
    rating: Mapped[int | None] = mapped_column(String(10), comment="评级A/B/C")


class AssSpace(CommonMixin, Base):
    """项目空间表（方案 P0-1 核心新增）：项目→空间→户型→房间 四级空间树。"""

    __tablename__ = "ass_space"

    space_name: Mapped[str] = mapped_column(String(100), comment="空间名称")
    space_type: Mapped[int] = mapped_column(
        SmallInteger, comment="1售楼处 2样板间 3办公室 4仓库"
    )
    parent_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="上级空间，0为根")
    project_id: Mapped[int] = mapped_column(BigInteger, comment="所属项目(组织ID)")
    layout: Mapped[str | None] = mapped_column(String(50), comment="户型(如89㎡)")
    room_type: Mapped[str | None] = mapped_column(String(50), comment="房间功能(客厅/主卧)")
    space_status: Mapped[int] = mapped_column(
        SmallInteger, default=1, comment="1筹备中 2开放中 3已关闭 4已清盘"
    )
    floor: Mapped[str | None] = mapped_column(String(20), comment="楼层")
    area: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), comment="面积㎡")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")

    __table_args__ = (Index("idx_space_project", "project_id", "space_type"),)


class AssOffice(CommonMixin, Base):
    """办公地点表：公司/园区/楼栋楼层级办公位置，供资产挂靠与按部门归属使用。"""

    __tablename__ = "ass_office"

    office_name: Mapped[str] = mapped_column(String(100), comment="办公地点名称")
    org_id: Mapped[int] = mapped_column(BigInteger, comment="所属公司")
    project_id: Mapped[int | None] = mapped_column(BigInteger, comment="关联项目(可选)")
    building: Mapped[str | None] = mapped_column(String(50), comment="楼栋")
    floor: Mapped[str | None] = mapped_column(String(20), comment="楼层")
    address: Mapped[str | None] = mapped_column(String(200), comment="详细地址")
    manager_id: Mapped[int | None] = mapped_column(BigInteger, comment="负责人")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")

    __table_args__ = (Index("idx_office_org", "org_id"),)


class AssWarehouse(CommonMixin, Base):
    __tablename__ = "ass_warehouse"

    warehouse_name: Mapped[str] = mapped_column(String(100), comment="仓库名称")
    warehouse_type: Mapped[int] = mapped_column(
        SmallInteger, comment="1总部总仓 2项目临时仓 3样板间周转仓"
    )
    org_id: Mapped[int] = mapped_column(BigInteger, comment="所属组织")
    project_id: Mapped[int | None] = mapped_column(BigInteger, comment="所属项目")
    space_id: Mapped[int | None] = mapped_column(BigInteger, comment="关联空间位置")
    manager_id: Mapped[int | None] = mapped_column(BigInteger, comment="仓管员")
    address: Mapped[str | None] = mapped_column(String(200), comment="地址")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")

    __table_args__ = (Index("idx_wh_org", "org_id", "warehouse_type"),)



