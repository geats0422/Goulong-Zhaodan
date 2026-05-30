<script setup>
import AppTopNav from '../components/app/AppTopNav.vue'

const rules = ['招投标法', '房建施工规范']
const avoidRules = ['内部代号X7', '旧版公司名']
const records = [
  { icon: 'picture_as_pdf', name: 'A区数据中心投标文件.pdf', status: '3 Warnings', tone: 'amber' },
  { icon: 'description', name: '2026标准外包合同.docx', status: 'Clean Pass', tone: 'green' },
  { icon: 'picture_as_pdf', name: '第三季度采购需求.pdf', status: 'Avoidance Triggered', tone: 'red' },
]
</script>

<template>
  <div class="dashboard-page">
    <AppTopNav active="dashboard" />

    <main class="dashboard-main">
      <header class="dashboard-header">
        <div class="breadcrumb">
          <span>句龙</span>
          <span>/</span>
          <strong>靶场大盘</strong>
        </div>
        <div class="dashboard-title-row">
          <h1>欢迎调遣，<span>经办人张三</span></h1>
          <div class="secure-status"><i></i>TEE 本地静默保护中</div>
        </div>
      </header>

      <section class="dropzone-card">
        <div class="grid-pattern"></div>
        <div class="dropzone-inner">
          <div class="upload-orb">
            <span class="material-symbols-outlined">file_upload</span>
          </div>
          <div>
            <h2>极速载入案卷</h2>
            <p>拖拽企业材料包至此，或点击调用系统窗口</p>
          </div>
          <button class="primary-action" type="button">
            <span class="material-symbols-outlined">add_circle</span>
            发起智能初审
          </button>
        </div>
      </section>

      <section class="dashboard-grid">
        <article class="dashboard-panel">
          <div class="panel-accent"></div>
          <header class="panel-header">
            <span class="material-symbols-outlined">rule</span>
            <h3>当前挂载标尺</h3>
          </header>
          <div class="panel-section">
            <h4>层级索引树</h4>
            <div class="tag-row">
              <span v-for="rule in rules" :key="rule" class="tag">{{ rule }}</span>
              <span class="tag tag-add"><span class="material-symbols-outlined">add</span>添加</span>
            </div>
          </div>
          <div class="panel-section">
            <h4>负面规避清单</h4>
            <div class="tag-row">
              <span v-for="rule in avoidRules" :key="rule" class="tag tag-danger">{{ rule }}</span>
            </div>
          </div>
        </article>

        <article class="dashboard-panel">
          <div class="panel-accent"></div>
          <header class="panel-header panel-header-between">
            <div>
              <span class="material-symbols-outlined">history</span>
              <h3>近期体检记录</h3>
            </div>
            <button class="panel-link" type="button" aria-label="查看全部">
              <span class="material-symbols-outlined">arrow_forward</span>
            </button>
          </header>
          <div class="record-list">
            <div v-for="record in records" :key="record.name" class="record-item">
              <div class="record-title">
                <span class="material-symbols-outlined">{{ record.icon }}</span>
                <span>{{ record.name }}</span>
              </div>
              <span class="status-pill" :class="`status-${record.tone}`">{{ record.status }}</span>
            </div>
          </div>
        </article>

        <article class="dashboard-panel lab-panel">
          <div class="lab-accent"></div>
          <header class="panel-header lab-header">
            <span class="material-symbols-outlined">science</span>
            <h3>句龙实验室</h3>
          </header>
          <div class="lab-content">
            <div>
              <p class="lab-label">Experimental Feature</p>
              <h4>项目统筹与架构生成引擎</h4>
              <div class="engine-preview">
                <div class="engine-glow"></div>
                <span class="material-symbols-outlined">account_tree</span>
                <span>[Mermaid Engine Rendering...]</span>
              </div>
            </div>
            <button class="lab-button" type="button">
              <span class="material-symbols-outlined">input</span>
              进入实验室
            </button>
          </div>
        </article>
      </section>
    </main>

    <footer class="dashboard-footer">
      <strong>句龙 · 照胆</strong>
      <div>
        <a href="#">隐私政策</a>
        <a href="#">服务条款</a>
        <a href="#">技术文档</a>
        <a href="#">安全白皮书</a>
      </div>
      <span>© 2024 句龙 · 照胆. SECURED BY TIGER TALLY PROTOCOL</span>
    </footer>
  </div>
</template>
