"""资产履历服务（方案 P0-3）：任何状态/归属/位置变动写入流水，只增不改。"""
import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssAsset, AssAssetLog

# 履历动作类型
ACTION_STOCK_IN = 1
ACTION_RECEIVE = 2
ACTION_RETURN = 3
ACTION_TRANSFER = 4
ACTION_REPAIR = 5
ACTION_CHECK = 6
ACTION_DEPRECIATION = 7
ACTION_SCRAP = 8
ACTION_DISPOSE = 9
ACTION_MODIFY = 10
ACTION_BORROW = 11

SNAPSHOT_FIELDS = (
    "status", "org_id", "project_id", "warehouse_id", "space_id",
    "location_detail", "use_user_id", "use_dept_id", "group_id",
)


def snapshot(asset: AssAsset) -> dict:
    return {f: getattr(asset, f) for f in SNAPSHOT_FIELDS}


async def write_log(
    db: AsyncSession,
    asset: AssAsset,
    action_type: int,
    biz_type: str | None = None,
    biz_id: int | None = None,
    before: dict | None = None,
    operator_id: int | None = None,
) -> None:
    after = snapshot(asset)
    log = AssAssetLog(
        asset_id=asset.id,
        action_type=action_type,
        biz_type=biz_type,
        biz_id=biz_id,
        before_snapshot=json.dumps(before, ensure_ascii=False, default=str) if before else None,
        after_snapshot=json.dumps(after, ensure_ascii=False, default=str),
        operator_id=operator_id,
        operate_time=datetime.now(),
    )
    db.add(log)


async def write_logs(
    db: AsyncSession,
    assets: list[AssAsset],
    action_type: int,
    biz_type: str | None = None,
    biz_id: int | None = None,
    befores: list[dict] | None = None,
    operator_id: int | None = None,
) -> None:
    for i, asset in enumerate(assets):
        before = befores[i] if befores else None
        await write_log(db, asset, action_type, biz_type, biz_id, before, operator_id)
