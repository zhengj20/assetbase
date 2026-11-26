"""首页驾驶舱 API（方案模块2）：指标卡 + 分布统计 + 趋势 + 业务预警。"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import and_, case, func, select

from app.core.deps import DbDep, UserDep
from app.models.archive import AssCategory, AssSpace
from app.models.asset import AssAsset
from app.models.check import AssCheckTask, WfInstance, WfTask
from app.models.consumable import ConIssue, ConIssueItem, ConItem, ConPurchase, ConStock
from app.models.doc import AssStockIn, AssTransfer
from app.models.sys import SysOrg

router = APIRouter(prefix="/dashboard", tags=["驾驶舱"])


def _asset_scope(user):
    conds = [AssAsset.del_flag == 0]
    if user.org_ids is None:
        return conds
    if not user.org_ids:
        conds.append(
            (AssAsset.use_user_id == user.id) | (AssAsset.create_by == user.id)
        )
        return conds
    from sqlalchemy import or_

    conds.append(
        or_(AssAsset.org_id.in_(user.org_ids), AssAsset.project_id.in_(user.org_ids))
    )
    return conds


@router.get("")
async def dashboard(db: DbDep, user: UserDep):
    conds = _asset_scope(user)
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ---- 核心指标卡 ----
    row = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(case((AssAsset.status == 1, 1), else_=0)).label("in_stock"),
                func.sum(case((AssAsset.status == 2, 1), else_=0)).label("in_use"),
                func.sum(case((AssAsset.status == 4, 1), else_=0)).label("in_transfer"),
                func.coalesce(func.sum(AssAsset.price), 0).label("orig_value"),
                func.coalesce(func.sum(AssAsset.net_value), 0).label("net_value"),
            ).where(*conds)
        )
    ).one()

    # 本月新增 / 报废
    new_month = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            *conds, AssAsset.create_time >= month_start
        )
    )
    scrap_month = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            *conds, AssAsset.status.in_([5, 6]), AssAsset.update_time >= month_start
        )
    )

    # 待办审批数
    todo_count = await db.scalar(
        select(func.count())
        .select_from(WfTask)
        .join(WfInstance, WfInstance.id == WfTask.instance_id)
        .where(
            WfTask.assignee_id == user.id,
            WfTask.action.is_(None),
            WfInstance.status == 1,
        )
    )

    # ---- 地产行业特色指标（方案 P2-5） ----
    # 呆滞资产：在库超 180 天未领用
    stale_days = now - timedelta(days=180)
    stale = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            *conds, AssAsset.status == 1, AssAsset.create_time <= stale_days
        )
    )
    total_count = row.total or 0
    # 清盘待处置：已清盘空间内未处置资产
    clearing = await db.scalar(
        select(func.count())
        .select_from(AssAsset)
        .join(AssSpace, AssSpace.id == AssAsset.space_id)
        .where(*conds, AssSpace.space_status == 4, AssAsset.status.notin_([5, 6]))
    )
    # 样板间资产闲置率：样板间空间内在库 / 样板间资产总数
    sample_total = await db.scalar(
        select(func.count())
        .select_from(AssAsset)
        .join(AssSpace, AssSpace.id == AssAsset.space_id)
        .where(*conds, AssSpace.space_type == 2)
    )
    sample_idle = await db.scalar(
        select(func.count())
        .select_from(AssAsset)
        .join(AssSpace, AssSpace.id == AssAsset.space_id)
        .where(*conds, AssSpace.space_type == 2, AssAsset.status == 1)
    )
    # 资产复用率：可复用标记资产占存活资产比例
    reusable = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            *conds, AssAsset.is_reusable == 1, AssAsset.status.notin_([5, 6])
        )
    )

    # ---- 易耗品指标（con 域无组织权限过滤，与 con 模块列表口径一致） ----
    # 库存金额：库存余额 数量 × 成本单价
    con_stock_value = await db.scalar(
        select(func.coalesce(func.sum(ConStock.qty * ConStock.unit_price), 0)).where(
            ConStock.del_flag == 0
        )
    )
    # 有库存的物料数
    con_sku_count = await db.scalar(
        select(func.count(func.distinct(ConStock.item_id))).where(ConStock.del_flag == 0)
    )
    # 本月领用（已通过单据，按领用日期；distinct 避免 join 明细后单据数翻倍）
    con_issue_month = (
        await db.execute(
            select(
                func.count(func.distinct(ConIssue.id)),
                func.coalesce(func.sum(ConIssueItem.num * ConIssueItem.unit_price), 0),
            )
            .select_from(ConIssue)
            .join(ConIssueItem, ConIssueItem.issue_id == ConIssue.id)
            .where(
                ConIssue.del_flag == 0,
                ConIssue.status == 2,
                ConIssue.issue_date >= month_start.date(),
            )
        )
    ).one()
    # 本月采购（已通过单据，按申请日期）
    con_purchase_month = await db.scalar(
        select(func.coalesce(func.sum(ConPurchase.total_amount), 0)).where(
            ConPurchase.del_flag == 0,
            ConPurchase.status == 2,
            ConPurchase.apply_date >= month_start.date(),
        )
    )
    # 断货：库存余额为 0 的物料数
    con_stockout = await db.scalar(
        select(func.count(func.distinct(ConStock.item_id))).where(
            ConStock.del_flag == 0, ConStock.qty == 0
        )
    )

    # ---- 分布统计 ----
    org_rows = await db.execute(
        select(
            SysOrg.org_name,
            func.count(AssAsset.id),
            func.coalesce(func.sum(AssAsset.price), 0),
        )
        .join(AssAsset, AssAsset.org_id == SysOrg.id)
        .where(*conds)
        .group_by(SysOrg.org_name)
        .order_by(func.count(AssAsset.id).desc())
        .limit(10)
    )
    cat_rows = await db.execute(
        select(
            AssCategory.category_name,
            func.count(AssAsset.id),
        )
        .select_from(AssAsset)
        .join(AssCategory, AssCategory.id == AssAsset.category_id)
        .where(*conds)
        .group_by(AssCategory.category_name)
        .order_by(func.count(AssAsset.id).desc())
    )

    # 近 6 个月增减趋势（固定资产新增 + 易耗品领用金额）
    trend = []
    for i in range(5, -1, -1):
        d = (now.replace(day=1) - timedelta(days=30 * i))
        start = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i == 0:
            end = now
        else:
            end = (start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        added = await db.scalar(
            select(func.count()).select_from(AssAsset).where(
                *conds, AssAsset.create_time >= start, AssAsset.create_time < end
            )
        )
        # 当月含今日（日期列无时分秒，i==0 时 end 为当前时刻，需 <= 才不漏当天）
        end_cond = ConIssue.issue_date <= now.date() if i == 0 else ConIssue.issue_date < end.date()
        con_amount = await db.scalar(
            select(func.coalesce(func.sum(ConIssueItem.num * ConIssueItem.unit_price), 0))
            .select_from(ConIssue)
            .join(ConIssueItem, ConIssueItem.issue_id == ConIssue.id)
            .where(
                ConIssue.del_flag == 0,
                ConIssue.status == 2,
                ConIssue.issue_date >= start.date(),
                end_cond,
            )
        )
        trend.append({"month": f"{d:%Y-%m}", "added": added or 0, "con_amount": float(con_amount or 0)})

    # 易耗品领用 Top10（近 6 个月，按金额）
    top_start = (now.replace(day=1) - timedelta(days=30 * 5)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    top_rows = (
        await db.execute(
            select(ConItem.item_name, func.coalesce(func.sum(ConIssueItem.num * ConIssueItem.unit_price), 0))
            .select_from(ConIssue)
            .join(ConIssueItem, ConIssueItem.issue_id == ConIssue.id)
            .join(ConItem, ConItem.id == ConIssueItem.item_id)
            .where(
                ConIssue.del_flag == 0,
                ConIssue.status == 2,
                ConIssue.issue_date >= top_start.date(),
            )
            .group_by(ConItem.item_name)
            .order_by(func.coalesce(func.sum(ConIssueItem.num * ConIssueItem.unit_price), 0).desc())
            .limit(10)
        )
    ).all()

    # ---- 业务预警 ----
    alerts: list[dict] = []
    # 呆滞预警
    if stale:
        alerts.append({"type": "stale", "level": "warning", "message": f"呆滞资产预警：{stale} 项在库超180天未领用"})
    # 保修到期预警（30天内）
    warranty_end = now.date() + timedelta(days=30)
    warranty = await db.scalar(
        select(func.count()).select_from(AssAsset).where(
            *conds,
            AssAsset.warranty_end.is_not(None),
            AssAsset.warranty_end <= warranty_end,
            AssAsset.status.notin_([5, 6]),
        )
    )
    if warranty:
        alerts.append({"type": "warranty", "level": "info", "message": f"保修到期预警：{warranty} 项资产30天内保修到期"})
    # 盘点逾期
    overdue = await db.scalar(
        select(func.count()).select_from(AssCheckTask).where(
            AssCheckTask.status.in_([0, 1]),
            AssCheckTask.plan_end < now.date(),
            AssCheckTask.del_flag == 0,
        )
    )
    if overdue:
        alerts.append({"type": "check_overdue", "level": "danger", "message": f"盘点逾期预警：{overdue} 个任务已超计划完成日期"})
    # 易耗品断货预警
    if con_stockout:
        alerts.append({"type": "con_stockout", "level": "danger", "message": f"易耗品断货预警：{con_stockout} 项物料库存为0，请及时补货"})
    if todo_count:
        alerts.append({"type": "todo", "level": "info", "message": f"待办审批：{todo_count} 条待你审批"})

    return {
        "cards": {
            "total": total_count,
            "orig_value": float(row.orig_value or 0),
            "net_value": float(row.net_value or 0),
            "in_stock": row.in_stock or 0,
            "in_use": row.in_use or 0,
            "in_transfer": row.in_transfer or 0,
            "new_month": new_month or 0,
            "scrap_month": scrap_month or 0,
            "todo_count": todo_count or 0,
        },
        "estate_metrics": {
            "stale_count": stale or 0,
            "stale_ratio": round((stale or 0) / total_count, 4) if total_count else 0,
            "clearing_pending": clearing or 0,
            "sample_idle_ratio": round((sample_idle or 0) / sample_total, 4) if sample_total else 0,
            "reusable_ratio": round((reusable or 0) / total_count, 4) if total_count else 0,
        },
        "con_metrics": {
            "stock_value": float(con_stock_value or 0),
            "sku_count": con_sku_count or 0,
            "issue_month_num": con_issue_month[0] or 0,
            "issue_month_amount": float(con_issue_month[1] or 0),
            "purchase_month_amount": float(con_purchase_month or 0),
            "stockout_count": con_stockout or 0,
        },
        "org_distribution": [
            {"name": r[0], "count": r[1], "value": float(r[2] or 0)} for r in org_rows
        ],
        "category_distribution": [
            {"name": r[0], "count": r[1]} for r in cat_rows
        ],
        "trend": trend,
        "con_top_items": [
            {"name": r[0], "amount": float(r[1] or 0)} for r in top_rows
        ],
        "alerts": alerts,
    }
