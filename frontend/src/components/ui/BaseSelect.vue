<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { getEnabledOptionIndex, getNextEnabledOptionIndex } from './selectNavigation.js'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择' },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'change'])

const open = ref(false)
const rootRef = ref(null)
const activeIndex = ref(-1)
const labelId = useId()
const listboxId = `base-select-listbox-${Math.random().toString(36).slice(2)}`

const selectedLabel = computed(() => {
  const hit = props.options.find((opt) => String(opt.value) === String(props.modelValue))
  return hit?.label ?? props.placeholder
})

function openMenu() {
  if (props.disabled) return
  activeIndex.value = getEnabledOptionIndex(props.options, props.modelValue)
  open.value = true
}

function closeMenu() {
  open.value = false
}

function toggle() {
  if (props.disabled) return
  if (open.value) closeMenu()
  else openMenu()
}

function selectOption(opt) {
  if (props.disabled || opt.disabled) return
  emit('update:modelValue', opt.value)
  emit('change', opt.value)
  closeMenu()
}

function onDocClick(event) {
  if (!rootRef.value?.contains(event.target)) closeMenu()
}

function onKeydown(event) {
  if (props.disabled) return
  const navigation = { ArrowDown: 1, ArrowUp: -1, Home: 'home', End: 'end' }

  if (event.key === 'Escape') {
    if (open.value) {
      event.preventDefault()
      closeMenu()
    }
    return
  }

  if (Object.hasOwn(navigation, event.key)) {
    event.preventDefault()
    if (!open.value) openMenu()
    activeIndex.value = getNextEnabledOptionIndex(props.options, activeIndex.value, navigation[event.key])
    return
  }

  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    if (!open.value) {
      openMenu()
      return
    }
    const option = props.options[activeIndex.value]
    if (option) selectOption(option)
  }
}

watch(() => props.disabled, (v) => { if (v) closeMenu() })

onMounted(() => {
  document.addEventListener('click', onDocClick)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<template>
  <div ref="rootRef" class="base-select" :class="{ open, disabled }">
    <span v-if="label" :id="labelId" class="base-select-label">{{ label }}</span>
    <button
      type="button"
      class="base-select-trigger"
      :disabled="disabled"
      role="combobox"
      :aria-expanded="open"
      aria-haspopup="listbox"
      :aria-controls="listboxId"
      :aria-labelledby="label ? labelId : undefined"
      :aria-activedescendant="open && activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined"
      @keydown="onKeydown"
      @click="toggle"
    >
      <span class="base-select-value" :class="{ placeholder: modelValue === '' || modelValue == null }">{{ selectedLabel }}</span>
      <span class="material-symbols-outlined base-select-caret">expand_more</span>
    </button>
    <ul v-if="open" :id="listboxId" class="base-select-menu" role="listbox">
      <li
        v-for="(opt, index) in options"
        :key="String(opt.value)"
        :id="`${listboxId}-option-${index}`"
        role="option"
        class="base-select-option"
        :class="{ active: index === activeIndex, disabled: opt.disabled }"
        :aria-selected="String(opt.value) === String(modelValue)"
        :aria-disabled="opt.disabled || undefined"
        @click="selectOption(opt)"
      >
        {{ opt.label }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.base-select {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
}

.base-select-label {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--color-muted, #99907c);
}

.base-select-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-height: 38px;
  padding: 8px 4px;
  border: 0;
  border-bottom: 2px solid color-mix(in srgb, var(--color-border, #a67c00) 70%, transparent);
  background: transparent;
  color: var(--color-text, #f1e8d7);
  font-family: var(--font-body);
  font-size: 14px;
  cursor: pointer;
  text-align: left;
}

.base-select-trigger:hover:not(:disabled),
.base-select.open .base-select-trigger {
  border-bottom-color: var(--color-primary, #d4af37);
  box-shadow: 0 4px 12px var(--color-primary-glow, rgba(212, 175, 55, 0.15));
}

.base-select-trigger:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.base-select-value.placeholder {
  color: var(--color-muted, #99907c);
}

.base-select-caret {
  font-size: 18px;
  color: var(--color-primary, #d4af37);
  transition: transform 0.15s;
}

.base-select.open .base-select-caret {
  transform: rotate(180deg);
}

.base-select-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 40;
  margin: 0;
  padding: 6px 0;
  list-style: none;
  border: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 80%, transparent);
  background: var(--color-surface, #171717);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35), 0 0 16px var(--color-primary-glow, rgba(212, 175, 55, 0.08));
  max-height: 240px;
  overflow-y: auto;
}

.base-select-option {
  padding: 10px 12px;
  color: var(--color-text, #f1e8d7);
  font-size: 13px;
  cursor: pointer;
}

.base-select-option:hover,
.base-select-option.active {
  background: color-mix(in srgb, var(--color-primary, #d4af37) 12%, transparent);
  color: var(--color-primary, #d4af37);
}

.base-select-option.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

[data-theme="light"] .base-select-menu {
  background: var(--color-surface, #fff);
  box-shadow: 0 12px 28px rgba(44, 36, 22, 0.12);
}
</style>
