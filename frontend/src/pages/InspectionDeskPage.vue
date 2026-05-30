<script setup>
import AppTopNav from '../components/app/AppTopNav.vue'

const issues = [
  {
    icon: 'warning',
    tone: 'error',
    title: '私有规避标准触发',
    location: '原文第 14 页 -> 业务背景段落',
    object: '检测到绝密内部代号: [X7架构]。违反企业《绝密代号规避清单》。',
    suggestion: '建议替换为对外脱敏统称: [高算力云端集群]',
    tag: '[请经办人在原稿中手动脱敏]',
  },
  {
    icon: 'balance',
    tone: 'gold',
    title: '法定索引树偏离',
    location: '原文第 22 页 -> 支付条款',
    object: '原文规定预付款比例为 [10%]，存在极大商务风险。',
    citation: '《国家建筑工程标准合同库》 -> 第三章 -> 第二节 -> 第三段: 重大新基建项目预付款不得低于 30%',
  },
]
</script>

<template>
  <div class="dashboard-page inspection-page">
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
        <button class="inspection-action circuit-border" type="button">
          <span class="material-symbols-outlined">download</span>
          导出体检报告
        </button>
        <button class="inspection-action danger" type="button">
          <span class="material-symbols-outlined">local_fire_department</span>
          物理销毁案卷
        </button>
      </div>
    </div>

    <main class="inspection-main">
      <section class="document-pane">
        <div class="page-indicator">PAGE 1 / 45</div>
        <article class="document-sheet">
          <h1>A区数据中心建设项目<br />招 标 文 件</h1>
          <p>
            第一章 招标总则<br /><br />
            1.1 项目概况<br />
            本招标项目A区数据中心建设工程已由相关部门批准建设，建设资金来自企业自筹，项目出资比例为100%，招标人为地区数字科技发展有限公司。项目已具备招标条件，现对该项目的设计采购施工总承包（EPC）进行公开招标。
          </p>
          <p>
            1.2 项目要求与关键技术指标<br />
            为确保数据中心的高可用性与安全性，投标方需提供全面的架构设计方案。核心网络设备必须支持最新的SDN标准。在服务器集群配置方面，<mark>本项目将采用内部代号X7的架构，且预付款比例为10%</mark>，以保证建设初期的资金流转效率。所有存储设备需满足国家保密局三级等保要求。
          </p>
          <p>
            1.3 投标资质要求<br />
            (1) 投标人须具备独立法人资格，具备有效的营业执照。<br />
            (2) 具备电子与智能化工程专业承包一级资质及建筑机电安装工程专业承包一级资质。<br />
            (3) 近三年内至少完成过2个合同额不少于1亿元的类似数据中心项目。
          </p>
          <div class="document-watermark">内部绝密</div>
        </article>
      </section>

      <section class="diagnostic-pane">
        <div class="diagnostic-inner">
          <header class="diagnostic-header">
            <h2><span class="material-symbols-outlined">policy</span>智能审查诊断书</h2>
            <span class="diagnostic-alert"><i></i>[发现 2 处逻辑矛盾与红线偏离]</span>
          </header>

          <div class="issue-list">
            <article v-for="issue in issues" :key="issue.title" class="issue-card circuit-border card-top-highlight">
              <div class="issue-icon" :class="`issue-${issue.tone}`">
                <span class="material-symbols-outlined">{{ issue.icon }}</span>
              </div>
              <div class="issue-body">
                <h3>{{ issue.title }}</h3>
                <p class="issue-location">{{ issue.location }}</p>
                <p><span>诊断对象:</span>{{ issue.object }}</p>
                <p v-if="issue.suggestion" class="issue-suggestion"><span>修复建议:</span>{{ issue.suggestion }}</p>
                <div v-if="issue.citation" class="citation-box">
                  <div><span class="material-symbols-outlined">menu_book</span>引证标尺</div>
                  <p>{{ issue.citation }}</p>
                </div>
                <div v-if="issue.tag" class="issue-tag">{{ issue.tag }}</div>
              </div>
            </article>
          </div>

          <div class="report-end"><span></span><em>审查结束</em><span></span></div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.inspection-page {
  height: 100vh;
  overflow: hidden;
}

.inspection-action-bar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 0 64px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.3);
  background: #0e0e0e;
}

.inspection-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.inspection-breadcrumb strong {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #f2ca50;
  font-weight: 500;
}

.inspection-breadcrumb .material-symbols-outlined {
  font-size: 14px;
}

.inspection-actions {
  display: flex;
  gap: 12px;
}

.inspection-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(153, 144, 124, 0.28);
  padding: 10px 16px;
  background: #353534;
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 12px;
  cursor: pointer;
}

.inspection-action.danger {
  border-color: rgba(255, 180, 171, 0.3);
  background: #1a0a0a;
  color: #ffb4ab;
  box-shadow: 0 0 15px rgba(255, 180, 171, 0.1);
}

.inspection-main {
  height: calc(100vh - 144px);
  display: grid;
  grid-template-columns: 1fr 1fr;
  overflow: hidden;
}

.document-pane,
.diagnostic-pane {
  height: 100%;
  overflow-y: auto;
}

.document-pane {
  position: relative;
  border-right: 1px solid rgba(77, 70, 53, 0.35);
  background: #16181c;
  padding: 64px 48px;
}

.page-indicator {
  position: absolute;
  top: 24px;
  right: 32px;
  border: 1px solid rgba(77, 70, 53, 0.45);
  padding: 6px 10px;
  background: rgba(32, 31, 31, 0.8);
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
  margin: 0 0 48px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.42);
  color: #e5e2e1;
  text-align: center;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 26px;
}

.document-sheet p {
  margin-bottom: 28px;
  text-align: justify;
}

.document-sheet mark {
  border-bottom: 1px dashed #ffb4ab;
  border-radius: 2px;
  background: rgba(255, 180, 171, 0.15);
  color: #ffb4ab;
  padding: 0 4px;
}

.document-watermark {
  position: fixed;
  left: 18%;
  top: 45%;
  transform: rotate(-45deg);
  color: rgba(255, 255, 255, 0.05);
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 112px;
  font-weight: 700;
  pointer-events: none;
  user-select: none;
}

.diagnostic-pane {
  background: #0a0a0a;
  padding: 64px;
}

.diagnostic-inner {
  max-width: 640px;
  margin: 0 auto;
}

.diagnostic-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 32px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.55);
}

.diagnostic-header h2 {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: #f2ca50;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 24px;
}

.diagnostic-alert {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(255, 180, 171, 0.3);
  padding: 7px 10px;
  background: rgba(147, 0, 10, 0.2);
  color: #ffb4ab;
  font-family: "Geist", monospace;
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
  background: #121212;
}

.card-top-highlight {
  border-top: 2px solid #d4af37;
}

.issue-icon {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.issue-error {
  border: 1px solid rgba(255, 180, 171, 0.2);
  background: rgba(147, 0, 10, 0.1);
  color: #ffb4ab;
}

.issue-gold {
  border: 1px solid rgba(255, 249, 239, 0.2);
  background: rgba(255, 219, 60, 0.1);
  color: #ffe16d;
}

.issue-body h3 {
  margin: 0 0 14px;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 20px;
}

.issue-location {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.issue-body p {
  margin: 8px 0;
  color: #d0c5af;
  font-size: 14px;
}

.issue-body p span {
  margin-right: 8px;
  color: #99907c;
}

.issue-suggestion,
.issue-suggestion span {
  color: #f2ca50 !important;
}

.issue-tag {
  display: inline-flex;
  margin-top: 10px;
  border: 1px solid rgba(77, 70, 53, 0.35);
  padding: 7px 10px;
  background: rgba(53, 53, 52, 0.5);
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
}

.citation-box {
  margin-top: 14px;
  border-left: 2px solid #d4af37;
  padding: 14px;
  background: rgba(0, 0, 0, 0.6);
  color: rgba(227, 226, 226, 0.8);
  font-family: "Geist", monospace;
  font-size: 12px;
}

.citation-box div {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.35);
  color: #e9c349;
}

.report-end {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 14px;
  margin-top: 40px;
  opacity: 0.42;
}

.report-end span {
  width: 48px;
  height: 1px;
  background: #4d4635;
}

.report-end em {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
  font-style: normal;
}

@media (max-width: 980px) {
  .inspection-page {
    height: auto;
    overflow: visible;
  }

  .inspection-action-bar {
    height: auto;
    align-items: flex-start;
    flex-direction: column;
    padding: 18px 20px;
  }

  .inspection-actions {
    flex-wrap: wrap;
  }

  .inspection-main {
    height: auto;
    grid-template-columns: 1fr;
  }

  .document-pane,
  .diagnostic-pane {
    height: auto;
    overflow: visible;
    padding: 32px 20px;
  }

  .diagnostic-header,
  .issue-card {
    grid-template-columns: 1fr;
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
