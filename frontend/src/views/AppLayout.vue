<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { clearSession, tokenExpireAt } from '../session'

const router = useRouter()
const SIDEBAR_KEY = 'pea_sidebar_collapsed'

function loadSidebarState() {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === '1'
  } catch {
    return false
  }
}

const isCollapsed = ref(loadSidebarState())

function toggleSidebar() {
  isCollapsed.value = !isCollapsed.value
  try {
    localStorage.setItem(SIDEBAR_KEY, isCollapsed.value ? '1' : '0')
  } catch {}
}

async function logout() {
  clearSession()
  await router.replace('/login')
}
</script>

<template>
  <div class="shell" :class="{ collapsed: isCollapsed }">
    <aside class="sidebar">
      <div class="sidebar-head">
        <div class="brand">
          <div class="brand-mark">PEA</div>
          <div v-show="!isCollapsed">
            <h1>Security Console</h1>
            <p>邮件安全分析平台</p>
          </div>
        </div>
        <button class="ghost small sidebar-toggle" @click="toggleSidebar" :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'">
          {{ isCollapsed ? '>>' : '<<' }}
        </button>
      </div>

      <nav class="menu">
        <section class="menu-group">
          <p class="menu-group-title" v-show="!isCollapsed">工作区</p>
          <RouterLink to="/app/overview" class="menu-item" :title="isCollapsed ? '导航总览' : ''">
            <span class="menu-icon">OV</span>
            <span class="menu-label" v-show="!isCollapsed">导航总览</span>
          </RouterLink>
        </section>

        <section class="menu-group">
          <p class="menu-group-title" v-show="!isCollapsed">分析</p>
          <RouterLink to="/app/upload" class="menu-item" :title="isCollapsed ? '上传分析' : ''">
            <span class="menu-icon">UP</span>
            <span class="menu-label" v-show="!isCollapsed">上传分析</span>
          </RouterLink>
          <RouterLink to="/app/url-risk" class="menu-item" :title="isCollapsed ? 'URL 风险' : ''">
            <span class="menu-icon">UR</span>
            <span class="menu-label" v-show="!isCollapsed">URL 风险</span>
          </RouterLink>
          <RouterLink to="/app/history" class="menu-item" :title="isCollapsed ? '历史记录' : ''">
            <span class="menu-icon">HS</span>
            <span class="menu-label" v-show="!isCollapsed">历史记录</span>
          </RouterLink>
        </section>

        <section class="menu-group">
          <p class="menu-group-title" v-show="!isCollapsed">静态沙箱</p>
          <RouterLink to="/app/static-sandbox" class="menu-item" :title="isCollapsed ? '上传扫描' : ''">
            <span class="menu-icon">SS</span>
            <span class="menu-label" v-show="!isCollapsed">上传扫描</span>
          </RouterLink>
          <RouterLink to="/app/static-rules" class="menu-item" :title="isCollapsed ? '规则管理' : ''">
            <span class="menu-icon">SR</span>
            <span class="menu-label" v-show="!isCollapsed">规则管理</span>
          </RouterLink>
        </section>

      </nav>

      <div class="sidebar-footer">
        <p v-if="tokenExpireAt && !isCollapsed">Token 到期: {{ tokenExpireAt }}</p>
        <button class="ghost" @click="logout" :title="isCollapsed ? '退出登录' : ''">
          <span class="menu-icon">EX</span>
          <span v-show="!isCollapsed">退出登录</span>
        </button>
      </div>
    </aside>

    <main class="content-area">
      <router-view />
    </main>
  </div>
</template>
