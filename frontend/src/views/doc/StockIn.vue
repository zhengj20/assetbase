<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">入库管理</h1>
      <div class="flex gap-8">
        <el-button v-perm="'stockin:create'" type="primary" :icon="Plus" @click="openCreate">新建入库单</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="入库单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="in_no" label="入库单号" width="150" fixed />
        <el-table-column label="仓库" width="130">
          <template #default="{ row }">{{ whName(row.warehouse_id) }}</template>
        </el-table-column>
        <el-table-column label="入库类型" width="100" align="center">
          <template #default="{ row }">{{ IN_TYPE[row.in_type] || "-" }}</template>
        </el-table-column>
        <el-table-column prop="in_date" label="入库日期" width="102" />
        <el-table-column prop="total_num" label="数量" width="70" align="right" />
        <el-table-column label="总金额" width="120" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.total_price) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="88" align="center">
          <template #default="{ row }">
            <el-tag :type="DOC_STATUS[row.status]?.type" size="small">{{ DOC_STATUS[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="150" :formatter="(_, __, v) => fmtDateTime(v)" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">明细</el-button>
            <el-button v-if="row.status === 0" link type="success" size="small" @click="submit(row)">{{ flowEnabled ? "提交审批" : "提交" }}</el-button>
            <el-button v-if="row.status === 1 && !flowEnabled" v-perm="'approval:approve'" link type="success" size="small" @click="manualApprove(row)">手动审批</el-button>
            <el-button v-if="row.status === 0 || row.status === 1" link type="danger" size="small" @click="cancel(row)">撤销</el-button>
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

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" size="600px" :title="`入库单 ${detail.in_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="仓库">{{ detail.warehouse_name || whName(detail.warehouse_id) }}</el-descriptions-item>
        <el-descriptions-item label="入库类型">{{ IN_TYPE[detail.in_type] || "-" }}</el-descriptions-item>
        <el-descriptions-item label="入库日期">{{ fmtDate(detail.in_date) }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ detail.total_num }}</el-descriptions-item>
        <el-descriptions-item label="总金额"><span class="money">{{ fmtMoney(detail.total_price) }}</span></el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="DOC_STATUS[detail.status]?.type" size="small">{{ DOC_STATUS[detail.status]?.label }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">入库明细（审批通过后自动建档赋码）</div>
      <el-table :data="detail.items || []" size="small" border>
        <el-table-column prop="asset_name" label="资产名称" min-width="150" />
        <el-table-column prop="num" label="数量" width="64" align="center" />
        <el-table-column label="单价" width="100" align="right">
          <template #default="{ row }">{{ fmtMoney(row.unit_price) }}</template>
        </el-table-column>
        <el-table-column label="金额" width="110" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.amount) }}</span></template>
        </el-table-column>
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 选择采购申请对话框 -->
    <el-dialog v-model="purchaseDialogVisible" title="选择采购申请" width="800px" destroy-on-close>
      <div class="filter-bar" style="padding-left: 0">
        <el-input v-model="purchaseQuery.keyword" placeholder="采购单号" clearable @keyup.enter="loadPurchases" />
        <el-button type="primary" plain @click="loadPurchases">查询</el-button>
      </div>
      <el-table :data="purchaseList" v-loading="purchaseLoading" height="400" @row-click="selectPurchase" highlight-current-row>
        <el-table-column prop="apply_no" label="采购单号" width="150" />
        <el-table-column prop="org_name" label="核算公司" width="140" show-overflow-tooltip />
        <el-table-column prop="apply_date" label="申请日期" width="100" />
        <el-table-column label="总金额" width="120" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.total_amount) }}</span></template>
        </el-table-column>
        <el-table-column prop="total_num" label="采购数量" width="90" align="center" />
        <el-table-column prop="inbound_num" label="已入库" width="80" align="center" />
        <el-table-column label="可入库" width="80" align="center">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.remaining_num === 0 }">{{ row.remaining_num }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.fully_inbound" type="info" size="small">已全部入库</el-tag>
            <el-tag v-else type="success" size="small">可入库</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="purchaseDialogVisible = false">取消</el-button>
      </template>
    </el-dialog>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建入库单" width="820px" destroy-on-close top="6vh">
      <el-form :model="form" label-width="86px">
        <el-row :gutter="14">
          <el-col :span="8">
            <el-form-item label="入库单号">
              <el-input v-model="form.in_no" readonly placeholder="保存时自动生成">
                <template #append>
                  <el-button @click="refreshNo" :disabled="!formVisible">刷新</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="入库仓库" required>
              <el-select v-model="form.warehouse_id" filterable>
                <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="入库类型" required>
              <el-select v-model="form.in_type" @change="onInTypeChange">
                <el-option v-for="(t, k) in IN_TYPE" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="入库日期">
              <el-date-picker v-model="form.in_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="供应商">
              <el-select v-model="form.supplier_id" filterable clearable>
                <el-option v-for="s in suppliers" :key="s.id" :label="s.supplier_name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 采购入库时显示选择采购申请按钮 -->
        <el-form-item v-if="form.in_type === 1" label="采购申请">
          <div v-if="form.purchase_id" class="purchase-selected">
            <el-tag closable @close="clearPurchase">{{ selectedPurchase?.apply_no }}</el-tag>
            <span class="text-muted" style="margin-left: 8px">{{ selectedPurchase?.org_name }}</span>
          </div>
          <el-button v-else type="primary" plain @click="openPurchaseDialog">选择采购申请</el-button>
        </el-form-item>

        <div class="sec-title">入库明细（一单多明细，审批生效后逐条生成资产档案并打印二维码）</div>
        <el-table :data="form.items" size="small" border>
          <el-table-column label="资产名称" min-width="150">
            <template #default="{ row }"><el-input v-model="row.asset_name" placeholder="名称" /></template>
          </el-table-column>
          <el-table-column label="分类" width="160">
            <template #default="{ row }">
              <el-tree-select v-model="row.category_id" :data="categoryTree" node-key="id"
                :props="{ label: 'category_name', children: 'children' }" check-strictly size="small" />
            </template>
          </el-table-column>
          <el-table-column label="数量" width="90">
            <template #default="{ row }"><el-input-number v-model="row.num" :min="1" size="small" controls-position="right" /></template>
          </el-table-column>
          <el-table-column label="单价" width="130">
            <template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" :controls="false" size="small" style="width: 100%" /></template>
          </el-table-column>
          <el-table-column width="60" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="form.items.splice($index, 1)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button class="mt-8" :icon="Plus" plain size="small" @click="form.items.push({ asset_name: '', category_id: null, num: 1, unit_price: null })">
          添加明细行
        </el-button>

        <el-form-item label="备注" class="mt-12">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
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
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { docApi, archiveApi } from "../../api";
import { DOC_STATUS, IN_TYPE, fmtMoney, fmtDate, fmtDateTime, todayStr } from "../../utils/constants";
import { loadFlowEnabled } from "../../utils/approval";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";

const router = useRouter();

const loading = ref(false);
const saving = ref(false);
const flowEnabled = ref(true);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null });

const warehouses = ref([]);
const suppliers = ref([]);
const categories = ref([]);
const whName = (id) => warehouses.value.find((w) => w.id === id)?.warehouse_name || id;
const categoryTree = computed(() => {
  const roots = categories.value.filter((c) => !c.parent_id || c.parent_id === 0);
  return roots.map((r) => ({ ...r, children: categories.value.filter((c) => c.parent_id === r.id) }));
});

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    const res = await docApi.stockIns(params);
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

// ---- 明细 ----
const detailVisible = ref(false);
const detail = ref({});
async function openDetail(row) {
  detail.value = await docApi.stockIn(row.id);
  detailVisible.value = true;
}

// ---- 采购申请选择 ----
const purchaseDialogVisible = ref(false);
const purchaseLoading = ref(false);
const purchaseList = ref([]);
const purchaseQuery = reactive({ keyword: "" });
const selectedPurchase = ref(null);

async function openPurchaseDialog() {
  purchaseDialogVisible.value = true;
  purchaseQuery.keyword = "";
  await loadPurchases();
}

async function loadPurchases() {
  purchaseLoading.value = true;
  try {
    const params = { page: 1, page_size: 50 };
    if (purchaseQuery.keyword) params.keyword = purchaseQuery.keyword;
    const res = await docApi.approvedPurchases(params);
    purchaseList.value = (res.records || []).filter((p) => !p.fully_inbound);
  } finally {
    purchaseLoading.value = false;
  }
}

async function selectPurchase(row) {
  if (row.fully_inbound) {
    ElMessage.warning("该采购申请已全部入库");
    return;
  }
  selectedPurchase.value = row;
  form.purchase_id = row.id;
  form.supplier_id = row.supplier_id;
  
  // 加载采购申请的可入库明细
  try {
    const res = await docApi.purchaseItemsForInbound(row.id);
    if (res.items && res.items.length > 0) {
      // 过滤掉可入库数量为0的明细行
      const validItems = res.items.filter((item) => item.num > 0);
      if (validItems.length === 0) {
        ElMessage.warning("该采购申请已全部入库");
        form.purchase_id = null;
        selectedPurchase.value = null;
        return;
      }
      form.items = validItems.map((item) => ({
        category_id: item.category_id,
        asset_name: item.asset_name,
        spec: item.spec,
        num: item.num,
        unit_price: item.unit_price ? Number(item.unit_price) : null,
      }));
    } else {
      ElMessage.warning("该采购申请无可入库明细");
      form.purchase_id = null;
      selectedPurchase.value = null;
    }
  } catch (e) {
    console.error("加载采购明细失败", e);
    ElMessage.error("加载采购明细失败");
  }
  
  purchaseDialogVisible.value = false;
  ElMessage.success(`已选择采购申请 ${row.apply_no}`);
}

function clearPurchase() {
  selectedPurchase.value = null;
  form.purchase_id = null;
  form.items = [{ asset_name: "", category_id: null, num: 1, unit_price: null }];
}

function onInTypeChange() {
  // 切换入库类型时清空采购申请选择
  if (form.in_type !== 1) {
    clearPurchase();
  }
}

// ---- 新建 ----
const formVisible = ref(false);
const form = reactive({ in_no: "", warehouse_id: null, in_type: 1, in_date: "", supplier_id: null, purchase_id: null, remark: "", items: [] });
function openCreate() {
  Object.assign(form, {
    in_no: "",
    warehouse_id: warehouses.value[0]?.id ?? null, in_type: 1,
    in_date: todayStr(), supplier_id: null, purchase_id: null, remark: "",
    items: [{ asset_name: "", category_id: null, num: 1, unit_price: null }],
  });
  selectedPurchase.value = null;
  formVisible.value = true;
  refreshNo();
}

// ---- 编号预览（自动生成，只读展示） ----
async function refreshNo() {
  try {
    const res = await docApi.nextDocNo("stock_in");
    form.in_no = res.next_no;
  } catch {
    form.in_no = "";
  }
}
async function save(submit = false) {
  if (!form.warehouse_id) return ElMessage.warning("请选择入库仓库");
  if (form.in_type === 1 && !form.purchase_id) return ElMessage.warning("采购入库必须选择采购申请");
  const items = form.items.filter((i) => i.asset_name?.trim());
  if (!items.length) return ElMessage.warning("请至少填写一行入库明细");
  saving.value = true;
  try {
    const created = await docApi.createStockIn({ ...form, items });
    if (submit) {
      const res = await docApi.submit("stock_in", created.id);
      ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
      formVisible.value = false;
      load();
      return;
    }
    ElMessage.success("入库单已保存（草稿）");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

const submitting = ref(false);
async function submit(row) {
  if (submitting.value) return;
  const tip = flowEnabled.value ? "提交后单据进入审批流，确认提交？" : "提交后单据待手动审批，确认提交？";
  try {
    await ElMessageBox.confirm(tip, "提交", { type: "warning" });
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const res = await docApi.submit("stock_in", row.id);
    ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
    load();
  } finally {
    submitting.value = false;
  }
}
async function manualApprove(row) {
  try {
    await ElMessageBox.confirm("手动审批通过后单据立即生效，确认通过？", "手动审批", { type: "warning" });
  } catch {
    return;
  }
  await docApi.manualApprove("stock_in", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，确认撤销？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("stock_in", row.id);
  ElMessage.success("已撤销");
  load();
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("stock_in");
  const [ws, ss, cs] = await Promise.allSettled([archiveApi.warehouses(), archiveApi.suppliers(), archiveApi.categories()]);
  if (ws.status === "fulfilled") warehouses.value = ws.value;
  if (ss.status === "fulfilled") suppliers.value = ss.value;
  if (cs.status === "fulfilled") categories.value = cs.value;
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
