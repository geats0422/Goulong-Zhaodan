<script setup>
import { useConfirmState, resolveConfirm } from '../../composables/useConfirm.js'

const state = useConfirmState()

function onCancel() {
  resolveConfirm(false)
}

function onConfirm() {
  resolveConfirm(true)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="state.open" class="confirm-overlay" role="presentation" @click.self="onCancel">
      <div class="confirm-dialog" role="alertdialog" aria-modal="true" :aria-labelledby="'confirm-title'" :aria-describedby="'confirm-message'">
        <p id="confirm-title" class="confirm-eyebrow">CONFIRM</p>
        <h3 class="confirm-title">{{ state.title }}</h3>
        <p id="confirm-message" class="confirm-message">{{ state.message }}</p>
        <div class="confirm-actions">
          <button type="button" class="confirm-btn ghost" @click="onCancel">{{ state.cancelText }}</button>
          <button type="button" class="confirm-btn solid" :class="{ danger: state.danger }" @click="onConfirm">{{ state.confirmText }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(4px);
}

.confirm-dialog {
  width: min(420px, 100%);
  border: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 80%, transparent);
  background: var(--color-surface, #171717);
  box-shadow: 0 0 40px rgba(0, 0, 0, 0.45), 0 0 24px var(--color-primary-glow, rgba(212, 175, 55, 0.12));
  padding: 24px 24px 20px;
  color: var(--color-text, #f1e8d7);
}

.confirm-eyebrow {
  margin: 0 0 8px;
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--color-primary, #e9c349);
}

.confirm-title {
  margin: 0 0 10px;
  font-family: var(--font-display, serif);
  font-size: 22px;
  font-weight: 600;
}

.confirm-message {
  margin: 0 0 22px;
  color: var(--color-muted, #d4ccb5);
  line-height: 1.7;
  font-size: 14px;
  white-space: pre-wrap;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.confirm-btn {
  min-height: 36px;
  padding: 0 16px;
  border-radius: 0.25rem;
  font-family: var(--font-body);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.confirm-btn.ghost {
  border: 1px solid var(--color-primary, #d4af37);
  background: transparent;
  color: var(--color-primary, #d4af37);
}

.confirm-btn.ghost:hover {
  background: color-mix(in srgb, var(--color-primary, #d4af37) 16%, transparent);
}

.confirm-btn.solid {
  border: 1px solid var(--color-primary, #d4af37);
  background: var(--color-primary, #d4af37);
  color: #1f1a12;
}

.confirm-btn.solid:hover {
  filter: brightness(1.05);
}

.confirm-btn.solid.danger {
  border-color: #c24132;
  background: #c24132;
  color: #fffaf0;
}

[data-theme="light"] .confirm-dialog {
  background: var(--color-surface, #fff);
  box-shadow: 0 18px 48px rgba(44, 36, 22, 0.18);
}
</style>
