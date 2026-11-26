<template>
  <div class="m">
    <!-- ============ 登录（无 token 时） ============ -->
    <div v-if="!token" class="m-login">
      <div class="m-login__brand">
        <div class="m-login__mark">审</div>
        <h1>移动端审批</h1>
        <p>固定资产管理 · 随时审批待办</p>
      </div>
      <div class="m-card">
        <input v-model="login.username" class="m-input" placeholder="用户名" @keyup.enter="doLogin" />
        <input v-model="login.password" class="m-input" type="password" placeholder="密码" @keyup.enter="doLogin" />
        <button class="m-btn m-btn--primary" :disabled="busy" @click="doLogin">登录</button>
      </div>
    </div>

    <!-- ============ 待审批列表 ============ -->
    <template v-else>
      <div class="m-head">
        <div>
          <h2>待我审批</h2>
          <span class="m-head__sub">共 {{ todos.length }} 条待办</span>
        </div>
        <button class="m-btn m-btn--ghost m-btn--sm" :disabled="busy" @click="load">刷新</button>
      </div>

      <div v-if="loading" class="m-empty">加载中…</div>
      <div v-else-if="!todos.length" class="m-empty">暂无待审批单据<br />去 Web 端发起审批吧</div>

      <div v-for="row in todos" :key="row.task.id" class="m-card m-task" @click="open(row)">
        <div class="m-task__name">
          <span class="m-tag" :class="bizTag(row.biz_type)">{{ BIZ_LABEL[row.biz_type] || row.biz_type }}</span>
          {{ row.biz_no }}
        </div>
        <div class="m-task__meta">
          <span class="m-tag">节点：{{ row.task.node_name || "-" }}</span>
          <span class="m-muted">{{ row.apply_user_name || "" }}</span>
        </div>
      </div>

      <!-- ============ 审批操作 ============ -->
      <div v-if="cur" class="m-card m-act">
        <div class="m-sec">{{ BIZ_LABEL[cur.biz_type] || cur.biz_type }} {{ cur.biz_no }}</div>
        <div class="m-muted" style="margin-bottom: 10px">当前节点：{{ cur.task.node_name || "-" }} · 申请人：{{ cur.apply_user_name || "-" }}</div>
        <textarea v-model="comment" class="m-textarea" rows="3" placeholder="审批意见（可留空）"></textarea>
        <div class="m-row">
          <button class="m-btn m-btn--bad" :disabled="busy" @click="approve(2)">驳回</button>
          <button class="m-btn m-btn--ok" :disabled="busy" @click="approve(1)">通过</button>
        </div>
        <button class="m-btn m-btn--ghost" style="width: 100%; margin-top: 8px" :disabled="busy" @click="cur = null">返回</button>
      </div>

      <div style="text-align: center; margin-top: 8px">
        <button class="m-btn m-btn--ghost m-btn--sm" @click="logout">退出登录</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { authApi, docApi } from "../../api";

const BIZ_LABEL = {
  purchase: "采购申请", stock_in: "入库单", stock_out: "出库单", transfer: "调拨单", scrap: "报废单",
  borrow: "借用单", return: "归还单",
  con_purchase: "易耗品采购单", con_inbound: "易耗品入库单", con_issue: "易耗品领用单",
};
const bizTag = (t) => ({ purchase: "m-tag--ok", stock_in: "m-tag--ok", stock_out: "m-tag--warn", transfer: "", scrap: "m-tag--bad" }[t] || "");

const token = ref(localStorage.getItem("token"));
const busy = ref(false);
const login = ref({ username: "", password: "" });
const loading = ref(false);
const todos = ref([]);
const cur = ref(null);
const comment = ref("");

async function doLogin() {
  if (!login.value.username || !login.value.password) return ElMessage.warning("请输入用户名和密码");
  busy.value = true;
  try {
    const res = await authApi.login(login.value);
    localStorage.setItem("token", res.token);
    if (res.refresh_token) localStorage.setItem("refresh_token", res.refresh_token);
    localStorage.setItem("user", JSON.stringify(res.user));
    localStorage.setItem("perms", JSON.stringify(res.perms || []));
    token.value = res.token;
    await load();
  } finally {
    busy.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    todos.value = await docApi.todos();
  } finally {
    loading.value = false;
  }
}

function open(row) {
  cur.value = row;
  comment.value = "";
}

async function approve(action) {
  const verb = action === 1 ? "通过" : "驳回";
  busy.value = true;
  try {
    await docApi.approve(cur.value.task.id, { action, comment: comment.value.trim() || null });
    ElMessage.success(`已${verb}：${cur.value.biz_no}`);
    cur.value = null;
    await load();
  } finally {
    busy.value = false;
  }
}

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
  localStorage.removeItem("perms");
  token.value = null;
  todos.value = [];
  cur.value = null;
}
</script>

<style scoped>
.m { max-width: 480px; margin: 0 auto; padding: 14px 14px 40px; min-height: 100vh; background: #f5f4f0; }
.m-card { background: #fff; border-radius: 12px; padding: 14px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(20, 30, 50, 0.06); }
.m-head { display: flex; align-items: center; justify-content: space-between; padding: 4px 2px 12px; }
.m-head h2 { font-size: 18px; color: #16283c; margin: 0; }
.m-head__sub { font-size: 12px; color: #9aa5b1; }
.m-sec { font-size: 13px; font-weight: 600; color: #16283c; margin-bottom: 10px; }
.m-muted { color: #9aa5b1; font-size: 12px; }
.m-empty { text-align: center; color: #9aa5b1; padding: 40px 0; font-size: 14px; line-height: 1.8; }
.m-input {
  width: 100%; box-sizing: border-box; padding: 12px 14px; margin-bottom: 10px;
  border: 1px solid #e2e0d8; border-radius: 10px; font-size: 15px; background: #faf9f6; outline: none;
}
.m-input:focus { border-color: #b07a2e; background: #fff; }
.m-textarea {
  width: 100%; box-sizing: border-box; padding: 10px 12px; margin-bottom: 10px;
  border: 1px solid #e2e0d8; border-radius: 10px; font-size: 15px; background: #faf9f6; outline: none; resize: none;
}
.m-textarea:focus { border-color: #b07a2e; background: #fff; }
.m-btn {
  padding: 12px 18px; border: 1px solid #e2e0d8; border-radius: 10px; background: #fff;
  font-size: 15px; color: #16283c; cursor: pointer; flex: 1;
}
.m-btn:disabled { opacity: 0.5; }
.m-btn--ok { background: #1f8a4c; color: #fff; border-color: #1f8a4c; }
.m-btn--bad { background: #b23b32; color: #fff; border-color: #b23b32; }
.m-btn--ghost { background: transparent; border-color: #d8d5cc; }
.m-btn--sm { padding: 8px 14px; font-size: 13px; flex: none; }
.m-row { display: flex; gap: 8px; }
.m-task { cursor: pointer; }
.m-task__name { font-size: 15px; font-weight: 600; color: #16283c; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.m-task__meta { display: flex; align-items: center; gap: 10px; }
.m-tag { font-size: 12px; padding: 2px 10px; border-radius: 10px; background: #eef0f4; color: #5a6675; }
.m-tag--ok { background: #e5f3ec; color: #1f8a4c; }
.m-tag--warn { background: #f6ecd9; color: #b07a2e; }
.m-tag--bad { background: #f7e4e2; color: #b23b32; }
.m-act { border: 1px solid #b07a2e; }
.m-login { padding: 60px 0; }
.m-login__brand { text-align: center; margin-bottom: 24px; }
.m-login__mark {
  width: 56px; height: 56px; margin: 0 auto 12px; border-radius: 12px;
  background: linear-gradient(135deg, #b07a2e, #8a5a1e); color: #fff; font-size: 26px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.m-login h1 { font-size: 20px; color: #16283c; margin: 0 0 6px; }
.m-login p { font-size: 13px; color: #9aa5b1; margin: 0; }
</style>
