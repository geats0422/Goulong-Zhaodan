<script setup>
const props = defineProps({
  modelValue: { type: [String, Number, Boolean], default: '' },
  value: { type: [String, Number, Boolean], required: true },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: '' },
  name: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'change'])

function isChecked() {
  return String(props.modelValue) === String(props.value)
}

function select() {
  if (props.disabled) return
  emit('update:modelValue', props.value)
  emit('change', props.value)
}
</script>

<template>
  <label class="base-radio" :class="{ checked: isChecked(), disabled }">
    <button
      type="button"
      class="base-radio-dot"
      role="radio"
      :aria-checked="isChecked()"
      :disabled="disabled"
      :name="name"
      @click.prevent="select"
    >
      <i v-if="isChecked()" />
    </button>
    <span v-if="label || $slots.default" class="base-radio-label">
      <slot>{{ label }}</slot>
    </span>
  </label>
</template>

<style scoped>
.base-radio {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.base-radio.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.base-radio-dot {
  width: 18px;
  height: 18px;
  border-radius: 9999px;
  border: 1px solid color-mix(in srgb, var(--color-primary, #d4af37) 55%, transparent);
  background: transparent;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.base-radio-dot i {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background: var(--color-primary, #d4af37);
  box-shadow: 0 0 8px var(--color-primary-glow, rgba(212, 175, 55, 0.35));
}

.base-radio.checked .base-radio-dot {
  border-color: var(--color-primary, #d4af37);
  box-shadow: 0 0 10px var(--color-primary-glow, rgba(212, 175, 55, 0.2));
}

.base-radio-label {
  font-size: 13px;
  color: var(--color-muted, #d4ccb5);
}

.base-radio.checked .base-radio-label {
  color: var(--color-text, #f1e8d7);
}
</style>
