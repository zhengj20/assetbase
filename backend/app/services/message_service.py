"""消息通知服务（方案模块7：站内信/待办推送）。"""
import asyncio
from datetime import datetime

from app.models.sys import SysMessage

# SSE 消息事件订阅器（简单实现：内存中的订阅者列表）
_message_subscribers: dict[int, asyncio.Queue] = {}


def notify_user(user_id: int, message: dict) -> bool:
    """通知指定用户有新消息（供其他模块调用）。"""
    queue = _message_subscribers.get(user_id)
    if queue is not None:
        queue.put_nowait(message)
        return True
    return False


async def send(
    db,
    receiver_id: int | None,
    title: str,
    content: str | None = None,
    msg_type: int = 1,
    biz_type: str | None = None,
    biz_id: int | None = None,
    sender_id: int | None = None,
) -> SysMessage | None:
    """写一条站内信（随当前事务提交；receiver 为空则忽略）。"""
    if not receiver_id:
        return None
    m = SysMessage(
        msg_type=msg_type,
        title=title,
        content=content,
        receiver_id=receiver_id,
        biz_type=biz_type,
        biz_id=biz_id,
        is_read=0,
        send_time=datetime.now(),
        create_by=sender_id or 0,  # 系统发送时为0，否则为发送者ID
    )
    db.add(m)
    await db.flush()
    notify_user(receiver_id, {
        "type": "new_message",
        "id": m.id,
        "title": title,
        "content": content,
        "msg_type": msg_type,
        "biz_type": biz_type,
        "biz_id": biz_id,
    })
    return m
