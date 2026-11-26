import { ref } from 'vue'

const API = import.meta.env?.VITE_API_BASE || 'http://127.0.0.1:5000'
const KEY = 'xinyu-account'
export const account = ref(uni.getStorageSync(KEY) || null)

export function accountHeaders() {
  if (account.value?.expires_at && account.value.expires_at * 1000 <= Date.now()) clearAccount()
  return account.value ? { Authorization: 'Bearer ' + account.value.token } : {}
}

export function openLogin() {
  uni.navigateTo({ url: '/pages/login/index' })
}

export function clearAccount() {
  const owner = account.value?.user.id
  if (owner) {
    for (const key of uni.getStorageInfoSync().keys) {
      if (key.startsWith('xinyu-pending-write:' + owner + ':')) uni.removeStorageSync(key)
    }
  }
  uni.removeStorageSync(KEY)
  account.value = null
}

export function requestAccount(action, data, method = 'POST') {
  const header = accountHeaders()
  const token = account.value?.token
  return new Promise((resolve, reject) => {
    uni.request({
      url: API + '/api/auth/' + action, method, header, data,
      timeout: 10000,
      success: response => {
        if (!['register', 'login'].includes(action) && token !== account.value?.token) return reject(new Error('登录状态已变更'))
        if (response.statusCode === 401 && !['register', 'login', 'password'].includes(action)) clearAccount()
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(response.data)
        else reject(new Error(response.data?.msg || '账号操作失败'))
      },
      fail: () => reject(new Error('无法连接心屿服务，请稍后重试')),
    })
  })
}

export async function signIn(action, username, password) {
  let deviceLabel = '网页客户端'
  // #ifdef MP-WEIXIN
  deviceLabel = '微信小程序'
  // #endif
  const result = await requestAccount(action, { username, password, device_label: deviceLabel })
  account.value = { user: result.user, token: result.token, expires_at: result.expires_at }
  uni.setStorageSync(KEY, account.value)
}

export async function signOut() {
  try {
    if (account.value) await requestAccount('logout')
  } catch (_) {
  } finally {
    clearAccount()
    uni.reLaunch({ url: '/pages/index/index' })
  }
}
