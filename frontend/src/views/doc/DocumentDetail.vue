<template>
  <div class="page" v-loading="loading">
    <div class="page__head">
      <div>
        <h1 class="page__title">
          {{ BIZ_LABEL[bizType] || "单据" }}
          <el-tag :type="DOC_STATUS[d.status]?.type || 'info'" style="margin-left: 8px">
            {{ DOC_STATUS[d.status]?.label || d.status }}
          </el-tag>
        </h1>
        <span class="page__sub">{{ d.no || "-" }}</span>
      </div>
      <div class="flex gap-8">
        <el-button @click="goBack">返回</el-button>
        <el-button v-if="d.wf_instance_id" type="primary" @click="pushSafe(router, `/doc/progress/${d.wf_instance_id}`)">
          查看审批进度
        </el-button>
      </div>
    </div>

    <template v-if="!missing">
    <div class="card">
      <div class="sec-title">基本信息</div>
      <div class="info-grid">
        <div v-for="f in fields" :key="f.label" class="info-item">
          <span class="info-item__label">{{ f.label }}</span>
          <span>{{ f.value }}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="sec-title">明细（{{ items.length }} 项）</div>
      <el-table v-if="cfg" :data="items" border size="small">
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column
          v-for="c in cfg.columns"
          :key="c.label"
          :label="c.label"
          :width="c.width"
          :min-width="c.minWidth"
          :align="c.align"
        >
          <template #default="{ row }">
            <span v-if="c.money">{{ fmtMoney(row[c.prop]) }}</span>
            <span v-else-if="c.fmt">{{ c.fmt(row[c.prop]) }}</span>
            <span v-else>{{ dash(row[c.prop]) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="card">
      <div class="sec-title">审批流程</div>
      <ApprovalFlowPanel :instance-id="d.wf_instance_id" />
    </div>
    </template>
    <el-empty v-else description="单据不存在或已被删除" :image-size="90">
      <el-button type="primary" @click="goBack">返回</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { docApi, assetApi, conApi } from "../../api";
import { DOC_STATUS, IN_TYPE, OUT_TYPE, DISPOSE_TYPE, fmtMoney, fmtDate, fmtDateTime } from "../../utils/constants";
import { pushSafe } from "../../utils/nav";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";

const route = useRoute();
const router = useRouter();
const bizType = route.params.bizType;
const docId = Number(route.params.id);

const BIZ_LABEL = {
  purchase: "采购申请", stock_in: "入库单", stock_out: "出库单", transfer: "调拨单", scrap: "报废单",
  borrow: "借用单", return: "归还单",
  con_purchase: "易耗品采购单", con_inbound: "易耗品入库单", con_issue: "易耗品领用单",
};
const PURPOSE = { 1: "办公", 2: "样板间", 3: "项目" };
const TRANSFER_TYPE = { 1: "仓库调拨", 2: "项目调拨", 3: "公司调拨", 4: "部门调拨" };
const dash = (v) => (v == null || v === "" ? "-" : v);

const CONFIG = {
  purchase: {
    fetch: (id) => docApi.purchase(id),
    no: (d) => d.apply_no,
    assetItems: false,
    fields: (d) => [
      { label: "申请日期", value: fmtDate(d.apply_date) },
      { label: "核算公司", value: dash(d.org_name) },
      { label: "申请人", value: dash(d.apply_user_name) },
      { label: "总金额", value: `¥ ${fmtMoney(d.total_amount)}` },
      { label: "预算项目", value: dash(d.budget_item) },
      { label: "成本科目", value: dash(d.cost_subject) },
      { label: "合同编号", value: dash(d.contract_no) },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "资产名称", prop: "asset_name", minWidth: 150 },
      { label: "规格", prop: "spec", minWidth: 120 },
      { label: "数量", prop: "num", width: 70, align: "center" },
      { label: "单价", prop: "unit_price", width: 110, money: true, align: "right" },
      { label: "金额", prop: "amount", width: 120, money: true, align: "right" },
      { label: "用途", prop: "purpose", width: 90, align: "center", fmt: (v) => PURPOSE[v] || "-" },
    ],
  },
  stock_in: {
    fetch: (id) => docApi.stockIn(id),
    no: (d) => d.in_no,
    assetItems: false,
    fields: (d) => [
      { label: "入库类型", value: IN_TYPE[d.in_type] || "-" },
      { label: "仓库", value: dash(d.warehouse_name) },
      { label: "入库日期", value: fmtDate(d.in_date) },
      { label: "总数量", value: dash(d.total_num) },
      { label: "总金额", value: `¥ ${fmtMoney(d.total_price)}` },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "资产名称", prop: "asset_name", minWidth: 150 },
      { label: "数量", prop: "num", width: 70, align: "center" },
      { label: "单价", prop: "unit_price", width: 110, money: true, align: "right" },
      { label: "金额", prop: "amount", width: 120, money: true, align: "right" },
    ],
  },
  stock_out: {
    fetch: (id) => docApi.stockOut(id),
    no: (d) => d.out_no,
    assetItems: true,
    fields: (d) => [
      { label: "出库类型", value: OUT_TYPE[d.out_type] || "-" },
      { label: "仓库", value: dash(d.warehouse_name) },
      { label: "领用人", value: dash(d.receive_user_name) },
      { label: "出库日期", value: fmtDate(d.out_date) },
      { label: "总数量", value: dash(d.total_num) },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "资产编码", prop: "asset_code", minWidth: 130 },
      { label: "资产名称", prop: "asset_name", minWidth: 150 },
      { label: "数量", prop: "num", width: 70, align: "center" },
      { label: "使用地点", prop: "use_location", minWidth: 140 },
    ],
  },
  transfer: {
    fetch: (id) => docApi.transfer(id),
    no: (d) => d.transfer_no,
    assetItems: true,
    fields: (d) => [
      { label: "调拨类型", value: TRANSFER_TYPE[d.transfer_type] || "-" },
      { label: "调出仓库", value: dash(d.out_warehouse_name) },
      { label: "调入仓库", value: dash(d.in_warehouse_name) },
      { label: "申请人", value: dash(d.apply_user_name) },
      { label: "调拨日期", value: fmtDate(d.transfer_date) },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "资产编码", prop: "asset_code", minWidth: 130 },
      { label: "资产名称", prop: "asset_name", minWidth: 150 },
      { label: "数量", prop: "num", width: 70, align: "center" },
    ],
  },
  scrap: {
    fetch: (id) => docApi.scrap(id),
    no: (d) => d.scrap_no,
    assetItems: true,
    fields: (d) => [
      { label: "处置方式", value: DISPOSE_TYPE[d.dispose_type] || "-" },
      { label: "申请人", value: dash(d.apply_user_name) },
      { label: "报废日期", value: fmtDate(d.scrap_date) },
      { label: "处置收入", value: `¥ ${fmtMoney(d.dispose_income)}` },
      { label: "损益", value: `¥ ${fmtMoney(d.profit_loss)}` },
      { label: "报废原因", value: dash(d.scrap_reason) },
    ],
    columns: [
      { label: "资产编码", prop: "asset_code", minWidth: 130 },
      { label: "资产名称", prop: "asset_name", minWidth: 150 },
      { label: "净值", prop: "net_value", width: 110, money: true, align: "right" },
      { label: "评估金额", prop: "evaluate_amount", width: 120, money: true, align: "right" },
    ],
  },
  borrow: {
    fetch: (id) => docApi.borrow(id),
    no: (d) => d.borrow_no,
    assetItems: true,
    fields: (d) => [
      { label: "申请人", value: dash(d.apply_user_name) },
      { label: "借用人", value: dash(d.borrow_user_name) },
      { label: "借用日期", value: fmtDate(d.borrow_date) },
      { label: "预计归还日期", value: fmtDate(d.expected_return_date) },
      { label: "核算公司", value: dash(d.org_name) },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "资产编码", prop: "asset_code", minWidth: 130 },
      { label: "资产名称", prop: "asset_name", minWidth: 150 },
      { label: "来源仓库", prop: "src_warehouse_name", minWidth: 130 },
      { label: "归还状态", prop: "return_status", width: 90, align: "center", fmt: (v) => ({ 0: "未归还", 1: "已归还" }[v] || "-") },
      { label: "归还日期", prop: "return_date", width: 110, align: "center", fmt: (v) => fmtDate(v) },
    ],
  },
  return: {
    fetch: (id) => docApi.returnDetail(id),
    no: (d) => d.return_no,
    assetItems: true,
    fields: (d) => [
      { label: "申请人", value: dash(d.apply_user_name) },
      { label: "归还日期", value: fmtDate(d.return_date) },
      { label: "核算公司", value: dash(d.org_name) },
      { label: "备注", value: dash(d.remark) },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "资产编码", prop: "asset_code", minWidth: 130 },
      { label: "资产名称", prop: "asset_name", minWidth: 150 },
      { label: "归还至仓库", prop: "target_warehouse_name", minWidth: 130 },
    ],
  },
  con_purchase: {
    fetch: (id) => conApi.purchase(id),
    no: (d) => d.purchase_no,
    assetItems: false,
    fields: (d) => [
      { label: "申请人", value: dash(d.apply_user_name) },
      { label: "申请日期", value: fmtDate(d.apply_date) },
      { label: "部门", value: dash(d.org_name) },
      { label: "总金额", value: `¥ ${fmtMoney(d.total_amount)}` },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "物料名称", prop: "item_name", minWidth: 150 },
      { label: "单位", prop: "item_unit", width: 70, align: "center" },
      { label: "数量", prop: "num", width: 80, align: "center" },
      { label: "单价", prop: "unit_price", width: 110, money: true, align: "right" },
      { label: "金额", prop: "amount", width: 120, money: true, align: "right" },
      { label: "已入库", prop: "inbound_num", width: 80, align: "center" },
      { label: "已领用", prop: "issued_num", width: 80, align: "center" },
    ],
  },
  con_inbound: {
    fetch: (id) => conApi.inbound(id),
    no: (d) => d.in_no,
    assetItems: false,
    fields: (d) => [
      { label: "仓库", value: dash(d.warehouse_name) },
      { label: "入库日期", value: fmtDate(d.in_date) },
      { label: "部门", value: dash(d.org_name) },
      { label: "总数量", value: dash(d.total_num) },
      { label: "总金额", value: `¥ ${fmtMoney(d.total_amount)}` },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "物料名称", prop: "item_name", minWidth: 150 },
      { label: "数量", prop: "num", width: 80, align: "center" },
      { label: "单价", prop: "unit_price", width: 110, money: true, align: "right" },
      { label: "金额", prop: "amount", width: 120, money: true, align: "right" },
    ],
  },
  con_issue: {
    fetch: (id) => conApi.issue(id),
    no: (d) => d.issue_no,
    assetItems: false,
    fields: (d) => [
      { label: "来源", value: dash(d.source_name) },
      { label: "仓库", value: dash(d.warehouse_name) },
      { label: "领用人", value: dash(d.receive_user_name) },
      { label: "领用日期", value: fmtDate(d.issue_date) },
      { label: "总数量", value: dash(d.total_num) },
      { label: "创建时间", value: fmtDateTime(d.create_time) },
    ],
    columns: [
      { label: "物料名称", prop: "item_name", minWidth: 150 },
      { label: "数量", prop: "num", width: 80, align: "center" },
      { label: "单价", prop: "unit_price", width: 110, money: true, align: "right" },
    ],
  },
};

const cfg = CONFIG[bizType];
const loading = ref(false);
const missing = ref(false);
const d = ref({});
const items = ref([]);
const fields = computed(() => (cfg ? cfg.fields(d.value) : []));

async function load() {
  if (!cfg || !Number.isFinite(docId)) {
    ElMessage.error("未知单据类型或单据ID");
    return;
  }
  loading.value = true;
  try {
    const data = await cfg.fetch(docId);
    d.value = data;
    let list = data.items || [];
    if (cfg.assetItems) {
      list = await Promise.all(
        list.map(async (i) => {
          try {
            const a = await assetApi.detail(i.asset_id);
            return { ...i, asset_code: a.asset_code, asset_name: a.asset_name };
          } catch {
            return { ...i, asset_code: `#${i.asset_id}`, asset_name: "-" };
          }
        })
      );
    }
    items.value = list;
  } catch (e) {
    if (e?.response?.status === 404) {
      missing.value = true;
      return;
    }
    ElMessage.error(e?.response?.data?.detail || "单据加载失败");
  } finally {
    loading.value = false;
  }
}

function goBack() {
  if (window.history.length > 1) router.back();
  else router.push("/doc/approval");
}

onMounted(load);
</script>

<style scoped>
.page { max-width: 1200px; width: 100%; margin: 0 auto; padding: 20px 32px 32px; overflow-y: auto; }
.page .card { padding: 16px 20px; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px 24px; }
.info-item { display: flex; align-items: baseline; gap: 8px; font-size: 13px; }
.info-item__label { color: #8a8f98; flex-shrink: 0; }
</style>
