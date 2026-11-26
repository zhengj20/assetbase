<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">操作日志</h1>
      <span class="page__sub">全链路审计 · 写操作留痕</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.module" placeholder="模块（如 资产档案）" clearable :prefix-icon="Search" style="width: 180px" @keyup.enter="load" />
        <el-select v-model="q.user_id" placeholder="操作人" clearable filterable style="width: 150px" @change="page = 1, load()">
          <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="log_id" label="ID" width="80" />
        <el-table-column label="操作人" width="100">
          <template #default="{ row }">{{ userName(row.user_id) }}</template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="110" show-overflow-tooltip />
        <el-table-column prop="operation" label="操作" width="130" show-overflow-tooltip />
        <el-table-column prop="method" label="方法" width="80" align="center">
          <template #default="{ row }">
            <el-tag
              size="small" effect="plain"
              :type="row.method === 'GET' ? 'info' : row.method === 'POST' ? 'success' : row.method === 'PUT' ? 'warning' : 'danger'"
            >{{ row.method }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="request_url" label="请求地址" min-width="260" show-overflow-tooltip>
          <template #default="{ row }"><span class="num">{{ row.request_url }}</span></template>
        </el-table-column>
        <el-table-column label="结果" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.result === 1 ? 'success' : 'danger'" size="small">
              {{ row.result === 1 ? "成功" : "失败" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="130" />
        <el-table-column label="耗时" width="90" align="right">
          <template #default="{ row }">
            <span class="num" :class="{ slow: row.cost_ms > 500 }">{{ row.cost_ms != null ? `${row.cost_ms}ms` : "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="时间" width="160" :formatter="(_, __, v) => fmtDateTime(v)" />
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 条日志</span>
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
import { onMounted, reactive, ref } from "vue";
import { Search } from "@element-plus/icons-vue";
import { sysApi } from "../../api";
import { fmtDateTime } from "../../utils/constants";

const loading = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const q = reactive({ module: "", user_id: null });

const users = ref([]);
const userName = (id) => users.value.find((u) => u.id === id)?.real_name || id || "-";

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.module) params.module = q.module;
    if (q.user_id) params.user_id = q.user_id;
    const res = await sysApi.logs(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}
function reset() {
  Object.assign(q, { module: "", user_id: null });
  page.value = 1;
  load();
}

onMounted(async () => {
  const us = await sysApi.users({ page: 1, page_size: 200 });
  users.value = us.records;
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.slow { color: var(--danger); }
</style>
