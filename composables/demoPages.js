import { account, accountHeaders, clearAccount } from './account'
import { pendingWrite } from './requestIds'

const API = import.meta.env?.VITE_API_BASE || 'http://127.0.0.1:5000'

function headerValue(headers, name) {
  if (!headers) return undefined
  const target = name.toLowerCase()
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === target) return value
  }
  return undefined
}

export function demoRequest(path, method = 'GET', data, { header, timeout = 10000, withMeta = false } = {}) {
  const privateDiary = !path.startsWith('/review')
  const authHeader = privateDiary ? accountHeaders() : {}
  const token = account.value?.token
  const create = method === 'POST' && (path === '/diaries' || path === '/posts' || /^\/posts\/\d+\/comments$/.test(path))
  const pending = create && account.value?.user?.id ? pendingWrite(account.value.user.id, path, data) : null
  return new Promise((resolve, reject) => {
    uni.request({
      url: API + '/api/demo' + path,
      method,
      data: pending?.data || data,
      header: privateDiary ? { ...authHeader, ...header } : header,
      timeout,
      success(response) {
        if (privateDiary && token !== account.value?.token) return reject(new Error('登录状态已变更'))
        if (privateDiary && response.statusCode === 401) clearAccount()
        if (response.statusCode >= 200 && response.statusCode < 300) {
          pending?.complete()
          if (!withMeta) {
            resolve(response.data)
            return
          }
          const rawNextOffset = headerValue(response.header, 'x-next-offset')
          const rawNextBefore = headerValue(response.header, 'x-next-before-id')
          resolve({
            data: response.data,
            hasMore: headerValue(response.header, 'x-has-more') === '1',
            nextOffset: rawNextOffset !== undefined ? Number(rawNextOffset) : null,
            nextBeforeId: rawNextBefore !== undefined ? Number(rawNextBefore) : null,
          })
        } else {
          const failure = new Error(response.data?.message || response.data?.msg || '演示接口不可用，请检查后端配置')
          failure.statusCode = response.statusCode
          reject(failure)
        }
      },
      fail() { reject(new Error('无法连接演示后端，请检查网络后重试')) },
    })
  })
}

export function beijingDay(offset = 0) {
  return new Date(Date.now() + 8 * 3600000 + offset * 86400000).toISOString().slice(0, 10)
}
