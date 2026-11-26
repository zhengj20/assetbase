<template>
  <el-container class="layout">
    <!-- ============ 侧边栏 ============ -->
    <el-aside width="224px" class="sidebar">
      <div class="sidebar__brand">
        <div class="sidebar__mark">固</div>
        <div class="sidebar__name">
          <b>固定资产管理</b>
          <span>REAL ESTATE · ASSET LEDGER</span>
        </div>
      </div>
      <el-scrollbar class="sidebar__scroll">
        <el-menu
          :default-active="$route.path"
          background-color="transparent"
          text-color="#b8c5d2"
          active-text-color="#ffffff"
          router
          unique-opened
        >
          <template v-for="dir in menuTree" :key="dir.id">
            <el-sub-menu v-if="dir.children.length" :index="String(dir.id)">
              <template #title>
                <el-icon v-if="dir.icon"><component :is="dir.icon" /></el-icon>
                <span>{{ dir.menu_name }}</span>
              </template>
              <template v-for="m in dir.children" :key="m.id">
                <el-sub-menu v-if="m.children.length" :index="String(m.id)">
                  <template #title>
                    <el-icon v-if="m.icon"><component :is="m.icon" /></el-icon>
                    <span>{{ m.menu_name }}</span>
                  </template>
                  <el-menu-item v-for="c in m.children" :key="c.id" :index="c.path">
                    <el-icon v-if="c.icon"><component :is="c.icon" /></el-icon>
                    <span>{{ c.menu_name }}</span>
                  </el-menu-item>
                </el-sub-menu>
                <el-menu-item v-else :index="m.path">
                  <el-icon v-if="m.icon"><component :is="m.icon" /></el-icon>
                  <span>{{ m.menu_name }}</span>
                </el-menu-item>
              </template>
            </el-sub-menu>
            <el-menu-item v-else :index="dir.path">
              <el-icon v-if="dir.icon"><component :is="dir.icon" /></el-icon>
              <span>{{ dir.menu_name }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </el-scrollbar>
      <div class="sidebar__foot">V2.0 · 多并发架构</div>
    </el-aside>

    <!-- ============ 主体 ============ -->
    <el-container>
      <el-header class="topbar" height="56px">
        <div class="topbar__title">{{ $route.meta.title || "" }}</div>

        <!-- 顶栏全局搜索（核心需求） -->
        <div class="topbar__search" v-click-outside="closeSuggest">
          <el-input
            v-model="kw"
            placeholder="全局搜索：资产编码 / 名称 / 规格 / 品牌 / 位置"
            clearable
            :prefix-icon="Search"
            @input="onSearch"
            @keyup.enter="goSearch"
            @focus="kw && onSearch()"
          />
          <transition name="fade">
            <div v-if="suggestions.length && showSuggest" class="suggest card">
              <div class="suggest__head">
                资产匹配 <b class="num">{{ totalHits }}</b> 条
                <a class="suggest__more" @click="goSearch">查看全部 →</a>
              </div>
              <div
                v-for="s in suggestions"
                :key="s.id"
                class="suggest__item"
                @click="$router.push(`/asset/list?focus=${s.id}`)"
              >
                <span class="suggest__code num">{{ s.asset_code }}</span>
                <span class="suggest__name">{{ s.asset_name }}</span>
                <span class="suggest__cat" v-if="s.category_name">{{ s.category_name }}</span>
                <el-tag size="small" :type="s.status === 1 ? 'success' : s.status === 2 ? 'primary' : 'info'">
                  {{ assetStatusName(s.status) }}
                </el-tag>
              </div>
            </div>
          </transition>
        </div>

        <!-- 消息中心（方案模块7：站内信/待办推送） -->
        <el-dropdown @command="onMsgCmd" class="topbar__bell-wrap">
          <span class="topbar__bell">
            <el-badge :value="unread" :hidden="!unread" :max="99">
              <el-icon :size="20"><Bell /></el-icon>
            </el-badge>
          </span>
          <template #dropdown>
            <el-dropdown-menu style="min-width: 340px">
              <el-dropdown-item disabled style="font-weight: 600">
                消息通知（未读 {{ unread }}）
              </el-dropdown-item>
              <el-dropdown-item
                v-for="m in recentMsgs" :key="m.id" divided
                :disabled="false" @click="onMsgClick(m)"
              >
                <div class="msg-item">
                  <span class="msg-dot" :class="{ on: m.is_read === 0 }"></span>
                  <div style="flex: 1; min-width: 0">
                    <div class="msg-title">{{ m.title }}</div>
                    <div class="msg-time">{{ fmtDateTime(m.send_time || m.create_time) }}</div>
                  </div>
                </div>
              </el-dropdown-item>
              <el-dropdown-item v-if="!recentMsgs.length" disabled>暂无消息</el-dropdown-item>
              <el-dropdown-item divided command="all">查看全部消息 →</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-dropdown @command="onUserCmd">
          <span class="topbar__user">
            <el-avatar :size="30" class="topbar__avatar">{{ (user?.real_name || "用")[0] }}</el-avatar>
            <span class="topbar__uname">{{ user?.real_name }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled command="info">
                {{ user?.username }} · {{ permLabel }}
              </el-dropdown-item>
              <el-dropdown-item command="pwd">
                <el-icon><Lock /></el-icon>修改密码
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="main">
        <router-view :key="$route.fullPath" />
      </el-main>
    </el-container>

    <!-- 修改密码弹窗 -->
    <el-dialog v-model="pwdDialog" title="修改密码" width="380px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="原密码">
          <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="输入当前密码" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pwdForm.confirm" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialog = false">取消</el-button>
        <el-button type="primary" :loading="pwdSaving" @click="savePassword">确认修改</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Search, Lock } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useAuthStore } from "../stores/auth";
import { searchApi, msgApi, authApi } from "../api";
import { assetStatusName, fmtDateTime } from "../utils/constants";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const user = computed(() => auth.user);
const permLabel = computed(() => (auth.isSuperAdmin ? "超级管理员" : `${auth.perms.length} 项权限`));

// ---- 菜单树（支持目录嵌套，如 盘点管理 > 易耗品 > 物料档案）----
const menuTree = computed(() => {
  const all = auth.menus || [];
  const byParent = {};
  for (const m of all) (byParent[m.parent_id || 0] ||= []).push(m);
  const build = (pid) =>
    (byParent[pid] || [])
      .slice()
      .sort((a, b) => a.sort - b.sort)
      .map((m) => ({ ...m, children: build(m.id) }));
  return build(0);
});

// ---- 顶栏全局搜索 ----
const kw = ref("");
const showSuggest = ref(false);
const suggestions = ref([]);
const totalHits = ref(0);
let timer = null;

function onSearch() {
  clearTimeout(timer);
  if (!kw.value.trim()) {
    suggestions.value = [];
    showSuggest.value = false;
    return;
  }
  timer = setTimeout(async () => {
    const res = await searchApi.quick({ keyword: kw.value.trim(), limit: 8 });
    suggestions.value = res;
    totalHits.value = res.length;
    showSuggest.value = true;
  }, 300);
}
function closeSuggest() {
  showSuggest.value = false;
}
function goSearch() {
  closeSuggest();
  router.push({ path: "/search", query: { keyword: kw.value.trim() } });
}

// v-click-outside 指令（简单实现）
const vClickOutside = {
  mounted(el, binding) {
    el.__clickOutside__ = (e) => {
      if (!(el === e.target || el.contains(e.target))) binding.value();
    };
    document.addEventListener("click", el.__clickOutside__);
  },
  unmounted(el) {
    document.removeEventListener("click", el.__clickOutside__);
  },
};

// ---- 修改密码 ----
const pwdDialog = ref(false);
const pwdSaving = ref(false);
const pwdForm = { old_password: "", new_password: "", confirm: "" };

function onUserCmd(cmd) {
  if (cmd === "logout") {
    auth.logout();
    router.push("/login");
  } else if (cmd === "pwd") {
    pwdForm.old_password = "";
    pwdForm.new_password = "";
    pwdForm.confirm = "";
    pwdDialog.value = true;
  }
}

async function savePassword() {
  if (!pwdForm.old_password) return ElMessage.warning("请输入原密码");
  if (pwdForm.new_password.length < 6) return ElMessage.warning("新密码至少 6 位");
  if (pwdForm.new_password !== pwdForm.confirm) return ElMessage.warning("两次输入不一致");
  pwdSaving.value = true;
  try {
    await authApi.changePassword({ old_password: pwdForm.old_password, new_password: pwdForm.new_password });
    ElMessage.success("密码已修改，请重新登录");
    pwdDialog.value = false;
    setTimeout(() => { auth.logout(); router.push("/login"); }, 1200);
  } finally {
    pwdSaving.value = false;
  }
}

// ---- 消息通知（方案模块7） ----
const unread = ref(0);
const recentMsgs = ref([]);
async function loadMsgs() {
  try {
    const [u, l] = await Promise.all([
      msgApi.unread(),
      msgApi.list({ page: 1, page_size: 8, is_read: 0 }),
    ]);
    unread.value = u.count || 0;
    recentMsgs.value = l.records || [];
  } catch {
    /* 忽略 */
  }
}
async function onMsgClick(m) {
  if (m.is_read === 0) {
    await msgApi.read(m.id);
    unread.value = Math.max(0, unread.value - 1);
  }
  loadMsgs();
}
function onMsgCmd(cmd) {
  if (cmd === "all") router.push("/messages");
}

// 轮询未读数（优化：10s 拉一次，更及时的更新；卸载时清理，避免定时器泄漏）
let pollTimer = null;
onMounted(() => {
  loadMsgs();
  pollTimer = setInterval(loadMsgs, 10000);
});
onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<style scoped>
.layout { height: 100vh; }

/* ---------- 侧边栏 ---------- */
.sidebar {
  background: linear-gradient(180deg, var(--navy) 0%, #0f2135 100%);
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 10;
}
.sidebar::after {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, transparent, rgba(176, 122, 46, 0.4), transparent);
}
.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.sidebar__mark {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  background: linear-gradient(135deg, var(--gold), var(--gold-deep));
  color: #fff;
  font-family: var(--serif);
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(176, 122, 46, 0.35);
}
.sidebar__name { display: flex; flex-direction: column; line-height: 1.2; }
.sidebar__name b { color: #fff; font-size: 14px; font-family: var(--serif); letter-spacing: 1px; }
.sidebar__name span { color: rgba(184, 197, 210, 0.5); font-size: 9px; letter-spacing: 1.5px; }
.sidebar__scroll { flex: 1; }
.sidebar__foot {
  padding: 10px;
  text-align: center;
  color: rgba(184, 197, 210, 0.35);
  font-size: 10px;
  letter-spacing: 2px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.el-menu) { border-right: none; padding: 6px 8px; }
:deep(.el-menu-item), :deep(.el-sub-menu__title) { height: 44px; border-radius: 4px; margin: 2px 0; }
:deep(.el-menu-item:hover), :deep(.el-sub-menu__title:hover) { background: rgba(255, 255, 255, 0.06) !important; }
:deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(176, 122, 46, 0.28), rgba(176, 122, 46, 0.08)) !important;
  position: relative;
}
:deep(.el-menu-item.is-active)::before {
  content: "";
  position: absolute;
  left: 0;
  top: 20%;
  bottom: 20%;
  width: 3px;
  border-radius: 2px;
  background: var(--gold);
}
:deep(.el-sub-menu .el-menu) { background: rgba(0, 0, 0, 0.15) !important; border-radius: 4px; }

/* ---------- 顶栏 ---------- */
.topbar {
  background: var(--card);
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 22px;
  z-index: 5;
}
.topbar__title {
  font-family: var(--serif);
  font-size: 16px;
  font-weight: 700;
  color: var(--navy);
  white-space: nowrap;
}
.topbar__search { position: relative; flex: 1; max-width: 560px; }
.topbar__search :deep(.el-input__wrapper) {
  border-radius: 18px;
  background: var(--bg);
  box-shadow: none;
  border: 1px solid var(--line);
}
.topbar__search :deep(.el-input__wrapper.is-focus) { border-color: var(--gold); }
.topbar__bell-wrap { margin-left: auto; cursor: pointer; display: flex; align-items: center; }
.topbar__bell { display: flex; align-items: center; padding: 4px 6px; border-radius: 6px; }
.topbar__bell:hover { background: rgba(176, 122, 46, 0.08); }
.topbar__user { display: flex; align-items: center; gap: 8px; cursor: pointer; margin-left: 10px; }
.topbar__avatar { background: var(--navy); color: #fff; font-family: var(--serif); }
.topbar__uname { font-size: 13px; color: var(--ink); }
.msg-item { display: flex; align-items: flex-start; gap: 8px; padding: 2px 0; max-width: 360px; }
.msg-dot { width: 8px; height: 8px; border-radius: 50%; background: #dcdfe6; margin-top: 5px; flex-shrink: 0; }
.msg-dot.on { background: var(--danger, #d0453e); }
.msg-title { font-size: 13px; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msg-time { font-size: 11px; color: #9aa5b1; margin-top: 2px; }

/* 搜索建议下拉 */
.suggest {
  position: absolute;
  top: 42px;
  left: 0;
  right: 0;
  z-index: 100;
  max-height: 420px;
  overflow-y: auto;
  padding: 4px 0;
}
.suggest__head {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  font-size: 12px;
  color: var(--ink-3);
  border-bottom: 1px solid var(--line);
}
.suggest__more { margin-left: auto; color: var(--brand); cursor: pointer; }
.suggest__more:hover { text-decoration: underline; }
.suggest__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  cursor: pointer;
  border-bottom: 1px dashed #f0ede5;
}
.suggest__item:hover { background: #faf6ec; }
.suggest__code { color: var(--gold-deep); font-size: 12px; width: 158px; flex-shrink: 0; }
.suggest__name { flex: 1; color: var(--ink); }
.suggest__cat { color: var(--ink-3); font-size: 12px; }

.main { padding: 0; overflow: hidden; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s, transform 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
