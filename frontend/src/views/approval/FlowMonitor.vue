<template>
  <div class="page">
    <div class="page__head">
      <div>
        <h1 class="page__title">流程监控</h1>
        <span class="page__sub">全部审批实例汇总 · 审批中可终止 / 删除（管理员）· 点击查看内容与审批进度</span>
      </div>
      <el-button type="primary" plain :icon="Refresh" @click="loadAll">刷新</el-button>
    </div>

    <!-- 汇总卡片 -->
    <div class="stat-row">
      <div v-for="s in statCards" :key="s.label" class="stat-card" @click="goTab(s)" :class="{ clickable: s.status !== null }">
        <div class="stat-card__num">{{ s.count }}</div>
        <div class="stat-card__label">{{ s.label }}</div>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-radio-group v-model="tab" @change="onTab">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="1">审批中</el-radio-button>
          <el-radio-button value="2">已通过</el-radio-button>
          <el-radio-button value="3">已驳回</el-radio-button>
          <el-radio-button value="4">已撤销</el-radio-button>
          <el-radio-button value="5">已终止</el-radio-button>
        </el-radio-group>
        <el-select v-model="bizType" clearable placeholder="单据类型" style="width: 140px" @change="onTab">
          <el-option v-for="(l, k) in BIZ_LABEL" :key="k" :label="l" :value="k" />
        </el-select>
        <el-input v-model="keyword" placeholder="单据编号" clearable style="width: 180px" @keyup.enter="onTab" @clear="onTab" />
        <el-button type="primary" @click="onTab">查询</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="biz_no" label="单据编号" width="150" />
        <el-table-column label="单据类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.biz_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="flow_name" label="流程" width="150" show-overflow-tooltip />
        <el-table-column prop="apply_user_name" label="申请人" width="90" />
        <el-table-column prop="initiator_name" label="发起人" width="90" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="STATUS_TYPE[row.status] || 'info'">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前节点" width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.status === 1 ? row.current_node || "-" : "-" }}</template>
        </el-table-column>
        <el-table-column label="发起时间" width="150">
          <template #default="{ row }">{{ fmtDateTime(row.start_time) }}</template>
        </el-table-column>
        <el-table-column label="结束信息" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.finish_time">{{ row.finish_by_name || "系统" }} · {{ fmtDateTime(row.finish_time) }}</span>
            <span v-else class="text-muted">-</span>
            <span v-if="row.finish_note"> · {{ row.finish_note }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openProgress(row)">进度</el-button>
            <el-button link type="primary" size="small" @click="openBiz(row)">查看单据</el-button>
            <template v-if="row.status === 1">
              <el-button v-if="canWithdraw(row)" link type="warning" size="small" @click="withdraw(row)">撤销</el-button>
              <el-button v-if="isAdmin" link type="danger" size="small" @click="terminate(row)">终止</el-button>
              <el-button v-if="isAdmin" link type="danger" size="small" @click="del(row)">删除</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 条</span>
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="load"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { docApi, monitorApi } from "../../api";
import { fmtDateTime } from "../../utils/constants";
import { pushSafe } from "../../utils/nav";
import { useAuthStore } from "../../stores/auth";

const router = useRouter();
const auth = useAuthStore();
const isAdmin = computed(() => auth.isSuperAdmin);

const BIZ_LABEL = {
  purchase: "采购申请", stock_in: "入库单", stock_out: "出库单", transfer: "调拨单", scrap: "报废单",
  borrow: "借用单", return: "归还单",
  con_purchase: "易耗品采购单", con_inbound: "易耗品入库单", con_issue: "易耗品领用单",
};
const STATUS_TYPE = { 1: "warning", 2: "success", 3: "danger", 4: "info", 5: "info" };

const tab = ref("all");
const bizType = ref("");
const keyword = ref("");
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 15;
const loading = ref(false);
const stats = ref({ by_status: {} });

const statCards = computed(() => {
  const bs = stats.value.by_status || {};
  return [
    { label: "实例总数", count: stats.value.total ?? 0, status: null, tab: "all" },
    { label: "审批中", count: bs[1] || 0, status: 1, tab: "1" },
    { label: "已通过", count: bs[2] || 0, status: 2, tab: "2" },
    { label: "已驳回", count: bs[3] || 0, status: 3, tab: "3" },
    { label: "已撤销", count: bs[4] || 0, status: 4, tab: "4" },
    { label: "已终止", count: bs[5] || 0, status: 5, tab: "5" },
  ];
});

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize };
    if (tab.value !== "all") params.status = Number(tab.value);
    if (bizType.value) params.biz_type = bizType.value;
    if (keyword.value.trim()) params.keyword = keyword.value.trim();
    const res = await monitorApi.list(params);
    rows.value = res.records || [];
    total.value = res.total || 0;
  } finally {
    loading.value = false;
  }
}

function onTab() {
  page.value = 1;
  load();
}

async function loadStats() {
  stats.value = await monitorApi.stats();
}

function loadAll() {
  page.value = 1;
  load();
  loadStats();
}

function openProgress(row) {
  router.push(`/doc/progress/${row.id}`);
}
function openBiz(row) {
  pushSafe(router, `/doc/detail/${row.biz_type}/${row.biz_id}`);
}
function canWithdraw(row) {
  return isAdmin.value || auth.user?.id === row.initiator_id;
}

async function withdraw(row) {
  try {
    await ElMessageBox.confirm(`撤销后单据作废且不可恢复，确认撤销「${row.biz_no}」？`, "撤销申请", { type: "warning" });
  } catch {
    return;
  }
  await docApi.withdraw(row.id);
  ElMessage.success("已撤销");
  loadAll();
}

async function terminate(row) {
  try {
    const { value } = await ElMessageBox.prompt("终止原因（可留空）", `终止「${row.biz_no}」的审批流程`, {
      confirmButtonText: "终止",
      cancelButtonText: "取消",
      inputType: "textarea",
      type: "warning",
    });
    await docApi.terminate(row.id, value || null);
    ElMessage.success("已终止");
    loadAll();
  } catch {
    /* 用户取消 */
  }
}

async function del(row) {
  try {
    await ElMessageBox.confirm(
      `删除后实例记录将隐藏、单据作废（${row.biz_no}），进度页仍可按原链接查看。确认删除？`,
      "删除确认",
      { type: "warning", confirmButtonText: "确认删除", confirmButtonClass: "el-button--danger" }
    );
  } catch {
    return;
  }
  await docApi.delInstance(row.id);
  ElMessage.success("已删除");
  loadAll();
}

onMounted(loadAll);
</script>

<style scoped>
.stat-row { display: flex; gap: 12px; flex-wrap: wrap; }
.stat-card {
  flex: 1; min-width: 110px; background: #fff; border: 1px solid var(--line, #e7e3d9);
  border-radius: 8px; padding: 12px 16px; text-align: center;
}
.stat-card.clickable { cursor: pointer; transition: border-color 0.15s; }
.stat-card.clickable:hover { border-color: var(--brand, #b07a2e); }
.stat-card__num { font-size: 22px; font-weight: 700; color: var(--ink); }
.stat-card__label { font-size: 12px; color: #8a8f98; margin-top: 2px; }
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
