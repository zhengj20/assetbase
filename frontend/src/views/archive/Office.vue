<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">办公地点</h1>
      <span class="page__sub">公司/园区/楼栋楼层级办公位置 · 供资产挂靠与部门归属</span>
      <div class="flex gap-8" style="margin-left: auto">
        <el-button v-perm="'office:create'" type="primary" :icon="Plus" @click="openCreate()">新增办公地点</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="keyword" placeholder="地点名称" clearable style="width: 220px" @keyup.enter="load" />
        <el-select v-model="orgFilter" placeholder="所属公司" clearable filterable style="width: 200px" @change="load">
          <el-option v-for="o in orgOptions" :key="o.id" :label="o.org_name" :value="o.id" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="office_name" label="办公地点" min-width="180" show-overflow-tooltip />
        <el-table-column label="所属公司" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ orgName(row.org_id) }}</template>
        </el-table-column>
        <el-table-column label="关联项目" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.project_id ? orgName(row.project_id) : "-" }}</template>
        </el-table-column>
        <el-table-column prop="building" label="楼栋" width="90" />
        <el-table-column prop="floor" label="楼层" width="80" />
        <el-table-column prop="address" label="详细地址" min-width="200" show-overflow-tooltip />
        <el-table-column prop="sort" label="排序" width="70" align="center" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? "启用" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-perm="'office:edit'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-perm="'office:delete'" link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ rows.length }} 个办公地点</span>
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="editing ? '编辑办公地点' : '新增办公地点'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="86px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="地点名称" required>
              <el-input v-model="form.office_name" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属公司" required>
              <el-select v-model="form.org_id" filterable>
                <el-option v-for="o in orgOptions" :key="o.id" :label="o.org_name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联项目">
              <el-select v-model="form.project_id" clearable filterable placeholder="（可选）">
                <el-option v-for="p in projects" :key="p.id" :label="p.org_name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="楼栋">
              <el-input v-model="form.building" placeholder="如 A座" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="楼层">
              <el-input v-model="form.floor" placeholder="如 15F" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="详细地址">
              <el-input v-model="form.address" maxlength="200" />
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
import { Plus } from "@element-plus/icons-vue";
import { archiveApi, sysApi } from "../../api";

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const keyword = ref("");
const orgFilter = ref(null);
const orgs = ref([]);

const orgOptions = computed(() => orgs.value.filter((o) => o.org_type <= 3 || o.is_accounting));
const projects = computed(() => orgs.value.filter((o) => o.org_type === 3));
const orgName = (id) => orgs.value.find((o) => o.id === id)?.org_name || id;

async function load() {
  loading.value = true;
  try {
    const params = {};
    if (keyword.value) params.keyword = keyword.value;
    if (orgFilter.value) params.org_id = orgFilter.value;
    rows.value = await archiveApi.offices(params);
  } finally {
    loading.value = false;
  }
}

function reset() {
  keyword.value = "";
  orgFilter.value = null;
  load();
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({
  office_name: "", org_id: null, project_id: null, building: "", floor: "",
  address: "", sort: 0, status: 1, remark: "",
});

function openCreate() {
  editing.value = null;
  Object.assign(form, {
    office_name: "", org_id: orgOptions.value[0]?.id ?? null, project_id: null,
    building: "", floor: "", address: "", sort: 0, status: 1, remark: "",
  });
  formVisible.value = true;
}
function openEdit(row) {
  editing.value = row;
  Object.assign(form, {
    office_name: row.office_name, org_id: row.org_id, project_id: row.project_id,
    building: row.building || "", floor: row.floor || "", address: row.address || "",
    sort: row.sort || 0, status: row.status, remark: "",
  });
  formVisible.value = true;
}
async function save() {
  if (!form.office_name.trim()) return ElMessage.warning("请填写地点名称");
  if (!form.org_id) return ElMessage.warning("请选择所属公司");
  saving.value = true;
  try {
    await archiveApi.saveOffice({ ...form, id: editing.value?.id });
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
      `确认删除办公地点「${row.office_name}」？名下存在资产时将无法删除。`,
      "删除", { type: "warning" }
    );
  } catch {
    return;
  }
  await archiveApi.delOffice(row.id);
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
