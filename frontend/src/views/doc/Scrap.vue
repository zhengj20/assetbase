<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">报废处置</h1>
      <span class="page__sub">净值核销 · 变卖收入自动计损益</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="报废单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-perm="'scrap:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">新建报废单</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="scrap_no" label="报废单号" width="150" fixed />
        <el-table-column label="核算公司" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ orgName(row.org_id) }}</template>
        </el-table-column>
        <el-table-column prop="scrap_date" label="报废日期" width="102" />
        <el-table-column prop="scrap_reason" label="报废原因" min-width="120" show-overflow-tooltip />
        <el-table-column label="处置方式" width="90" align="center">
          <template #default="{ row }">{{ DISPOSE_TYPE[row.dispose_type] || "-" }}</template>
        </el-table-column>
        <el-table-column label="处置收入" width="110" align="right">
          <template #default="{ row }">{{ fmtMoney(row.dispose_income) }}</template>
        </el-table-column>
        <el-table-column label="损益" width="110" align="right">
          <template #default="{ row }">
            <span class="money">{{ fmtMoney(row.profit_loss) }}</span>
          </template>
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
        <span class="text-muted">共 {{ total }} 张报废单</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" size="620px" :title="`报废单 ${detail.scrap_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="核算公司">{{ orgName(detail.org_id) }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ detail.apply_user_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="报废日期">{{ fmtDate(detail.scrap_date) }}</el-descriptions-item>
        <el-descriptions-item label="处置方式">{{ DISPOSE_TYPE[detail.dispose_type] || "-" }}</el-descriptions-item>
        <el-descriptions-item label="处置收入">{{ fmtMoney(detail.dispose_income) }}</el-descriptions-item>
        <el-descriptions-item label="损益"><span class="money">{{ fmtMoney(detail.profit_loss) }}</span></el-descriptions-item>
        <el-descriptions-item label="报废原因" :span="2">{{ detail.scrap_reason || "-" }}</el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">报废明细</div>
      <el-table :data="detailItems" size="small" border>
        <el-table-column prop="asset_code" label="资产编码" width="165" />
        <el-table-column prop="asset_name" label="资产名称" min-width="150" />
        <el-table-column label="净值" width="110" align="right">
          <template #default="{ row }">{{ fmtMoney(row.net_value) }}</template>
        </el-table-column>
        <el-table-column label="评估残值" width="110" align="right">
          <template #default="{ row }">{{ fmtMoney(row.evaluate_amount) }}</template>
        </el-table-column>
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建报废处置单" width="760px" destroy-on-close top="6vh">
      <el-form :model="form" label-width="86px">
        <el-row :gutter="14">
          <el-col :span="8">
            <el-form-item label="报废单号">
              <el-input v-model="form.scrap_no" readonly placeholder="保存时自动生成">
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
            <el-form-item label="报废日期">
              <el-date-picker v-model="form.scrap_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="处置方式" required>
              <el-select v-model="form.dispose_type">
                <el-option v-for="(t, k) in DISPOSE_TYPE" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="报废原因">
              <el-input v-model="form.scrap_reason" maxlength="50" placeholder="如：设备老化无法维修" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="处置收入">
              <el-input-number v-model="form.dispose_income" :min="0" :precision="2" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="sec-title">选择报废资产（在库 / 领用中均可）</div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap">
          <el-button type="primary" plain @click="openAssetSelect">选择资产</el-button>
          <span class="text-muted">已选 <b>{{ form.items.length }}</b> 项</span>
          <el-select
            v-model="pickedGroup" placeholder="或：按组合包整包添加" clearable style="width: 260px" @change="onGroupPick"
          >
            <el-option v-for="g in groups" :key="g.id" :label="`${g.group_name}（${g.asset_count} 项）`" :value="g.id" />
          </el-select>
        </div>

        <el-table v-if="form.items.length" :data="form.items" size="small" border class="mt-8">
          <el-table-column prop="asset_code" label="资产编码" width="165" />
          <el-table-column prop="asset_name" label="资产名称" min-width="150" />
          <el-table-column label="评估残值" width="180">
            <template #default="{ row }">
              <el-input-number v-model="row.evaluate_amount" :min="0" :precision="2" :controls="false" size="small" style="width: 100%" />
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

    <!-- 资产选择弹窗 -->
    <AssetSelectDialog
      v-model="assetSelectVisible"
      title="选择报废资产"
      :preset="assetSelectPreset"
      :allow-statuses="[0, 1, 2, 3, 4]"
      @confirm="onAssetConfirmed"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { docApi, sysApi, assetApi, groupApi } from "../../api";
import AssetSelectDialog from "../../components/AssetSelectDialog.vue";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";
import { DOC_STATUS, DISPOSE_TYPE, fmtMoney, fmtDate, fmtDateTime, todayStr } from "../../utils/constants";
import { useRouter } from "vue-router";
import { loadFlowEnabled } from "../../utils/approval";

const router = useRouter();

const flowEnabled = ref(true);
const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null });

const orgs = ref([]);
const orgName = (id) => orgs.value.find((o) => o.id === id)?.org_name || (id ?? "-");

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    const res = await docApi.scraps(params);
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
  detail.value = await docApi.scrap(row.id);
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
const form = reactive({ scrap_no: "", org_id: null, scrap_date: "", scrap_reason: "", dispose_type: 1, dispose_income: null, remark: "", items: [] });
const selectedAssetIds = ref([]);
const assetOptions = ref([]);

// ---- 资产选择弹窗（按公司/项目/仓库/状态维度多选） ----
const assetSelectVisible = ref(false);
const assetSelectPreset = ref([]);
function openAssetSelect() {
  assetSelectPreset.value = form.items.map((i) => ({ id: i.asset_id, asset_code: i.asset_code, asset_name: i.asset_name }));
  assetSelectVisible.value = true;
}
function onAssetConfirmed(assets) {
  const existing = new Set(assetOptions.value.map((a) => a.id));
  const newOpts = assets
    .filter((a) => !existing.has(a.id))
    .map((a) => ({ id: a.id, asset_code: a.asset_code, asset_name: a.asset_name, net_value: a.net_value }));
  if (newOpts.length) assetOptions.value = [...assetOptions.value, ...newOpts];
  const selIds = new Set(selectedAssetIds.value);
  const newIds = assets.filter((a) => !selIds.has(a.id)).map((a) => a.id);
  if (newIds.length) {
    selectedAssetIds.value = [...selectedAssetIds.value, ...newIds];
    ElMessage.success(`已添加 ${newIds.length} 项资产`);
  }
}

// ---- 组合包整包添加（报废/变卖均可，方案 P1-4） ----
const groups = ref([]);
const pickedGroup = ref(null);
async function loadGroups() {
  try {
    const res = await groupApi.list({ page: 1, page_size: 100 });
    groups.value = (res.records || []).filter((g) => g.status === 1);
  } catch {
    groups.value = [];
  }
}
async function onGroupPick(gid) {
  if (!gid) return;
  const d = await groupApi.detail(gid);
  const assets = (d.assets || []).filter((a) => a.status !== 5 && a.status !== 6);
  const optIds = new Set(assetOptions.value.map((a) => a.id));
  const newOpts = assets
    .filter((a) => !optIds.has(a.id))
    .map((a) => ({ id: a.id, asset_code: a.asset_code, asset_name: a.asset_name }));
  if (newOpts.length) assetOptions.value = [...assetOptions.value, ...newOpts];
  const selIds = new Set(selectedAssetIds.value);
  const newIds = assets.filter((a) => !selIds.has(a.id)).map((a) => a.id);
  if (newIds.length) selectedAssetIds.value = [...selectedAssetIds.value, ...newIds];
  if (newIds.length) ElMessage.success(`已整包添加 ${newIds.length} 项资产`);
  else if (assets.length) ElMessage.warning("该包内资产均已报废/处置或已在列表中");
}

function openCreate() {
  Object.assign(form, {
    scrap_no: "",
    org_id: orgs.value[0]?.id ?? null, scrap_date: todayStr(),
    scrap_reason: "", dispose_type: 1, dispose_income: null, remark: "", items: [],
  });
  selectedAssetIds.value = [];
  assetOptions.value = [];
  formVisible.value = true;
  refreshNo();
}

// ---- 编号预览（自动生成，只读展示） ----
async function refreshNo() {
  try {
    const res = await docApi.nextDocNo("scrap");
    form.scrap_no = res.next_no;
  } catch {
    form.scrap_no = "";
  }
}
async function save(submit = false) {
  if (!form.org_id) return ElMessage.warning("请选择核算公司");
  const items = form.items.filter((i) => selectedAssetIds.value.includes(i.asset_id));
  if (!items.length) return ElMessage.warning("请选择报废资产");
  saving.value = true;
  try {
    const created = await docApi.createScrap({
      ...form,
      items: items.map((i) => ({ asset_id: i.asset_id, evaluate_amount: i.evaluate_amount })),
    });
    if (submit) {
      const res = await docApi.submit("scrap", created.id);
      ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批");
    } else {
      ElMessage.success("报废单已保存（草稿）");
    }
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

// 选中变化时同步明细行
watch(selectedAssetIds, (ids) => {
  const map = new Map(assetOptions.value.map((a) => [a.id, a]));
  form.items = ids
    .map((id) => map.get(id) || form.items.find((i) => i.asset_id === id))
    .filter(Boolean)
    .map((a) => {
      const prev = form.items.find((i) => i.asset_id === a.id);
      return {
        asset_id: a.id,
        asset_code: a.asset_code,
        asset_name: a.asset_name,
        evaluate_amount: prev?.evaluate_amount ?? a.evaluate_amount ?? null,
      };
    });
});

const submitting = ref(false);
async function submit(row) {
  if (submitting.value) return;
  try {
    const tip = flowEnabled.value
      ? "提交后单据进入审批流并锁定资产，确认提交？"
      : "提交后单据待手动审批，确认提交？";
    await ElMessageBox.confirm(tip, flowEnabled.value ? "提交审批" : "提交", { type: "warning" });
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const res = await docApi.submit("scrap", row.id);
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
  await docApi.manualApprove("scrap", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，确认撤销？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("scrap", row.id);
  ElMessage.success("已撤销");
  load();
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("scrap");
  try {
    const os = await sysApi.orgs();
    orgs.value = os.filter((o) => o.org_type <= 3 || o.is_accounting);
  } catch { /* 基础数据加载失败不阻塞列表 */ }
  loadGroups();
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
