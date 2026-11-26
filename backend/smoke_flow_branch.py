"""冒烟：单流程分支（v3 branches）——解析/路由 + 接口创建/校验/版本。
用法（backend 目录下，后端已运行）：uv run --with httpx python smoke_flow_branch.py
"""
import json
import types

import httpx

BASE = "http://127.0.0.1:5200/api/v1"
PASS = 0
FAIL = 0


def check(name: str, cond, extra: str = ""):
    global PASS, FAIL
    ok = bool(cond)
    print(f"  [{'PASS' if ok else '!!FAIL'}] {name}" + (f" -> {extra}" if extra and not ok else ""))
    PASS, FAIL = PASS + ok, FAIL + (not ok)


def main():
    # ---------- 1) 单元级：解析与路由 ----------
    from app.services.workflow_service import parse_branches, select_branch

    v2 = json.dumps({"version": 2, "nodes": [
        {"id": "n1", "name": "财务审核", "mode": "single", "approvers": [{"type": "role", "code": "finance"}]},
    ]})
    v3 = json.dumps({"version": 3, "branches": [
        {"name": "≤5万", "condition": {"field": "total_amount", "op": "le", "value": 50000},
         "nodes": [{"id": "n1", "name": "小额审批", "mode": "single", "approvers": [{"type": "role", "code": "finance"}]}]},
        {"name": "默认", "condition": None,
         "nodes": [{"id": "n1", "name": "大额审批", "mode": "single", "approvers": [{"type": "role", "code": "approver"}]}]},
    ]})

    b2 = parse_branches(v2)
    check("v2 定义归一为单个默认分支", len(b2) == 1 and b2[0]["condition"] is None and b2[0]["nodes"][0]["name"] == "财务审核")

    b3 = parse_branches(v3)
    check("v3 定义解析为 2 分支", len(b3) == 2 and b3[0]["name"] == "≤5万" and b3[0]["condition"]["op"] == "le")

    low = types.SimpleNamespace(total_amount=30000)
    high = types.SimpleNamespace(total_amount=80000)
    sel_low = select_branch(b3, "purchase", low)
    sel_high = select_branch(b3, "purchase", high)
    check("小额单据命中 ≤5万 分支", sel_low["name"] == "≤5万" and sel_low["nodes"][0]["name"] == "小额审批")
    check("大额单据落到默认分支", sel_high["name"] == "默认" and sel_high["nodes"][0]["name"] == "大额审批")

    # ---------- 2) 接口级 ----------
    c = httpx.Client(base_url=BASE, timeout=30)
    tok = c.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()["token"]
    c.headers["Authorization"] = f"Bearer {tok}"

    payload = {
        "flow_name": "分支冒烟流程",
        "biz_type": "purchase",
        "priority": 1,
        "branches": [
            {"name": "≤5万", "condition": {"field": "total_amount", "op": "le", "value": 50000},
             "nodes": [{"name": "小额审批", "mode": "single", "approvers": [{"type": "role", "code": "finance"}]}]},
            {"name": "默认", "condition": None,
             "nodes": [{"name": "大额审批", "mode": "single", "approvers": [{"type": "role", "code": "approver"}]}]},
        ],
    }
    r = c.post("/flows", json=payload)
    check("创建分支流程成功", r.status_code == 200, r.text)
    created = r.json()
    check("响应包含 2 个分支", len(created.get("branches", [])) == 2)
    check("兼容字段 nodes = 默认分支节点", created.get("nodes", [{}])[0].get("name") == "大额审批")
    fid = created["id"]

    bad = dict(payload)
    bad["branches"] = [payload["branches"][0]]
    r = c.post("/flows", json=bad)
    check("缺少默认分支被拒绝", r.status_code == 400, r.text)

    r = c.put(f"/flows/{fid}", json=payload)
    check("保存生成 v2 版本", r.status_code == 200 and r.json().get("version") == 2, r.text)
    fid2 = r.json()["id"]

    for x in (fid2, fid):
        c.delete(f"/flows/{x}")
    flows = c.get("/flows").json()["flows"]
    check("测试流程已清理", not any(f.get("flow_name") == "分支冒烟流程" for f in flows))

    print(f"\n结果：{PASS} 通过 / {FAIL} 失败")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
