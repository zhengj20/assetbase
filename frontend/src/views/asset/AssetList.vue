<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">资产台账</h1>
      <div class="flex gap-8">
        <el-button v-perm="'asset:create'" :icon="UploadFilled" @click="fileInput?.click()" :loading="importing">批量导入</el-button>
        <el-button v-perm="'asset:create'" :icon="Document" @click="assetApi.importTemplate">下载模板</el-button>
        <el-button v-perm="'asset:export'" :icon="Download" @click="exportExcel">导出清单</el-button>
        <el-button v-perm="'asset:create'" type="primary" :icon="Plus" @click="openCreate">新建资产</el-button>
        <el-button
          v-perm="'asset:edit'"
          :disabled="!selectedRows.length"
          @click="openBatchUpdate"
        >批量变更（{{ selectedRows.length }}）</el-button>
        <el-button
          v-perm="'asset:export'"
          :icon="Printer"
          :disabled="!selectedRows.length"
          @click="batchPrint"
        >批量打印二维码（{{ selectedRows.length }}）</el-button>
        <input ref="fileInput" type="file" accept=".xlsx,.xlsm" style="display:none" @change="onImportFile" />
      </div>
    </div>

    <div class="card table-card">
      <!-- 筛选区 -->
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="名称/规格/品牌/位置" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-input v-model="q.asset_code" placeholder="资产编码前缀" clearable @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="资产状态" clearable @change="load">
          <el-option v-for="s in ASSET_STATUS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-tree-select
          v-model="q.category_id"
          :data="categoryTree"
          node-key="id"
          :props="{ label: 'category_name', children: 'children' }"
          placeholder="资产分类" clearable check-strictly @change="page = 1, load()"
        />
        <el-select v-model="q.org_id" placeholder="核算公司" clearable filterable @change="load">
          <el-option v-for="o in orgOptions" :key="o.id" :label="o.org_name" :value="o.id" />
        </el-select>
        <el-select v-model="q.project_id" placeholder="项目" clearable filterable @change="load">
          <el-option v-for="p in projects" :key="p.id" :label="p.org_name" :value="p.id" />
        </el-select>
        <el-select v-model="q.use_dept_id" placeholder="责任部门" clearable filterable @change="load">
          <el-option v-for="d in depts" :key="d.id" :label="d.org_name" :value="d.id" />
        </el-select>
        <el-select v-model="q.warehouse_id" placeholder="仓库" clearable filterable @change="load">
          <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
        </el-select>
        <el-select v-model="q.is_high_value" placeholder="高值资产" clearable @change="page = 1, load()">
          <el-option label="高值" :value="1" />
          <el-option label="普通" :value="0" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <!-- 表格（固定表头 + 横向滚动，列不换行） -->
      <el-table
        :data="rows" v-loading="loading" height="100%" class="flex-table"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="50" fixed />
        <el-table-column prop="asset_code" label="资产编码" width="175" fixed>
          <template #default="{ row }">
            <a class="code-link num" @click="openDetail(row)">{{ row.asset_code }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="asset_name" label="资产名称" min-width="190" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="110" />
        <el-table-column prop="spec" label="规格" min-width="150" show-overflow-tooltip />
        <el-table-column prop="brand" label="品牌" width="90" />
        <el-table-column label="状态" width="86" align="center">
          <template #default="{ row }">
            <span class="st" :class="`st--${row.status}`">{{ assetStatusName(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="高值" width="60" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_high_value" type="warning" size="small" effect="plain">高</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="原值" width="110" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.price) }}</span></template>
        </el-table-column>
        <el-table-column label="净值" width="110" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.net_value) }}</span></template>
        </el-table-column>
        <el-table-column prop="buy_date" label="购置日期" width="102" />
        <el-table-column prop="org_name" label="核算公司" width="130" show-overflow-tooltip />
        <el-table-column prop="warehouse_name" label="仓库" width="110" show-overflow-tooltip />
        <el-table-column label="位置" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.office_name || row.project_name || row.space_name || "-" }}</template>
        </el-table-column>
        <el-table-column prop="use_user_name" label="责任人" width="84" />
        <el-table-column prop="use_dept_name" label="责任部门" width="120" show-overflow-tooltip />
        <el-table-column prop="create_time" label="建档时间" width="150" :formatter="(_, __, v) => fmtDateTime(v)" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <el-button v-perm="'asset:edit'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 5 || row.status === 6" v-perm="'asset:repair'" link type="warning" size="small" @click="repairAsset(row)">报修</el-button>
            <el-button v-if="row.status === 3" v-perm="'asset:repair'" link type="success" size="small" @click="repairDoneAsset(row)">完成维修</el-button>
            <el-button v-perm="'asset:delete'" link type="danger" size="small" @click="delAsset(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页（列表外常显） -->
      <div class="pager">
        <span class="text-muted">共 {{ total }} 项资产</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="sizes, prev, pager, next, jumper"
          background
          @current-change="load"
          @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" size="560px" :title="detail.asset_name || '资产详情'">
      <template #header>
        <div>
          <div style="font-size: 16px">{{ detail.asset_name }}</div>
          <div class="num" style="font-size: 12px; color: var(--gold-deep)">{{ detail.asset_code }}</div>
        </div>
      </template>
      <el-descriptions :column="2" border size="small" class="mt-8">
        <el-descriptions-item label="分类">{{ detail.category_name || detail.category_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <span class="st" :class="`st--${detail.status}`">{{ assetStatusName(detail.status) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="规格">{{ detail.spec || "-" }}</el-descriptions-item>
        <el-descriptions-item label="品牌">{{ detail.brand || "-" }}</el-descriptions-item>
        <el-descriptions-item label="原值"><span class="money">{{ fmtMoney(detail.price) }}</span></el-descriptions-item>
        <el-descriptions-item label="净值"><span class="num">{{ fmtMoney(detail.net_value) }}</span></el-descriptions-item>
        <el-descriptions-item label="购置日期">{{ fmtDate(detail.buy_date) }}</el-descriptions-item>
        <el-descriptions-item label="保修到期">{{ fmtDate(detail.warranty_end) }}</el-descriptions-item>
        <el-descriptions-item label="核算公司" :span="2">{{ detail.org_name || detail.org_id }}</el-descriptions-item>
        <el-descriptions-item label="位置" :span="2">
          {{ detail.office_name || detail.project_name || detail.space_name || detail.warehouse_name || detail.location_detail || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="责任人">
          {{ users.find((u) => u.id === detail.use_user_id)?.real_name || detail.use_user_name || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="责任部门">
          {{ allOrgs.find((o) => o.id === detail.use_dept_id)?.org_name || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="二维码" :span="2">
          <div class="qr-box">
            <img v-if="detailQr" :src="detailQr" alt="资产二维码" class="qr-img" />
            <div v-if="detail.qrcode" class="qr-code num">{{ detail.qrcode }}</div>
            <div class="flex gap-8 qr-actions">
              <el-button v-perm="'asset:export'" link type="primary" size="small" :disabled="!detailQr" @click="printSingle">打印标签</el-button>
              <el-button v-perm="'asset:edit'" link type="primary" size="small" @click="reprint">补打新码</el-button>
            </div>
          </div>
        </el-descriptions-item>
      </el-descriptions>

      <div class="sec-title mt-12">资产图片</div>
      <div class="img-toolbar">
        <el-button v-perm="'asset:edit'" size="small" :icon="Upload" :loading="imgUploading" @click="imgFileInput?.click()">上传图片</el-button>
        <span class="text-muted">支持 jpg/png/webp/gif · 服务端自动压缩</span>
        <input ref="imgFileInput" type="file" accept="image/*" multiple style="display:none" @change="onUploadImages" />
      </div>
      <div v-if="images.length" class="img-grid">
        <div v-for="im in images" :key="im.id" class="img-item">
          <el-image
            :src="im.image_url"
            :preview-src-list="images.map((x) => x.image_url)"
            fit="cover" class="img-thumb" :preview-teleported="true"
          />
          <div class="img-item__bar">
            <span class="text-muted">{{ fmtDate(im.upload_time) }}</span>
            <el-button v-perm="'asset:edit'" link type="danger" size="small" @click="delImage(im)">删除</el-button>
          </div>
        </div>
      </div>
      <div v-else class="empty-hint">暂无图片，可上传资产实拍图</div>

      <div class="sec-title mt-12">履历时间线（只增不改）</div>
      <el-timeline v-if="logs.length">
        <el-timeline-item
          v-for="log in logs"
          :key="log.id"
          :timestamp="fmtDateTime(log.operate_time)"
          :type="logColors[log.action_type] || 'info'"
        >
          <b>{{ actionName(log.action_type) }}</b>
          <span class="text-muted" v-if="log.biz_type">
            · {{ log.biz_type }} #{{ log.biz_id }}
          </span>
        </el-timeline-item>
      </el-timeline>
      <div v-else class="empty-hint">暂无履历记录</div>
    </el-drawer>

    <!-- 新建/编辑 -->
    <el-dialog v-model="formVisible" :title="editing ? '编辑资产' : '新建资产'" width="680px" destroy-on-close>
      <el-form :model="form" label-width="92px" size="default">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="资产名称" required>
              <el-input v-model="form.asset_name" maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产分类" required>
              <el-tree-select
                v-model="form.category_id" :data="categoryTree" node-key="id"
                :props="{ label: 'category_name', children: 'children' }" check-strictly
              />
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="规格"><el-input v-model="form.spec" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="品牌"><el-input v-model="form.brand" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="核算公司" required>
              <el-select v-model="form.org_id" filterable>
                <el-option v-for="o in orgOptions" :key="o.id" :label="o.org_name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="原值（元）">
              <el-input-number v-model="form.price" :min="0" :precision="2" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="购置日期">
              <el-date-picker v-model="form.buy_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保修到期">
              <el-date-picker v-model="form.warranty_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="位置类型">
              <el-radio-group v-model="form.loc_type">
                <el-radio value="project">项目</el-radio>
                <el-radio value="office">办公地点</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col v-if="form.loc_type === 'project'" :span="12">
            <el-form-item label="项目" required>
              <el-select v-model="form.project_id" filterable placeholder="选择项目">
                <el-option v-for="p in formProjects" :key="p.id" :label="p.org_name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-else :span="12">
            <el-form-item label="办公地点" required>
              <el-select v-model="form.office_id" filterable placeholder="选择办公地点">
                <el-option v-for="o in offices" :key="o.id" :label="o.office_name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="责任人">
              <el-select v-model="form.use_user_id" clearable filterable placeholder="选择责任人">
                <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="责任部门">
              <el-select v-model="form.use_dept_id" clearable filterable placeholder="选择责任部门">
                <el-option v-for="d in depts" :key="d.id" :label="d.org_name" :value="d.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="详细位置">
              <el-input v-model="form.location_detail" placeholder="选填，如：售楼处-洽谈区" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="高值资产">
              <el-switch v-model="form.is_high_value" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="可复用标记">
              <el-switch v-model="form.is_reusable" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量变更对话框 -->
    <el-dialog v-model="batchUpdateVisible" title="批量变更资产信息" width="600px" destroy-on-close>
      <el-alert type="info" :closable="false" class="mb-12">
        已选择 <b>{{ selectedRows.length }}</b> 项资产，仅填写需要变更的字段（留空的字段不变更）。
      </el-alert>
      <el-form :model="batchForm" label-width="100px">
        <el-form-item label="责任人">
          <el-select v-model="batchForm.use_user_id" filterable clearable placeholder="不变更">
            <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="责任部门">
          <el-select v-model="batchForm.use_dept_id" filterable clearable placeholder="不变更">
            <el-option v-for="d in depts" :key="d.id" :label="d.org_name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所在仓库">
          <el-select v-model="batchForm.warehouse_id" filterable clearable placeholder="不变更">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="batchForm.project_id" filterable clearable placeholder="不变更">
            <el-option v-for="p in projects" :key="p.id" :label="p.org_name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所在空间">
          <el-tree-select
            v-model="batchForm.space_id"
            :data="spaceTree"
            node-key="id"
            :props="{ label: 'space_name', children: 'children' }"
            check-strictly
            clearable
            placeholder="不变更"
          />
        </el-form-item>
        <el-form-item label="详细位置">
          <el-input v-model="batchForm.location_detail" placeholder="不变更" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchUpdateVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchUpdating" @click="saveBatchUpdate">确认变更</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Download, Plus, UploadFilled, Document, Printer, Upload } from "@element-plus/icons-vue";
import QRCode from "qrcode";
import { assetApi, archiveApi, sysApi, download } from "../../api";
import { ASSET_STATUS, assetStatusName, fmtMoney, fmtDate, fmtDateTime, todayStr } from "../../utils/constants";

const route = useRoute();
const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({
  keyword: "", asset_code: "", status: null, category_id: null,
  org_id: null, project_id: null, use_dept_id: null,
  warehouse_id: null, is_high_value: null,
});

const categories = ref([]);
const warehouses = ref([]);
const orgOptions = ref([]);
const allOrgs = ref([]);
const users = ref([]);
const offices = ref([]);
const spaces = ref([]);
const projects = computed(() => allOrgs.value.filter((o) => o.org_type === 3));
const depts = computed(() => allOrgs.value.filter((o) => o.org_type === 4));

// 项目空间全部关闭（清盘）的项目：新建/编辑资产时不可再选择
const closedProjectIds = computed(() => {
  const roots = spaces.value.filter((s) => !s.parent_id || s.parent_id === 0);
  const byProject = {};
  roots.forEach((s) => {
    (byProject[s.project_id] = byProject[s.project_id] || []).push(s.space_status);
  });
  const set = new Set();
  Object.entries(byProject).forEach(([pid, statuses]) => {
    if (statuses.every((st) => st !== 1)) set.add(Number(pid));
  });
  return set;
});
const formProjects = computed(() => projects.value.filter((o) => !closedProjectIds.value.has(o.id)));

const categoryTree = computed(() => {
  const roots = categories.value.filter((c) => !c.parent_id || c.parent_id === 0);
  return roots.map((r) => ({
    ...r,
    children: categories.value.filter((c) => c.parent_id === r.id),
  }));
});

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    Object.entries(q).forEach(([k, v]) => {
      if (v !== null && v !== "" && v !== undefined) params[k] = v;
    });
    const res = await assetApi.list(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}

function reset() {
  Object.assign(q, {
    keyword: "", asset_code: "", status: null, category_id: null,
    org_id: null, project_id: null, use_dept_id: null,
    warehouse_id: null, is_high_value: null,
  });
  page.value = 1;
  load();
}

async function exportExcel() {
  const params = {};
  Object.entries(q).forEach(([k, v]) => {
    if (v !== null && v !== "" && v !== undefined) params[k] = v;
  });
  const qs = new URLSearchParams(params).toString();
  await download(`/assets/export${qs ? `?${qs}` : ""}`, `资产清单_${todayStr()}.xlsx`);
}

// ---- 批量导入 ----
const fileInput = ref();
const importing = ref(false);
async function onImportFile(e) {
  const file = e.target.files?.[0];
  e.target.value = "";
  if (!file) return;
  importing.value = true;
  try {
    const res = await assetApi.importFile(file);
    if (res.ok === 0) {
      ElMessage.warning(`导入失败：${res.errors?.[0]?.msg || "无有效数据行"}`);
    } else {
      ElMessage.success(`导入完成：成功 ${res.ok} 条，失败 ${res.failed} 条`);
    }
    if (res.failed > 0) {
      const lines = (res.errors || []).map((x) => `第 ${x.row} 行：${x.msg}`).join("\n");
      ElMessageBox.alert(`<div style="white-space:pre-line;max-height:400px;overflow:auto">${lines}</div>`, "以下行导入失败", {
        dangerouslyUseHTMLString: true,
        confirmButtonText: "知道了",
      });
    }
    load();
  } finally {
    importing.value = false;
  }
}

// ---- 详情 ----
const detailVisible = ref(false);
const detail = ref({});
const detailQr = ref("");
const logs = ref([]);
const logColors = { 1: "primary", 2: "success", 3: "warning", 4: "primary", 5: "danger", 6: "info" };
const LOG_NAMES = { 1: "建档入库", 2: "修改", 3: "领用", 4: "归还", 5: "调拨", 6: "盘点", 7: "折旧", 8: "报废处置" };
const actionName = (t) => LOG_NAMES[t] || `操作#${t}`;

async function openDetail(row) {
  detail.value = row;
  detailQr.value = "";
  images.value = [];
  detailVisible.value = true;
  const [d, lg] = await Promise.all([assetApi.detail(row.id), assetApi.logs(row.id)]);
  detail.value = { ...row, ...d };
  logs.value = lg;
  if (detail.value.qrcode) {
    detailQr.value = await QRCode.toDataURL(detail.value.qrcode, { width: 160, margin: 1, errorCorrectionLevel: "M" });
  }
  loadImages(row.id);
}

// ---- 资产图片 ----
const images = ref([]);
const imgUploading = ref(false);
const imgFileInput = ref();

async function loadImages(assetId) {
  try {
    images.value = await assetApi.images(assetId);
  } catch {
    images.value = [];
  }
}

async function onUploadImages(e) {
  const files = Array.from(e.target.files || []);
  e.target.value = "";
  if (!files.length) return;
  imgUploading.value = true;
  try {
    for (const f of files) {
      await assetApi.uploadImage(detail.value.id, f);
    }
    ElMessage.success(`已上传 ${files.length} 张图片（已自动压缩）`);
    await loadImages(detail.value.id);
  } finally {
    imgUploading.value = false;
  }
}

async function delImage(im) {
  try {
    await ElMessageBox.confirm("删除后不可恢复，确认删除该图片？", "删除图片", { type: "warning" });
  } catch {
    return;
  }
  await assetApi.delImage(detail.value.id, im.id);
  ElMessage.success("已删除");
  await loadImages(detail.value.id);
}

async function reprint() {
  try {
    await ElMessageBox.confirm("补打后旧码作废，将生成新二维码绑定本资产，确认继续？", "补打标签", { type: "warning" });
  } catch {
    return;
  }
  await assetApi.reprint(detail.value.id);
  ElMessage.success("已生成新标签码");
  openDetail({ ...detail.value });
}

// ---- 二维码打印 ----
const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function buildPrintWindow(items) {
  const rowsHtml = items
    .map(
      (it) => `<div class="card">
        <img src="${it.qr}" alt="QR" />
        <div class="code">${escapeHtml(it.code)}</div>
        <div class="name">${escapeHtml(it.name)}</div>
        <div class="spec">${escapeHtml(it.spec)}</div>
      </div>`
    )
    .join("");
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>打印资产二维码</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, "Microsoft YaHei", sans-serif; color: #1a1a1a; }
    .toolbar { text-align: center; padding: 14px; border-bottom: 1px solid #eee; }
    .toolbar button { padding: 8px 22px; font-size: 14px; cursor: pointer; margin: 0 6px; border: 1px solid #d0d0d0; background: #fff; border-radius: 6px; }
    .toolbar button.primary { background: #2b6be4; color: #fff; border-color: #2b6be4; }
    .head { text-align: center; padding: 14px; font-size: 15px; font-weight: 600; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 14px; }
    .card { border: 1px solid #b8b8b8; border-radius: 8px; padding: 10px; text-align: center; break-inside: avoid; }
    .card img { width: 132px; height: 132px; }
    .code { font-size: 13px; font-weight: 600; margin-top: 6px; }
    .name { font-size: 12px; margin-top: 2px; word-break: break-all; }
    .spec { font-size: 11px; color: #666; margin-top: 2px; word-break: break-all; }
    @media print { .noprint { display: none; } .grid { padding: 0; gap: 8px; } }
  </style></head>
  <body>
    <div class="toolbar noprint">
      <button class="primary" onclick="window.print()">打印</button>
      <button onclick="window.close()">关闭</button>
    </div>
    <div class="head">资产二维码标签（共 ${items.length} 项）</div>
    <div class="grid">${rowsHtml}</div>
    <script>window.addEventListener('load', function(){ setTimeout(function(){ window.print(); }, 350); });<\/script>
  </body></html>`;
  const win = window.open("", "_blank", "width=900,height=700");
  if (!win) return false;
  win.document.open();
  win.document.write(html);
  win.document.close();
  return true;
}

async function printSingle() {
  if (!detail.value.qrcode) return;
  const qr = await QRCode.toDataURL(detail.value.qrcode, { width: 160, margin: 0.5, errorCorrectionLevel: "M" });
  const ok = buildPrintWindow([{ code: detail.value.asset_code, name: detail.value.asset_name, spec: detail.value.spec || "", qr }]);
  if (!ok) ElMessage.warning("浏览器拦截了弹窗，请允许弹窗后重试");
}

async function batchPrint() {
  const assets = selectedRows.value.filter((r) => r.qrcode);
  if (!assets.length) return ElMessage.warning("所选资产没有可打印的二维码");
  const items = await Promise.all(
    assets.map(async (a) => ({
      code: a.asset_code,
      name: a.asset_name,
      spec: a.spec || "",
      qr: await QRCode.toDataURL(a.qrcode, { width: 160, margin: 0.5, errorCorrectionLevel: "M" }),
    }))
  );
  const ok = buildPrintWindow(items);
  if (!ok) ElMessage.warning("浏览器拦截了弹窗，请允许弹窗后重试");
  else ElMessage.success(`已生成 ${items.length} 张二维码标签`);
}

// ---- 新建/编辑 ----
const formVisible = ref(false);
const editing = ref(null);
const form = reactive({
  asset_name: "", category_id: null, spec: "", brand: "", org_id: null,
  price: null, buy_date: "", warranty_end: "",
  loc_type: "project", project_id: null, office_id: null, location_detail: "",
  use_user_id: null, use_dept_id: null,
  is_high_value: false, is_reusable: false, remark: "",
});

function openCreate() {
  editing.value = null;
  Object.assign(form, {
    asset_name: "", category_id: null, spec: "", brand: "", org_id: orgOptions.value[0]?.id ?? null,
    price: null, buy_date: "", warranty_end: "",
    loc_type: "project", project_id: null, office_id: null, location_detail: "",
    use_user_id: null, use_dept_id: null,
    is_high_value: false, is_reusable: false, remark: "",
  });
  formVisible.value = true;
}

async function openEdit(row) {
  let d;
  try {
    d = await assetApi.detail(row.id);
  } catch {
    return;
  }
  editing.value = row;
  Object.assign(form, {
    asset_name: d.asset_name, category_id: d.category_id, spec: d.spec, brand: d.brand,
    org_id: d.org_id, price: d.price != null ? Number(d.price) : null,
    buy_date: d.buy_date || "", warranty_end: d.warranty_end || "",
    loc_type: d.office_id ? "office" : "project",
    project_id: d.project_id, office_id: d.office_id,
    location_detail: d.location_detail || "",
    use_user_id: d.use_user_id, use_dept_id: d.use_dept_id,
    is_high_value: !!d.is_high_value, is_reusable: !!d.is_reusable, remark: "",
  });
  formVisible.value = true;
}

async function delAsset(row) {
  try {
    await ElMessageBox.confirm(`删除后不可恢复，确认删除资产「${row.asset_name}」？`, "删除资产", { type: "warning" });
  } catch {
    return;
  }
  await assetApi.remove(row.id);
  ElMessage.success("资产已删除");
  load();
}

// ---- 维修流程（已报废/已处置 → 维修中 → 恢复原状态）----
async function repairAsset(row) {
  let note = "";
  try {
    ({ value: note } = await ElMessageBox.prompt("维修说明（可留空）", `报修「${row.asset_name}」`, {
      inputType: "textarea",
      inputValidator: (v) => (v || "").length <= 500,
    }));
  } catch {
    return;
  }
  await assetApi.repair(row.id, { note: note || null });
  ElMessage.success("已登记维修，状态变更为「维修中」");
  load();
}

async function repairDoneAsset(row) {
  try {
    await ElMessageBox.confirm("确认维修完成？资产将恢复维修前状态。", "完成维修", { type: "success" });
  } catch {
    return;
  }
  await assetApi.repairDone(row.id);
  ElMessage.success("维修完成");
  load();
}

function buildPayload() {
  const { loc_type, ...rest } = form;
  return {
    ...rest,
    project_id: loc_type === "project" ? form.project_id : null,
    office_id: loc_type === "office" ? form.office_id : null,
  };
}

async function save() {
  if (!form.asset_name || !form.category_id || !form.org_id) return ElMessage.warning("请填写名称、分类与核算公司");
  if (form.loc_type === "project" && !form.project_id) return ElMessage.warning("请选择项目");
  if (form.loc_type === "office" && !form.office_id) return ElMessage.warning("请选择办公地点");
  saving.value = true;
  try {
    const payload = buildPayload();
    if (editing.value) {
      await assetApi.update(editing.value.id, payload);
      ElMessage.success("资产已更新");
    } else {
      await assetApi.create(payload);
      ElMessage.success("资产已建档");
    }
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

// ---- 批量变更 ----
const selectedRows = ref([]);
const batchUpdateVisible = ref(false);
const batchUpdating = ref(false);
const batchForm = reactive({
  use_user_id: null,
  use_dept_id: null,
  warehouse_id: null,
  project_id: null,
  space_id: null,
  location_detail: null,
});

const spaceTree = computed(() => {
  const roots = spaces.value.filter((s) => !s.parent_id || s.parent_id === 0);
  const buildTree = (parentId) => {
    const children = spaces.value.filter((s) => s.parent_id === parentId);
    return children.map((c) => ({
      ...c,
      children: buildTree(c.id),
    }));
  };
  return roots.map((r) => ({
    ...r,
    children: buildTree(r.id),
  }));
});

function onSelectionChange(selection) {
  selectedRows.value = selection;
}

function openBatchUpdate() {
  if (!selectedRows.value.length) return ElMessage.warning("请先选择要变更的资产");
  // 重置表单
  Object.assign(batchForm, {
    use_user_id: null,
    use_dept_id: null,
    warehouse_id: null,
    project_id: null,
    space_id: null,
    location_detail: null,
  });
  batchUpdateVisible.value = true;
}

async function saveBatchUpdate() {
  // 检查是否至少填写了一项
  const hasChange = Object.values(batchForm).some((v) => v !== null && v !== "");
  if (!hasChange) return ElMessage.warning("请至少选择一项要变更的字段");
  
  batchUpdating.value = true;
  try {
    const assetIds = selectedRows.value.map((r) => r.id);
    const payload = { asset_ids: assetIds };
    // 只传非空字段
    Object.entries(batchForm).forEach(([k, v]) => {
      if (v !== null && v !== "") payload[k] = v;
    });
    
    const res = await assetApi.batchUpdate(payload);
    ElMessage.success(`批量变更完成，共更新 ${res.updated} 项资产`);
    batchUpdateVisible.value = false;
    selectedRows.value = [];
    load();
  } finally {
    batchUpdating.value = false;
  }
}

onMounted(async () => {
  const [cats, whs, orgs, userList, officeList, sps] = await Promise.all([
    archiveApi.categories(), archiveApi.warehouses(), sysApi.orgs(),
    sysApi.users({ page: 1, page_size: 200 }), archiveApi.offices(), archiveApi.spaces({}),
  ]);
  categories.value = cats;
  warehouses.value = whs;
  allOrgs.value = orgs;
  orgOptions.value = orgs.filter((o) => o.org_type <= 3 || o.is_accounting);
  users.value = userList.records || [];
  offices.value = officeList;
  spaces.value = sps || [];
  load();

  // 顶栏搜索跳转定位：支持跨页定位
  if (route.query.focus) {
    const focusId = Number(route.query.focus);
    // 先在当前页查找
    let row = rows.value.find((r) => r.id === focusId);
    if (!row) {
      // 如果当前页没有，通过编码搜索定位
      try {
        const res = await assetApi.list({ page: 1, page_size: 1, asset_code: route.query.focus });
        if (res.records && res.records.length > 0 && res.records[0].id === focusId) {
          row = res.records[0];
        }
      } catch {
        // 忽略错误
      }
    }
    if (row) openDetail(row);
  }
});
</script>

<style scoped>
.table-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.flex-table { flex: 1; min-height: 0; }
.code-link { color: var(--brand); cursor: pointer; }
.code-link:hover { text-decoration: underline; }
.ml-8 { margin-left: 8px; }
.qr-box { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.qr-img { width: 128px; height: 128px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; padding: 6px; background: #fff; }
.qr-code { font-size: 13px; color: var(--el-text-color-regular); word-break: break-all; }
.qr-actions { width: 100%; }
.img-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.img-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.img-item { border: 1px solid var(--el-border-color-lighter); border-radius: 8px; overflow: hidden; }
.img-thumb { width: 100%; height: 108px; display: block; background: var(--el-fill-color-lighter); }
.img-item__bar { display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; font-size: 12px; }
</style>
