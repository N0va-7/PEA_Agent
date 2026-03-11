<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiFetch, isAuthError } from '../api'
import { clearSession } from '../session'

const router = useRouter()
const loading = ref(false)
const errorText = ref('')
const recentItems = ref([])
const runtimeInfo = ref(null)
const totals = ref({ total: 0, malicious: 0, suspicious: 0, benign: 0 })

const stageCards = computed(() => [
  { label: '邮件解析', desc: '拆出主题、正文、附件与原始头部。', tone: 'safe' },
  { label: 'URL 信誉', desc: '查询 VirusTotal URL 情报并结合本地缓存。', tone: 'warning' },
  { label: '内容复核', desc: '对正文、HTML 和诱导话术做结构化复核。', tone: 'danger' },
  { label: '报告输出', desc: '输出结构化决策与 Markdown 报告。', tone: 'neutral' },
])
const totalVisible = computed(() => totals.value.malicious + totals.value.suspicious + totals.value.benign)
const riskSegments = computed(() => {
  const total = Math.max(1, totalVisible.value || 1)
  return [
    { label: '恶意', value: totals.value.malicious, color: 'var(--danger)', ratio: totals.value.malicious / total },
    { label: '可疑', value: totals.value.suspicious, color: 'var(--warning)', ratio: totals.value.suspicious / total },
    { label: '正常', value: totals.value.benign, color: 'var(--safe)', ratio: totals.value.benign / total },
  ]
})
const riskDonutStyle = computed(() => {
  const total = Math.max(1, totalVisible.value || 1)
  const malicious = ((totals.value.malicious / total) * 100).toFixed(2)
  const suspicious = (((totals.value.malicious + totals.value.suspicious) / total) * 100).toFixed(2)
  return {
    background: `conic-gradient(
      var(--danger) 0 ${malicious}%,
      var(--warning) ${malicious}% ${suspicious}%,
      var(--safe) ${suspicious}% 100%
    )`,
  }
})
const recentTrend = computed(() => {
  const rows = [...recentItems.value].reverse()
  if (!rows.length) return []
  return rows.map((item, index) => ({
    x: index,
    y: Number(item?.decision?.score || 0),
    label: item?.email?.subject || '--',
    verdict: item?.decision?.verdict || '',
  }))
})
const trendPath = computed(() => {
  const points = recentTrend.value
  if (!points.length) return ''
  const width = 420
  const height = 160
  const step = points.length === 1 ? 0 : width / (points.length - 1)
  return points
    .map((point, index) => {
      const x = index * step
      const y = height - point.y * 130 - 10
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
})
const trendArea = computed(() => {
  const path = trendPath.value
  const points = recentTrend.value
  if (!path || !points.length) return ''
  const width = 420
  const height = 160
  if (points.length === 1) {
    const y = height - points[0].y * 130 - 10
    return `M 0 ${height} L 0 ${y.toFixed(2)} L ${width} ${y.toFixed(2)} L ${width} ${height} Z`
  }
  return `${path} L 420 160 L 0 160 Z`
})

function formatDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function formatScore(value, digits = 2) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '--'
  return num.toFixed(digits).replace(/\.?0+$/, '')
}

function verdictColor(verdict) {
  const value = String(verdict || '').toLowerCase()
  if (value === 'malicious') return 'var(--danger)'
  if (value === 'suspicious') return 'var(--warning)'
  if (value === 'benign') return 'var(--safe)'
  return 'var(--neutral)'
}

function verdictLabel(item) {
  const verdict = String(item?.decision?.verdict || '').toLowerCase()
  if (verdict === 'malicious') return '恶意'
  if (verdict === 'suspicious') return '可疑'
  if (verdict === 'benign') return '正常'
  return '未判定'
}

function verdictClass(item) {
  const verdict = String(item?.decision?.verdict || '').toLowerCase()
  if (verdict === 'malicious') return 'danger'
  if (verdict === 'suspicious') return 'warning'
  if (verdict === 'benign') return 'safe'
  return 'neutral'
}

async function loadOverview() {
  loading.value = true
  errorText.value = ''
  try {
    const [analysesRes, runtimeRes] = await Promise.allSettled([
      apiFetch('/api/v1/analyses?page=1&page_size=20&sort_by=created_at&sort_order=desc'),
      apiFetch('/api/v1/system/runtime-info'),
    ])

    if (analysesRes.status !== 'fulfilled') {
      throw analysesRes.reason
    }

    const payload = await analysesRes.value.json()
    const rows = payload.items || []
    recentItems.value = rows.slice(0, 6)
    totals.value.total = Number(payload.total || rows.length || 0)
    totals.value.malicious = rows.filter((row) => row?.decision?.verdict === 'malicious').length
    totals.value.suspicious = rows.filter((row) => row?.decision?.verdict === 'suspicious').length
    totals.value.benign = rows.filter((row) => row?.decision?.verdict === 'benign').length

    if (runtimeRes.status === 'fulfilled') {
      runtimeInfo.value = await runtimeRes.value.json()
    }
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
      <p>主流程已经切到 URL 信誉、内容复核、附件沙箱和统一决策输出。</p>
    </header>

    <div class="nav-grid">
      <RouterLink to="/app/upload" class="nav-card">
        <h3>上传分析</h3>
        <p>上传 `.eml` 并查看新的 Agent workflow 时间线。</p>
      </RouterLink>
      <RouterLink to="/app/history" class="nav-card">
        <h3>历史记录</h3>
        <p>查看 URL 信誉、内容复核、附件结果与最终决策。</p>
      </RouterLink>
      <RouterLink to="/app/static-sandbox" class="nav-card">
        <h3>静态沙箱扫描</h3>
        <p>独立上传样本，查看静态规则命中与风险分。</p>
      </RouterLink>
      <RouterLink to="/app/static-rules" class="nav-card">
        <h3>静态沙箱规则</h3>
        <p>查看或维护沙箱规则版本与规则内容。</p>
      </RouterLink>
    </div>

    <article class="panel">
      <div class="section-head">
        <h3>分析流程</h3>
        <p>工具层能力与主工作流解耦，结果统一落在同一份分析详情里。</p>
      </div>
      <div class="workflow-strip">
        <div v-for="card in stageCards" :key="card.label" class="workflow-card">
          <span :class="card.tone">{{ card.label }}</span>
          <strong>{{ card.desc }}</strong>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="section-head">
        <h3>系统快照</h3>
        <p>以下统计基于最近拉取到的分析列表，不做额外推断。</p>
      </div>
      <p v-if="loading" class="hint">加载中...</p>
      <p v-if="errorText" class="error-text">{{ errorText }}</p>

      <div class="stat-grid" v-if="!loading">
        <div class="stat-item">
          <span>总分析数</span>
          <strong>{{ totals.total }}</strong>
        </div>
        <div class="stat-item">
          <span>近20条恶意</span>
          <strong class="danger">{{ totals.malicious }}</strong>
        </div>
        <div class="stat-item">
          <span>近20条可疑</span>
          <strong class="warning">{{ totals.suspicious }}</strong>
        </div>
        <div class="stat-item">
          <span>近20条正常</span>
          <strong class="safe">{{ totals.benign }}</strong>
        </div>
        <div class="stat-item">
          <span>近20条可见记录</span>
          <strong>{{ totalVisible }}</strong>
        </div>
      </div>

      <div class="overview-charts" v-if="!loading && totalVisible">
        <article class="chart-card">
          <h4>风险分布</h4>
          <div class="risk-wrap">
            <div class="risk-ring" :style="riskDonutStyle">
              <div class="risk-ring-inner">
                <strong>{{ totalVisible }}</strong>
                <span>近20条样本</span>
              </div>
            </div>
            <div class="risk-legend">
              <p v-for="segment in riskSegments" :key="segment.label">
                <span class="dot" :style="{ background: segment.color }"></span>
                {{ segment.label }} {{ segment.value }} 条
                <strong>{{ formatScore(segment.ratio * 100, 1) }}%</strong>
              </p>
            </div>
          </div>
        </article>

        <article class="chart-card">
          <h4>近期风险趋势</h4>
          <svg v-if="recentTrend.length" viewBox="0 0 420 160" class="trend-svg" preserveAspectRatio="none">
            <defs>
              <linearGradient id="trendFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="rgba(15, 76, 129, 0.28)" />
                <stop offset="100%" stop-color="rgba(15, 76, 129, 0.04)" />
              </linearGradient>
            </defs>
            <line class="axis-line" x1="0" y1="150" x2="420" y2="150" />
            <path class="trend-area" :d="trendArea" fill="url(#trendFill)" />
            <path class="trend-line" :d="trendPath" />
            <circle
              v-for="(point, index) in recentTrend"
              :key="`${point.label}-${index}`"
              :cx="recentTrend.length === 1 ? 210 : (420 / (recentTrend.length - 1)) * index"
              :cy="160 - point.y * 130 - 10"
              r="4"
              :fill="verdictColor(point.verdict)"
            />
          </svg>
          <p v-else class="hint">暂无足够样本绘制趋势</p>
        </article>
      </div>

      <h4>最近记录</h4>
      <ul class="overview-recent-list" v-if="recentItems.length">
        <li v-for="item in recentItems" :key="item.id">
          <div class="overview-recent-top">
            <strong>{{ item.email?.subject || '--' }}</strong>
            <em class="badge" :class="verdictClass(item)">{{ verdictLabel(item) }}</em>
          </div>
          <div class="overview-recent-meta">
            <span>{{ formatDate(item.created_at) }}</span>
            <span>{{ item.email?.sender || '--' }}</span>
            <span>风险分 {{ formatScore(item.decision?.score, 4) }}</span>
          </div>
        </li>
      </ul>
      <p v-else-if="!loading" class="hint">暂无分析记录</p>

      <h4>后端连接信息（脱敏）</h4>
      <div class="meta-grid" v-if="runtimeInfo">
        <div>
          <label>数据库驱动</label>
          <p>{{ runtimeInfo.database?.driver || '--' }}</p>
        </div>
        <div>
          <label>数据库地址</label>
          <p>{{ runtimeInfo.database?.display || '--' }}</p>
        </div>
        <div>
          <label>任务队列</label>
          <p>{{ runtimeInfo.queue?.backend || '--' }}</p>
        </div>
        <div>
          <label>Redis 地址</label>
          <p>{{ runtimeInfo.queue?.display || '--' }}</p>
        </div>
      </div>
    </article>
  </section>
</template>
