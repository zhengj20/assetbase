<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">我的审批</h1>
      <span class="page__sub">待办 / 已办 / 我发起的流程 · 通过即生效并联动资产状态</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-radio-group v-model="tab" @change="load">
          <el-radio-button value="todo">待办（{{ todos.length }}）</el-radio-button>
          <el-radio-button value="done">已办</el-radio-button>
          <el-radio-button value="mine">我发起的（{{ mine.length }}）</el-radio-button>
        </el-radio-group>
        <el-button type="primary" plain :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-table v-if="tab !== 'mine'" :data="filtered" v-loading="loading" height="100%">
        <el-table-column label="单据类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ BIZ_LABEL[row.biz_type] || row.biz_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="biz_no" label="单据编号" width="160" />
        <el-table-column prop="task.node_name" label="当前节点" width="120" />
        <el-table-column prop="apply_user_name" label="申请人" width="90" />
        <el-table-column label="到达时间" width="150">
          <template #default="{ row }">{{ fmtDateTime(row.task.arrive_time) }}</template>
        </el-table-column>
        <el-table-column label="我的动作" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.task.action === 1" type="success" size="small">已通过</el-tag>
            <el-tag v-else-if="row.task.action === 2" type="danger" size="small">已驳回</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="task.comment" label="审批意见" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.task?.comment || "-" }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <template v-if="tab === 'todo'">
              <el-button v-perm="'approval:approve'" link type="success" size="small" @click="approve(row, 1)">通过</el-button>
              <el-button v-perm="'approval:approve'" link type="danger" size="small" @click="approve(row, 2)">驳回</el-button>
              <el-button v-perm="'approval:delegate'" link size="small" @click="openSign(row)">加签</el-button>
              <el-button v-perm="'approval:delegate'" link size="small" @click="openAction(row, 'delegate')">委托</el-button>
              <el-button v-perm="'approval:approve'" link size="small" @click="openAction(row, 'back')">退回</el-button>
            </template>
            <el-button link type="primary" size="small" @click="openProgress(row)">进度</el-button>
            <el-button link type="primary" size="small" @click="openBiz(row)">查看单据</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-table v-else :data="mine" v-loading="loading" height="100%">
        <el-table-column label="单据类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ BIZ_LABEL[row.biz_type] || row.biz_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="biz_no" label="单据编号" width="160" />
        <el-table-column prop="flow_name" label="流程" width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="MINE_STATUS_TYPE[row.status] || 'info'">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_node" label="当前节点" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.status === 1 ? row.current_node || "-" : "-" }}</template>
        </el-table-column>
        <el-table-column prop="initiator_name" label="发起人" width="90" />
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
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="router.push(`/doc/progress/${row.id}`)">进度</el-button>
            <el-button link type="primary" size="small" @click="openBiz(row)">查看单据</el-button>
            <el-button v-if="row.status === 1" link type="warning" size="small" @click="withdrawMine(row)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">
          {{ tab === "todo" ? "等待您处理" : tab === "done" ? "历史审批记录" : "我发起的流程实例" }}
        </span>
      </div>

      <!-- 委托 / 退回 -->
      <ApprovalActionDialog
        v-model="actionVisible"
        :mode="actionMode"
        :task="actionTask"
        @done="load"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { docApi, sysApi } from "../../api";
import { fmtDateTime } from "../../utils/constants";
import { pushSafe } from "../../utils/nav";
import ApprovalActionDialog from "../../components/ApprovalActionDialog.vue";

const router = useRouter();

const BIZ_LABEL = {
  purchase: "采购申请", stock_in: "入库单", stock_out: "出库单", transfer: "调拨单", scrap: "报废单",
  borrow: "借用单", return: "归还单",
  con_purchase: "易耗品采购单", con_inbound: "易耗品入库单", con_issue: "易耗品领用单",
};
const MINE_STATUS_TYPE = { 1: "warning", 2: "success", 3: "danger", 4: "info", 5: "info" };

const loading = ref(false);
const tab = ref("todo");
const todos = ref([]);
const dones = ref([]);
const mine = ref([]);

const filtered = computed(() => (tab.value === "done" ? dones.value : todos.value));

async function load() {
  loading.value = true;
  try {
    const jobs =
      tab.value === "done"
        ? [docApi.dones()]
        : tab.value === "mine"
          ? [docApi.mine({ page: 1, page_size: 100 })]
          : [docApi.todos(), docApi.mine({ page: 1, page_size: 100 })];
    const res = await Promise.all(jobs);
    if (tab.value === "done") dones.value = res[0];
    else if (tab.value === "mine") mine.value = res[0].records || [];
    else {
      todos.value = res[0];
      // 打开页面即统计「我发起的」数量
      mine.value = res[1].records || [];
    }
  } finally {
    loading.value = false;
  }
}

async function withdrawMine(row) {
  try {
    await ElMessageBox.confirm(`撤销后单据作废且不可恢复，确认撤销「${row.biz_no}」？`, "撤销申请", { type: "warning" });
  } catch {
    return;
  }
  await docApi.withdraw(row.id);
  ElMessage.success("已撤销");
  load();
}

// ---- 委托 / 退回 ----
const actionVisible = ref(false);
const actionMode = ref("delegate");
const actionTask = ref(null);
function openAction(row, mode) {
  actionMode.value = mode;
  actionTask.value = { id: row.task.id, instance_id: row.task.instance_id, node_name: row.task.node_name };
  actionVisible.value = true;
}

async function approve(row, action) {
  const verb = action === 1 ? "通过" : "驳回";
  try {
    const { value } = await ElMessageBox.prompt(
      `${BIZ_LABEL[row.biz_type]} ${row.biz_no} · 节点「${row.task.node_name}」`,
      `${verb}审批`,
      {
        confirmButtonText: verb,
        cancelButtonText: "取消",
        inputPlaceholder: "审批意见（可留空）",
        inputType: "textarea",
        type: action === 1 ? "success" : "warning",
      }
    );
    await docApi.approve(row.task.id, { action, comment: value || null });
    ElMessage.success(`已${verb}`);
    load();
  } catch {
    /* 用户取消 */
  }
}

function openBiz(row) {
  pushSafe(router, `/doc/detail/${row.biz_type}/${row.biz_id}`);
}
function openProgress(row) {
  router.push(`/doc/progress/${row.task.instance_id}`);
}

// ---- 加签 ----
const signVisible = ref(false);
const signing = ref(false);
const signRow = ref(null);
const signTo = ref(null);
const signComment = ref("");
const users = ref([]);
async function openSign(row) {
  signRow.value = row;
  signTo.value = null;
  signComment.value = "";
  signVisible.value = true;
  if (!users.value.length) {
    const res = await sysApi.users({ page: 1, page_size: 200, status: 1 });
    users.value = res.records || res || [];
  }
}
async function doSign() {
  if (!signTo.value) return ElMessage.warning("请选择加签审批人");
  signing.value = true;
  try {
    await docApi.approve(signRow.value.task.id, {
      action: 4,
      sign_to: signTo.value,
      comment: signComment.value || null,
    });
    ElMessage.success("已加签");
    signVisible.value = false;
    load();
  } finally {
    signing.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
