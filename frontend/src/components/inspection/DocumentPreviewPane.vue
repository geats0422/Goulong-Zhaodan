<script setup>
defineProps({
  text: { type: String, default: '' },
})

function renderParagraphs(text) {
  if (!text) return []
  return text.split(/\n/)
}
</script>

<template>
  <div class="document-preview">
    <div class="preview-header">
      <span class="material-symbols-outlined">article</span>
      <span>结构化文档预览</span>
    </div>
    <div v-if="text" class="preview-content">
        <article class="document-sheet">
          <template v-for="(paragraph, idx) in renderParagraphs(text)" :key="idx">
            <p v-if="paragraph.trim()">{{ paragraph }}</p>
            <div v-else class="paragraph-spacer"></div>
          </template>
        </article>
    </div>
    <div v-else class="preview-placeholder">
      <span class="material-symbols-outlined">note_add</span>
      <p>暂无文档内容</p>
    </div>
  </div>
</template>

<style scoped>
.document-preview {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #16181c;
  border-right: 1px solid rgba(77, 70, 53, 0.35);
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.3);
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.06em;
}

.preview-header .material-symbols-outlined {
  font-size: 16px;
  color: #d4af37;
}

.preview-content {
  flex: 1;
  min-height: 0;
  overflow-y: scroll;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #d4af37 rgba(77, 70, 53, 0.14);
  padding: 32px 28px 32px 24px;
}

.preview-content::-webkit-scrollbar {
  width: 12px;
}

.preview-content::-webkit-scrollbar-track {
  background: rgba(77, 70, 53, 0.14);
  border-left: 1px solid rgba(77, 70, 53, 0.18);
}

.preview-content::-webkit-scrollbar-thumb {
  min-height: 72px;
  border: 3px solid rgba(255, 255, 255, 0.02);
  border-radius: 999px;
  background: #d4af37;
}

.preview-content::-webkit-scrollbar-thumb:hover {
  background: #f2ca50;
}

.document-sheet {
  max-width: 680px;
  margin: 0 auto;
}

.document-sheet p {
  margin-bottom: 6px;
  color: rgba(229, 226, 225, 0.72);
  line-height: 1.9;
  text-align: justify;
  font-size: 14px;
}

.paragraph-spacer {
  height: 12px;
}

.preview-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #99907c;
}

.preview-placeholder .material-symbols-outlined {
  font-size: 48px;
  opacity: 0.3;
}

.preview-placeholder p {
  font-family: "Geist", monospace;
  font-size: 12px;
}

[data-theme="light"] .document-preview {
  background: #fff;
  border-right-color: rgba(111, 86, 48, 0.15);
}

[data-theme="light"] .preview-header {
  border-bottom-color: rgba(111, 86, 48, 0.15);
  color: #6f5630;
}

[data-theme="light"] .preview-header .material-symbols-outlined {
  color: #c5961a;
}

[data-theme="light"] .preview-content {
  scrollbar-color: #d49f00 rgba(111, 86, 48, 0.12);
}

[data-theme="light"] .preview-content::-webkit-scrollbar-track {
  background: rgba(111, 86, 48, 0.12);
  border-left-color: rgba(111, 86, 48, 0.16);
}

[data-theme="light"] .preview-content::-webkit-scrollbar-thumb {
  border-color: rgba(255, 255, 255, 0.45);
  background: #d49f00;
}

[data-theme="light"] .document-sheet p {
  color: rgba(44, 36, 22, 0.72);
}

[data-theme="light"] .preview-placeholder {
  color: #8a7a66;
}
</style>
