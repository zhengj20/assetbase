<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">字典管理</h1>
      <span class="page__sub">业务枚举统一维护 · 前端下拉全量加载</span>
    </div>

    <div class="dict-layout">
      <!-- 左：字典类型 -->
      <div class="card dict-panel">
        <div class="dict-panel__head">
          <span>字典类型</span>
          <el-button type="primary" size="small" :icon="Plus" @click="openTypeCreate">新增</el-button>
        </div>
        <div class="dict-list" v-loading="typeLoading">
          <div
            v-for="t in dictTypes" :key="t.id"
            class="dict-item" :class="{ 'is-active': curType?.id === t.id }"
            @click="selectType(t)"
          >
            <div class="dict-item__name">{{ t.dict_name }}</div>
            <div class="dict-item__code num">{{ t.dict_code }}</div>
          </div>
          <div v-if="!typeLoading && !dictTypes.length" class="empty-hint">暂无字典类型</div>
        </div>
      </div>

      <!-- 右：字典数据 -->
      <div class="card table-card">
        <div class="filter-bar">
          <span class="sec-title" style="margin: 0">
            {{ curType ? `${curType.dict_name}（${curType.dict_code}）` : "请选择左侧字典类型" }}
          </span>
          <div class="flex gap-8" style="margin-left: auto">
            <el-button type="primary" size="small" :icon="Plus" :disabled="!curType" @click="openDataCreate">新增字典项</el-button>
          </div>
        </div>

        <el-table :data="dataRows" v-loading="dataLoading" height="100%">
          <el-table-column prop="label" label="标签" min-width="140" />
          <el-table-column prop="value" label="键值" width="120" />
          <el-table-column prop="sort" label="排序" width="80" align="center" />
          <el-table-column label="默认" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="warning" size="small" effect="plain">默认</el-tag>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="ext_json" label="扩展JSON" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.ext_json || "-" }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openDataEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="delData(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pager">
          <span class="text-muted">{{ dataRows.length }} 项</span>
        </div>
      </div>
    </div>

    <!-- 字典类型编辑 -->
    <el-dialog v-model="typeVisible" :title="editingType ? '编辑字典类型' : '新增字典类型'" width="440px" destroy-on-close>
      <el-form :model="typeForm" label-width="80px">
        <el-form-item label="字典名称" required>
          <el-input v-model="typeForm.dict_name" maxlength="100" />
        </el-form-item>
        <el-form-item label="字典编码" required>
          <el-input v-model="typeForm.dict_code" maxlength="100" :disabled="!!editingType" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveType">保存</el-button>
      </template>
    </el-dialog>

    <!-- 字典数据编辑 -->
    <el-dialog v-model="dataVisible" :title="editingData ? '编辑字典项' : '新增字典项'" width="440px" destroy-on-close>
      <el-form :model="dataForm" label-width="80px">
        <el-form-item label="标签" required>
          <el-input v-model="dataForm.label" maxlength="100" />
        </el-form-item>
        <el-form-item label="键值" required>
          <el-input v-model="dataForm.value" maxlength="100" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="dataForm.sort" :min="0" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认项">
          <el-switch v-model="dataForm.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dataVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveData">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus } from "@element-plus/icons-vue";
import { sysApi } from "../../api";

const typeLoading = ref(false);
const dataLoading = ref(false);
const saving = ref(false);

const dictTypes = ref([]);
const curType = ref(null);
const dataRows = ref([]);

async function loadTypes() {
  typeLoading.value = true;
  try {
    dictTypes.value = await sysApi.dictTypes();
    if (!curType.value && dictTypes.value.length) selectType(dictTypes.value[0]);
  } finally {
    typeLoading.value = false;
  }
}

async function selectType(t) {
  curType.value = t;
  dataLoading.value = true;
  try {
    dataRows.value = await sysApi.dictDatas(t.id);
  } finally {
    dataLoading.value = false;
  }
}

// ---- 字典类型 ----
const typeVisible = ref(false);
const editingType = ref(null);
const typeForm = reactive({ dict_name: "", dict_code: "" });

function openTypeCreate() {
  editingType.value = null;
  Object.assign(typeForm, { dict_name: "", dict_code: "" });
  typeVisible.value = true;
}
async function saveType() {
  if (!typeForm.dict_name.trim() || !typeForm.dict_code.trim()) return ElMessage.warning("请填写名称与编码");
  saving.value = true;
  try {
    await sysApi.saveDictType({ ...typeForm, id: editingType.value?.id });
    ElMessage.success("已保存");
    typeVisible.value = false;
    loadTypes();
  } finally {
    saving.value = false;
  }
}

// ---- 字典数据 ----
const dataVisible = ref(false);
const editingData = ref(null);
const dataForm = reactive({ label: "", value: "", sort: 0, is_default: false });

function openDataCreate() {
  editingData.value = null;
  Object.assign(dataForm, { label: "", value: "", sort: dataRows.value.length + 1, is_default: false });
  dataVisible.value = true;
}
function openDataEdit(row) {
  editingData.value = row;
  Object.assign(dataForm, { label: row.label, value: row.value, sort: row.sort, is_default: !!row.is_default });
  dataVisible.value = true;
}
async function saveData() {
  if (!dataForm.label.trim() || !dataForm.value.trim()) return ElMessage.warning("请填写标签与键值");
  saving.value = true;
  try {
    await sysApi.saveDictData({ ...dataForm, dict_id: curType.value.id, id: editingData.value?.id });
    ElMessage.success("已保存");
    dataVisible.value = false;
    selectType(curType.value);
  } finally {
    saving.value = false;
  }
}
async function delData(row) {
  try {
    await ElMessageBox.confirm(`确认删除字典项「${row.label}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await sysApi.delDictData(row.id);
  ElMessage.success("已删除");
  selectType(curType.value);
}

onMounted(loadTypes);
</script>

<style scoped>
.dict-layout {
  flex: 1;
  display: flex;
  gap: 14px;
  min-height: 0;
}
.dict-panel {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dict-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  font-family: var(--serif);
  font-weight: 700;
  color: var(--navy);
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}
.dict-list { flex: 1; overflow-y: auto; padding: 6px; }
.dict-item {
  padding: 10px 12px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid transparent;
}
.dict-item:hover { background: #faf6ec; }
.dict-item.is-active {
  background: linear-gradient(90deg, rgba(176, 122, 46, 0.1), transparent);
  border-color: var(--gold-line);
}
.dict-item__name { color: var(--ink); font-size: 13px; }
.dict-item__code { color: var(--ink-3); font-size: 11px; margin-top: 2px; }
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
