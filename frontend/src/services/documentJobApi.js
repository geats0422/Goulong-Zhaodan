import { useAuth } from '../composables/useAuth.js'

const { fetchWithAuth } = useAuth()

const TERMINAL_FAILURE_STATUSES = ['failed', 'cancelled']
const MAX_BACKOFF_MS = 10000

/** 连续网络错误达到此次数后停止轮询并报错。 */
export const MAX_NETWORK_ERRORS = 5

async function parseResponse(response) {
  if (response.status === 204) return null
  let data
  try {
    const text = await response.text()
    data = text ? JSON.parse(text) : {}
  } catch {
    if (!response.ok) throw new Error(`请求失败（HTTP ${response.status}）`)
    return null
  }
  if (!response.ok) {
    throw new Error(data.detail || `请求失败（HTTP ${response.status}）`)
  }
  return data
}

/**
 * 查询文档处理任务状态。
 * @param {string} jobId 任务 ID
 * @returns {Promise<object>} { id, type, status, stage, progress, message, parser_engine,
 *   retry_count, max_retries, knowledge_version_id, inspection_record_id,
 *   created_at, updated_at, finished_at, error }
 */
export async function getDocumentJobStatus(jobId) {
  return parseResponse(await fetchWithAuth(`/api/v1/document-jobs/${jobId}`))
}

/**
 * 重试一个失败/取消的文档处理任务，返回更新后的任务对象。
 * @param {string} jobId 任务 ID
 */
export async function retryDocumentJob(jobId) {
  return parseResponse(
    await fetchWithAuth(`/api/v1/document-jobs/${jobId}/retry`, { method: 'POST' }),
  )
}

/**
 * 计算连续网络错误后的退避延迟（毫秒）。
 * - 第 1 次失败：立即重试（0ms）
 * - 之后按 1s → 2s → 4s → 8s 指数增长，上限 10s
 * @param {number} consecutiveFailures 连续失败次数（从 1 开始）
 */
export function backoffDelay(consecutiveFailures) {
  if (consecutiveFailures <= 1) return 0
  const delay = Math.pow(2, consecutiveFailures - 2) * 1000
  return Math.min(delay, MAX_BACKOFF_MS)
}

function defaultSchedule(fn, delay) {
  const id = setTimeout(fn, delay)
  return () => clearTimeout(id)
}

/**
 * 轮询文档任务状态，直到任务进入终态（succeeded/failed/cancelled）或被取消。
 *
 * 终止条件：
 * - status === 'succeeded' → 调用 onComplete 并停止
 * - status === 'failed' | 'cancelled' → 调用 onError(job.error) 并停止
 * - 连续网络错误达到 MAX_NETWORK_ERRORS(5) 次 → 调用 onError 并停止
 * - 超过 maxAttempts 次查询 → 调用 onError(超时) 并停止
 *
 * 网络错误退避：首次失败立即重试，之后指数退避（1s→2s→4s→…，上限 10s），
 * 期间任何一次成功都会重置连续错误计数。
 *
 * @param {string} jobId
 * @param {object} options
 * @param {(job: object) => void} [options.onUpdate] 每次成功获取状态时回调
 * @param {(job: object) => void} [options.onComplete] 任务成功时回调
 * @param {(err: Error) => void} [options.onError] 任务失败/取消/网络错误/超时时回调
 * @param {number} [options.intervalMs=2000] 正常轮询间隔
 * @param {number} [options.maxAttempts=600] 最大查询次数（含网络错误重试）
 * @returns {{ cancel: () => void }} 控制对象，cancel() 立即停止轮询并清理定时器。
 *   组件卸载时必须调用 cancel。
 */
export function pollDocumentJob(jobId, options = {}) {
  const {
    onUpdate,
    onComplete,
    onError,
    intervalMs = 2000,
    maxAttempts = 600,
    // 以下两个参数用于依赖注入测试，调用方一般无需传入
    fetcher = getDocumentJobStatus,
    scheduler = defaultSchedule,
  } = options

  let cancelled = false
  let cancelTimer = null
  let attempts = 0
  let consecutiveNetworkErrors = 0

  function stop() {
    cancelled = true
    if (cancelTimer) {
      cancelTimer()
      cancelTimer = null
    }
  }

  function fail(err) {
    if (cancelled) return
    onError?.(err)
  }

  async function tick() {
    if (cancelled) return
    attempts += 1
    if (attempts > maxAttempts) {
      fail(new Error('文档处理轮询超时，请刷新页面后重试'))
      return
    }

    let job
    try {
      job = await fetcher(jobId)
    } catch (err) {
      if (cancelled) return
      consecutiveNetworkErrors += 1
      if (consecutiveNetworkErrors >= MAX_NETWORK_ERRORS) {
        fail(err instanceof Error ? err : new Error(String(err)))
        return
      }
      cancelTimer = scheduler(tick, backoffDelay(consecutiveNetworkErrors))
      return
    }

    if (cancelled) return
    consecutiveNetworkErrors = 0
    onUpdate?.(job)

    if (job.status === 'succeeded') {
      onComplete?.(job)
      return
    }
    if (TERMINAL_FAILURE_STATUSES.includes(job.status)) {
      fail(job.error ? new Error(job.error) : new Error('文档处理失败'))
      return
    }

    cancelTimer = scheduler(tick, intervalMs)
  }

  // 立即发起首次查询
  tick()

  return { cancel: stop }
}
