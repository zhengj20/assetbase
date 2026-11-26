<template>
  <div class="page" v-loading="loading">
    <div class="page__head">
      <div>
        <h1 class="page__title">
          审批进度
          <el-tag :type="statusType" style="margin-left: 8px">{{ data.instance?.status_label }}</el-tag>
        </h1>
        <span class="page__sub">
          {{ data.biz?.label }} {{ data.biz?.no }} · {{ data.instance?.flow_name }} ·
          发起人 {{ data.initiator_name || data.biz?.apply_user_name || "-" }}
          <template v-if="data.instance?.start_time"> · {{ fmtDateTime(data.instance.start_time) }} 发起</template>
        </span>
      </div>
      <div class="flex gap-8">
        <el-button @click="goBack">返回</el-button>
        <el-button type="primary" @click="openBiz">查看单据</el-button>
      </div>
    </div>

    <!-- 操作区 -->
    <div v-if="data.instance?.status === 1" class="card action-bar">
      <template v-if="data.my_task_id">
        <el-button type="success" @click="approve(1)">通过</el-button>
        <el-button type="danger" @click="approve(2)">驳回</el-button>
        <el-button @click="signDialog = true">加签</el-button>
      </template>
      <template v-else>
        <span class="text-muted">当前节点等待其他审批人处理</span>
      </template>
      <div style="margin-left: auto" class="flex gap-8">
        <el-button v-if="data.can_withdraw" type="warning" plain @click="withdraw">撤销申请</el-button>
        <el-button v-if="data.can_terminate" type="danger" plain @click="terminate">终止流程</el-button>
      </div>
    </div>
    <div v-else-if="data.instance" class="card finish-bar">
      <span class="text-muted">
        {{ data.instance.finish_by_name || "系统" }}
        {{ data.instance.finish_time ? ` · ${fmtDateTime(data.instance.finish_time)}` : "" }}
        <template v-if="data.instance.finish_note"> · {{ data.instance.finish_note }}</template>
      </span>
    </div>

    <!-- 节点时间线 -->
    <el-timeline class="card timeline">
      <el-timeline-item
        v-for="(n, i) in data.nodes"
        :key="n.id || i"
        :type="nodeState(n)"
        :timestamp="`节点 ${i + 1}`"
      >
        <div class="node">
          <div class="node__head">
            <b>{{ n.name }}</b>
            <el-tag size="small" effect="plain">{{ MODE_LABEL[n.mode] || "单签" }}</el-tag>
            <el-tag v-if="n.tasks.some((t) => !t.action)" type="warning" size="small" effect="plain">审批中</el-tag>
            <el-tag v-else-if="n.tasks.some((t) => t.action === 1)" type="success" size="small" effect="plain">已通过</el-tag>
            <el-tag v-else-if="n.tasks.some((t) => t.action === 2)" type="danger" size="small" effect="plain">已驳回</el-tag>
            <span v-else class="text-muted">待流转</span>
          </div>
          <div v-for="t in n.tasks" :key="t.id" class="task">
            <span class="task__who">{{ t.assignee_name }}</span>
            <el-tag v-if="t.action === 1" type="success" size="small">通过</el-tag>
            <el-tag v-else-if="t.action === 2" type="danger" size="small">驳回</el-tag>
            <el-tag v-else-if="t.action === 4" size="small">加签</el-tag>
            <el-tag v-else-if="t.action === 5" type="warning" size="small">退回</el-tag>
            <el-tag v-else type="warning" size="small" effect="plain">待审批</el-tag>
            <span v-if="t.sign_from_user" class="text-muted">（{{ t.sign_from_user }} 加签）</span>
            <span class="text-muted">{{ t.done_time ? fmtDateTime(t.done_time) : `待办 ${fmtDateTime(t.arrive_time)}` }}</span>
            <span v-if="t.comment" class="task__comment">意见：{{ t.comment }}</span>
          </div>
        </div>
      </el-timeline-item>
      <el-timeline-item v-for="t in data.orphan_tasks" :key="`o${t.id}`" :timestamp="t.node_name">
        <div class="task">
          <span class="task__who">{{ t.assignee_name }}</span>
          <el-tag v-if="t.action === 1" type="success" size="small">通过</el-tag>
          <el-tag v-else-if="t.action === 2" type="danger" size="small">驳回</el-tag>
          <el-tag v-else-if="t.action === 4" size="small">加签</el-tag>
          <el-tag v-else type="warning" size="small" effect="plain">待审批</el-tag>
          <span class="text-muted">{{ t.done_time ? fmtDateTime(t.done_time) : fmtDateTime(t.arrive_time) }}</span>
          <span v-if="t.comment" class="task__comment">意见：{{ t.comment }}</span>
        </div>
      </el-timeline-item>
    </el-timeline>

    <!-- 加签弹窗 -->
    <el-dialog v-model="signDialog" title="加签（追加必审人）" width="420px">
      <el-form label-width="70px">
        <el-form-item label="加签给">
          <el-select v-model="signTo" filterable placeholder="选择审批人" style="width: 100%">
            <el-option v-for="u in data.users || []" :key="u.id" :label="u.real_name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="signComment" type="textarea" :rows="2" placeholder="加签说明（可留空）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signDialog = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="doSign">确认加签</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { docApi } from "../../api";
import { fmtDateTime } from "../../utils/constants";
import { pushSafe } from "../../utils/nav";
import ApprovalActionDialog from "../../components/ApprovalActionDialog.vue";

const route = useRoute();
const router = useRouter();
const instanceId = Number(route.params.instanceId);

const loading = ref(false);
const acting = ref(false);
const data = ref({ nodes: [], orphan_tasks: [], users: [] });
const signDialog = ref(false);
const signTo = ref(null);
const signComment = ref("");
const actionVisible = ref(false);
const actionMode = ref("delegate");
function openAction(mode) {
  actionMode.value = mode;
  actionVisible.value = true;
}

const MODE_LABEL = { single: "单签", any: "或签", all: "会签" };
const statusType = computed(() => {
  const s = data.value.instance?.status;
  return { 1: "warning", 2: "success", 3: "danger", 4: "info", 5: "info" }[s] || "info";
});

const BIZ_PATH = {
  purchase: "/doc/purchase", stock_in: "/doc/stock-in", stock_out: "/doc/stock-out",
  transfer: "/doc/transfer", scrap: "/doc/scrap",
};

function nodeState(n) {
  if (n.tasks.some((t) => t.action === 2)) return "danger";
  if (n.tasks.some((t) => t.action === 1)) return "success";
  if (n.tasks.some((t) => !t.action)) return "primary";
  return "info";
}

async function load() {
  loading.value = true;
  try {
    data.value = await docApi.instance(instanceId);
  } finally {
    loading.value = false;
  }
}

async function approve(action) {
  const verb = action === 1 ? "通过" : "驳回";
  try {
    const { value } = await ElMessageBox.prompt("审批意见（可留空）", `${verb}审批`, {
      confirmButtonText: verb,
      cancelButtonText: "取消",
      inputType: "textarea",
      type: action === 1 ? "success" : "warning",
    });
    await docApi.approve(data.value.my_task_id, { action, comment: value || null });
    ElMessage.success(`已${verb}`);
    load();
  } catch {
    /* 用户取消 */
  }
}

async function doSign() {
  if (!signTo.value) return ElMessage.warning("请选择加签审批人");
  acting.value = true;
  try {
    await docApi.approve(data.value.my_task_id, {
      action: 4,
      sign_to: signTo.value,
      comment: signComment.value || null,
    });
    ElMessage.success("已加签");
    signDialog.value = false;
    signComment.value = "";
    load();
  } finally {
    acting.value = false;
  }
}

async function withdraw() {
  try {
    await ElMessageBox.confirm("撤销后单据作废且不可恢复，确认撤销？", "撤销申请", { type: "warning" });
  } catch {
    return;
  }
  await docApi.withdraw(instanceId);
  ElMessage.success("已撤销");
  load();
}

async function terminate() {
  try {
    const { value } = await ElMessageBox.prompt("终止原因（可留空）", "终止流程", {
      confirmButtonText: "终止",
      cancelButtonText: "取消",
      inputType: "textarea",
      type: "warning",
    });
    await docApi.terminate(instanceId, value || null);
    ElMessage.success("已终止");
    load();
  } catch {
    /* 用户取消 */
  }
}

function openBiz() {
  const b = data.value.biz;
  if (b?.type && b?.id) pushSafe(router, `/doc/detail/${b.type}/${b.id}`);
}
function goBack() {
  if (window.history.length > 1) router.back();
  else router.push("/doc/approval");
}

onMounted(load);
</script>

<style scoped>
.action-bar, .finish-bar { display: flex; align-items: center; gap: 8px; padding: 12px 16px; }
.timeline { padding: 18px 24px; overflow-y: auto; }
.node { line-height: 1.7; }
.node__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.task { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 6px 0 6px 16px; font-size: 13px; }
.task__who { font-weight: 600; }
.task__comment { color: var(--ink, #333); }
</style>
