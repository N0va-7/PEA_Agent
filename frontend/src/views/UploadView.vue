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
  }))
})

function formatDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
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
      <p>上传邮件文件并观察任务阶段事件</p>
    </header>

    <article class="panel">
      <div class="upload-box">
        <label>选择 .eml 文件</label>
        <input type="file" accept=".eml" @change="onFileChange" />
        <button :disabled="isAnalyzing" @click="startAnalysis">{{ isAnalyzing ? '分析中...' : '开始分析' }}</button>
      </div>

      <p v-if="actionMessage" class="success-text">{{ actionMessage }}</p>
      <p v-if="actionError" class="error-text">{{ actionError }}</p>

      <div v-if="jobStatus" class="status-line">
        状态: {{ jobStatus.status }}
        <span v-if="jobStatus.current_stage_label">｜当前阶段: {{ jobStatus.current_stage_label }}</span>
      </div>

      <div class="action-row" v-if="latestAnalysisId">
        <button class="ghost" @click="openResult">查看分析结果</button>
      </div>

      <h3>任务时间线</h3>
      <ul class="timeline" v-if="timeline.length">
        <li v-for="(event, idx) in timeline" :key="`${event.at}-${idx}`">
          <span>{{ formatDate(event.at) }}</span>
          <strong>{{ event.message }}</strong>
        </li>
      </ul>
      <p v-else class="hint">暂无任务事件</p>
    </article>
  </section>
</template>
