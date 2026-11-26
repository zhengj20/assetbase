<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">折旧管理</h1>
      <span class="page__sub">平均年限法 · 按月计提 · 反结账冲回</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-date-picker
          v-model="period" type="month" value-format="YYYYMM"
          placeholder="会计期间（默认当月）" style="width: 200px"
        />
        <el-button type="primary" :icon="Plus" :loading="acting" @click="onCalculate">计提折旧</el-button>
        <el-button type="success" plain :icon="Lock" :loading="acting" @click="onLock">结账</el-button>
        <el-button type="warning" plain :icon="Unlock" :loading="acting" @click="onUnlock">反结账(解锁)</el-button>
        <el-button type="danger" plain :icon="RefreshLeft" :loading="acting" @click="onReverse">冲回本期</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="period" label="期间" width="90" />
        <el-table-column prop="asset_code" label="资产编码" width="180" show-overflow-tooltip>
          <template #default="{ row }"><span class="num">{{ row.asset_code }}</span></template>
        </el-table-column>
        <el-table-column prop="asset_name" label="资产名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="原值" width="120" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.orig_value) }}</span></template>
        </el-table-column>
        <el-table-column label="本月计提" width="120" align="right">
          <template #default="{ row }"><span class="num" style="color: var(--danger)">{{ fmtMoney(row.monthly_dep) }}</span></template>
        </el-table-column>
        <el-table-column label="累计折旧" width="120" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.accum_dep) }}</span></template>
        </el-table-column>
        <el-table-column label="期末净值" width="120" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.net_value) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? "已结账" : "未结账" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="计提时间" width="160">
          <template #default="{ row }">{{ fmtDateTime(row.create_time) }}</template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 条计提记录</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50, 100]" layout="sizes, prev, pager, next, jumper" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Refresh, RefreshLeft, Lock, Unlock } from "@element-plus/icons-vue";
import { depApi } from "../../api";
import { fmtMoney, fmtDateTime, thisPeriod } from "../../utils/constants";

const loading = ref(false);
const acting = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const period = ref(thisPeriod());

async function load() {
  loading.value = true;
  try {
    const res = await depApi.list({ page: page.value, page_size: pageSize.value });
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}

async function onCalculate() {
  const p = period.value;
  if (!p) return ElMessage.warning("请先选择会计期间");
  try {
    await ElMessageBox.confirm(
      `将对期间 ${p} 内所有符合条件的资产按月计提折旧（平均年限法），确定执行？`,
      "计提折旧",
      { type: "warning", confirmButtonText: "确定计提", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }
  acting.value = true;
  try {
    const res = await depApi.calculate(p);
    ElMessage.success(`计提完成：处理 ${res.processed} 项资产，本月计提 ¥${fmtMoney(res.amount)}`);
    load();
  } catch {
    /* 全局拦截器已提示错误 */
  } finally {
    acting.value = false;
  }
}

async function onReverse() {
  const p = period.value;
  if (!p) return ElMessage.warning("请先选择会计期间");
  try {
    await ElMessageBox.confirm(
      `将冲回期间 ${p} 的全部未结账计提记录，并恢复资产累计折旧/净值，确定执行？`,
      "反结账",
      { type: "warning", confirmButtonText: "确定冲回", cancelButtonText: "取消" }
    );
  } catch {
    return;
  }
  acting.value = true;
  try {
    const res = await depApi.reverse(p);
    ElMessage.success(`反结账完成：冲回 ${res.count} 条记录，合计 ¥${fmtMoney(res.amount)}`);
    load();
  } catch {
    /* 全局拦截器已提示错误 */
  } finally {
    acting.value = false;
  }
}

async function onLock() {
  const p = period.value;
  if (!p) return ElMessage.warning("请先选择会计期间");
  try {
    await ElMessageBox.confirm(`确定将期间 ${p} 的全部计提记录结账（锁定，不可再冲回）？`, "结账", {
      type: "warning",
      confirmButtonText: "确定结账",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  acting.value = true;
  try {
    const res = await depApi.lock(p);
    ElMessage.success(`结账完成：${res.count} 条记录已锁定`);
    load();
  } catch {
    /* 全局拦截器已提示错误 */
  } finally {
    acting.value = false;
  }
}

async function onUnlock() {
  const p = period.value;
  if (!p) return ElMessage.warning("请先选择会计期间");
  try {
    await ElMessageBox.confirm(`确定将期间 ${p} 的已结账记录解锁（解锁后可冲回）？`, "反结账（解锁）", {
      type: "warning",
      confirmButtonText: "确定解锁",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  acting.value = true;
  try {
    const res = await depApi.unlock(p);
    ElMessage.success(`已解锁 ${res.count} 条记录`);
    load();
  } catch {
    /* 全局拦截器已提示错误 */
  } finally {
    acting.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
</style>
