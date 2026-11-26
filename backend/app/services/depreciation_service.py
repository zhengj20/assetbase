"""折旧按月计提/反结账服务（方案 6.7：平均年限法）。

计提：按资产所属分类的折旧年限(月)与净残值，月折旧 = (原值-残值)/折旧月数，
最后一期提足；每期生成 ass_depreciation 记录（未结账），并回写资产累计折旧/净值。
反结账：仅允许对未结账期间，冲回当月记录并恢复资产折旧状态。
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.archive import AssCategory
from app.models.asset import AssAsset
from app.models.check import AssDepreciation
from app.services.asset_log_service import ACTION_DEPRECIATION, snapshot, write_log

TWO = Decimal("0.01")


def _scope(user) -> list:
    conds = [AssAsset.del_flag == 0]
    if user.org_ids is None:
        return conds
    if not user.org_ids:
        conds.append(AssAsset.create_by == user.id)
    else:
        conds.append(AssAsset.org_id.in_(user.org_ids))
    return conds


async def _check_period(db, period: str) -> None:
    n = await db.scalar(
        select(func.count()).select_from(AssDepreciation).where(AssDepreciation.period == period)
    )
    if n:
        raise HTTPException(400, f"期间 {period} 已有 {n} 条计提记录，如需重提请先反结账")


async def calculate(db, user, period: str | None = None) -> dict:
    period = period or date.today().strftime("%Y%m")
    if not (len(period) == 6 and period.isdigit()):
        raise HTTPException(400, "期间格式应为 YYYYMM")
    await _check_period(db, period)

    cat_rows = (await db.execute(
        select(AssCategory.id, AssCategory.parent_id, AssCategory.depreciate_month, AssCategory.residual_rate)
        .where(AssCategory.del_flag == 0)
    )).all()
    cats = {r[0]: r for r in cat_rows}

    def _resolve(cat_id: int):
        """向上溯取首个配置了折旧年限的祖先分类。"""
        seen: set = set()
        cur = cat_id
        while cur and cur in cats and cur not in seen:
            seen.add(cur)
            r = cats[cur]
            if r[2]:
                return int(r[2]), (r[3] or Decimal(0))
            cur = r[1] or 0
        return None

    months_map: dict = {}
    rate_map: dict = {}
    for cid in cats:
        r = _resolve(cid)
        if r:
            months_map[cid] = r[0]
            rate_map[cid] = r[1]
    if not months_map:
        raise HTTPException(400, "未找到已配置折旧年限的分类，请先在「资产分类」配置折旧年限")

    res = await db.execute(select(AssAsset).where(
        *_scope(user),
        AssAsset.status.not_in((5, 6)),
        AssAsset.dep_status.in_((0, 1)),
        AssAsset.price.isnot(None),
        AssAsset.category_id.in_(list(months_map)),
    ))
    assets = list(res.scalars())

    processed = skipped = 0
    amount = Decimal("0")
    for a in assets:
        months = months_map[a.category_id]
        residual = (
            a.residual_value
            if a.residual_value is not None
            else (a.price * (rate_map[a.category_id] or Decimal(0)) / Decimal(100)).quantize(TWO, ROUND_HALF_UP)
        )
        depreciable = a.price - residual
        if depreciable <= 0:
            continue
        prev = (a.accum_depreciation or Decimal(0))
        monthly = (depreciable / months).quantize(TWO, ROUND_HALF_UP)
        monthly = min(monthly, depreciable - prev)
        if monthly <= 0:
            continue
        acc = prev + monthly
        net = (a.price - acc).quantize(TWO, ROUND_HALF_UP)
        before = snapshot(a)
        a.accum_depreciation = acc
        a.net_value = net
        a.dep_status = 2 if acc >= depreciable else 1
        a.update_by = user.id
        db.add(AssDepreciation(period=period, asset_id=a.id, orig_value=a.price, monthly_dep=monthly,
                               accum_dep=acc, net_value=net, status=0))
        await write_log(db, a, ACTION_DEPRECIATION, biz_type="depreciation", before=before, operator_id=user.id)
        processed += 1
        amount += monthly

    if processed:
        await db.flush()
    return {"period": period, "processed": processed, "skipped": len(assets) - processed,
            "amount": float(amount), "status": 0}


async def reverse(db, user, period: str) -> dict:
    if not (len(period) == 6 and period.isdigit()):
        raise HTTPException(400, "期间格式应为 YYYYMM")
    # 行锁串行化并发反结账，避免同一期间被重复冲回
    records = list((await db.execute(
        select(AssDepreciation).where(AssDepreciation.period == period).order_by(AssDepreciation.asset_id)
        .with_for_update()
    )).scalars())
    if not records:
        raise HTTPException(400, f"期间 {period} 无计提记录")
    locked = [r for r in records if r.status == 1]
    if locked:
        raise HTTPException(400, f"期间 {period} 已有 {len(locked)} 条记录已结账，请先执行「反结账（解锁）」再冲回")

    reversed_amount = Decimal("0")
    for r in records:
        a = list(await db.scalars(
            select(AssAsset).where(AssAsset.id == r.asset_id).with_for_update()
        ))
        if not a:
            raise HTTPException(400, f"资产ID {r.asset_id} 不存在或已删除")
        a = a[0]
        if a.del_flag == 1:
            raise HTTPException(400, f"资产ID {r.asset_id} 不存在或已删除")
        before = snapshot(a)
        amt = min(r.monthly_dep or Decimal(0), a.accum_depreciation or Decimal(0))
        a.accum_depreciation = (a.accum_depreciation or Decimal(0)) - amt
        a.net_value = (a.price + amt).quantize(TWO, ROUND_HALF_UP) if a.price is not None else None
        a.dep_status = 0
        a.update_by = user.id
        await write_log(db, a, ACTION_DEPRECIATION, biz_type="depreciation_reverse", before=before, operator_id=user.id)
        await db.delete(r)
        reversed_amount += amt
    await db.flush()
    return {"period": period, "count": len(records), "amount": float(reversed_amount)}
