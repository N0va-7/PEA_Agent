<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiFetch, isAuthError } from '../api'
import { clearSession } from '../session'

const router = useRouter()

const emlFile = ref(null)
const isAnalyzing = ref(false)
const actionMessage = ref('')
const actionError = ref('')
const latestAnalysisId = ref('')
const jobStatus = ref(null)

const timeline = computed(() => {
  return (jobStatus.value?.progress_events || []).map((event) => ({
    at: event.at,
    message: event.message || event.stage_label || event.type,
    stageLabel: event.stage_label || '',
    status: event.status || '',
  }))
})

const selectedFileMeta = computed(() => {
  if (!emlFile.value) return null
  return {
    name: emlFile.value.name,
    size: emlFile.value.size,
    type: emlFile.value.type || 'message/rfc822',
  }
})

const workflowCards = computed(() => [
  { label: '解析', desc: '提取主题、正文、附件' },
  { label: 'VT', desc: '查询 URL 信誉' },
  { label: '模型', desc: 'URL 模型分析' },
  { label: '决策', desc: '综合裁决与报告' },
])
const uploadStats = computed(() => [
  {
    label: '当前状态',
    value: jobStatus.value?.status || (isAnalyzing.value ? 'running' : 'idle'),
    tone: jobStatus.value?.status === 'failed' ? 'danger' : jobStatus.value?.status === 'cached' ? 'warning' : 'safe',
  },
  {
    label: '阶段数',
    value: timeline.value.length || 0,
    tone: 'neutral',
  },
  {
    label: '结果 ID',
    value: latestAnalysisId.value || '--',
    tone: latestAnalysisId.value ? 'safe' : 'neutral',
  },
])

function formatDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function formatSize(bytes) {
  const value = Number(bytes || 0)
  if (!Number.isFinite(value) || value <= 0) return '--'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function onFileChange(event) {
  const file = event.target.files?.[0]
  emlFile.value = file || null
}

async function createJob() {
  const form = new FormData()
  form.append('file', emlFile.value)
  const response = await apiFetch('/api/v1/analyses', { method: 'POST', body: form })
  return await response.json()
}

async function getJob(jobId) {
  const response = await apiFetch(`/api/v1/jobs/${jobId}`)
  return await response.json()
}

async function pollJob(jobId) {
  const start = Date.now()
  while (true) {
    const payload = await getJob(jobId)
    jobStatus.value = payload
    if (['succeeded', 'failed', 'cached'].includes(payload.status)) return payload
    if (Date.now() - start > 240000) throw new Error('任务轮询超时')
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
}

async function startAnalysis() {
  actionMessage.value = ''
  actionError.value = ''
  latestAnalysisId.value = ''
  jobStatus.value = null
  if (!emlFile.value) {
    actionError.value = '请先选择 .eml 文件'
    return
  }

  isAnalyzing.value = true
  try {
    const job = await createJob()
    const finalJob = await pollJob(job.job_id)
    if (finalJob.status === 'failed') {
      throw new Error(finalJob.error || '后端任务失败')
    }
    if (!finalJob.analysis_id) {
      throw new Error('任务完成但未返回 analysis_id')
    }
    latestAnalysisId.value = finalJob.analysis_id
    actionMessage.value = finalJob.status === 'cached' ? '命中历史缓存，已返回历史结果' : '分析完成'
  } catch (error) {
    actionError.value = `分析失败: ${error.message}`
    if (isAuthError(error)) {
      clearSession()
      await router.replace('/login')
    }
  } finally {
    isAnalyzing.value = false
  }
}

async function openResult() {
  if (!latestAnalysisId.value) return
  await router.push(`/app/history/${latestAnalysisId.value}`)
}
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>上传分析</h2>
      <p>上传邮件文件，观察 Agent workflow 的真实执行阶段与最终裁决。</p>
    </header>

    <article class="panel page-banner-panel">
      <div class="page-banner">
        <div class="page-banner-copy">
          <span class="page-banner-kicker">Mail Intake</span>
          <h3>邮件上传与分析入口</h3>
          <p>上传 `.eml`，进入主分析链路，查看执行阶段、结果状态和后续详情。</p>
        </div>
        <div class="page-banner-icon mail">
          <svg viewBox="0 0 64 64" aria-hidden="true">
            <defs>
              <linearGradient id="mailBannerBg" x1="0%" x2="100%" y1="0%" y2="100%">
                <stop offset="0%" stop-color="#1f5d96" />
                <stop offset="100%" stop-color="#0b3b65" />
              </linearGradient>
            </defs>
            <rect x="6" y="10" width="52" height="44" rx="8" fill="url(#mailBannerBg)" />
            <path d="M14 24 32 37 50 24" fill="none" stroke="#f8fbff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M14 44 25 33" fill="none" stroke="#cfe3ff" stroke-width="2.6" stroke-linecap="round" />
            <path d="M50 44 39 33" fill="none" stroke="#cfe3ff" stroke-width="2.6" stroke-linecap="round" />
            <circle cx="50" cy="16" r="5" fill="#7dd3fc" />
          </svg>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="ingest-console">
        <section class="ingest-primary">
          <div class="section-head">
            <div>
              <h3>邮件上传台</h3>
              <p>提交 `.eml` 后，主流程会依次执行解析、VT 查询、模型分析和综合决策。</p>
            </div>
          </div>

          <div class="upload-box upload-box-enhanced upload-console-form">
            <div class="upload-field">
              <label>选择 .eml 文件</label>
              <input type="file" accept=".eml" @change="onFileChange" />
            </div>
            <div class="upload-actions upload-actions-stacked">
              <button :disabled="isAnalyzing" @click="startAnalysis">{{ isAnalyzing ? '分析中...' : '开始分析' }}</button>
              <button v-if="latestAnalysisId" class="ghost" @click="openResult">查看分析结果</button>
            </div>
          </div>

          <div v-if="selectedFileMeta" class="file-card file-card-emphasis">
            <div class="file-card-top">
              <strong>{{ selectedFileMeta.name }}</strong>
              <span class="badge neutral">邮件源文件</span>
            </div>
            <div class="entity-meta">
              <span>{{ formatSize(selectedFileMeta.size) }}</span>
              <span>{{ selectedFileMeta.type }}</span>
            </div>
          </div>

          <p v-if="actionMessage" class="success-text">{{ actionMessage }}</p>
          <p v-if="actionError" class="error-text">{{ actionError }}</p>

          <div v-if="jobStatus" class="status-line">
            状态: {{ jobStatus.status }}
            <span v-if="jobStatus.current_stage_label">｜当前阶段: {{ jobStatus.current_stage_label }}</span>
          </div>
        </section>

        <aside class="ingest-side">
          <section class="hero-kpis">
            <article v-for="card in uploadStats" :key="card.label" class="summary-card hero-kpi-card">
              <span>{{ card.label }}</span>
              <strong :class="card.tone">{{ card.value }}</strong>
            </article>
          </section>

          <section class="mini-panel">
            <div class="section-head">
              <div>
                <h4>执行阶段</h4>
                <p>只展示真实流程，不做额外推断。</p>
              </div>
            </div>
            <div class="workflow-strip compact-workflow">
              <article v-for="card in workflowCards" :key="card.label" class="workflow-card">
                <span>{{ card.label }}</span>
                <strong>{{ card.desc }}</strong>
              </article>
            </div>
          </section>
        </aside>
      </div>
    </article>

    <article class="panel">
      <div class="section-head">
        <div>
          <h3>任务时间线</h3>
          <p>这里展示后端返回的真实进度事件。</p>
        </div>
      </div>
      <ul class="timeline timeline-extended" v-if="timeline.length">
        <li v-for="(event, idx) in timeline" :key="`${event.at}-${idx}`">
          <div class="trace-head">
            <span>{{ formatDate(event.at) }}</span>
            <strong>{{ event.stageLabel || event.status || '事件' }}</strong>
          </div>
          <strong>{{ event.message }}</strong>
        </li>
      </ul>
      <p v-else class="hint">暂无任务事件</p>
    </article>
  </section>
</template>
