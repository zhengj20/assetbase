from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    db_host: str = "127.0.0.1"
    db_port: int = 3307
    db_user: str = "root"
    db_password: str = "change-me-db-password"
    db_name: str = "guding"

    # JWT
    jwt_secret: str = "change-me-jwt-secret"
    jwt_expire_hours: int = 8
    jwt_algorithm: str = "HS256"
    # 刷新令牌有效期（天）
    jwt_refresh_expire_days: int = 7

    # 服务
    host: str = "0.0.0.0"
    port: int = 5200
    workers: int = 4

    # 连接池
    pool_size: int = 20
    max_overflow: int = 40

    # 上传文件目录（相对 backend 根目录）
    upload_dir: str = "uploads"

    # 登录失败锁定
    login_max_fail: int = 5
    login_lock_minutes: int = 10

    # CORS 允许来源（逗号分隔；* 表示全部，生产环境应收敛为前端域名）
    cors_origins: str = "*"

    @property
    def db_url(self) -> str:
        from urllib.parse import quote_plus

        pwd = quote_plus(self.db_password)
        return (
            f"mysql+aiomysql://{self.db_user}:{pwd}@{self.db_host}:{self.db_port}"
            f"/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
