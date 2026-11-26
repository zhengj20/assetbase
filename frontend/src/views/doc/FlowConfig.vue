<template>
  <div class="page">
    <div class="page__head">
      <div>
        <h1 class="page__title">审批流配置</h1>
        <span class="page__sub">
          一条流程可含多个分支：条件命中执行对应分支，默认分支兜底 · 列表仅显示每个流程最新版本 · 保存生成新版本，在途单据按发起时版本执行
        </span>
      </div>
      <el-button type="primary" :icon="Plus" @click="startCreate">新建流程</el-button>
    </div>

    <!-- 单据审批方式：按单据类型开关审批流 -->
    <div class="card approval-cfg" v-if="approvalCfgs.length">
      <div class="sec-title">单据审批方式</div>
      <div class="text-muted approval-cfg__hint">
        为每种单据选择审批方式：开启走审批流（审批中心审批）；关闭后在单据页「手动审批通过」。两种方式均审批通过即生效
      </div>
      <div class="approval-cfg__grid">
        <div class="approval-cfg__item" v-for="c in approvalCfgs" :key="c.biz_type">
          <span class="approval-cfg__label">{{ c.label }}</span>
          <el-tag size="small" :type="c.on ? 'success' : 'info'" effect="plain">
            {{ c.on ? "审批流" : "手动审批" }}
          </el-tag>
          <el-switch
            v-model="c.on"
            inline-prompt
            active-text="开"
            inactive-text="关"
            @change="(v) => toggleApprovalCfg(c, v)"
          />
        </div>
      </div>
    </div>

    <div class="flow-layout">
      <!-- 左：流程列表（每个流程仅显示最新版本） -->
      <div class="card flow-list">
        <div
          v-for="f in latestFlows"
          :key="f.id || f.flow_key"
          class="flow-item"
          :class="{ active: isCur(f) }"
          @click="openFlow(f)"
        >
          <div class="flow-item__head">
            <span class="flow-item__name">{{ f.flow_name }}</span>
            <el-tag size="small" :type="f.id === 0 ? 'info' : 'success'">
              {{ f.id === 0 ? "内置" : `v${f.version}` }}
            </el-tag>
            <el-tag v-if="f.id" size="small" effect="plain" :type="f.status === 1 ? 'success' : 'info'">
              {{ f.status === 1 ? "启用" : "停用" }}
            </el-tag>
          </div>
          <div class="text-muted">{{ bizLabel(f.biz_type) }} · {{ branchInfo(f) }} · 优先级 {{ f.priority }}</div>
          <div class="text-muted">
            <span v-if="f.branches && f.branches.length > 1">
              多分支：{{ f.branches.map((b) => (b.condition ? condText(b.condition, f.biz_type) : "默认")).join(" / ") }}
            </span>
            <span v-else-if="f.condition">{{ condText(f.condition, f.biz_type) }}</span>
            <span v-else>无条件（兜底流程）</span>
          </div>
          <div v-if="f.id" class="flow-item__ops" @click.stop>
            <el-button link size="small" @click="openFlow(f)">编辑</el-button>
            <el-button link size="small" @click="toggleStatus(f)">{{ f.status === 1 ? "停用" : "启用" }}</el-button>
            <el-button link size="small" type="danger" @click="removeFlow(f)">删除</el-button>
          </div>
        </div>
        <div v-if="!latestFlows.length" class="text-muted" style="padding: 12px">暂无流程，点击「新建流程」创建</div>
      </div>

      <!-- 右：流程图 + 版本管理 + 编辑器 -->
      <div class="card flow-editor">
        <template v-if="cur && cur.readOnly">
          <div class="flow-editor__head">
            <b>{{ cur.flow_name }}</b>
            <el-tag size="small" type="info" style="margin-left: 8px">内置默认流程 · 只读</el-tag>
          </div>

          <div class="flow-diagram">
            <span class="fd-node fd-term">发起</span>
            <span class="fd-arrow">→</span>
            <div class="fd-branches">
              <div class="fd-branch" v-for="(b, bi) in diagramBranches" :key="bi">
                <span class="fd-brtag">{{ b.name || `分支${bi + 1}` }}</span>
                <span class="fd-arrow">→</span>
                <template v-for="(n, i) in b.nodes" :key="i">
                  <div class="fd-node">
                    <span class="fd-node__name"><span class="fd-node__idx">{{ i + 1 }}</span>{{ n.name }}</span>
                    <span class="fd-node__sub">{{ MODE_LABEL[n.mode] || "单签" }} · {{ approversShort(n) }}</span>
                  </div>
                  <span v-if="i < b.nodes.length - 1" class="fd-arrow">→</span>
                </template>
              </div>
            </div>
            <span class="fd-arrow">→</span>
            <span class="fd-node fd-term">完成</span>
          </div>

          <div class="sec-title mt-12">节点列表（默认分支）</div>
          <el-table :data="(cur.branches && cur.branches[0]) ? cur.branches[0].nodes : cur.nodes" size="small" border>
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="name" label="节点名称" />
            <el-table-column label="审批方式" width="110">
              <template #default="{ row }">{{ MODE_LABEL[row.mode] || "单签" }}</template>
            </el-table-column>
            <el-table-column label="审批人" min-width="220">
              <template #default="{ row }">{{ approverText(row) }}</template>
            </el-table-column>
          </el-table>
        </template>

        <template v-else-if="form">
          <div class="flow-editor__head">
            <b>{{ form.defId ? "编辑流程（保存将生成新版本）" : "新建流程" }}</b>
            <el-button type="primary" :icon="Check" :loading="saving" @click="save">保存</el-button>
          </div>

          <div class="flow-diagram">
            <span class="fd-node fd-term">发起</span>
            <span class="fd-arrow">→</span>
            <div class="fd-branches">
              <div class="fd-branch" v-for="(b, bi) in form.branches" :key="bi">
                <span class="fd-brtag" :class="{ on: b.condOn }">
                  {{ b.name || `分支${bi + 1}` }}
                  <i>{{ b.condOn ? condText(b.cond, form.biz_type) : "默认" }}</i>
                </span>
                <span class="fd-arrow">→</span>
                <template v-for="(n, i) in b.nodes" :key="i">
                  <div class="fd-node">
                    <span class="fd-node__name"><span class="fd-node__idx">{{ i + 1 }}</span>{{ n.name || "未命名" }}</span>
                    <span class="fd-node__sub">{{ MODE_LABEL[n.mode] || "单签" }} · {{ approversShort(n) }}</span>
                  </div>
                  <span v-if="i < b.nodes.length - 1" class="fd-arrow">→</span>
                </template>
              </div>
            </div>
            <span class="fd-arrow">→</span>
            <span class="fd-node fd-term">完成</span>
          </div>

          <div class="form-row mt-12">
            <div class="form-field">
              <span class="form-field__label">流程名称</span>
              <el-input v-model="form.flow_name" maxlength="100" placeholder="如：采购申请审批" style="width: 220px" />
            </div>
            <div class="form-field">
              <span class="form-field__label">单据类型</span>
              <el-select v-model="form.biz_type" :disabled="!!form.defId" style="width: 160px" @change="onBizChange">
                <el-option v-for="b in bizTypes" :key="b.key" :label="b.label" :value="b.key" />
              </el-select>
            </div>
            <div class="form-field">
              <span class="form-field__label">优先级</span>
              <el-input-number v-model="form.priority" :min="1" :max="9999" style="width: 120px" />
            </div>
          </div>

          <template v-if="form.defId">
            <div class="sec-title" style="margin-top: 16px">
              版本管理（{{ flowVersions.length }}）
              <span class="text-muted">当前查看 v{{ cur.version }} · 仅「启用」版本参与新单据匹配，在途单据不受影响</span>
            </div>
            <el-table :data="flowVersions" size="small" border>
              <el-table-column label="版本" width="70" align="center">
                <template #default="{ row }">
                  <b>v{{ row.version }}</b>
                  <el-tag v-if="row.id === cur.id" size="small" type="warning" effect="plain" style="margin-left: 4px">当前</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.status === 1 ? 'success' : 'info'">
                    {{ row.status === 1 ? "启用" : "停用" }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="节点" width="110" align="center">
                <template #default="{ row }">{{ branchInfo(row) }}</template>
              </el-table-column>
              <el-table-column label="创建时间" min-width="150">
                <template #default="{ row }">{{ row.create_time || "-" }}</template>
              </el-table-column>
              <el-table-column label="操作" width="170" align="center">
                <template #default="{ row }">
                  <el-button link size="small" type="primary" @click="openFlow(row)">编辑</el-button>
                  <el-button link size="small" type="primary" @click="toggleStatus(row)">
                    {{ row.status === 1 ? "停用" : "启用" }}
                  </el-button>
                  <el-button link size="small" type="danger" @click="removeFlow(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <div class="sec-title mt-12">
            审批分支（条件命中执行对应分支；默认分支兜底）
            <span class="text-muted">{{ form.branches.length }} / {{ MAX_BRANCHES }}</span>
          </div>
          <div v-for="(b, bi) in form.branches" :key="bi" class="branch-card">
            <div class="branch-card__head">
              <span class="branch-card__idx">{{ bi + 1 }}</span>
              <el-input v-model="b.name" placeholder="分支名称，如：≤5万" style="width: 150px" maxlength="50" />
              <el-switch v-model="b.condOn" />
              <span class="text-muted branch-cond-label">分支条件</span>
              <template v-if="b.condOn">
                <el-select v-model="b.cond.field" style="width: 130px">
                  <el-option v-for="fl in condFields" :key="fl.key" :label="fl.label" :value="fl.key" />
                </el-select>
                <el-select v-model="b.cond.op" style="width: 110px">
                  <el-option v-for="o in condOps" :key="o.op" :label="o.label" :value="o.op" />
                </el-select>
                <el-input v-model="b.cond.value" style="width: 120px" placeholder="条件值" />
                <span class="text-muted">命中 → 执行本分支</span>
              </template>
              <span v-else class="text-muted">无条件 → 默认分支（兜底）</span>
              <div class="branch-card__ops">
                <el-button link size="small" :disabled="bi === 0" @click="moveBranch(bi, -1)">上移</el-button>
                <el-button link size="small" :disabled="bi === form.branches.length - 1" @click="moveBranch(bi, 1)">下移</el-button>
                <el-button link size="small" type="danger" :disabled="form.branches.length <= 1" @click="removeBranch(bi)">删除分支</el-button>
              </div>
            </div>

            <div class="branch-card__body">
              <div v-for="(n, i) in b.nodes" :key="i" class="node-card">
                <div class="node-card__head">
                  <span class="node-card__idx">{{ i + 1 }}</span>
                  <el-input v-model="n.name" placeholder="节点名称，如：财务审核" style="width: 200px" maxlength="100" />
                  <el-select v-model="n.mode" style="width: 150px" @change="onModeChange(n)">
                    <el-option label="单签" value="single" />
                    <el-option label="或签（任一通过）" value="any" />
                    <el-option label="会签（全部通过）" value="all" />
                  </el-select>
                  <div class="node-card__ops">
                    <el-button link size="small" :disabled="i === 0" @click="moveNode(b, i, -1)">上移</el-button>
                    <el-button link size="small" :disabled="i === b.nodes.length - 1" @click="moveNode(b, i, 1)">下移</el-button>
                    <el-button link size="small" type="danger" :disabled="b.nodes.length <= 1" @click="removeNode(b, i)">删除</el-button>
                  </div>
                </div>
                <div class="text-muted node-card__mode">{{ MODE_HINT[n.mode] }}</div>
                <div v-for="(a, j) in n.approvers" :key="j" class="appr-row">
                  <el-select v-model="a.type" style="width: 90px" @change="onTypeChange(a)">
                    <el-option label="角色" value="role" />
                    <el-option label="用户" value="user" />
                  </el-select>
                  <el-select v-if="a.type === 'role'" v-model="a.code" style="width: 190px" placeholder="选择角色">
                    <el-option v-for="r in roles" :key="r.role_code" :label="r.role_name" :value="r.role_code" />
                  </el-select>
                  <el-select v-else v-model="a.id" style="width: 190px" placeholder="选择用户">
                    <el-option v-for="u in users" :key="u.id" :label="`${u.real_name}（${u.username}）`" :value="u.id" />
                  </el-select>
                  <el-button link size="small" type="danger" :disabled="n.approvers.length <= 1" @click="n.approvers.splice(j, 1)">
                    移除
                  </el-button>
                </div>
                <el-button size="small" :icon="Plus" :disabled="n.mode === 'single'" @click="addApprover(n)">添加审批人</el-button>
              </div>
              <el-button class="mt-8" :icon="Plus" :disabled="b.nodes.length >= MAX_NODES" @click="addNode(b)">添加节点</el-button>
            </div>
          </div>
          <div class="branch-foot">
            <el-button :icon="Plus" :disabled="form.branches.length >= MAX_BRANCHES" @click="addBranch">添加分支</el-button>
            <span class="text-muted">不同条件走不同审批链；至少保留一个「默认分支」（条件关闭）兜底</span>
          </div>
        </template>

        <div v-else class="flow-editor__empty text-muted">
          从左侧选择流程查看 / 编辑，或点击「新建流程」
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Check } from "@element-plus/icons-vue";
import { flowApi } from "../../api";

const MAX_NODES = 8;
const MAX_BRANCHES = 6;
const MODE_LABEL = { single: "单签", any: "或签", all: "会签" };
const MODE_HINT = {
  single: "单签：由第一位审批人处理即可",
  any: "或签：任一审批人通过即流转，其余任务自动完成",
  all: "会签：所有审批人全部通过才流转",
};

const flows = ref([]);
const roles = ref([]);
const users = ref([]);
const bizTypes = ref([]);
const condOps = ref([]);
const cur = ref(null);
const form = ref(null);
const saving = ref(false);
const approvalCfgs = ref([]);

// 列表仅显示每个流程最新版本：按「流程名称+单据类型」归为同一逻辑流程，取最新版本为代表
// （多次“新建流程”会生成不同 flow_key 的同名流程，对用户而言它们是同一流程的不同版本）
const latestFlows = computed(() => {
  const latest = new Map();
  for (const f of flows.value) {
    if (!f.id) continue;
    const key = `${f.biz_type}::${f.flow_name}`;
    const prev = latest.get(key);
    if (!prev || f.version > prev.version || (f.version === prev.version && f.id > prev.id)) {
      latest.set(key, f);
    }
  }
  return flows.value.filter(
    (f) => f.id === 0 || latest.get(`${f.biz_type}::${f.flow_name}`)?.id === f.id
  );
});

// 当前逻辑流程（同名称+同单据类型）的全部版本，供版本管理区查看/启用/停用/删除
const flowVersions = computed(() => {
  if (!cur.value?.id) return [];
  return flows.value
    .filter(
      (f) => f.id && f.flow_name === cur.value.flow_name && f.biz_type === cur.value.biz_type
    )
    .sort((a, b) => b.version - a.version || b.id - a.id);
});

// 流程图数据（内置流取定义分支；编辑态取表单分支）
const diagramBranches = computed(() => {
  const raw =
    cur.value?.readOnly
      ? cur.value.branches || [{ name: "默认", condition: null, nodes: cur.value.nodes }]
      : form.value?.branches || [];
  return raw.map((b) => ({
    name: b.name || "",
    condOn: !!(b.condOn ?? b.condition),
    cond: (b.condOn ? b.cond : null) || (b.condOn ? b.condition : null),
    nodes: b.nodes || [],
  }));
});

const bizLabel = (key) => bizTypes.value.find((b) => b.key === key)?.label || key;
function branchInfo(f) {
  const total = (f.branches || []).reduce((s, b) => s + (b.nodes?.length || 0), 0) || f.nodes?.length || 0;
  const bc = (f.branches || []).filter((b) => b.nodes?.length).length;
  return bc > 1 ? `${bc} 分支 · ${total} 节点` : `${total} 节点`;
}
function condText(c, bizKey) {
  const opLabel = condOps.value.find((o) => o.op === c.op)?.label || c.op;
  const fieldLabel = bizTypes.value.find((b) => b.key === bizKey)?.fields?.[c.field] || c.field;
  return `${fieldLabel} ${opLabel} ${c.value}`;
}
const condFields = computed(() => {
  const biz = bizTypes.value.find((b) => b.key === form.value?.biz_type);
  return Object.entries(biz?.fields || {}).map(([key, label]) => ({ key, label }));
});

function approverText(row) {
  return (row.approvers || [])
    .map((a) =>
      a.type === "role"
        ? `角色：${roles.value.find((r) => r.role_code === a.code)?.role_name || a.code}`
        : `用户：${users.value.find((u) => u.id === a.id)?.real_name || a.id}`
    )
    .join("、");
}

function approversShort(n) {
  const list = (n.approvers || []).map((a) =>
    a.type === "role"
      ? roles.value.find((r) => r.role_code === a.code)?.role_name || a.code
      : users.value.find((u) => u.id === a.id)?.real_name || `用户${a.id}`
  );
  if (!list.length) return "未设审批人";
  return list.length > 3 ? `${list.slice(0, 3).join("、")} 等${list.length}人` : list.join("、");
}

function isCur(f) {
  return !!cur.value && (cur.value.id === f.id || (cur.value.readOnly && cur.value.flow_key === f.flow_key));
}

async function load() {
  const res = await flowApi.list();
  flows.value = res.flows || [];
  roles.value = res.roles || [];
  users.value = res.users || [];
  bizTypes.value = res.biz_types || [];
  condOps.value = res.cond_ops || [];
  if (cur.value?.readOnly) {
    const f = flows.value.find((x) => x.flow_key === cur.value.flow_key);
    cur.value = f ? { ...f, readOnly: true } : null;
  }
}

async function loadApprovalCfg() {
  try {
    const res = await flowApi.approvalConfig();
    approvalCfgs.value = (res.configs || []).map((c) => ({ ...c, on: c.flow_enabled === 1 }));
  } catch {
    approvalCfgs.value = [];
  }
}

async function toggleApprovalCfg(c, v) {
  try {
    await flowApi.setApprovalConfig(c.biz_type, v ? 1 : 0);
    ElMessage.success(v ? `${c.label} 已启用审批流` : `${c.label} 已切换为手动审批`);
  } catch {
    c.on = !v;
  }
}

function newNode() {
  return {
    name: "",
    mode: "single",
    approvers: [
      roles.value.length
        ? { type: "role", code: roles.value[0].role_code, id: null }
        : { type: "user", code: "", id: users.value[0]?.id || null },
    ],
  };
}

function firstFieldOf(bizKey) {
  const biz = bizTypes.value.find((b) => b.key === bizKey);
  return Object.keys(biz?.fields || {})[0] || "";
}

function startCreate() {
  cur.value = null;
  form.value = {
    defId: null,
    flow_name: "",
    biz_type: "purchase",
    priority: 100,
    branches: [
      {
        name: "默认",
        condOn: false,
        cond: { field: firstFieldOf("purchase"), op: "gt", value: "" },
        nodes: [newNode()],
      },
    ],
  };
}

function openFlow(f) {
  form.value = null;
  cur.value = { ...f, readOnly: f.id === 0 };
  if (f.id === 0) return;
  const src = f.branches?.length ? f.branches : [{ name: "默认", condition: null, nodes: f.nodes }];
  form.value = {
    defId: f.id,
    flow_key: f.flow_key,
    flow_name: f.flow_name,
    biz_type: f.biz_type,
    priority: f.priority ?? 100,
    branches: src.map((b) => ({
      name: b.name || "",
      condOn: !!b.condition,
      cond: b.condition
        ? { field: b.condition.field, op: b.condition.op, value: String(b.condition.value) }
        : { field: firstFieldOf(f.biz_type), op: "gt", value: "" },
      nodes: (b.nodes || []).map((n) => ({
        name: n.name,
        mode: n.mode || "single",
        approvers: (n.approvers || []).map((a) => ({
          type: a.type || "role",
          code: a.type === "role" ? a.code : "",
          id: a.type === "user" ? a.id : null,
        })),
      })),
    })),
  };
}

function onBizChange(key) {
  const first = firstFieldOf(key);
  (form.value?.branches || []).forEach((b) => {
    const fields = bizTypes.value.find((x) => x.key === key)?.fields || {};
    if (!fields[b.cond.field]) b.cond.field = first;
  });
}

// ---- 分支操作 ----
function addBranch() {
  form.value.branches.push({
    name: "",
    condOn: true,
    cond: { field: firstFieldOf(form.value.biz_type), op: "gt", value: "" },
    nodes: [newNode()],
  });
}
function removeBranch(i) {
  form.value.branches.splice(i, 1);
}
function moveBranch(i, delta) {
  const bs = form.value.branches;
  const j = i + delta;
  [bs[i], bs[j]] = [bs[j], bs[i]];
}

// ---- 分支内节点操作 ----
function addNode(b) {
  b.nodes.push(newNode());
}
function removeNode(b, i) {
  b.nodes.splice(i, 1);
}
function moveNode(b, i, delta) {
  const j = i + delta;
  [b.nodes[i], b.nodes[j]] = [b.nodes[j], b.nodes[i]];
}

function onModeChange(n) {
  if (n.mode === "single") n.approvers = n.approvers.slice(0, 1);
  if (!n.approvers.length) n.approvers = [newNode().approvers[0]];
}

function onTypeChange(a) {
  if (a.type === "role") {
    a.code = roles.value[0]?.role_code || "";
    a.id = null;
  } else {
    a.id = users.value[0]?.id || null;
    a.code = "";
  }
}

function addApprover(n) {
  n.approvers.push(
    roles.value.length
      ? { type: "role", code: roles.value[0].role_code, id: null }
      : { type: "user", code: "", id: users.value[0]?.id || null }
  );
}

function buildPayload() {
  const v = form.value;
  return {
    flow_name: v.flow_name.trim(),
    biz_type: v.biz_type,
    priority: v.priority,
    branches: v.branches.map((b) => ({
      name: b.name.trim() || null,
      condition: b.condOn
        ? { field: b.cond.field, op: b.cond.op, value: Number(b.cond.value) || b.cond.value }
        : null,
      nodes: b.nodes.map((n) => ({
        name: n.name.trim(),
        mode: n.mode,
        approvers: n.approvers.map((a) =>
          a.type === "role" ? { type: "role", code: a.code } : { type: "user", id: a.id }
        ),
      })),
    })),
  };
}

function validate() {
  const v = form.value;
  if (!v.flow_name.trim()) return "请填写流程名称";
  if (!v.branches.length) return "请至少添加一个分支";
  if (!v.branches.some((b) => !b.condOn)) return "请至少保留一个默认分支（关闭分支条件）作为兜底";
  for (let bi = 0; bi < v.branches.length; bi++) {
    const b = v.branches[bi];
    const label = b.name.trim() || `分支${bi + 1}`;
    if (b.condOn && !String(b.cond.value).trim()) return `分支「${label}」请填写条件值`;
    if (!b.nodes.length) return `分支「${label}」至少保留一个审批节点`;
    const names = new Set();
    for (const n of b.nodes) {
      if (!n.name.trim()) return `分支「${label}」请填写所有节点名称`;
      if (names.has(n.name.trim())) return `分支「${label}」内节点名称不能重复`;
      names.add(n.name.trim());
      for (const a of n.approvers) {
        if (a.type === "role" && !a.code) return `分支「${label}」节点「${n.name}」请选择角色`;
        if (a.type === "user" && !a.id) return `分支「${label}」节点「${n.name}」请选择用户`;
      }
    }
  }
  return null;
}

async function save() {
  const err = validate();
  if (err) return ElMessage.warning(err);
  saving.value = true;
  try {
    const payload = buildPayload();
    const res = form.value.defId
      ? await flowApi.save(form.value.defId, payload)
      : await flowApi.create(payload);
    ElMessage.success(`已保存为 v${res.version}，新单据将按此流程审批`);
    await load();
    // 重新打开刚保存的版本，便于继续查看/编辑（历史版本编辑保存后同样生效）
    const saved = flows.value.find((f) => f.id === res.id);
    if (saved) openFlow(saved);
  } finally {
    saving.value = false;
  }
}

async function toggleStatus(f) {
  const next = f.status === 1 ? 0 : 1;
  await flowApi.setStatus(f.id, next);
  ElMessage.success(next === 1 ? "已启用" : "已停用");
  await load();
}

async function removeFlow(f) {
  try {
    await ElMessageBox.confirm(
      `删除版本 v${f.version}「${f.flow_name}」？删除后不可恢复，在途实例不受影响。`,
      "删除确认",
      { type: "warning" }
    );
  } catch {
    return;
  }
  await flowApi.remove(f.id);
  ElMessage.success("已删除");
  if (isCur(f)) {
    cur.value = null;
    form.value = null;
  }
  await load();
}

onMounted(() => {
  load();
  loadApprovalCfg();
});
</script>

<style scoped>
.approval-cfg { padding: 12px 16px; margin-bottom: 14px; }
.approval-cfg__hint { margin: 4px 0 12px; font-size: 12px; }
.approval-cfg__grid { display: flex; flex-wrap: wrap; gap: 10px; }
.approval-cfg__item {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 12px; border: 1px solid var(--line, #e7e3d9); border-radius: 8px; background: #fdfcfa;
}
.approval-cfg__label { font-size: 13px; color: var(--ink); }
.flow-layout { display: flex; gap: 14px; flex: 1; min-height: 0; }
.flow-list {
  width: 300px; flex-shrink: 0; min-width: 0; padding: 10px;
  display: flex; flex-direction: column; gap: 8px; overflow-y: auto;
}
.flow-item {
  padding: 10px 12px; border: 1px solid var(--line, #e7e3d9); border-radius: 8px;
  cursor: pointer; transition: all 0.15s; background: #fff;
}
.flow-item:hover { border-color: var(--brand, #b07a2e); }
.flow-item.active { border-color: var(--brand, #b07a2e); box-shadow: 0 0 0 2px rgba(176, 122, 46, 0.12); background: #fdfaf5; }
.flow-item__head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.flow-item__name { font-size: 13px; font-weight: 600; color: var(--ink); }
.flow-item__ops { display: flex; margin-top: 6px; }
.flow-editor {
  flex: 1; min-width: 0; padding: 14px 18px 18px;
  display: flex; flex-direction: column; overflow-y: auto;
}
/* 内容超出一屏时靠容器滚动，禁止子项被 flex 压缩（否则 el-table 会被压成 0 高、按钮被后续元素遮挡） */
.flow-editor > * { flex-shrink: 0; }
.flow-editor__head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.flow-editor__empty { padding: 40px 0; text-align: center; }

/* 流程图 */
.flow-diagram {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  margin-top: 14px; padding: 12px 14px;
  border: 1px dashed var(--gold-line, #e7d9bd); border-radius: 8px;
  background: #fbf8f1;
}
.fd-node {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  padding: 6px 12px; border: 1px solid var(--line, #e7e3d9); border-radius: 6px; background: #fff;
}
.fd-node__name { font-size: 13px; font-weight: 600; color: var(--ink); display: flex; align-items: center; gap: 6px; }
.fd-node__idx {
  width: 18px; height: 18px; border-radius: 50%; flex-shrink: 0;
  background: var(--brand, #1f5c8b); color: #fff; font-size: 11px;
  display: inline-flex; align-items: center; justify-content: center;
}
.fd-node__sub { font-size: 11px; color: var(--ink-3, #93a1ad); }
.fd-node.fd-term { background: var(--gold-soft, #f4ead8); border-color: var(--gold-line, #e7d9bd); font-size: 12px; font-weight: 600; color: var(--gold-deep, #8f6222); }
.fd-arrow { color: var(--ink-3, #93a1ad); font-size: 14px; }
.fd-branches { display: flex; flex-direction: column; gap: 8px; }
.fd-branch { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.fd-brtag {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;
  border: 1px solid var(--line, #e7e3d9); border-radius: 6px; background: #fff;
  font-size: 12px; font-weight: 600; color: var(--ink);
}
.fd-brtag i { font-style: normal; font-size: 11px; font-weight: 400; color: var(--ink-3, #93a1ad); }
.fd-brtag.on { border-color: var(--brand, #b07a2e); color: var(--brand, #b07a2e); background: #fdfaf5; }

/* 紧凑表单行 */
.form-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 18px; }
.form-field { display: inline-flex; align-items: center; gap: 8px; }
.form-field__label { font-size: 13px; color: var(--ink-2, #5b6b7a); white-space: nowrap; }

/* 分支卡片 */
.branch-card {
  border: 1px solid var(--line, #e7e3d9); border-radius: 8px;
  padding: 12px; margin-bottom: 10px; background: #fdfcfa;
}
.branch-card__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.branch-card__idx {
  width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  background: var(--brand, #b07a2e); color: #fff; font-size: 12px;
  display: flex; align-items: center; justify-content: center;
}
.branch-card__ops { margin-left: auto; display: flex; gap: 2px; }
.branch-card__body { margin-top: 12px; padding-left: 8px; border-left: 2px dashed var(--gold-line, #e7d9bd); }
.branch-cond-label { font-size: 12px; }
.branch-foot { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

.node-card {
  border: 1px solid var(--line, #e7e3d9); border-radius: 8px; padding: 12px;
  margin-bottom: 10px; background: #fff;
}
.node-card__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.node-card__idx {
  width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  background: var(--brand, #b07a2e); color: #fff; font-size: 12px;
  display: flex; align-items: center; justify-content: center;
}
.node-card__ops { margin-left: auto; display: flex; gap: 2px; }
.node-card__mode { margin: 6px 0 8px 30px; font-size: 12px; }
.appr-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; margin-left: 30px; flex-wrap: wrap; }
</style>
