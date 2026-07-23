<script setup>
import { computed, onMounted, ref } from 'vue'
import AppTopNav from '../components/app/AppTopNav.vue'
import DashboardFooter from '../components/app/DashboardFooter.vue'
import { useAuth } from '../composables/useAuth.js'

const { fetchWithAuth } = useAuth()

const loading = ref(true)
const error = ref('')
const viewMode = ref('table')
const stats = ref({
  range: '7d',
  timezone: 'Asia/Shanghai',
  summary: { total_docs: 0, hit_docs: 0, banned_rate: 0, quota_consumed: 0 },
  trend: { dates: [], total_docs: [], hit_docs: [], banned_rate: [], quota_consumed: [] },
})

const summaryCards = computed(() => [
  { label: '上传文档数', value: `${stats.value.summary.total_docs}`, detail: '近 7 天累计上传' },
  { label: '违禁词出现率', value: `${(stats.value.summary.banned_rate * 100).toFixed(1)}%`, detail: '命中文档 / 总文档' },
  { label: '额度消耗', value: `${stats.value.summary.quota_consumed}`, detail: '近 7 天累计消耗' },
])

const trendRows = computed(() =>
  stats.value.trend.dates.map((date, index) => ({
    date,
    totalDocs: stats.value.trend.total_docs[index] ?? 0,
    hitDocs: stats.value.trend.hit_docs[index] ?? 0,
    bannedRate: `${((stats.value.trend.banned_rate[index] ?? 0) * 100).toFixed(1)}%`,
    quotaConsumed: stats.value.trend.quota_consumed[index] ?? 0,
  }))
)

const trendChartRows = computed(() => {
  const maxDocs = Math.max(...trendRows.value.map((row) => row.totalDocs), 1)
  const maxQuota = Math.max(...trendRows.value.map((row) => row.quotaConsumed), 1)
  return trendRows.value.map((row) => ({
    ...row,
    docsPercent: Math.max((row.totalDocs / maxDocs) * 100, 6),
    bannedPercent: Math.max(Number.parseFloat(row.bannedRate), 6),
    quotaPercent: Math.max((row.quotaConsumed / maxQuota) * 100, 6),
  }))
})

const isEmpty = computed(() => stats.value.summary.total_docs === 0)

async function fetchStats() {
  loading.value = true
  error.value = ''
  try {
    const response = await fetchWithAuth('/inspection/stats/history?range=7d')
    if (!response.ok) {
      throw new Error('统计接口请求失败')
    }
    stats.value = await response.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '未知错误'
    stats.value = {
      range: '7d',
      timezone: 'Asia/Shanghai',
      summary: { total_docs: 0, hit_docs: 0, banned_rate: 0, quota_consumed: 0 },
      trend: { dates: [], total_docs: [], hit_docs: [], banned_rate: [], quota_consumed: [] },
    }
  } finally {
    loading.value = false
  }
}

onMounted(fetchStats)
</script>

<template>
  <div class="dashboard-page statistics-page">
    <AppTopNav active="statistics" />
    <main class="statistics-main">
      <header class="statistics-header">
        <div>
          <p>OPERATIONS INSIGHT</p>
          <h1>数据统计</h1>
        </div>
        <span>最近 7 天</span>
      </header>

      <section class="stat-summary-grid">
        <article v-for="card in summaryCards" :key="card.label" class="stat-card circuit-card">
          <p>{{ card.label }}</p>
          <strong>{{ loading ? '--' : card.value }}</strong>
          <small>{{ card.detail }}</small>
        </article>
      </section>

      <section class="analytics-panel trend-panel">
        <header>
          <div>
            <p>INSPECTION TREND</p>
            <h2>体检趋势</h2>
          </div>
          <div class="header-actions">
            <div class="view-switch" role="tablist" aria-label="趋势视图切换">
              <button
                type="button"
                class="view-btn"
                :class="{ active: viewMode === 'table' }"
                @click="viewMode = 'table'"
              >
                表格
              </button>
              <button
                type="button"
                class="view-btn"
                :class="{ active: viewMode === 'chart' }"
                @click="viewMode = 'chart'"
              >
                图表
              </button>
            </div>
            <button type="button" class="retry-btn" @click="fetchStats">刷新</button>
          </div>
        </header>

        <p v-if="loading" class="hint">加载中...</p>
        <p v-else-if="error" class="hint error">加载失败：{{ error }}</p>
        <p v-else-if="isEmpty" class="hint">近 7 天暂无数据</p>

        <table v-else-if="viewMode === 'table'" class="trend-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>上传文档数</th>
              <th>命中文档数</th>
              <th>违禁词出现率</th>
              <th>额度消耗</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in trendRows" :key="row.date">
              <td>{{ row.date }}</td>
              <td>{{ row.totalDocs }}</td>
              <td>{{ row.hitDocs }}</td>
              <td>{{ row.bannedRate }}</td>
              <td>{{ row.quotaConsumed }}</td>
            </tr>
          </tbody>
        </table>

        <div v-else class="trend-chart" aria-label="近7天趋势图表">
          <div v-for="row in trendChartRows" :key="row.date" class="chart-day">
            <div class="bars">
              <span class="bar docs" :style="{ height: `${row.docsPercent}%` }" :title="`上传文档数 ${row.totalDocs}`"></span>
              <span class="bar banned" :style="{ height: `${row.bannedPercent}%` }" :title="`违禁词出现率 ${row.bannedRate}`"></span>
              <span class="bar quota" :style="{ height: `${row.quotaPercent}%` }" :title="`额度消耗 ${row.quotaConsumed}`"></span>
            </div>
            <small>{{ row.date.slice(5) }}</small>
          </div>
          <div class="legend">
            <span><i class="docs"></i> 上传文档数</span>
            <span><i class="banned"></i> 违禁词出现率</span>
            <span><i class="quota"></i> 额度消耗</span>
          </div>
        </div>
      </section>
    </main>

    <DashboardFooter />
  </div>
</template>

<style scoped>
.statistics-main {
  width: min(1200px, calc(100% - 40px));
  margin: 0 auto;
  padding: 48px 0 96px;
}

.statistics-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin: 20px 0 24px;
  border-bottom: 1px solid rgba(212, 175, 55, 0.24);
  padding-bottom: 16px;
}

.statistics-header p {
  margin: 0;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.16em;
}

.statistics-header h1 {
  margin: 8px 0 0;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
}

.statistics-header span {
  border: 1px solid rgba(212, 175, 55, 0.28);
  padding: 8px 12px;
  color: #f2ca50;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.stat-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.stat-card,
.analytics-panel {
  border: 1px solid rgba(212, 175, 55, 0.2);
  background: rgba(18, 18, 18, 0.72);
  backdrop-filter: blur(18px);
}

.stat-card {
  padding: 22px;
}

.stat-card p {
  margin: 0;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.stat-card strong {
  display: block;
  margin: 10px 0 8px;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 30px;
}

.stat-card small {
  color: #d0c5af;
}

.analytics-panel {
  margin-top: 24px;
  padding: 24px;
}

.analytics-panel header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.55);
  padding-bottom: 12px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.view-switch {
  display: inline-flex;
  border: 1px solid rgba(212, 175, 55, 0.2);
}

.view-btn {
  border: none;
  background: transparent;
  color: #d0c5af;
  padding: 6px 10px;
  cursor: pointer;
}

.view-btn.active {
  background: rgba(212, 175, 55, 0.16);
  color: #f2ca50;
}

.analytics-panel h2,
.analytics-panel p {
  margin: 0;
}

.retry-btn {
  border: 1px solid rgba(212, 175, 55, 0.28);
  color: #f2ca50;
  background: transparent;
  padding: 6px 12px;
  cursor: pointer;
}

.hint {
  color: #d0c5af;
}

.hint.error {
  color: #ffb4ab;
}

.trend-table {
  width: 100%;
  border-collapse: collapse;
}

.trend-table th,
.trend-table td {
  border-bottom: 1px solid rgba(77, 70, 53, 0.55);
  padding: 10px 6px;
  text-align: left;
}

.trend-chart {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 10px;
  align-items: end;
}

.chart-day {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.bars {
  width: 100%;
  height: 180px;
  display: flex;
  align-items: end;
  justify-content: center;
  gap: 4px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.55);
}

.bar {
  width: 18%;
  min-height: 8px;
  border-radius: 2px 2px 0 0;
}

.bar.docs,
.legend i.docs {
  background: #f2ca50;
}

.bar.banned,
.legend i.banned {
  background: #ffb4ab;
}

.bar.quota,
.legend i.quota {
  background: #34d399;
}

.chart-day small {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 11px;
}

.legend {
  grid-column: 1 / -1;
  display: flex;
  gap: 16px;
  margin-top: 8px;
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.legend i {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 6px;
}

@media (max-width: 980px) {
  .stat-summary-grid {
    grid-template-columns: 1fr;
  }

  .trend-table {
    font-size: 12px;
  }

  .trend-chart {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .legend {
    flex-direction: column;
    gap: 6px;
  }
}
</style>
