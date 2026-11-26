<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">资产分类</h1>
      <span class="page__sub">折旧年限与残值率的全局基线 · 子类未填时继承父类</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="kw" placeholder="分类名称/编码" clearable :prefix-icon="Search" style="width: 220px" />
        <el-button v-perm="'category:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate(0)">新增根分类</el-button>
      </div>

      <el-table
        :data="treeData" v-loading="loading" height="100%" row-key="id"
        :tree-props="{ children: 'children' }" default-expand-all
      >
        <el-table-column prop="category_name" label="分类名称" min-width="220" />
        <el-table-column prop="code" label="编码" width="110" />
        <el-table-column label="折旧年限(月)" width="110" align="right">
          <template #default="{ row }">{{ row.depreciate_month ?? "-" }}</template>
        </el-table-column>
        <el-table-column label="残值率" width="90" align="right">
          <template #default="{ row }">{{ row.residual_rate != null ? `${Number(row.residual_rate) * 100}%` : "-" }}</template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="70" align="center" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? "启用" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-perm="'category:edit'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-perm="'category:create'" link type="success" size="small" @click="openCreate(row.id)">加子类</el-button>
            <el-button v-perm="'category:delete'" link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ flatList.length }} 个分类（两级结构）</span>
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="editing ? '编辑分类' : '新增分类'" width="520px" destroy-on-close>
      <el-form :model="form" label-width="92px">
        <el-form-item label="上级分类">
          <el-input :model-value="parentName" disabled />
        </el-form-item>
        <el-form-item label="分类名称" required>
          <el-input v-model="form.category_name" maxlength="100" />
        </el-form-item>
        <el-form-item label="编码" required>
          <el-input v-model="form.code" maxlength="10" placeholder="如 F0101" />
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="折旧年限">
              <el-input-number v-model="form.depreciate_month" :min="0" :controls="false" style="width: 100%" placeholder="月" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="残值率">
              <el-input-number v-model="form.residual_rate" :min="0" :max="1" :step="0.01" :precision="4" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { archiveApi } from "../../api";

const loading = ref(false);
const saving = ref(false);
const flatList = ref([]);
const kw = ref("");

const treeData = computed(() => {
  const keyword = kw.value.trim();
  let roots = flatList.value.filter((c) => !c.parent_id || c.parent_id === 0);
  let childrenOf = (pid) => flatList.value.filter((c) => c.parent_id === pid);
  if (keyword) {
    const match = (c) => c.category_name.includes(keyword) || c.code?.includes(keyword);
    return roots
      .map((r) => ({
        ...r,
        children: childrenOf(r.id).filter((c) => match(c) || match(r)),
      }))
      .filter((r) => match(r) || r.children.length);
  }
  return roots.map((r) => ({ ...r, children: childrenOf(r.id) }));
});

const parentName = computed(() => {
  if (!form.parent_id) return "（根分类）";
  return flatList.value.find((c) => c.id === form.parent_id)?.category_name || form.parent_id;
});

async function load() {
  loading.value = true;
  try {
    flatList.value = await archiveApi.categories();
  } finally {
    loading.value = false;
  }
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({ category_name: "", code: "", parent_id: 0, depreciate_month: null, residual_rate: null, sort: 0, status: 1 });

function openCreate(parentId) {
  editing.value = null;
  Object.assign(form, { category_name: "", code: "", parent_id: parentId, depreciate_month: null, residual_rate: null, sort: 0, status: 1 });
  formVisible.value = true;
}
function openEdit(row) {
  editing.value = row;
  Object.assign(form, {
    category_name: row.category_name, code: row.code, parent_id: row.parent_id || 0,
    depreciate_month: row.depreciate_month, residual_rate: row.residual_rate != null ? Number(row.residual_rate) : null,
    sort: row.sort, status: row.status,
  });
  formVisible.value = true;
}
async function save() {
  if (!form.category_name.trim() || !form.code.trim()) return ElMessage.warning("请填写分类名称与编码");
  saving.value = true;
  try {
    await archiveApi.saveCategory({ ...form, id: editing.value?.id });
    ElMessage.success("已保存");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
async function del(row) {
  try {
    await ElMessageBox.confirm(`确认删除分类「${row.category_name}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await archiveApi.delCategory(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
