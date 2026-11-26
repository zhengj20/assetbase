<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">用户管理</h1>
      <div class="flex gap-8">
        <el-button v-perm="'sys:user'" type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="用户名/姓名" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.org_id" placeholder="所属组织" clearable filterable @change="page = 1, load()">
          <el-option v-for="o in orgs" :key="o.id" :label="o.org_name" :value="o.id" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="username" label="登录名" width="130" fixed />
        <el-table-column prop="real_name" label="姓名" width="110" />
        <el-table-column label="所属组织" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ orgName(row.org_id) }}</template>
        </el-table-column>
        <el-table-column label="角色" min-width="160">
          <template #default="{ row }">
            <template v-if="roleMap.get(row.id)?.length">
              <el-tag v-for="rid in roleMap.get(row.id)" :key="rid" size="small" class="mr-4">{{ roleName(rid) }}</el-tag>
            </template>
            <span v-else class="text-muted">未分配</span>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? "正常" : "锁定" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="150" :formatter="(_, __, v) => fmtDateTime(v)" />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-perm="'sys:user'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-perm="'sys:user'" link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 位用户</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="editing ? '编辑用户' : '新增用户'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="92px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="登录名" required>
              <el-input v-model="form.username" :disabled="!!editing" maxlength="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" required>
              <el-input v-model="form.real_name" maxlength="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="editing ? '重置密码' : '初始密码'" :required="!editing">
              <el-input
                v-model="form.password" type="password" show-password maxlength="64"
                :placeholder="editing ? '留空则不修改' : '至少6位'"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属组织" required>
              <el-select v-model="form.org_id" filterable>
                <el-option v-for="o in orgs" :key="o.id" :label="o.org_name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="form.phone" maxlength="20" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" maxlength="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="分配角色">
          <el-select v-model="form.role_ids" multiple filterable style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.role_name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="正常" inactive-text="锁定" />
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
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { sysApi } from "../../api";
import { fmtDateTime } from "../../utils/constants";

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", org_id: null });

const orgs = ref([]);
const roles = ref([]);
const roleMap = ref(new Map());
const orgName = (id) => orgs.value.find((o) => o.id === id)?.org_name || id;
const roleName = (id) => roles.value.find((r) => r.id === id)?.role_name || `#${id}`;

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.org_id) params.org_id = q.org_id;
    const res = await sysApi.users(params);
    rows.value = res.records;
    total.value = res.total;
    roleMap.value = new Map(res.records.map((u) => [u.id, u.role_ids || []]));
  } finally {
    loading.value = false;
  }
}
function reset() {
  q.keyword = "";
  q.org_id = null;
  page.value = 1;
  load();
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({ username: "", real_name: "", password: "", org_id: null, phone: "", email: "", status: 1, role_ids: [] });

function openCreate() {
  editing.value = null;
  Object.assign(form, { username: "", real_name: "", password: "", org_id: orgs.value[0]?.id ?? null, phone: "", email: "", status: 1, role_ids: [] });
  formVisible.value = true;
}
function openEdit(row) {
  editing.value = row;
  Object.assign(form, {
    username: row.username, real_name: row.real_name, password: "",
    org_id: row.org_id, phone: row.phone || "", email: row.email || "",
    status: row.status, role_ids: roleMap.value.get(row.id) || [],
  });
  formVisible.value = true;
}
async function save() {
  if (!form.username.trim() || !form.real_name.trim()) return ElMessage.warning("请填写登录名与姓名");
  if (!form.org_id) return ElMessage.warning("请选择所属组织");
  if (!editing.value && !form.password) return ElMessage.warning("请设置初始密码");
  saving.value = true;
  try {
    await sysApi.saveUser({ ...form, id: editing.value?.id });
    ElMessage.success("已保存");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
async function del(row) {
  try {
    await ElMessageBox.confirm(`确认删除用户「${row.real_name}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await sysApi.delUser(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(async () => {
  const [os, rs] = await Promise.all([sysApi.orgs(), sysApi.roles()]);
  orgs.value = os;
  roles.value = rs;
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.mr-4 { margin-right: 4px; }
</style>
