"""端到端联调验证：登录→建档→入库→领用→盘点→报表导出→全局搜索。

前置：MySQL 已启动、后端运行于 127.0.0.1:8000 且已初始化种子数据。
用法（backend 目录下）：
    uv run --with httpx python e2e_test.py
"""
import sys
from datetime import datetime

import httpx

BASE = "http://127.0.0.1:5200/api/v1"
TS = f"E2E{datetime.now():%m%d%H%M}"  # 测试数据标识（按运行时间隔离，可重复执行）

PASS = 0
FAIL = 0


def check(name: str, cond, extra: str = ""):
    global PASS, FAIL
    ok = bool(cond)
    print(f"  [{'PASS' if ok else '!!FAIL'}] {name}" + (f" -> {extra}" if extra else ""))
    PASS, FAIL = PASS + ok, FAIL + (not ok)


def login(c: httpx.Client, username: str) -> str:
    r = c.post("/auth/login", json={"username": username, "password": "admin123"})
    r.raise_for_status()
    return r.json()["token"]


USERNAME_BY_ID = {1: "admin", 2: "wangqiang", 3: "zhangwei", 4: "liuyan", 5: "lifang", 6: "zhaomin"}
_TOKENS: dict[int, str] = {}


def _as_user(c: httpx.Client, uid: int) -> None:
    if uid not in _TOKENS:
        _TOKENS[uid] = login(c, USERNAME_BY_ID[uid])
    c.headers["Authorization"] = f"Bearer {_TOKENS[uid]}"


def approve_until_done(c: httpx.Client, admin: str, iid: int, max_nodes: int = 6) -> list:
    """按实际流程逐节点审批（以各节点待办任务的指派人为身份通过）。返回 [(节点名, result), ...]"""
    steps = []
    for _ in range(max_nodes):
        c.headers["Authorization"] = f"Bearer {admin}"
        p = c.get(f"/instances/{iid}").json()
        if p["instance"]["status"] != 1:
            break
        pending = next((t for n in p["nodes"] for t in n["tasks"] if t["action"] is None), None)
        if pending is None:
            break
        _as_user(c, pending["assignee_id"])
        r = c.post(f"/approvals/{pending['id']}", json={"action": 1, "comment": "E2E：审批通过"})
        steps.append((pending["node_name"], r.json().get("result")))
    return steps


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)

    # ========== 1. 登录认证 ==========
    print("\n[1] 登录认证（管理员发起业务 / 资产专员审批，模拟真实多角色协作）")
    admin = login(c, "admin")
    zhangwei = login(c, "zhangwei")
    check("admin / zhangwei 双账号登录", True)
    bad = c.post("/auth/login", json={"username": "admin", "password": "wrongpass"})
    check("错误密码返回 401", bad.status_code == 401, f"HTTP {bad.status_code}")
    c.headers["Authorization"] = f"Bearer {admin}"
    me = c.get("/auth/me").json()
    check("获取当前用户信息", me["user"]["real_name"] == "系统管理员", me["user"]["real_name"])

    # ========== 2. 基础档案 ==========
    print("\n[2] 基础档案：分类 / 仓库")
    cats = c.get("/categories").json()
    cat = next(x for x in cats if not any(y["parent_id"] == x["id"] for y in cats))
    wh = c.post("/warehouses", json={
        "warehouse_name": f"{TS}联调仓库", "warehouse_type": 1, "org_id": 3,
    }).json()
    check("创建联调仓库", wh.get("id"), f"#{wh['id']} {wh['warehouse_name']}")

    # ========== 3. 手工建档 ==========
    print("\n[3] 资产建档（手工）")
    a0 = c.post("/assets", json={
        "asset_name": f"{TS}曲面显示器", "category_id": cat["id"], "org_id": 3,
        "warehouse_id": wh["id"], "price": 2500, "brand": "戴尔",
        "location_detail": "售楼处-前台",
    }).json()
    check("手工建档并自动赋码", bool(a0.get("asset_code")), a0["asset_code"])
    logs = c.get(f"/assets/{a0['id']}/logs").json()
    check("建档写入履历", len(logs) >= 1, f"{len(logs)} 条")

    # ========== 4. 入库：草稿→提交→审批→自动建档 ==========
    print("\n[4] 入库管理：一单两明细，审批生效后逐件建档")
    si = c.post("/stock-ins", json={
        "warehouse_id": wh["id"], "in_type": 1,
        "items": [
            {"category_id": cat["id"], "asset_name": f"{TS}ThinkPad笔记本", "num": 2, "unit_price": 7999},
            {"category_id": cat["id"], "asset_name": f"{TS}罗技机械键盘", "num": 3, "unit_price": 299},
        ],
    }).json()
    check("创建入库单（草稿）", si["status"] == 0,
          f"{si['in_no']} 数量{si['total_num']} 金额{si['total_price']}")
    r = c.post(f"/docs/stock_in/{si['id']}/submit")
    check("提交审批", r.status_code == 200 and r.json().get("wf_instance_id") is not None)
    iid_in = r.json()["wf_instance_id"]

    c.headers["Authorization"] = f"Bearer {zhangwei}"
    todos = c.get("/approvals/todos").json()
    todo = next((t for t in todos if t["biz_type"] == "stock_in" and t["biz_id"] == si["id"]), None)
    check("审批待办推送到资产管理员", todo is not None,
          f"节点「{todo['task']['node_name'] if todo else '-'}」")
    steps = approve_until_done(c, admin, iid_in)
    check("逐节点审批至通过", bool(steps) and steps[-1][1] == "approved",
          " -> ".join(f"{n}:{r}" for n, r in steps))

    c.headers["Authorization"] = f"Bearer {admin}"
    check("入库单状态->已通过", c.get(f"/stock-ins/{si['id']}").json()["status"] == 2)
    tps = c.get("/assets", params={"keyword": f"{TS}ThinkPad笔记本", "page_size": 50}).json()
    check("审批生效自动建档 2 台笔记本", tps["total"] == 2,
          " / ".join(x["asset_code"] for x in tps["records"]))
    logs = c.get(f"/assets/{tps['records'][0]['id']}/logs").json()
    check("入库履历留痕", any(x.get("biz_type") == "stock_in" for x in logs), f"{len(logs)} 条")

    # ========== 5. 领用出库 ==========
    print("\n[5] 出库管理：领用 1 台笔记本 + 1 把键盘")
    kbs = c.get("/assets", params={"keyword": f"{TS}罗技机械键盘", "page_size": 50}).json()
    pick = [tps["records"][0]["id"], kbs["records"][0]["id"]]
    so = c.post("/stock-outs", json={
        "warehouse_id": wh["id"], "out_type": 1, "receive_user": 4,
        "items": [{"asset_id": i, "use_location": "售楼处-洽谈区"} for i in pick],
    }).json()
    check("创建领用出库单（草稿）", so["status"] == 0, so["out_no"])
    r = c.post(f"/docs/stock_out/{so['id']}/submit")
    iid_out = r.json()["wf_instance_id"]
    c.headers["Authorization"] = f"Bearer {zhangwei}"
    todos = c.get("/approvals/todos").json()
    todo = next((t for t in todos if t["biz_type"] == "stock_out" and t["biz_id"] == so["id"]), None)
    check("领用待办推送到资产管理员", todo is not None,
          f"节点「{todo['task']['node_name'] if todo else '-'}」")
    steps = approve_until_done(c, admin, iid_out)
    check("领用审批通过", bool(steps) and steps[-1][1] == "approved",
          " -> ".join(f"{n}:{r}" for n, r in steps))

    c.headers["Authorization"] = f"Bearer {admin}"
    detail = c.get(f"/assets/{pick[0]}").json()
    check("资产状态->领用中", detail["status"] == 2, f"status={detail['status']}")
    check("领用人绑定", detail["use_user_id"] == 4, f"use_user_id={detail['use_user_id']}")

    # ========== 6. 盘点 ==========
    print("\n[6] 盘点管理：账面快照->实盘->差异比对")
    task = c.post("/check-tasks", json={
        "task_name": f"{TS}联调盘点", "check_type": 2, "scope_type": 3, "scope_id": wh["id"],
    }).json()
    items = c.get(f"/check-tasks/{task['id']}/items", params={"page_size": 100}).json()
    check("创建盘点任务并冻结账面快照", task["status"] == 1 and items["total"] >= 3,
          f"{task['task_no']} 账面 {items['total']} 项")
    rows = items["records"]
    for i, it in enumerate(rows):
        result = 3 if i == 0 else (4 if i == 1 else 1)  # 1 盘亏 + 1 位置异常，其余正常
        c.post(f"/check-items/{it['id']}/record", json={
            "check_result": result,
            "actual_location": "样板间B-客厅" if result == 4 else None,
        })
    r = c.post(f"/check-tasks/{task['id']}/surplus", json={
        "surplus_name": f"{TS}盘盈工程水准仪", "surplus_price": 1800, "actual_location": "仓库-货架3",
    })
    check("登记盘盈实物", r.status_code == 200)
    fin = c.post(f"/check-tasks/{task['id']}/finish").json()
    check("完成盘点自动差异比对", fin.get("diff_rate") is not None,
          f"正常{fin.get('normal')} 盘盈{fin.get('surplus')} 盘亏{fin.get('loss')} "
          f"位置异常{fin.get('position_diff')} 差异率{fin.get('diff_rate')}")
    check("差异率>2% 标记需复盘", fin.get("need_review") is True)
    summ = c.get(f"/check-tasks/{task['id']}/summary").json()
    check("盘点汇总统计", summ["book_total"] == items["total"]
          and summ["surplus"] == 1 and summ["loss"] == 1,
          f"账面{summ['book_total']} 盘盈{summ['surplus']} 盘亏{summ['loss']}")

    # ========== 7. 报表导出 ==========
    print("\n[7] 盘点报表输出：明细表 / 差异表 / 汇总表")
    labels = {"detail": "明细表", "diff": "差异表", "summary": "汇总表"}
    for t, label in labels.items():
        r = c.get(f"/check-tasks/{task['id']}/export", params={"type": t})
        ok = r.status_code == 200 and r.content[:2] == b"PK" and len(r.content) > 2000
        check(f"导出{label}(xlsx)", ok, f"{len(r.content)} bytes")

    # ========== 8. 差异闭环 ==========
    print("\n[8] 差异闭环：盘盈建档入库 / 盘亏销账")
    r = c.post(f"/check-tasks/{task['id']}/handle-diff")
    check("差异处理完成", r.status_code == 200, str(r.json()))
    sp = c.get("/assets", params={"keyword": f"{TS}盘盈工程水准仪"}).json()
    check("盘盈自动建档", sp["total"] == 1,
          sp["records"][0]["asset_code"] if sp["records"] else "-")
    loss = c.get(f"/assets/{rows[0]['asset_id']}").json()
    check("盘亏资产销账->已报废", loss["status"] == 5, f"status={loss['status']}")
    t2 = c.get(f"/check-tasks/{task['id']}").json()
    check("盘点任务->已完成", t2["status"] == 3, f"status={t2['status']}")

    # ========== 9. 全局搜索 ==========
    print("\n[9] 全局固定资产搜索")
    quick = c.get("/search/quick", params={"keyword": TS}).json()
    check("顶栏快速检索（名称）", len(quick) >= 5, f"{len(quick)} 条")
    by_code = c.get("/search/quick", params={"keyword": tps["records"][0]["asset_code"]}).json()
    check("全局搜索（编码精确）", len(by_code) == 1,
          by_code[0]["asset_code"] if by_code else "-")
    full = c.get("/search/assets", params={"keyword": "ThinkPad"}).json()
    check("全局搜索完整结果（名称）", full["total"] >= 1, f"total={full['total']}")
    by_loc = c.get("/search/quick", params={"keyword": "售楼处-前台"}).json()
    check("全局搜索（位置）", len(by_loc) >= 1, f"{len(by_loc)} 条")

    # ========== 10. 驾驶舱 ==========
    print("\n[10] 驾驶舱汇总指标")
    dash = c.get("/dashboard").json()
    check("驾驶舱指标卡加载", dash["cards"]["total"] >= 6,
          f"资产总数{dash['cards']['total']} 原值{dash['cards']['orig_value']:.0f} "
          f"在库{dash['cards']['in_stock']} 领用中{dash['cards']['in_use']}")
    check("地产行业特色指标", "estate_metrics" in dash and "alerts" in dash)
    con = dash.get("con_metrics") or {}
    check("易耗品指标", "stock_value" in con and "stockout_count" in con and "con_top_items" in dash,
          f"库存{con.get('stock_value', 0):.0f} 本月领用{con.get('issue_month_amount', 0):.0f} 断货{con.get('stockout_count', 0)}")
    check("趋势含易耗品领用金额", all("con_amount" in t for t in dash.get("trend", [])))

    print(f"\n========== 结果：{PASS} 通过 / {FAIL} 失败 ==========")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
