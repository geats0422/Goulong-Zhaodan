import { beforeEach, describe, expect, it, vi } from 'vitest'

import { buildLoginBody, useAuth } from './useAuth.js'

const { currentUser, fetchWithAuth, login, updateCurrentUserPhone } = useAuth()

describe('useAuth password login identity handling', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    sessionStorage.clear()
    globalThis.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        id: 'user-1',
        nickname: '测试用户',
        email: null,
        phone: null,
        access_token: 'token',
      }),
    }))
  })

  it('trims and lowercases username without treating it as a phone number', () => {
    expect(buildLoginBody('  Review_User  ', 'secret')).toEqual({
      username: 'review_user',
      password: 'secret',
    })
  })

  it('keeps email and phone login payloads compatible', () => {
    expect(buildLoginBody('user@example.com', 'secret')).toEqual({
      email: 'user@example.com',
      password: 'secret',
    })
    expect(buildLoginBody('13800138000', 'secret')).toEqual({
      phone: '13800138000',
      password: 'secret',
    })
  })

  it('posts the normalized username login body', async () => {
    await login('  Review_User  ', 'secret')

    expect(globalThis.fetch).toHaveBeenCalledWith('/auth/login', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ username: 'review_user', password: 'secret' }),
    }))
  })

  it('does not refresh, replay, or clear the session for an opted-out business 401', async () => {
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'user-1',
          nickname: '测试用户',
          email: null,
          phone: null,
          access_token: 'token',
        }),
      })
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: '验证码错误' }) })

    await login('user@example.com', 'secret')
    const response = await fetchWithAuth('/settings/phone', { method: 'POST' }, { skipAuthRefresh: true })

    expect(response.status).toBe(401)
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    expect(sessionStorage.getItem('goulong_access_token')).toBe('token')
    expect(JSON.parse(sessionStorage.getItem('goulong_current_user')).phone).toBeNull()
    expect(currentUser.value).toMatchObject({ id: 'user-1', phone: null })
  })

  it('keeps refresh and replay enabled for ordinary protected APIs', async () => {
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'user-1',
          nickname: '测试用户',
          email: null,
          phone: null,
          access_token: 'token',
        }),
      })
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: '令牌过期' }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: 'refreshed-token' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ ok: true }) })

    await login('user@example.com', 'secret')
    const response = await fetchWithAuth('/protected')

    expect(response.status).toBe(200)
    expect(globalThis.fetch).toHaveBeenCalledTimes(4)
    expect(globalThis.fetch.mock.calls[3][1].headers.Authorization).toBe('Bearer refreshed-token')
  })

  it('updates the reactive user and persisted session after phone binding', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 'user-1',
        nickname: '测试用户',
        email: null,
        phone: null,
        access_token: 'token',
      }),
    })
    await login('user@example.com', 'secret')

    updateCurrentUserPhone('13800138000')

    expect(currentUser.value.phone).toBe('13800138000')
    expect(JSON.parse(sessionStorage.getItem('goulong_current_user')).phone).toBe('13800138000')
  })
})
