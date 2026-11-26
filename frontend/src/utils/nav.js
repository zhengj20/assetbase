import { useRouter } from "vue-router";

/**
 * 跳转到目标路由；若当前 SPA 会话的路由表中不存在该路由
 * （例如页面长时间未刷新、新增了路由），则退回整页加载，避免白屏。
 */
export function pushSafe(router, path) {
  try {
    const to = router.resolve(path);
    if (to.matched && to.matched.length) {
      router.push(path);
      return;
    }
  } catch {
    /* resolve 异常时走整页加载 */
  }
  window.location.href = path;
}
