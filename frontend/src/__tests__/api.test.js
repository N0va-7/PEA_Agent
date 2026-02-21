import { describe, expect, it } from 'vitest'

import { mapErrorMessage } from '../api'

describe('api error mapping', () => {
  it('maps known backend code', () => {
    expect(mapErrorMessage('invalid_credentials', 'fallback')).toBe('用户名或密码错误')
  })

  it('falls back to server message for unknown code', () => {
    expect(mapErrorMessage('custom_error', 'server side message')).toBe('server side message')
  })
})
