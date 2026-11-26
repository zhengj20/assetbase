"""原子发号服务（多并发核心）。

替代方案中的「Redis 分布式锁」：MySQL `INSERT ... ON DUPLICATE KEY UPDATE
seq_value = seq_value + 1` 原子自增，唯一键行锁天然串行化并发发号，
多 worker / 多节点部署下资产编码与单据号绝不重号，且无需额外基础设施。
"""
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sys import SysCodeSeq


async def next_seq(db: AsyncSession, key: str) -> int:
    """获取 key 的下一个流水号（1 起）。必须在同一事务/连接内执行。"""
    stmt = (
        mysql_insert(SysCodeSeq)
        .values(seq_key=key, seq_value=1)
        .on_duplicate_key_update(seq_value=SysCodeSeq.seq_value + 1)
    )
    await db.execute(stmt)
    # 回读本行当前值而非 LAST_INSERT_ID()：后者在首次 INSERT 分支（行不存在，
    # ON DUPLICATE 不执行）会返回连接上残留的旧值，导致错号且计数器停在 0。
    # upsert 已对唯一键加锁（并发插入/更新阻塞至本事务提交），同事务回读安全。
    result = await db.execute(
        select(SysCodeSeq.seq_value).where(SysCodeSeq.seq_key == key)
    )
    return int(result.scalar_one())


# ---- 单据号前缀（方案单据域）----
DOC_PREFIX = {
    "purchase": "CG",  # 采购申请
    "stock_in": "RK",  # 入库单
    "stock_out": "CK",  # 出库单
    "transfer": "DB",  # 调拨单
    "borrow": "JJ",  # 借用单
    "return": "GH",  # 归还单
    "scrap": "BF",  # 报废处置单
    "check": "PD",  # 盘点任务
    "con_purchase": "YHCG",  # 易耗品采购单
    "con_inbound": "YHRK",  # 易耗品入库单
    "con_issue": "YHLY",  # 易耗品领用单
}


async def next_doc_no(db: AsyncSession, biz_type: str, date_ref=None) -> str:
    """业务单据号：前缀 + 年月 + 4位流水，如 CG2608-0001。"""
    from datetime import datetime

    d = date_ref or datetime.now()
    prefix = DOC_PREFIX.get(biz_type, biz_type[:2].upper())
    ym = f"{d:%y%m}"
    seq = await next_seq(db, f"doc:{biz_type}:{ym}")
    return f"{prefix}{ym}-{seq:04d}"


async def peek_doc_no(db: AsyncSession, biz_type: str, date_ref=None) -> str:
    """预览下一单据号（只读，不消耗流水号），供新建单据页展示「将生成的编号」。"""
    from datetime import datetime

    d = date_ref or datetime.now()
    prefix = DOC_PREFIX.get(biz_type, biz_type[:2].upper())
    ym = f"{d:%y%m}"
    cur = await db.scalar(
        select(SysCodeSeq.seq_value).where(SysCodeSeq.seq_key == f"doc:{biz_type}:{ym}")
    )
    return f"{prefix}{ym}-{(int(cur) + 1 if cur is not None else 1):04d}"


async def next_asset_code(
    db: AsyncSession, org_code: str, category_code: str, date_ref=None
) -> str:
    """资产编码（方案附录A）：公司代码-分类代码-年月-流水号，如 GD-A0201-2608-0001。"""
    from datetime import datetime

    d = date_ref or datetime.now()
    ym = f"{d:%y%m}"
    seq = await next_seq(db, f"asset:{org_code}:{category_code}:{ym}")
    return f"{org_code}-{category_code}-{ym}-{seq:04d}"
