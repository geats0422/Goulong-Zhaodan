<script setup>
const props = defineProps({
  modelValue: { type: [Boolean, Array], default: false },
  value: { type: [String, Number, Boolean], default: true },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: '' },
  ariaLabel: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'change'])

function isChecked() {
  if (Array.isArray(props.modelValue)) return props.modelValue.map(String).includes(String(props.value))
  return !!props.modelValue
}

function toggle() {
  if (props.disabled) return
  let next
  if (Array.isArray(props.modelValue)) {
    const set = new Set(props.modelValue.map(String))
    const key = String(props.value)
    if (set.has(key)) set.delete(key)
    else set.add(key)
    // 尽量保留原始类型：若原数组空则用 props.value 类型
    next = [...set].map((item) => {
      const hit = props.modelValue.find((v) => String(v) === item)
      return hit !== undefined ? hit : (item === String(props.value) ? props.value : item)
    })
  } else {
    next = !props.modelValue
  }
  emit('update:modelValue', next)
  emit('change', next)
}
</script>

<template>
  <label class="base-checkbox" :class="{ checked: isChecked(), disabled }">
    <button
      type="button"
      class="base-checkbox-box"
      role="checkbox"
      :aria-checked="isChecked()"
      :aria-label="ariaLabel || undefined"
      :disabled="disabled"
      @click.prevent="toggle"
    >
      <span v-if="isChecked()" class="material-symbols-outlined">check</span>
    </button>
    <span v-if="label || $slots.default" class="base-checkbox-label">
      <slot>{{ label }}</slot>
    </span>
  </label>
</template>

<style scoped>
.base-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
  color: var(--color-text, #f1e8d7);
}

.base-checkbox.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.base-checkbox-box {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--color-primary, #d4af37) 55%, transparent);
  background: transparent;
  color: var(--color-primary, #d4af37);
  border-radius: 0.125rem;
  padding: 0;
  cursor: inherit;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.base-checkbox-box .material-symbols-outlined {
  font-size: 14px;
  font-weight: 700;
}

.base-checkbox.checked .base-checkbox-box {
  background: color-mix(in srgb, var(--color-primary, #d4af37) 18%, transparent);
  border-color: var(--color-primary, #d4af37);
  box-shadow: 0 0 10px var(--color-primary-glow, rgba(212, 175, 55, 0.2));
}

.base-checkbox-label {
  font-size: 13px;
  line-height: 1.4;
  color: var(--color-muted, #d4ccb5);
}

.base-checkbox.checked .base-checkbox-label {
  color: var(--color-text, #f1e8d7);
}
</style>
