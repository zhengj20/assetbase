"""认证与通用 Schema。"""
from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=64)


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str
    org_id: int
    phone: str | None = None
    email: str | None = None


class LoginOut(BaseModel):
    token: str
    refresh_token: str
    user: UserInfo
    perms: list[str]


class RefreshIn(BaseModel):
    refresh_token: str


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IdOut(BaseModel):
    id: int
