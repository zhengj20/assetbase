"""P3 新特性冒烟：流程监控 / 我发起的 / 委托转办 / 退回节点 / 管理员删除。
用法（backend 目录下，后端已运行）：uv run --with httpx python smoke_flow2.py
"""
import httpx

BASE = "http://127.0.0.1:5200/api/v1"
PASS = 0
FAIL = 0
USERNAME_BY_ID = {1: "admin", 2: "wangqiang", 3: "zhangwei", 4: "liuyan", 5: "lifang", 6: "zhaomin"}


def check(name, cond, extra=""):
    global PASS, FAIL
    ok = bool(cond)
    print(f"  [{'PASS' if ok else '!!FAIL'}] {name}" + (f" -> {extra}" if extra else ""))
    PASS, FAIL = PASS + ok, FAIL + (not ok)


def login(c, u):
    return c.post("/auth/login", json={"username": u, "password": "admin123"}).json()["token"]


def as_user(c, u):
    c.headers["Authorization"] = f"Bearer {login(c, u)}"


def new_purchase(c, user, amount):
    as_user(c, user)
    return c.post("/purchases", json={
        "org_id": 3,
        "items": [{"asset_name": f"P3冒烟采购{amount}", "num": 1, "unit_price": amount}],
    }).json()


def submit(c, user, doc_id):
    as_user(c, user)
    return c.post(f"/docs/purchase/{doc_id}/submit").json()


def current_pending(c, iid):
    """(进度dict, 当前节点dict|None, 待办任务dict|None, 当前节点下标)。"""
    as_user(c, "admin")
    d = c.get(f"/instances/{iid}").json()
    node, task = None, None
    for n in d["nodes"]:
        for t in n["tasks"]:
            if t["action"] is None:
                node, task = n, t
                break
        if task:
            break
    idx = next((i for i, n in enumerate(d["nodes"]) if n["name"] == d["instance"]["current_node"]), 0)
    return d, node, task, idx


def approve_step(c, iid):
    as_user(c, "admin")
    d = c.get(f"/instances/{iid}").json()
    _, _, t, _ = current_pending(c, iid)
    if t:
        as_user(c, USERNAME_BY_ID[t["assignee_id"]])
        c.post(f"/approvals/{t['id']}", json={"action": 1, "comment": "ok"})


def approve_until_done(c, iid):
    steps = []
    for _ in range(12):
        as_user(c, "admin")
        d = c.get(f"/instances/{iid}").json()
        if d["instance"]["status"] != 1:
            return steps
        _, n, t, _ = current_pending(c, iid)
        if not t:
            return steps
        as_user(c, USERNAME_BY_ID[t["assignee_id"]])
        r = c.post(f"/approvals/{t['id']}", json={"action": 1, "comment": "ok"}).json()
        steps.append(f"{n['name']}:{r.get('result')}")
    return steps


def main():
    c = httpx.Client(base_url=BASE, timeout=60)

    # ========== 1. 流程监控 ==========
    print("\n[1] 流程监控")
    as_user(c, "admin")
    st = c.get("/monitor/stats").json()
    check("stats 结构", "total" in st and "by_status" in st, f"total={st.get('total')}")
    li = c.get("/monitor/instances", params={"page": 1, "page_size": 5}).json()
    check("监控列表", li.get("total", 0) >= 1 and len(li.get("records", [])) >= 1, f"total={li.get('total')}")
    r1 = c.get("/monitor/instances", params={"status": 1}).json()
    check("按状态过滤(审批中)", all(x["status"] == 1 for x in r1.get("records", [])), f"n={r1.get('total')}")
    kw = c.get("/monitor/instances", params={"keyword": "zzz_no_such_999"}).json()
    check("编号搜索(无命中)", kw["total"] == 0)
    as_user(c, "zhangwei")
    r2 = c.get("/monitor/instances").json()
    check("非 admin 可查看监控", r2.get("total", 0) >= 1)

    # ========== 2. 我发起的 ==========
    print("\n[2] 我发起的")
    d1 = new_purchase(c, "zhangwei", 2000)
    iid_a = submit(c, "zhangwei", d1["id"]).get("wf_instance_id")
    check("zhangwei 发起实例", iid_a is not None, f"#{iid_a}")
    as_user(c, "zhangwei")
    mine = c.get("/approvals/mine").json()
    check("我发起的包含新实例", any(x["id"] == iid_a for x in mine.get("records", [])), f"total={mine.get('total')}")
    row = next(x for x in mine["records"] if x["id"] == iid_a)
    check("行字段完整", row["biz_no"] and row["initiator_name"] and row["status"] == 1,
          f"no={row['biz_no']} init={row['initiator_name']}")
    as_user(c, "admin")
    mine_admin = c.get("/approvals/mine", params={"status": 1}).json()
    check("admin 的我发起的不含 zhangwei 实例", all(x["id"] != iid_a for x in mine_admin.get("records", [])))

    # ========== 3. 委托转办 ==========
    print("\n[3] 委托转办")
    as_user(c, "admin")
    _, _, t, _ = current_pending(c, iid_a)
    a_uid = t["assignee_id"]
    target = 6 if a_uid != 6 else 3
    as_user(c, USERNAME_BY_ID[a_uid])
    bad = c.post(f"/approvals/{t['id']}/delegate", json={"to_user": a_uid})
    check("委托给自己被拒", bad.status_code == 400)
    ok = c.post(f"/approvals/{t['id']}/delegate", json={"to_user": target, "comment": "委托冒烟"})
    check("委托成功", ok.status_code == 200 and ok.json().get("assignee_id") == target, f"-> user{target}")
    as_user(c, USERNAME_BY_ID[target])
    todos = c.get("/approvals/todos").json()
    check("受托人待办出现该任务", any(x["task"]["instance_id"] == iid_a for x in todos))

    # ========== 4. 退回节点 ==========
    print("\n[4] 退回节点")
    d, n, t, idx = current_pending(c, iid_a)
    if idx == 0 and t:
        approve_step(c, iid_a)
        d, n, t, idx = current_pending(c, iid_a)
    if not t:
        check("退回(跳过：实例已完成或无待办)", d["instance"]["status"] == 2, f"status={d['instance']['status']}")
    elif idx == 0:
        check("退回(跳过：当前为首节点)", True, "首节点无可退回目标")
    else:
        as_user(c, USERNAME_BY_ID[t["assignee_id"]])
        bad = c.post(f"/approvals/{t['id']}", json={"action": 5, "target_node": idx})
        check("退回到当前/后置节点被拒", bad.status_code == 400)
        ok = c.post(f"/approvals/{t['id']}", json={"action": 5, "target_node": 0, "comment": "退回冒烟"})
        check("退回首节点成功", ok.status_code == 200 and ok.json().get("result") == "sent_back")
        as_user(c, "admin")
        d3, n0, t0, _ = current_pending(c, iid_a)
        check("流程回到首节点且有待办",
              d3["instance"]["status"] == 1
              and d3["instance"]["current_node"] == d3["nodes"][0]["name"]
              and t0 is not None and n0["name"] == d3["nodes"][0]["name"])

    # ========== 5. 审批完成 ==========
    print("\n[5] 审批完成")
    steps = approve_until_done(c, iid_a)
    as_user(c, "admin")
    dfin = c.get(f"/instances/{iid_a}").json()
    check("实例已通过", dfin["instance"]["status"] == 2, "; ".join(steps))

    # ========== 6. 管理员删除 ==========
    print("\n[6] 管理员删除审批中实例")
    d2 = new_purchase(c, "zhangwei", 3000)
    iid_b = submit(c, "zhangwei", d2["id"]).get("wf_instance_id")
    check("第二个审批中实例", iid_b is not None, f"#{iid_b}")
    as_user(c, "zhangwei")
    r = c.delete(f"/instances/{iid_b}")
    check("非管理员删除被拒", r.status_code == 403)
    as_user(c, "admin")
    r = c.delete(f"/instances/{iid_b}")
    check("管理员删除成功", r.status_code == 200, r.text[:80])
    li2 = c.get("/monitor/instances", params={"status": 1}).json()
    check("监控列表不再含已删实例", all(x["id"] != iid_b for x in li2.get("records", [])))
    as_user(c, "zhangwei")
    mine2 = c.get("/approvals/mine").json()
    check("我发起的不再含已删实例", all(x["id"] != iid_b for x in mine2.get("records", [])))
    as_user(c, "admin")
    dbiz = c.get(f"/purchases/{d2['id']}").json()
    check("单据已作废", dbiz.get("status") == 4, f"status={dbiz.get('status')}")
    as_user(c, "admin")
    dview = c.get(f"/instances/{iid_b}").json()
    check("进度页仍可查看", dview["instance"]["status"] == 5 and "删除" in (dview["instance"].get("finish_note") or ""))

    print(f"\n===== 结果: {PASS} PASS / {FAIL} FAIL =====")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
