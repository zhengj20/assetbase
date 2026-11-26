<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">仓库管理</h1>
      <div class="flex gap-8">
        <el-button v-perm="'warehouse:create'" type="primary" :icon="Plus" @click="openCreate">新增仓库</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="kw" placeholder="仓库名称" clearable :prefix-icon="Search" style="width: 220px" />
        <el-select v-model="whType" placeholder="仓库类型" clearable>
          <el-option label="自有仓" :value="1" />
          <el-option label="租赁仓" :value="2" />
          <el-option label="项目现场" :value="3" />
        </el-select>
      </div>

      <el-table :data="filtered" v-loading="loading" height="100%">
        <el-table-column prop="warehouse_name" label="仓库名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">{{ WH_TYPE[row.warehouse_type] || "-" }}</template>
        </el-table-column>
        <el-table-column label="所属公司" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ orgName(row.org_id) }}</template>
        </el-table-column>
        <el-table-column prop="address" label="地址" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.address || "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? "启用" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewStock(row)">库存台账</el-button>
            <el-button v-perm="'warehouse:edit'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-perm="'warehouse:delete'" link type="danger" size="small" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ filtered.length }} 个仓库</span>
      </div>
    </div>

    <!-- 新建/编辑 -->
    <el-dialog v-model="formVisible" :title="editing ? '编辑仓库' : '新增仓库'" width="540px" destroy-on-close>
      <el-form :model="form" label-width="86px">
        <el-form-item label="仓库名称" required>
          <el-input v-model="form.warehouse_name" maxlength="100" />
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="仓库类型" required>
              <el-select v-model="form.warehouse_type">
                <el-option v-for="(t, k) in WH_TYPE" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属公司" required>
              <el-select v-model="form.org_id" filterable>
                <el-option v-for="o in orgs" :key="o.id" :label="o.org_name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="地址">
              <el-input v-model="form.address" placeholder="详细地址" />
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

    <!-- 库存台账 -->
    <el-drawer v-model="stockVisible" size="620px" :title="`库存台账 · ${curWh?.warehouse_name || ''}`">
      <el-table :data="stockRows" v-loading="stockLoading" size="small" border>
        <el-table-column prop="category_name" label="资产分类" min-width="140" />
        <el-table-column prop="total_count" label="总数" width="80" align="right" />
        <el-table-column prop="in_stock" label="在库" width="80" align="right" />
        <el-table-column label="资产原值合计" width="130" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.total_price) }}</span></template>
        </el-table-column>
      </el-table>
      <div v-if="!stockLoading && !stockRows.length" class="empty-hint">该仓库暂无在管资产</div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { archiveApi, sysApi } from "../../api";
import { fmtMoney } from "../../utils/constants";

const WH_TYPE = { 1: "自有仓", 2: "租赁仓", 3: "项目现场" };

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const kw = ref("");
const whType = ref(null);
const orgs = ref([]);
const orgName = (id) => orgs.value.find((o) => o.id === id)?.org_name || id;

const filtered = computed(() => {
  let list = rows.value;
  if (kw.value.trim()) list = list.filter((r) => r.warehouse_name?.includes(kw.value.trim()));
  if (whType.value !== null) list = list.filter((r) => r.warehouse_type === whType.value);
  return list;
});

async function load() {
  loading.value = true;
  try {
    rows.value = await archiveApi.warehouses();
  } finally {
    loading.value = false;
  }
}

const formVisible = ref(false);
const editing = ref(null);
const form = reactive({ warehouse_name: "", warehouse_type: 1, org_id: null, address: "", status: 1, remark: "" });

function openCreate() {
  editing.value = null;
  Object.assign(form, { warehouse_name: "", warehouse_type: 1, org_id: orgs.value[0]?.id ?? null, address: "", status: 1, remark: "" });
  formVisible.value = true;
}
function openEdit(row) {
  editing.value = row;
  Object.assign(form, { ...row, remark: "" });
  formVisible.value = true;
}
async function save() {
  if (!form.warehouse_name.trim()) return ElMessage.warning("请填写仓库名称");
  if (!form.org_id) return ElMessage.warning("请选择所属公司");
  saving.value = true;
  try {
    await archiveApi.saveWarehouse({ ...form, id: editing.value?.id });
    ElMessage.success("已保存");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
async function del(row) {
  try {
    await ElMessageBox.confirm(`确认删除仓库「${row.warehouse_name}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await archiveApi.delWarehouse(row.id);
  ElMessage.success("已删除");
  load();
}

// 库存台账
const stockVisible = ref(false);
const stockLoading = ref(false);
const stockRows = ref([]);
const curWh = ref(null);
async function viewStock(row) {
  curWh.value = row;
  stockVisible.value = true;
  stockLoading.value = true;
  try {
    stockRows.value = await archiveApi.warehouseStock(row.id);
  } finally {
    stockLoading.value = false;
  }
}

onMounted(async () => {
  orgs.value = await sysApi.orgs();
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
