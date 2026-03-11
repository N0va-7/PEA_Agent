<script setup>
import { computed, onMounted, ref } from 'vue'

import { sandboxFetch } from '../api'

const sampleFile = ref(null)
const sourceId = ref('manual-ui')
const running = ref(false)
const historyLoading = ref(false)
const actionError = ref('')
const actionMessage = ref('')
const historyItems = ref([])
const selectedJobId = ref('')

const selectedFileMeta = computed(() => {
  if (!sampleFile.value) return null
  return {
    name: sampleFile.value.name,
    size: sampleFile.value.size,
    type: sampleFile.value.type || 'application/octet-stream',
  }
})

const selectedJob = computed(() => historyItems.value.find((item) => item.job_id === selectedJobId.value) || null)

const summaryCards = computed(() => {
  const payload = selectedJob.value || {}
  return [
    { label: '状态', value: statusLabel(payload.status), tone: statusTone(payload.status) },
    { label: '裁决', value: verdictLabel(payload.verdict), tone: verdictTone(payload.verdict) },
    { label: '风险分', value: payload.risk_score ?? '--', tone: verdictTone(payload.verdict) },
    { label: '类型', value: payload.normalized_type || '--', tone: 'neutral' },
  ]
})

const consoleCards = computed(() => [
  {
    label: '任务状态',
    value: selectedJob.value ? statusLabel(selectedJob.value.status) : running.value ? '扫描中' : '待提交',
    tone: selectedJob.value ? statusTone(selectedJob.value.status) : running.value ? 'warning' : 'neutral',
  },
  {
    label: '恶意判定',
    value: historyItems.value.filter((item) => item.verdict === 'block').length,
    tone: historyItems.value.some((item) => item.verdict === 'block') ? 'danger' : 'neutral',
  },
  {
    label: '最近记录',
    value: historyItems.value.length,
    tone: historyItems.value.length ? 'safe' : 'neutral',
  },
])

function statusLabel(value) {
  const raw = String(value || '').toLowerCase()
  if (raw === 'queued') return '排队中'
  if (raw === 'running') return '扫描中'
  if (raw === 'completed') return '已完成'
  return value || '--'
}

function statusTone(value) {
  const raw = String(value || '').toLowerCase()
  if (raw === 'completed') return 'safe'
  if (raw === 'running' || raw === 'queued') return 'warning'
  return 'neutral'
}

function verdictLabel(value) {
  const raw = String(value || '').toLowerCase()
  if (!raw) return '--'
  if (raw === 'allow') return '正常'
  if (raw === 'quarantine') return '可疑'
  if (raw === 'block') return '恶意'
  if (raw === 'error') return '错误'
  return value
}

function verdictTone(value) {
  const raw = String(value || '').toLowerCase()
  if (raw === 'block' || raw === 'error') return 'danger'
  if (raw === 'quarantine') return 'warning'
  if (raw === 'allow') return 'safe'
  return 'neutral'
}

function verdictDescription(value) {
  const raw = String(value || '').toLowerCase()
  if (raw === 'block') return '静态沙箱已判定该样本为恶意，建议阻断或隔离。'
  if (raw === 'quarantine') return '样本命中高风险规则，建议进入隔离或人工复核。'
  if (raw === 'allow') return '当前样本未命中高风险规则，静态扫描视角下为正常。'
  if (raw === 'error') return '静态沙箱处理失败，需要查看错误信息或重新提交。'
  return '等待静态沙箱返回结论。'
}

function onFileChange(event) {
  sampleFile.value = event.target.files?.[0] || null
}

function formatSize(bytes) {
  const value = Number(bytes || 0)
  if (!Number.isFinite(value) || value <= 0) return '--'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function compactDate(value) {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

async function loadHistory(selectId = '') {
  historyLoading.value = true
  try {
    const response = await sandboxFetch('/analysis/jobs?limit=40')
    const payload = await response.json()
    historyItems.value = Array.isArray(payload.items) ? payload.items : []
    if (selectId && historyItems.value.some((item) => item.job_id === selectId)) {
      selectedJobId.value = selectId
    } else if (!selectedJobId.value && historyItems.value.length) {
      selectedJobId.value = historyItems.value[0].job_id
    } else if (selectedJobId.value && !historyItems.value.some((item) => item.job_id === selectedJobId.value)) {
      selectedJobId.value = historyItems.value[0]?.job_id || ''
    }
  } finally {
    historyLoading.value = false
  }
}

async function openJob(jobId) {
  selectedJobId.value = jobId
  const response = await sandboxFetch(`/analysis/jobs/${jobId}`)
  const payload = await response.json()
  const index = historyItems.value.findIndex((item) => item.job_id === jobId)
  if (index >= 0) {
    historyItems.value[index] = payload
  } else {
    historyItems.value.unshift(payload)
  }
}

async function pollJob(jobId) {
  const startedAt = Date.now()
  while (true) {
    const response = await sandboxFetch(`/analysis/jobs/${jobId}`)
    const payload = await response.json()
    const index = historyItems.value.findIndex((item) => item.job_id === jobId)
    if (index >= 0) historyItems.value[index] = payload
    else historyItems.value.unshift(payload)
    selectedJobId.value = jobId
    if (['done', 'completed', 'succeeded', 'error'].includes(String(payload.status || '').toLowerCase())) {
      return payload
    }
    if (Date.now() - startedAt > 180000) {
      throw new Error('静态沙箱任务轮询超时')
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
}

async function submitScan() {
  actionError.value = ''
  actionMessage.value = ''
  if (!sampleFile.value) {
    actionError.value = '请先选择附件样本'
    return
  }

  running.value = true
  try {
    const form = new FormData()
    form.append('file', sampleFile.value)
    form.append('source_id', sourceId.value.trim() || 'manual-ui')
    const response = await sandboxFetch('/analysis/jobs', {
      method: 'POST',
      body: form,
    })
    const payload = await response.json()
    const finalJob = await pollJob(payload.job_id)
    await loadHistory(payload.job_id)
    actionMessage.value = finalJob.verdict === 'block'
      ? '静态沙箱分析完成，样本已判定为恶意'
      : finalJob.verdict === 'quarantine'
        ? '静态沙箱分析完成，样本命中可疑规则'
        : finalJob.verdict === 'allow'
          ? '静态沙箱分析完成，当前样本判定为正常'
          : '静态沙箱分析完成'
  } catch (error) {
    actionError.value = `提交失败: ${error.message}`
  } finally {
    running.value = false
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>静态沙箱上传扫描</h2>
      <p>直接向独立静态沙箱提交附件样本，查看规则命中、风险分、历史记录和恶意结论。</p>
    </header>

    <article class="panel page-banner-panel">
      <div class="page-banner">
        <div class="page-banner-copy">
          <span class="page-banner-kicker">Static Sandbox</span>
          <h3>样本隔离、历史回看与规则命中</h3>
          <p>独立提交单个样本进行静态扫描，支持回看最近任务、命中原因和裁决，不走邮件主流程。</p>
        </div>
        <div class="page-banner-icon sandbox">
          <svg viewBox="0 0 64 64" aria-hidden="true">
            <defs>
              <linearGradient id="sandboxBannerBg" x1="0%" x2="100%" y1="0%" y2="100%">
                <stop offset="0%" stop-color="#164e84" />
                <stop offset="100%" stop-color="#0b2f52" />
              </linearGradient>
            </defs>
            <rect x="8" y="8" width="48" height="48" rx="10" fill="url(#sandboxBannerBg)" />
            <rect x="18" y="18" width="28" height="28" rx="4" fill="none" stroke="#f8fbff" stroke-width="3" />
            <path d="M32 18v28M18 32h28" stroke="#cfe3ff" stroke-width="2.4" stroke-linecap="round" />
            <path d="m24 24 16 16M40 24 24 40" stroke="rgba(248,251,255,0.32)" stroke-width="2" stroke-linecap="round" />
            <path d="M48 14h4a4 4 0 0 1 4 4v4" fill="none" stroke="#7dd3fc" stroke-width="2.8" stroke-linecap="round" />
            <path d="M16 50h-4a4 4 0 0 1-4-4v-4" fill="none" stroke="#7dd3fc" stroke-width="2.8" stroke-linecap="round" />
          </svg>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="ingest-console">
        <section class="ingest-primary">
          <div class="section-head">
            <div>
              <h3>静态样本上传台</h3>
              <p>提交单个文件到独立沙箱，返回规则命中、风险分和恶意/可疑/正常结论。</p>
            </div>
          </div>

          <div class="sandbox-submit-grid">
            <label class="field-label">
              <span>样本文件</span>
              <input type="file" @change="onFileChange" />
            </label>
            <label class="field-label">
              <span>来源标识</span>
              <input v-model="sourceId" placeholder="manual-ui" />
            </label>
            <div class="sandbox-submit-actions">
              <button :disabled="running" @click="submitScan">{{ running ? '扫描中...' : '开始扫描' }}</button>
            </div>
          </div>

          <div v-if="selectedFileMeta" class="file-card file-card-emphasis">
            <div class="file-card-top">
              <strong>{{ selectedFileMeta.name }}</strong>
              <span class="badge neutral">静态样本</span>
            </div>
            <div class="entity-meta">
              <span>{{ formatSize(selectedFileMeta.size) }}</span>
              <span>{{ selectedFileMeta.type }}</span>
            </div>
          </div>

          <p v-if="actionMessage" class="success-text">{{ actionMessage }}</p>
          <p v-if="actionError" class="error-text">{{ actionError }}</p>
        </section>

        <aside class="ingest-side">
          <section class="hero-kpis">
            <article v-for="card in consoleCards" :key="card.label" class="summary-card hero-kpi-card">
              <span>{{ card.label }}</span>
              <strong :class="card.tone">{{ card.value }}</strong>
            </article>
          </section>

          <section class="mini-panel">
            <div class="section-head">
              <div>
                <h4>扫描说明</h4>
                <p>当前页面直连独立静态沙箱，不经过邮件分析主流程。</p>
              </div>
            </div>
            <ul class="evidence-list">
              <li>结果来自规则命中、归一化类型和静态策略裁决。</li>
              <li>同一附件样本会按 SHA256 复用已有静态分析记录。</li>
              <li>左侧历史区会保留最近静态沙箱任务，可重复回看。</li>
            </ul>
          </section>
        </aside>
      </div>
    </article>

    <div class="split-layout url-console-layout">
      <article class="panel">
        <div class="list-head">
          <h3>扫描历史</h3>
          <p class="hint" v-if="historyLoading">加载中...</p>
          <p class="hint" v-else>共 {{ historyItems.length }} 条</p>
        </div>

        <ul class="history-records url-history-list" v-if="historyItems.length">
          <li v-for="item in historyItems" :key="item.job_id" class="history-item">
            <article
              class="history-select url-check-card"
              :class="{ selected: selectedJobId === item.job_id }"
              role="button"
              tabindex="0"
              @click="openJob(item.job_id)"
            >
              <div class="history-select-top">
                <strong>{{ item.filename || item.sample_sha256 }}</strong>
                <em class="badge" :class="verdictTone(item.verdict)">{{ verdictLabel(item.verdict) }}</em>
              </div>
              <div class="history-select-meta url-check-meta">
                <span>{{ compactDate(item.updated_at || item.created_at) }}</span>
                <span>{{ item.normalized_type || 'unknown' }}</span>
              </div>
              <div class="history-select-foot">
                <span class="history-foot-label">{{ item.reasons?.length ? `${item.reasons.length} 个命中原因` : '无命中原因' }}</span>
                <span class="badge neutral">{{ statusLabel(item.status) }}</span>
              </div>
            </article>
          </li>
        </ul>
        <p v-else class="hint">暂无静态沙箱历史记录</p>
      </article>

      <article class="panel detail-panel">
        <p v-if="!selectedJob" class="hint">从左侧选择一条静态沙箱记录查看详情</p>
        <template v-else>
          <div class="detail-head">
            <div>
              <h3>{{ selectedJob.filename || selectedJob.sample_sha256 }}</h3>
              <p>{{ verdictDescription(selectedJob.verdict) }}</p>
            </div>
            <span class="badge" :class="verdictTone(selectedJob.verdict)">{{ verdictLabel(selectedJob.verdict) }}</span>
          </div>

          <section class="summary-strip">
            <article v-for="card in summaryCards" :key="card.label" class="summary-card">
              <span>{{ card.label }}</span>
              <strong :class="card.tone">{{ card.value }}</strong>
            </article>
          </section>

          <section class="detail-section">
            <h4>基础信息</h4>
            <div class="meta-grid">
              <div>
                <label>作业 ID</label>
                <p>{{ selectedJob.job_id }}</p>
              </div>
              <div>
                <label>规则版本</label>
                <p>{{ selectedJob.rule_version || '--' }}</p>
              </div>
              <div>
                <label>样本哈希</label>
                <p>{{ selectedJob.sample_sha256 || '--' }}</p>
              </div>
              <div>
                <label>来源</label>
                <p>{{ selectedJob.source_id || '--' }}</p>
              </div>
              <div>
                <label>创建时间</label>
                <p>{{ compactDate(selectedJob.created_at) }}</p>
              </div>
              <div>
                <label>更新时间</label>
                <p>{{ compactDate(selectedJob.updated_at) }}</p>
              </div>
            </div>
          </section>

          <section class="detail-section">
            <h4>命中原因</h4>
            <ul class="entity-list" v-if="selectedJob.reasons?.length">
              <li v-for="reason in selectedJob.reasons" :key="reason" class="entity-card">
                <div class="entity-head">
                  <strong>{{ reason }}</strong>
                  <span class="badge" :class="verdictTone(selectedJob.verdict)">{{ verdictLabel(selectedJob.verdict) }}</span>
                </div>
              </li>
            </ul>
            <p v-else class="hint">当前结果没有返回命中原因。</p>
          </section>

          <section class="detail-section">
            <h4>产物</h4>
            <pre class="raw-json">{{ JSON.stringify(selectedJob.artifacts || [], null, 2) }}</pre>
          </section>

          <section class="detail-section" v-if="selectedJob.error_message">
            <h4>错误信息</h4>
            <p class="error-text">{{ selectedJob.error_message }}</p>
          </section>
        </template>
      </article>
    </div>
  </section>
</template>
