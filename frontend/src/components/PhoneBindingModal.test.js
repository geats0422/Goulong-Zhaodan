import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

const { sendSmsCode, bindPhone, updateCurrentUserPhone } = vi.hoisted(() => ({
  sendSmsCode: vi.fn(),
  bindPhone: vi.fn(),
  updateCurrentUserPhone: vi.fn(),
}))

vi.mock('../composables/useAuth.js', () => ({
  useAuth: () => ({ sendSmsCode, updateCurrentUserPhone }),
}))

vi.mock('../services/settingsApi.js', () => ({ bindPhone }))

import PhoneBindingModal from './PhoneBindingModal.vue'

describe('PhoneBindingModal', () => {
  beforeEach(() => {
    sendSmsCode.mockReset()
    bindPhone.mockReset()
    updateCurrentUserPhone.mockReset()
  })

  it('provides accessible dialog semantics and a skippable action', async () => {
    const wrapper = mount(PhoneBindingModal)

    expect(wrapper.attributes('role')).toBe('dialog')
    expect(wrapper.attributes('aria-modal')).toBe('true')
    expect(wrapper.attributes('aria-labelledby')).toBe('phone-binding-title')
    expect(wrapper.find('label[for="phone-binding-phone"]').exists()).toBe(true)
    expect(wrapper.find('label[for="phone-binding-code"]').exists()).toBe(true)

    await wrapper.find('.phone-binding-skip').trigger('click')
    expect(wrapper.emitted('skip')).toBeTruthy()
  })

  it('sends the login-scene SMS code and binds the submitted phone', async () => {
    sendSmsCode.mockResolvedValueOnce({ expires_in: 60 })
    bindPhone.mockResolvedValueOnce({ phone: '13800138000' })
    const wrapper = mount(PhoneBindingModal, { attachTo: document.body })

    await wrapper.find('input[name="phone-binding-phone"]').setValue('13800138000')
    await wrapper.find('.phone-binding-send').trigger('click')
    await flushPromises()
    expect(sendSmsCode).toHaveBeenCalledWith('13800138000', 'login')

    await wrapper.find('input[name="phone-binding-code"]').setValue('123456')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(bindPhone).toHaveBeenCalledWith({ phone: '13800138000', code: '123456' })
    expect(updateCurrentUserPhone).toHaveBeenCalledWith('13800138000')
    expect(wrapper.find('.phone-binding-success').text()).toContain('手机号绑定成功')
    expect(wrapper.find('.phone-binding-success').attributes('aria-live')).toBe('polite')
    await nextTick()
    await nextTick()
    expect(document.activeElement).toBe(wrapper.find('.phone-binding-success button').element)
    wrapper.unmount()
  })

  it('shows backend validation and duplicate-phone errors', async () => {
    bindPhone.mockRejectedValueOnce(new Error('验证码错误或已过期'))
    const wrapper = mount(PhoneBindingModal)
    await wrapper.find('input[name="phone-binding-phone"]').setValue('13800138000')
    await wrapper.find('input[name="phone-binding-code"]').setValue('123456')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('验证码错误或已过期')

    bindPhone.mockRejectedValueOnce(new Error('手机号已被使用'))
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('手机号已被使用')
  })

  it('requires the success continue action instead of dismissing a completed binding', async () => {
    bindPhone.mockResolvedValueOnce({ phone: '13800138000' })
    const wrapper = mount(PhoneBindingModal)
    await wrapper.find('input[name="phone-binding-phone"]').setValue('13800138000')
    await wrapper.find('input[name="phone-binding-code"]').setValue('123456')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.phone-binding-skip').exists()).toBe(false)
    expect(wrapper.find('.phone-binding-card > .modal-header .icon-btn').exists()).toBe(false)
  })
})
