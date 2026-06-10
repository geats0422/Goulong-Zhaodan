<script setup>
defineProps({
  currentStep: { type: Number, default: 1 },
  steps: {
    type: Array,
    default: () => [
      { label: '解析文件', icon: 'upload_file' },
      { label: '审查准备', icon: 'checklist' },
      { label: '审查报告', icon: 'assessment' },
    ],
  },
})
</script>

<template>
  <div class="step-header">
    <div
      v-for="(step, idx) in steps"
      :key="idx"
      class="step-item"
      :class="{
        'step-active': idx + 1 === currentStep,
        'step-done': idx + 1 < currentStep,
        'step-error': step.error,
      }"
    >
      <div class="step-indicator">
        <span v-if="idx + 1 < currentStep" class="material-symbols-outlined">check</span>
        <span v-else-if="step.error" class="material-symbols-outlined">error</span>
        <span v-else class="step-number">{{ idx + 1 }}</span>
      </div>
      <span class="step-label">{{ step.label }}</span>
      <span v-if="idx < steps.length - 1" class="step-connector" />
    </div>
  </div>
</template>

<style scoped>
.step-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 20px 0;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}

.step-indicator {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 1px solid rgba(77, 70, 53, 0.35);
  background: #1a1a1a;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.step-indicator .material-symbols-outlined {
  font-size: 16px;
}

.step-active .step-indicator {
  border-color: #d4af37;
  background: rgba(212, 175, 55, 0.1);
  color: #d4af37;
  box-shadow: 0 0 12px rgba(212, 175, 55, 0.15);
}

.step-done .step-indicator {
  border-color: rgba(212, 175, 55, 0.5);
  background: rgba(212, 175, 55, 0.15);
  color: #d4af37;
}

.step-error .step-indicator {
  border-color: rgba(255, 180, 171, 0.5);
  background: rgba(147, 0, 10, 0.15);
  color: #ffb4ab;
}

.step-label {
  font-family: "Geist", monospace;
  font-size: 12px;
  color: #99907c;
  letter-spacing: 0.06em;
}

.step-active .step-label {
  color: #d4af37;
}

.step-done .step-label {
  color: #d0c5af;
}

.step-connector {
  width: 48px;
  height: 1px;
  background: rgba(77, 70, 53, 0.35);
  margin: 0 8px;
}

[data-theme="light"] .step-indicator {
  border-color: rgba(111, 86, 48, 0.25);
  background: #fff;
  color: #6f5630;
}

[data-theme="light"] .step-active .step-indicator {
  border-color: #c5961a;
  background: rgba(197, 150, 26, 0.08);
  color: #c5961a;
  box-shadow: 0 0 12px rgba(197, 150, 26, 0.1);
}

[data-theme="light"] .step-done .step-indicator {
  border-color: rgba(197, 150, 26, 0.4);
  background: rgba(197, 150, 26, 0.1);
  color: #c5961a;
}

[data-theme="light"] .step-label {
  color: #8a7a66;
}

[data-theme="light"] .step-active .step-label {
  color: #c5961a;
}

[data-theme="light"] .step-done .step-label {
  color: #6f5630;
}

[data-theme="light"] .step-connector {
  background: rgba(111, 86, 48, 0.2);
}
</style>
