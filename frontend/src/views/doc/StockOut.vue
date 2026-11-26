<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">出库管理</h1>
      <div class="flex gap-8">
        <el-button v-perm="'stockout:create'" type="primary" :icon="Plus" @click="openCreate">新建出库单</el-button>
      </div>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="出库单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="out_no" label="出库单号" width="150" fixed />
        <el-table-column label="仓库" width="130">
          <template #default="{ row }">{{ whName(row.warehouse_id) }}</template>
        </el-table-column>
        <el-table-column label="出库类型" width="100" align="center">
          <template #default="{ row }">{{ OUT_TYPE[row.out_type] || "-" }}</template>
        </el-table-column>
        <el-table-column label="领用人" width="90">
          <template #default="{ row }">{{ userName(row.receive_user) }}</template>
        </el-table-column>
        <el-table-column prop="out_date" label="出库日期" width="102" />
        <el-table-column prop="total_num" label="数量" width="70" align="right" />
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
        <span class="text-muted">共 {{ total }} 张出库单</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" size="600px" :title="`出库单 ${detail.out_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="仓库">{{ detail.warehouse_name || whName(detail.warehouse_id) }}</el-descriptions-item>
        <el-descriptions-item label="出库类型">{{ OUT_TYPE[detail.out_type] || "-" }}</el-descriptions-item>
        <el-descriptions-item label="领用人">{{ detail.receive_user_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="出库日期">{{ fmtDate(detail.out_date) }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ detail.total_num }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="DOC_STATUS[detail.status]?.type" size="small">{{ DOC_STATUS[detail.status]?.label }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">出库明细（审批通过后资产转为「领用中」）</div>
      <el-table :data="detailItems" size="small" border>
        <el-table-column prop="asset_code" label="资产编码" width="165" />
        <el-table-column prop="asset_name" label="资产名称" min-width="150" />
        <el-table-column prop="use_location" label="使用位置" min-width="130">
          <template #default="{ row }">{{ row.use_location || "-" }}</template>
        </el-table-column>
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建出库单" width="820px" destroy-on-close top="6vh">
      <el-form :model="form" label-width="86px">
        <el-row :gutter="14">
          <el-col :span="8">
            <el-form-item label="出库单号">
              <el-input v-model="form.out_no" readonly placeholder="保存时自动生成">
                <template #append>
                  <el-button @click="refreshNo" :disabled="!formVisible">刷新</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="出库仓库" required>
              <el-select v-model="form.warehouse_id" filterable @change="onWhChange">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="出库类型" required>
              <el-select v-model="form.out_type">
                <el-option v-for="(t, k) in OUT_TYPE" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="出库日期">
              <el-date-picker v-model="form.out_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="领用人" :required="form.out_type === 1">
              <el-select v-model="form.receive_user" filterable clearable>
                <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <div class="sec-title">选择在库资产（仅该仓库在库资产）</div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px">
          <el-button type="primary" plain :disabled="!form.warehouse_id" @click="openAssetSelect">选择资产</el-button>
          <span class="text-muted">已选 <b>{{ form.items.length }}</b> 项</span>
          <el-button v-if="form.items.length" link type="danger" size="small" @click="selectedAssetIds = []">清空</el-button>
        </div>

        <el-table v-if="form.items.length" :data="form.items" size="small" border class="mt-8">
          <el-table-column prop="asset_code" label="资产编码" width="150" />
          <el-table-column prop="asset_name" label="名称" min-width="120" show-overflow-tooltip />
          <el-table-column prop="org_name" label="公司" width="100" show-overflow-tooltip />
          <el-table-column label="状态" width="78" align="center">
            <template #default="{ row }"><el-tag size="small">{{ assetStatusName(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="使用位置" min-width="150">
            <template #default="{ row }">
              <el-input v-model="row.use_location" size="small" placeholder="如：售楼处-洽谈区" />
            </template>
          </el-table-column>
        </el-table>

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

    <!-- 资产选择弹窗（限在库 + 出库仓库） -->
    <AssetSelectDialog
      v-model="assetSelectVisible"
      title="选择出库资产（在库）"
      :preset="assetSelectPreset"
      :allow-statuses="[1]"
      :defaults="assetSelectDefaults"
      @confirm="onAssetConfirmed"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { docApi, archiveApi, sysApi, assetApi } from "../../api";
import AssetSelectDialog from "../../components/AssetSelectDialog.vue";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";
import { DOC_STATUS, OUT_TYPE, fmtMoney, fmtDate, fmtDateTime, todayStr, assetStatusName } from "../../utils/constants";
import { loadFlowEnabled } from "../../utils/approval";

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
const users = ref([]);
const whName = (id) => warehouses.value.find((w) => w.id === id)?.warehouse_name || id;
const userName = (id) => users.value.find((u) => u.id === id)?.real_name || id;

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    const res = await docApi.stockOuts(params);
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
const detailItems = ref([]);
async function openDetail(row) {
  detail.value = await docApi.stockOut(row.id);
  const items = detail.value.items || [];
  detailItems.value = await Promise.all(
    items.map(async (i) => {
      try {
        const a = await assetApi.detail(i.asset_id);
        return { ...i, asset_code: a.asset_code, asset_name: a.asset_name };
      } catch {
        return { ...i, asset_code: `#${i.asset_id}`, asset_name: "-" };
      }
    })
  );
  detailVisible.value = true;
}

// ---- 新建 ----
const formVisible = ref(false);
const form = reactive({ out_no: "", warehouse_id: null, out_type: 1, out_date: "", receive_user: null, remark: "", items: [] });
const inStockAssets = ref([]);
const selectedAssetIds = ref([]);

watch(selectedAssetIds, (ids) => {
  const map = new Map(inStockAssets.value.map((a) => [a.id, a]));
  form.items = ids
    .map((id) => map.get(id))
    .filter(Boolean)
    .map((a) => {
      const prev = form.items.find((i) => i.asset_id === a.id);
      return {
        asset_id: a.id,
        asset_code: a.asset_code,
        asset_name: a.asset_name,
        org_name: a.org_name || "",
        status: a.status,
        use_location: prev?.use_location || "",
      };
    });
});

// ---- 资产选择弹窗（限在库 + 出库仓库） ----
const assetSelectVisible = ref(false);
const assetSelectPreset = ref([]);
const assetSelectDefaults = ref({});
function openAssetSelect() {
  if (!form.warehouse_id) return ElMessage.warning("请先选择出库仓库");
  assetSelectPreset.value = form.items.map((i) => ({ id: i.asset_id, asset_code: i.asset_code, asset_name: i.asset_name, org_name: i.org_name, status: i.status }));
  assetSelectDefaults.value = { warehouse_id: form.warehouse_id, status: 1 };
  assetSelectVisible.value = true;
}
function onAssetConfirmed(assets) {
  const existing = new Set(inStockAssets.value.map((a) => a.id));
  const newOpts = assets.filter((a) => !existing.has(a.id));
  if (newOpts.length) inStockAssets.value = [...inStockAssets.value, ...newOpts];
  const selIds = new Set(selectedAssetIds.value);
  const newIds = assets.filter((a) => !selIds.has(a.id)).map((a) => a.id);
  if (newIds.length) selectedAssetIds.value = [...selectedAssetIds.value, ...newIds];
}
function onWhChange() {
  selectedAssetIds.value = [];
  inStockAssets.value = [];
}

function openCreate() {
  Object.assign(form, {
    out_no: "",
    warehouse_id: warehouses.value[0]?.id ?? null, out_type: 1,
    out_date: todayStr(), receive_user: null, remark: "", items: [],
  });
  selectedAssetIds.value = [];
  inStockAssets.value = [];
  formVisible.value = true;
  refreshNo();
}

// ---- 编号预览（自动生成，只读展示） ----
async function refreshNo() {
  try {
    const res = await docApi.nextDocNo("stock_out");
    form.out_no = res.next_no;
  } catch {
    form.out_no = "";
  }
}
async function save(submit = false) {
  if (!form.warehouse_id) return ElMessage.warning("请选择出库仓库");
  if (!form.items.length) return ElMessage.warning("请选择出库资产");
  if (form.out_type === 1 && !form.receive_user) return ElMessage.warning("领用出库必须指定领用人");
  saving.value = true;
  try {
    const payload = {
      warehouse_id: form.warehouse_id, out_type: form.out_type, out_date: form.out_date,
      receive_user: form.receive_user, remark: form.remark,
      items: form.items.map((i) => ({ asset_id: i.asset_id, use_location: i.use_location })),
    };
    const created = await docApi.createStockOut(payload);
    if (submit) {
      const res = await docApi.submit("stock_out", created.id);
      ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
      formVisible.value = false;
      load();
      if (res.wf_instance_id) router.push(`/doc/progress/${res.wf_instance_id}`);
      return;
    }
    ElMessage.success("出库单已保存（草稿）");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}
function openProgress(row) {
  router.push(`/doc/progress/${row.wf_instance_id}`);
}

const submitting = ref(false);
async function submit(row) {
  if (submitting.value) return;
  const tip = flowEnabled.value
    ? "提交后单据进入审批流并锁定资产，确认提交？"
    : "提交后单据待手动审批并锁定资产，确认提交？";
  try {
    await ElMessageBox.confirm(tip, "提交", { type: "warning" });
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const res = await docApi.submit("stock_out", row.id);
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
  await docApi.manualApprove("stock_out", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，确认撤销？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("stock_out", row.id);
  ElMessage.success("已撤销");
  load();
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("stock_out");
  const [ws, us] = await Promise.all([
    archiveApi.warehouses(),
    sysApi.users({ page: 1, page_size: 200 }),
  ]);
  warehouses.value = ws;
  users.value = us.records;
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
