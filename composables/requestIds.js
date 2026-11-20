// Keep the ID of an uncertain write so a retry (including after a reload)
// can recover the server's receipt rather than create another record.
export function pendingWrite(owner, path, data = {}) {
  const key = 'xinyu-pending-write:' + owner + ':' + path
  const { request_id: suppliedId, ...payload } = data
  const signature = JSON.stringify(payload)
  const previous = uni.getStorageSync(key)
  const requestId = suppliedId || (previous?.signature === signature ? previous.requestId
    : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2))
  uni.setStorageSync(key, { signature, requestId })
  return {
    data: { ...payload, request_id: requestId },
    complete() {
      if (uni.getStorageSync(key)?.requestId === requestId) uni.removeStorageSync(key)
    },
  }
}
