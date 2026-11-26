"""系统管理域（方案 6.2-1）：组织/用户/角色/菜单/字典/日志/消息/文件 + 编码发号表。"""
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CommonMixin


class SysOrg(CommonMixin, Base):
    """组织架构表：五级架构（集团/区域/项目公司/部门/点位）。"""

    __tablename__ = "sys_org"

    org_name: Mapped[str] = mapped_column(String(100), comment="组织名称")
    org_type: Mapped[int] = mapped_column(
        SmallInteger,
        comment="1集团 2区域公司 3项目公司 4部门 5点位(售楼处/样板间等)",
    )
    parent_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="上级组织ID，0为根")
    org_code: Mapped[str] = mapped_column(String(10), comment="公司代码(编码规则用,2-4位)")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    is_accounting: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="独立核算标记"
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")

    __table_args__ = (Index("idx_org_parent", "parent_id"),)


class SysUser(CommonMixin, Base):
    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(String(50), unique=True, comment="登录账号")
    password: Mapped[str] = mapped_column(String(100), comment="BCrypt 密码")
    real_name: Mapped[str] = mapped_column(String(50), comment="姓名")
    org_id: Mapped[int] = mapped_column(BigInteger, comment="所属组织")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    email: Mapped[str | None] = mapped_column(String(100), comment="邮箱")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")

    __table_args__ = (Index("idx_user_org", "org_id"),)


class SysRole(CommonMixin, Base):
    __tablename__ = "sys_role"

    role_name: Mapped[str] = mapped_column(String(50), comment="角色名称")
    role_code: Mapped[str] = mapped_column(String(50), unique=True, comment="角色编码")
    data_scope: Mapped[int] = mapped_column(
        SmallInteger, default=5,
        comment="数据权限:1全部 2本公司及下级 3本公司 4本部门 5仅本人",
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")


class SysUserRole(Base):
    """用户角色关联（多对多）。"""

    __tablename__ = "sys_user_role"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class SysMenu(CommonMixin, Base):
    __tablename__ = "sys_menu"

    menu_name: Mapped[str] = mapped_column(String(50), comment="菜单名称")
    parent_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="上级菜单")
    menu_type: Mapped[int] = mapped_column(SmallInteger, comment="1目录 2菜单 3按钮")
    perm_code: Mapped[str | None] = mapped_column(String(100), comment="权限标识如 asset:list")
    path: Mapped[str | None] = mapped_column(String(200), comment="前端路由路径")
    icon: Mapped[str | None] = mapped_column(String(50), comment="菜单图标")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    visible: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1显示 0隐藏")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")


class SysRoleMenu(Base):
    __tablename__ = "sys_role_menu"

    role_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    menu_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class SysDictType(CommonMixin, Base):
    __tablename__ = "sys_dict_type"

    dict_name: Mapped[str] = mapped_column(String(100), comment="字典名称")
    dict_code: Mapped[str] = mapped_column(String(100), unique=True, comment="字典编码")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1启用 0停用")


class SysDictData(CommonMixin, Base):
    __tablename__ = "sys_dict_data"

    dict_id: Mapped[int] = mapped_column(BigInteger, comment="字典类型ID")
    label: Mapped[str] = mapped_column(String(100), comment="标签")
    value: Mapped[str] = mapped_column(String(100), comment="键值")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, comment="默认项")
    ext_json: Mapped[str | None] = mapped_column(Text, comment="扩展JSON(如折旧年限)")

    __table_args__ = (Index("idx_dict_data_type", "dict_id"),)


class SysOperationLog(Base):
    """操作日志：只增不改（方案 1.2）。"""

    __tablename__ = "sys_operation_log"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, comment="操作人")
    module: Mapped[str | None] = mapped_column(String(50), comment="模块")
    operation: Mapped[str | None] = mapped_column(String(50), comment="动作")
    method: Mapped[str | None] = mapped_column(String(10), comment="HTTP方法")
    request_url: Mapped[str | None] = mapped_column(String(500), comment="请求地址")
    request_param: Mapped[str | None] = mapped_column(Text, comment="请求参数(脱敏)")
    result: Mapped[int | None] = mapped_column(SmallInteger, comment="1成功 0失败")
    ip: Mapped[str | None] = mapped_column(String(50), comment="来源IP")
    cost_ms: Mapped[int | None] = mapped_column(Integer, comment="耗时ms")
    create_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="操作时间"
    )

    __table_args__ = (Index("idx_oplog_user_time", "user_id", "create_time"),)


class SysMessage(CommonMixin, Base):
    __tablename__ = "sys_message"

    msg_type: Mapped[int] = mapped_column(SmallInteger, comment="1审批 2预警 3系统")
    title: Mapped[str] = mapped_column(String(200), comment="标题")
    content: Mapped[str | None] = mapped_column(Text, comment="内容")
    receiver_id: Mapped[int] = mapped_column(BigInteger, comment="接收人")
    biz_type: Mapped[str | None] = mapped_column(String(50), comment="业务类型")
    biz_id: Mapped[int | None] = mapped_column(BigInteger, comment="业务ID")
    is_read: Mapped[int] = mapped_column(SmallInteger, default=0, comment="0未读 1已读")
    send_time: Mapped[datetime | None] = mapped_column(DateTime, comment="发送时间")

    __table_args__ = (Index("idx_msg_receiver", "receiver_id", "is_read"),)


class SysWorkRecord(Base):
    """工作台工作记录/提醒：用户按日记录的工作内容与日程提醒。"""

    __tablename__ = "sys_work_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, comment="记录人")
    title: Mapped[str] = mapped_column(String(200), comment="标题")
    content: Mapped[str | None] = mapped_column(Text, comment="内容")
    record_date: Mapped[date] = mapped_column(Date, comment="日期")
    rec_type: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1工作记录 2提醒")
    remind_time: Mapped[str | None] = mapped_column(String(5), comment="提醒时间 HH:mm")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("idx_workrecord_user_date", "user_id", "record_date"),)


class SysFile(Base):
    __tablename__ = "sys_file"

    file_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(200), comment="文件名")
    file_path: Mapped[str] = mapped_column(String(500), comment="存储路径")
    file_size: Mapped[int | None] = mapped_column(BigInteger, comment="字节")
    biz_type: Mapped[str | None] = mapped_column(String(50), comment="业务类型")
    biz_id: Mapped[int | None] = mapped_column(BigInteger, comment="业务ID")
    upload_user: Mapped[int | None] = mapped_column(BigInteger, comment="上传人")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SysCodeSeq(Base):
    """编码发号表（V2.0 优化项）。

    替代方案中的 Redis 分布式锁：利用 MySQL 原子自增（LAST_INSERT_ID 技巧），
    多 worker / 多节点并发下保证资产编码与单据号绝不重号。
    """

    __tablename__ = "sys_code_seq"

    seq_key: Mapped[str] = mapped_column(String(100), primary_key=True, comment="发号键")
    seq_value: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", comment="当前值")

    __table_args__ = (
        UniqueConstraint("seq_key", name="uk_seq_key"),
    )
