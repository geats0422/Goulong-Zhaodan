import { test } from 'node:test'
import assert from 'node:assert/strict'

// useAuth.js 模块顶层访问 sessionStorage，在纯 Node 环境下需要 polyfill。
if (!globalThis.sessionStorage) {
  const store = new Map()
  globalThis.sessionStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  }
}

const {
  getDocumentJobStatus,
  retryDocumentJob,
  pollDocumentJob,
  backoffDelay,
  MAX_NETWORK_ERRORS,
} = await import('../documentJobApi.js')

// ---------------------------------------------------------------------------
// 工具：可手动驱动的假调度器，避免真实 setTimeout，精确控制时间推进。
// ---------------------------------------------------------------------------
function createFakeScheduler() {
  const calls = []
  const scheduler = (fn, delay) => {
    const entry = { fn, delay, cancelled: false, ran: false }
    calls.push(entry)
    return () => {
      entry.cancelled = true
    }
  }
  scheduler.calls = calls
  return scheduler
}

// 刷新微任务，让异步 tick 主体跑完。
async function settle() {
  for (let i = 0; i < 30; i += 1) await Promise.resolve()
}

// 运行一个尚未执行/未取消的调度任务。
async function runOne(scheduler) {
  const entry = scheduler.calls.find((e) => !e.cancelled && !e.ran)
  if (!entry) return null
  entry.ran = true
  await entry.fn()
  await settle()
  return entry
}

// ---------------------------------------------------------------------------
// backoffDelay 纯函数
// ---------------------------------------------------------------------------
test('backoffDelay: 第 1 次失败立即重试 (0ms)', () => {
  assert.equal(backoffDelay(1), 0)
})

test('backoffDelay: 指数退避 1s→2s→4s→8s', () => {
  assert.equal(backoffDelay(2), 1000)
  assert.equal(backoffDelay(3), 2000)
  assert.equal(backoffDelay(4), 4000)
  assert.equal(backoffDelay(5), 8000)
})

test('backoffDelay: 上限 10s', () => {
  assert.equal(backoffDelay(6), 10000)
  assert.equal(backoffDelay(100), 10000)
})

// ---------------------------------------------------------------------------
// 终止状态：succeeded / failed / cancelled
// ---------------------------------------------------------------------------
test('pollDocumentJob: succeeded 立即停止并调用 onComplete', async () => {
  const job = { id: 'j1', status: 'succeeded', progress: 100 }
  const fetcher = async () => job
  const scheduler = createFakeScheduler()
  const updates = []
  let completed = null
  let errored = null

  pollDocumentJob('j1', {
    fetcher,
    scheduler,
    onUpdate: (j) => updates.push(j),
    onComplete: (j) => {
      completed = j
    },
    onError: (e) => {
      errored = e
    },
  })
  await settle()

  assert.equal(updates.length, 1)
  assert.deepEqual(updates[0], job)
  assert.deepEqual(completed, job)
  assert.equal(errored, null)
  assert.equal(scheduler.calls.length, 0, '成功后不应再调度')
})

test('pollDocumentJob: failed 触发 onError 并停止', async () => {
  const job = { id: 'j2', status: 'failed', error: '解析失败' }
  const fetcher = async () => job
  const scheduler = createFakeScheduler()
  let errored = null
  let completed = false

  pollDocumentJob('j2', {
    fetcher,
    scheduler,
    onComplete: () => {
      completed = true
    },
    onError: (e) => {
      errored = e
    },
  })
  await settle()

  assert.equal(completed, false)
  assert.ok(errored instanceof Error)
  assert.match(errored.message, /解析失败/)
  assert.equal(scheduler.calls.length, 0, '失败后不应再调度')
})

test('pollDocumentJob: failed error 对象使用 message 文案', async () => {
  const job = { id: 'j2-object-error', status: 'failed', error: { code: 'inspection_failed', message: '文档审查失败，请稍后重试' } }
  const fetcher = async () => job
  const scheduler = createFakeScheduler()
  let errored = null

  pollDocumentJob('j2-object-error', {
    fetcher,
    scheduler,
    onError: (e) => {
      errored = e
    },
  })
  await settle()

  assert.ok(errored instanceof Error)
  assert.equal(errored.message, '文档审查失败，请稍后重试')
  assert.equal(scheduler.calls.length, 0)
})

test('pollDocumentJob: cancelled 状态触发 onError 并停止', async () => {
  const job = { id: 'j3', status: 'cancelled' }
  const fetcher = async () => job
  const scheduler = createFakeScheduler()
  let errored = null

  pollDocumentJob('j3', { fetcher, scheduler, onError: (e) => { errored = e } })
  await settle()

  assert.ok(errored instanceof Error)
  assert.equal(scheduler.calls.length, 0)
})

// ---------------------------------------------------------------------------
// 正常轮询：pending → succeeded
// ---------------------------------------------------------------------------
test('pollDocumentJob: pending 多次轮询后成功', async () => {
  const pending = { id: 'j4', status: 'pending', progress: 10 }
  const indexing = { id: 'j4', status: 'running', stage: 'indexing', progress: 60 }
  const done = { id: 'j4', status: 'succeeded', progress: 100 }
  const responses = [pending, indexing, done]
  let callIndex = 0
  const fetcher = async () => responses[Math.min(callIndex++, responses.length - 1)]

  const scheduler = createFakeScheduler()
  const updates = []
  let completed = null

  pollDocumentJob('j4', {
    fetcher,
    scheduler,
    intervalMs: 2000,
    onUpdate: (j) => updates.push(j.status),
    onComplete: (j) => { completed = j },
  })
  await settle() // tick0: pending → schedule(interval=2000)

  assert.deepEqual(updates, ['pending'])
  assert.equal(scheduler.calls.length, 1)
  assert.equal(scheduler.calls[0].delay, 2000)

  await runOne(scheduler) // tick1: indexing → schedule
  assert.deepEqual(updates, ['pending', 'running'])

  await runOne(scheduler) // tick2: succeeded → onComplete
  assert.deepEqual(updates, ['pending', 'running', 'succeeded'])
  assert.deepEqual(completed, done)
  assert.equal(scheduler.calls.length, 2, '最后一次成功不再调度')
})

// ---------------------------------------------------------------------------
// 网络错误退避
// ---------------------------------------------------------------------------
test('pollDocumentJob: 网络错误指数退避序列 0→1s→2s→4s，第 5 次触发 onError', async () => {
  const fetcher = async () => {
    throw new Error('network down')
  }
  const scheduler = createFakeScheduler()
  let errored = null
  let updateCount = 0

  pollDocumentJob('j5', {
    fetcher,
    scheduler,
    onUpdate: () => { updateCount += 1 },
    onError: (e) => { errored = e },
  })
  await settle() // tick0: error #1 → schedule(delay=0)

  assert.equal(scheduler.calls.length, 1)
  assert.equal(scheduler.calls[0].delay, 0, '首次失败立即重试')

  await runOne(scheduler) // tick1: error #2 → delay 1000
  await runOne(scheduler) // tick2: error #3 → delay 2000
  await runOne(scheduler) // tick3: error #4 → delay 4000

  assert.deepEqual(
    scheduler.calls.map((c) => c.delay),
    [0, 1000, 2000, 4000],
  )

  await runOne(scheduler) // tick4: error #5 → onError，不再调度

  assert.ok(errored instanceof Error)
  assert.match(errored.message, /network down/)
  assert.equal(updateCount, 0, '网络错误期间不应回调 onUpdate')
  assert.equal(scheduler.calls.length, 4, '第 5 次失败不再调度退避')
})

test('pollDocumentJob: 网络错误成功恢复后连续错误计数清零', async () => {
  // 第 1 次抛错 → 退避；第 2 次成功 pending；第 3 次成功 succeeded
  const responses = [new Error('boom'), { status: 'pending' }, { status: 'succeeded' }]
  let i = 0
  const fetcher = async () => {
    const r = responses[i++]
    if (r instanceof Error) throw r
    return r
  }
  const scheduler = createFakeScheduler()
  const statuses = []
  let completed = false

  pollDocumentJob('j6', {
    fetcher,
    scheduler,
    onUpdate: (j) => statuses.push(j.status),
    onComplete: () => { completed = true },
  })
  await settle() // tick0: throw → backoff(0)
  assert.equal(scheduler.calls.length, 1)

  await runOne(scheduler) // tick1: pending → schedule(interval)
  assert.deepEqual(statuses, ['pending'])

  await runOne(scheduler) // tick2: succeeded → onComplete
  assert.equal(completed, true)
})

// ---------------------------------------------------------------------------
// cancel
// ---------------------------------------------------------------------------
test('pollDocumentJob: cancel 阻止后续请求与回调', async () => {
  const fetcher = async () => ({ status: 'pending' })
  const scheduler = createFakeScheduler()
  let updateCount = 0

  const poller = pollDocumentJob('j7', {
    fetcher,
    scheduler,
    onUpdate: () => { updateCount += 1 },
  })
  await settle() // tick0: pending → schedule(interval)

  assert.equal(updateCount, 1)
  assert.equal(scheduler.calls.length, 1)

  poller.cancel()
  assert.equal(scheduler.calls[0].cancelled, true, 'cancel 应标记已调度任务为取消')

  await runOne(scheduler) // 不会有新回调
  assert.equal(updateCount, 1)
  assert.equal(scheduler.calls.length, 1, 'cancel 后不再产生新调度')
})

test('pollDocumentJob: cancel 在退避等待期间也能停止', async () => {
  const fetcher = async () => {
    throw new Error('net')
  }
  const scheduler = createFakeScheduler()
  let errored = false

  const poller = pollDocumentJob('j8', {
    fetcher,
    scheduler,
    onError: () => { errored = true },
  })
  await settle() // tick0: error#1 → schedule(0)
  poller.cancel()

  await runOne(scheduler) // 被取消，不应继续
  assert.equal(errored, false)
})

// ---------------------------------------------------------------------------
// maxAttempts
// ---------------------------------------------------------------------------
test('pollDocumentJob: 超过 maxAttempts 触发 onError', async () => {
  const fetcher = async () => ({ status: 'pending' })
  const scheduler = createFakeScheduler()
  let errored = null

  pollDocumentJob('j9', {
    fetcher,
    scheduler,
    maxAttempts: 2,
    onError: (e) => { errored = e },
  })
  await settle() // tick0: attempts=1 pending → schedule
  await runOne(scheduler) // tick1: attempts=2 pending → schedule
  await runOne(scheduler) // tick2: attempts=3 > 2 → onError 超时

  assert.ok(errored instanceof Error)
  assert.match(errored.message, /超时|轮询/)
})

// ---------------------------------------------------------------------------
// 契约：getDocumentJobStatus / retryDocumentJob 的 URL 和方法
// useAuth.fetchWithAuth 内部使用全局 fetch，stub globalThis.fetch 即可拦截。
// ---------------------------------------------------------------------------

test('getDocumentJobStatus: GET /api/v1/document-jobs/{jobId}', async () => {
  const captured = { url: null, options: null }
  const original = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    captured.url = url
    captured.options = options || {}
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ id: 'job-abc', status: 'succeeded' }),
    }
  }
  try {
    const job = await getDocumentJobStatus('job-abc')
    assert.equal(captured.url, '/api/v1/document-jobs/job-abc')
    assert.equal(captured.options.method, undefined, 'GET 不应显式设置 method')
    assert.equal(job.id, 'job-abc')
  } finally {
    globalThis.fetch = original
  }
})

test('retryDocumentJob: POST /api/v1/document-jobs/{jobId}/retry', async () => {
  const captured = { url: null, options: null }
  const original = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    captured.url = url
    captured.options = options || {}
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ id: 'job-xyz', status: 'pending', retry_count: 1 }),
    }
  }
  try {
    const job = await retryDocumentJob('job-xyz')
    assert.equal(captured.url, '/api/v1/document-jobs/job-xyz/retry')
    assert.equal(captured.options.method, 'POST')
    assert.equal(job.retry_count, 1)
  } finally {
    globalThis.fetch = original
  }
})

test('常量 MAX_NETWORK_ERRORS === 5', () => {
  assert.equal(MAX_NETWORK_ERRORS, 5)
})

// ---------------------------------------------------------------------------
// useDocumentJobPolling composable 冒烟测试
// 验证结构、与 pollDocumentJob 的集成，以及 currentJob 自动更新。
// 注：onUnmounted 在非组件上下文下仅打印警告、不抛错（Vue 3 行为）。
// ---------------------------------------------------------------------------
test('useDocumentJobPolling: 返回结构正确并自动更新 currentJob', async () => {
  const { useDocumentJobPolling } = await import('../../composables/useDocumentJobPolling.js')
  const { startPolling, cancelPolling, currentJob } = useDocumentJobPolling()

  assert.equal(typeof startPolling, 'function')
  assert.equal(typeof cancelPolling, 'function')
  assert.ok(currentJob && 'value' in currentJob, 'currentJob 应为 ref')
  assert.equal(currentJob.value, null)

  const job = { id: 'c1', status: 'succeeded', progress: 100 }
  const scheduler = createFakeScheduler()
  let completed = null
  const poller = startPolling('c1', {
    fetcher: async () => job,
    scheduler,
    onComplete: (j) => { completed = j },
  })
  await settle()

  assert.deepEqual(completed, job)
  assert.deepEqual(currentJob.value, job, 'currentJob 应在 onUpdate/onComplete 时更新')
  assert.equal(typeof poller.cancel, 'function')

  // 不应抛错
  cancelPolling()
})

test('useDocumentJobPolling: 重新 startPolling 会先停止旧轮询', async () => {
  const { useDocumentJobPolling } = await import('../../composables/useDocumentJobPolling.js')
  const { startPolling, cancelPolling } = useDocumentJobPolling()

  const scheduler = createFakeScheduler()
  const fetcher = async () => ({ status: 'pending' })

  startPolling('old', { fetcher, scheduler })
  await settle()
  assert.equal(scheduler.calls.length, 1, '旧轮询启动并调度')

  startPolling('new', { fetcher, scheduler })
  await settle()
  assert.equal(
    scheduler.calls[0].cancelled,
    true,
    '再次 startPolling 应取消旧轮询的定时器，避免重复请求',
  )
  cancelPolling()
})
