import { ref } from 'vue'
import { demoRequest } from './demoPages'

const AUTHOR_KEY = 'xinyu-treehole-author'
export const hasLegacyPosts = ref(Boolean(uni.getStorageSync(AUTHOR_KEY)))

export async function claimLegacyPosts() {
  const legacyToken = uni.getStorageSync(AUTHOR_KEY)
  const result = await demoRequest('/posts/claim', 'POST', {}, { header: { 'X-Treehole-Token': legacyToken } })
  uni.removeStorageSync(AUTHOR_KEY)
  hasLegacyPosts.value = false
  return result
}

export async function treeholeRequest(path, method = 'GET', data) {
  return demoRequest(path, method, data, { timeout: 25000 })
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
