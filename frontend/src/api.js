import { accessToken, apiBaseUrl, normalizeBaseUrl } from './session'

export const SANDBOX_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_SANDBOX_BASE_URL || 'http://127.0.0.1:8000')

const ERROR_MAP = {
  invalid_credentials: '用户名或密码错误',
  too_many_login_attempts: '登录失败次数过多，请稍后再试',
  invalid_token: '登录状态无效，请重新登录',
  analysis_not_found: '分析记录不存在',
  url_analysis_not_found: 'URL 分析记录不存在',
  report_not_found: '报告文件不存在',
  invalid_file_type: '仅支持上传 .eml 文件',
  empty_file: '上传文件为空',
  file_too_large: '上传文件过大',
  invalid_datetime: '时间格式错误',
  invalid_url: '请输入有效的 http/https URL',
  too_many_urls: '单次提交的 URL 数量过多',
  forbidden: '当前账号无权限执行该操作',
}

export function mapErrorMessage(code, fallback) {
  return ERROR_MAP[code] || fallback || '请求失败'
}

async function parseError(response) {
  let payload = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  const code = payload?.code || `http_${response.status}`
  const message = mapErrorMessage(code, payload?.message || payload?.detail || `HTTP ${response.status}`)
  const err = new Error(message)
  err.code = code
  err.status = response.status
  err.detail = payload?.detail
  throw err
}

export async function apiFetch(path, options = {}) {
  const base = normalizeBaseUrl(apiBaseUrl.value)
  if (!base) {
    const err = new Error('后端地址未配置')
    err.code = 'missing_api_base'
    throw err
  }

  const headers = { ...(options.headers || {}) }
  if (accessToken.value) {
    headers.Authorization = `Bearer ${accessToken.value}`
  }

  const response = await fetch(`${base}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    await parseError(response)
  }
  return response
}

export async function loginApi(username, password) {
  const base = normalizeBaseUrl(apiBaseUrl.value)
  const response = await fetch(`${base}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    await parseError(response)
  }
  return await response.json()
}

export function isAuthError(error) {
  const code = String(error?.code || '')
  return code === 'invalid_token' || code === 'http_401' || Number(error?.status) === 401
}

export async function sandboxFetch(path, options = {}) {
  if (!SANDBOX_BASE_URL) {
    const err = new Error('静态沙箱地址未配置')
    err.code = 'missing_sandbox_base'
    throw err
  }

  const response = await fetch(`${SANDBOX_BASE_URL}${path}`, {
    ...options,
    headers: { ...(options.headers || {}) },
  })

  if (!response.ok) {
    await parseError(response)
  }
  return response
}
