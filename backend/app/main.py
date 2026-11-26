"""应用入口：FastAPI + 操作日志中间件 + 路由聚合。

多并发部署：`uvicorn app.main:app --workers 4`（配合 Nginx 负载均衡可水平扩展，
方案 3.2 应用双节点 + 负载均衡）。
"""
import asyncio
import json
import time

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    archive_api,
    asset_api,
    auth,
    check_api,
    consumable_api,
    dashboard_api,
    doc_api,
    flow_api,
    group_api,
    message_api,
    search_api,
    sys_api,
    workbench_api,
)
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.sys import SysOperationLog

app = FastAPI(
    title="房地产行业固定资产管理系统",
    description="基于《可落地方案 V2.0》：资产全生命周期 + 售楼处样板间专项 + 盘点闭环 + 全局搜索",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SENSITIVE_FIELDS = {"password", "old_password", "new_password"}


def _mask(param: dict | None) -> dict | None:
    if not param:
        return param
    return {k: ("***" if k in SENSITIVE_FIELDS else v) for k, v in param.items()}


@app.middleware("http")
async def operation_log_middleware(request: Request, call_next):
    """操作日志（方案 1.2）：写操作全留痕，只增不改，后台异步落库不阻塞响应。"""
    start = time.time()
    response = await call_next(request)
    cost_ms = int((time.time() - start) * 1000)

    if request.method in ("POST", "PUT", "DELETE") and request.url.path.startswith("/api"):
        try:
            user_id = getattr(getattr(request.state, "current_user", None), "id", None)
            body = None
            if request.method in ("POST", "PUT"):
                body_bytes = b""
                # 流已在依赖中消费，通过 body 缓存读取
                body_bytes = getattr(request, "_cached_body", b"")
                if not body_bytes:
                    try:
                        body_bytes = await request.body()
                    except Exception:
                        body_bytes = b""
                if body_bytes:
                    try:
                        parsed = json.loads(body_bytes)
                        body = _mask(parsed if isinstance(parsed, dict) else {"data": parsed})
                    except Exception:
                        body = {"raw": body_bytes[:500].decode(errors="ignore")}

            module = request.url.path.split("/")[2] if len(request.url.path.split("/")) > 2 else "api"
            log = SysOperationLog(
                user_id=user_id,
                module=module,
                operation=request.method,
                method=request.method,
                request_url=str(request.url.path)[:500],
                request_param=json.dumps(
                    {**(body or {}), **_mask(dict(request.query_params))},
                    ensure_ascii=False, default=str,
                )[:2000],
                result=1 if response.status_code < 400 else 0,
                ip=request.client.host if request.client else None,
                cost_ms=cost_ms,
            )
            task = asyncio.create_task(_write_log(log))
            _bg_tasks.add(task)
            task.add_done_callback(_bg_tasks.discard)
        except Exception:
            pass  # 日志失败不影响业务
    return response


async def _write_log(log: SysOperationLog) -> None:
    try:
        async with AsyncSessionLocal() as session:
            session.add(log)
            await session.commit()
    except Exception:
        pass


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "guding-fa-backend"}


api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(sys_api.router, prefix=api_prefix)
app.include_router(archive_api.router, prefix=api_prefix)
app.include_router(asset_api.router, prefix=api_prefix)
app.include_router(search_api.router, prefix=api_prefix)
app.include_router(doc_api.router, prefix=api_prefix)
app.include_router(consumable_api.router, prefix=api_prefix)
app.include_router(flow_api.router, prefix=api_prefix)
app.include_router(check_api.router, prefix=api_prefix)
app.include_router(dashboard_api.router, prefix=api_prefix)
app.include_router(group_api.router, prefix=api_prefix)
app.include_router(message_api.router, prefix=api_prefix)
app.include_router(workbench_api.router, prefix=api_prefix)

# 上传文件静态服务（资产图片，asset_api 写入 backend/uploads）
_upload_root = Path(get_settings().upload_dir)
if not _upload_root.is_absolute():
    _upload_root = Path(__file__).resolve().parent.parent / _upload_root
_upload_root.mkdir(parents=True, exist_ok=True)
app.mount("/api/v1/uploads", StaticFiles(directory=_upload_root), name="uploads")


if __name__ == "__main__":
    import uvicorn

    from app.core.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
    )
