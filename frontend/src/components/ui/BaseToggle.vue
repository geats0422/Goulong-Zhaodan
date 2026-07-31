<script setup>
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'change'])

function toggle() {
  if (props.disabled) return
  const next = !props.modelValue
  emit('update:modelValue', next)
  emit('change', next)
}
</script>

<template>
  <label class="base-toggle" :class="{ on: modelValue, disabled }">
    <button
      type="button"
      class="base-toggle-track"
      role="switch"
      :aria-checked="modelValue"
      :disabled="disabled"
      @click.prevent="toggle"
    >
      <span class="base-toggle-thumb" />
    </button>
    <span v-if="label || $slots.default" class="base-toggle-label">
      <slot>{{ label }}</slot>
    </span>
  </label>
</template>

<style scoped>
.base-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.base-toggle.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.base-toggle-track {
  width: 36px;
  height: 20px;
  border-radius: 9999px;
  border: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 80%, transparent);
  background: color-mix(in srgb, var(--color-surface-raised, #202020) 90%, transparent);
  padding: 0;
  position: relative;
  cursor: inherit;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.base-toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 9999px;
  background: var(--color-muted, #99907c);
  transition: transform 0.15s, background 0.15s;
}

.base-toggle.on .base-toggle-track {
  border-color: var(--color-primary, #d4af37);
  background: color-mix(in srgb, var(--color-primary, #d4af37) 22%, transparent);
  box-shadow: 0 0 12px var(--color-primary-glow, rgba(212, 175, 55, 0.18));
}

.base-toggle.on .base-toggle-thumb {
  transform: translateX(16px);
  background: var(--color-primary, #d4af37);
}

.base-toggle-label {
  font-size: 13px;
  color: var(--color-muted, #d4ccb5);
}
</style>
