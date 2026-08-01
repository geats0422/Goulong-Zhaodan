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

const { listArchivedKnowledge, deleteArchivedKnowledge } = await import('../settingsApi.js')

// ---------------------------------------------------------------------------
// 归档招投标资料 API 契约（任务 9 提供的后端接口）
// GET    /inspection/archived-knowledge
// DELETE /inspection/archived-knowledge/{id}
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// ---------------------------------------------------------------------------

// 构造 fake response：settingsApi.parseResponse 使用 response.json() 读取正文，
// status===204 时直接返回 null 不读取正文。
function jsonResponse(status, body, ok) {
  return {
    ok: ok ?? (status >= 200 && status < 300),
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
  }
}

test('listArchivedKnowledge: GET /inspection/archived-knowledge', async () => {
  const captured = { url: null, options: null }
  const original = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    captured.url = url
    captured.options = options || {}
    return jsonResponse(200, {
      documents: [
        {
          id: 10,
          title: '我的招投标资料',
          owner_type: 'user',
          application_scenario: 'bidding',
          is_active: false,
          created_at: '2026-07-01T00:00:00Z',
        },
      ],
    })
  }
  try {
    const data = await listArchivedKnowledge()
    assert.equal(captured.url, '/inspection/archived-knowledge')
    assert.equal(captured.options.method, undefined, 'GET 不应显式设置 method')
    assert.ok(Array.isArray(data.documents))
    assert.equal(data.documents.length, 1)
    assert.equal(data.documents[0].id, 10)
    assert.equal(data.documents[0].application_scenario, 'bidding')
    assert.equal(data.documents[0].is_active, false)
  } finally {
    globalThis.fetch = original
  }
})

test('listArchivedKnowledge: 后端返回空列表时正常解析', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => jsonResponse(200, { documents: [] })
  try {
    const data = await listArchivedKnowledge()
    assert.ok(Array.isArray(data.documents))
    assert.equal(data.documents.length, 0)
  } finally {
    globalThis.fetch = original
  }
})

test('listArchivedKnowledge: 401 鉴权失败抛出错误', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => jsonResponse(401, { detail: '未授权' }, false)
  try {
    await assert.rejects(
      () => listArchivedKnowledge(),
      (err) => {
        assert.ok(err instanceof Error)
        assert.match(err.message, /未授权/)
        return true
      },
    )
  } finally {
    globalThis.fetch = original
  }
})

test('deleteArchivedKnowledge: DELETE /inspection/archived-knowledge/{id}', async () => {
  const captured = { url: null, options: null }
  const original = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    captured.url = url
    captured.options = options || {}
    // 204 No Content：parseResponse 直接返回 null，不读取正文
    return { ok: true, status: 204, headers: new Headers(), json: async () => null }
  }
  try {
    const result = await deleteArchivedKnowledge(20)
    assert.equal(captured.url, '/inspection/archived-knowledge/20')
    assert.equal(captured.options.method, 'DELETE')
    assert.equal(result, null, '204 No Content 应返回 null')
  } finally {
    globalThis.fetch = original
  }
})

test('deleteArchivedKnowledge: 404 归档资料不存在/无权删除时抛错', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () =>
    jsonResponse(404, { detail: '归档资料不存在或无权删除' }, false)
  try {
    await assert.rejects(
      () => deleteArchivedKnowledge(999),
      (err) => {
        assert.ok(err instanceof Error)
        assert.match(err.message, /归档资料不存在或无权删除/)
        return true
      },
    )
  } finally {
    globalThis.fetch = original
  }
})

test('deleteArchivedKnowledge: 503 删除失败抛错（前端据此恢复列表）', async () => {
  // 后端 _type_error 返回 detail={code, message} 对象。
  // settingsApi.parseResponse 对非数组 detail 走既有路径，关键是抛出 Error
  // 让 SettingsPage 能捕获并恢复归档列表。
  const original = globalThis.fetch
  globalThis.fetch = async () =>
    jsonResponse(
      503,
      {
        detail: {
          code: 'archive_delete_failed',
          message: '归档资料删除失败，请稍后重试',
        },
      },
      false,
    )
  try {
    await assert.rejects(
      () => deleteArchivedKnowledge(21),
      (err) => {
        assert.ok(err instanceof Error, '503 必须抛出 Error 以触发列表恢复')
        return true
      },
    )
  } finally {
    globalThis.fetch = original
  }
})
