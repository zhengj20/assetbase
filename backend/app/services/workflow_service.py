"""工作流服务（三期：可视化流程 + 分支条件 + 会签/或签 + 加签）。

流程定义 v2（wf_definition.flow_json）：
    {"version": 2, "nodes": [
        {"id": "n1", "name": "财务审核", "mode": "single|any|all",
         "approvers": [{"type": "role", "code": "finance"}, {"type": "user", "id": 5}]}
    ]}
- mode=single 单人审批（取第一个匹配审批人）；any 或签（任一人通过即过）；all 会签（全部通过才过）
- 同 biz_type 可配多条启用流程：发起时按 priority 升序 + condition_json 匹配，
  无条件流程兜底；无定义时回退内置默认流（方案 1.4 流程版本管理不变，在途实例按发起时版本执行）
"""
import json
import operator
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.check import WfBizApprovalConfig, WfDefinition, WfInstance, WfTask
from app.models.doc import AssBorrow, AssPurchaseApply, AssReturn, AssScrap, AssStockIn, AssStockOut, AssTransfer
from app.models.consumable import ConInbound, ConIssue, ConPurchase
from app.models.sys import SysRole, SysUser, SysUserRole

# 单据类型 → 单据模型（分支路由时按实例回查单据取值）
DOC_MODELS: dict[str, type] = {
    "purchase": AssPurchaseApply,
    "stock_in": AssStockIn,
    "stock_out": AssStockOut,
    "transfer": AssTransfer,
    "borrow": AssBorrow,
    "return": AssReturn,
    "scrap": AssScrap,
    "con_purchase": ConPurchase,
    "con_inbound": ConInbound,
    "con_issue": ConIssue,
}

# 内置默认流（无自定义定义时兜底；purchase_high 用于采购高额）
DEFAULT_FLOWS: dict[str, list[dict]] = {
    "purchase": [
        {"name": "领导审批", "role_code": "approver"},
    ],
    "purchase_high": [
        {"name": "财务审核", "role_code": "finance"},
        {"name": "领导审批", "role_code": "approver"},
    ],
    "stock_in": [{"name": "资产管理员审批", "role_code": "project_asset"}],
    "stock_out": [{"name": "资产管理员审批", "role_code": "project_asset"}],
    "transfer": [{"name": "资产管理员审批", "role_code": "project_asset"}],
    "borrow": [{"name": "资产管理员审批", "role_code": "project_asset"}],
    "return": [{"name": "资产管理员审批", "role_code": "project_asset"}],
    "scrap": [
        {"name": "资产管理员核验", "role_code": "project_asset"},
        {"name": "财务审核", "role_code": "finance"},
        {"name": "领导审批", "role_code": "approver"},
    ],
    "con_purchase": [{"name": "领导审批", "role_code": "approver"}],
    "con_inbound": [{"name": "资产管理员审批", "role_code": "project_asset"}],
    "con_issue": [{"name": "资产管理员审批", "role_code": "project_asset"}],
}

# 单据类型 → 标签 / 可用作分支条件的单据字段（value 为字段中文标签）
BIZ_TYPES: dict[str, dict] = {
    "purchase": {"label": "采购申请单", "fields": {"total_amount": "总金额"}},
    "stock_in": {"label": "入库单", "fields": {"total_price": "总金额", "total_num": "总数量"}},
    "stock_out": {"label": "领用出库单", "fields": {"total_num": "总数量"}},
    "transfer": {"label": "调拨单", "fields": {"transfer_type": "调拨类型"}},
    "borrow": {"label": "借用单", "fields": {"expected_return_date": "预计归还日期"}},
    "return": {"label": "归还单"},
    "scrap": {"label": "报废处置单", "fields": {"dispose_type": "处置方式", "dispose_income": "处置收入"}},
    "con_purchase": {"label": "易耗品采购单", "fields": {"total_amount": "总金额"}},
    "con_inbound": {"label": "易耗品入库单", "fields": {"total_num": "总数量"}},
    "con_issue": {"label": "易耗品领用单", "fields": {"total_num": "总数量"}},
}

COND_OPS = {
    "eq": ("等于", operator.eq),
    "ne": ("不等于", operator.ne),
    "gt": ("大于", operator.gt),
    "ge": ("大于等于", operator.ge),
    "lt": ("小于", operator.lt),
    "le": ("小于等于", operator.le),
}


def _norm_nodes(raw) -> list[dict]:
    """把原始节点数组（v1/v2 元素）归一为 v2 节点列表。"""
    nodes = []
    for i, n in enumerate(raw):
        if not n or not n.get("name"):
            continue
        if "mode" in n or "approvers" in n:
            nodes.append(
                {
                    "id": n.get("id") or f"n{i + 1}",
                    "name": n["name"],
                    "mode": n.get("mode") or "single",
                    "approvers": n.get("approvers") or [],
                }
            )
        else:  # v1: {name, role_code}
            nodes.append(
                {
                    "id": f"n{i + 1}",
                    "name": n["name"],
                    "mode": "single",
                    "approvers": (
                        [{"type": "role", "code": n["role_code"]}] if n.get("role_code") else []
                    ),
                }
            )
    return nodes


def normalize_nodes(flow_json) -> list[dict]:
    """把 flow_json（v1 节点数组 / v2 对象）归一为 v2 节点列表。"""
    if not flow_json:
        return []
    data = json.loads(flow_json) if isinstance(flow_json, str) else flow_json
    if isinstance(data, dict):
        raw = data.get("nodes") or []
    elif isinstance(data, list):
        raw = data
    else:
        return []
    return _norm_nodes(raw)


def parse_branches(flow_json) -> list[dict]:
    """归一为分支列表 [{name, condition, nodes}]。

    v3 定义含 branches（一条流程内多分支，分支条件路由到不同审批链）；
    v1/v2 定义等价于单个无条件默认分支。
    """
    if not flow_json:
        return []
    data = json.loads(flow_json) if isinstance(flow_json, str) else flow_json
    if isinstance(data, list):
        data = {"nodes": data}
    if not isinstance(data, dict):
        return []
    raw = data.get("branches")
    if raw:
        branches = []
        for i, b in enumerate(raw):
            if not b:
                continue
            branches.append(
                {
                    "name": b.get("name") or f"分支{i + 1}",
                    "condition": b.get("condition") or None,
                    "nodes": _norm_nodes(b.get("nodes") or []),
                }
            )
        return branches
    nodes = _norm_nodes(data.get("nodes") or [])
    return [{"name": "默认", "condition": None, "nodes": nodes}] if nodes else []


def eval_cond(cond, biz_type: str, doc) -> bool:
    """评估单个分支条件是否命中单据（字段缺失/比较失败视为不命中）。"""
    if not cond or doc is None:
        return False
    field, op, value = cond.get("field"), cond.get("op"), cond.get("value")
    if field not in BIZ_TYPES.get(biz_type, {}).get("fields", {}) or op not in COND_OPS:
        return False
    actual = getattr(doc, field, None)
    if actual is None or value is None:
        return False
    try:
        return bool(COND_OPS[op][1](actual, value))
    except TypeError:
        return False


def select_branch(branches: list[dict], biz_type: str, doc) -> dict | None:
    """分支路由：按序命中第一个条件分支；无命中则取无条件默认分支；都没有取首个。"""
    if not branches:
        return None
    for b in branches:
        if b.get("condition") and eval_cond(b["condition"], biz_type, doc):
            return b
    for b in branches:
        if not b.get("condition"):
            return b
    return branches[0]


def eval_condition(defn: WfDefinition, doc) -> bool:
    """评估流程级分支条件是否命中单据（字段缺失/比较失败视为不命中）。"""
    if not defn.condition_json:
        return False
    try:
        cond = json.loads(defn.condition_json)
    except (TypeError, ValueError):
        return False
    return eval_cond(cond, defn.biz_type, doc)


async def match_flow(db: AsyncSession, biz_type: str, doc) -> WfDefinition | None:
    """按 priority 升序匹配启用流程：先命中条件流程，无条件流程兜底。"""
    defs = list(
        await db.scalars(
            select(WfDefinition)
            .where(
                WfDefinition.biz_type == biz_type,
                WfDefinition.status == 1,
                WfDefinition.del_flag == 0,
            )
            .order_by(WfDefinition.priority, WfDefinition.id)
        )
    )
    if not defs:
        return None
    for d in defs:
        if d.condition_json and eval_condition(d, doc):
            return d
    for d in defs:
        if not d.condition_json:
            return d
    return None


async def is_flow_enabled(db: AsyncSession, biz_type: str) -> bool:
    """单据类型是否启用审批流（默认启用，保留既有行为）。

    flow_enabled=0 表示关闭审批流，走单据页「手动审批通过」。
    """
    enabled = await db.scalar(
        select(WfBizApprovalConfig.flow_enabled).where(
            WfBizApprovalConfig.biz_type == biz_type,
            WfBizApprovalConfig.del_flag == 0,
        )
    )
    return enabled != 0


async def _users_of_role(db: AsyncSession, role_code: str) -> list[int]:
    return list(
        await db.scalars(
            select(SysUser.id)
            .join(SysUserRole, SysUserRole.user_id == SysUser.id)
            .join(SysRole, SysRole.id == SysUserRole.role_id)
            .where(SysRole.role_code == role_code, SysUser.status == 1, SysUser.del_flag == 0)
            .order_by(SysUser.id)
        )
    )


async def resolve_approvers(db: AsyncSession, node: dict) -> list[int]:
    """解析节点审批人：role 展开为该角色全部启用用户，user 直取；去重保序。"""
    ids: list[int] = []
    for ap in node.get("approvers") or []:
        if not ap:
            continue
        if ap.get("type") == "user" and ap.get("id"):
            u = await db.get(SysUser, ap["id"])
            if u and u.status == 1 and u.del_flag == 0:
                ids.append(u.id)
        elif ap.get("type") == "role" and ap.get("code"):
            ids.extend(await _users_of_role(db, ap["code"]))
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


async def activate_node(
    db: AsyncSession, instance: WfInstance, nodes: list[dict], idx: int
) -> list[WfTask]:
    """激活第 idx 个节点：按 mode 生成待办任务（single 1 个；any/all 每人 1 个）。"""
    node = nodes[idx]
    mode = node.get("mode") or "single"
    approvers = await resolve_approvers(db, node)
    if not approvers:  # 兜底：角色无人时由管理员处理（一期既有策略）
        approvers = await _users_of_role(db, "admin")
    if not approvers:
        approvers = [0]
    if mode == "single":
        approvers = approvers[:1]
    tasks = []
    for uid in approvers:
        t = WfTask(
            instance_id=instance.id,
            node_key=node.get("id"),
            node_name=node["name"],
            node_order=idx + 1,
            assignee_id=uid,
            arrive_time=datetime.now(),
        )
        db.add(t)
        tasks.append(t)
    instance.current_node = node["name"]
    return tasks


async def start_instance(
    db: AsyncSession,
    biz_type: str,
    biz_id: int,
    doc,
    initiator_id: int | None = None,
) -> WfInstance | None:
    """发起审批：匹配流程（分支条件），创建实例并激活首节点。"""
    definition = await match_flow(db, biz_type, doc)
    if definition:
        branch = select_branch(parse_branches(definition.flow_json), biz_type, doc)
        nodes = (branch or {}).get("nodes") or []
        def_id, def_ver = definition.id, definition.version
        flow_name = definition.flow_name or definition.def_name
    else:
        flow_key = biz_type
        if biz_type == "purchase":
            amount = getattr(doc, "total_amount", None)
            if amount is not None and float(amount) > 50000:
                flow_key = "purchase_high"
        nodes = normalize_nodes(DEFAULT_FLOWS.get(flow_key, []))
        def_id, def_ver = 0, 1
        flow_name = BIZ_TYPES.get(biz_type, {}).get("label", biz_type)
    if not nodes:
        return None

    instance = WfInstance(
        def_id=def_id,
        def_version=def_ver,
        flow_name=flow_name,
        biz_type=biz_type,
        biz_id=biz_id,
        initiator_id=initiator_id,
        status=1,
    )
    db.add(instance)
    await db.flush()
    await activate_node(db, instance, nodes, 0)
    return instance


async def get_instance_nodes(db: AsyncSession, instance: WfInstance, doc=None) -> list[dict]:
    """实例的节点定义（v2 归一；优先取定义表，退化到内置默认流）。

    分支流程按单据取值重新路由（doc 可由调用方传入；未传时按 biz_type/biz_id 回查）。
    """
    if instance.def_id:
        definition = await db.get(WfDefinition, instance.def_id)
        if definition:
            branches = parse_branches(definition.flow_json)
            if branches:
                if doc is None and len(branches) > 1:
                    model = DOC_MODELS.get(instance.biz_type)
                    if model:
                        doc = await db.get(model, instance.biz_id)
                branch = select_branch(branches, instance.biz_type, doc)
                if branch and branch.get("nodes"):
                    return branch["nodes"]
    flow_key = instance.biz_type
    if flow_key == "purchase":
        names = (
            await db.scalars(
                select(WfTask.node_name).where(WfTask.instance_id == instance.id)
            )
        ).all()
        if "财务审核" in names:
            flow_key = "purchase_high"
    return normalize_nodes(DEFAULT_FLOWS.get(flow_key, []))


async def pending_tasks(db: AsyncSession, instance: WfInstance, node: dict) -> list[WfTask]:
    """节点内未完成的任务（node_key 缺失的旧实例按节点名匹配）。"""
    cond = [WfTask.instance_id == instance.id, WfTask.action.is_(None)]
    if node.get("id"):
        cond.append(WfTask.node_key == node["id"])
    else:
        cond.append(WfTask.node_name == node["name"])
    return list(
        await db.scalars(
            select(WfTask).where(*cond).order_by(WfTask.arrive_time, WfTask.id)
        )
    )


def find_node(nodes: list[dict], task: WfTask) -> tuple[int, dict] | None:
    """按 node_key（或节点名）在节点列表中定位 task 所属节点。"""
    for i, n in enumerate(nodes):
        if task.node_key and n.get("id") == task.node_key:
            return i, n
    for i, n in enumerate(nodes):
        if n["name"] == task.node_name:
            return i, n
    return None
