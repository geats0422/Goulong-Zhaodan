<script setup>
// 任务 16：统一额度不足错误弹窗。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 16
//
// 契约：
//   - 文案统一为「当前账户额度不足 / 本次审查需要更多算力额度。」；
//   - 主按钮跳转 action.path（来自后端契约，默认 /settings?tab=billing，永不指向 /pricing）；
//   - 关闭按钮 emit('close')，不改变路由；
//   - 跳转目标由 getQuotaAction(err) 决定，组件本身不感知错误码判定逻辑。
import { computed } from 'vue'
import { getQuotaAction } from '../composables/quotaError.js'

const props = defineProps({
  // 是否打开
  open: { type: Boolean, default: false },
  // 完整错误对象（携带 code/action 属性）；缺失时使用默认文案与默认跳转目标
  error: { type: Object, default: null },
})

const emit = defineEmits(['close', 'navigate'])

// 主按钮跳转目标：从错误中提取 action.path，安全回退到 /settings?tab=billing
const quotaAction = computed(() => getQuotaAction(props.error))

// 主按钮文案：使用 action.label，与设计稿对齐
const actionLabel = computed(() => quotaAction.value.label)

// 副标题：固定为设计稿文案
const SUBTITLE = '本次审查需要更多算力额度。'
const TITLE = '当前账户额度不足'

function handleClose() {
  // 关闭按钮：不改变路由，仅通知父组件关闭弹窗
  emit('close')
}

function handleNavigate() {
  // 主按钮：先通知父组件关闭弹窗，再触发跳转（保持 SPA 体验）
  emit('navigate', quotaAction.value.path)
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="quota-overlay" @click.self="handleClose">
      <div class="quota-dialog" role="alertdialog" aria-modal="true" aria-labelledby="quota-error-title" aria-describedby="quota-error-message">
        <span class="quota-icon material-symbols-outlined">error</span>
        <h3 id="quota-error-title" class="quota-title">{{ TITLE }}</h3>
        <p id="quota-error-message" class="quota-message">{{ SUBTITLE }}</p>
        <div class="quota-actions">
          <a
            :href="quotaAction.path"
            class="quota-btn quota-btn-primary"
            @click="handleNavigate"
          >{{ actionLabel }}</a>
          <button type="button" class="quota-btn quota-btn-ghost" @click="handleClose">关闭</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.quota-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
}

.quota-dialog {
  width: min(420px, 100%);
  border: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 80%, transparent);
  background: var(--color-surface, #171717);
  box-shadow: 0 0 40px rgba(0, 0, 0, 0.45), 0 0 24px var(--color-primary-glow, rgba(212, 175, 55, 0.12));
  padding: 28px 24px 22px;
  color: var(--color-text, #f1e8d7);
  text-align: center;
}

.quota-icon {
  font-size: 40px;
  color: #ffb4ab;
  font-variation-settings: 'FILL' 1;
}

.quota-title {
  margin: 12px 0 8px;
  font-family: var(--font-display, serif);
  font-size: 22px;
  font-weight: 600;
  color: var(--color-text, #f1e8d7);
}

.quota-message {
  margin: 0 0 22px;
  color: var(--color-muted, #d4ccb5);
  line-height: 1.7;
  font-size: 14px;
}

.quota-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quota-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0 18px;
  border-radius: 0.25rem;
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.15s, border-color 0.15s, color 0.15s, filter 0.15s;
}

.quota-btn-primary {
  border: 1px solid var(--color-primary, #d4af37);
  background: var(--color-primary, #d4af37);
  color: #1f1a12;
}

.quota-btn-primary:hover {
  filter: brightness(1.05);
}

.quota-btn-ghost {
  border: 1px solid color-mix(in srgb, var(--color-primary, #d4af37) 50%, transparent);
  background: transparent;
  color: var(--color-primary, #d4af37);
}

.quota-btn-ghost:hover {
  background: color-mix(in srgb, var(--color-primary, #d4af37) 12%, transparent);
}

[data-theme="light"] .quota-dialog {
  background: var(--color-surface, #fff);
  box-shadow: 0 18px 48px rgba(44, 36, 22, 0.18);
}
</style>
