<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">供应商档案</h1>
      <div class="flex gap-8">
        <el-button v-perm="'supplier:create'" type="primary" :icon="Plus" @click="openCreate">新增供应商</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="kw" placeholder="供应商名称/联系人" clearable :prefix-icon="Search" style="width: 220px" />
      </div>

      <el-table :data="filtered" v-loading="loading" height="100%">
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column prop="supplier_name" label="供应商名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="contact" label="联系人" width="110" />
        <el-table-column prop="phone" label="电话" width="130" />
        <el-table-column prop="bank_account" label="银行账户" width="180" show-overflow-tooltip />
        <el-table-column label="合作状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.coop_status === 1 ? 'success' : 'info'" size="small">
              {{ row.coop_status === 1 ? "合作中" : "已终止" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rating" label="评级" width="80" align="center" />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-perm="'supplier:edit'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-perm="'supplier:delete'" link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ filtered.length }} 家供应商</span>
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="editing ? '编辑供应商' : '新增供应商'" width="520px" destroy-on-close>
      <el-form :model="form" label-width="86px">
        <el-form-item label="供应商" required>
          <el-input v-model="form.supplier_name" maxlength="200" />
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="form.contact" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="电话">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="银行账户">
              <el-input v-model="form.bank_account" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="评级">
              <el-select v-model="form.rating" clearable>
                <el-option v-for="r in ['A', 'B', 'C', 'D']" :key="r" :label="r" :value="r" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合作状态">
              <el-switch v-model="form.coop_status" :active-value="1" :inactive-value="0" active-text="合作中" inactive-text="终止" />
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
import { archiveApi } from "../../api";

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const kw = ref("");

const filtered = computed(() => {
  const k = kw.value.trim();
  if (!k) return rows.value;
  return rows.value.filter(
    (r) => r.supplier_name?.includes(k) || r.contact?.includes(k)
  );
});

async function load() {
  loading.value = true;
  try {
    rows.value = await archiveApi.suppliers();
  } finally {
    loading.value = false;
  }
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({ supplier_name: "", contact: "", phone: "", bank_account: "", coop_status: 1, rating: null, remark: "" });

function openCreate() {
  editing.value = null;
  Object.assign(form, { supplier_name: "", contact: "", phone: "", bank_account: "", coop_status: 1, rating: null, remark: "" });
  formVisible.value = true;
}
function openEdit(row) {
  editing.value = row;
  Object.assign(form, { ...row, rating: row.rating || null });
  formVisible.value = true;
}
async function save() {
  if (!form.supplier_name.trim()) return ElMessage.warning("请填写供应商名称");
  saving.value = true;
  try {
    await archiveApi.saveSupplier({ ...form, id: editing.value?.id });
    ElMessage.success("已保存");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
async function del(row) {
  try {
    await ElMessageBox.confirm(`确认删除供应商「${row.supplier_name}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await archiveApi.delSupplier(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
