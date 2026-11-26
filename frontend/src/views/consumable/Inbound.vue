<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">易耗品入库</h1>
      <span class="page__sub">采购入库 / 直接入库 · 审批通过后库存增加</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="入库单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-perm="'con_inbound:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">新建入库单</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="in_no" label="入库单号" width="150" fixed />
        <el-table-column prop="warehouse_name" label="入库仓库" width="140" show-overflow-tooltip />
        <el-table-column label="来源" width="100" align="center">
          <template #default="{ row }">{{ row.purchase_id ? "采购入库" : "直接入库" }}</template>
        </el-table-column>
        <el-table-column label="总数量" width="90" align="right"><template #default="{ row }"><span class="num">{{ row.total_num }}</span></template></el-table-column>
        <el-table-column label="总金额" width="110" align="right"><template #default="{ row }"><span class="num">{{ fmtMoney(row.total_amount) }}</span></template></el-table-column>
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
            <el-button v-if="row.status === 0" v-perm="'con_inbound:create'" link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 张入库单</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细 -->
    <el-drawer v-model="detailVisible" size="640px" :title="`入库单 ${detail.in_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="入库仓库">{{ detail.warehouse_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ detail.purchase_id ? "采购入库" : "直接入库" }}</el-descriptions-item>
        <el-descriptions-item label="入库日期">{{ fmtDate(detail.in_date) }}</el-descriptions-item>
        <el-descriptions-item label="总金额"><span class="num">{{ fmtMoney(detail.total_amount) }}</span></el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag :type="DOC_STATUS[detail.status]?.type" size="small">{{ DOC_STATUS[detail.status]?.label }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="制单人">{{ detail.create_by_name || "-" }}</el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">入库明细</div>
      <el-table :data="detail.items || []" size="small" border>
        <el-table-column prop="item_name" label="物料" min-width="150" show-overflow-tooltip />
        <el-table-column prop="num" label="数量" width="80" align="right" />
        <el-table-column label="单价" width="100" align="right"><template #default="{ row }"><span class="num">{{ fmtMoney(row.unit_price) }}</span></template></el-table-column>
        <el-table-column label="金额" width="110" align="right"><template #default="{ row }"><span class="num">{{ fmtMoney(row.amount) }}</span></template></el-table-column>
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建入库单" width="780px" destroy-on-close top="5vh">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="入库仓库" required>
              <el-select v-model="form.warehouse_id" filterable placeholder="请选择" style="width: 100%">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="入库日期">
              <el-date-picker v-model="form.in_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关联采购单">
          <el-select v-model="form.purchase_id" filterable clearable placeholder="选填（采购入库时选择已通过采购单）" style="width: 100%">
            <el-option v-for="p in approvedPurchases" :key="p.id" :label="`${p.purchase_no}（${p.org_name || ''}）`" :value="p.id" />
          </el-select>
        </el-form-item>
        <div class="sec-title mt-12">入库明细</div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px">
          <el-select v-model="pickItem" filterable placeholder="选择物料" style="width: 240px">
            <el-option v-for="it in itemOptions" :key="it.id" :label="`${it.item_name} (${it.spec || '-'})`" :value="it.id" />
          </el-select>
          <el-button type="primary" plain @click="addItem">添加</el-button>
          <span class="text-muted">合计：<b class="num">{{ form.items.reduce((s, i) => s + (i.num || 0), 0) }}</b> 件</span>
        </div>
        <el-table v-if="form.items.length" :data="form.items" size="small" border>
          <el-table-column prop="item_name" label="物料" min-width="160" show-overflow-tooltip />
          <el-table-column label="数量" width="120"><template #default="{ row }"><el-input-number v-model="row.num" :min="1" size="small" style="width: 100%" /></template></el-table-column>
          <el-table-column label="单价" width="130"><template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" style="width: 100%" /></template></el-table-column>
          <el-table-column label="操作" width="70" align="center"><template #default="{ $index }"><el-button link type="danger" size="small" @click="form.items.splice($index, 1)">移除</el-button></template></el-table-column>
        </el-table>
        <el-form-item label="备注" class="mt-12"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
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
import { conApi, docApi, archiveApi } from "../../api";
import { DOC_STATUS, fmtDate, fmtDateTime, fmtMoney, todayStr } from "../../utils/constants";
import { loadFlowEnabled } from "../../utils/approval";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";

const flowEnabled = ref(true);
const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null });
const warehouses = ref([]);
const itemOptions = ref([]);
const approvedPurchases = ref([]);

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    const res = await conApi.inbounds(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}
function reset() {
  q.keyword = "";
  q.status = null;
  page.value = 1;
  load();
}

const detailVisible = ref(false);
const detail = ref({});
async function openDetail(row) {
  detail.value = await conApi.inbound(row.id);
  detailVisible.value = true;
}

const formVisible = ref(false);
const pickItem = ref(null);
const form = reactive({ warehouse_id: null, in_date: "", purchase_id: null, remark: "", items: [] });
function addItem() {
  if (!pickItem.value) return ElMessage.warning("请选择物料");
  const it = itemOptions.value.find((x) => x.id === pickItem.value);
  if (form.items.some((x) => x.item_id === it.id)) return ElMessage.warning("该物料已添加");
  form.items.push({ item_id: it.id, item_name: it.item_name, num: 1, unit_price: it.unit_price ?? 0 });
  pickItem.value = null;
}
function openCreate() {
  Object.assign(form, { warehouse_id: null, in_date: todayStr(), purchase_id: null, remark: "", items: [] });
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
  if (!form.warehouse_id) return ElMessage.warning("请选择入库仓库");
  if (!form.items.length) return ElMessage.warning("请添加入库明细");
  saving.value = true;
  (async () => {
    try {
      const created = await conApi.createInbound({
        warehouse_id: form.warehouse_id,
        purchase_id: form.purchase_id || null,
        in_date: form.in_date || null,
        remark: form.remark || null,
        items: form.items.map((i) => ({ item_id: i.item_id, num: i.num, unit_price: i.unit_price ?? null })),
      });
      if (submit) {
        const res = await docApi.submit("con_inbound", created.id);
        ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
      } else {
        ElMessage.success("入库单已保存（草稿）");
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
      ? `确认提交「${row.in_no}」进入审批？`
      : `确认提交「${row.in_no}」待手动审批？`;
    await ElMessageBox.confirm(tip, flowEnabled.value ? "提交审批" : "提交", { type: "warning" });
  } catch {
    return;
  }
  const res = await docApi.submit("con_inbound", row.id);
  ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
  load();
}
async function manualApprove(row) {
  try {
    await ElMessageBox.confirm("手动审批通过后单据立即生效，确认通过？", "手动审批", { type: "warning" });
  } catch {
    return;
  }
  await docApi.manualApprove("con_inbound", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，确认？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("con_inbound", row.id);
  ElMessage.success("已撤销");
  load();
}
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除入库单「${row.in_no}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await conApi.delInbound(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("con_inbound");
  try {
    const [ws, iopts] = await Promise.all([archiveApi.warehouses(), conApi.itemOptions()]);
    warehouses.value = Array.isArray(ws) ? ws : ws.records || [];
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
