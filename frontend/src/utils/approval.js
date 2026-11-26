import { flowApi } from "../api";

/**
 * 查询某单据类型是否启用审批流（默认启用，保留既有行为）。
 * 失败时按启用处理，避免误伤既有流程。
 */
export async function loadFlowEnabled(bizType) {
  try {
    const res = await flowApi.approvalConfig();
    const cfg = (res.configs || []).find((c) => c.biz_type === bizType);
    return !cfg || cfg.flow_enabled === 1;
  } catch {
    return true;
  }
}
