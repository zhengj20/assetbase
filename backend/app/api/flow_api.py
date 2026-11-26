"""审批流可视化配置 API（三期：新建流程 + 关联单据 + 分支条件 + 会签/或签）。

- 流程 = 名称 + 关联单据类型 + 可选分支条件 + 节点列表（节点支持单签/或签/会签，审批人=角色∪用户）
- 同单据类型可建多条流程：发起时按 priority + 条件匹配
- 保存即生成新版本并启用同流程旧版本停用；在途实例仍按发起时版本执行（方案 1.4）
"""
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, DbDep, UserDep, require_perm
from app.models.check import WfBizApprovalConfig, WfDefinition, WfInstance
from app.models.sys import SysRole, SysUser
from app.services.workflow_service import (
    BIZ_TYPES,
    COND_OPS,
    DEFAULT_FLOWS,
    normalize_nodes,
    parse_branches,
)

router = APIRouter(prefix="/flows", tags=["审批流配置"])

MAX_NODES = 8
MAX_BRANCHES = 6


class ApproverIn(BaseModel):
    type: str = Field(pattern="^(role|user)$", description="role 角色 / user 指定用户")
    code: str | None = Field(default=None, description="角色编码")
    id: int | None = Field(default=None, description="用户ID")


class FlowNodeIn(BaseModel):
    name: str = Field(max_length=100)
    mode: str = Field(default="single", pattern="^(single|any|all)$", description="single单人 any或签 all会签")
    approvers: list[ApproverIn] = Field(min_length=1)


class FlowCondIn(BaseModel):
    field: str
    op: str
    value: float | int | str


class FlowBranchIn(BaseModel):
    name: str | None = Field(default=None, max_length=50, description="分支名称")
    condition: FlowCondIn | None = Field(default=None, description="分支条件；空=默认分支（兜底）")
    nodes: list[FlowNodeIn] = Field(min_length=1)


class FlowIn(BaseModel):
    flow_name: str = Field(min_length=1, max_length=100)
    biz_type: str
    condition: FlowCondIn | None = None
    priority: int = Field(default=100, ge=1, le=9999)
    nodes: list[FlowNodeIn] | None = Field(default=None, description="v2 单分支流程（兼容旧版）")
    branches: list[FlowBranchIn] | None = Field(default=None, description="v3 多分支：一条流程按分支条件路由到不同审批链")


class BizApprovalCfgIn(BaseModel):
    flow_enabled: int = Field(ge=0, le=1, description="1启用审批流 0手动审批")


def _def_out(d: WfDefinition) -> dict:
    cond = None
    if d.condition_json:
        try:
            cond = json.loads(d.condition_json)
        except ValueError:
            cond = None
    branches = parse_branches(d.flow_json)
    nodes = normalize_nodes(d.flow_json)
    if not nodes and branches:
        nodes = next((b["nodes"] for b in branches if not b.get("condition")), branches[0]["nodes"])
    return {
        "id": d.id,
        "flow_key": d.flow_key,
        "def_name": d.def_name,
        "flow_name": d.flow_name,
        "biz_type": d.biz_type,
        "condition": cond,
        "priority": d.priority,
        "version": d.version,
        "status": d.status,
        "nodes": nodes,
        "branches": branches,
        "create_time": d.create_time,
    }


@router.get("")
async def list_flows(db: DbDep, user: UserDep):
    """全部流程定义 + 内置默认流（无自定义时展示，只读）+ 配置元数据。"""
    roles = list(
        await db.scalars(
            select(SysRole).where(SysRole.del_flag == 0, SysRole.status == 1).order_by(SysRole.id)
        )
    )
    users = list(
        await db.scalars(
            select(SysUser).where(SysUser.del_flag == 0, SysUser.status == 1).order_by(SysUser.id)
        )
    )
    defs = list(
        await db.scalars(
            select(WfDefinition)
            .where(WfDefinition.del_flag == 0)
            .order_by(WfDefinition.biz_type, WfDefinition.priority, WfDefinition.id)
        )
    )
    flows = [_def_out(d) for d in defs]

    # 无自定义流程的单据类型 → 展示内置默认流（def_id=0，只读）
    covered = {d.biz_type for d in defs}
    for key, meta in BIZ_TYPES.items():
        if key in covered:
            continue
        nodes = normalize_nodes(DEFAULT_FLOWS.get(key, []))
        if not nodes:
            continue
        flows.append(
            {
                "id": 0, "flow_key": f"default_{key}", "def_name": f"{meta['label']}（内置）",
                "flow_name": meta["label"], "biz_type": key, "condition": None,
                "priority": 9999, "version": 1, "status": 1, "nodes": nodes,
                "branches": [{"name": "默认", "condition": None, "nodes": nodes}],
                "create_time": None,
            }
        )
    flows.sort(key=lambda f: (f["biz_type"], f["priority"], f["id"]))

    return {
        "flows": flows,
        "roles": [{"id": r.id, "role_code": r.role_code, "role_name": r.role_name} for r in roles],
        "users": [{"id": u.id, "real_name": u.real_name, "username": u.username} for u in users],
        "biz_types": [
            {"key": k, "label": m["label"], "fields": m.get("fields", {})} for k, m in BIZ_TYPES.items()
        ],
        "cond_ops": [{"op": k, "label": v[0]} for k, v in COND_OPS.items()],
    }


@router.get("/approval-config")
async def get_biz_approval_config(db: DbDep, user: UserDep):
    """各单据类型审批方式（启用审批流 / 手动审批），无记录默认启用。"""
    rows = (
        await db.scalars(select(WfBizApprovalConfig).where(WfBizApprovalConfig.del_flag == 0))
    ).all()
    cfg = {r.biz_type: r.flow_enabled for r in rows}
    return {
        "configs": [
            {
                "biz_type": k,
                "label": BIZ_TYPES[k]["label"],
                "flow_enabled": 1 if cfg.get(k, 1) else 0,
            }
            for k in BIZ_TYPES
        ]
    }


@router.put("/approval-config/{biz_type}")
async def set_biz_approval_config(
    biz_type: str,
    body: BizApprovalCfgIn,
    db: DbDep,
    user: UserDep,
    _p: Annotated[CurrentUser, Depends(require_perm("flow:config"))],
):
    """设置单据类型审批方式：1启用审批流 / 0关闭(单据页手动审批通过)。"""
    if biz_type not in BIZ_TYPES:
        raise HTTPException(400, f"未知单据类型: {biz_type}")
    if body.flow_enabled not in (0, 1):
        raise HTTPException(400, "flow_enabled 仅支持 0/1")
    cfg = await db.scalar(
        select(WfBizApprovalConfig).where(
            WfBizApprovalConfig.biz_type == biz_type, WfBizApprovalConfig.del_flag == 0
        )
    )
    if not cfg:
        cfg = WfBizApprovalConfig(biz_type=biz_type, flow_enabled=body.flow_enabled, create_by=user.id)
        db.add(cfg)
    else:
        cfg.flow_enabled = body.flow_enabled
        cfg.update_by = user.id
    await db.flush()
    return {"biz_type": biz_type, "flow_enabled": body.flow_enabled}


async def _validate_flow(body: FlowIn, db) -> None:
    if body.biz_type not in BIZ_TYPES:
        raise HTTPException(400, f"未知单据类型: {body.biz_type}")
    if body.branches:
        if len(body.branches) > MAX_BRANCHES:
            raise HTTPException(400, f"最多设置 {MAX_BRANCHES} 个分支")
        if not any(b.condition is None for b in body.branches):
            raise HTTPException(400, "请至少设置一个默认分支（关闭分支条件）")
        brs = [(b.name or f"分支{i + 1}", b.condition, b.nodes) for i, b in enumerate(body.branches)]
    else:
        if not body.nodes:
            raise HTTPException(400, "请至少设置一个审批节点")
        brs = [("默认", body.condition, body.nodes)]
    fields = BIZ_TYPES[body.biz_type].get("fields", {})
    role_codes = {
        r.role_code for r in await db.scalars(select(SysRole).where(SysRole.del_flag == 0))
    }
    user_ids = {
        u.id for u in await db.scalars(select(SysUser).where(SysUser.del_flag == 0, SysUser.status == 1))
    }
    for br_name, cond, nodes in brs:
        if len(nodes) > MAX_NODES:
            raise HTTPException(400, f"分支「{br_name}」最多 {MAX_NODES} 个审批节点")
        if cond:
            if cond.field not in fields:
                raise HTTPException(400, f"该单据类型不支持条件字段: {cond.field}")
            if cond.op not in COND_OPS:
                raise HTTPException(400, f"未知条件操作: {cond.op}")
        names = []
        for n in nodes:
            if not n.name.strip():
                raise HTTPException(400, f"分支「{br_name}」存在空节点名称")
            names.append(n.name.strip())
            for ap in n.approvers:
                if ap.type == "role" and ap.code not in role_codes:
                    raise HTTPException(400, f"分支「{br_name}」角色不存在: {ap.code}")
                if ap.type == "user" and ap.id not in user_ids:
                    raise HTTPException(400, f"分支「{br_name}」审批用户不存在或已停用: {ap.id}")
        if len(set(names)) != len(names):
            raise HTTPException(400, f"分支「{br_name}」内节点名称不能重复")


def _node_out(n: FlowNodeIn, i: int) -> dict:
    return {
        "id": f"n{i + 1}", "name": n.name.strip(), "mode": n.mode,
        "approvers": [a.model_dump(exclude_none=True) for a in n.approvers],
    }


def _flow_payload(body: FlowIn) -> dict:
    if body.branches:
        branches = [
            {
                "name": b.name or f"分支{i + 1}",
                "condition": (
                    {"field": b.condition.field, "op": b.condition.op, "value": b.condition.value}
                    if b.condition else None
                ),
                "nodes": [_node_out(n, j) for j, n in enumerate(b.nodes)],
            }
            for i, b in enumerate(body.branches)
        ]
        return {
            "flow_json": json.dumps({"version": 3, "branches": branches}, ensure_ascii=False),
            "condition_json": None,
            "priority": body.priority,
        }
    nodes = [_node_out(n, i) for i, n in enumerate(body.nodes)]
    return {
        "flow_json": json.dumps({"version": 2, "nodes": nodes}, ensure_ascii=False),
        "condition_json": (
            json.dumps({"field": body.condition.field, "op": body.condition.op,
                        "value": body.condition.value}, ensure_ascii=False)
            if body.condition else None
        ),
        "priority": body.priority,
    }


async def _create_version(db, body: FlowIn, flow_key: str, version: int, user) -> WfDefinition:
    payload = _flow_payload(body)
    return WfDefinition(
        flow_key=flow_key,
        def_name=f"{body.flow_name.strip()} v{version}",
        flow_name=body.flow_name.strip(),
        biz_type=body.biz_type,
        flow_json=payload["flow_json"],
        condition_json=payload["condition_json"],
        priority=payload["priority"],
        version=version,
        status=1,
        create_by=user.id,
    )


@router.post("")
async def create_flow(body: FlowIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("flow:config"))]):
    """新建流程（启用），关联指定单据类型，可带分支条件。"""
    await _validate_flow(body, db)
    d = await _create_version(db, body, f"fl_{uuid.uuid4().hex[:12]}", 1, user)
    db.add(d)
    await db.flush()
    return _def_out(d)


@router.put("/{def_id}")
async def save_flow(def_id: int, body: FlowIn, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("flow:config"))]):
    """保存为新版本并启用；同流程旧版本停用（在途实例不受影响）。"""
    old = await db.get(WfDefinition, def_id)
    if not old or old.del_flag == 1:
        raise HTTPException(404, "流程不存在")
    await _validate_flow(body, db)
    max_ver = await db.scalar(
        select(func.max(WfDefinition.version)).where(WfDefinition.flow_key == old.flow_key)
    ) or old.version
    for d in (
        await db.scalars(
            select(WfDefinition).where(
                WfDefinition.flow_key == old.flow_key, WfDefinition.del_flag == 0
            )
        )
    ).all():
        d.status = 0
        d.update_by = user.id
    d = await _create_version(db, body, old.flow_key, max_ver + 1, user)
    db.add(d)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "该流程正被其他人保存，请刷新后重试")
    return _def_out(d)


@router.post("/{def_id}/status")
async def set_flow_status(def_id: int, status: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("flow:config"))]):
    """启用/停用流程（同单据类型可多条流程并存，按条件分流）。"""
    if status not in (0, 1):
        raise HTTPException(400, "status 仅支持 0/1")
    d = await db.get(WfDefinition, def_id)
    if not d or d.del_flag == 1:
        raise HTTPException(404, "流程不存在")
    d.status = status
    d.update_by = user.id
    return {"id": d.id, "status": status}


@router.delete("/{def_id}")
async def delete_flow(def_id: int, db: DbDep, user: UserDep, _p: Annotated[CurrentUser, Depends(require_perm("flow:config"))]):
    """删除流程（软删）；存在审批中的实例时禁止删除。"""
    d = await db.get(WfDefinition, def_id)
    if not d or d.del_flag == 1:
        raise HTTPException(404, "流程不存在")
    running = await db.scalar(
        select(func.count()).select_from(WfInstance).where(
            WfInstance.def_id == def_id, WfInstance.status == 1
        )
    )
    if running:
        raise HTTPException(400, f"该流程有 {running} 个审批中的实例，不能删除")
    d.del_flag = 1
    d.update_by = user.id
    return {"ok": True}
