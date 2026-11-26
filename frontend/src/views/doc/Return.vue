<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">归还管理</h1>
      <span class="page__sub">对「借用中」资产发起归还 · 走审批 · 通过后自动回原仓库，与借用单形成闭环</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="归还单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-perm="'return:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">发起归还</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="return_no" label="归还单号" width="150" fixed />
        <el-table-column label="申请人" width="110">
          <template #default="{ row }">{{ userName(row.apply_user) }}</template>
        </el-table-column>
        <el-table-column prop="return_date" label="归还日期" width="110" />
        <el-table-column label="备注" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="88" align="center">
          <template #default="{ row }">
            <el-tag :type="DOC_STATUS[row.status]?.type" size="small">{{ DOC_STATUS[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="150" :formatter="(_, __, v) => fmtDateTime(v)" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">明细</el-button>
            <el-button v-if="row.status === 0" link type="success" size="small" @click="submit(row)">{{ flowEnabled ? "提交审批" : "提交" }}</el-button>
            <el-button v-if="row.status === 1 && !flowEnabled" v-perm="'approval:approve'" link type="success" size="small" @click="manualApprove(row)">手动审批</el-button>
            <el-button v-if="row.status === 0 || row.status === 1" link type="danger" size="small" @click="cancel(row)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 张归还单</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" size="620px" :title="`归还单 ${detail.return_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="申请人">{{ detail.apply_user_name || userName(detail.apply_user) || "-" }}</el-descriptions-item>
        <el-descriptions-item label="归还日期">{{ fmtDate(detail.return_date) }}</el-descriptions-item>
        <el-descriptions-item label="资产数">{{ (detail.items || []).length }} 项</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="DOC_STATUS[detail.status]?.type" size="small">{{ DOC_STATUS[detail.status]?.label }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detail.remark || "-" }}</el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">归还明细</div>
      <el-table :data="detailItems" size="small" border>
        <el-table-column prop="asset_code" label="资产编码" width="150" />
        <el-table-column prop="asset_name" label="资产名称" min-width="120" show-overflow-tooltip />
        <el-table-column label="归还至仓库" width="120">
          <template #default="{ row }">{{ row.target_warehouse_name || "-" }}</template>
        </el-table-column>
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="发起归还" width="720px" destroy-on-close top="5vh">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="归还单号">
              <el-input v-model="form.return_no" readonly placeholder="保存时自动生成">
                <template #append>
                  <el-button @click="refreshNo" :disabled="!formVisible">刷新</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="归还日期">
              <el-date-picker v-model="form.return_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="sec-title mt-12">
          选择资产
          <span class="text-muted asset-hint">限「借用中」资产</span>
        </div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px">
          <el-button type="primary" plain @click="openAssetSelect">选择资产</el-button>
          <span class="text-muted">已选 <b>{{ selectedAssets.length }}</b> 项</span>
        </div>
        <el-table v-if="selectedAssets.length" :data="selectedAssets" size="small" border class="mt-8">
          <el-table-column prop="asset_code" label="资产编码" width="150" />
          <el-table-column prop="asset_name" label="名称" min-width="130" show-overflow-tooltip />
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }"><el-tag size="small">{{ assetStatusName(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="原值" width="90" align="right">
            <template #default="{ row }"><span class="num">{{ fmtMoney(row.price) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="64" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="selectedAssets.splice($index, 1)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-form-item label="备注" class="mt-12">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="归还说明（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button :loading="saving" @click="save(false)">保存草稿</el-button>
        <el-button type="primary" :loading="saving" @click="save(true)">发起审批</el-button>
      </template>
    </el-dialog>

    <!-- 资产选择弹窗（限借用中） -->
    <AssetSelectDialog
      v-model="assetSelectVisible"
      title="选择借用中的资产"
      :allow-statuses="[7]"
      :preset="assetSelectPreset"
      @confirm="onAssetConfirmed"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { docApi, assetApi, sysApi } from "../../api";
import AssetSelectDialog from "../../components/AssetSelectDialog.vue";
import { DOC_STATUS, fmtDate, fmtDateTime, todayStr, assetStatusName, fmtMoney } from "../../utils/constants";
import { loadFlowEnabled } from "../../utils/approval";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";

const flowEnabled = ref(true);
const loading = ref(false);
const saving = ref(false);
const submitting = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null });
const users = ref([]);

const userName = (id) => (id ? users.value.find((u) => u.id === id)?.real_name : "") || "-";

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    const res = await docApi.returns(params);
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
  detail.value = await docApi.returnDetail(row.id);
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
const form = reactive({
  return_no: "",
  return_date: "",
  remark: "",
});
const selectedAssets = ref([]);

async function refreshNo() {
  try {
    const res = await docApi.nextDocNo("return");
    form.return_no = res.next_no;
  } catch {
    form.return_no = "";
  }
}

// ---- 资产选择弹窗 ----
const assetSelectVisible = ref(false);
const assetSelectPreset = ref([]);
function openAssetSelect() {
  assetSelectPreset.value = selectedAssets.value;
  assetSelectVisible.value = true;
}
function onAssetConfirmed(assets) {
  const existing = new Set(selectedAssets.value.map((a) => a.id));
  const newOnes = assets.filter((a) => !existing.has(a.id));
  if (newOnes.length) selectedAssets.value = [...selectedAssets.value, ...newOnes];
}

function openCreate() {
  Object.assign(form, {
    return_no: "",
    return_date: todayStr(),
    remark: "",
  });
  selectedAssets.value = [];
  formVisible.value = true;
  refreshNo();
}
function save(submit = false) {
  if (!selectedAssets.value.length) return ElMessage.warning("请选择要归还的资产");
  saving.value = true;
  (async () => {
    try {
      const created = await docApi.createReturn({
        return_date: form.return_date || null,
        remark: form.remark || null,
        items: selectedAssets.value.map((a) => ({ asset_id: a.id })),
      });
      if (submit) {
        const res = await docApi.submit("return", created.id);
        ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
      } else {
        ElMessage.success("归还单已保存（草稿），编号自动生成");
      }
      formVisible.value = false;
      load();
    } finally {
      saving.value = false;
    }
  })();
}

async function submit(row) {
  if (submitting.value) return;
  try {
    const tip = flowEnabled.value
      ? `提交后单据进入审批流，审批通过后资产回库，确认提交「${row.return_no || row.id}」？`
      : `提交后单据待手动审批，确认提交「${row.return_no || row.id}」？`;
    await ElMessageBox.confirm(tip, flowEnabled.value ? "提交审批" : "提交", { type: "warning" });
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const res = await docApi.submit("return", row.id);
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
  await docApi.manualApprove("return", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，确认撤销？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("return", row.id);
  ElMessage.success("已撤销");
  load();
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("return");
  try {
    const us = await sysApi.users({ page: 1, page_size: 200 });
    users.value = (us.records || []).filter((u) => u.status === 1);
  } catch {
    users.value = [];
  }
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.asset-hint { font-size: 12px; font-weight: 400; margin-left: 8px; }
</style>