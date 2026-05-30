<script setup>
import { ref } from 'vue'
import AppTopNav from '../components/app/AppTopNav.vue'

const activeTab = ref('system')
const tabs = [
  { key: 'system', label: '[系统设置]' },
  { key: 'knowledge', label: '[知识库设置]' },
  { key: 'taboo', label: '[违禁词设置]' },
]

const bindings = [
  { name: '微信', status: '未绑定', active: false },
  { name: '支付宝', status: '已绑定', active: true },
]

const knowledgeCards = [
  ['房建类', '施工组织设计、建筑安全规范'],
  ['市政类', '城市管网规划、绿化工程标准'],
  ['路桥类', '桥梁载荷测试、高速公路施工'],
  ['新基建', '数据中心建设、5G基站选址'],
]

const tabooWords = ['旧版主体名称V1', '内部绝密代号X7', '绝对化极限违约金条款']
</script>

<template>
  <div class="dashboard-page settings-page">
    <AppTopNav active="settings" />

    <main class="settings-main">
      <div class="settings-breadcrumb">
        <a href="/dashboard">首页</a>
        <span class="material-symbols-outlined">chevron_right</span>
        <strong>设置中枢</strong>
      </div>

      <header class="settings-header">
        <h1>系统配置与权限矩阵</h1>
      </header>

      <nav class="settings-tabs" aria-label="设置分类">
        <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" type="button" @click="activeTab = tab.key">
          {{ tab.label }}
        </button>
      </nav>

      <section v-if="activeTab === 'system'" class="settings-content system-settings">
        <article class="settings-card circuit-card card-primary">
          <header>
            <span class="material-symbols-outlined">account_balance_wallet</span>
            <h2>令鉴与配额</h2>
          </header>
          <div class="quota-grid">
            <div>
              <p class="setting-label">当前订阅等级</p>
              <strong><span class="material-symbols-outlined">workspace_premium</span>年度订阅 (Annual Pass)</strong>
            </div>
            <div>
              <div class="quota-head">
                <p class="setting-label">本月可用体检额度</p>
                <span>142 / 500</span>
              </div>
              <div class="quota-track"><i></i></div>
            </div>
          </div>
        </article>

        <article class="settings-card">
          <header>
            <span class="material-symbols-outlined muted-icon">badge</span>
            <h2>身份与绑定</h2>
          </header>
          <div class="identity-grid">
            <label>
              <span>用户名</span>
              <input readonly value="ZHL-ADMIN-8821" />
            </label>
            <label>
              <span>密码</span>
              <input readonly type="password" value="****************" />
            </label>
          </div>
          <div class="binding-section">
            <p class="setting-label">第三方鉴权绑定</p>
            <div class="binding-row">
              <span v-for="binding in bindings" :key="binding.name" class="binding-chip" :class="{ active: binding.active }">
                {{ binding.name }} <small>{{ binding.status }}</small>
              </span>
            </div>
          </div>
        </article>

        <article class="settings-card circuit-card card-primary safety-card">
          <div>
            <header>
              <span class="material-symbols-outlined">enhanced_encryption</span>
              <h2>数据安全锁</h2>
            </header>
            <p>激活后，所有会话结束立即清除内存残留痕迹，符合最高级保密标准。</p>
          </div>
          <div class="burn-toggle">
            <span>阅后即焚模式</span>
            <label aria-label="阅后即焚模式">
              <input checked type="checkbox" />
              <i></i>
            </label>
          </div>
        </article>
      </section>

      <section v-else-if="activeTab === 'knowledge'" class="settings-content knowledge-settings">
        <article class="settings-card public-tree">
          <header><span class="material-symbols-outlined">public</span><h2>公共索引树</h2></header>
          <ul>
            <li>招投标法律法规基准</li>
            <li>国家行业标准库V4</li>
            <li>地方性合规审查补充</li>
          </ul>
        </article>
        <article class="settings-card private-archive circuit-card card-primary">
          <header><span class="material-symbols-outlined">folder_special</span><h2>私有企业卷宗</h2></header>
          <div class="knowledge-grid">
            <div v-for="card in knowledgeCards" :key="card[0]"><strong>{{ card[0] }}</strong><span>{{ card[1] }}</span></div>
          </div>
        </article>
      </section>

      <section v-else class="settings-content taboo-settings">
        <article class="settings-card taboo-card">
          <header><span class="material-symbols-outlined">warning</span><h2>生成与审查规避标准</h2></header>
          <p>设置绝对红线规避标准，引擎在处理文本时将严格隔离以下词条。</p>
          <div class="taboo-input">
            <input placeholder="输入需规避的敏感词汇..." />
            <button type="button">隔离入库</button>
          </div>
          <div class="taboo-list">
            <span v-for="word in tabooWords" :key="word">[{{ word }}]<button type="button" aria-label="移除词条">×</button></span>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

<style scoped>
.settings-page {
  min-height: 100vh;
  background: #0f1115;
}

.settings-main {
  width: min(1440px, calc(100% - 40px));
  margin: 0 auto;
  padding: 48px 0 96px;
}

.settings-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.settings-breadcrumb a {
  color: inherit;
  text-decoration: none;
}

.settings-breadcrumb a:hover,
.settings-breadcrumb strong {
  color: #f2ca50;
  font-weight: 500;
}

.settings-breadcrumb .material-symbols-outlined {
  font-size: 16px;
}

.settings-header {
  margin: 24px 0 28px;
  padding-top: 16px;
  border-top: 2px solid rgba(212, 175, 55, 0.4);
}

.settings-header h1 {
  margin: 0;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.2;
}

.settings-tabs {
  display: flex;
  gap: 32px;
  border-bottom: 1px solid #353534;
  margin-bottom: 32px;
}

.settings-tabs button {
  position: relative;
  border: 0;
  padding: 0 0 16px;
  background: transparent;
  color: #d0c5af;
  font-size: 18px;
  cursor: pointer;
}

.settings-tabs button.active {
  border-bottom: 2px solid #d4af37;
  color: #f2ca50;
  box-shadow: 0 4px 10px -2px rgba(212, 175, 55, 0.3);
}

.settings-tabs button.active::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: -5px;
  width: 8px;
  height: 8px;
  transform: translateX(-50%);
  background: #d4af37;
}

.settings-content {
  max-width: 960px;
}

.system-settings,
.knowledge-settings,
.taboo-settings {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.knowledge-settings {
  max-width: 1120px;
  display: grid;
  grid-template-columns: 360px 1fr;
}

.settings-card {
  position: relative;
  border: 1px solid rgba(212, 175, 55, 0.2);
  padding: 24px;
  background: rgba(18, 18, 18, 0.72);
  backdrop-filter: blur(20px);
}

.card-primary {
  border-top: 2px solid rgba(212, 175, 55, 0.62);
}

.circuit-card::before,
.circuit-card::after {
  content: "";
  position: absolute;
  width: 7px;
  height: 7px;
  border: 1px solid #d4af37;
}

.circuit-card::before {
  top: 0;
  left: 0;
  border-right: 0;
  border-bottom: 0;
}

.circuit-card::after {
  right: 0;
  bottom: 0;
  border-top: 0;
  border-left: 0;
}

.settings-card header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.settings-card header h2 {
  margin: 0;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 24px;
}

.settings-card header .material-symbols-outlined {
  color: #f2ca50;
}

.muted-icon {
  color: #99907c !important;
}

.quota-grid,
.identity-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 32px;
}

.setting-label,
.identity-grid label span {
  display: block;
  margin: 0 0 8px;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.1em;
}

.quota-grid strong {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #ffe088;
  font-size: 18px;
}

.quota-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.quota-head span {
  color: #f2ca50;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.quota-track {
  position: relative;
  height: 8px;
  overflow: hidden;
  background: #2a2a2a;
}

.quota-track i {
  position: absolute;
  inset: 0 auto 0 0;
  width: 28.4%;
  background: #10b981;
  box-shadow: 0 0 10px rgba(74, 222, 128, 0.3);
}

.identity-grid input,
.taboo-input input {
  width: 100%;
  border: 0;
  border-bottom: 1px solid #4d4635;
  padding: 0 0 10px;
  background: transparent;
  color: #d0c5af;
  font-family: "Geist", monospace;
  outline: none;
}

.binding-section {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid #353534;
}

.binding-row,
.taboo-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.binding-chip,
.taboo-list span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #4d4635;
  padding: 8px 12px;
  background: #1c1b1b;
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.binding-chip.active {
  border-color: rgba(212, 175, 55, 0.35);
  background: rgba(242, 202, 80, 0.05);
  box-shadow: 0 0 15px rgba(212, 175, 55, 0.15);
}

.binding-chip small {
  color: #99907c;
}

.binding-chip.active small {
  color: #f2ca50;
}

.safety-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
}

.safety-card p {
  margin: 0;
  color: #99907c;
}

.burn-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #34d399;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.burn-toggle label {
  position: relative;
  width: 44px;
  height: 24px;
  cursor: pointer;
}

.burn-toggle input {
  opacity: 0;
}

.burn-toggle i {
  position: absolute;
  inset: 0;
  border: 1px solid #4d4635;
  border-radius: 999px;
  background: #353534;
}

.burn-toggle i::after {
  content: "";
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
}

.burn-toggle input:checked + i {
  background: #10b981;
  box-shadow: 0 0 10px rgba(74, 222, 128, 0.3);
}

.public-tree ul {
  list-style: none;
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
}

.public-tree li,
.knowledge-grid div {
  border: 1px solid #4d4635;
  padding: 14px;
  background: #1c1b1b;
  color: #d0c5af;
}

.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.knowledge-grid strong {
  display: block;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 22px;
}

.knowledge-grid span {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.taboo-card {
  border-top: 2px solid #ffb4ab;
  overflow: hidden;
}

.taboo-card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 120px;
  background: linear-gradient(180deg, rgba(255, 180, 171, 0.1), transparent);
  pointer-events: none;
}

.taboo-card header,
.taboo-card p,
.taboo-input,
.taboo-list {
  position: relative;
  z-index: 1;
}

.taboo-card header h2,
.taboo-card header .material-symbols-outlined {
  color: #ffb4ab;
}

.taboo-card p {
  color: #99907c;
}

.taboo-input {
  display: flex;
  gap: 10px;
  margin: 28px 0;
}

.taboo-input input:focus {
  border-bottom-color: #ffb4ab;
}

.taboo-input button {
  border: 1px solid #ffb4ab;
  padding: 10px 22px;
  background: rgba(255, 180, 171, 0.2);
  color: #ffb4ab;
  cursor: pointer;
}

.taboo-list span {
  border-color: rgba(255, 180, 171, 0.5);
}

.taboo-list button {
  border: 0;
  background: transparent;
  color: #99907c;
  cursor: pointer;
}

.taboo-list button:hover {
  color: #ffb4ab;
}

@media (max-width: 900px) {
  .settings-tabs,
  .safety-card,
  .taboo-input {
    align-items: flex-start;
    flex-direction: column;
  }

  .quota-grid,
  .identity-grid,
  .knowledge-settings,
  .knowledge-grid {
    grid-template-columns: 1fr;
  }
}
</style>
