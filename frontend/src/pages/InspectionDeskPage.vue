<script setup>
import AppTopNav from '../components/app/AppTopNav.vue'
import DashboardFooter from '../components/app/DashboardFooter.vue'

const issues = [
  {
    icon: 'warning',
    tone: 'danger',
    title: '私有规避标准触发',
    location: '原文第 14 页 -> 业务背景段落',
    object: '检测到内部代号 X7。违反企业《绝密代号规避清单》。',
    suggestion: '建议替换为对外脱敏统称：高算力云端集群。',
    tag: '[请经办人在原稿中手动脱敏]',
  },
  {
    icon: 'balance',
    tone: 'warn',
    title: '法定索引树偏离',
    location: '原文第 22 页 -> 支付条款',
    object: '原文规定预付款比例为 10%，存在商务风险。',
    citation: '《国家建筑工程标准合同库》 -> 第三章 -> 第二节 -> 第三段：重大新基建项目预付款不得低于 30%。',
  },
]
</script>

<template>
  <div class="inspection-page">
    <AppTopNav active="inspection" />

    <div class="inspection-action-bar">
      <div class="inspection-breadcrumb">
        <span>句龙</span>
        <span>/</span>
        <span>体检台</span>
        <span>/</span>
        <strong><span class="material-symbols-outlined">description</span>A区数据中心项目招标文件_v2.pdf</strong>
      </div>
      <div class="inspection-actions">
        <button class="inspection-action" type="button">
          <span class="material-symbols-outlined">download</span>
          导出体检报告
        </button>
        <button class="inspection-action danger" type="button">
          <span class="material-symbols-outlined">delete</span>
          删除记录
        </button>
      </div>
    </div>

    <main class="inspection-main">
      <section class="document-pane">
        <div class="page-indicator">PAGE 1 / 45</div>
        <article class="document-sheet">
          <h1>A区数据中心建设项目<br />招 标 文 件</h1>
          <p>
            第一章 招标总则。A区数据中心建设工程已具备招标条件，现对该项目的设计采购施工总承包进行公开招标。
          </p>
          <p>
            为确保数据中心高可用性与安全性，投标方需提供全面的架构设计方案。<mark>本项目将采用内部代号 X7 的架构，且预付款比例为 10%</mark>，以保证建设初期的资金流转效率。
          </p>
          <p>
            投标人须具备独立法人资格，具备有效营业执照，并在近三年内完成过同类数据中心项目。
          </p>
          <div class="document-watermark">内部绝密</div>
        </article>
      </section>

      <section class="diagnostic-pane">
        <header class="diagnostic-header">
          <h2><span class="material-symbols-outlined">policy</span>智能审查诊断书</h2>
          <span class="diagnostic-alert"><i></i>[发现 2 处逻辑矛盾与红线偏离]</span>
        </header>

        <div class="issue-list">
          <article v-for="issue in issues" :key="issue.title" class="issue-card card-top-highlight">
            <div class="issue-icon" :class="`issue-${issue.tone}`">
              <span class="material-symbols-outlined">{{ issue.icon }}</span>
            </div>
            <div class="issue-body">
              <h3>{{ issue.title }}</h3>
              <p class="issue-location">{{ issue.location }}</p>
              <p><span>诊断对象：</span>{{ issue.object }}</p>
              <p v-if="issue.suggestion" class="issue-suggestion"><span>修复建议：</span>{{ issue.suggestion }}</p>
              <div v-if="issue.citation" class="citation-box">
                <div><span class="material-symbols-outlined">menu_book</span>引证标尺</div>
                <p>{{ issue.citation }}</p>
              </div>
              <div v-if="issue.tag" class="issue-tag">{{ issue.tag }}</div>
            </div>
          </article>
        </div>

        <div class="report-end"><span></span><em>审查结束</em><span></span></div>
      </section>
    </main>

    <DashboardFooter />
  </div>
</template>

<style scoped>
.inspection-page {
  min-height: 100vh;
  background: #0f1115;
}

.inspection-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 64px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.3);
  background: #0e0e0e;
}

.inspection-breadcrumb,
.inspection-actions,
.inspection-action,
.diagnostic-header h2,
.diagnostic-alert {
  display: flex;
  align-items: center;
}

.inspection-breadcrumb {
  gap: 8px;
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.inspection-breadcrumb strong,
.diagnostic-header h2 {
  color: #f2ca50;
}

.inspection-actions {
  gap: 12px;
}

.inspection-action {
  gap: 8px;
  border: 1px solid rgba(153, 144, 124, 0.28);
  padding: 10px 16px;
  background: #353534;
  color: #e5e2e1;
  cursor: pointer;
}

.inspection-action.danger {
  border-color: rgba(255, 180, 171, 0.3);
  background: #1a0a0a;
  color: #ffb4ab;
}

.inspection-main {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: calc(100vh - 137px);
}

.document-pane,
.diagnostic-pane {
  overflow-y: auto;
  padding: 56px 48px;
}

.document-pane {
  position: relative;
  border-right: 1px solid rgba(77, 70, 53, 0.35);
  background: #16181c;
}

.page-indicator {
  position: absolute;
  top: 24px;
  right: 32px;
  border: 1px solid rgba(77, 70, 53, 0.45);
  padding: 6px 10px;
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.document-sheet {
  position: relative;
  max-width: 680px;
  margin: 0 auto;
  color: rgba(229, 226, 225, 0.78);
  line-height: 1.9;
}

.document-sheet h1 {
  margin: 0 0 40px;
  color: #e5e2e1;
  text-align: center;
}

.document-sheet mark {
  background: rgba(255, 180, 171, 0.15);
  color: #ffb4ab;
}

.document-watermark {
  position: fixed;
  left: 18%;
  top: 45%;
  transform: rotate(-45deg);
  color: rgba(255, 255, 255, 0.05);
  font-size: 96px;
  font-weight: 700;
  pointer-events: none;
}

.diagnostic-pane {
  background: #0a0a0a;
}

.diagnostic-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 32px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.55);
}

.diagnostic-header h2 {
  gap: 12px;
  margin: 0;
}

.diagnostic-alert {
  gap: 6px;
  border: 1px solid rgba(255, 180, 171, 0.3);
  padding: 7px 10px;
  color: #ffb4ab;
  font-size: 12px;
}

.diagnostic-alert i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ffb4ab;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.issue-card {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 16px;
  padding: 24px;
  border: 1px solid rgba(77, 70, 53, 0.35);
  background: #121212;
}

.card-top-highlight {
  border-top: 2px solid #d4af37;
}

.issue-icon {
  color: #f2ca50;
}

.issue-danger {
  color: #ffb4ab;
}

.issue-body h3 {
  margin: 0 0 14px;
  color: #e5e2e1;
}

.issue-body p,
.citation-box {
  color: #d0c5af;
}

.issue-location,
.issue-tag,
.report-end em {
  color: #99907c;
}

.citation-box {
  margin-top: 14px;
  border-left: 2px solid #d4af37;
  padding: 14px;
  background: rgba(0, 0, 0, 0.6);
}

.report-end {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 14px;
  margin-top: 40px;
}

.report-end span {
  width: 48px;
  height: 1px;
  background: #4d4635;
}

@media (max-width: 980px) {
  .inspection-action-bar,
  .diagnostic-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .inspection-action-bar,
  .document-pane,
  .diagnostic-pane {
    padding: 24px 20px;
  }

  .inspection-main,
  .issue-card {
    grid-template-columns: 1fr;
  }
}
</style>
