import { beforeEach, describe, expect, it, vi } from 'vitest'

const { fetchWithAuth } = vi.hoisted(() => ({ fetchWithAuth: vi.fn() }))

vi.mock('../composables/useAuth.js', () => ({
  useAuth: () => ({ fetchWithAuth }),
}))

import { bindPhone, recoverPassword } from './settingsApi.js'

describe('settings phone binding API', () => {
  beforeEach(() => {
    fetchWithAuth.mockReset()
  })

  it('posts the phone and code to the authenticated binding endpoint', async () => {
    fetchWithAuth.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ phone: '13800138000' }),
    })

    await bindPhone({ phone: '13800138000', code: '123456' })

    expect(fetchWithAuth).toHaveBeenCalledWith(
      '/settings/phone',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: '13800138000', code: '123456' }),
      },
      { skipAuthRefresh: true },
    )
  })

  it('preserves backend errors for invalid codes and duplicate phones', async () => {
    fetchWithAuth.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: '验证码错误或已过期' }),
    })
    await expect(bindPhone({ phone: '13800138000', code: '000000' }))
      .rejects.toThrow('验证码错误或已过期')

    fetchWithAuth.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: '手机号已被使用' }),
    })
    await expect(bindPhone({ phone: '13800138000', code: '123456' }))
      .rejects.toThrow('手机号已被使用')
  })

  it('does not refresh the session for password recovery failures', async () => {
    fetchWithAuth.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: [{ msg: '验证码错误' }, { msg: '请稍后重试' }] }),
    })

    await expect(recoverPassword({ phone_code: '000000', new_password: 'Password1' }))
      .rejects.toThrow('验证码错误；请稍后重试')
    expect(fetchWithAuth).toHaveBeenCalledWith(
      '/settings/password/recover',
      expect.any(Object),
      { skipAuthRefresh: true },
    )
  })

  it('turns structured validation arrays into readable text', async () => {
    fetchWithAuth.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: [{ loc: ['body', 'code'], msg: '验证码格式错误' }] }),
    })

    await expect(bindPhone({ phone: '13800138000', code: 'bad' }))
      .rejects.toThrow('验证码格式错误')
  })
})
