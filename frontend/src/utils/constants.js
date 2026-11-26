/** 业务常量映射（与后端字典/枚举对齐） */

export const ASSET_STATUS = [
  { value: 0, label: "待入库" },
  { value: 1, label: "在库" },
  { value: 2, label: "领用中" },
  { value: 3, label: "维修中" },
  { value: 4, label: "调拨中" },
  { value: 5, label: "已报废" },
  { value: 6, label: "已处置" },
  { value: 7, label: "借用中" },
];
export const assetStatusName = (v) => ASSET_STATUS.find((s) => s.value === v)?.label ?? v;

export const DOC_STATUS = {
  0: { label: "草稿", type: "info" },
  1: { label: "审批中", type: "warning" },
  2: { label: "已生效", type: "success" },
  3: { label: "已驳回", type: "danger" },
  4: { label: "已作废", type: "info" },
};

export const CHECK_STATUS = {
  0: { label: "待执行", type: "info" },
  1: { label: "执行中", type: "primary" },
  2: { label: "差异处理", type: "warning" },
  3: { label: "已完成", type: "success" },
};

export const CHECK_RESULT = {
  1: { label: "正常", type: "success" },
  2: { label: "盘盈", type: "warning" },
  3: { label: "盘亏", type: "danger" },
  4: { label: "位置异常", type: "primary" },
};

export const IN_TYPE = { 1: "采购入库", 2: "调拨入库", 3: "退库入库", 4: "盘盈入库", 5: "直接入库" };
export const OUT_TYPE = { 1: "领用出库", 2: "调拨出库", 3: "报废出库", 4: "盘亏出库" };
export const DISPOSE_TYPE = { 1: "报废", 2: "变卖", 3: "捐赠" };
export const SCOPE_LABEL = { 1: "公司", 2: "项目", 3: "仓库", 4: "空间", 5: "部门" };
export const CHECK_TYPE_LABEL = { 1: "定期盘点", 2: "临时盘点", 3: "清盘专项" };

export const fmtMoney = (v) =>
  v == null ? "-" : Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtDateTime = (v) => (v ? String(v).replace("T", " ").slice(0, 19) : "-");
export const fmtDate = (v) => (v ? String(v).slice(0, 10) : "-");
export const pct = (v) => (v == null ? "-" : `${(Number(v) * 100).toFixed(2)}%`);

/** 本地时区今日 YYYY-MM-DD（避免 toISOString 走 UTC 导致凌晨 0–8 点取到昨天） */
export const todayStr = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

/** 本地时区当前期间 YYYYMM（折旧期间默认值，避免跨月凌晨取到上月） */
export const thisPeriod = () => {
  const d = new Date();
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}`;
};
