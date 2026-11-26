<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">组合包</h1>
      <span class="page__sub">软装包/成套资产整包管理 · 建包 / 拆包 / 合包 / 整包调拨</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="组合包名称" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">新建组合包</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="group_name" label="组合包名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="资产数" width="80" align="center">
          <template #default="{ row }"><el-tag size="small">{{ row.asset_count }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="asset_names" label="包含资产" min-width="260" show-overflow-tooltip class-name="text-muted" />
        <el-table-column label="包总价" width="130" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.total_price) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? "使用中" : "已解散" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">{{ fmtDateTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">明细</el-button>
            <el-button v-if="row.status === 1" link type="warning" size="small" @click="openAdjust(row)">拆/合包</el-button>
            <el-button v-if="row.status === 1" link type="danger" size="small" @click="dissolve(row)">解散</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 个组合包</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 新建 -->
    <el-dialog v-model="createVisible" title="新建组合包" width="680px" destroy-on-close top="8vh">
      <el-form label-width="86px">
        <el-form-item label="包名称" required>
          <el-input v-model="createForm.group_name" placeholder="如：XX项目售楼处软装包" />
        </el-form-item>
        <el-form-item label="包含资产" required>
      <div style="width: 100%">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px">
          <el-button type="primary" plain @click="openAssetSelect">选择资产</el-button>
          <span class="text-muted">已选 <b>{{ createSelected.length }}</b> 项</span>
          <el-button v-if="createSelected.length" link type="danger" size="small" @click="createSelected = []">清空</el-button>
        </div>
        <el-table v-if="createSelected.length" :data="createSelected" size="small" border max-height="240">
          <el-table-column prop="asset_code" label="资产编码" width="140" />
          <el-table-column prop="asset_name" label="名称" min-width="110" show-overflow-tooltip />
          <el-table-column prop="category_name" label="分类" width="90" show-overflow-tooltip />
          <el-table-column prop="org_name" label="公司" width="100" show-overflow-tooltip />
          <el-table-column prop="warehouse_name" label="仓库" width="90" show-overflow-tooltip />
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }"><el-tag size="small">{{ assetStatusName(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="原值" width="90" align="right">
            <template #default="{ row }"><span class="num">{{ fmtMoney(row.price) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="64" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="createSelected.splice($index, 1)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCreate">确定建包</el-button>
      </template>
    </el-dialog>

    <!-- 拆包/合包 -->
    <el-dialog v-model="adjustVisible" title="拆包 / 合包" width="680px" destroy-on-close top="8vh">
      <div class="text-muted" style="margin-bottom: 10px">
        包 {{ adjustTarget.group_name }} 当前 {{ adjustAssets.length }} 项资产
      </div>
      <el-form label-width="86px">
        <el-form-item label="移出资产（拆包）">
          <el-select v-model="adjustForm.remove_asset_ids" multiple filterable placeholder="选择要移出的资产" style="width: 100%">
            <el-option v-for="a in adjustAssets" :key="a.id" :label="`${a.asset_code} · ${a.asset_name}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="加入资产（合包）">
          <div style="display: flex; align-items: center; gap: 10px">
            <el-button type="primary" plain @click="openAdjustAddSelect">选择资产</el-button>
            <span class="text-muted">已选 <b>{{ adjustForm.add_asset_ids.length }}</b> 项</span>
            <el-button v-if="adjustForm.add_asset_ids.length" link type="danger" size="small" @click="adjustForm.add_asset_ids = []">清空</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveAdjust">保存调整</el-button>
      </template>
    </el-dialog>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" size="560px" :title="`组合包 ${detail.group_name || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="资产数">{{ detail.assets?.length || 0 }}</el-descriptions-item>
        <el-descriptions-item label="包总价">{{ fmtMoney(detail.total_price) }}</el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">包内资产</div>
      <el-table :data="detail.assets || []" size="small" border>
        <el-table-column prop="asset_code" label="资产编码" width="170" />
        <el-table-column prop="asset_name" label="资产名称" min-width="140" show-overflow-tooltip />
        <el-table-column label="原值" width="100" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.price) }}</span></template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 资产选择弹窗（按公司/项目/仓库/状态维度多选） -->
    <AssetSelectDialog
      v-model="assetSelectVisible"
      :title="assetSelectMode === 'create' ? '选择组合包资产' : '选择加入组合包的资产'"
      :preset="assetSelectPreset"
      :allow-statuses="[0, 1, 2, 3, 4]"
      @confirm="onAssetConfirmed"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { groupApi } from "../../api";
import AssetSelectDialog from "../../components/AssetSelectDialog.vue";
import { fmtMoney, fmtDateTime, assetStatusName } from "../../utils/constants";

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "" });

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    const res = await groupApi.list(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}

// ---- 新建 ----
const createVisible = ref(false);
const createForm = reactive({ group_name: "", remark: "" });
const createSelected = ref([]);
async function openCreate() {
  createForm.group_name = "";
  createForm.remark = "";
  createSelected.value = [];
  createVisible.value = true;
}
async function saveCreate() {
  if (!createForm.group_name.trim()) return ElMessage.warning("请填写组合包名称");
  if (!createSelected.value.length) return ElMessage.warning("请至少选择一项资产");
  saving.value = true;
  try {
    await groupApi.create({ ...createForm, asset_ids: createSelected.value.map((a) => a.id) });
    ElMessage.success("组合包已创建");
    createVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

// ---- 资产选择弹窗 ----
const assetSelectVisible = ref(false);
const assetSelectMode = ref("create");
const assetSelectPreset = ref([]);
function openAssetSelect() {
  assetSelectMode.value = "create";
  assetSelectPreset.value = createSelected.value;
  assetSelectVisible.value = true;
}
function openAdjustAddSelect() {
  assetSelectMode.value = "adjust";
  assetSelectPreset.value = [];
  assetSelectVisible.value = true;
}
function onAssetConfirmed(assets) {
  if (assetSelectMode.value === "create") {
    createSelected.value = assets;
  } else {
    const ids = assets.map((a) => a.id);
    adjustForm.add_asset_ids = Array.from(new Set([...adjustForm.add_asset_ids, ...ids]));
  }
}

// ---- 拆包/合包 ----
const adjustVisible = ref(false);
const adjustTarget = ref({});
const adjustAssets = ref([]);
const adjustForm = reactive({ remove_asset_ids: [], add_asset_ids: [] });
async function openAdjust(row) {
  adjustTarget.value = row;
  adjustForm.remove_asset_ids = [];
  adjustForm.add_asset_ids = [];
  const d = await groupApi.detail(row.id);
  adjustAssets.value = d.assets || [];
  adjustVisible.value = true;
}
async function saveAdjust() {
  const { remove_asset_ids, add_asset_ids } = adjustForm;
  if (!remove_asset_ids.length && !add_asset_ids.length) return ElMessage.warning("请至少选择移出或加入的资产");
  saving.value = true;
  try {
    await groupApi.adjust(adjustTarget.value.id, { remove_asset_ids, add_asset_ids });
    ElMessage.success("组合包已调整");
    adjustVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

// ---- 明细 / 解散 ----
const detailVisible = ref(false);
const detail = ref({});
async function openDetail(row) {
  detail.value = await groupApi.detail(row.id);
  detailVisible.value = true;
}
async function dissolve(row) {
  try {
    await ElMessageBox.confirm(
      `解散后包内资产将清空组合包归属（资产本身保留），确定解散「${row.group_name}」？`,
      "解散组合包",
      { type: "warning" }
    );
  } catch {
    return;
  }
  const res = await groupApi.dissolve(row.id);
  ElMessage.success(`已解散，释放 ${res.released} 项资产`);
  load();
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
