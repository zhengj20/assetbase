"""消息中心 API（方案模块7：站内信/待办推送）。"""
import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core.deps import DbDep, UserDep
from app.core.pagination import PageData, PageParams
from app.models.sys import SysMessage
from app.services import message_service as msg

router = APIRouter(prefix="/messages", tags=["消息中心"])


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
    create_time: datetime


@router.get("", response_model=PageData[MessageOut])
async def my_messages(
    db: DbDep, user: UserDep, params: PageParams = Depends(), is_read: int | None = None
):
    """我的消息（默认倒序，可按已读状态过滤）。"""
    conds = [SysMessage.receiver_id == user.id, SysMessage.del_flag == 0]
    if is_read is not None:
        conds.append(SysMessage.is_read == is_read)
    total = await db.scalar(select(func.count()).select_from(SysMessage).where(*conds))
    rows = await db.scalars(
        select(SysMessage).where(*conds).order_by(SysMessage.id.desc())
        .offset(params.offset).limit(params.limit)
    )
    return PageData.build(total, params, [MessageOut.model_validate(m) for m in rows])


@router.get("/unread-count")
async def unread_count(db: DbDep, user: UserDep):
    n = await db.scalar(
        select(func.count())
        .select_from(SysMessage)
        .where(SysMessage.receiver_id == user.id, SysMessage.is_read == 0)
    )
    return {"count": n or 0}


@router.post("/{mid}/read")
async def read_one(mid: int, db: DbDep, user: UserDep):
    m = await db.get(SysMessage, mid)
    if not m or m.del_flag == 1 or m.receiver_id != user.id:
        raise HTTPException(404, "消息不存在")
    m.is_read = 1
    m.update_by = user.id
    return {"ok": True}


@router.post("/read-all")
async def read_all(db: DbDep, user: UserDep):
    result = await db.execute(
        update(SysMessage)
        .where(SysMessage.receiver_id == user.id, SysMessage.is_read == 0)
        .values(is_read=1, update_by=user.id)
    )
    return {"ok": True, "count": result.rowcount or 0}


@router.get("/subscribe")
async def subscribe_messages(user: UserDep):
    """SSE 端点：订阅实时消息推送。
    
    前端使用 EventSource 连接，当有新消息时会收到推送。
    """
    user_id = user.id

    async def event_generator() -> AsyncGenerator[str, None]:
        """SSE 事件生成器。"""
        queue: asyncio.Queue = asyncio.Queue()
        msg._message_subscribers[user_id] = queue
        try:
            # 发送初始连接成功消息
            yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"
            
            # 持续监听新消息
            while True:
                try:
                    # 等待新消息，超时30秒发送心跳
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            # 连接关闭时清理订阅者
            if msg._message_subscribers.get(user_id) is queue:
                del msg._message_subscribers[user_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
