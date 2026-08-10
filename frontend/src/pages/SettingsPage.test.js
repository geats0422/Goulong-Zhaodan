import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const settingsMocks = vi.hoisted(() => ({
  getSettingsOverview: vi.fn(),
  updateProfile: vi.fn(),
  listApiKeys: vi.fn(),
  listArchivedKnowledge: vi.fn(),
  updatePassword: vi.fn(),
  recoverPassword: vi.fn(),
  sendPasswordRecoverCode: vi.fn(),
  updateKnowledgeDocument: vi.fn(),
  createTabooWord: vi.fn(),
  updateTabooWord: vi.fn(),
  deleteTabooWord: vi.fn(),
  createApiKey: vi.fn(),
  getApiKeySecret: vi.fn(),
  revokeApiKey: vi.fn(),
  deleteArchivedKnowledge: vi.fn(),
  bindPhone: vi.fn(),
}))

vi.mock('../services/settingsApi.js', () => settingsMocks)
vi.mock('../services/paymentApi.js', () => ({ listOrders: vi.fn() }))
vi.mock('../composables/knowledgeArchive.js', () => ({
  canDeleteArchived: () => false,
  applyArchiveDeletion: (items) => items,
}))
vi.mock('../composables/useAuth.js', () => ({
  useAuth: () => ({ sendSmsCode: vi.fn(), updateCurrentUserPhone: vi.fn() }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
}))

import SettingsPage from './SettingsPage.vue'

const baseProfile = (phone = null) => ({
  nickname: '测试用户',
  email: 'user@example.com',
  phone,
  burn_after_read: true,
  monthly_quota: 50,
  quota_used: 0,
  subscription_plan: 'free',
  subscription_label: '免费体验',
  subscription_period: '永久',
  subscription_price: '¥0',
  model_name: 'qwen-max',
})

function mockOverview(phone = null) {
  settingsMocks.getSettingsOverview.mockResolvedValue({
    profile: baseProfile(phone),
    knowledge: [],
    taboo_words: [],
  })
  settingsMocks.listApiKeys.mockResolvedValue([])
  settingsMocks.listArchivedKnowledge.mockResolvedValue({ documents: [] })
}

describe('SettingsPage phone binding', () => {
  beforeEach(() => {
    Object.values(settingsMocks).forEach((mock) => mock.mockReset())
    mockOverview()
  })

  it('does not include phone in profile saves and exposes a binding entry', async () => {
    const wrapper = mount(SettingsPage, {
      global: {
        stubs: {
          AppTopNav: true,
          DashboardFooter: true,
          PaymentModal: true,
          BaseToggle: true,
          BaseRadio: true,
          BaseCheckbox: true,
        },
      },
    })
    await flushPromises()

    const phoneRow = wrapper.findAll('.identity-row').find((row) => row.text().includes('绑定手机号'))
    expect(phoneRow.find('button').text()).toBe('绑定')

    await wrapper.findAll('button').find((button) => button.text() === '编辑').trigger('click')
    await wrapper.find('.edit-input').setValue('新昵称')
    await wrapper.findAll('button').find((button) => button.text() === '保存').trigger('click')
    await flushPromises()

    expect(settingsMocks.updateProfile).toHaveBeenCalledWith({
      nickname: '新昵称',
      email: 'user@example.com',
    })
    expect(settingsMocks.updateProfile.mock.calls[0][0]).not.toHaveProperty('phone')
  })

  it('marks an existing phone as bound and does not offer replacement', async () => {
    mockOverview('138****8000')
    const wrapper = mount(SettingsPage, {
      global: {
        stubs: {
          AppTopNav: true,
          DashboardFooter: true,
          PaymentModal: true,
          BaseToggle: true,
          BaseRadio: true,
          BaseCheckbox: true,
        },
      },
    })
    await flushPromises()

    const phoneRow = wrapper.findAll('.identity-row').find((row) => row.text().includes('绑定手机号'))
    expect(phoneRow.text()).toContain('已绑定')
    expect(phoneRow.find('button').exists()).toBe(false)
  })
})
