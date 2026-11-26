<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">组织架构</h1>
      <span class="page__sub">集团 / 区域 / 项目 / 部门四级树 · 数据权限基线</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="kw" placeholder="组织名称/编码" clearable :prefix-icon="Search" style="width: 220px" />
        <el-button type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate(0)">新增根组织</el-button>
      </div>

      <el-table :data="treeData" v-loading="loading" height="100%" row-key="id" :tree-props="{ children: 'children' }" default-expand-all>
        <el-table-column prop="org_name" label="组织名称" min-width="220" />
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">{{ ORG_TYPE[row.org_type] || "-" }}</template>
        </el-table-column>
        <el-table-column prop="org_code" label="编码" width="90" />
        <el-table-column label="核算主体" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_accounting" type="warning" size="small" effect="plain">核算</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
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
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="success" size="small" @click="openCreate(row.id)">加下级</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ flatList.length }} 个组织节点</span>
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="editing ? '编辑组织' : '新增组织'" width="520px" destroy-on-close>
      <el-form :model="form" label-width="86px">
        <el-form-item label="上级组织">
          <el-input :model-value="parentName" disabled />
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="组织名称" required>
              <el-input v-model="form.org_name" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="编码" required>
              <el-input v-model="form.org_code" maxlength="10" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="组织类型" required>
              <el-select v-model="form.org_type">
                <el-option v-for="(t, k) in ORG_TYPE" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="核算主体">
              <el-switch v-model="form.is_accounting" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
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
import { sysApi } from "../../api";

const ORG_TYPE = { 1: "集团", 2: "区域公司", 3: "项目部", 4: "部门", 5: "其他" };

const loading = ref(false);
const saving = ref(false);
const flatList = ref([]);
const kw = ref("");

const treeData = computed(() => {
  const childrenOf = (pid) => flatList.value.filter((c) => c.parent_id === pid);
  const build = (r) => ({ ...r, children: childrenOf(r.id).map(build) });
  const k = kw.value.trim();
  if (k) {
    // 命中节点及其祖先链都保留
    const hit = new Set();
    const byId = new Map(flatList.value.map((o) => [o.id, o]));
    flatList.value.forEach((o) => {
      if (o.org_name?.includes(k) || o.org_code?.includes(k)) {
        let cur = o;
        while (cur) {
          hit.add(cur.id);
          cur = byId.get(cur.parent_id);
        }
      }
    });
    const filterBuild = (r) => ({ ...r, children: childrenOf(r.id).filter((c) => hit.has(c.id)).map(filterBuild) });
    return flatList.value
      .filter((c) => (!c.parent_id || c.parent_id === 0) && hit.has(c.id))
      .map(filterBuild);
  }
  return flatList.value
    .filter((c) => !c.parent_id || c.parent_id === 0)
    .map(build);
});

const parentName = computed(() => {
  if (!form.parent_id) return "（根组织）";
  return flatList.value.find((o) => o.id === form.parent_id)?.org_name || form.parent_id;
});

async function load() {
  loading.value = true;
  try {
    flatList.value = await sysApi.orgs();
  } finally {
    loading.value = false;
  }
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({ org_name: "", org_type: 2, parent_id: 0, org_code: "", sort: 0, is_accounting: false, status: 1, remark: "" });

function openCreate(parentId) {
  editing.value = null;
  Object.assign(form, { org_name: "", org_type: parentId ? 4 : 1, parent_id: parentId, org_code: "", sort: 0, is_accounting: false, status: 1, remark: "" });
  formVisible.value = true;
}
function openEdit(row) {
  editing.value = row;
  Object.assign(form, {
    org_name: row.org_name, org_type: row.org_type, parent_id: row.parent_id || 0,
    org_code: row.org_code, sort: row.sort, is_accounting: !!row.is_accounting, status: row.status, remark: row.remark || "",
  });
  formVisible.value = true;
}
async function save() {
  if (!form.org_name.trim() || !form.org_code.trim()) return ElMessage.warning("请填写组织名称与编码");
  saving.value = true;
  try {
    await sysApi.saveOrg({ ...form, id: editing.value?.id });
    ElMessage.success("已保存");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
async function del(row) {
  try {
    await ElMessageBox.confirm(`确认删除组织「${row.org_name}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await sysApi.delOrg(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
