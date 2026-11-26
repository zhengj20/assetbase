<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">项目空间</h1>
      <span class="page__sub">楼盘/楼栋/房间三级结构 · 清盘前资产清空校验</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-select v-model="projectId" placeholder="按项目筛选" clearable filterable style="width: 200px" @change="load">
          <el-option v-for="p in projects" :key="p.id" :label="p.org_name" :value="p.id" />
        </el-select>
        <el-button v-perm="'space:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate()">新增空间</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%" row-key="id" :tree-props="{ children: 'children' }" default-expand-all>
        <el-table-column prop="space_name" label="空间名称" min-width="220" />
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">{{ SPACE_TYPE[row.space_type] || "-" }}</template>
        </el-table-column>
        <el-table-column label="所属项目" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ orgName(row.project_id) }}</template>
        </el-table-column>
        <el-table-column prop="floor" label="楼层" width="80" />
        <el-table-column prop="room_type" label="户型" width="100" />
        <el-table-column label="面积(㎡)" width="90" align="right">
          <template #default="{ row }">{{ row.area != null ? Number(row.area) : "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.space_status === 1 ? 'success' : 'info'" size="small">
              {{ row.space_status === 1 ? "在用" : "关闭" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-perm="'space:edit'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-perm="'space:delete'" link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">项目空间树（{{ rowCount }} 个节点）</span>
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="editing ? '编辑空间' : '新增空间'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="86px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="所属项目" required>
              <el-select v-model="form.project_id" filterable>
                <el-option v-for="p in projects" :key="p.id" :label="p.org_name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="空间类型" required>
              <el-select v-model="form.space_type">
                <el-option v-for="(t, k) in SPACE_TYPE" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="空间名称" required>
              <el-input v-model="form.space_name" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="上级空间">
              <el-tree-select
                v-model="form.parent_id" :data="spaceTreeOptions" node-key="id"
                :props="{ label: 'space_name', children: 'children' }" check-strictly
                placeholder="（项目根节点）" style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="楼层">
              <el-input v-model="form.floor" placeholder="如 2F" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="户型">
              <el-input v-model="form.room_type" placeholder="如 三室两厅" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="面积(㎡)">
              <el-input-number v-model="form.area" :min="0" :precision="2" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.space_status" :active-value="1" :inactive-value="2" active-text="在用" inactive-text="关闭" />
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
import { Plus } from "@element-plus/icons-vue";
import { archiveApi, sysApi } from "../../api";

const SPACE_TYPE = { 1: "售楼处", 2: "样板间", 3: "办公室", 4: "仓库" };

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const projectId = ref(null);
const orgs = ref([]);

const projects = computed(() => orgs.value.filter((o) => o.org_type === 3));
const orgName = (id) => orgs.value.find((o) => o.id === id)?.org_name || id;

// 上级空间选项：当前项目的空间树（排除自身）
const spaceTreeOptions = computed(() => {
  const list = rows.value.filter((s) => !projectId.value || s.project_id === projectId.value);
  const byParent = {};
  list.forEach((s) => {
    const pid = s.parent_id || 0;
    if (!byParent[pid]) byParent[pid] = [];
    byParent[pid].push(s);
  });
  const build = (pid) => (byParent[pid] || [])
    .filter((s) => s.id !== editing.value?.id)
    .map((s) => ({ ...s, children: build(s.id) }));
  return build(0);
});

const rowCount = computed(() => {
  let n = 0;
  const walk = (list) => list.forEach((s) => { n++; walk(s.children || []); });
  walk(rows.value);
  return n;
});

async function load() {
  loading.value = true;
  try {
    rows.value = await archiveApi.spaces(projectId.value ? { project_id: projectId.value } : {});
  } finally {
    loading.value = false;
  }
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({
  space_name: "", space_type: 4, parent_id: 0, project_id: null,
  floor: "", room_type: "", area: null, space_status: 1, remark: "",
});

function openCreate() {
  editing.value = null;
  Object.assign(form, {
    space_name: "", space_type: 4, parent_id: 0,
    project_id: projectId.value || projects.value[0]?.id || null,
    floor: "", room_type: "", area: null, space_status: 1, remark: "",
  });
  formVisible.value = true;
}
function openEdit(row) {
  editing.value = row;
  Object.assign(form, {
    space_name: row.space_name, space_type: row.space_type, parent_id: row.parent_id || 0,
    project_id: row.project_id, floor: row.floor || "", room_type: row.room_type || "",
    area: row.area != null ? Number(row.area) : null, space_status: row.space_status, remark: "",
  });
  formVisible.value = true;
}
function countDescendants(id) {
  const flat = [];
  const walk = (list) => list.forEach((s) => { flat.push(s); walk(s.children || []); });
  walk(rows.value);
  const byParent = {};
  flat.forEach((s) => { (byParent[s.parent_id] = byParent[s.parent_id] || []).push(s.id); });
  let n = 0;
  let frontier = [id];
  while (frontier.length) {
    const next = [];
    frontier.forEach((pid) => (byParent[pid] || []).forEach((cid) => { n++; next.push(cid); }));
    frontier = next;
  }
  return n;
}

async function save() {
  if (!form.space_name.trim()) return ElMessage.warning("请填写空间名称");
  if (!form.project_id) return ElMessage.warning("请选择所属项目");
  if (editing.value && form.space_status !== editing.value.space_status) {
    const n = countDescendants(editing.value.id);
    if (n) {
      try {
        await ElMessageBox.confirm(
          `状态变更后，其下 ${n} 个下级空间将同步为「${form.space_status === 1 ? "在用" : "关闭"}」（下级之后仍可单独调整）。`,
          "状态同步确认",
          { type: "warning", confirmButtonText: "确认同步" }
        );
      } catch {
        return;
      }
    }
  }
  saving.value = true;
  try {
    await archiveApi.saveSpace({ ...form, id: editing.value?.id });
    ElMessage.success("已保存");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
async function del(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除空间「${row.space_name}」？空间内存在资产时将无法删除。`,
      "删除", { type: "warning" }
    );
  } catch {
    return;
  }
  await archiveApi.delSpace(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(async () => {
  orgs.value = await sysApi.orgs();
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
