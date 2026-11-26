<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">全局资产搜索</h1>
      <span class="page__sub">编码 / 名称 / 规格 / 品牌 / 位置 全字段全文检索（ngram 索引加速）</span>
    </div>

    <!-- 大搜索框 -->
    <div class="hero card">
      <el-input
        v-model="keyword"
        size="large"
        placeholder="输入关键词，回车搜索：如 ThinkPad / GD-A0101 / 沙发 / 售楼处"
        :prefix-icon="Search"
        clearable
        @keyup.enter="doSearch"
      >
        <template #append>
          <el-button type="primary" @click="doSearch">搜 索</el-button>
        </template>
      </el-input>
      <div class="hero__filters">
        <el-select v-model="f.status" placeholder="状态" clearable size="default" @change="doSearch">
          <el-option v-for="s in ASSET_STATUS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="f.category_id" placeholder="分类" clearable filterable size="default" @change="doSearch">
          <el-option v-for="c in categories" :key="c.id" :label="c.category_name" :value="c.id" />
        </el-select>
        <el-select v-model="f.warehouse_id" placeholder="仓库" clearable filterable size="default" @change="doSearch">
          <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
        </el-select>
        <el-select v-model="f.org_id" placeholder="核算公司" clearable filterable size="default" @change="doSearch">
          <el-option v-for="o in orgs" :key="o.id" :label="o.org_name" :value="o.id" />
        </el-select>
        <el-select v-model="f.is_high_value" placeholder="高值" clearable size="default" @change="doSearch">
          <el-option label="高值" :value="1" />
          <el-option label="普通" :value="0" />
        </el-select>
      </div>
    </div>

    <!-- 结果 -->
    <div class="card table-card">
      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="asset_code" label="资产编码" width="175">
          <template #default="{ row }">
            <router-link class="code-link num" :to="`/asset/list?focus=${row.id}`">{{ row.asset_code }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="asset_name" label="资产名称" min-width="190" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="140" show-overflow-tooltip />
        <el-table-column prop="brand" label="品牌" width="90" />
        <el-table-column label="状态" width="86" align="center">
          <template #default="{ row }">
            <span class="st" :class="`st--${row.status}`">{{ assetStatusName(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="原值" width="110" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.price) }}</span></template>
        </el-table-column>
        <el-table-column prop="location_detail" label="存放位置" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.location_detail || "-" }}</template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <span class="text-muted" v-if="searched">匹配 {{ total }} 项</span>
        <span v-else class="text-muted">输入关键词开始检索</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { Search } from "@element-plus/icons-vue";
import { searchApi, archiveApi, sysApi } from "../api";
import { ASSET_STATUS, assetStatusName, fmtMoney } from "../utils/constants";

const route = useRoute();
const keyword = ref("");
const f = reactive({ status: null, category_id: null, warehouse_id: null, org_id: null, is_high_value: null });
const rows = ref([]);
const total = ref(0);
const loading = ref(false);
const searched = ref(false);
const categories = ref([]);
const warehouses = ref([]);
const orgs = ref([]);

async function doSearch() {
  if (!keyword.value.trim()) return;
  loading.value = true;
  try {
    const params = { keyword: keyword.value.trim(), limit: 200 };
    Object.entries(f).forEach(([k, v]) => {
      if (v !== null && v !== "" && v !== undefined) params[k] = v;
    });
    const res = await searchApi.assets(params);
    rows.value = res.records;
    total.value = res.total;
    searched.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  const [cats, whs, os] = await Promise.all([
    archiveApi.categories(), archiveApi.warehouses(), sysApi.orgs(),
  ]);
  categories.value = cats;
  warehouses.value = whs;
  orgs.value = os;
  if (route.query.keyword) {
    keyword.value = route.query.keyword;
    doSearch();
  }
});
</script>

<style scoped>
.hero { padding: 20px 20px 14px; flex-shrink: 0; }
.hero :deep(.el-input__inner) { height: 44px; font-size: 15px; }
.hero__filters { display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
.hero__filters .el-select { width: 160px; }
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.code-link { color: var(--brand); }
.code-link:hover { text-decoration: underline; }
</style>
