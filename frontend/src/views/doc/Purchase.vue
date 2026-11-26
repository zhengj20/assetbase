<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">采购申请</h1>
      <div class="flex gap-8">
        <el-button v-perm="'purchase:create'" type="primary" :icon="Plus" @click="openCreate">新建采购申请</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="申请单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="apply_no" label="申请单号" width="130" fixed />
        <el-table-column prop="org_name" label="核算公司" width="140" show-overflow-tooltip />
        <el-table-column prop="apply_user_name" label="申请人" width="90" />
        <el-table-column prop="apply_date" label="申请日期" width="102" />
        <el-table-column label="总金额" width="120" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.total_amount) }}</span></template>
        </el-table-column>
        <el-table-column prop="budget_item" label="预算项" width="120" show-overflow-tooltip />
        <el-table-column prop="cost_subject" label="成本科目" width="110" show-overflow-tooltip />
        <el-table-column prop="contract_no" label="合同编号" width="130" show-overflow-tooltip />
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
            <el-button v-if="row.status === 0" link type="danger" size="small" @click="del(row)">删除</el-button>
            <el-button v-if="row.status === 1" link type="warning" size="small" @click="cancel(row)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 张采购申请</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" size="620px" :title="`采购申请 ${detail.apply_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="核算公司">{{ detail.org_name || detail.org_id }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ detail.apply_user_name || detail.apply_user }}</el-descriptions-item>
        <el-descriptions-item label="申请日期">{{ fmtDate(detail.apply_date) }}</el-descriptions-item>
        <el-descriptions-item label="总金额"><span class="money">{{ fmtMoney(detail.total_amount) }}</span></el-descriptions-item>
        <el-descriptions-item label="预算项">{{ detail.budget_item || "-" }}</el-descriptions-item>
        <el-descriptions-item label="成本科目">{{ detail.cost_subject || "-" }}</el-descriptions-item>
        <el-descriptions-item label="合同编号" :span="2">{{ detail.contract_no || "-" }}</el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">采购明细</div>
      <el-table :data="detail.items || []" size="small" border>
        <el-table-column prop="asset_name" label="资产名称" min-width="140" />
        <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip />
        <el-table-column prop="num" label="数量" width="64" align="center" />
        <el-table-column label="单价" width="100" align="right">
          <template #default="{ row }">{{ fmtMoney(row.unit_price) }}</template>
        </el-table-column>
        <el-table-column label="金额" width="110" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.amount) }}</span></template>
        </el-table-column>
        <el-table-column label="用途" width="76" align="center">
          <template #default="{ row }">{{ PURPOSE[row.purpose] || "-" }}</template>
        </el-table-column>
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建采购申请" width="860px" destroy-on-close top="6vh">
      <el-form :model="form" label-width="86px">
        <el-row :gutter="14">
          <el-col :span="8">
            <el-form-item label="申请单号">
              <el-input v-model="form.apply_no" readonly placeholder="保存时自动生成">
                <template #append>
                  <el-button @click="refreshNo" :disabled="!formVisible">刷新</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="核算公司" required>
              <el-select v-model="form.org_id" filterable>
                <el-option v-for="o in orgs" :key="o.id" :label="o.org_name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="申请日期">
              <el-date-picker v-model="form.apply_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="供应商">
              <el-select v-model="form.supplier_id" filterable clearable>
                <el-option v-for="s in suppliers" :key="s.id" :label="s.supplier_name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8"><el-form-item label="预算项"><el-input v-model="form.budget_item" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="成本科目"><el-input v-model="form.cost_subject" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="合同编号"><el-input v-model="form.contract_no" /></el-form-item></el-col>
        </el-row>

        <div class="sec-title">采购明细（一单多明细）</div>
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
          <el-table-column label="规格" min-width="120">
            <template #default="{ row }"><el-input v-model="row.spec" size="small" /></template>
          </el-table-column>
          <el-table-column label="数量" width="90">
            <template #default="{ row }"><el-input-number v-model="row.num" :min="1" size="small" controls-position="right" /></template>
          </el-table-column>
          <el-table-column label="单价" width="130">
            <template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" :controls="false" size="small" style="width: 100%" /></template>
          </el-table-column>
          <el-table-column label="用途" width="110">
            <template #default="{ row }">
              <el-select v-model="row.purpose" size="small" clearable>
                <el-option v-for="(p, k) in PURPOSE" :key="k" :label="p" :value="Number(k)" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column width="60" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="form.items.splice($index, 1)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button class="mt-8" :icon="Plus" plain size="small" @click="form.items.push({ asset_name: '', category_id: null, spec: '', num: 1, unit_price: null, purpose: 1 })">
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
import { docApi, archiveApi, sysApi } from "../../api";
import { DOC_STATUS, fmtMoney, fmtDate, fmtDateTime, todayStr } from "../../utils/constants";
import { loadFlowEnabled } from "../../utils/approval";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";

const router = useRouter();
const PURPOSE = { 1: "办公", 2: "样板间", 3: "项目" };

const loading = ref(false);
const saving = ref(false);
const flowEnabled = ref(true);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null });

const orgs = ref([]);
const suppliers = ref([]);
const categories = ref([]);
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
    const res = await docApi.purchases(params);
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
  detail.value = await docApi.purchase(row.id);
  detailVisible.value = true;
}

// ---- 新建 ----
const formVisible = ref(false);
const form = reactive({
  apply_no: "",
  org_id: null, apply_date: "", budget_item: "", cost_subject: "",
  supplier_id: null, contract_no: "", remark: "", items: [],
});
function openCreate() {
  Object.assign(form, {
    apply_no: "",
    org_id: orgs.value[0]?.id ?? null, apply_date: todayStr(),
    budget_item: "", cost_subject: "", supplier_id: null, contract_no: "", remark: "",
    items: [{ asset_name: "", category_id: null, spec: "", num: 1, unit_price: null, purpose: 1 }],
  });
  formVisible.value = true;
  refreshNo();
}

// ---- 编号预览（自动生成，只读展示） ----
async function refreshNo() {
  try {
    const res = await docApi.nextDocNo("purchase");
    form.apply_no = res.next_no;
  } catch {
    form.apply_no = "";
  }
}
async function save(submit = false) {
  if (!form.org_id) return ElMessage.warning("请选择核算公司");
  const items = form.items.filter((i) => i.asset_name?.trim());
  if (!items.length) return ElMessage.warning("请至少填写一行采购明细");
  saving.value = true;
  try {
    const created = await docApi.createPurchase({ ...form, items });
    if (submit) {
      const res = await docApi.submit("purchase", created.id);
      ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
      formVisible.value = false;
      load();
      return;
    }
    ElMessage.success("采购申请已保存（草稿）");
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
    const res = await docApi.submit("purchase", row.id);
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
  await docApi.manualApprove("purchase", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，确认撤销？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("purchase", row.id);
  ElMessage.success("已撤销");
  load();
}
async function del(row) {
  try {
    await ElMessageBox.confirm("确认删除该草稿？", "删除", { type: "warning" });
  } catch {
    return;
  }
  await docApi.delPurchase(row.id);
  ElMessage.success("已删除");
  load();
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("purchase");
  const [os, ss, cs] = await Promise.allSettled([sysApi.orgs(), archiveApi.suppliers(), archiveApi.categories()]);
  if (os.status === "fulfilled") orgs.value = os.value.filter((o) => o.org_type <= 3);
  if (ss.status === "fulfilled") suppliers.value = ss.value;
  if (cs.status === "fulfilled") categories.value = cs.value;
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
