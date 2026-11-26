<template>
  <div class="page" v-loading="loading">
    <div class="page__head">
      <h1 class="page__title">工作台</h1>
      <span class="page__sub">{{ user?.real_name }}，{{ today }}</span>
    </div>

    <div class="grid">
      <!-- 待办事项 -->
      <div class="card wb-card">
        <div class="wb-card__head">
          <span class="sec-title" style="margin: 0">待办事项</span>
          <el-badge :value="todos.length" :hidden="!todos.length" :max="99" />
        </div>
        <div class="wb-card__body">
          <template v-if="todos.length">
            <div v-for="(t, i) in todos" :key="i" class="todo-item" @click="goTodo(t)">
              <span class="todo-dot" :class="`todo-dot--${t.biz_type}`"></span>
              <div class="todo-info">
                <span class="todo-type">{{ bizTypeLabel(t.biz_type) }}</span>
                <span class="todo-node">{{ t.node_name }}</span>
              </div>
              <span class="todo-time">{{ relTime(t.arrive_time) }}</span>
            </div>
          </template>
          <el-empty v-else description="暂无待办事项" :image-size="64" />
        </div>
      </div>

      <!-- 发起审批 -->
      <div class="card wb-card">
        <div class="wb-card__head">
          <span class="sec-title" style="margin: 0">发起审批</span>
        </div>
        <div class="wb-card__body">
          <div class="doc-grid">
            <div v-for="d in docTypes" :key="d.name" class="doc-btn" @click="router.push(d.path)">
              <el-icon :size="22"><component :is="d.icon" /></el-icon>
              <span>{{ d.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 消息 -->
      <div class="card wb-card">
        <div class="wb-card__head">
          <span class="sec-title" style="margin: 0">消息</span>
          <a class="wb-card__link" @click="router.push('/messages')">查看全部</a>
        </div>
        <div class="wb-card__body">
          <template v-if="unreadMessages.length">
            <div v-for="m in unreadMessages" :key="m.id" class="msg-item" @click="viewMessage(m)">
              <div class="msg-left">
                <span v-if="m.is_read === 0" class="msg-unread-dot"></span>
                <span class="msg-title" :class="{ 'msg-title--unread': m.is_read === 0 }">{{ m.title }}</span>
              </div>
              <div class="msg-right">
                <el-tag size="small" :type="msgTypeTag(m.msg_type)" effect="plain">{{ msgTypeLabel(m.msg_type) }}</el-tag>
                <span class="msg-time">{{ fmtDateTime(m.send_time || m.create_time) }}</span>
              </div>
            </div>
          </template>
          <el-empty v-else description="暂无未读消息" :image-size="64" />
        </div>
      </div>

      <!-- 日历 -->
      <div class="card wb-card">
        <div class="wb-card__head">
          <div class="cal-nav">
            <span class="cal-nav__btn" @click="prevPeriod">&lt;</span>
            <span class="cal-nav__label">{{ calLabel }}</span>
            <span class="cal-nav__btn" @click="nextPeriod">&gt;</span>
          </div>
          <div class="cal-toggle">
            <span class="cal-toggle__item" :class="{ 'cal-toggle__item--active': calView === 'month' }" @click="switchView('month')">月</span>
            <span class="cal-toggle__item" :class="{ 'cal-toggle__item--active': calView === 'week' }" @click="switchView('week')">周</span>
          </div>
        </div>
        <div class="wb-card__body">
          <!-- 月度视图 -->
          <div v-if="calView === 'month'" class="cal-grid">
            <div v-for="w in calWeekdays" :key="w" class="cal-head">{{ w }}</div>
            <div
              v-for="(cell, idx) in calCells"
              :key="idx"
              class="cal-cell"
              :class="{ 'cal-cell--muted': cell.other, 'cal-cell--today': cell.today, 'cal-cell--active': cell.dateStr === selectedDate }"
              @click="openDayDialog(cell)"
            >
              <span class="cal-cell__num">{{ cell.day }}</span>
              <div class="cal-dots" v-if="cell.events.length">
                <span v-for="(e, i) in cell.events.slice(0, 3)" :key="i" class="cal-dot" :class="`cal-dot--${e.type}`"></span>
              </div>
            </div>
          </div>
          <!-- 周度视图 -->
          <div v-if="calView === 'week'" class="week-grid">
            <div v-for="(day, di) in weekDays" :key="di" class="week-col"
              :class="{ 'week-col--today': day.isToday, 'week-col--active': day.dateStr === selectedDate }"
              @click="openDayDialog(day)">
              <div class="week-col__head">
                <span class="week-col__dow">{{ calWeekdays[day.dow] }}</span>
                <span class="week-col__num">{{ day.dateStr.slice(5) }}</span>
              </div>
              <div class="week-col__events">
                <div v-for="(e, ei) in day.events" :key="ei" class="week-event" :class="`week-event--${e.type}`">
                  <el-icon v-if="e.type === 'reminder'" :size="12"><Bell /></el-icon>
                  <span class="week-event__label">{{ e.label }}</span>
                </div>
                <span v-if="!day.events.length" class="week-col__empty">—</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 日历弹窗 -->
    <el-dialog v-model="dayDialog" :title="`${selectedDate} 日程`" width="440px" :close-on-click-modal="false">
      <div class="day-events">
        <div v-for="(e, i) in dayEvents" :key="i" class="day-event">
          <span class="cal-dot" :class="`cal-dot--${e.type}`"></span>
          <el-icon v-if="e.type === 'reminder'" :size="13" class="day-event__bell"><Bell /></el-icon>
          <span class="day-event__title">{{ e.label }}</span>
          <el-button v-if="(e.type === 'record' || e.type === 'reminder') && e.record_id" link type="danger" size="small" @click="removeRecord(e.record_id)">删除</el-button>
        </div>
        <div v-if="!dayEvents.length" class="empty-hint">当天暂无日程</div>
      </div>
      <el-divider />
      <div class="day-form">
        <div class="sec-title" style="margin-top: 0">添加日程</div>
        <el-radio-group v-model="newRecord.rec_type" style="margin-bottom: 10px">
          <el-radio-button :value="1">工作记录</el-radio-button>
          <el-radio-button :value="2">提醒</el-radio-button>
        </el-radio-group>
        <el-input v-model="newRecord.title" placeholder="标题" style="margin-bottom: 10px" />
        <el-input v-model="newRecord.content" type="textarea" :rows="2" placeholder="内容（可选）" style="margin-bottom: 12px" />
        <div v-if="newRecord.rec_type === 2" style="margin-bottom: 12px">
          <span style="font-size: 12px; color: var(--ink-2); margin-right: 8px">提醒时间</span>
          <el-time-picker v-model="newRecord.remind_time" format="HH:mm" value-format="HH:mm" placeholder="选择时间" style="width: 140px" />
        </div>
        <el-button type="primary" :loading="saving" @click="saveRecord">保存</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  ShoppingCart, Box, Switch, Coin, Delete, Present, Bell,
} from "@element-plus/icons-vue";
import { workbenchApi, msgApi } from "../api";
import { useAuthStore } from "../stores/auth";
import { fmtDateTime } from "../utils/constants";

const router = useRouter();
const auth = useAuthStore();
const user = computed(() => auth.user);
const today = new Date().toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" });

const loading = ref(false);
const todos = ref([]);
const messages = ref([]);
const unreadMessages = computed(() => messages.value.filter((m) => m.is_read === 0));

// ---- 发起审批按钮 ----
const docTypes = [
  { name: "采购申请", icon: ShoppingCart, path: "/doc/purchase" },
  { name: "入库单", icon: Box, path: "/doc/stock-in" },
  { name: "出库单", icon: Box, path: "/doc/stock-out" },
  { name: "调拨单", icon: Switch, path: "/doc/transfer" },
  { name: "借用单", icon: Coin, path: "/doc/borrow" },
  { name: "报废单", icon: Delete, path: "/doc/scrap" },
  { name: "易耗品采购", icon: ShoppingCart, path: "/con/purchase" },
  { name: "易耗品领用", icon: Present, path: "/con/issue" },
];

// ---- 日历 ----
const calView = ref("month");
const now = new Date();
const calYear = ref(now.getFullYear());
const calMonth = ref(now.getMonth());
const calWeekStart = ref(getMonday(now));
const selectedDate = ref("");
const dayDialog = ref(false);
const dayEvents = ref([]);
const saving = ref(false);
const newRecord = reactive({ title: "", content: "", rec_type: 1, remind_time: "" });

const calWeekdays = ["日", "一", "二", "三", "四", "五", "六"];
const calCells = ref([]);
const weekDays = ref([]);

const calLabel = computed(() => {
  if (calView.value === "month") return `${calYear.value}年${calMonth.value + 1}月`;
  const s = calWeekStart.value;
  const e = new Date(s); e.setDate(e.getDate() + 6);
  const sm = `${s.getMonth() + 1}/${s.getDate()}`;
  const em = `${e.getMonth() + 1}/${e.getDate()}`;
  return `${s.getFullYear()} ${sm} - ${em}`;
});

function getMonday(d) {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.getFullYear(), d.getMonth(), diff);
}

function dateStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function switchView(v) {
  calView.value = v;
  fetchCalendar();
}

async function fetchCalendar() {
  try {
    if (calView.value === "month") {
      await fetchMonthCalendar();
    } else {
      await fetchWeekCalendar();
    }
  } catch {
    calCells.value = [];
    weekDays.value = [];
  }
}

async function fetchMonthCalendar() {
  const res = await workbenchApi.calendar({ year: calYear.value, month: calMonth.value + 1 });
  const events = res || [];
  const map = {};
  for (const e of events) {
    const d = (e.date || "").slice(0, 10);
    if (!d) continue;
    (map[d] ||= []).push({ ...e, type: e.type || "doc" });
  }
  const first = new Date(calYear.value, calMonth.value, 1);
  const startDay = first.getDay();
  const daysInMonth = new Date(calYear.value, calMonth.value + 1, 0).getDate();
  const todayStr = dateStr(new Date());

  const cells = [];
  for (let i = 0; i < startDay; i++) cells.push({ day: 0, other: true, dateStr: "", events: [] });
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${calYear.value}-${String(calMonth.value + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    cells.push({ day: d, other: false, dateStr: ds, today: ds === todayStr, events: map[ds] || [] });
  }
  while (cells.length % 7 !== 0) cells.push({ day: 0, other: true, dateStr: "", events: [] });
  calCells.value = cells;
}

async function fetchWeekCalendar() {
  const start = new Date(calWeekStart.value);
  const end = new Date(start); end.setDate(end.getDate() + 6);
  const res = await workbenchApi.calendarRange({ start: dateStr(start), end: dateStr(end) });
  const events = res || [];
  const map = {};
  for (const e of events) {
    const d = (e.date || "").slice(0, 10);
    if (!d) continue;
    (map[d] ||= []).push({ ...e, type: e.type || "doc" });
  }
  const todayStr = dateStr(new Date());
  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(start); d.setDate(d.getDate() + i);
    const ds = dateStr(d);
    days.push({ dateStr: ds, dow: d.getDay(), isToday: ds === todayStr, events: map[ds] || [] });
  }
  weekDays.value = days;
}

function prevPeriod() {
  if (calView.value === "month") {
    if (calMonth.value === 0) { calMonth.value = 11; calYear.value--; }
    else calMonth.value--;
  } else {
    calWeekStart.value = new Date(calWeekStart.value);
    calWeekStart.value.setDate(calWeekStart.value.getDate() - 7);
  }
  fetchCalendar();
}
function nextPeriod() {
  if (calView.value === "month") {
    if (calMonth.value === 11) { calMonth.value = 0; calYear.value++; }
    else calMonth.value++;
  } else {
    calWeekStart.value = new Date(calWeekStart.value);
    calWeekStart.value.setDate(calWeekStart.value.getDate() + 7);
  }
  fetchCalendar();
}

function openDayDialog(cell) {
  if (cell.other) return;
  selectedDate.value = cell.dateStr;
  dayEvents.value = cell.events || [];
  newRecord.title = "";
  newRecord.content = "";
  newRecord.rec_type = 1;
  newRecord.remind_time = "";
  dayDialog.value = true;
}

async function saveRecord() {
  if (!newRecord.title.trim()) { ElMessage.warning("请输入标题"); return; }
  saving.value = true;
  try {
    await workbenchApi.createWorkRecord({
      title: newRecord.title.trim(),
      content: newRecord.content.trim() || null,
      record_date: selectedDate.value,
      rec_type: newRecord.rec_type,
      remind_time: newRecord.rec_type === 2 ? (newRecord.remind_time || null) : null,
    });
    ElMessage.success("已保存");
    newRecord.title = "";
    newRecord.content = "";
    newRecord.remind_time = "";
    newRecord.rec_type = 1;
    fetchCalendar();
  } finally {
    saving.value = false;
  }
}

async function removeRecord(id) {
  try {
    await workbenchApi.delWorkRecord(id);
    ElMessage.success("已删除");
    fetchCalendar();
  } catch { /* error handled by interceptor */ }
}

// ---- 辅助 ----
const BIZ_TYPE_MAP = {
  purchase: "采购申请", purchase_apply: "采购申请", stock_in: "入库单", stock_out: "出库单",
  transfer: "调拨单", borrow: "借用单", return: "归还单",
  scrap: "报废单", con_purchase: "易耗品采购", con_inbound: "易耗品入库", con_issue: "易耗品领用",
};
function bizTypeLabel(t) { return BIZ_TYPE_MAP[t] || t; }

function msgTypeLabel(t) { return { 1: "审批", 2: "预警", 3: "系统" }[t] || "通知"; }
function msgTypeTag(t) { return { 1: "warning", 2: "danger", 3: "info" }[t] || "info"; }

function relTime(t) {
  if (!t) return "";
  const diff = Date.now() - new Date(t).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins}分钟前`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}小时前`;
  const days = Math.floor(hrs / 24);
  return `${days}天前`;
}

function goTodo(t) {
  pushSafe(router, `/doc/detail/${t.biz_type}/${t.biz_id}`);
}

async function viewMessage(m) {
  if (m.is_read === 0) {
    try {
      await msgApi.read(m.id);
      m.is_read = 1;
    } catch { /* 标记已读失败不影响跳转 */ }
  }
  router.push("/messages");
}

// ---- 初始化 ----
onMounted(async () => {
  loading.value = true;
  try {
    const res = await workbenchApi.summary();
    todos.value = res.todos || [];
    messages.value = res.messages || [];
    await fetchCalendar();
  } catch { /* error handled by interceptor */ } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  flex: 1;
  min-height: 0;
}
@media (max-width: 1200px) {
  .grid { grid-template-columns: 1fr; }
}

.wb-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  min-height: 280px;
}
.wb-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.wb-card__link {
  font-size: 12px;
  color: var(--brand);
  cursor: pointer;
  text-decoration: none;
}
.wb-card__link:hover { text-decoration: underline; }
.wb-card__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

/* ---- 待办 ---- */
.todo-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 0.15s;
}
.todo-item:hover { background: #faf6ec; }
.todo-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--brand);
  flex-shrink: 0;
}
.todo-dot--purchase, .todo-dot--con_purchase, .todo-dot--purchase_apply { background: var(--brand); }
.todo-dot--stock_in { background: var(--ok); }
.todo-dot--stock_out, .todo-dot--con_inbound { background: var(--gold); }
.todo-dot--transfer, .todo-dot--con_issue { background: #7a5fb0; }
.todo-dot--borrow { background: var(--warn); }
.todo-dot--return { background: #2a6da0; }
.todo-dot--scrap { background: var(--danger); }
.todo-info { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; }
.todo-type { font-size: 12px; color: var(--ink-2); white-space: nowrap; }
.todo-node { font-size: 12px; color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.todo-time { font-size: 11px; color: var(--ink-3); white-space: nowrap; }

/* ---- 发起审批 ---- */
.doc-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.doc-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 14px 6px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  font-size: 12px;
  color: var(--ink-2);
  cursor: pointer;
  transition: all 0.15s;
  background: #fff;
}
.doc-btn :deep(.el-icon) { color: var(--navy); font-size: 22px; }
.doc-btn:hover {
  border-color: var(--gold);
  box-shadow: 0 2px 10px rgba(176, 122, 46, 0.15);
  transform: translateY(-1px);
}

/* ---- 消息 ---- */
.msg-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px;
  border-bottom: 1px solid #f0ede5;
  cursor: pointer;
  border-radius: var(--radius);
}
.msg-item:hover { background: #faf6ec; }
.msg-item:last-child { border-bottom: none; }
.msg-left { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; }
.msg-unread-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gold);
  flex-shrink: 0;
}
.msg-title {
  font-size: 13px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.msg-title--unread { font-weight: 600; }
.msg-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.msg-time { font-size: 11px; color: var(--ink-3); }

/* ---- 日历导航 ---- */
.cal-nav {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cal-nav__btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  cursor: pointer;
  color: var(--ink-2);
  font-size: 14px;
  font-weight: 600;
  transition: background 0.15s;
}
.cal-nav__btn:hover { background: #f0ede5; }
.cal-nav__label { font-family: var(--serif); font-size: 14px; font-weight: 700; color: var(--navy); }

.cal-toggle {
  display: flex;
  border: 1px solid var(--line);
  border-radius: 4px;
  overflow: hidden;
}
.cal-toggle__item {
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
  color: var(--ink-3);
  transition: all 0.15s;
}
.cal-toggle__item--active {
  background: var(--navy);
  color: #fff;
}

/* ---- 月度日历 ---- */
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  text-align: center;
}
.cal-head {
  font-size: 11px;
  color: var(--ink-3);
  padding: 4px 0;
  font-weight: 600;
}
.cal-cell {
  padding: 6px 2px;
  border-radius: var(--radius);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  transition: background 0.15s;
}
.cal-cell:hover { background: #f5f2ea; }
.cal-cell--muted { opacity: 0.3; cursor: default; }
.cal-cell--muted:hover { background: transparent; }
.cal-cell--today .cal-cell__num {
  background: var(--navy);
  color: #fff;
  border-radius: 50%;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cal-cell--active { background: var(--gold-soft); }
.cal-cell__num { font-size: 12px; color: var(--ink); }
.cal-dots { display: flex; gap: 2px; }
.cal-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  display: inline-block;
}
.cal-dot--doc { background: var(--brand); }
.cal-dot--record { background: var(--ok); }
.cal-dot--reminder { background: var(--gold); }
.cal-dot--due { background: var(--danger); }

/* ---- 周度日历 ---- */
.week-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}
.week-col {
  border: 1px solid #f0ede5;
  border-radius: var(--radius);
  padding: 8px 6px;
  cursor: pointer;
  transition: all 0.15s;
  min-height: 120px;
  display: flex;
  flex-direction: column;
}
.week-col:hover { border-color: var(--gold); background: #faf8f2; }
.week-col--today .week-col__num { color: var(--brand); font-weight: 700; }
.week-col--active { border-color: var(--brand); background: var(--gold-soft); }
.week-col__head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f0ede5;
}
.week-col__dow { font-size: 11px; color: var(--ink-3); }
.week-col__num { font-size: 13px; font-weight: 600; color: var(--ink); }
.week-col__events { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.week-col__empty { font-size: 11px; color: var(--ink-3); text-align: center; margin-top: 12px; }
.week-event {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 3px 5px;
  border-radius: 3px;
  background: #f7f5f0;
  line-height: 1.3;
}
.week-event--doc { border-left: 2px solid var(--brand); }
.week-event--record { border-left: 2px solid var(--ok); }
.week-event--reminder { border-left: 2px solid var(--gold); }
.week-event--due { border-left: 2px solid var(--danger); }
.week-event__label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ---- 弹窗 ---- */
.day-events { display: flex; flex-direction: column; gap: 8px; }
.day-event {
  display: flex;
  align-items: center;
  gap: 8px;
}
.day-event__bell { color: var(--gold); }
.day-event__title { flex: 1; font-size: 13px; color: var(--ink); }
.day-form { margin-top: 4px; }
</style>
