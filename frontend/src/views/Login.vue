<template>
  <div class="login">
    <!-- 左：品牌叙事区 -->
    <div class="login__hero">
      <div class="hero-grid"></div>
      <div class="hero-body">
        <div class="hero-mark">固</div>
        <h1 class="hero-title">固定资产<br />全生命周期管理</h1>
        <p class="hero-sub">房地产行业适配 · 多公司多项目 · 售楼处样板间专项</p>
        <ul class="hero-points">
          <li>资产台账 · 履历留痕 · 二维码标签</li>
          <li>采购入库 · 领用调拨 · 报废处置全流程审批</li>
          <li>扫码盘点 · 盘盈盘亏差异闭环 · 报表输出</li>
          <li>全局资产搜索 · 账实一致率 ≤ 0.5%</li>
        </ul>
      </div>
      <div class="hero-foot">REAL ESTATE ASSET MANAGEMENT SYSTEM · V2.0</div>
    </div>

    <!-- 右：登录表单 -->
    <div class="login__panel">
      <div class="login-form">
        <h2 class="login-form__title">登 录</h2>
        <p class="login-form__sub">请使用资产管理账号登录系统</p>
        <el-form :model="form" size="large" @keyup.enter="submit">
          <el-form-item>
            <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              show-password
              :prefix-icon="Lock"
            />
          </el-form-item>
          <el-button
            class="login-form__btn"
            type="primary"
            size="large"
            :loading="loading"
            @click="submit"
          >
            进入系统
          </el-button>
        </el-form>
        <div v-if="showDemoAccount" class="login-form__tip">
          演示账号：<b>admin / admin123</b>（超级管理员）
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { User, Lock } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);
const form = reactive({ username: "", password: "" });

// 生产环境不显示演示账号（通过 VITE_SHOW_DEMO_ACCOUNT 环境变量控制）
const showDemoAccount = import.meta.env.VITE_SHOW_DEMO_ACCOUNT === "true";

async function submit() {
  if (!form.username || !form.password) return ElMessage.warning("请输入用户名与密码");
  loading.value = true;
  try {
    await auth.login(form);
    router.push("/dashboard");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login {
  height: 100vh;
  display: flex;
  background: var(--bg);
}

/* ---------- 左侧品牌区 ---------- */
.login__hero {
  flex: 1.15;
  background:
    radial-gradient(ellipse at 20% 10%, rgba(42, 80, 119, 0.55), transparent 55%),
    radial-gradient(ellipse at 85% 85%, rgba(176, 122, 46, 0.22), transparent 50%),
    linear-gradient(160deg, #12283f 0%, var(--navy) 45%, #0e1e30 100%);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  color: #fff;
}
.hero-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 78%);
}
.hero-body { position: relative; padding: 0 9%; max-width: 640px; }
.hero-mark {
  width: 58px;
  height: 58px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--gold), var(--gold-deep));
  font-family: var(--serif);
  font-size: 32px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28px;
  box-shadow: 0 6px 24px rgba(176, 122, 46, 0.45);
}
.hero-title {
  font-family: var(--serif);
  font-size: 42px;
  line-height: 1.25;
  letter-spacing: 3px;
  margin: 0 0 14px;
  font-weight: 700;
}
.hero-sub { color: rgba(184, 197, 210, 0.85); font-size: 14px; letter-spacing: 1px; margin: 0 0 34px; }
.hero-points { list-style: none; padding: 0; margin: 0; }
.hero-points li {
  padding: 9px 0 9px 26px;
  position: relative;
  color: rgba(230, 236, 242, 0.9);
  font-size: 13.5px;
  letter-spacing: 0.5px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}
.hero-points li::before {
  content: "◆";
  position: absolute;
  left: 2px;
  color: var(--gold);
  font-size: 10px;
  top: 13px;
}
.hero-foot {
  position: absolute;
  bottom: 26px;
  left: 9%;
  color: rgba(184, 197, 210, 0.4);
  font-size: 10px;
  letter-spacing: 3px;
}

/* ---------- 右侧表单区 ---------- */
.login__panel {
  width: 460px;
  background: var(--card);
  display: flex;
  align-items: center;
  justify-content: center;
  border-left: 1px solid var(--line);
}
.login-form { width: 300px; }
.login-form__title {
  font-family: var(--serif);
  font-size: 30px;
  color: var(--navy);
  letter-spacing: 14px;
  margin: 0 0 6px;
  font-weight: 700;
}
.login-form__sub { color: var(--ink-3); font-size: 12px; margin: 0 0 30px; }
.login-form__btn { width: 100%; margin-top: 6px; height: 42px; }
.login-form__tip {
  margin-top: 26px;
  padding: 10px 14px;
  background: var(--gold-soft);
  border: 1px dashed var(--gold-line);
  border-radius: 4px;
  color: var(--gold-deep);
  font-size: 12px;
}
.login-form__tip b { font-family: var(--serif); }

@media (max-width: 900px) {
  .login__hero { display: none; }
}
</style>
