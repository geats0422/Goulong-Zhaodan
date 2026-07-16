/**
 * 体检弹窗中"文档处理任务"阶段的可展示信息映射。
 *
 * 这些纯函数把 useDocumentJobPolling 返回的 job 对象转换为可直接渲染的
 * 中文消息、进度值与解析引擎标识，便于在 InspectionReviewModal 中展示
 * "正在识别文档类型 / 正在解析 / 正在构建索引 / 正在审查"等阶段，
 * 同时识别 `convert_to_pdf_required` 等特殊失败码。
 *
 * 设计为纯函数：无副作用、不依赖 Vue，可直接用 node:test 覆盖。
 */

/** 体检任务各 stage 对应的中文展示消息。 */
export const STAGE_MESSAGES = {
  queued: '任务已排队，等待处理',
  detecting: '正在识别文档类型',
  parsing_local: '正在解析文档',
  parsing_mineru: '正在进行高质量文档解析',
  indexing: '正在构建文档索引',
  inspecting: '正在审查文档',
  succeeded: '文档处理完成',
  failed: '任务处理失败',
  cancelled: '任务已取消',
}

/** 表示"需要先转 PDF 才能继续解析"的错误码。 */
export const CONVERT_TO_PDF_CODE = 'convert_to_pdf_required'

const CONVERT_TO_PDF_FALLBACK = '请将文档转为 PDF 后重新上传'
const DEFAULT_UPLOAD_MESSAGE = '正在上传文件...'
const DEFAULT_STAGE_MESSAGE = '文档任务处理中'
const DEFAULT_ERROR_FALLBACK = '文档处理失败，请重试'

function clampProgress(value) {
  if (!Number.isFinite(value)) return 0
  if (value < 0) return 0
  if (value > 100) return 100
  return value
}

/**
 * 描述体检文档任务当前阶段的可展示信息。
 *
 * @param {object|null} job documentJobApi 返回的 job 对象
 * @returns {{message: string, progress: number, parserEngine: string|null, isMineru: boolean}}
 *   - message: 展示给用户的中文消息（job.message 优先，否则按 stage 回退）
 *   - progress: 限制在 [0,100] 的整数进度
 *   - parserEngine: 解析引擎标识（如 'mineru' / 'markitdown'），未填时为 null
 *   - isMineru: 是否使用 MinerU 高质量解析（用于展示 MinerU 标识）
 */
export function describeInspectionJobStage(job) {
  if (!job) {
    return {
      message: DEFAULT_UPLOAD_MESSAGE,
      progress: 0,
      parserEngine: null,
      isMineru: false,
    }
  }
  const message = job.message || STAGE_MESSAGES[job.stage] || DEFAULT_STAGE_MESSAGE
  const parserEngine = job.parser_engine || null
  const isMineru = parserEngine === 'mineru' || job.stage === 'parsing_mineru'
  return {
    message,
    progress: clampProgress(job.progress),
    parserEngine,
    isMineru,
  }
}

/**
 * 判断任务失败是否因"需要先转换为 PDF"（例如 PPTX/XLSX）。
 *
 * @param {object|null} job
 * @returns {boolean}
 */
export function isConvertToPdfRequired(job) {
  return job?.error?.code === CONVERT_TO_PDF_CODE
}

/**
 * 获取任务失败时展示给用户的可读错误消息。
 *
 * @param {object|null} job
 * @param {string} [fallback] 无 error 时的回退消息
 * @returns {string}
 */
export function describeInspectionJobError(job, fallback = DEFAULT_ERROR_FALLBACK) {
  if (!job?.error) return fallback
  if (isConvertToPdfRequired(job)) {
    return job.error.message || CONVERT_TO_PDF_FALLBACK
  }
  return job.error.message || fallback
}
