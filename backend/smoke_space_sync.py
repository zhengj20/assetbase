"""冒烟：项目空间父级状态变更同步子级 + 子级单独设置。
用法（backend 目录下，后端已运行）：uv run --with httpx python smoke_space_sync.py
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


def main():
    c = httpx.Client(base_url=BASE, timeout=60)
    tok = c.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()["token"]
    c.headers["Authorization"] = f"Bearer {tok}"

    def mk(name, parent_id):
        r = c.post("/spaces", json={
            "space_name": name, "space_type": 2, "parent_id": parent_id,
            "project_id": 3, "space_status": 1,
        })
        assert r.status_code == 200, r.text
        return r.json()

    def status_of(sid):
        tree = c.get("/spaces").json()

        def find(nodes):
            for s in nodes:
                if s["id"] == sid:
                    return s["space_status"]
                r = find(s.get("children") or [])
                if r is not None:
                    return r
            return None

        return find(tree)

    root = mk("冒烟同步父空间", 0)
    child = mk("冒烟同步子空间", root["id"])
    grand = mk("冒烟同步孙空间", child["id"])
    ids = [root["id"], child["id"], grand["id"]]
    try:
        check("初始三节点均为在用", all(status_of(i) == 1 for i in ids),
              f"{[status_of(i) for i in ids]}")

        # 1) 父级关闭 → 子级/孙级同步关闭
        body = {"space_name": root["space_name"], "space_type": 2, "parent_id": 0,
                "project_id": 3, "space_status": 2}
        r = c.put(f"/spaces/{root['id']}", json=body)
        check("父级关闭成功", r.status_code == 200, r.text)
        check("子级同步关闭", status_of(child["id"]) == 2, str(status_of(child["id"])))
        check("孙级同步关闭", status_of(grand["id"]) == 2, str(status_of(grand["id"])))

        # 2) 子级单独设置为在用（可与父级不同；其自身作为孙级的父级，孙级随之同步）
        r = c.put(f"/spaces/{child['id']}", json={**body, "parent_id": root["id"], "space_status": 1})
        check("子级单独启用成功", r.status_code == 200, r.text)
        check("子级为在用（与父级不同，允许单独设置）", status_of(child["id"]) == 1, str(status_of(child["id"])))
        check("父级仍关闭", status_of(root["id"]) == 2, str(status_of(root["id"])))
        check("孙级随其父级（子级）同步为在用", status_of(grand["id"]) == 1, str(status_of(grand["id"])))

        # 3) 父级重新在用 → 子级/孙级同步在用
        r = c.put(f"/spaces/{root['id']}", json={**body, "space_status": 1})
        check("父级重新启用成功", r.status_code == 200, r.text)
        check("子级同步在用", status_of(child["id"]) == 1, str(status_of(child["id"])))
        check("孙级同步在用", status_of(grand["id"]) == 1, str(status_of(grand["id"])))
    finally:
        for sid in reversed(ids):
            c.delete(f"/spaces/{sid}")

    print(f"\n结果：{PASS} 通过 / {FAIL} 失败")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
