import { test } from 'node:test'
import assert from 'node:assert/strict'

const {
  describeInspectionJobStage,
  describeInspectionJobError,
  isConvertToPdfRequired,
  STAGE_MESSAGES,
  CONVERT_TO_PDF_CODE,
} = await import('../inspectionJobStages.js')

// ---------------------------------------------------------------------------
// describeInspectionJobStage: 默认（无 job）
// ---------------------------------------------------------------------------
test('describeInspectionJobStage: 无 job 时返回上传中默认信息', () => {
  const result = describeInspectionJobStage(null)
  assert.match(result.message, /上传/)
  assert.equal(result.progress, 0)
  assert.equal(result.parserEngine, null)
  assert.equal(result.isMineru, false)
})

// ---------------------------------------------------------------------------
// 各 stage 的中文消息映射
// ---------------------------------------------------------------------------
test('STAGE_MESSAGES: 覆盖体检弹窗需要的所有阶段', () => {
  assert.equal(STAGE_MESSAGES.detecting, '正在识别文档类型')
  assert.equal(STAGE_MESSAGES.parsing_local, '正在解析文档')
  assert.equal(STAGE_MESSAGES.parsing_mineru, '正在进行高质量文档解析')
  assert.equal(STAGE_MESSAGES.indexing, '正在构建文档索引')
  assert.equal(STAGE_MESSAGES.inspecting, '正在审查文档')
  assert.equal(STAGE_MESSAGES.succeeded, '文档处理完成')
})

test('describeInspectionJobStage: 按 stage 映射消息', () => {
  assert.equal(
    describeInspectionJobStage({ stage: 'detecting', progress: 10 }).message,
    '正在识别文档类型',
  )
  assert.equal(
    describeInspectionJobStage({ stage: 'indexing', progress: 70 }).message,
    '正在构建文档索引',
  )
})

// ---------------------------------------------------------------------------
// job.message 优先于 stage 默认消息
// ---------------------------------------------------------------------------
test('describeInspectionJobStage: job.message 优先于 stage 默认消息', () => {
  const result = describeInspectionJobStage({
    stage: 'parsing_mineru',
    progress: 50,
    message: 'MinerU 解析中（页 12/30）',
  })
  assert.equal(result.message, 'MinerU 解析中（页 12/30）')
})

test('describeInspectionJobStage: 未知 stage 回退到通用提示', () => {
  const result = describeInspectionJobStage({ stage: 'weird_stage', progress: 5 })
  assert.match(result.message, /文档任务处理中/)
})

// ---------------------------------------------------------------------------
// progress 边界保护
// ---------------------------------------------------------------------------
test('describeInspectionJobStage: progress 限制在 0-100', () => {
  assert.equal(describeInspectionJobStage({ stage: 'indexing', progress: 150 }).progress, 100)
  assert.equal(describeInspectionJobStage({ stage: 'indexing', progress: -5 }).progress, 0)
})

test('describeInspectionJobStage: 非数字 progress 视为 0', () => {
  assert.equal(describeInspectionJobStage({ stage: 'indexing', progress: 'abc' }).progress, 0)
  assert.equal(describeInspectionJobStage({ stage: 'indexing' }).progress, 0)
})

// ---------------------------------------------------------------------------
// MinerU 标识
// ---------------------------------------------------------------------------
test('describeInspectionJobStage: parser_engine=mineru 标识为 MinerU', () => {
  const result = describeInspectionJobStage({
    stage: 'indexing',
    progress: 80,
    parser_engine: 'mineru',
  })
  assert.equal(result.isMineru, true)
  assert.equal(result.parserEngine, 'mineru')
})

test('describeInspectionJobStage: stage=parsing_mineru 即使未填 engine 也标识为 MinerU', () => {
  const result = describeInspectionJobStage({
    stage: 'parsing_mineru',
    progress: 40,
    parser_engine: null,
  })
  assert.equal(result.isMineru, true)
})

test('describeInspectionJobStage: 本地解析引擎不标识为 MinerU', () => {
  const result = describeInspectionJobStage({
    stage: 'indexing',
    progress: 80,
    parser_engine: 'markitdown',
  })
  assert.equal(result.isMineru, false)
  assert.equal(result.parserEngine, 'markitdown')
})

// ---------------------------------------------------------------------------
// isConvertToPdfRequired
// ---------------------------------------------------------------------------
test('CONVERT_TO_PDF_CODE 常量', () => {
  assert.equal(CONVERT_TO_PDF_CODE, 'convert_to_pdf_required')
})

test('isConvertToPdfRequired: code 匹配返回 true', () => {
  assert.equal(
    isConvertToPdfRequired({ error: { code: 'convert_to_pdf_required', message: 'x' } }),
    true,
  )
})

test('isConvertToPdfRequired: 其它错误码返回 false', () => {
  assert.equal(
    isConvertToPdfRequired({ error: { code: 'mineru_failed', message: 'x' } }),
    false,
  )
})

test('isConvertToPdfRequired: 无 error 返回 false', () => {
  assert.equal(isConvertToPdfRequired(null), false)
  assert.equal(isConvertToPdfRequired({}), false)
  assert.equal(isConvertToPdfRequired({ error: null }), false)
})

// ---------------------------------------------------------------------------
// describeInspectionJobError
// ---------------------------------------------------------------------------
test('describeInspectionJobError: 优先返回 error.message', () => {
  assert.equal(
    describeInspectionJobError({ error: { code: 'mineru_failed', message: 'MinerU 文档解析失败，请稍后重试' } }),
    'MinerU 文档解析失败，请稍后重试',
  )
})

test('describeInspectionJobError: convert_to_pdf_required 使用其专属消息', () => {
  assert.equal(
    describeInspectionJobError({ error: { code: 'convert_to_pdf_required', message: 'PPTX 需先转 PDF' } }),
    'PPTX 需先转 PDF',
  )
  // message 缺失时回退到通用转 PDF 提示
  assert.equal(
    describeInspectionJobError({ error: { code: 'convert_to_pdf_required' } }),
    '请将文档转为 PDF 后重新上传',
  )
})

test('describeInspectionJobError: 无 error 返回 fallback', () => {
  assert.equal(describeInspectionJobError(null), '文档处理失败，请重试')
  assert.equal(describeInspectionJobError(null, '网络错误'), '网络错误')
  assert.equal(describeInspectionJobError({}), '文档处理失败，请重试')
})

test('describeInspectionJobError: error.message 缺失时回退到 fallback', () => {
  assert.equal(
    describeInspectionJobError({ error: { code: 'processing_failed' } }),
    '文档处理失败，请重试',
  )
})
