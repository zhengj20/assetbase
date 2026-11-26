// 列表分页公共逻辑：page-size 变化时重置到第 1 页，避免越界空页
import { reactive } from "vue";

export function usePaged(load, defaultPageSize = 10) {
  const pager = reactive({ page: 1, pageSize: defaultPageSize });
  pager.reset = () => {
    pager.page = 1;
    load();
  };
  return pager;
}
