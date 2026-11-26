"""资产核心域（方案 6.2-3）：资产主表 / 组合包 / 履历 / 图片。

含全局搜索支撑：asset_code 唯一索引 + (org_id,status) 等高频复合索引 + FULLTEXT ngram 全文索引。
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Numeric as SaDecimal,
    Index,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CommonMixin


class AssAsset(CommonMixin, Base):
    """资产主表（30+ 字段，管理/财务/追溯三类）。"""

    __tablename__ = "ass_asset"

    # ---- 基础信息
    asset_code: Mapped[str] = mapped_column(String(30), unique=True, comment="唯一资产编码")
    asset_name: Mapped[str] = mapped_column(String(200), comment="资产名称")
    category_id: Mapped[int] = mapped_column(BigInteger, comment="分类")
    spec: Mapped[str | None] = mapped_column(String(200), comment="规格")
    brand: Mapped[str | None] = mapped_column(String(100), comment="品牌")
    model: Mapped[str | None] = mapped_column(String(100), comment="型号")
    unit: Mapped[str] = mapped_column(String(20), default="件", comment="计量单位")
    qrcode: Mapped[str | None] = mapped_column(String(64), comment="二维码令牌(补打即换)")

    # ---- 归属（双维度：财务核算公司 + 业务项目/空间）
    org_id: Mapped[int] = mapped_column(BigInteger, comment="财务核算公司")
    project_id: Mapped[int | None] = mapped_column(BigInteger, comment="业务项目")
    office_id: Mapped[int | None] = mapped_column(BigInteger, comment="办公地点")
    warehouse_id: Mapped[int | None] = mapped_column(BigInteger, comment="所在仓库")
    space_id: Mapped[int | None] = mapped_column(BigInteger, comment="房间级位置")
    location_detail: Mapped[str | None] = mapped_column(String(200), comment="详细位置")
    use_user_id: Mapped[int | None] = mapped_column(BigInteger, comment="领用人")
    use_dept_id: Mapped[int | None] = mapped_column(BigInteger, comment="使用部门")

    # ---- 状态与标记
    status: Mapped[int] = mapped_column(
        SmallInteger, default=0,
        comment="0待入库 1在库 2领用中 3维修中 4调拨中 5已报废 6已处置 7借用中",
    )
    pre_repair_status: Mapped[int | None] = mapped_column(
        SmallInteger, comment="维修前状态(维修完成时恢复,维修中为原状态)"
    )
    is_high_value: Mapped[bool] = mapped_column(SmallInteger, default=0, comment="高值标记")
    is_reusable: Mapped[bool] = mapped_column(SmallInteger, default=0, comment="可复用标记")
    group_id: Mapped[int | None] = mapped_column(BigInteger, comment="软装组合包ID")

    # ---- 采购与财务
    price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="原值")
    buy_date: Mapped[date | None] = mapped_column(Date, comment="购置日期")
    warranty_end: Mapped[date | None] = mapped_column(Date, comment="保修到期")
    supplier_id: Mapped[int | None] = mapped_column(BigInteger, comment="供应商")
    invoice_no: Mapped[str | None] = mapped_column(String(100), comment="发票号")
    depreciation_method: Mapped[int | None] = mapped_column(
        SmallInteger, comment="1平均年限法 2工作量法"
    )
    residual_value: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="净残值")
    accum_depreciation: Mapped[Decimal | None] = mapped_column(
        SaDecimal(14, 2), default=0, comment="累计折旧"
    )
    net_value: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="净值")
    dep_status: Mapped[int] = mapped_column(
        SmallInteger, default=0, comment="0未计提 1计提中 2已计提完"
    )
    last_check_time: Mapped[datetime | None] = mapped_column(DateTime, comment="最近盘点时间")
    image_cover: Mapped[str | None] = mapped_column(String(500), comment="主图URL")

    __table_args__ = (
        # 方案 6.4 索引规范
        Index("idx_asset_org_status", "org_id", "status"),
        Index("idx_asset_project", "project_id"),
        Index("idx_asset_space", "space_id"),
        Index("idx_asset_use_user", "use_user_id"),
        Index("idx_asset_category", "category_id"),
        Index("idx_asset_warehouse", "warehouse_id"),
        Index("idx_asset_office", "office_id"),
        # 全局搜索全文索引（中文 ngram 分词，MySQL 8）
        Index(
            "ft_asset_search",
            "asset_name",
            "spec",
            "brand",
            "model",
            mysql_prefix="FULLTEXT",
            mysql_with_parser="ngram",
        ),
    )


class AssAssetGroup(CommonMixin, Base):
    """资产组合包表（方案 P1-4）：软装包整体采购、拆分为单件、整包调拨。"""

    __tablename__ = "ass_asset_group"

    group_name: Mapped[str] = mapped_column(String(200), comment="组合包名称")
    project_id: Mapped[int | None] = mapped_column(BigInteger, comment="所属项目")
    space_id: Mapped[int | None] = mapped_column(BigInteger, comment="绑定空间")
    total_price: Mapped[Decimal | None] = mapped_column(SaDecimal(14, 2), comment="包总价")
    source_type: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1采购 2调拨")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1使用中 0已解散")


class AssAssetLog(CommonMixin, Base):
    """资产履历表（方案 P0-3 核心新增）：只增不改，变更前后 JSON 快照。"""

    __tablename__ = "ass_asset_log"

    asset_id: Mapped[int] = mapped_column(BigInteger, comment="资产ID")
    action_type: Mapped[int] = mapped_column(
        SmallInteger,
        comment="1入库 2领用 3归还 4调拨 5维修 6盘点 7折旧 8报废 9处置 10变更",
    )
    biz_type: Mapped[str | None] = mapped_column(String(50), comment="业务单据类型")
    biz_id: Mapped[int | None] = mapped_column(BigInteger, comment="业务单据ID")
    before_snapshot: Mapped[str | None] = mapped_column(Text, comment="变更前JSON")
    after_snapshot: Mapped[str | None] = mapped_column(Text, comment="变更后JSON")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, comment="操作人")
    operate_time: Mapped[datetime] = mapped_column(
        DateTime, comment="操作时间"
    )

    __table_args__ = (
        Index("idx_log_asset_time", "asset_id", "operate_time"),
        Index("idx_log_biz", "biz_type", "biz_id"),
    )


class AssAssetImage(CommonMixin, Base):
    __tablename__ = "ass_asset_image"

    asset_id: Mapped[int] = mapped_column(BigInteger, comment="资产ID")
    file_id: Mapped[int | None] = mapped_column(BigInteger, comment="文件ID")
    image_type: Mapped[int] = mapped_column(
        SmallInteger, default=1, comment="1档案图 2盘点实拍 3维修凭证"
    )
    image_url: Mapped[str | None] = mapped_column(String(500), comment="图片地址")
    upload_time: Mapped[datetime | None] = mapped_column(DateTime, comment="上传时间")

    __table_args__ = (Index("idx_img_asset", "asset_id"),)
