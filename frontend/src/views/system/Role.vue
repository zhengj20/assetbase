<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">角色管理</h1>
      <div class="flex gap-8">
        <el-button v-perm="'sys:role'" type="primary" :icon="Plus" @click="openCreate">新增角色</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="kw" placeholder="角色名称/编码" clearable :prefix-icon="Search" style="width: 220px" />
      </div>

      <el-table :data="filtered" v-loading="loading" height="100%">
        <el-table-column prop="role_name" label="角色名称" width="160" />
        <el-table-column prop="role_code" label="角色编码" width="140" />
        <el-table-column label="数据权限" width="150" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ DATA_SCOPE[row.data_scope] || row.data_scope }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="说明" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? "启用" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-perm="'sys:role'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-perm="'sys:role'" link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ filtered.length }} 个角色</span>
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="editing ? '编辑角色' : '新增角色'" width="640px" destroy-on-close top="6vh">
      <el-form :model="form" label-width="86px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="角色名称" required>
              <el-input v-model="form.role_name" maxlength="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色编码" required>
              <el-input v-model="form.role_code" maxlength="50" :disabled="!!editing" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据权限" required>
              <el-select v-model="form.data_scope">
                <el-option v-for="(t, k) in DATA_SCOPE" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="说明">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="功能菜单">
          <div class="menu-tree card-plain">
            <el-tree
              ref="menuTreeRef"
              :data="menuTreeData" node-key="id" show-checkbox
              :props="{ label: 'menu_name', children: 'children' }"
              default-expand-all
              :check-strictly="false"
            />
          </div>
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

const DATA_SCOPE = { 1: "全部数据", 2: "本公司及下级", 3: "本公司", 4: "本部门及下级", 5: "仅本人" };

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const kw = ref("");
const menus = ref([]);
const menuTreeRef = ref();

const filtered = computed(() => {
  const k = kw.value.trim();
  if (!k) return rows.value;
  return rows.value.filter((r) => r.role_name?.includes(k) || r.role_code?.includes(k));
});

// /menus 返回树；展平为扁平列表，供「按 parent_id 递归建树」与「按 id 回填」共用
function flattenMenus(tree, acc = []) {
  for (const m of tree || []) {
    acc.push(m);
    if (m.children?.length) flattenMenus(m.children, acc);
  }
  return acc;
}

const menuTreeData = computed(() => {
  const byParent = {};
  menus.value.forEach((m) => {
    const pid = m.parent_id || 0;
    if (!byParent[pid]) byParent[pid] = [];
    byParent[pid].push(m);
  });
  const build = (pid) => (byParent[pid] || []).map((m) => ({ ...m, children: build(m.id) }));
  return build(0);
});

async function load() {
  loading.value = true;
  try {
    const [roleRows, menuTree] = await Promise.all([sysApi.roles(), sysApi.menus()]);
    rows.value = roleRows;
    menus.value = flattenMenus(menuTree);
  } finally {
    loading.value = false;
  }
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({ role_name: "", role_code: "", data_scope: 5, status: 1, remark: "" });

async function openCreate() {
  editing.value = null;
  Object.assign(form, { role_name: "", role_code: "", data_scope: 5, status: 1, remark: "" });
  formVisible.value = true;
  setTimeout(() => menuTreeRef.value?.setCheckedKeys([]));
}
async function openEdit(row) {
  editing.value = row;
  Object.assign(form, {
    role_name: row.role_name, role_code: row.role_code,
    data_scope: row.data_scope, status: row.status, remark: row.remark || "",
  });
  formVisible.value = true;
  // 回填已分配菜单（仅勾选「父级不在已分配集合中」的最深节点，父级由级联带出）
  const ids = await sysApi.roleMenuIds(row.id);
  const idSet = new Set(ids || []);
  setTimeout(() => {
    const leafIds = (ids || []).filter((id) => {
      const m = menus.value.find((x) => x.id === id);
      return m && !(m.parent_id && idSet.has(m.parent_id));
    });
    menuTreeRef.value?.setCheckedKeys(leafIds);
  });
}

async function save() {
  if (!form.role_name.trim() || !form.role_code.trim()) return ElMessage.warning("请填写角色名称与编码");
  const menuIds = [
    ...menuTreeRef.value.getCheckedKeys(),
    ...menuTreeRef.value.getHalfCheckedKeys(),
  ];
  saving.value = true;
  try {
    await sysApi.saveRole({ ...form, menu_ids: menuIds, id: editing.value?.id });
    ElMessage.success("已保存");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
async function del(row) {
  try {
    await ElMessageBox.confirm(`确认删除角色「${row.role_name}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await sysApi.delRole(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.menu-tree {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 8px;
  max-height: 320px;
  overflow-y: auto;
  width: 100%;
}
</style>
