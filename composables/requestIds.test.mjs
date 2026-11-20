import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('uncertain writes retain their ID across retries and module reloads', async () => {
  const storage = new Map()
  globalThis.uni = {
    getStorageSync: key => storage.get(key),
    setStorageSync: (key, value) => storage.set(key, value),
    removeStorageSync: key => storage.delete(key),
  }
  const source = await readFile(new URL('./requestIds.js', import.meta.url), 'utf8')
  const { pendingWrite } = await import('data:text/javascript,' + encodeURIComponent(source))
  const payload = { session_id: 'session', text: '心情测试' }
  const original = pendingWrite('owner', '/api/chat', payload)
  const retry = pendingWrite('owner', '/api/chat', original.data)
  assert.equal(retry.data.request_id, original.data.request_id)
  const restored = await import('data:text/javascript,' + encodeURIComponent(source + '\n// reload'))
  const afterReload = restored.pendingWrite('owner', '/api/chat', payload)
  assert.equal(afterReload.data.request_id, original.data.request_id)
  assert.notEqual(pendingWrite('other', '/api/chat', payload).data.request_id, original.data.request_id)
  afterReload.complete()
  assert.notEqual(pendingWrite('owner', '/api/chat', payload).data.request_id, original.data.request_id)
  delete globalThis.uni
})
