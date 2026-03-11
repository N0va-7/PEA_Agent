<script setup>
import { computed, onMounted, ref } from 'vue'

import { sandboxFetch } from '../api'

const loading = ref(false)
const actionError = ref('')
const actionMessage = ref('')
const rulesVersion = ref('')
const rules = ref([])
const selectedRulePath = ref('')
const selectedRule = ref(null)
const editorPath = ref('')
const editorContent = ref('')
const creating = ref(false)
const saving = ref(false)
const deleting = ref(false)

const filteredRules = computed(() => rules.value)

async function loadRules() {
  loading.value = true
  actionError.value = ''
  try {
    const response = await sandboxFetch('/rules')
    const payload = await response.json()
    rulesVersion.value = payload.rules_version || ''
    rules.value = payload.rules || []
    if (!selectedRulePath.value && rules.value.length) {
      await openRule(rules.value[0].path)
    }
  } catch (error) {
    actionError.value = `读取规则失败: ${error.message}`
  } finally {
    loading.value = false
  }
}

async function openRule(rulePath) {
  selectedRulePath.value = rulePath
  actionError.value = ''
  try {
    const response = await sandboxFetch(`/rules/${encodeURI(rulePath)}`)
    const payload = await response.json()
    selectedRule.value = payload
    editorPath.value = payload.path || ''
    editorContent.value = payload.content || ''
    creating.value = false
  } catch (error) {
    actionError.value = `读取规则详情失败: ${error.message}`
  }
}

function startCreateRule() {
  creating.value = true
  selectedRulePath.value = ''
  selectedRule.value = null
  editorPath.value = ''
  editorContent.value = ''
}

async function saveRule() {
  actionError.value = ''
  actionMessage.value = ''
  if (!editorPath.value.trim() || !editorContent.value.trim()) {
    actionError.value = '规则路径和内容不能为空'
    return
  }

  saving.value = true
  try {
    const method = creating.value ? 'POST' : 'PUT'
    const path = creating.value ? '/rules' : `/rules/${encodeURI(editorPath.value.trim())}`
    const response = await sandboxFetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: editorPath.value.trim(),
        content: editorContent.value,
      }),
    })
    const payload = await response.json()
    rulesVersion.value = payload.rules_version || rulesVersion.value
    actionMessage.value = creating.value ? '规则已创建' : '规则已更新'
    creating.value = false
    await loadRules()
    await openRule(payload.rule.path)
  } catch (error) {
    actionError.value = `保存规则失败: ${error.message}`
  } finally {
    saving.value = false
  }
}

async function deleteRule() {
  if (!selectedRule.value?.path) return
  if (!window.confirm(`确认删除规则 ${selectedRule.value.path}？`)) return
  actionError.value = ''
  actionMessage.value = ''
  deleting.value = true
  try {
    await sandboxFetch(`/rules/${encodeURI(selectedRule.value.path)}`, { method: 'DELETE' })
    actionMessage.value = '规则已删除'
    selectedRule.value = null
    selectedRulePath.value = ''
    editorPath.value = ''
    editorContent.value = ''
    await loadRules()
  } catch (error) {
    actionError.value = `删除规则失败: ${error.message}`
  } finally {
    deleting.value = false
  }
}

onMounted(loadRules)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <h2>静态沙箱规则</h2>
      <p>查看和维护独立静态沙箱的 YARA 规则。`external/*` 只读，`local/*` 可编辑。</p>
    </header>

    <article class="panel">
      <div class="section-head">
        <h3>规则版本</h3>
        <p>{{ rulesVersion || '--' }}</p>
      </div>
      <div class="sandbox-rule-toolbar">
        <button class="ghost" @click="loadRules">刷新规则</button>
        <button @click="startCreateRule">新建本地规则</button>
      </div>
      <p v-if="actionMessage" class="success-text">{{ actionMessage }}</p>
      <p v-if="actionError" class="error-text">{{ actionError }}</p>
    </article>

    <div class="split-layout sandbox-rules-layout">
      <article class="panel">
        <div class="list-head">
          <h3>规则列表</h3>
          <p class="hint" v-if="loading">加载中...</p>
        </div>
        <ul class="history-records sandbox-rule-list" v-if="filteredRules.length">
          <li v-for="rule in filteredRules" :key="rule.path" class="history-item">
            <article
              class="history-select sandbox-rule-card"
              :class="{ selected: selectedRulePath === rule.path }"
              role="button"
              tabindex="0"
              @click="openRule(rule.path)"
            >
              <div class="history-select-top">
                <strong>{{ rule.path }}</strong>
                <em class="badge" :class="rule.editable ? 'safe' : 'neutral'">{{ rule.editable ? '可编辑' : '只读' }}</em>
              </div>
              <p class="rule-card-tags">{{ rule.rule_names?.join(', ') || '--' }}</p>
              <div class="history-select-foot rule-select-foot">
                <span>{{ rule.source_kind }}</span>
                <span>{{ rule.size_bytes }} B</span>
              </div>
            </article>
          </li>
        </ul>
      </article>

      <article class="panel detail-panel">
        <div class="section-head">
          <h3>{{ creating ? '新建规则' : selectedRule?.path || '规则详情' }}</h3>
          <p>{{ selectedRule?.editable || creating ? '可编辑' : '只读' }}</p>
        </div>

        <label class="field-label">
          <span>规则路径</span>
          <input v-model="editorPath" :disabled="!creating && !selectedRule?.editable" placeholder="local/your_rule.yar" />
        </label>

        <label class="field-label">
          <span>规则内容</span>
          <textarea v-model="editorContent" rows="22" :disabled="!creating && !selectedRule?.editable" placeholder="输入真实规则内容"></textarea>
        </label>

        <div class="sandbox-rule-toolbar">
          <button :disabled="saving || (!creating && !selectedRule?.editable)" @click="saveRule">{{ saving ? '保存中...' : '保存规则' }}</button>
          <button class="ghost danger-action" :disabled="deleting || creating || !selectedRule?.editable" @click="deleteRule">{{ deleting ? '删除中...' : '删除规则' }}</button>
        </div>
      </article>
    </div>
  </section>
</template>
