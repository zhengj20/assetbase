"""系统管理域 Schema：组织/用户/角色/菜单/字典。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_name: str
    org_type: int
    parent_id: int
    org_code: str
    sort: int
    is_accounting: bool
    status: int


class OrgIn(BaseModel):
    org_name: str = Field(max_length=100)
    org_type: int = Field(ge=1, le=5)
    parent_id: int = 0
    org_code: str = Field(min_length=2, max_length=10)
    sort: int = 0
    is_accounting: bool = False
    status: int = 1
    remark: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str
    org_id: int
    phone: str | None = None
    email: str | None = None
    status: int
    create_time: datetime
    role_ids: list[int] = []


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str | None = Field(default=None, min_length=6, max_length=64)
    real_name: str = Field(max_length=50)
    org_id: int
    phone: str | None = None
    email: str | None = None
    status: int = 1
    role_ids: list[int] = []


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role_name: str
    role_code: str
    data_scope: int
    status: int
    remark: str | None = None


class RoleIn(BaseModel):
    role_name: str = Field(max_length=50)
    role_code: str = Field(min_length=2, max_length=50)
    data_scope: int = Field(ge=1, le=5, default=5)
    status: int = 1
    remark: str | None = None
    menu_ids: list[int] = []


class MenuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_name: str
    parent_id: int
    menu_type: int
    perm_code: str | None = None
    path: str | None = None
    icon: str | None = None
    sort: int
    visible: int
    status: int


class MenuIn(BaseModel):
    menu_name: str = Field(max_length=50)
    parent_id: int = 0
    menu_type: int = Field(ge=1, le=3)
    perm_code: str | None = None
    path: str | None = None
    icon: str | None = None
    sort: int = 0
    visible: int = 1
    status: int = 1


class DictTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dict_name: str
    dict_code: str
    status: int


class DictTypeIn(BaseModel):
    dict_name: str = Field(max_length=100)
    dict_code: str = Field(min_length=2, max_length=100)
    status: int = 1


class DictDataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dict_id: int
    label: str
    value: str
    sort: int
    is_default: bool
    ext_json: str | None = None


class DictDataIn(BaseModel):
    dict_id: int
    label: str = Field(max_length=100)
    value: str = Field(max_length=100)
    sort: int = 0
    is_default: bool = False
    ext_json: str | None = None


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    user_id: int | None = None
    module: str | None = None
    operation: str | None = None
    method: str | None = None
    request_url: str | None = None
    result: int | None = None
    ip: str | None = None
    cost_ms: int | None = None
    create_time: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    msg_type: int
    title: str
    content: str | None = None
    biz_type: str | None = None
    biz_id: int | None = None
    is_read: int
    send_time: datetime | None = None
