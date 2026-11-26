"""归还单闭环 e2e：建单 → 提交审批 → 审批通过 → 资产回库。"""
import json
import urllib.request as u

B = "http://127.0.0.1:5200/api/v1"


def c(method, path, token=None, j=None):
    d = json.dumps(j).encode() if j is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    r = u.Request(B + path, data=d, method=method, headers=h)
    try:
        with u.urlopen(r, timeout=25) as x:
            return x.status, json.loads(x.read().decode() or "{}")
    except Exception as e:
        return getattr(e, "code", -1), json.loads(e.read().decode() or "{}")


def main():
    s, b = c("POST", "/auth/login", None, {"username": "admin", "password": "admin123"})
    assert s == 200, f"login {s} {b}"
    tok = b["token"]

    # 1) 列表
    s, b = c("GET", "/returns?page=1&page_size=5", tok)
    print("归还单列表:", s, "total=", b.get("total"), "首单=", (b.get("records") or [{}])[0].get("return_no"))

    # 2) 找借用中(7)资产
    s, b = c("GET", "/assets?page=1&page_size=200&status=7", tok)
    recs = b.get("records") or []
    print("借用中资产:", len(recs), "项，样本:", [(r["asset_code"], r["asset_name"]) for r in recs[:3]])
    if not recs:
        print("无借用中资产，无法继续 e2e")
        return
    aid = recs[0]["id"]

    # 3) 创建归还单
    s, b = c("POST", "/returns", tok, {"remark": "e2e闭环", "items": [{"asset_id": aid}]})
    assert s == 200, f"create {s} {b}"
    rid = b["id"]
    print("创建归还单:", rid, b.get("return_no"))

    # 4) 提交审批
    s, b = c("POST", f"/docs/return/{rid}/submit", tok)
    assert s == 200, f"submit {s} {b}"
    print("提交审批:", s, b)

    # 5) 找待办并审批通过
    s, b = c("GET", "/approvals/todos", tok)
    todos = b if isinstance(b, list) else b.get("records") or b.get("data") or []
    task = next((t for t in todos if t.get("biz_type") == "return" and t.get("biz_id") == rid), None)
    print("待办任务:", "找到" if task else "未找到", task and task.get("id"))
    if task:
        s, b = c("POST", f"/approvals/{task['id']}", tok, {"action": "approve", "comment": "同意归还"})
        print("审批通过:", s, b)

    # 6) 验证资产回库
    s, b = c("GET", f"/assets/{aid}", tok)
    print("资产最终状态:", s, "status=", b.get("status"), "(1=在库，回库成功)" if b.get("status") == 1 else "(!)未回库")

    # 7) 归还单详情
    s, b = c("GET", f"/returns/{rid}", tok)
    print("归还单最终:", s, "status=", b.get("status"), "(2=已通过)" if b.get("status") == 2 else "(!)未通过")


main()
