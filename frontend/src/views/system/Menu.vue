<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">菜单管理</h1>
      <div class="flex gap-8">
        <el-button type="primary" :icon="Plus" @click="openCreate(0)">新增目录</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="kw" placeholder="菜单名称" clearable :prefix-icon="Search" style="width: 220px" />
      </div>

      <el-table :data="treeData" v-loading="loading" height="100%" row-key="id" :tree-props="{ children: 'children' }" default-expand-all>
        <el-table-column prop="menu_name" label="菜单名称" min-width="200" />
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.menu_type === 1 ? '' : row.menu_type === 2 ? 'success' : 'info'" size="small">
              {{ MENU_TYPE[row.menu_type] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路由地址" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.path || "-" }}</template>
        </el-table-column>
        <el-table-column prop="perm_code" label="权限标识" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.perm_code || "-" }}</template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="70" align="center" />
        <el-table-column label="可见" width="70" align="center">
          <template #default="{ row }">
            <span :class="row.visible === 1 ? 'text-ok' : 'text-muted'">{{ row.visible === 1 ? "是" : "否" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.menu_type === 1" link type="success" size="small" @click="openCreate(row.id)">加菜单</el-button>
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ flatList.length }} 个菜单节点</span>
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="editing ? '编辑菜单' : '新增菜单'" width="540px" destroy-on-close>
      <el-form :model="form" label-width="86px">
        <el-form-item label="上级菜单">
          <el-input :model-value="parentName" disabled />
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="菜单名称" required>
              <el-input v-model="form.menu_name" maxlength="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="类型" required>
              <el-select v-model="form.menu_type" :disabled="!!editing">
                <el-option v-for="(t, k) in MENU_TYPE" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.menu_type <= 2" :span="12">
            <el-form-item label="路由地址">
              <el-input v-model="form.path" placeholder="如 /asset/list" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.menu_type === 3" :span="12">
            <el-form-item label="权限标识">
              <el-input v-model="form.perm_code" placeholder="如 asset:export" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="可见">
              <el-switch v-model="form.visible" :active-value="1" :inactive-value="0" />
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
import { sysApi } from "../../api";

const MENU_TYPE = { 1: "目录", 2: "菜单", 3: "按钮" };

const loading = ref(false);
const saving = ref(false);
const flatList = ref([]);
const kw = ref("");

const treeData = computed(() => {
  const childrenOf = (pid) => flatList.value.filter((c) => c.parent_id === pid);
  const build = (r) => ({ ...r, children: childrenOf(r.id).map(build) });
  const k = kw.value.trim();
  const roots = flatList.value.filter((c) => !c.parent_id || c.parent_id === 0);
  if (k) {
    const hit = new Set();
    const byId = new Map(flatList.value.map((m) => [m.id, m]));
    flatList.value.forEach((m) => {
      if (m.menu_name?.includes(k)) {
        let cur = m;
        while (cur) {
          hit.add(cur.id);
          cur = byId.get(cur.parent_id);
        }
      }
    });
    return roots.filter((r) => hit.has(r.id)).map((r) => ({
      ...r,
      children: childrenOf(r.id).filter((c) => hit.has(c.id)).map(build),
    }));
  }
  return roots.map(build);
});

const parentName = computed(() => {
  if (!form.parent_id) return "（根目录）";
  return flatList.value.find((m) => m.id === form.parent_id)?.menu_name || form.parent_id;
});

async function load() {
  loading.value = true;
  try {
    flatList.value = await sysApi.menus();
  } finally {
    loading.value = false;
  }
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({ menu_name: "", parent_id: 0, menu_type: 2, perm_code: "", path: "", icon: "", sort: 0, visible: 1, status: 1 });

function openCreate(parentId) {
  editing.value = null;
  Object.assign(form, {
    menu_name: "", parent_id: parentId, menu_type: parentId ? 2 : 1,
    perm_code: "", path: "", icon: "", sort: 0, visible: 1, status: 1,
  });
  formVisible.value = true;
}
function openEdit(row) {
  editing.value = row;
  Object.assign(form, {
    menu_name: row.menu_name, parent_id: row.parent_id || 0, menu_type: row.menu_type,
    perm_code: row.perm_code || "", path: row.path || "", icon: row.icon || "",
    sort: row.sort, visible: row.visible, status: row.status,
  });
  formVisible.value = true;
}
async function save() {
  if (!form.menu_name.trim()) return ElMessage.warning("请填写菜单名称");
  saving.value = true;
  try {
    await sysApi.saveMenu({ ...form, id: editing.value?.id });
    ElMessage.success("已保存");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
async function del(row) {
  try {
    await ElMessageBox.confirm(`确认删除菜单「${row.menu_name}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await sysApi.delMenu(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.text-ok { color: var(--ok); font-size: 12px; }
</style>
