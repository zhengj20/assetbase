<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">易耗品领用管理</h1>
      <span class="page__sub">来源：库存领用 / 采购直发 · 审批通过后扣减库存或采购余量</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="领用单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable style="width: 120px" @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-select v-model="q.source_type" placeholder="来源" clearable style="width: 120px" @change="page = 1, load()">
          <el-option label="库存领用" :value="2" />
          <el-option label="采购直发" :value="1" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-perm="'con_issue:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">新建领用单</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="issue_no" label="领用单号" width="150" fixed />
        <el-table-column prop="source_name" label="来源" width="100" align="center" />
        <el-table-column prop="receive_user_name" label="领用人" width="100" />
        <el-table-column label="总数量" width="90" align="right"><template #default="{ row }"><span class="num">{{ row.total_num }}</span></template></el-table-column>
        <el-table-column prop="issue_date" label="领用日期" width="102" :formatter="(_, __, v) => fmtDate(v)" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }"><el-tag :type="DOC_STATUS[row.status]?.type" size="small">{{ DOC_STATUS[row.status]?.label }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="150" :formatter="(_, __, v) => fmtDateTime(v)" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">明细</el-button>
            <el-button v-if="row.status === 0" link type="success" size="small" @click="submit(row)">{{ flowEnabled ? "提交审批" : "提交" }}</el-button>
            <el-button v-if="row.status === 1 && !flowEnabled" v-perm="'approval:approve'" link type="success" size="small" @click="manualApprove(row)">手动审批</el-button>
            <el-button v-if="row.status === 0 || row.status === 1" link type="danger" size="small" @click="cancel(row)">撤销</el-button>
            <el-button v-if="row.status === 0" v-perm="'con_issue:create'" link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 张领用单</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细 -->
    <el-drawer v-model="detailVisible" size="600px" :title="`领用单 ${detail.issue_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="来源">{{ detail.source_name || (detail.source_type === 1 ? "采购直发" : "库存领用") }}</el-descriptions-item>
        <el-descriptions-item label="领用人">{{ detail.receive_user_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="领用日期">{{ fmtDate(detail.issue_date) }}</el-descriptions-item>
        <el-descriptions-item label="仓库/来源">{{ detail.warehouse_name || (detail.purchase_id ? `采购单 #${detail.purchase_id}` : "-") }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag :type="DOC_STATUS[detail.status]?.type" size="small">{{ DOC_STATUS[detail.status]?.label }}</el-tag></el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">领用明细</div>
      <el-table :data="detail.items || []" size="small" border>
        <el-table-column prop="item_name" label="物料" min-width="160" show-overflow-tooltip />
        <el-table-column prop="num" label="数量" width="80" align="right" />
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建领用单" width="760px" destroy-on-close top="5vh">
      <el-form :model="form" label-width="100px">
        <el-form-item label="领用来源" required>
          <el-radio-group v-model="form.source_type">
            <el-radio :value="2">从库存领用</el-radio>
            <el-radio :value="1">采购直接分配</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="14">
          <el-col v-if="form.source_type === 2" :span="12">
            <el-form-item label="领用仓库" required>
              <el-select v-model="form.warehouse_id" filterable placeholder="请选择" style="width: 100%">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-else :span="12">
            <el-form-item label="采购单" required>
              <el-select v-model="form.purchase_id" filterable placeholder="选择已通过采购单" style="width: 100%">
                <el-option v-for="p in approvedPurchases" :key="p.id" :label="p.purchase_no" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="领用人">
              <el-select v-model="form.receive_user" filterable clearable placeholder="选填" style="width: 100%">
                <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="领用日期">
              <el-date-picker v-model="form.issue_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="sec-title mt-12">领用明细</div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px">
          <el-select v-model="pickItem" filterable placeholder="选择物料" style="width: 240px">
            <el-option v-for="it in itemOptions" :key="it.id" :label="`${it.item_name} (${it.spec || '-'})`" :value="it.id" />
          </el-select>
          <el-button type="primary" plain @click="addItem">添加</el-button>
          <span class="text-muted">合计：<b class="num">{{ form.items.reduce((s, i) => s + (i.num || 0), 0) }}</b> 件</span>
        </div>
        <el-table v-if="form.items.length" :data="form.items" size="small" border>
          <el-table-column prop="item_name" label="物料" min-width="160" show-overflow-tooltip />
          <el-table-column label="数量" width="130"><template #default="{ row }"><el-input-number v-model="row.num" :min="1" size="small" style="width: 100%" /></template></el-table-column>
          <el-table-column label="操作" width="70" align="center"><template #default="{ $index }"><el-button link type="danger" size="small" @click="form.items.splice($index, 1)">移除</el-button></template></el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button :loading="saving" @click="save(false)">保存草稿</el-button>
        <el-button type="primary" :loading="saving" @click="save(true)">发起审批</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { conApi, docApi, sysApi, archiveApi } from "../../api";
import { DOC_STATUS, fmtDate, fmtDateTime, todayStr } from "../../utils/constants";
import { loadFlowEnabled } from "../../utils/approval";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";

const flowEnabled = ref(true);
const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null, source_type: null });
const warehouses = ref([]);
const users = ref([]);
const itemOptions = ref([]);
const approvedPurchases = ref([]);

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    if (q.source_type !== null) params.source_type = q.source_type;
    const res = await conApi.issues(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}
function reset() {
  q.keyword = "";
  q.status = null;
  q.source_type = null;
  page.value = 1;
  load();
}

const detailVisible = ref(false);
const detail = ref({});
async function openDetail(row) {
  detail.value = await conApi.issue(row.id);
  detailVisible.value = true;
}

const formVisible = ref(false);
const pickItem = ref(null);
const form = reactive({ source_type: 2, warehouse_id: null, purchase_id: null, receive_user: null, issue_date: "", items: [] });
function addItem() {
  if (!pickItem.value) return ElMessage.warning("请选择物料");
  const it = itemOptions.value.find((x) => x.id === pickItem.value);
  if (form.items.some((x) => x.item_id === it.id)) return ElMessage.warning("该物料已添加");
  form.items.push({ item_id: it.id, item_name: it.item_name, num: 1 });
  pickItem.value = null;
}
function openCreate() {
  Object.assign(form, { source_type: 2, warehouse_id: null, purchase_id: null, receive_user: null, issue_date: todayStr(), items: [] });
  pickItem.value = null;
  loadApprovedPurchases();
  formVisible.value = true;
}
async function loadApprovedPurchases() {
  try {
    const res = await conApi.purchases({ status: 2, page: 1, page_size: 100 });
    approvedPurchases.value = res.records || [];
  } catch {
    approvedPurchases.value = [];
  }
}
function save(submit = false) {
  if (form.source_type === 2 && !form.warehouse_id) return ElMessage.warning("请选择领用仓库");
  if (form.source_type === 1 && !form.purchase_id) return ElMessage.warning("请选择采购单");
  if (!form.items.length) return ElMessage.warning("请添加领用明细");
  saving.value = true;
  (async () => {
    try {
      const created = await conApi.createIssue({
        source_type: form.source_type,
        warehouse_id: form.source_type === 2 ? form.warehouse_id : null,
        purchase_id: form.source_type === 1 ? form.purchase_id : null,
        receive_user: form.receive_user || null,
        issue_date: form.issue_date || null,
        items: form.items.map((i) => ({ item_id: i.item_id, num: i.num })),
      });
      if (submit) {
        const res = await docApi.submit("con_issue", created.id);
        ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
      } else {
        ElMessage.success("领用单已保存（草稿）");
      }
      formVisible.value = false;
      load();
    } finally {
      saving.value = false;
    }
  })();
}

async function submit(row) {
  try {
    const tip = flowEnabled.value
      ? `确认提交「${row.issue_no}」进入审批？`
      : `确认提交「${row.issue_no}」待手动审批？`;
    await ElMessageBox.confirm(tip, flowEnabled.value ? "提交审批" : "提交", { type: "warning" });
  } catch {
    return;
  }
  const res = await docApi.submit("con_issue", row.id);
  ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
  load();
}
async function manualApprove(row) {
  try {
    await ElMessageBox.confirm("手动审批通过后单据立即生效，确认通过？", "手动审批", { type: "warning" });
  } catch {
    return;
  }
  await docApi.manualApprove("con_issue", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，确认？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("con_issue", row.id);
  ElMessage.success("已撤销");
  load();
}
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除领用单「${row.issue_no}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await conApi.delIssue(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("con_issue");
  try {
    const [ws, us, iopts] = await Promise.all([archiveApi.warehouses(), sysApi.users({ page: 1, page_size: 200 }), conApi.itemOptions()]);
    warehouses.value = Array.isArray(ws) ? ws : ws.records || [];
    users.value = (us.records || []).filter((u) => u.status === 1);
    itemOptions.value = iopts || [];
  } catch {
    /* ignore */
  }
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
