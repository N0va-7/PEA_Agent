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
const historyItems = ref([])
const total = ref(0)

const selectedAnalysisId = ref('')
const detailLoading = ref(false)
const analysis = ref(null)
const reportText = ref('')
const reportName = ref('')
const activeTab = ref('overview')

const finalDecision = computed(() => analysis.value?.final_decision || {})
const bodyProb = computed(() => Number(analysis.value?.body_analysis?.phishing_probability || 0))
const urlProb = computed(() => Number(analysis.value?.url_analysis?.max_possibility || 0))
const attachThreat = computed(() => analysis.value?.attachment_analysis?.threat_level || 'unknown')
const reportHtml = computed(() => md.render(reportText.value || ''))
const pageCount = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize.value)))

function formatDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function getVerdict(item) {
  const flag = item?.final_decision?.is_malicious
  if (flag === true) return '恶意'
  if (flag === false) return '正常'
  return '未判定'
}

function getVerdictClass(item) {
  const flag = item?.final_decision?.is_malicious
  if (flag === true) return 'danger'
  if (flag === false) return 'safe'
  return 'neutral'
}

function truncate(text, max = 42) {
  if (!text) return '--'
  return text.length > max ? `${text.slice(0, max)}...` : text
}

function toIsoOrEmpty(value) {
  if (!value) return ''
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? '' : dt.toISOString()
}

const timelineEvents = computed(() => {
  const trace = analysis.value?.execution_trace || []
  return trace.map((stage, idx) => ({
    at: `步骤 ${idx + 1}`,
    message: String(stage),
  }))
})

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

async function getAnalysis(analysisId) {
  const response = await apiFetch(`/api/v1/analyses/${analysisId}`)
  return await response.json()
}

async function getReport(analysisId) {
  const response = await apiFetch(`/api/v1/reports/${analysisId}`)
  const blob = await response.blob()
  const text = await blob.text()
  let filename = `report_${analysisId}.md`
  const cd = response.headers.get('content-disposition') || ''
  if (cd.includes('filename=')) {
    filename = cd.split('filename=')[1].replaceAll('"', '').trim()
  }
  return { text, filename }
}

async function openAnalysis(analysisId, { updateRoute = true } = {}) {
  if (!analysisId) return
  selectedAnalysisId.value = analysisId
  detailLoading.value = true
  try {
    if (updateRoute && route.params.analysisId !== analysisId) {
      await router.push(`/app/history/${analysisId}`)
    }
    const [analysisPayload, reportPayload] = await Promise.all([getAnalysis(analysisId), getReport(analysisId)])
    analysis.value = analysisPayload
    reportText.value = reportPayload.text
    reportName.value = reportPayload.filename
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

async function applyFilters() {
  await loadHistory({ resetPage: true })
}

async function changePage(delta) {
  const next = page.value + delta
  if (next < 1 || next > pageCount.value) return
  page.value = next
  await loadHistory()
}

function resetFilters() {
  senderFilter.value = ''
  subjectFilter.value = ''
  createdFrom.value = ''
  createdTo.value = ''
  sortBy.value = 'created_at'
  sortOrder.value = 'desc'
  pageSize.value = 10
  loadHistory({ resetPage: true })
}

function downloadReport() {
  if (!reportText.value) return
  const blob = new Blob([reportText.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = reportName.value || 'report.md'
  a.click()
  URL.revokeObjectURL(url)
}

watch(
  () => route.params.analysisId,
  async (id) => {
    if (!id) return
    const analysisId = String(id)
    if (analysisId === selectedAnalysisId.value && analysis.value) return
    await openAnalysis(analysisId, { updateRoute: false })
  },
  { immediate: true },
)

onMounted(async () => {
  await loadHistory()
})
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>历史分析结果</h2>
      <p>按时间、主题、发件人检索，查看详细分析报告</p>
    </header>

    <div class="history-layout">
      <article class="panel">
        <div class="card-head">
          <h3>筛选与列表</h3>
          <button class="ghost small" @click="loadHistory()">刷新</button>
        </div>

        <div class="filters">
          <input v-model="subjectFilter" placeholder="按主题过滤" />
          <input v-model="senderFilter" placeholder="按发件人过滤" />
          <div class="row">
            <input v-model="createdFrom" type="datetime-local" />
            <input v-model="createdTo" type="datetime-local" />
          </div>
          <div class="row">
            <select v-model="sortBy">
              <option value="created_at">创建时间</option>
              <option value="sender">发件人</option>
              <option value="subject">主题</option>
            </select>
            <select v-model="sortOrder">
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
            <select v-model.number="pageSize">
              <option :value="10">10/页</option>
              <option :value="20">20/页</option>
              <option :value="50">50/页</option>
            </select>
          </div>
          <div class="filter-actions">
            <button class="ghost small" @click="applyFilters">查询</button>
            <button class="ghost small" @click="resetFilters">清空</button>
          </div>
        </div>

        <p v-if="historyLoading" class="hint">历史记录加载中...</p>
        <p v-if="historyError" class="error-text">{{ historyError }}</p>

        <ul v-if="historyItems.length" class="history-list">
          <li
            v-for="item in historyItems"
            :key="item.id"
            :class="{ active: selectedAnalysisId === item.id }"
            @click="openAnalysis(item.id)"
          >
            <div class="history-top">
              <strong>{{ truncate(item.subject, 30) }}</strong>
              <span class="badge" :class="getVerdictClass(item)">{{ getVerdict(item) }}</span>
            </div>
            <div class="history-meta">
              <span>{{ truncate(item.sender, 24) }}</span>
              <span>{{ formatDate(item.created_at) }}</span>
            </div>
          </li>
        </ul>
        <p v-else-if="!historyLoading" class="hint">暂无历史记录</p>

        <div class="pagination">
          <span>共 {{ total }} 条 / 第 {{ page }} / {{ pageCount }} 页</span>
          <div class="pager-actions">
            <button class="ghost small" :disabled="page <= 1" @click="changePage(-1)">上一页</button>
            <button class="ghost small" :disabled="page >= pageCount" @click="changePage(1)">下一页</button>
          </div>
        </div>
      </article>

      <article class="panel">
        <div class="card-head">
          <h3>分析详情</h3>
          <button class="ghost small" :disabled="!reportText" @click="downloadReport">下载报告</button>
        </div>
        <div class="tabs">
          <button class="ghost small" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">概览</button>
          <button class="ghost small" :class="{ active: activeTab === 'report' }" @click="activeTab = 'report'">报告</button>
          <button class="ghost small" :class="{ active: activeTab === 'raw' }" @click="activeTab = 'raw'">原始数据</button>
        </div>

        <div v-if="detailLoading" class="hint">正在加载详情...</div>
        <template v-else-if="analysis">
          <template v-if="activeTab === 'overview'">
            <div class="metrics compact">
              <div class="metric">
                <span>最终判定</span>
                <strong :class="getVerdictClass(analysis)">{{ getVerdict(analysis) }}</strong>
              </div>
              <div class="metric">
                <span>综合分数</span>
                <strong>{{ Number(finalDecision.score || 0).toFixed(3) }}</strong>
              </div>
              <div class="metric">
                <span>正文钓鱼概率</span>
                <strong>{{ (bodyProb * 100).toFixed(2) }}%</strong>
              </div>
              <div class="metric">
                <span>URL钓鱼概率</span>
                <strong>{{ (urlProb * 100).toFixed(2) }}%</strong>
              </div>
              <div class="metric">
                <span>附件威胁</span>
                <strong>{{ attachThreat }}</strong>
              </div>
            </div>
            <div class="meta-grid">
              <div><label>分析ID</label><p>{{ analysis.id }}</p></div>
              <div><label>发件人</label><p>{{ analysis.sender || '--' }}</p></div>
              <div><label>收件人</label><p>{{ analysis.recipient || '--' }}</p></div>
              <div><label>主题</label><p>{{ analysis.subject || '--' }}</p></div>
              <div><label>创建时间</label><p>{{ formatDate(analysis.created_at) }}</p></div>
            </div>

            <h4>执行轨迹</h4>
            <ul class="timeline" v-if="timelineEvents.length">
              <li v-for="(event, idx) in timelineEvents" :key="`${event.at}-${idx}`">
                <span>{{ event.at }}</span>
                <strong>{{ event.message }}</strong>
              </li>
            </ul>
            <p v-else class="hint">无执行轨迹</p>
          </template>

          <template v-else-if="activeTab === 'report'">
            <article class="report markdown-body" v-html="reportHtml"></article>
          </template>

          <template v-else>
            <pre class="raw-json">{{ JSON.stringify(analysis, null, 2) }}</pre>
          </template>
        </template>
        <div v-else class="empty-state">请先从左侧选择一条历史记录。</div>
      </article>
    </div>
  </section>
</template>
