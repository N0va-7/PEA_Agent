<script setup>
import { computed, onMounted, ref } from 'vue'

import { apiFetch, isAuthError } from '../api'
import { clearSession } from '../session'

const urlDraft = ref('')
const running = ref(false)
const actionError = ref('')
const actionMessage = ref('')
const historyLoading = ref(false)
const historyItems = ref([])
const total = ref(0)
const selectedCheckId = ref('')
const selectedCheck = ref(null)

const latestBatch = ref(null)

const heroCards = computed(() => {
  const batch = latestBatch.value || {}
  const selected = selectedCheck.value || {}
  return [
    {
      label: '最近提交',
      value: batch.submitted_count ?? 0,
      tone: 'neutral',
    },
    {
      label: '记录复用',
      value: batch.reused_count ?? 0,
      tone: batch.reused_count ? 'safe' : 'neutral',
    },
    {
      label: '新建结果',
      value: batch.created_count ?? 0,
      tone: batch.created_count ? 'warning' : 'neutral',
    },
    {
      label: '当前结论',
      value: verdictLabel(selected.decision?.verdict),
      tone: verdictClass(selected.decision?.verdict),
    },
  ]
})

const summaryCards = computed(() => {
  const current = selectedCheck.value || {}
  const outputs = current.tool_outputs || {}
  const vt = outputs.url_reputation || {}
  const urlAnalysis = outputs.url_analysis || {}
  const firstItem = (vt.items || [])[0] || {}
  return [
    { label: 'VT 风险分', value: formatScore(vt.max_risk_score, 4), tone: firstItem.is_high_risk ? 'danger' : verdictClass(firstItem.risk_level) },
    { label: '模型分', value: formatScore(urlAnalysis.max_possibility, 4), tone: Number(urlAnalysis.max_possibility || 0) >= 0.75 ? 'warning' : 'neutral' },
    { label: '决策分', value: formatScore(current.decision?.score, 4), tone: verdictClass(current.decision?.verdict) },
    { label: '复用次数', value: current.request_count ?? 1, tone: (current.request_count || 1) > 1 ? 'safe' : 'neutral' },
  ]
})

function formatScore(value, digits = 4) {
  if (value === null || value === undefined || value === '') return '--'
  const num = Number(value)
  if (!Number.isFinite(num)) return String(value)
  return num.toFixed(digits).replace(/\.?0+$/, '')
}

function compactDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return `${dt.getFullYear()}/${dt.getMonth() + 1}/${dt.getDate()} ${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`
}

function verdictLabel(verdict) {
  const value = String(verdict || '').toLowerCase()
  if (value === 'malicious') return '恶意'
  if (value === 'suspicious') return '可疑'
  if (value === 'benign') return '正常'
  return '--'
}

function verdictClass(verdict) {
  const value = String(verdict || '').toLowerCase()
  if (value === 'malicious' || value === 'high') return 'danger'
  if (value === 'suspicious' || value === 'medium') return 'warning'
  if (value === 'benign' || value === 'low') return 'safe'
  return 'neutral'
}

function normalizeDraftLines() {
  return urlDraft.value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const response = await apiFetch('/api/v1/url-checks?page=1&page_size=20')
    const payload = await response.json()
    historyItems.value = payload.items || []
    total.value = Number(payload.total || 0)
    if (!selectedCheckId.value && historyItems.value.length) {
      await openCheck(historyItems.value[0].id)
    }
  } catch (error) {
    actionError.value = `读取 URL 检查历史失败: ${error.message}`
    if (isAuthError(error)) {
      clearSession()
      window.location.href = '/login'
    }
  } finally {
    historyLoading.value = false
  }
}

async function openCheck(checkId) {
  if (!checkId) return
  try {
    const response = await apiFetch(`/api/v1/url-checks/${checkId}`)
    const payload = await response.json()
    selectedCheckId.value = checkId
    selectedCheck.value = payload
  } catch (error) {
    actionError.value = `读取 URL 检查详情失败: ${error.message}`
  }
}

async function submitUrls() {
  actionError.value = ''
  actionMessage.value = ''
  latestBatch.value = null
  const urls = normalizeDraftLines()
  if (!urls.length) {
    actionError.value = '请至少输入一条 URL'
    return
  }

  running.value = true
  try {
    const response = await apiFetch('/api/v1/url-checks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls }),
    })
    const payload = await response.json()
    latestBatch.value = payload
    actionMessage.value = payload.reused_count ? `本次复用了 ${payload.reused_count} 条已有 URL 记录` : 'URL 风险分析完成'
    await loadHistory()
    if (payload.items?.length) {
      await openCheck(payload.items[0].id)
    }
  } catch (error) {
    actionError.value = `提交失败: ${error.message}`
    if (isAuthError(error)) {
      clearSession()
      window.location.href = '/login'
    }
  } finally {
    running.value = false
  }
}

onMounted(loadHistory)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>URL 风险分析</h2>
      <p>直接提交 URL，复用 VT 信誉、URL 模型和决策规则，命中已分析记录时直接复用数据库结果。</p>
    </header>

    <article class="panel page-banner-panel">
      <div class="page-banner">
        <div class="page-banner-copy">
          <span class="page-banner-kicker">URL Console</span>
          <h3>独立 URL 风险检查台</h3>
          <p>面向单条或少量 URL 的快速核验入口。结果会写入 URL 历史库，再次提交同一归一化 URL 时直接返回已分析记录。</p>
        </div>
        <div class="page-banner-icon url">
          <svg viewBox="0 0 64 64" aria-hidden="true">
            <defs>
              <linearGradient id="urlBannerBg" x1="0%" x2="100%" y1="0%" y2="100%">
                <stop offset="0%" stop-color="#16508c" />
                <stop offset="100%" stop-color="#0b2f52" />
              </linearGradient>
            </defs>
            <rect x="8" y="8" width="48" height="48" rx="10" fill="url(#urlBannerBg)" />
            <path d="M24 27a7 7 0 0 1 7-7h6a7 7 0 1 1 0 14h-4" fill="none" stroke="#f8fbff" stroke-width="3" stroke-linecap="round" />
            <path d="M40 37a7 7 0 0 1-7 7h-6a7 7 0 1 1 0-14h4" fill="none" stroke="#cfe3ff" stroke-width="3" stroke-linecap="round" />
            <path d="M27 37 37 27" fill="none" stroke="#7dd3fc" stroke-width="2.6" stroke-linecap="round" />
          </svg>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="ingest-console">
        <section class="ingest-primary">
          <div class="section-head">
            <div>
              <h3>URL 提交台</h3>
              <p>支持按行输入多个 URL。系统会按归一化结果去重，并优先复用已有分析记录。</p>
            </div>
          </div>

          <label class="field-label">
            <span>URL 列表</span>
            <textarea v-model="urlDraft" rows="8" placeholder="https://example.com/login&#10;https://secure.example.com/verify"></textarea>
          </label>

          <div class="upload-actions">
            <button :disabled="running" @click="submitUrls">{{ running ? '分析中...' : '开始检查' }}</button>
          </div>

          <p v-if="actionMessage" class="success-text">{{ actionMessage }}</p>
          <p v-if="actionError" class="error-text">{{ actionError }}</p>
        </section>

        <aside class="ingest-side">
          <section class="hero-kpis">
            <article v-for="card in heroCards" :key="card.label" class="summary-card hero-kpi-card">
              <span>{{ card.label }}</span>
              <strong :class="card.tone">{{ card.value }}</strong>
            </article>
          </section>

          <section class="mini-panel">
            <div class="section-head">
              <div>
                <h4>复用说明</h4>
                <p>URL 和附件样本都优先复用已有分析记录。</p>
              </div>
            </div>
            <ul class="evidence-list">
              <li>同一归一化 URL 会直接复用主库中的 URL 分析结果。</li>
              <li>附件静态沙箱已按样本 SHA256 复用已有分析结果。</li>
              <li>VT 子查询仍会复用本地缓存，不重复消耗同一条 URL 的实时配额。</li>
            </ul>
          </section>
        </aside>
      </div>
    </article>

    <div class="split-layout url-console-layout">
      <article class="panel">
        <div class="list-head">
          <h3>URL 历史</h3>
          <p class="hint" v-if="historyLoading">加载中...</p>
          <p class="hint" v-else>共 {{ total }} 条</p>
        </div>
        <ul class="history-records url-history-list" v-if="historyItems.length">
          <li v-for="item in historyItems" :key="item.id" class="history-item">
            <article
              class="history-select url-check-card"
              :class="{ selected: selectedCheckId === item.id }"
              role="button"
              tabindex="0"
              @click="openCheck(item.id)"
            >
              <div class="history-select-top">
                <strong>{{ item.normalized_url }}</strong>
                <em class="badge" :class="verdictClass(item.decision?.verdict)">{{ verdictLabel(item.decision?.verdict) }}</em>
              </div>
              <div class="history-select-meta url-check-meta">
                <span>{{ compactDate(item.updated_at) }}</span>
                <span>请求 {{ item.request_count || 1 }} 次</span>
              </div>
              <div class="history-select-foot">
                <span class="history-foot-label">{{ item.is_cached_result ? '本次命中复用' : 'URL 检查记录' }}</span>
                <span class="badge neutral">ID {{ item.id.slice(0, 8) }}</span>
              </div>
            </article>
          </li>
        </ul>
        <p v-else class="hint">暂无 URL 历史记录</p>
      </article>

      <article class="panel detail-panel">
        <p v-if="!selectedCheck" class="hint">从左侧选择一条 URL 记录查看详情</p>
        <template v-else>
          <div class="detail-head">
            <div>
              <h3>{{ selectedCheck.normalized_url }}</h3>
              <p>{{ selectedCheck.requested_url }}</p>
            </div>
            <span class="badge" :class="verdictClass(selectedCheck.decision?.verdict)">{{ verdictLabel(selectedCheck.decision?.verdict) }}</span>
          </div>

          <section class="summary-strip">
            <article v-for="card in summaryCards" :key="card.label" class="summary-card">
              <span>{{ card.label }}</span>
              <strong :class="card.tone">{{ card.value }}</strong>
            </article>
          </section>

          <section class="detail-section">
            <h4>URL 情报</h4>
            <div class="meta-grid">
              <div>
                <label>更新时间</label>
                <p>{{ compactDate(selectedCheck.updated_at) }}</p>
              </div>
              <div>
                <label>数据库复用</label>
                <p>{{ (latestBatch?.items || []).some((item) => item.id === selectedCheck.id && item.is_cached_result) ? '是' : '否' }}</p>
              </div>
              <div>
                <label>VT 摘要</label>
                <p>{{ selectedCheck.tool_outputs?.url_reputation?.summary || '--' }}</p>
              </div>
              <div>
                <label>模型摘要</label>
                <p>{{ selectedCheck.tool_outputs?.url_analysis?.summary || '--' }}</p>
              </div>
            </div>
          </section>

          <section class="detail-section">
            <h4>逐项结果</h4>
            <ul class="entity-list" v-if="selectedCheck.tool_outputs?.url_reputation?.items?.length">
              <li v-for="item in selectedCheck.tool_outputs.url_reputation.items" :key="item.url" class="entity-card">
                <div class="entity-head">
                  <strong>{{ item.url }}</strong>
                  <span class="badge" :class="item.is_high_risk ? 'danger' : verdictClass(item.risk_level)">{{ item.is_high_risk ? '高危' : item.risk_level || '--' }}</span>
                </div>
                <div class="entity-meta">
                  <span>cache={{ item.cache_status || '--' }}</span>
                  <span>malicious={{ item.last_analysis_stats?.malicious || 0 }}</span>
                  <span>suspicious={{ item.last_analysis_stats?.suspicious || 0 }}</span>
                  <span>risk={{ formatScore(item.risk_score, 4) }}</span>
                </div>
                <p class="entity-summary">{{ item.summary || '--' }}</p>
              </li>
            </ul>
          </section>

          <section class="detail-section">
            <h4>决策结果</h4>
            <ul class="evidence-list" v-if="selectedCheck.decision?.reasons?.length">
              <li v-for="reason in selectedCheck.decision.reasons" :key="reason">{{ reason }}</li>
            </ul>
            <div class="meta-grid">
              <div>
                <label>主风险源</label>
                <p>{{ selectedCheck.decision?.primary_risk_source || '--' }}</p>
              </div>
              <div>
                <label>处置建议</label>
                <p>{{ selectedCheck.decision?.recommended_action || '--' }}</p>
              </div>
            </div>
          </section>
        </template>
      </article>
    </div>
  </section>
</template>
