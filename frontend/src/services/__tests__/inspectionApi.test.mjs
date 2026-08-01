// 任务 16：inspectionApi.parseResponse 错误透传契约测试。
//
// 关键修复（任务 13 质量审查发现的问题）：
//   旧实现把对象型 detail 压扁成 detail.message 字符串，丢弃 code/action/label。
//   新实现保留 Error.message 兼容现有调用，同时把完整 detail 结构挂到 Error 属性上。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 16
import { test } from 'node:test'
import assert from 'node:assert/strict'

// useAuth.js 模块顶层访问 sessionStorage，在纯 Node 环境下需要 polyfill。
if (!globalThis.sessionStorage) {
  const store = new Map()
  globalThis.sessionStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(String(k), String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  }
}

const { parseInspectionFile, inspectInspectionRecord } = await import('../inspectionApi.js')

function jsonResponse(status, body, ok) {
  return {
    ok: ok ?? (status >= 200 && status < 300),
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    text: async () => JSON.stringify(body),
  }
}

// ---------------------------------------------------------------------------
// 402 insufficient_quota: 完整结构透传到 Error 属性（关键修复）
// ---------------------------------------------------------------------------
test('402 insufficient_quota: Error.message 保留可读文案（向后兼容）', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () =>
    jsonResponse(
      402,
      {
        detail: {
          code: 'insufficient_quota',
          message: '当前账户额度不足，本次审查需要更多算力额度。',
          action: {
            type: 'billing',
            path: '/settings?tab=billing',
            label: '前往账单与订阅',
          },
        },
      },
      false,
    )
  try {
    await assert.rejects(() => parseInspectionFile(new File(['x'], 'a.pdf')), (err) => {
      assert.ok(err instanceof Error)
      assert.match(err.message, /当前账户额度不足/)
      return true
    })
  } finally {
    globalThis.fetch = original
  }
})

test('402 insufficient_quota: Error.code === "insufficient_quota"（不再依赖文本匹配）', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () =>
    jsonResponse(
      402,
      {
        detail: {
          code: 'insufficient_quota',
          message: '当前账户额度不足，本次审查需要更多算力额度。',
          action: { type: 'billing', path: '/settings?tab=billing', label: '前往账单与订阅' },
        },
      },
      false,
    )
  try {
    await assert.rejects(() => parseInspectionFile(new File(['x'], 'a.pdf')), (err) => {
      assert.equal(err.code, 'insufficient_quota', 'Error 必须挂载稳定 code 属性')
      return true
    })
  } finally {
    globalThis.fetch = original
  }
})

test('402 insufficient_quota: Error.action 透传完整结构（path + label，不再丢弃）', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () =>
    jsonResponse(
      402,
      {
        detail: {
          code: 'insufficient_quota',
          message: '当前账户额度不足，本次审查需要更多算力额度。',
          action: { type: 'billing', path: '/settings?tab=billing', label: '前往账单与订阅' },
        },
      },
      false,
    )
  try {
    await assert.rejects(() => inspectInspectionRecord(42, {}), (err) => {
      assert.deepEqual(err.action, {
        type: 'billing',
        path: '/settings?tab=billing',
        label: '前往账单与订阅',
      })
      assert.equal(err.action.path, '/settings?tab=billing')
      assert.notEqual(err.action.path, '/pricing')
      return true
    })
  } finally {
    globalThis.fetch = original
  }
})

// ---------------------------------------------------------------------------
// 普通错误：行为保持向后兼容
// ---------------------------------------------------------------------------
test('普通 500 错误: 字符串 detail 仍作为 message 抛出', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => jsonResponse(500, { detail: '服务器内部错误' }, false)
  try {
    await assert.rejects(() => parseInspectionFile(new File(['x'], 'a.pdf')), (err) => {
      assert.equal(err.message, '服务器内部错误')
      assert.ok(!err.code, '非额度错误不应伪造 code')
      return true
    })
  } finally {
    globalThis.fetch = original
  }
})

test('解析会话不存在: 404 仍走专用文案分支（既有契约不破坏）', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () =>
    jsonResponse(404, { detail: '解析会话不存在' }, false)
  try {
    await assert.rejects(() => parseInspectionFile(new File(['x'], 'a.pdf')), (err) => {
      assert.match(err.message, /解析会话已失效/)
      return true
    })
  } finally {
    globalThis.fetch = original
  }
})

test('对象型 detail 无 code 字段: message 仍可读，不伪造 code', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () =>
    jsonResponse(
      503,
      { detail: { message: '归档资料删除失败，请稍后重试' } },
      false,
    )
  try {
    await assert.rejects(() => inspectInspectionRecord(42, {}), (err) => {
      assert.match(err.message, /归档资料删除失败/)
      assert.ok(!err.code, '无 code 字段时不应伪造 code')
      return true
    })
  } finally {
    globalThis.fetch = original
  }
})
