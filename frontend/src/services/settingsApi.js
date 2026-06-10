import { useAuth } from '../composables/useAuth.js'

const { fetchWithAuth } = useAuth()

async function parseResponse(response) {
  if (response.status === 204) return null
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || '请求失败')
  }
  return data
}

export async function getSettingsOverview() {
  return parseResponse(await fetchWithAuth('/settings/overview'))
}

export async function updateProfile(payload) {
  return parseResponse(await fetchWithAuth('/settings/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function updatePassword(payload) {
  return parseResponse(await fetchWithAuth('/settings/password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function updateKnowledgeDocument(documentId, enabled) {
  return parseResponse(await fetchWithAuth(`/settings/knowledge/documents/${documentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  }))
}

export async function createTabooWord(payload) {
  return parseResponse(await fetchWithAuth('/settings/taboo-words', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function updateTabooWord(wordId, payload) {
  return parseResponse(await fetchWithAuth(`/settings/taboo-words/${wordId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function deleteTabooWord(wordId) {
  return parseResponse(await fetchWithAuth(`/settings/taboo-words/${wordId}`, {
    method: 'DELETE',
  }))
}
