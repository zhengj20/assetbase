<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">易耗品物料档案</h1>
      <span class="page__sub">易耗品（低值易耗品/办公用品）基础台账，独立于固定资产</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="物料编码/名称" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-input v-model="q.category" placeholder="分类" clearable style="width: 140px" @keyup.enter="load" />
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-perm="'con_item:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">新增物料</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="item_code" label="物料编码" width="120" fixed />
        <el-table-column prop="item_name" label="物料名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="120" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="70" align="center" />
        <el-table-column prop="category" label="分类" width="110" show-overflow-tooltip />
        <el-table-column label="默认单价" width="110" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.unit_price) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{ row.status === 1 ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-perm="'con_item:create'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-perm="'con_item:create'" link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 项物料</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <el-dialog v-model="formVisible" :title="form.id ? '编辑物料' : '新增物料'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item label="物料编码" required>
          <el-input v-model="form.item_code" :disabled="!!form.id" placeholder="如 YH-A4" />
        </el-form-item>
        <el-form-item label="物料名称" required>
          <el-input v-model="form.item_name" placeholder="如 A4复印纸" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="规格"><el-input v-model="form.spec" placeholder="选填" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位"><el-input v-model="form.unit" placeholder="个/包/瓶" /></el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="分类"><el-input v-model="form.category" placeholder="如 办公用品" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认单价"><el-input-number v-model="form.unit_price" :min="0" :precision="2" style="width: 100%" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
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
import { conApi } from "../../api";
import { fmtMoney } from "../../utils/constants";

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", category: "" });

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.category) params.category = q.category;
    const res = await conApi.items(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}
function reset() {
  q.keyword = "";
  q.category = "";
  page.value = 1;
  load();
}

const formVisible = ref(false);
const form = reactive({ id: null, item_code: "", item_name: "", spec: "", unit: "个", category: "", unit_price: null, status: 1, remark: "" });
function openCreate() {
  Object.assign(form, { id: null, item_code: "", item_name: "", spec: "", unit: "个", category: "", unit_price: null, status: 1, remark: "" });
  formVisible.value = true;
}
function openEdit(row) {
  Object.assign(form, { id: row.id, item_code: row.item_code, item_name: row.item_name, spec: row.spec || "", unit: row.unit, category: row.category || "", unit_price: row.unit_price, status: row.status, remark: row.remark || "" });
  formVisible.value = true;
}
function save() {
  if (!form.item_code) return ElMessage.warning("请填写物料编码");
  if (!form.item_name) return ElMessage.warning("请填写物料名称");
  saving.value = true;
  (async () => {
    try {
      const { id, ...body } = form;
      await conApi.saveItem(id ? { ...body, id } : body);
      ElMessage.success("已保存");
      formVisible.value = false;
      load();
    } finally {
      saving.value = false;
    }
  })();
}
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除物料「${row.item_name}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await conApi.delItem(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
