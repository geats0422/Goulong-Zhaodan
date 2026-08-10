import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { login, loginByCode, sendSmsCode, push, bindPhone } = vi.hoisted(() => ({
  login: vi.fn(),
  loginByCode: vi.fn(),
  sendSmsCode: vi.fn(),
  push: vi.fn(),
  bindPhone: vi.fn(),
}))

vi.mock('../composables/useAuth.js', () => ({
  useAuth: () => ({ login, loginByCode, sendSmsCode }),
}))

vi.mock('../services/settingsApi.js', () => ({ bindPhone }))

vi.mock('../composables/useTheme.js', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

import LoginPage from './LoginPage.vue'

describe('LoginPage password login', () => {
  beforeEach(() => {
    login.mockReset()
    loginByCode.mockReset()
    sendSmsCode.mockReset()
    push.mockReset()
    bindPhone.mockReset()
  })

  it('accepts a username identity and shows a skippable binding prompt', async () => {
    login.mockResolvedValueOnce({ require_phone_binding: true })
    const wrapper = mount(LoginPage)

    await wrapper.find('input[autocomplete="username"]').setValue('  Review_User  ')
    await wrapper.find('input[autocomplete="current-password"]').setValue('password123')
    await wrapper.find('.base-checkbox-box').trigger('click')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(login).toHaveBeenCalledWith('  Review_User  ', 'password123')
    expect(wrapper.find('.phone-binding-modal').exists()).toBe(true)
    expect(push).not.toHaveBeenCalled()

    await wrapper.find('.phone-binding-skip').trigger('click')
    expect(push).toHaveBeenCalledWith('/dashboard')
  })

  it('keeps a password login without binding requirement on the dashboard path', async () => {
    login.mockResolvedValueOnce({ require_phone_binding: false })
    const wrapper = mount(LoginPage)

    await wrapper.find('input[autocomplete="username"]').setValue('user@example.com')
    await wrapper.find('input[autocomplete="current-password"]').setValue('password123')
    await wrapper.find('.base-checkbox-box').trigger('click')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(push).toHaveBeenCalledWith('/dashboard')
    expect(wrapper.find('.phone-binding-modal').exists()).toBe(false)
  })

  it('ignores a second password-login submission while the first is pending', async () => {
    let resolveLogin
    login.mockReturnValueOnce(new Promise((resolve) => { resolveLogin = resolve }))
    const wrapper = mount(LoginPage)

    await wrapper.find('input[autocomplete="username"]').setValue('user@example.com')
    await wrapper.find('input[autocomplete="current-password"]').setValue('password123')
    await wrapper.find('.base-checkbox-box').trigger('click')
    const form = wrapper.find('form')
    const firstSubmit = form.trigger('submit')
    await form.trigger('submit')

    expect(login).toHaveBeenCalledTimes(1)
    resolveLogin({ require_phone_binding: false })
    await firstSubmit
    await flushPromises()
  })

  it('ignores a second SMS-login submission while the first is pending', async () => {
    let resolveLogin
    loginByCode.mockReturnValueOnce(new Promise((resolve) => { resolveLogin = resolve }))
    const wrapper = mount(LoginPage)

    await wrapper.findAll('.tab-bar button')[0].trigger('click')
    await wrapper.find('input[type="tel"]').setValue('13800138000')
    await wrapper.find('input[placeholder="请输入短信验证码"]').setValue('123456')
    await wrapper.find('.base-checkbox-box').trigger('click')
    const form = wrapper.find('form')
    const firstSubmit = form.trigger('submit')
    await form.trigger('submit')

    expect(loginByCode).toHaveBeenCalledTimes(1)
    resolveLogin({ require_phone_binding: false })
    await firstSubmit
    await flushPromises()
  })

  it('accepts only ASCII six-digit SMS codes', async () => {
    const wrapper = mount(LoginPage)

    await wrapper.findAll('.tab-bar button')[0].trigger('click')
    await wrapper.find('input[type="tel"]').setValue('13800138000')
    await wrapper.find('input[placeholder="请输入短信验证码"]').setValue('１２３４５６')
    await wrapper.find('.base-checkbox-box').trigger('click')
    await wrapper.find('form').trigger('submit')

    expect(loginByCode).not.toHaveBeenCalled()
    expect(wrapper.find('.alert-error').text()).toContain('验证码')
  })

  it('renders structured login errors without object coercion', async () => {
    login.mockRejectedValueOnce({ detail: [{ msg: '账号不存在' }, { msg: '请检查登录信息' }] })
    const wrapper = mount(LoginPage)

    await wrapper.find('input[autocomplete="username"]').setValue('user@example.com')
    await wrapper.find('input[autocomplete="current-password"]').setValue('password123')
    await wrapper.find('.base-checkbox-box').trigger('click')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.alert-error').text()).toContain('账号不存在；请检查登录信息')
    expect(wrapper.text()).not.toContain('[object Object]')
  })

  it('gives the terms checkbox an accessible name', () => {
    const wrapper = mount(LoginPage)

    expect(wrapper.find('[role="checkbox"]').attributes('aria-label')).toBe('同意服务条款与隐私政策')
  })
})
