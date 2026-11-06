import { ref } from 'vue'
import { demoRequest } from './demoPages'

const AUTHOR_KEY = 'xinyu-treehole-author'
let authorToken = uni.getStorageSync(AUTHOR_KEY)
let authorRequest

async function getAuthorToken() {
  if (authorToken) return authorToken
  authorRequest ||= demoRequest('/posts/session', 'POST').then(({ token }) => {
    uni.setStorageSync(AUTHOR_KEY, token)
    authorToken = token
    return token
  }).finally(() => { authorRequest = undefined })
  return authorRequest
}

export async function treeholeRequest(path, method = 'GET', data) {
  const send = token => demoRequest(path, method, data, {
    header: { 'X-Treehole-Token': token },
    timeout: 25000,
  })
  const token = await getAuthorToken()
  try {
    return await send(token)
  } catch (failure) {
    if (failure.statusCode !== 401) throw failure
    if (authorToken === token) {
      authorToken = ''
      uni.removeStorageSync(AUTHOR_KEY)
    }
    return send(await getAuthorToken())
  }
}

export const reviewerToken = ref('')

export async function reviewRequest(path, method = 'GET', data) {
  const token = reviewerToken.value
  try {
    return await demoRequest('/review' + path, method, data, {
      header: token ? { Authorization: 'Bearer ' + token } : undefined,
    })
  } catch (failure) {
    if ([401, 403].includes(failure.statusCode) && reviewerToken.value === token) reviewerToken.value = ''
    throw failure
  }
}
