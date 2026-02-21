<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiFetch, isAuthError } from '../api'
import { clearSession } from '../session'

const router = useRouter()

const reviewedFrom = ref('')
const reviewedTo = ref('')
const fprTarget = ref(0.03)
const wStep = ref(0.05)
const thMin = ref(0.5)
const thMax = ref(0.95)
const thStep = ref(0.01)

const loadingPrecheck = ref(false)
const loadingRun = ref(false)
const loadingRuns = ref(false)
const activatingRunId = ref('')

const pageError = ref('')
const pageSuccess = ref('')
const precheck = ref(null)
const lastRun = ref(null)
const runs = ref([])

function toIsoOrNull(value) {
  if (!value) return null
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return null
  return dt.toISOString()
}

function formatDate(value) {
  if (!value) return '--'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function buildPayload({ withConfirm = false } = {}) {
  return {
    reviewed_from: toIsoOrNull(reviewedFrom.value),
    reviewed_to: toIsoOrNull(reviewedTo.value),
    fpr_target: Number(fprTarget.value),
    w_step: Number(wStep.value),
    th_min: Number(thMin.value),
    th_max: Number(thMax.value),
    th_step: Number(thStep.value),
    ...(withConfirm ? { confirm: true } : {}),
  }
}

async function handleError(error, fallbackPrefix = '请求失败') {
  pageError.value = `${fallbackPrefix}: ${error.message}`
  if (isAuthError(error)) {
    clearSession()
    await router.replace('/login')
  }
}

async function loadRuns() {
  loadingRuns.value = true
  try {
    const res = await apiFetch('/api/v1/tuning/fusion/runs')
    const payload = await res.json()
    runs.value = payload.items || []
  } catch (error) {
    await handleError(error, '读取调参历史失败')
  } finally {
    loadingRuns.value = false
  }
}

async function runPrecheck() {
  loadingPrecheck.value = true
  pageError.value = ''
  pageSuccess.value = ''
  try {
    const res = await apiFetch('/api/v1/tuning/fusion/precheck', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildPayload()),
    })
    precheck.value = await res.json()
    if (precheck.value.meets_requirements) {
      pageSuccess.value = 'Precheck 通过，可以手动运行调参。'
    } else {
      pageSuccess.value = ''
    }
  } catch (error) {
    await handleError(error, '预检查失败')
  } finally {
    loadingPrecheck.value = false
  }
}

async function runTuning() {
  pageError.value = ''
  pageSuccess.value = ''
  if (!precheck.value || !precheck.value.meets_requirements) {
    pageError.value = '请先完成并通过 Precheck。'
    return
  }
  if (!window.confirm('确认基于当前条件手动运行融合调参？')) {
    return
  }

  loadingRun.value = true
  try {
    const res = await apiFetch('/api/v1/tuning/fusion/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildPayload({ withConfirm: true })),
    })
    lastRun.value = await res.json()
    pageSuccess.value = `调参完成：run_id=${lastRun.value.run_id}`
    await loadRuns()
  } catch (error) {
    await handleError(error, '运行调参失败')
  } finally {
    loadingRun.value = false
  }
}

async function activateRun(runId) {
  if (!runId) return
  if (!window.confirm(`确认启用参数版本 ${runId}？`)) {
    return
  }
  activatingRunId.value = runId
  pageError.value = ''
  pageSuccess.value = ''
  try {
    const res = await apiFetch(`/api/v1/tuning/fusion/runs/${runId}/activate`, {
      method: 'POST',
    })
    const payload = await res.json()
    pageSuccess.value = `已启用参数版本：${payload.active_run_id}`
    await loadRuns()
  } catch (error) {
    await handleError(error, '启用参数失败')
  } finally {
    activatingRunId.value = ''
  }
}

onMounted(loadRuns)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>调参管理</h2>
      <p>手动触发融合调参：先 Precheck，再确认 Run，最后 Activate 生效。</p>
    </header>

    <article class="panel tuning-panel">
      <div class="card-head">
        <h3>运行条件</h3>
        <button class="ghost small" :disabled="loadingPrecheck" @click="runPrecheck">
          {{ loadingPrecheck ? '预检查中...' : '运行 Precheck' }}
        </button>
      </div>

      <div class="filters">
        <div class="row">
          <label class="field-label">
            反馈开始时间
            <input v-model="reviewedFrom" type="datetime-local" />
          </label>
          <label class="field-label">
            反馈结束时间
            <input v-model="reviewedTo" type="datetime-local" />
          </label>
        </div>

        <div class="row">
          <label class="field-label">
            FPR目标
            <input v-model.number="fprTarget" type="number" min="0.0001" max="0.5" step="0.001" />
          </label>
          <label class="field-label">
            权重步长
            <input v-model.number="wStep" type="number" min="0.01" max="1" step="0.01" />
          </label>
        </div>

        <div class="row three">
          <label class="field-label">
            阈值最小
            <input v-model.number="thMin" type="number" min="0" max="1" step="0.01" />
          </label>
          <label class="field-label">
            阈值最大
            <input v-model.number="thMax" type="number" min="0" max="1" step="0.01" />
          </label>
          <label class="field-label">
            阈值步长
            <input v-model.number="thStep" type="number" min="0.001" max="1" step="0.001" />
          </label>
        </div>
      </div>

      <div v-if="precheck" class="precheck-box">
        <h4>Precheck 结果</h4>
        <div class="stat-grid tuning-grid">
          <div class="stat-item">
            <span>可用样本</span>
            <strong>{{ precheck.valid_rows }}</strong>
          </div>
          <div class="stat-item">
            <span>正类样本</span>
            <strong>{{ precheck.positive_rows }}</strong>
          </div>
          <div class="stat-item">
            <span>负类样本</span>
            <strong>{{ precheck.negative_rows }}</strong>
          </div>
          <div class="stat-item">
            <span>近窗样本</span>
            <strong>{{ precheck.recent_feedback_rows }}</strong>
          </div>
        </div>
        <p class="hint">
          门槛：总样本>= {{ precheck.min_total_required }}，单类>= {{ precheck.min_class_required }}，近
          {{ precheck.recent_days_required }} 天有新增反馈
        </p>
        <ul v-if="precheck.blocking_reasons?.length" class="blocking-list">
          <li v-for="reason in precheck.blocking_reasons" :key="reason">{{ reason }}</li>
        </ul>
        <button
          class="small"
          :disabled="loadingRun || !precheck.meets_requirements"
          @click="runTuning"
        >
          {{ loadingRun ? '运行中...' : '确认并手动运行调参' }}
        </button>
      </div>

      <p v-if="pageError" class="error-text">{{ pageError }}</p>
      <p v-if="pageSuccess" class="success-text">{{ pageSuccess }}</p>
    </article>

    <article class="panel">
      <div class="card-head">
        <h3>调参历史</h3>
        <button class="ghost small" :disabled="loadingRuns" @click="loadRuns">刷新</button>
      </div>

      <p v-if="loadingRuns" class="hint">加载中...</p>
      <p v-else-if="!runs.length" class="hint">暂无调参历史</p>
      <ul v-else class="history-list tuning-run-list">
        <li v-for="item in runs" :key="item.id" :class="{ active: item.is_active }">
          <div class="history-top">
            <strong>{{ item.id }}</strong>
            <span class="badge" :class="item.is_active ? 'safe' : 'neutral'">
              {{ item.is_active ? '生效中' : item.status }}
            </span>
          </div>
          <div class="history-meta">
            <span>触发：{{ item.triggered_by }}</span>
            <span>{{ formatDate(item.triggered_at) }}</span>
          </div>
          <div class="tuning-meta">
            <span>样本：{{ item.row_count }}（+{{ item.positive_count }} / -{{ item.negative_count }}）</span>
            <span>最优：{{ item.best_params ? `w_url=${item.best_params.w_url_base}, th=${item.best_params.threshold}` : '--' }}</span>
          </div>
          <p v-if="item.error" class="error-text">{{ item.error }}</p>
          <div class="filter-actions">
            <button
              class="ghost small"
              :disabled="item.status !== 'succeeded' || item.is_active || activatingRunId === item.id"
              @click="activateRun(item.id)"
            >
              {{ activatingRunId === item.id ? '启用中...' : '设为生效版本' }}
            </button>
          </div>
        </li>
      </ul>
    </article>
  </section>
</template>
