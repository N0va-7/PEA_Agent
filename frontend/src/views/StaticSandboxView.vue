<script setup>
import { computed, ref } from 'vue'

import { sandboxFetch } from '../api'

const sampleFile = ref(null)
const sourceId = ref('manual-ui')
const running = ref(false)
const actionError = ref('')
const actionMessage = ref('')
const job = ref(null)
const selectedFileMeta = computed(() => {
  if (!sampleFile.value) return null
  return {
    name: sampleFile.value.name,
    size: sampleFile.value.size,
    type: sampleFile.value.type || 'application/octet-stream',
  }
})

const summaryCards = computed(() => {
  const payload = job.value || {}
  return [
    { label: '状态', value: payload.status || '--' },
    { label: '裁决', value: payload.verdict || '--' },
    { label: '风险分', value: payload.risk_score ?? '--' },
    { label: '类型', value: payload.normalized_type || '--' },
  ]
})
const consoleCards = computed(() => [
  {
    label: '任务状态',
    value: job.value?.status || (running.value ? 'running' : 'idle'),
    tone: String(job.value?.status || '').toLowerCase() === 'error' ? 'danger' : 'safe',
  },
  {
    label: '命中原因',
    value: job.value?.reasons?.length || 0,
    tone: job.value?.reasons?.length ? 'warning' : 'neutral',
  },
  {
    label: '产物数',
    value: job.value?.artifacts?.length || 0,
    tone: 'neutral',
  },
])

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

async function pollJob(jobId) {
  const startedAt = Date.now()
  while (true) {
    const response = await sandboxFetch(`/analysis/jobs/${jobId}`)
    const payload = await response.json()
    job.value = payload
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
  job.value = null
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
    actionMessage.value = ['error'].includes(String(finalJob.status || '').toLowerCase()) ? '任务已完成，但结果为 error' : '静态沙箱分析完成'
  } catch (error) {
    actionError.value = `提交失败: ${error.message}`
  } finally {
    running.value = false
  }
}
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>静态沙箱上传扫描</h2>
      <p>直接向独立静态沙箱提交附件样本，查看规则命中、风险分和归一化类型。</p>
    </header>

    <article class="panel page-banner-panel">
      <div class="page-banner">
        <div class="page-banner-copy">
          <span class="page-banner-kicker">Static Sandbox</span>
          <h3>样本隔离与规则命中入口</h3>
          <p>独立提交单个样本进行静态扫描，验证规则命中、风险分和归一化类型，不走邮件主流程。</p>
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
              <p>提交单个文件到独立沙箱，返回规则命中、风险分和归一化类型。</p>
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
              <li>结果来自规则命中和归一化类型映射。</li>
              <li>规则详情可在“静态沙箱 / 规则管理”中查看。</li>
              <li>同一附件样本会按 SHA256 复用已有静态分析记录。</li>
              <li>这里不会生成邮件分析历史记录。</li>
            </ul>
          </section>
        </aside>
      </div>
    </article>

    <article class="panel" v-if="job">
      <div class="section-head">
        <h3>扫描结果</h3>
        <p>以下结果直接来自静态沙箱服务。</p>
      </div>

      <section class="summary-strip">
        <article v-for="card in summaryCards" :key="card.label" class="summary-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
        </article>
      </section>

      <div class="meta-grid">
        <div>
          <label>作业 ID</label>
          <p>{{ job.job_id }}</p>
        </div>
        <div>
          <label>规则版本</label>
          <p>{{ job.rule_version || '--' }}</p>
        </div>
        <div>
          <label>样本哈希</label>
          <p>{{ job.sample_sha256 || '--' }}</p>
        </div>
        <div>
          <label>来源</label>
          <p>{{ job.source_id || '--' }}</p>
        </div>
      </div>

      <section class="detail-section">
        <h4>命中原因</h4>
        <ul class="entity-list" v-if="job.reasons?.length">
          <li v-for="reason in job.reasons" :key="reason" class="entity-card">
            <p class="entity-summary">{{ reason }}</p>
          </li>
        </ul>
        <p v-else class="hint">当前结果没有返回命中原因。</p>
      </section>

      <section class="detail-section">
        <h4>产物</h4>
        <pre class="raw-json">{{ JSON.stringify(job.artifacts || [], null, 2) }}</pre>
      </section>
    </article>
  </section>
</template>
