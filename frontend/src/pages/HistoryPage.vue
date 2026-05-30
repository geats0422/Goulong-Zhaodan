<script setup>
import { useRouter } from 'vue-router'
import AppTopNav from '../components/app/AppTopNav.vue'

const router = useRouter()

const records = [
  {
    file: 'A区数据中心项目招标文件_v2.pdf',
    category: '新基建',
    time: '2026-05-28 14:30',
    bases: ['招投标法', '私有禁忌词'],
    result: '3处红线偏离',
    tone: 'error',
    destroyed: false,
  },
  {
    file: '2026标准外包合同.docx',
    category: '通用商务',
    time: '2026-05-27 09:15',
    bases: ['民法典合同编'],
    result: '纯净通过',
    tone: 'success',
    destroyed: false,
  },
  {
    file: '第三季度市政采购需求.pdf',
    category: '市政工程',
    time: '2026-05-26 16:45',
    bases: ['国家标准GB', '市政规范'],
    result: '1处逻辑矛盾',
    tone: 'warning',
    destroyed: false,
  },
  {
    file: '内部绝密架构企划书.pdf',
    category: '房建类',
    time: '2026-05-25 11:20',
    bases: ['私有禁忌词'],
    result: '纯净通过',
    tone: 'muted',
    destroyed: true,
  },
]

const openInspectionDetail = (record) => {
  if (!record.destroyed) {
    router.push('/inspection-desk')
  }
}
</script>

<template>
  <div class="dashboard-page history-page">
    <AppTopNav active="inspection" />

    <main class="history-main">
      <div class="history-breadcrumb">
        <a href="/dashboard">首页</a>
        <span>/</span>
        <strong>审查档案库</strong>
      </div>

      <header class="history-header">
        <h1>审查档案库</h1>
        <div class="history-filters">
          <label class="history-search">
            <span class="material-symbols-outlined">search</span>
            <input placeholder="检索案卷名称..." type="text" />
          </label>
          <label class="history-select">
            <select>
              <option>工程类别</option>
              <option>新基建</option>
              <option>通用商务</option>
              <option>市政工程</option>
              <option>房建类</option>
            </select>
            <span class="material-symbols-outlined">expand_more</span>
          </label>
          <label class="history-select">
            <select>
              <option>审查时间</option>
              <option>本周</option>
              <option>本月</option>
              <option>本季度</option>
            </select>
            <span class="material-symbols-outlined">expand_more</span>
          </label>
          <button class="history-filter-button hud-corners" type="button">
            <span class="material-symbols-outlined">filter_list</span>
            过滤
            <i></i>
          </button>
        </div>
      </header>

      <section class="archive-panel neo-circuit">
        <div class="archive-top-line"></div>
        <div class="archive-table-wrap">
          <table class="archive-table">
            <thead>
              <tr>
                <th>案卷名称</th>
                <th>工程类别</th>
                <th>体检时间</th>
                <th>挂载基座</th>
                <th>诊断结果</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in records" :key="record.file" :class="{ destroyed: record.destroyed }" @click="openInspectionDetail(record)">
                <td>
                  <div class="file-cell">
                    <span class="material-symbols-outlined">description</span>
                    <span>{{ record.file }}</span>
                  </div>
                </td>
                <td>{{ record.category }}</td>
                <td class="mono">{{ record.time }}</td>
                <td>
                  <div class="archive-tags">
                    <span v-for="base in record.bases" :key="base">[{{ base }}]</span>
                  </div>
                </td>
                <td>
                  <div v-if="!record.destroyed" class="result-pill" :class="`result-${record.tone}`">
                    <i></i>
                    <span>{{ record.result }}</span>
                  </div>
                  <div v-else class="result-pill result-muted">
                    <i></i>
                    <span>{{ record.result }}</span>
                  </div>
                </td>
                <td class="actions-cell">
                  <template v-if="!record.destroyed">
                    <a href="/inspection-desk" @click.stop>查看报告</a>
                    <button class="download-action" type="button">
                      <span class="material-symbols-outlined">download</span>
                      下载
                    </button>
                  </template>
                  <span v-else class="burned-badge">
                    <span class="material-symbols-outlined">local_fire_department</span>
                    案卷已物理销毁
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <nav class="history-pagination" aria-label="历史记录分页">
        <button type="button">上一页</button>
        <button class="active" type="button">1</button>
        <button type="button">2</button>
        <button type="button">3</button>
        <button type="button">下一页</button>
      </nav>
    </main>

    <footer class="history-footer">
      <p>© 2024 句龙 · 照胆. ALL RIGHTS RESERVED.</p>
      <div>
        <a href="#">加密策略</a>
        <a href="#">节点状态</a>
        <a href="#">API 接入</a>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.history-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0f1115;
}

.history-main {
  flex: 1;
  width: min(1440px, calc(100% - 40px));
  margin: 0 auto;
  padding: 56px 0 40px;
}

.history-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 32px;
  color: rgba(208, 197, 175, 0.62);
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.1em;
}

.history-breadcrumb a {
  color: inherit;
  text-decoration: none;
}

.history-breadcrumb a:hover,
.history-breadcrumb strong {
  color: #f2ca50;
  font-weight: 500;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 32px;
  margin-bottom: 48px;
}

.history-header h1 {
  margin: 0;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: clamp(36px, 4vw, 48px);
  line-height: 1.2;
}

.history-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.history-search,
.history-select {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-width: 210px;
}

.history-search .material-symbols-outlined,
.history-select .material-symbols-outlined {
  position: absolute;
  color: rgba(208, 197, 175, 0.55);
  pointer-events: none;
}

.history-search .material-symbols-outlined {
  left: 10px;
}

.history-select .material-symbols-outlined {
  right: 8px;
}

.history-search input,
.history-select select {
  width: 100%;
  border: 0;
  border-bottom: 1px solid rgba(77, 70, 53, 0.85);
  padding: 10px 34px 10px 40px;
  background: #201f1f;
  color: #e5e2e1;
  font: inherit;
  outline: none;
}

.history-select select {
  appearance: none;
  padding-left: 14px;
}

.history-search input:focus,
.history-select select:focus {
  border-bottom-color: #f2ca50;
}

.history-filter-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  padding: 11px 24px;
  background: #d4af37;
  color: #554300;
  font-family: "Geist", monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  cursor: pointer;
}

.hud-corners::before,
.hud-corners::after,
.hud-corners i::before,
.hud-corners i::after {
  content: "";
  position: absolute;
  width: 8px;
  height: 8px;
  border: 2px solid #d4af37;
}

.hud-corners::before { top: -4px; left: -4px; border-right: 0; border-bottom: 0; }
.hud-corners::after { top: -4px; right: -4px; border-left: 0; border-bottom: 0; }
.hud-corners i::before { bottom: -4px; left: -4px; border-right: 0; border-top: 0; }
.hud-corners i::after { bottom: -4px; right: -4px; border-left: 0; border-top: 0; }

.archive-panel {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(212, 175, 55, 0.2);
  background: rgba(18, 18, 18, 0.85);
  backdrop-filter: blur(20px);
}

.neo-circuit::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 1px;
  background: rgba(212, 175, 55, 0.2);
}

.neo-circuit::after {
  content: "";
  position: absolute;
  top: -2px;
  left: 50%;
  width: 4px;
  height: 4px;
  background: #d4af37;
}

.archive-top-line {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: #f2ca50;
}

.archive-table-wrap {
  overflow-x: auto;
}

.archive-table {
  width: 100%;
  min-width: 1000px;
  border-collapse: collapse;
  text-align: left;
}

.archive-table th {
  padding: 24px 24px;
  border-bottom: 1px solid rgba(242, 202, 80, 0.2);
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.archive-table td {
  padding: 20px 24px;
  border-bottom: 1px solid rgba(242, 202, 80, 0.1);
  color: #d0c5af;
}

.archive-table tbody tr {
  cursor: pointer;
  transition: background 0.2s;
}

.archive-table tbody tr.destroyed {
  cursor: default;
}

.archive-table tbody tr:hover {
  background: rgba(58, 57, 57, 0.2);
}

.archive-table tbody tr:nth-child(even):not(.destroyed) {
  background: rgba(28, 27, 27, 0.3);
}

.archive-table .destroyed {
  background: rgba(14, 14, 14, 0.82);
  color: rgba(208, 197, 175, 0.4);
  opacity: 0.78;
}

.file-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  color: #e5e2e1;
}

.destroyed .file-cell {
  color: rgba(208, 197, 175, 0.42);
  text-decoration: line-through;
}

.file-cell .material-symbols-outlined {
  color: rgba(242, 202, 80, 0.72);
}

.mono {
  font-family: "Geist", monospace;
  font-size: 13px;
}

.archive-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.archive-tags span {
  border: 1px solid rgba(77, 70, 53, 0.45);
  padding: 5px 8px;
  background: #2a2a2a;
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 10px;
}

.result-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.result-pill i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.result-error { color: #ffb4ab; filter: drop-shadow(0 0 8px rgba(255, 180, 171, 0.45)); }
.result-error i { background: #ffb4ab; }
.result-success { color: #4ade80; filter: drop-shadow(0 0 8px rgba(74, 222, 128, 0.3)); }
.result-success i { background: #4ade80; }
.result-warning { color: #fbbf24; filter: drop-shadow(0 0 8px rgba(251, 191, 36, 0.3)); }
.result-warning i { background: #fbbf24; }
.result-muted { color: rgba(74, 222, 128, 0.42); }
.result-muted i { background: rgba(74, 222, 128, 0.42); }

.actions-cell {
  text-align: right;
}

.actions-cell button,
.actions-cell a {
  border: 0;
  margin-left: 16px;
  background: transparent;
  color: #d0c5af;
  cursor: pointer;
  text-decoration: none;
}

.actions-cell button:hover,
.actions-cell a:hover,
.download-action {
  color: #f2ca50 !important;
}

.download-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.download-action .material-symbols-outlined {
  font-size: 16px;
}

.burned-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(255, 180, 171, 0.2);
  padding: 6px 10px;
  background: #201f1f;
  color: rgba(255, 180, 171, 0.62);
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
}

.burned-badge .material-symbols-outlined {
  font-size: 14px;
}

.history-pagination {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 32px;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.history-pagination button {
  min-width: 34px;
  height: 34px;
  border: 1px solid rgba(77, 70, 53, 0.55);
  background: #1c1b1b;
  color: #d0c5af;
  cursor: pointer;
}

.history-pagination button:first-child,
.history-pagination button:last-child {
  padding: 0 16px;
}

.history-pagination button:hover,
.history-pagination .active {
  border-color: #f2ca50;
  color: #f2ca50;
  background: rgba(242, 202, 80, 0.1);
}

.history-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  border-top: 1px solid rgba(242, 202, 80, 0.2);
  padding: 32px 64px;
  background: #0e0e0e;
  color: rgba(153, 144, 124, 0.8);
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.history-footer div {
  display: flex;
  gap: 24px;
}

.history-footer a {
  color: #d0c5af;
  text-decoration: none;
}

.history-footer a:hover {
  color: #f2ca50;
}

@media (max-width: 980px) {
  .history-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-filters,
  .history-search,
  .history-select {
    width: 100%;
  }

  .history-footer {
    align-items: flex-start;
    flex-direction: column;
    padding: 28px 20px;
  }
}
</style>
