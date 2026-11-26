<template>
  <div class="afp">
    <div v-if="!instanceId" class="afp__empty">该单据未走审批流（未提交，或该单据类型已关闭审批流）</div>

    <div v-else-if="loading" class="afp__empty">审批流程加载中…</div>

    <template v-else-if="data">
      <div class="afp__head">
        <el-tag :type="statusType" size="small">{{ data.instance?.status_label || "审批中" }}</el-tag>
        <span v-if="data.instance?.flow_name" class="afp__meta">{{ data.instance.flow_name }}</span>
        <span v-if="data.initiator_name" class="afp__meta text-muted">发起人 {{ data.initiator_name }}</span>
        <span v-if="data.instance?.start_time" class="afp__meta text-muted">
          {{ fmtDateTime(data.instance.start_time) }} 发起
        </span>
        <el-button link type="primary" size="small" class="afp__link" @click="openFull">查看完整审批</el-button>
      </div>

      <div v-if="finishNote" class="afp__finish text-muted">{{ finishNote }}</div>

      <el-timeline class="afp__timeline">
        <el-timeline-item
          v-for="(n, i) in data.nodes"
          :key="n.id || i"
          :type="nodeState(n)"
          :timestamp="`节点 ${i + 1}`"
        >
          <div class="afp__node">
            <div class="afp__node-head">
              <b>{{ n.name }}</b>
              <el-tag size="small" effect="plain">{{ MODE_LABEL[n.mode] || "单签" }}</el-tag>
              <el-tag :type="nodeStatusType(n)" size="small" effect="plain">{{ nodeStatusLabel(n) }}</el-tag>
            </div>
            <div v-for="t in n.tasks" :key="t.id" class="afp__task">
              <span class="afp__who">{{ t.assignee_name }}</span>
              <el-tag v-if="t.action === 1" type="success" size="small">通过</el-tag>
              <el-tag v-else-if="t.action === 2" type="danger" size="small">驳回</el-tag>
              <el-tag v-else-if="t.action === 4" size="small">加签</el-tag>
              <el-tag v-else-if="t.action === 5" type="warning" size="small">退回</el-tag>
              <el-tag v-else type="warning" size="small" effect="plain">待审批</el-tag>
              <span v-if="t.sign_from_user" class="text-muted">（{{ t.sign_from_user }} 加签）</span>
              <span class="text-muted">{{ t.done_time ? fmtDateTime(t.done_time) : `待办 ${fmtDateTime(t.arrive_time)}` }}</span>
              <span v-if="t.comment" class="afp__comment">意见：{{ t.comment }}</span>
            </div>
          </div>
        </el-timeline-item>

        <el-timeline-item v-for="t in data.orphan_tasks" :key="`o${t.id}`" :timestamp="t.node_name || '历史节点'">
          <div class="afp__task">
            <span class="afp__who">{{ t.assignee_name }}</span>
            <el-tag v-if="t.action === 1" type="success" size="small">通过</el-tag>
            <el-tag v-else-if="t.action === 2" type="danger" size="small">驳回</el-tag>
            <el-tag v-else type="warning" size="small" effect="plain">待审批</el-tag>
            <span class="text-muted">{{ t.done_time ? fmtDateTime(t.done_time) : fmtDateTime(t.arrive_time) }}</span>
            <span v-if="t.comment" class="afp__comment">意见：{{ t.comment }}</span>
          </div>
        </el-timeline-item>
      </el-timeline>
    </template>

    <div v-else class="afp__empty">暂无审批流程信息（可能尚未提交审批）</div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { docApi } from "../api";
import { fmtDateTime } from "../utils/constants";

const props = defineProps({
  instanceId: { type: Number, default: null },
});

const router = useRouter();
const loading = ref(false);
const data = ref(null);

const MODE_LABEL = { single: "单签", any: "或签", all: "会签" };

const statusType = computed(() => {
  const s = data.value?.instance?.status;
  return { 1: "warning", 2: "success", 3: "danger", 4: "info", 5: "info" }[s] || "info";
});

const finishNote = computed(() => {
  const inst = data.value?.instance;
  if (!inst) return "";
  const who = inst.finish_by_name || "系统";
  const when = inst.finish_time ? ` · ${fmtDateTime(inst.finish_time)}` : "";
  return `${who} ${when}${inst.finish_note ? ` · ${inst.finish_note}` : ""}`.trim();
});

function nodeState(n) {
  if (n.tasks.some((t) => t.action === 2)) return "danger";
  if (n.tasks.some((t) => t.action === 1)) return "success";
  if (n.tasks.some((t) => !t.action)) return "primary";
  return "info";
}
function nodeStatusLabel(n) {
  if (n.tasks.some((t) => t.action === 2)) return "已驳回";
  if (n.tasks.some((t) => t.action === 1)) return "已通过";
  if (n.tasks.some((t) => !t.action)) return "审批中";
  return "待流转";
}
function nodeStatusType(n) {
  if (n.tasks.some((t) => t.action === 2)) return "danger";
  if (n.tasks.some((t) => t.action === 1)) return "success";
  if (n.tasks.some((t) => !t.action)) return "warning";
  return "info";
}

async function load() {
  data.value = null;
  if (!props.instanceId) return;
  loading.value = true;
  try {
    data.value = await docApi.instance(props.instanceId);
  } catch {
    data.value = null;
  } finally {
    loading.value = false;
  }
}

function openFull() {
  if (props.instanceId) router.push(`/doc/progress/${props.instanceId}`);
}

watch(() => props.instanceId, load, { immediate: true });
</script>

<style scoped>
.afp { line-height: 1.7; font-size: 13px; }
.afp__empty { color: #8a8f98; padding: 6px 0; }
.afp__head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 4px; }
.afp__meta { font-size: 13px; }
.afp__link { margin-left: auto; }
.afp__finish { margin: 2px 0 8px; }
.afp__timeline { padding-top: 4px; }
.afp__node { line-height: 1.7; }
.afp__node-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.afp__task { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 4px 0 4px 14px; }
.afp__who { font-weight: 600; }
.afp__comment { color: var(--ink, #333); }
</style>
