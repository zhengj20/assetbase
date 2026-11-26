<template>
  <el-dialog
    :model-value="modelValue"
    :title="mode === 'delegate' ? '委托转办（改派给其他审批人）' : '退回（回到前置节点重新审批）'"
    width="440px"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-form v-if="mode === 'delegate'" label-width="70px">
      <el-form-item label="委托给">
        <el-select v-model="toUser" filterable placeholder="选择审批人" style="width: 100%">
          <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="comment" type="textarea" :rows="2" placeholder="备注（可留空）" />
      </el-form-item>
    </el-form>

    <el-form v-else label-width="70px">
      <el-form-item label="退回到">
        <el-select v-model="targetIdx" placeholder="选择退回目标节点" style="width: 100%" v-loading="loadingNodes">
          <el-option v-for="(n, i) in backTargets" :key="i" :label="`节点 ${i + 1}：${n.name}`" :value="i" />
        </el-select>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="comment" type="textarea" :rows="2" placeholder="退回原因（可留空）" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="acting" @click="confirm">
        {{ mode === "delegate" ? "确认委托" : "确认退回" }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { docApi, sysApi } from "../api";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: "delegate" }, // delegate | back
  task: { type: Object, default: null }, // {id, instance_id, node_name}
});
const emit = defineEmits(["update:modelValue", "done"]);

const toUser = ref(null);
const comment = ref("");
const users = ref([]);
const acting = ref(false);
const loadingNodes = ref(false);
const nodes = ref([]);
const curIdx = ref(0);
const targetIdx = ref(null);
const backTargets = computed(() => nodes.value.slice(0, Math.max(curIdx.value, 0)));

watch(
  () => props.modelValue,
  async (open) => {
    if (!open || !props.task) return;
    toUser.value = null;
    comment.value = "";
    targetIdx.value = null;
    if (props.mode === "delegate") {
      if (!users.value.length) {
        const res = await sysApi.users({ page: 1, page_size: 200, status: 1 });
        users.value = res.records || res || [];
      }
    } else {
      loadingNodes.value = true;
      try {
        const d = await docApi.instance(props.task.instance_id);
        nodes.value = d.nodes || [];
        const idx = nodes.value.findIndex((n) => n.name === props.task.node_name);
        curIdx.value = idx < 0 ? 0 : idx;
      } finally {
        loadingNodes.value = false;
      }
    }
  }
);

async function confirm() {
  if (props.mode === "delegate") {
    if (!toUser.value) return ElMessage.warning("请选择委托对象");
    acting.value = true;
    try {
      await docApi.delegate(props.task.id, { to_user: toUser.value, comment: comment.value || null });
      ElMessage.success("已委托");
      emit("update:modelValue", false);
      emit("done");
    } finally {
      acting.value = false;
    }
  } else {
    if (targetIdx.value === null || targetIdx.value === undefined) return ElMessage.warning("请选择退回目标节点");
    acting.value = true;
    try {
      await docApi.approve(props.task.id, {
        action: 5,
        target_node: targetIdx.value,
        comment: comment.value || null,
      });
      ElMessage.success("已退回");
      emit("update:modelValue", false);
      emit("done");
    } finally {
      acting.value = false;
    }
  }
}
</script>
