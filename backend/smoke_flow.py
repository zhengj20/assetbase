"""新审批流特性冒烟：建流程/版本/启停/删除 + 条件分支 + 或签/会签 + 加签 + 驳回/撤销/终止。
用法（backend 目录下，后端已运行）：uv run --with httpx python smoke_flow.py
"""
import httpx

BASE = "http://127.0.0.1:5200/api/v1"
PASS = 0
FAIL = 0


def check(name: str, cond, extra: str = ""):
    global PASS, FAIL
    ok = bool(cond)
    print(f"  [{'PASS' if ok else '!!FAIL'}] {name}" + (f" -> {extra}" if extra else ""))
    PASS, FAIL = PASS + ok, FAIL + (not ok)


def login(c, u):
    return c.post("/auth/login", json={"username": u, "password": "admin123"}).json()["token"]


def as_user(c, u):
    c.headers["Authorization"] = f"Bearer {login(c, u)}"


def my_task(c, iid):
    """当前登录用户在实例中的待办任务ID（进度接口 my_task_id）。"""
    return c.get(f"/instances/{iid}").json().get("my_task_id")


def main():
    c = httpx.Client(base_url=BASE, timeout=60)

    # ========== 0. 基础数据：两个仓库 + 一件在库资产 ==========
    as_user(c, "admin")
    wh_out = c.post("/warehouses", json={"warehouse_name": "冒烟调出仓", "warehouse_type": 1, "org_id": 3}).json()
    wh_in = c.post("/warehouses", json={"warehouse_name": "冒烟调入仓", "warehouse_type": 1, "org_id": 3}).json()
    cats = c.get("/categories").json()
    cat = next(x for x in cats if not any(y["parent_id"] == x["id"] for y in cats))
    asset = c.post("/assets", json={
        "asset_name": "冒烟测试资产", "category_id": cat["id"], "org_id": 3,
        "warehouse_id": wh_out["id"], "price": 1000,
    }).json()
    check("基础数据就绪", bool(wh_out.get("id") and wh_in.get("id") and asset.get("id")))

    def new_transfer():
        as_user(c, "admin")
        a = c.get(f"/assets/{asset['id']}").json()
        if a.get("warehouse_id") == wh_out["id"]:
            out_id, in_id = wh_out["id"], wh_in["id"]
        else:
            out_id, in_id = wh_in["id"], wh_out["id"]
        d = c.post("/transfers", json={
            "out_warehouse_id": out_id, "in_warehouse_id": in_id,
            "out_org_id": 3, "in_org_id": 3, "transfer_type": 1,
            "items": [{"asset_id": asset["id"]}],
        }).json()
        return d

    def new_purchase(amount):
        as_user(c, "admin")
        d = c.post("/purchases", json={
            "org_id": 3,
            "items": [{"asset_name": f"冒烟采购{amount}", "num": 1, "unit_price": amount}],
        }).json()
        return d

    def submit(biz, d):
        r = c.post(f"/docs/{biz}/{d['id']}/submit")
        return r.json().get("wf_instance_id")

    # ========== 1. 新建流程（调拨：或签 + 会签） ==========
    print("\n[1] 新建流程 + 版本管理")
    as_user(c, "admin")
    for f in c.get("/flows").json()["flows"]:
        if f["biz_type"] == "transfer" and f["status"] == 1 and f["id"] != 0:
            c.post(f"/flows/{f['id']}/status", params={"status": 0})
    f1 = c.post("/flows", json={
        "flow_name": "冒烟调拨流", "biz_type": "transfer",
        "nodes": [
            {"name": "部门负责人或签", "mode": "any", "approvers": [{"type": "user", "id": 6}]},
            {"name": "双人会签", "mode": "all", "approvers": [{"type": "user", "id": 3}, {"type": "user", "id": 5}]},
        ],
    }).json()
    check("新建流程", f1.get("id"), f"#{f1.get('id')} key={f1.get('flow_key')}")
    f2 = c.put(f"/flows/{f1['id']}", json={
        "flow_name": "冒烟调拨流", "biz_type": "transfer",
        "nodes": [
            {"name": "部门负责人或签", "mode": "any", "approvers": [{"type": "user", "id": 6}, {"type": "user", "id": 2}]},
            {"name": "双人会签", "mode": "all", "approvers": [{"type": "user", "id": 3}, {"type": "user", "id": 5}]},
        ],
    }).json()
    check("保存为新版本", f2.get("version") == 2 and f2.get("id") != f1["id"],
          f"v{f2.get('version')} #{f2.get('id')}")
    flows = c.get("/flows").json()["flows"]
    same_key = [f for f in flows if f["flow_key"] == f2["flow_key"]]
    enabled = [f for f in same_key if f["status"] == 1]
    check("同流程仅一个启用版本", len(enabled) == 1 and enabled[0]["id"] == f2["id"],
          f"{[(f['id'], f['status']) for f in same_key]}")
    as_user(c, "admin")
    r = c.post("/flows/5/status", params={"status": 0})
    check("停用旧调拨流(id=5)", r.json().get("status") == 0)

    # ========== 2. 分支条件匹配（采购） ==========
    print("\n[2] 分支条件：采购金额 >5万 走财务+领导流")
    p_hi = new_purchase(80000)
    iid_hi = submit("purchase", p_hi)
    as_user(c, "admin")
    prog = c.get(f"/instances/{iid_hi}").json()
    check("8万采购命中 >5万 流程", prog["instance"]["flow_name"] == "采购申请（>5万）",
          prog["instance"]["flow_name"])
    p_lo = new_purchase(10000)
    iid_lo = submit("purchase", p_lo)
    as_user(c, "admin")
    prog = c.get(f"/instances/{iid_lo}").json()
    check("1万采购走无条件兜底流", prog["instance"]["flow_name"] == "采购申请（≤5万）",
          prog["instance"]["flow_name"])
    c.post(f"/instances/{iid_hi}/withdraw")  # 8万单撤销，避免占用
    c.post(f"/instances/{iid_lo}/withdraw")

    # ========== 3. 或签 + 会签（调拨） ==========
    print("\n[3] 调拨：或签节点 + 会签节点")
    t = new_transfer()
    iid = submit("transfer", t)
    as_user(c, "zhaomin")
    check("或签节点 2 人待办", my_task(c, iid) is not None)
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 1, "comment": "或签通过"})
    check("或签一人通过即流转", r.json().get("result") == "next_node", str(r.json()))
    as_user(c, "admin")
    prog = c.get(f"/instances/{iid}").json()
    n1 = next(n for n in prog["nodes"] if n["name"] == "部门负责人或签")
    auto = [x for x in n1["tasks"] if x["assignee_id"] == 2]
    check("或签另一人任务自动完成", bool(auto) and auto[0]["action"] == 1 and "或签" in (auto[0]["comment"] or ""),
          f"{auto[0]['comment'] if auto else '-'}")
    as_user(c, "zhangwei")
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 1, "comment": "会签1/2"})
    check("会签第一人通过->等待", r.json().get("result") == "waiting", str(r.json()))
    as_user(c, "lifang")
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 1, "comment": "会签2/2"})
    check("会签齐备->审批完成", r.json().get("result") == "approved", str(r.json()))
    as_user(c, "admin")
    check("调拨单->已通过", c.get(f"/transfers/{t['id']}").json()["status"] == 2)

    # ========== 4. 加签（采购兜底流 3 节点） ==========
    print("\n[4] 采购：加签（后加签必审）")
    iid = submit("purchase", new_purchase(10000))
    as_user(c, "zhangwei")
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 4, "sign_to": 4, "comment": ""})
    check("加签给刘燕", r.json().get("result") == "countersigned", str(r.json()))
    as_user(c, "admin")
    prog = c.get(f"/instances/{iid}").json()
    signed = [x for n in prog["nodes"] for x in n["tasks"] if x["sign_from"]]
    check("加签任务带来源", bool(signed) and signed[0]["assignee_id"] == 4 and signed[0]["sign_from_user"] == "张威",
          json_dump(signed))
    as_user(c, "zhangwei")
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 1, "comment": "本人通过"})
    check("加签后本人通过仍等待", r.json().get("result") == "waiting", str(r.json()))
    as_user(c, "liuyan")
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 1, "comment": "被加签人通过"})
    check("加签人通过->下一节点", r.json().get("result") == "next_node", str(r.json()))
    as_user(c, "lifang")
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 1, "comment": "财务通过"})
    check("财务节点->下一节点", r.json().get("result") == "next_node", str(r.json()))
    as_user(c, "wangqiang")
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 1, "comment": "领导通过"})
    check("末节点通过->完成", r.json().get("result") == "approved", str(r.json()))

    # ========== 5. 驳回 ==========
    print("\n[5] 驳回：流程终止 + 单据回退")
    t = new_transfer()
    iid = submit("transfer", t)
    as_user(c, "zhaomin")
    r = c.post(f"/approvals/{my_task(c, iid)}", json={"action": 2, "comment": "资产信息不符"})
    check("驳回成功", r.json().get("result") == "rejected", str(r.json()))
    as_user(c, "admin")
    prog = c.get(f"/instances/{iid}").json()
    check("实例->已驳回", prog["instance"]["status"] == 3, prog["instance"]["status_label"])
    check("调拨单->已驳回", c.get(f"/transfers/{t['id']}").json()["status"] == 3)

    # ========== 6. 撤销（限发起人/管理员） ==========
    print("\n[6] 撤销：仅发起人/管理员")
    t = new_transfer()
    iid = submit("transfer", t)
    as_user(c, "zhangwei")
    r = c.post(f"/instances/{iid}/withdraw")
    check("非发起人撤销被拒", r.status_code == 403, f"HTTP {r.status_code}")
    as_user(c, "admin")
    r = c.post(f"/instances/{iid}/withdraw")
    check("发起人撤销成功", r.json().get("instance_status") == 4, str(r.json()))
    check("调拨单->已取消", c.get(f"/transfers/{t['id']}").json()["status"] == 4)

    # ========== 7. 终止（限管理员） ==========
    print("\n[7] 终止：仅管理员")
    t = new_transfer()
    iid = submit("transfer", t)
    as_user(c, "lifang")
    r = c.post(f"/instances/{iid}/terminate", json={"reason": "越权"})
    check("非管理员终止被拒", r.status_code == 403, f"HTTP {r.status_code}")
    as_user(c, "admin")
    r = c.post(f"/instances/{iid}/terminate", json={"reason": "业务取消"})
    check("管理员终止成功", r.json().get("instance_status") == 5, str(r.json()))
    prog = c.get(f"/instances/{iid}").json()
    check("实例->已终止", prog["instance"]["status"] == 5, prog["instance"]["status_label"])
    check("调拨单->已取消", c.get(f"/transfers/{t['id']}").json()["status"] == 4)

    # ========== 8. 删除流程（有在途实例禁止） ==========
    print("\n[8] 删除流程")
    t = new_transfer()
    iid = submit("transfer", t)
    r = c.delete(f"/flows/{f2['id']}")
    check("有审批中实例禁止删除", r.status_code == 400, r.json().get("detail", ""))
    c.post(f"/instances/{iid}/withdraw")
    r = c.delete(f"/flows/{f2['id']}")
    check("删除流程成功", r.json().get("ok") is True)
    r = c.delete(f"/flows/{f1['id']}")
    check("删除旧版本成功", r.json().get("ok") is True)

    print(f"\n========== 冒烟结果：{PASS} 通过 / {FAIL} 失败 ==========")
    return 1 if FAIL else 0


def json_dump(x):
    import json
    return json.dumps(x, ensure_ascii=False)


if __name__ == "__main__":
    import sys
    sys.exit(main())
