<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">消息中心</h1>
      <span class="page__sub">审批待办 / 审批结果 / 系统通知</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-radio-group v-model="isRead" @change="page = 1, load()">
          <el-radio-button :value="null">全部</el-radio-button>
          <el-radio-button :value="0">未读</el-radio-button>
          <el-radio-button :value="1">已读</el-radio-button>
        </el-radio-group>
        <el-button type="primary" plain :icon="Check" style="margin-left: auto" @click="readAll">全部标为已读</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%" :row-class-name="rowClass" @row-click="onRowClick">
        <el-table-column label="状态" width="70" align="center">
          <template #default="{ row }">
            <span class="dot" :class="{ 'dot--unread': row.is_read === 0 }"></span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span :style="row.is_read === 0 ? 'font-weight: 600' : ''">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="280" show-overflow-tooltip class-name="text-muted" />
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.msg_type === 1 ? 'primary' : row.msg_type === 2 ? 'warning' : 'info'">
              {{ { 1: "审批", 2: "预警", 3: "系统" }[row.msg_type] || "系统" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtDateTime(row.send_time || row.create_time) }}</template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 条消息</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50, 100]" layout="sizes, prev, pager, next, jumper" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from "vue";
import { ElMessage } from "element-plus";
import { Check } from "@element-plus/icons-vue";
import { msgApi } from "../../api";
import { fmtDateTime } from "../../utils/constants";
import { getToken, tryRefresh } from "../../lib/auth-token";

const loading = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const isRead = ref(null);

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (isRead.value !== null) params.is_read = isRead.value;
    const res = await msgApi.list(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}

function rowClass({ row }) {
  return row.is_read === 0 ? "row-unread" : "";
}

async function onRowClick(row) {
  if (row.is_read === 0) {
    await msgApi.read(row.id);
    row.is_read = 1;
  }
}

async function readAll() {
  const res = await msgApi.readAll();
  ElMessage.success(`已将 ${res.count} 条消息标为已读`);
  load();
}

// ---- SSE 实时消息推送 ----
let es = null;
function disconnectSSE() {
  if (es) {
    es.close();
    es = null;
  }
}
function connectSSE() {
  disconnectSSE();
  const token = getToken();
  if (!token) return;
  es = new EventSource(`/api/v1/messages/subscribe?token=${encodeURIComponent(token)}`);
  es.onmessage = (e) => {
    let data;
    try {
      data = JSON.parse(e.data);
    } catch {
      return;
    }
    if (data.type !== "new_message") return; // heartbeat / connected 忽略
    ElMessage({ message: `新消息：${data.title || "您有一条新消息"}`, type: "info", duration: 4000 });
    load();
  };
  es.onerror = () => {
    // 内置重连仍会用旧 token，改为静默刷新后重连
    disconnectSSE();
    tryRefresh().then((ok) => {
      if (ok) setTimeout(connectSSE, 2000);
    });
  };
}

onMounted(() => {
  load();
  connectSSE();
});
onBeforeUnmount(disconnectSSE);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #dcdfe6;
}
.dot--unread { background: var(--danger, #d0453e); box-shadow: 0 0 0 3px rgba(208, 69, 62, 0.15); }
:deep(.row-unread) { background: #fdf8f2 !important; }
</style>
