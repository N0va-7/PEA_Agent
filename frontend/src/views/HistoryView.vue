<script setup>
import MarkdownIt from 'markdown-it'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { apiFetch, isAuthError } from '../api'
import { clearSession } from '../session'

const route = useRoute()
const router = useRouter()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const senderFilter = ref('')
const subjectFilter = ref('')
const createdFrom = ref('')
const createdTo = ref('')
const sortBy = ref('created_at')
const sortOrder = ref('desc')
const page = ref(1)
const pageSize = ref(10)

const historyLoading = ref(false)
const historyError = ref('')
const historyMessage = ref('')
const historyItems = ref([])
const total = ref(0)

const selectedAnalysisId = ref('')
const detailLoading = ref(false)
const analysis = ref(null)
const feedbackLabel = ref('')
const feedbackNote = ref('')
const feedbackSaving = ref(false)
const feedbackMessage = ref('')
const feedbackError = ref('')
const activeReportSection = ref('')
const activeDetailTab = ref('overview')

const pageCount = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize.value)))
const email = computed(() => analysis.value?.email || {})
const outputs = computed(() => analysis.value?.tool_outputs || {})
const decision = computed(() => analysis.value?.decision || {})
const report = computed(() => analysis.value?.report || {})
const urlItems = computed(() => outputs.value?.url_reputation?.items || [])
const contentReview = computed(() => outputs.value?.content_review || {})
const attachmentItems = computed(() => outputs.value?.attachment_analysis?.items || [])
const decisionTrace = computed(() => decision.value?.decision_trace || [])
const outputCards = computed(() => [
  {
    label: 'URL',
    value: outputs.value?.url_extraction?.normalized_urls?.length || 0,
    tone: urlItems.value.some((item) => item?.is_high_risk) ? 'danger' : 'neutral',
  },
  {
    label: 'VT 高危',
    value: vtHighRiskUrls.value.length,
    tone: vtHighRiskUrls.value.length ? 'danger' : 'safe',
  },
  {
    label: '内容分',
    value: formatScore(contentReview.value?.score, 2),
    tone: verdictClass(contentReview.value?.verdict),
  },
  {
    label: '决策分',
    value: formatScore(decision.value?.score, 4),
    tone: verdictClass(decision.value?.verdict),
  },
])
const vtShortCircuit = computed(() => {
  if (decision.value?.primary_risk_source === 'vt_url_reputation') return true
  return decisionTrace.value.some((item) => item?.source === 'decision_engine' && item?.mode === 'short_circuit_vt_url')
})
const vtHighRiskUrls = computed(() => outputs.value?.url_reputation?.high_risk_urls || [])

const reportSections = computed(() => {
  const markdown = String(report.value?.markdown || '').trim()
  if (!markdown) return []

  const normalized = markdown.replace(/\r\n/g, '\n')
  const parts = normalized.split(/\n(?=##\s+)/g).filter(Boolean)
  const sections = []

  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue
    const titleMatch = trimmed.match(/^##\s+(.+)$/m)
    const title = titleMatch ? titleMatch[1].trim() : '报告'
    const id = title
      .toLowerCase()
      .replace(/[^\w\u4e00-\u9fff]+/g, '-')
      .replace(/^-+|-+$/g, '')
    sections.push({
      id: id || `section-${sections.length + 1}`,
      title,
      html: md.render(trimmed),
    })
  }

  if (!sections.length) {
    sections.push({
      id: 'report',
      title: '报告',
      html: md.render(normalized),
    })
  }
  return sections
})

const currentReportSection = computed(() => {
  if (!reportSections.value.length) return null
  return reportSections.value.find((item) => item.id === activeReportSection.value) || reportSections.value[0]
})

function formatDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function compactDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return `${dt.getFullYear()}/${dt.getMonth() + 1}/${dt.getDate()} ${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`
}

function truncate(text, max = 48) {
  const raw = String(text || '')
  return raw.length > max ? `${raw.slice(0, max)}...` : raw || '--'
}

function formatScore(value, digits = 4) {
  if (value === null || value === undefined || value === '') return '--'
  const num = Number(value)
  if (!Number.isFinite(num)) return String(value)
  return num.toFixed(digits).replace(/\.?0+$/, '')
}

function verdictLabel(verdict) {
  const value = String(verdict || '').toLowerCase()
  if (value === 'malicious') return '恶意'
  if (value === 'suspicious') return '可疑'
  if (value === 'benign') return '正常'
  return '未判定'
}

function verdictClass(verdict) {
  const value = String(verdict || '').toLowerCase()
  if (value === 'malicious') return 'danger'
  if (value === 'suspicious') return 'warning'
  if (value === 'benign') return 'safe'
  return 'neutral'
}

function sourceLabel(source) {
  const value = String(source || '')
  return {
    url_reputation_vt: 'VT URL 信誉',
    url_model_analysis: 'URL 模型',
    content_review: '正文内容复核',
    attachment_sandbox: '附件沙箱',
    decision_engine: '决策引擎',
  }[value] || value || '--'
}

function modeLabel(mode) {
  const value = String(mode || '')
  return {
    short_circuit_vt_url: 'VT 高危短路',
    short_circuit_attachment: '附件恶意短路',
    content_strong_evidence: '内容强证据',
    url_model_high: 'URL 高分',
    content_malicious_soft: '内容偏恶意',
    content_suspicious: '内容可疑',
    attachment_suspicious: '附件可疑',
    baseline: '基线判断',
  }[value] || value
}

function riskLevelLabel(level) {
  const value = String(level || '').toLowerCase()
  if (value === 'high') return '高危'
  if (value === 'medium') return '中危'
  if (value === 'low') return '低危'
  return '未知'
}

function traceSummary(item) {
  if (!item || typeof item !== 'object') return []
  const parts = []
  if (item.mode) parts.push(modeLabel(item.mode))
  if (item.verdict) parts.push(`结论 ${verdictLabel(item.verdict)}`)
  if (item.score !== undefined) parts.push(`分数 ${formatScore(item.score, 4)}`)
  if (Array.isArray(item.cache_sources) && item.cache_sources.length) parts.push(`缓存 ${item.cache_sources.join(', ')}`)
  if (Array.isArray(item.high_risk_urls) && item.high_risk_urls.length) parts.push(`高危 URL ${item.high_risk_urls.length}`)
  return parts
}

function itemMetaList(item) {
  const items = []
  if (Array.isArray(item?.categories)) items.push(...item.categories)
  if (Array.isArray(item?.tags)) items.push(...item.tags)
  return items.filter(Boolean)
}

function selectReportSection(sectionId) {
  activeReportSection.value = sectionId
}

function toIsoOrEmpty(value) {
  if (!value) return ''
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? '' : dt.toISOString()
}

async function loadHistory({ resetPage = false } = {}) {
  historyLoading.value = true
  historyError.value = ''
  if (resetPage) page.value = 1
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    })
    if (subjectFilter.value.trim()) params.set('subject', subjectFilter.value.trim())
    if (senderFilter.value.trim()) params.set('sender', senderFilter.value.trim())
    if (createdFrom.value) params.set('created_from', toIsoOrEmpty(createdFrom.value))
    if (createdTo.value) params.set('created_to', toIsoOrEmpty(createdTo.value))

    const response = await apiFetch(`/api/v1/analyses?${params.toString()}`)
    const payload = await response.json()
    historyItems.value = payload.items || []
    total.value = Number(payload.total || 0)
    page.value = Number(payload.page || page.value)
    pageSize.value = Number(payload.page_size || pageSize.value)
  } catch (error) {
    historyError.value = `读取历史失败: ${error.message}`
    if (isAuthError(error)) {
      clearSession()
      await router.replace('/login')
    }
  } finally {
    historyLoading.value = false
  }
}

async function openAnalysis(analysisId, { updateRoute = true } = {}) {
  if (!analysisId) return
  detailLoading.value = true
  historyError.value = ''
  feedbackError.value = ''
  feedbackMessage.value = ''
  try {
    if (updateRoute && route.params.analysisId !== analysisId) {
      await router.push(`/app/history/${analysisId}`)
    }
    const response = await apiFetch(`/api/v1/analyses/${analysisId}`)
    const payload = await response.json()
    analysis.value = payload
    selectedAnalysisId.value = analysisId
    activeDetailTab.value = 'overview'
    feedbackLabel.value = payload.review_label || ''
    feedbackNote.value = payload.review_note || ''
  } catch (error) {
    historyError.value = `读取分析详情失败: ${error.message}`
    if (isAuthError(error)) {
      clearSession()
      await router.replace('/login')
    }
  } finally {
    detailLoading.value = false
  }
}

async function saveFeedback() {
  if (!selectedAnalysisId.value) return
  feedbackSaving.value = true
  feedbackMessage.value = ''
  feedbackError.value = ''
  try {
    const response = await apiFetch(`/api/v1/analyses/${selectedAnalysisId.value}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        review_label: feedbackLabel.value || null,
        review_note: feedbackNote.value || null,
      }),
    })
    const payload = await response.json()
    feedbackMessage.value = '反馈已保存'
    if (analysis.value) {
      analysis.value.review_label = payload.review_label
      analysis.value.review_note = payload.review_note
      analysis.value.reviewed_by = payload.reviewed_by
      analysis.value.reviewed_at = payload.reviewed_at
    }
    await loadHistory()
  } catch (error) {
    feedbackError.value = `保存反馈失败: ${error.message}`
    if (isAuthError(error)) {
      clearSession()
      await router.replace('/login')
    }
  } finally {
    feedbackSaving.value = false
  }
}

async function deleteAnalysis(analysisId) {
  if (!analysisId) return
  if (!window.confirm(`确认删除该记录（${analysisId}）？`)) return
  historyError.value = ''
  historyMessage.value = ''
  try {
    const response = await apiFetch(`/api/v1/analyses/${analysisId}`, { method: 'DELETE' })
    const payload = await response.json()
    historyMessage.value = `已删除 ${payload.deleted_count || 0} 条记录。`
    if (selectedAnalysisId.value === analysisId) {
      selectedAnalysisId.value = ''
      analysis.value = null
      await router.push('/app/history')
    }
    await loadHistory()
  } catch (error) {
    historyError.value = `删除失败: ${error.message}`
  }
}

watch(
  () => route.params.analysisId,
  async (analysisId) => {
    if (typeof analysisId === 'string' && analysisId) {
      await openAnalysis(analysisId, { updateRoute: false })
    } else {
      selectedAnalysisId.value = ''
      analysis.value = null
    }
  },
  { immediate: true }
)

watch(
  reportSections,
  (sections) => {
    if (!sections.length) {
      activeReportSection.value = ''
      return
    }
    if (!sections.some((item) => item.id === activeReportSection.value)) {
      activeReportSection.value = sections[0].id
    }
  },
  { immediate: true }
)

onMounted(async () => {
  await loadHistory()
})
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>历史记录</h2>
      <p>查看 URL 信誉、内容复核、附件结果和最终决策。</p>
    </header>

    <div class="panel">
      <div class="filters-row">
        <input v-model="senderFilter" placeholder="筛选发件人" />
        <input v-model="subjectFilter" placeholder="筛选主题" />
        <input v-model="createdFrom" type="datetime-local" />
        <input v-model="createdTo" type="datetime-local" />
        <button @click="loadHistory({ resetPage: true })">查询</button>
      </div>
      <p v-if="historyMessage" class="success-text">{{ historyMessage }}</p>
      <p v-if="historyError" class="error-text">{{ historyError }}</p>
    </div>

    <div class="split-layout">
      <article class="panel">
        <div class="list-head">
          <h3>分析列表</h3>
          <p class="hint" v-if="historyLoading">加载中...</p>
        </div>
        <ul class="history-records" v-if="historyItems.length">
          <li v-for="item in historyItems" :key="item.id" class="history-item">
            <article
              class="history-select"
              :class="{ selected: selectedAnalysisId === item.id }"
              role="button"
              tabindex="0"
              @click="openAnalysis(item.id)"
            >
              <div class="history-select-top">
                <strong>{{ item.email?.subject || '--' }}</strong>
                <em class="badge" :class="verdictClass(item.decision?.verdict)">{{ verdictLabel(item.decision?.verdict) }}</em>
              </div>
              <div class="history-select-meta">
                <span>{{ compactDate(item.created_at) }}</span>
                <span>{{ item.email?.sender || '--' }}</span>
              </div>
              <div class="history-select-foot">
                <span class="history-foot-label">邮件分析</span>
                <button class="ghost small history-delete" @click.stop="deleteAnalysis(item.id)">删除</button>
              </div>
            </article>
          </li>
        </ul>
        <p v-else-if="!historyLoading" class="hint">暂无历史记录</p>

        <div class="pagination">
          <button class="ghost small" :disabled="page <= 1" @click="page -= 1; loadHistory()">上一页</button>
          <span>{{ page }} / {{ pageCount }}</span>
          <button class="ghost small" :disabled="page >= pageCount" @click="page += 1; loadHistory()">下一页</button>
        </div>
      </article>

      <article class="panel detail-panel">
        <p v-if="detailLoading" class="hint">加载详情中...</p>
        <p v-else-if="!analysis" class="hint">从左侧选择一条分析记录查看详情</p>
        <template v-else>
          <div class="detail-head">
            <div>
              <h3>{{ email.subject || '--' }}</h3>
              <p>{{ email.sender || '--' }} → {{ email.recipient || '--' }}</p>
            </div>
            <span class="badge" :class="verdictClass(decision.verdict)">{{ verdictLabel(decision.verdict) }}</span>
          </div>

          <section class="summary-strip">
            <article v-for="card in outputCards" :key="card.label" class="summary-card">
              <span>{{ card.label }}</span>
              <strong :class="card.tone">{{ card.value }}</strong>
            </article>
          </section>

          <div class="detail-tabs">
            <button class="ghost small" :class="{ active: activeDetailTab === 'overview' }" @click="activeDetailTab = 'overview'">概览</button>
            <button class="ghost small" :class="{ active: activeDetailTab === 'signals' }" @click="activeDetailTab = 'signals'">信号详情</button>
            <button class="ghost small" :class="{ active: activeDetailTab === 'decision' }" @click="activeDetailTab = 'decision'">决策与反馈</button>
            <button class="ghost small" :class="{ active: activeDetailTab === 'report' }" @click="activeDetailTab = 'report'">分段报告</button>
          </div>

          <template v-if="activeDetailTab === 'overview'">
            <section class="detail-section">
              <h4>邮件概览</h4>
              <div class="meta-grid">
                <div>
                  <label>Message-ID</label>
                  <p>{{ email.message_id || '--' }}</p>
                </div>
                <div>
                  <label>URL 数量</label>
                  <p>{{ outputs.url_extraction?.normalized_urls?.length || 0 }}</p>
                </div>
                <div>
                  <label>附件数量</label>
                  <p>{{ email.attachments?.length || 0 }}</p>
                </div>
                <div>
                  <label>分析时间</label>
                  <p>{{ formatDate(analysis.created_at) }}</p>
                </div>
              </div>
            </section>

            <section class="detail-section">
              <h4>关键结论</h4>
              <ul class="evidence-list" v-if="decision.reasons?.length">
                <li v-for="reason in decision.reasons" :key="reason">{{ reason }}</li>
              </ul>
              <p v-else class="hint">当前记录没有额外决策原因。</p>
            </section>
          </template>

          <template v-else-if="activeDetailTab === 'signals'">
            <section class="detail-section">
              <h4>URL 提取与 VT 信誉</h4>
              <p class="hint">{{ outputs.url_reputation?.summary || '暂无 URL 信誉摘要' }}</p>
              <div v-if="vtShortCircuit" class="vt-alert">
                <strong>VT 直接触发恶意</strong>
                <p>
                  VirusTotal 已将
                  <span v-if="vtHighRiskUrls.length">{{ vtHighRiskUrls[0] }}</span>
                  <span v-else>该 URL</span>
                  标记为高危，系统已按短路规则直接判定为恶意。
                </p>
              </div>
              <ul class="entity-list" v-if="urlItems.length">
                <li v-for="item in urlItems" :key="item.url" class="entity-card">
                  <div class="entity-head">
                    <strong>{{ item.url }}</strong>
                    <span class="badge" :class="item.is_high_risk ? 'danger' : verdictClass(item.risk_level === 'medium' ? 'suspicious' : item.risk_level === 'low' ? 'benign' : '')">
                      {{ item.is_high_risk ? '直接触发恶意' : riskLevelLabel(item.risk_level) }}
                    </span>
                  </div>
                  <div class="entity-meta">
                    <span>cache={{ item.cache_status || '--' }}</span>
                    <span>malicious={{ item.last_analysis_stats?.malicious || 0 }}</span>
                    <span>suspicious={{ item.last_analysis_stats?.suspicious || 0 }}</span>
                  </div>
                  <p class="entity-summary">{{ item.summary || '--' }}</p>
                  <div v-if="itemMetaList(item).length" class="chip-row">
                    <span v-for="tag in itemMetaList(item)" :key="`${item.url}-${tag}`" class="chip">{{ tag }}</span>
                  </div>
                </li>
              </ul>
            </section>

            <section class="detail-section">
              <h4>正文内容复核</h4>
              <p><strong>结论：</strong>{{ verdictLabel(contentReview.verdict) }}</p>
              <p><strong>分数：</strong>{{ contentReview.score ?? '--' }}</p>
              <ul class="evidence-list" v-if="contentReview.reasons?.length">
                <li v-for="reason in contentReview.reasons" :key="reason">{{ reason }}</li>
              </ul>
            </section>

            <section class="detail-section">
              <h4>附件沙箱</h4>
              <p class="hint">{{ outputs.attachment_analysis?.summary || '暂无附件信息' }}</p>
              <ul class="entity-list" v-if="attachmentItems.length">
                <li v-for="item in attachmentItems" :key="item.filename" class="entity-card">
                  <div class="entity-head">
                    <strong>{{ item.filename }}</strong>
                    <span class="badge" :class="verdictClass(item.verdict)">{{ verdictLabel(item.verdict) }}</span>
                  </div>
                  <div class="entity-meta">
                    <span>分数 {{ formatScore(item.score, 4) }}</span>
                    <span v-if="item.artifacts?.length">产物 {{ item.artifacts.length }}</span>
                  </div>
                  <p class="entity-summary">{{ item.summary || '--' }}</p>
                </li>
              </ul>
            </section>
          </template>

          <template v-else-if="activeDetailTab === 'decision'">
            <section class="detail-section">
              <h4>最终决策</h4>
              <p v-if="vtShortCircuit" class="vt-short-circuit-text">当前结论由 VT 高危 URL 直接触发。</p>
              <div class="meta-grid">
                <div>
                  <label>主风险源</label>
                  <p>{{ decision.primary_risk_source || '--' }}</p>
                </div>
                <div>
                  <label>风险分</label>
                  <p>{{ decision.score ?? '--' }}</p>
                </div>
                <div>
                  <label>处置建议</label>
                  <p>{{ decision.recommended_action || '--' }}</p>
                </div>
              </div>
              <ul class="trace-list" v-if="decisionTrace.length">
                <li v-for="(item, idx) in decisionTrace" :key="`${item.source}-${idx}`">
                  <div class="trace-head">
                    <span>{{ sourceLabel(item.source) }}</span>
                    <strong>{{ item.mode ? modeLabel(item.mode) : verdictLabel(item.verdict) }}</strong>
                  </div>
                  <p class="trace-summary" v-if="traceSummary(item).length">{{ traceSummary(item).join(' · ') }}</p>
                  <div class="chip-row" v-if="Array.isArray(item.high_risk_urls) && item.high_risk_urls.length">
                    <span v-for="url in item.high_risk_urls" :key="`${item.source}-${url}`" class="chip danger-chip">{{ url }}</span>
                  </div>
                </li>
              </ul>
            </section>

            <section class="detail-section">
              <h4>人工反馈</h4>
              <div class="filters-row">
                <select v-model="feedbackLabel">
                  <option value="">未反馈</option>
                  <option value="malicious">标记恶意</option>
                  <option value="benign">标记正常</option>
                </select>
                <input v-model="feedbackNote" placeholder="补充备注" />
                <button :disabled="feedbackSaving" @click="saveFeedback">{{ feedbackSaving ? '保存中...' : '保存反馈' }}</button>
              </div>
              <p v-if="feedbackMessage" class="success-text">{{ feedbackMessage }}</p>
              <p v-if="feedbackError" class="error-text">{{ feedbackError }}</p>
            </section>
          </template>

          <template v-else>
            <section class="detail-section">
              <h4>报告输出</h4>
              <div v-if="reportSections.length" class="report-layout">
                <aside class="report-nav">
                  <button
                    v-for="section in reportSections"
                    :key="section.id"
                    class="report-nav-item"
                    :class="{ active: currentReportSection?.id === section.id }"
                    @click="selectReportSection(section.id)"
                  >
                    {{ section.title }}
                  </button>
                </aside>
                <div class="markdown-body report-surface" v-if="currentReportSection" v-html="currentReportSection.html"></div>
              </div>
              <p v-else class="hint">暂无报告内容</p>
            </section>
          </template>
        </template>
      </article>
    </div>
  </section>
</template>
