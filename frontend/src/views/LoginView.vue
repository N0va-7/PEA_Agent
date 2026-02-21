<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { loginApi } from '../api'
import { saveApiBase, setSession } from '../session'

const router = useRouter()
const username = ref('admin')
const password = ref('')
const loading = ref(false)
const errorText = ref('')

async function handleLogin() {
  errorText.value = ''
  loading.value = true
  try {
    saveApiBase(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000')
    const payload = await loginApi(username.value, password.value)
    setSession(payload.access_token, Number(payload.expires_in || 0))
    await router.replace('/app/overview')
  } catch (error) {
    errorText.value = `登录失败: ${error.message}`
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-shell">
    <div class="auth-card">
      <div class="auth-mark">PEA</div>
      <h1>邮件威胁分析平台</h1>
      <p class="auth-subtitle">登录后可进行邮件分析、查看历史报告与风险结论</p>

      <label>用户名</label>
      <input v-model="username" placeholder="admin" />

      <label>密码</label>
      <input v-model="password" type="password" placeholder="请输入密码" @keyup.enter="handleLogin" />

      <button :disabled="loading" @click="handleLogin">
        {{ loading ? '登录中...' : '登录系统' }}
      </button>
      <p v-if="errorText" class="error-text">{{ errorText }}</p>
    </div>
  </div>
</template>
