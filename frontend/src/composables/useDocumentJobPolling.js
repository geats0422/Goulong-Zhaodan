import { ref, onUnmounted } from 'vue'
import { pollDocumentJob } from '../services/documentJobApi.js'

/**
 * 封装 pollDocumentJob 为 Vue composable。
 *
 * - 自动管理 cancel：组件卸载（onUnmounted）时自动清理，避免页面卸载后继续请求。
 * - startPolling 返回底层控制对象，便于手动 cancel。
 * - currentJob 在每次 onUpdate/onComplete 时自动更新，可直接在模板中渲染进度。
 *
 * @example
 * const { startPolling, cancelPolling, currentJob } = useDocumentJobPolling()
 * startPolling(jobId, {
 *   onComplete: (job) => refreshList(),
 *   onError: (err) => showError(err.message),
 * })
 *
 * @returns {{ startPolling, cancelPolling, currentJob }}
 */
export function useDocumentJobPolling() {
  const currentJob = ref(null)
  let poller = null

  function startPolling(jobId, options = {}) {
    // 启动新轮询前，先停止可能存在的旧轮询，避免重复定时器。
    cancelPolling()

    // 解构出 composable 需要包装的回调，其余选项（intervalMs、maxAttempts，
    // 以及测试用的 fetcher/scheduler）原样透传给 pollDocumentJob。
    const { onUpdate, onComplete, onError, ...rest } = options

    poller = pollDocumentJob(jobId, {
      ...rest,
      onUpdate: (job) => {
        currentJob.value = job
        onUpdate?.(job)
      },
      onComplete: (job) => {
        currentJob.value = job
        poller = null
        onComplete?.(job)
      },
      onError: (err) => {
        poller = null
        onError?.(err)
      },
    })

    return poller
  }

  function cancelPolling() {
    if (poller) {
      poller.cancel()
      poller = null
    }
  }

  // 组件卸载时自动清理，保证不会产生页面卸载后的请求。
  onUnmounted(() => {
    cancelPolling()
  })

  return { startPolling, cancelPolling, currentJob }
}
