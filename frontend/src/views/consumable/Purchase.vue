<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">易耗品采购管理</h1>
      <span class="page__sub">采购审批通过后可「入库」或「直接分配领用」</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="采购单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-perm="'con_purchase:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">新建采购单</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="purchase_no" label="采购单号" width="150" fixed />
        <el-table-column prop="org_name" label="核算公司" width="130" show-overflow-tooltip />
        <el-table-column prop="apply_user_name" label="申请人" width="100" />
        <el-table-column prop="apply_date" label="申请日期" width="102" :formatter="(_, __, v) => fmtDate(v)" />
        <el-table-column label="总金额" width="110" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.total_amount) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="DOC_STATUS[row.status]?.type" size="small">{{ DOC_STATUS[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="150" :formatter="(_, __, v) => fmtDateTime(v)" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">明细</el-button>
            <el-button v-if="row.status === 0" link type="success" size="small" @click="submit(row)">{{ flowEnabled ? "提交审批" : "提交" }}</el-button>
            <el-button v-if="row.status === 1 && !flowEnabled" v-perm="'approval:approve'" link type="success" size="small" @click="manualApprove(row)">手动审批</el-button>
            <el-button v-if="row.status === 2" v-perm="'con_issue:create'" link type="warning" size="small" @click="openDirectIssue(row)">分配领用</el-button>
            <el-button v-if="row.status === 0 || row.status === 1" link type="danger" size="small" @click="cancel(row)">撤销</el-button>
            <el-button v-if="row.status === 0" v-perm="'con_purchase:create'" link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 张采购单</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细 -->
    <el-drawer v-model="detailVisible" size="680px" :title="`采购单 ${detail.purchase_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="核算公司">{{ detail.org_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ detail.apply_user_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="申请日期">{{ fmtDate(detail.apply_date) }}</el-descriptions-item>
        <el-descriptions-item label="总金额"><span class="num">{{ fmtMoney(detail.total_amount) }}</span></el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="DOC_STATUS[detail.status]?.type" size="small">{{ DOC_STATUS[detail.status]?.label }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="已入库/已直发">{{ detail.inbound_num ?? 0 }} / {{ detail.issued_num ?? 0 }}</el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">采购明细</div>
      <el-table :data="detail.items || []" size="small" border>
        <el-table-column prop="item_name" label="物料" min-width="140" show-overflow-tooltip />
        <el-table-column prop="num" label="数量" width="70" align="right" />
        <el-table-column label="单价" width="90" align="right"><template #default="{ row }"><span class="num">{{ fmtMoney(row.unit_price) }}</span></template></el-table-column>
        <el-table-column label="金额" width="100" align="right"><template #default="{ row }"><span class="num">{{ fmtMoney(row.amount) }}</span></template></el-table-column>
        <el-table-column prop="inbound_num" label="已入库" width="80" align="center" />
        <el-table-column prop="issued_num" label="已直发" width="80" align="center" />
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建采购单" width="820px" destroy-on-close top="5vh">
      <el-form :model="form" label-width="90px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="核算公司" required>
              <el-select v-model="form.org_id" filterable placeholder="请选择" style="width: 100%">
                <el-option v-for="o in orgs" :key="o.id" :label="o.org_name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="申请日期">
              <el-date-picker v-model="form.apply_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="sec-title mt-12">采购明细</div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px">
          <el-select v-model="pickItem" filterable placeholder="选择物料" style="width: 240px">
            <el-option v-for="it in itemOptions" :key="it.id" :label="`${it.item_name} (${it.spec || '-'})`" :value="it.id" />
          </el-select>
          <el-button type="primary" plain @click="addItem">添加</el-button>
          <span class="text-muted">合计金额：<b class="num">{{ fmtMoney(totalAmount) }}</b></span>
        </div>
        <el-table v-if="form.items.length" :data="form.items" size="small" border>
          <el-table-column prop="item_name" label="物料" min-width="150" show-overflow-tooltip />
          <el-table-column label="数量" width="120"><template #default="{ row }"><el-input-number v-model="row.num" :min="1" size="small" style="width: 100%" /></template></el-table-column>
          <el-table-column label="单价" width="130"><template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" style="width: 100%" /></template></el-table-column>
          <el-table-column label="金额" width="110" align="right"><template #default="{ row }"><span class="num">{{ fmtMoney((row.num || 0) * (row.unit_price || 0)) }}</span></template></el-table-column>
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

    <!-- 分配领用（采购直发） -->
    <el-dialog v-model="issueVisible" title="采购直接分配领用" width="720px" destroy-on-close>
      <el-form :model="issueForm" label-width="90px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="领用人">
              <el-select v-model="issueForm.receive_user" filterable clearable placeholder="请选择" style="width: 100%">
                <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="领用日期">
              <el-date-picker v-model="issueForm.issue_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="sec-title mt-12">分配数量（不超过可分配余量）</div>
        <el-table :data="allocItems" size="small" border>
          <el-table-column prop="item_name" label="物料" min-width="150" show-overflow-tooltip />
          <el-table-column label="可分配" width="80" align="center"><template #default="{ row }"><span class="num">{{ row.num - (row.inbound_num || 0) - (row.issued_num || 0) }}</span></template></el-table-column>
          <el-table-column label="本次领用" width="130"><template #default="{ row }"><el-input-number v-model="row.alloc" :min="0" :max="row.num - (row.inbound_num || 0) - (row.issued_num || 0)" size="small" style="width: 100%" /></template></el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="issueVisible = false">取消</el-button>
        <el-button type="primary" :loading="issuing" :disabled="!allocItems.some((i) => i.alloc > 0)" @click="doDirectIssue">保存领用单（草稿）</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { conApi, docApi, sysApi } from "../../api";
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
const orgs = ref([]);
const users = ref([]);
const itemOptions = ref([]);

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    const res = await conApi.purchases(params);
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

// 明细
const detailVisible = ref(false);
const detail = ref({});
async function openDetail(row) {
  detail.value = await conApi.purchase(row.id);
  detailVisible.value = true;
}

// 新建
const formVisible = ref(false);
const pickItem = ref(null);
const form = reactive({ org_id: null, apply_date: "", remark: "", items: [] });
const totalAmount = computed(() => form.items.reduce((s, i) => s + (i.num || 0) * (i.unit_price || 0), 0));
function addItem() {
  if (!pickItem.value) return ElMessage.warning("请选择物料");
  const it = itemOptions.value.find((x) => x.id === pickItem.value);
  if (form.items.some((x) => x.item_id === it.id)) {
    ElMessage.warning("该物料已添加");
    return;
  }
  form.items.push({ item_id: it.id, item_name: it.item_name, num: 1, unit_price: it.unit_price ?? 0 });
  pickItem.value = null;
}
function openCreate() {
  Object.assign(form, { org_id: null, apply_date: todayStr(), remark: "", items: [] });
  pickItem.value = null;
  formVisible.value = true;
}
function save(submit = false) {
  if (!form.org_id) return ElMessage.warning("请选择核算公司");
  if (!form.items.length) return ElMessage.warning("请添加采购明细");
  saving.value = true;
  (async () => {
    try {
      const created = await conApi.createPurchase({
        org_id: form.org_id,
        apply_date: form.apply_date || null,
        remark: form.remark || null,
        items: form.items.map((i) => ({ item_id: i.item_id, num: i.num, unit_price: i.unit_price ?? null })),
      });
      if (submit) {
        const res = await docApi.submit("con_purchase", created.id);
        ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
      } else {
        ElMessage.success("采购单已保存（草稿）");
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
      ? `确认提交「${row.purchase_no}」进入审批？`
      : `确认提交「${row.purchase_no}」待手动审批？`;
    await ElMessageBox.confirm(tip, flowEnabled.value ? "提交审批" : "提交", { type: "warning" });
  } catch {
    return;
  }
  const res = await docApi.submit("con_purchase", row.id);
  ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
  load();
}
async function manualApprove(row) {
  try {
    await ElMessageBox.confirm("手动审批通过后单据立即生效，确认通过？", "手动审批", { type: "warning" });
  } catch {
    return;
  }
  await docApi.manualApprove("con_purchase", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，确认？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("con_purchase", row.id);
  ElMessage.success("已撤销");
  load();
}
async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除采购单「${row.purchase_no}」？`, "删除", { type: "warning" });
  } catch {
    return;
  }
  await conApi.delPurchase(row.id);
  ElMessage.success("已删除");
  load();
}

// 分配领用（采购直发）
const issueVisible = ref(false);
const issuing = ref(false);
const issueForm = reactive({ receive_user: null, issue_date: "" });
const allocItems = ref([]);
const currentPurchase = ref(null);
async function openDirectIssue(row) {
  const d = await conApi.purchase(row.id);
  currentPurchase.value = d;
  issueForm.receive_user = null;
  issueForm.issue_date = todayStr();
  allocItems.value = (d.items || [])
    .map((i) => ({ ...i, alloc: 0 }))
    .filter((i) => i.num - (i.inbound_num || 0) - (i.issued_num || 0) > 0);
  if (!allocItems.value.length) return ElMessage.warning("该采购单已无剩余可分配数量");
  issueVisible.value = true;
}
async function doDirectIssue() {
  const items = allocItems.value.filter((i) => i.alloc > 0).map((i) => ({ item_id: i.item_id, num: i.alloc }));
  if (!items.length) return;
  issuing.value = true;
  try {
    await conApi.createIssue({
      source_type: 1,
      purchase_id: currentPurchase.value.id,
      org_id: currentPurchase.value.org_id,
      receive_user: issueForm.receive_user || null,
      issue_date: issueForm.issue_date || null,
      remark: "采购直接分配领用",
      items,
    });
    ElMessage.success("领用单已保存（草稿），可在领用管理提交审批");
    issueVisible.value = false;
    load();
  } finally {
    issuing.value = false;
  }
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("con_purchase");
  try {
    const [os, us, iopts] = await Promise.all([sysApi.orgs(), sysApi.users({ page: 1, page_size: 200 }), conApi.itemOptions()]);
    orgs.value = Array.isArray(os) ? os : os.records || [];
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
