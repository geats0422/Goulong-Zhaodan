import { useAuth } from '../composables/useAuth.js'

const { fetchWithAuth } = useAuth()

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
    if (response.status === 404 && data.detail === '解析会话不存在') {
      throw new Error('解析会话已失效，请关闭弹窗后重新上传文件')
    }
    const detail = typeof data.detail === 'object' && data.detail !== null
      ? data.detail.message || JSON.stringify(data.detail)
      : data.detail
    throw new Error(detail || `请求失败（HTTP ${response.status}）`)
  }
  return data
}

export async function parseInspectionFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  return parseResponse(await fetchWithAuth('/inspection/parse', {
    method: 'POST',
    body: formData,
  }))
}

export async function inspectParsedSession(sessionId, payload = {}) {
  return parseResponse(await fetchWithAuth(`/inspection/sessions/${sessionId}/inspect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function inspectInspectionRecord(recordId, payload = {}) {
  return parseResponse(await fetchWithAuth(`/inspection/records/${recordId}/inspect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function fetchInspectionRecords(params = {}) {
  const query = new URLSearchParams(params).toString()
  const url = query ? `/inspection/records?${query}` : '/inspection/records'
  return parseResponse(await fetchWithAuth(url))
}

export async function fetchInspectionRecord(recordId) {
  return parseResponse(await fetchWithAuth(`/inspection/records/${recordId}`))
}

export async function deleteInspectionRecord(recordId) {
  return parseResponse(await fetchWithAuth(`/inspection/records/${recordId}`, { method: 'DELETE' }))
}

export async function burnInspectionRecord(recordId) {
  return parseResponse(await fetchWithAuth(`/inspection/records/${recordId}/burn`, {
    method: 'POST',
  }))
}

function stripExtension(filename) {
  return filename.replace(/\.[^.]+$/, '')
}

export async function downloadInspectionReportPdf(recordId, documentName = '审查报告') {
  const response = await fetchWithAuth(`/inspection/records/${recordId}/report.pdf`)
  if (!response.ok) {
    let detail = `请求失败（HTTP ${response.status}）`
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      // ignore non-JSON errors
    }
    throw new Error(detail)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${stripExtension(documentName)}审查报告.pdf`
  a.click()
  URL.revokeObjectURL(url)
}
