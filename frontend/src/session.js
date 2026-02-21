import { computed, ref } from 'vue'

export const TOKEN_KEY = 'pea_agent_access_token'
export const API_KEY = 'pea_agent_api_base_url'
export const DEFAULT_API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

function safeStorageGet(key) {
  try {
    if (typeof localStorage !== 'undefined' && typeof localStorage.getItem === 'function') {
      return localStorage.getItem(key)
    }
  } catch {}
  return null
}

function safeStorageSet(key, value) {
  try {
    if (typeof localStorage !== 'undefined' && typeof localStorage.setItem === 'function') {
      localStorage.setItem(key, value)
    }
  } catch {}
}

function safeStorageRemove(key) {
  try {
    if (typeof localStorage !== 'undefined' && typeof localStorage.removeItem === 'function') {
      localStorage.removeItem(key)
    }
  } catch {}
}

export const apiBaseUrl = ref(safeStorageGet(API_KEY) || DEFAULT_API)
export const accessToken = ref(safeStorageGet(TOKEN_KEY) || '')
export const tokenExpireAt = ref('')

export const isAuthed = computed(() => !!accessToken.value)

export function normalizeBaseUrl(url) {
  return (url || '').trim().replace(/\/+$/, '')
}

export function saveApiBase(url) {
  apiBaseUrl.value = normalizeBaseUrl(url)
  safeStorageSet(API_KEY, apiBaseUrl.value)
}

export function setSession(token, expiresIn = 0) {
  accessToken.value = token
  safeStorageSet(TOKEN_KEY, token)
  tokenExpireAt.value = expiresIn > 0 ? new Date(Date.now() + expiresIn * 1000).toLocaleString() : ''
}

export function clearSession() {
  accessToken.value = ''
  tokenExpireAt.value = ''
  safeStorageRemove(TOKEN_KEY)
}
