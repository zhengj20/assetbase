<template>
  <div class="m">
    <!-- ============ 登录（无 token 时） ============ -->
    <div v-if="!token" class="m-login">
      <div class="m-login__brand">
        <div class="m-login__mark">固</div>
        <h1>移动端盘点</h1>
        <p>固定资产管理 · 扫码实盘</p>
      </div>
      <div class="m-card">
        <input v-model="login.username" class="m-input" placeholder="用户名" @keyup.enter="doLogin" />
        <input v-model="login.password" class="m-input" type="password" placeholder="密码" @keyup.enter="doLogin" />
        <button class="m-btn m-btn--primary" :disabled="busy" @click="doLogin">登录</button>
      </div>
    </div>

    <!-- ============ 任务选择 ============ -->
    <div v-else-if="!task" class="m-body">
      <div class="m-head">
        <h2>选择盘点任务</h2>
        <span class="m-head__sub">共 {{ tasks.length }} 个进行中任务</span>
      </div>
      <div v-if="loadingTasks" class="m-empty">加载中…</div>
      <div v-else-if="!tasks.length" class="m-empty">暂无进行中的盘点任务<br />请到 Web 端「盘点管理」创建</div>
      <div v-for="t in tasks" :key="t.id" class="m-card m-task" @click="pickTask(t)">
        <div class="m-task__name">{{ t.task_name }}</div>
        <div class="m-task__meta">
          <span class="m-tag" :class="t.status === 1 ? 'm-tag--run' : ''">{{ t.status === 1 ? '执行中' : '待执行' }}</span>
          <span class="m-muted">{{ t.book_total }} 项账面</span>
        </div>
      </div>
    </div>

    <!-- ============ 盘点执行 ============ -->
    <template v-else>
      <div class="m-head">
        <div>
          <h2>{{ task.task_name }}</h2>
          <span class="m-head__sub">{{ task.task_no }}</span>
        </div>
        <button class="m-btn m-btn--ghost m-btn--sm" @click="exitTask">退出</button>
      </div>

      <!-- 进度 -->
      <div class="m-card m-prog">
        <div class="m-prog__bar"><i :style="{ width: progPct + '%' }"></i></div>
        <div class="m-prog__txt">
          已盘 <b class="num">{{ sum.checked }}</b> / {{ sum.book_total }}
          <span class="m-muted">未盘 {{ sum.unchecked }}</span>
        </div>
      </div>

      <!-- 扫码 -->
      <div class="m-card">
        <div class="m-sec">扫码定位</div>
        <div ref="scanBox" class="m-scan"></div>
        <div class="m-scan__ops">
          <button class="m-btn" :disabled="busy" @click="toggleScan">{{ scanning ? '停止扫码' : '开始扫码' }}</button>
          <span class="m-muted" v-if="scanErr">{{ scanErr }}</span>
        </div>
        <div class="m-manual">
          <input v-model="manualCode" class="m-input" placeholder="或手动输入资产编码/二维码内容" @keyup.enter="locate(manualCode)" />
          <button class="m-btn" :disabled="busy" @click="locate(manualCode)">定位</button>
        </div>
      </div>

      <!-- 定位结果 -->
      <div v-if="found" class="m-card m-found">
        <div class="m-found__top">
          <div>
            <div class="m-found__code num">{{ found.asset_code }}</div>
            <div class="m-found__name">{{ found.asset_name }}</div>
            <div class="m-muted">账面：{{ bookStatus(found.book_status) }} · {{ found.book_location || '未记位置' }}</div>
          </div>
          <el-icon v-if="found.check_result" class="m-found__ok"><CircleCheckFilled /></el-icon>
        </div>

        <div v-if="found.check_result" class="m-done">
          已盘：{{ resultLabel(found.check_result) }}
          <span v-if="found.actual_location" class="m-muted">（{{ found.actual_location }}）</span>
        </div>
        <div v-else class="m-found__acts">
          <button class="m-btn m-btn--ok" :disabled="busy" @click="record(1)">✓ 在位正常</button>
          <button class="m-btn m-btn--warn" :disabled="busy" @click="record(4)">⚑ 位置异常</button>
          <button class="m-btn m-btn--bad" :disabled="busy" @click="record(3)">✗ 盘亏（未见）</button>
          <input v-if="locMode" v-model="actualLoc" class="m-input" placeholder="实盘位置（位置异常时填写）" @keyup.enter="record(4)" />
        </div>
      </div>

      <!-- 盘盈登记 -->
      <div v-if="surplusMode" class="m-card">
        <div class="m-sec">登记盘盈（账外实物）</div>
        <input v-model="surplus.name" class="m-input" placeholder="资产名称" />
        <div class="m-row">
          <input v-model="surplus.price" class="m-input" type="number" placeholder="原值(选填)" />
          <input v-model="surplus.loc" class="m-input" placeholder="所在位置" />
        </div>
        <button class="m-btn m-btn--primary" :disabled="busy" @click="saveSurplus">确认登记盘盈</button>
      </div>

      <!-- 最近记录 -->
      <div class="m-card">
        <div class="m-sec">最近盘点记录</div>
        <div v-if="!recent.length" class="m-muted" style="padding: 8px 0">暂无记录</div>
        <div v-for="r in recent" :key="r.id" class="m-rec">
          <span class="m-rec__code num">{{ r.asset_code || r.surplus_name }}</span>
          <span class="m-tag" :class="resultTag(r.check_result)">{{ resultLabel(r.check_result) }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { CircleCheckFilled } from "@element-plus/icons-vue";
import { Html5Qrcode } from "html5-qrcode";
import { authApi, checkApi } from "../../api";

const token = ref(localStorage.getItem("token"));
const busy = ref(false);
const login = ref({ username: "", password: "" });

const tasks = ref([]);
const task = ref(null);
const loadingTasks = ref(false);
const sum = ref({ checked: 0, book_total: 0, unchecked: 0 });
const progPct = computed(() => (sum.value.book_total ? Math.round((sum.value.checked / sum.value.book_total) * 100) : 0));

const found = ref(null);
const locMode = ref(false);
const actualLoc = ref("");
const surplusMode = ref(false);
const surplus = ref({ name: "", price: "", loc: "" });
const recent = ref([]);

const scanBox = ref(null);
const manualCode = ref("");
const scanning = ref(false);
const scanErr = ref("");
let scanner = null;

const RESULT = { 1: "正常", 2: "盘盈", 3: "盘亏", 4: "位置异常" };
const resultLabel = (v) => RESULT[v] || (v == null ? "未盘" : v);
const resultTag = (v) => ({ 1: "m-tag--ok", 2: "m-tag--ok", 3: "m-tag--bad", 4: "m-tag--warn" }[v] || "");
const bookStatus = (v) => ({ 0: "待入库", 1: "在库", 2: "领用中", 3: "维修中", 4: "调拨中", 5: "已报废", 6: "已处置" }[v] || "未知");

async function doLogin() {
  if (!login.value.username || !login.value.password) return ElMessage.warning("请输入用户名和密码");
  busy.value = true;
  try {
    const res = await authApi.login(login.value);
    localStorage.setItem("token", res.token);
    localStorage.setItem("user", JSON.stringify(res.user));
    localStorage.setItem("perms", JSON.stringify(res.perms || []));
    token.value = res.token;
    await loadTasks();
  } finally {
    busy.value = false;
  }
}

async function loadTasks() {
  loadingTasks.value = true;
  try {
    const res = await checkApi.tasks({ page: 1, page_size: 50 });
    tasks.value = (res.records || []).filter((t) => [0, 1].includes(t.status));
  } finally {
    loadingTasks.value = false;
  }
}

async function pickTask(t) {
  task.value = t;
  found.value = null;
  recent.value = [];
  await refresh();
}

async function refresh() {
  const [s, items] = await Promise.all([
    checkApi.summary(task.value.id),
    checkApi.items(task.value.id, { page: 1, page_size: 8, only_checked: true }),
  ]);
  sum.value = s;
  recent.value = items.records || [];
}

function exitTask() {
  stopScan();
  task.value = null;
  found.value = null;
}

async function locate(code) {
  code = (code || "").trim();
  if (!code) return ElMessage.warning("请输入或扫描资产编码");
  busy.value = true;
  try {
    const res = await checkApi.scan(task.value.id, code);
    found.value = res;
    locMode.value = false;
    actualLoc.value = "";
    surplusMode.value = false;
    stopScan();
  } catch (e) {
    const msg = e.response?.data?.detail || "";
    if (e.response?.status === 404) {
      surplusMode.value = true;
      surplus.value = { name: "", price: "", loc: "" };
    } else if (e.response?.status === 409) {
      ElMessage.warning(msg || "该资产不在本任务范围");
    }
  } finally {
    busy.value = false;
  }
}

async function record(result) {
  if (result === 4 && !actualLoc.value.trim()) {
    locMode.value = true;
    return ElMessage.warning("请填写实盘位置");
  }
  busy.value = true;
  try {
    await checkApi.record(found.value.id, {
      check_result: result,
      actual_location: result === 4 ? actualLoc.value.trim() : undefined,
    });
    ElMessage.success(result === 1 ? "已记录：在位正常" : result === 3 ? "已记录：盘亏" : "已记录：位置异常");
    found.value = { ...found.value, check_result: result, actual_location: result === 4 ? actualLoc.value : null };
    manualCode.value = "";
    await refresh();
  } finally {
    busy.value = false;
  }
}

async function saveSurplus() {
  if (!surplus.value.name.trim()) return ElMessage.warning("请填写盘盈资产名称");
  busy.value = true;
  try {
    await checkApi.surplus(task.value.id, {
      surplus_name: surplus.value.name.trim(),
      surplus_price: surplus.value.price || null,
      actual_location: surplus.value.loc.trim() || null,
    });
    ElMessage.success("盘盈已登记，完成盘点后自动生成入库单");
    surplusMode.value = false;
    await refresh();
  } finally {
    busy.value = false;
  }
}

// ---- 扫码 ----
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.connect(g);
    g.connect(ctx.destination);
    o.frequency.value = 1200;
    g.gain.value = 0.08;
    o.start();
    setTimeout(() => {
      o.stop();
      ctx.close();
    }, 120);
  } catch {
    /* 忽略音频失败 */
  }
}

async function toggleScan() {
  if (scanning.value) {
    stopScan();
    return;
  }
  if (!scanBox.value) return;
  scanErr.value = "";
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    scanErr.value =
      "浏览器未开放摄像头 API：iPhone 需先在「设置→通用→关于本机→证书信任设置」信任本机证书（本页根路径可下载 rootCA.pem），或手动输入编码";
    return;
  }
  scanner = scanner || new Html5Qrcode(scanBox.value);
  try {
    await Promise.race([
      scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 200, height: 140 } },
        async (text) => {
          beep();
          stopScan();
          await locate(text);
        },
        () => {}
      ),
      new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), 20000)),
    ]);
    scanning.value = true;
  } catch (e) {
    const msg = e?.message || String(e);
    if (!window.isSecureContext) {
      scanErr.value = "当前为 HTTP 地址，浏览器禁止调用摄像头：请用 https:// 打开本页，或手动输入编码";
    } else if (/timeout/i.test(msg)) {
      scanErr.value = "摄像头启动超时：iPhone 请在「证书信任设置」中信任本机证书；其他设备请检查相机权限，或手动输入编码";
    } else if (/not? ?found|permission|denied|insecure|https|not supported/i.test(msg)) {
      scanErr.value = "摄像头不可用（需已授权），请手动输入编码";
    } else {
      scanErr.value = `扫码启动失败：${msg}`;
    }
    scanning.value = false;
  }
}

async function stopScan() {
  scanning.value = false;
  if (scanner) {
    try {
      await scanner.stop();
      scanner.clear();
    } catch {
      /* 忽略 */
    }
    scanner = null;
  }
}

onMounted(async () => {
  if (token.value) await loadTasks();
});
onBeforeUnmount(stopScan);
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
.m-btn {
  padding: 12px 18px; border: 1px solid #e2e0d8; border-radius: 10px; background: #fff;
  font-size: 15px; color: #16283c; cursor: pointer; flex: 1;
}
.m-btn:disabled { opacity: 0.5; }
.m-btn--primary { background: #16283c; color: #fff; border-color: #16283c; width: 100%; }
.m-btn--ok { background: #1f8a4c; color: #fff; border-color: #1f8a4c; }
.m-btn--warn { background: #b07a2e; color: #fff; border-color: #b07a2e; }
.m-btn--bad { background: #b23b32; color: #fff; border-color: #b23b32; }
.m-btn--ghost { background: transparent; border-color: #d8d5cc; }
.m-btn--sm { padding: 8px 14px; font-size: 13px; flex: none; }
.m-row { display: flex; gap: 8px; }
.m-row .m-input { margin-bottom: 10px; }
.m-task__name { font-size: 15px; font-weight: 600; color: #16283c; margin-bottom: 8px; }
.m-task__meta { display: flex; align-items: center; gap: 10px; }
.m-tag { font-size: 12px; padding: 2px 10px; border-radius: 10px; background: #eef0f4; color: #5a6675; }
.m-tag--run { background: #e5f3ec; color: #1f8a4c; }
.m-tag--ok { background: #e5f3ec; color: #1f8a4c; }
.m-tag--warn { background: #f6ecd9; color: #b07a2e; }
.m-tag--bad { background: #f7e4e2; color: #b23b32; }
.m-prog__bar { height: 8px; border-radius: 6px; background: #eceae3; overflow: hidden; }
.m-prog__bar i { display: block; height: 100%; background: linear-gradient(90deg, #b07a2e, #d8a94e); }
.m-prog__txt { margin-top: 8px; font-size: 13px; color: #5a6675; display: flex; gap: 10px; align-items: center; }
.m-scan { width: 100%; border-radius: 10px; overflow: hidden; background: #101820; min-height: 160px; }
.m-scan :deep(video) { width: 100% !important; border-radius: 10px; }
.m-scan__ops { display: flex; align-items: center; gap: 12px; margin: 10px 0; }
.m-manual { display: flex; gap: 8px; }
.m-manual .m-input { margin-bottom: 0; }
.m-manual .m-btn { flex: none; }
.m-found__top { display: flex; justify-content: space-between; align-items: flex-start; }
.m-found__code { font-size: 15px; font-weight: 700; color: #16283c; }
.m-found__name { font-size: 14px; color: #5a6675; margin: 4px 0; }
.m-found__ok { font-size: 30px; color: #1f8a4c; }
.m-found__acts { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.m-found__acts .m-input { margin-bottom: 0; }
.m-done { margin-top: 10px; font-size: 14px; color: #1f8a4c; font-weight: 600; }
.m-rec { display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px dashed #eceae3; }
.m-rec:last-child { border-bottom: none; }
.m-rec__code { font-size: 13px; color: #16283c; }
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
