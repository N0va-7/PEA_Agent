<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiFetch, isAuthError } from '../api'
import { clearSession } from '../session'

const router = useRouter()
const loading = ref(false)
const errorText = ref('')
const stats = ref({
  total: 0,
  malicious: 0,
  normal: 0,
  latestAt: '',
})
const recentItems = ref([])

const riskSummary = computed(() => {
  const malicious = Number(stats.value.malicious || 0)
  const normal = Number(stats.value.normal || 0)
  const known = malicious + normal
  const unknown = Math.max(0, Number(stats.value.total || 0) - known)
  const maliciousPct = known > 0 ? Math.round((malicious / known) * 100) : 0
  const normalPct = known > 0 ? 100 - maliciousPct : 0
  return { known, unknown, maliciousPct, normalPct }
})

const riskRingStyle = computed(() => {
  if (riskSummary.value.known <= 0) {
    return { background: 'conic-gradient(#cbd5e1 0 100%)' }
  }
  const maliciousPct = riskSummary.value.maliciousPct
  return {
    background: `conic-gradient(#ef4444 0 ${maliciousPct}%, #22c55e ${maliciousPct}% 100%)`,
  }
})

const trendLinePoints = computed(() => {
  const rows = [...recentItems.value].reverse()
  if (rows.length === 0) return ''

  const width = 320
  const height = 120
  const pad = 12
  const usableWidth = width - pad * 2
  const usableHeight = height - pad * 2

  const values = rows.map((row) => {
    const score = Number(row?.final_decision?.score)
    if (!Number.isNaN(score)) return Math.min(1, Math.max(0, score))
    if (row?.final_decision?.is_malicious === true) return 1
    if (row?.final_decision?.is_malicious === false) return 0
    return 0.5
  })

  return values
    .map((value, index) => {
      const x = pad + (usableWidth * index) / Math.max(values.length - 1, 1)
      const y = height - pad - value * usableHeight
      return `${x},${y}`
    })
    .join(' ')
})

const trendAreaPoints = computed(() => {
  if (!trendLinePoints.value) return ''
  const points = trendLinePoints.value
  return `12,108 ${points} 308,108`
})

function formatDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function verdictLabel(item) {
  const v = item?.final_decision?.is_malicious
  if (v === true) return '恶意'
  if (v === false) return '正常'
  return '未判定'
}

async function loadOverview() {
  loading.value = true
  errorText.value = ''
  try {
    const response = await apiFetch('/api/v1/analyses?page=1&page_size=20&sort_by=created_at&sort_order=desc')
    const payload = await response.json()
    const rows = payload.items || []
    recentItems.value = rows.slice(0, 5)
    stats.value.total = Number(payload.total || rows.length || 0)
    stats.value.malicious = rows.filter((row) => row?.final_decision?.is_malicious === true).length
    stats.value.normal = rows.filter((row) => row?.final_decision?.is_malicious === false).length
    stats.value.latestAt = rows[0]?.created_at || ''
  } catch (error) {
    errorText.value = `读取概览失败: ${error.message}`
    if (isAuthError(error)) {
      clearSession()
      await router.replace('/login')
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>导航总览</h2>
      <p>从这里快速进入上传分析和历史查询模块</p>
    </header>

    <div class="nav-grid">
      <RouterLink to="/app/upload" class="nav-card">
        <h3>上传分析</h3>
        <p>上传 `.eml` 文件并触发异步分析任务</p>
      </RouterLink>
      <RouterLink to="/app/history" class="nav-card">
        <h3>历史记录</h3>
        <p>检索历史分析、查看报告和原始数据</p>
      </RouterLink>
      <RouterLink to="/app/tuning" class="nav-card">
        <h3>调参管理</h3>
        <p>基于人工反馈手动运行融合调参并启用参数版本</p>
      </RouterLink>
    </div>

    <article class="panel">
      <h3>系统快照</h3>
      <p v-if="loading" class="hint">加载中...</p>
      <p v-if="errorText" class="error-text">{{ errorText }}</p>

      <div class="stat-grid" v-if="!loading">
        <div class="stat-item">
          <span>分析总数</span>
          <strong>{{ stats.total }}</strong>
        </div>
        <div class="stat-item">
          <span>近20条恶意</span>
          <strong class="danger">{{ stats.malicious }}</strong>
        </div>
        <div class="stat-item">
          <span>近20条正常</span>
          <strong class="safe">{{ stats.normal }}</strong>
        </div>
        <div class="stat-item">
          <span>最近分析时间</span>
          <strong>{{ formatDate(stats.latestAt) }}</strong>
        </div>
      </div>

      <div class="overview-charts" v-if="!loading">
        <div class="chart-card">
          <h4>风险占比</h4>
          <div class="risk-wrap">
            <div class="risk-ring" :style="riskRingStyle">
              <div class="risk-ring-inner">
                <strong>{{ riskSummary.maliciousPct }}%</strong>
                <span>恶意占比</span>
              </div>
            </div>
            <div class="risk-legend">
              <p><i class="dot dot-danger"></i>恶意：{{ stats.malicious }}（{{ riskSummary.maliciousPct }}%）</p>
              <p><i class="dot dot-safe"></i>正常：{{ stats.normal }}（{{ riskSummary.normalPct }}%）</p>
              <p><i class="dot dot-neutral"></i>未判定：{{ riskSummary.unknown }}</p>
            </div>
          </div>
        </div>

        <div class="chart-card">
          <h4>近期风险趋势</h4>
          <svg viewBox="0 0 320 120" class="trend-svg" v-if="trendLinePoints">
            <line x1="12" y1="12" x2="12" y2="108" class="axis-line" />
            <line x1="12" y1="108" x2="308" y2="108" class="axis-line" />
            <polyline :points="trendAreaPoints" class="trend-area" />
            <polyline :points="trendLinePoints" class="trend-line" />
          </svg>
          <p class="hint" v-else>数据不足，暂无趋势图</p>
        </div>
      </div>

      <h4>最近记录</h4>
      <ul class="recent-list" v-if="recentItems.length">
        <li v-for="item in recentItems" :key="item.id">
          <span>{{ formatDate(item.created_at) }}</span>
          <strong>{{ item.subject || '--' }}</strong>
          <em>{{ verdictLabel(item) }}</em>
        </li>
      </ul>
      <p v-else-if="!loading" class="hint">暂无记录</p>
    </article>
  </section>
</template>
