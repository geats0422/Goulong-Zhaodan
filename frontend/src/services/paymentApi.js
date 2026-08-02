import { useAuth } from '../composables/useAuth.js'

const { fetchWithAuth } = useAuth()

async function parseErr(resp) {
  try {
    return await resp.json()
  } catch {
    return { detail: `请求失败（HTTP ${resp.status}）` }
  }
}

export async function createNativeOrder(productCode) {
  const resp = await fetchWithAuth('/payment/native', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_code: productCode }),
  })
  if (!resp.ok) throw new Error((await parseErr(resp)).detail || '创建订单失败')
  return resp.json()
}

export async function createAlipayPageOrder(productCode) {
  const resp = await fetchWithAuth('/payment/alipay/page', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_code: productCode }),
  })
  if (!resp.ok) throw new Error((await parseErr(resp)).detail || '创建订单失败')
  return resp.json()
}

export async function getOrderStatus(orderId) {
  const resp = await fetchWithAuth(`/payment/orders/${orderId}`)
  if (!resp.ok) throw new Error('查询订单失败')
  return resp.json()
}

export async function listOrders() {
  const resp = await fetchWithAuth('/payment/orders')
  if (!resp.ok) {
    const detail = (await parseErr(resp)).detail
    throw new Error(typeof detail === 'string' && detail.trim() ? detail : '历史订单加载失败')
  }
  return resp.json()
}

export async function createSubscription(planCode) {
  const resp = await fetchWithAuth('/subscription', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_code: planCode }),
  })
  if (!resp.ok) throw new Error((await parseErr(resp)).detail || '创建订阅失败')
  return resp.json()
}

export async function getCurrentSubscription() {
  const resp = await fetchWithAuth('/subscription/current')
  if (!resp.ok) return null
  return resp.json()
}

export async function cancelSubscription(contractId) {
  const resp = await fetchWithAuth(`/subscription/${contractId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error('取消订阅失败')
}

export async function listDeductions() {
  const resp = await fetchWithAuth('/subscription/deductions')
  if (!resp.ok) return []
  return resp.json()
}
