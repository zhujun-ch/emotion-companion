<template>
  <view class="account-page">
    <view v-if="account" class="account-card">
      <text class="account-title">{{ account.user.username }} · 账号管理</text>
      <text class="account-note">可撤销任一端登录；修改密码后，所有端均需重新登录。</text>
      <text v-if="error" class="account-error">{{ error }}</text>
      <button :disabled="busy" @click="loadCredentials">刷新登录列表</button>
      <view v-for="credential in credentials" :key="credential.id">
        <text>{{ credential.device_label }}{{ credential.current ? '（当前端）' : '' }}</text>
        <text class="account-note">有效期至 {{ formatExpiry(credential.expires_at) }}</text>
        <button :disabled="busy" @click="revoke(credential)">撤销此端登录</button>
      </view>
      <text>当前密码</text><input v-model="currentPassword" password maxlength="128" />
      <text>新密码</text><input v-model="newPassword" password maxlength="128" placeholder="8 至 128 个字符" />
      <text>确认新密码</text><input v-model="confirmNewPassword" password maxlength="128" placeholder="再次输入新密码" @confirm="updatePassword" />
      <button :disabled="busy" @click="updatePassword">修改密码并退出所有端</button>
      <button :disabled="busy" @click="revokeAll">退出所有端</button>
    </view>
    <view v-else class="account-card">
      <text class="account-title">{{ registering ? '注册心屿账号' : '登录心屿' }}</text>
      <text class="account-note">使用同一账号，可跨端继续倾诉、查看日记和本人匿名投稿。</text>
      <text>账号</text>
      <input v-model="username" placeholder="字母、数字、下划线或连字符" maxlength="32" />
      <text>密码</text>
      <input v-model="password" password placeholder="至少 8 个字符" maxlength="128" @confirm="registering ? undefined : submit()" />
      <template v-if="registering">
        <text>确认密码</text>
        <input v-model="confirmPassword" password placeholder="请再次输入密码" maxlength="128" @confirm="submit" />
      </template>
      <text v-if="error" class="account-error">{{ error }}</text>
      <button class="account-submit" :disabled="busy" :loading="busy" @click="submit">{{ registering ? '注册并登录' : '登录' }}</button>
      <button class="account-switch" :disabled="busy" @click="toggleRegisterMode">
        {{ registering ? '已有账号，去登录' : '没有账号，去注册' }}
      </button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { account, signIn, requestAccount, clearAccount } from '../../composables/account'

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const registering = ref(false)
const busy = ref(false)
const error = ref('')
const credentials = ref([])
const currentPassword = ref('')
const newPassword = ref('')
const confirmNewPassword = ref('')
function pad2(n) { return String(n).padStart(2, '0') }
function formatExpiry(timestamp) {
  const d = new Date(timestamp * 1000)
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}
function confirmAction(title, content) {
  return new Promise(resolve => {
    uni.showModal({
      title,
      content,
      success: result => resolve(Boolean(result.confirm)),
      fail: () => resolve(false),
    })
  })
}
function toggleRegisterMode() {
  registering.value = !registering.value
  confirmPassword.value = ''
  error.value = ''
}
async function run(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try { await action() } catch (failure) { error.value = failure.message }
  finally { busy.value = false }
}
async function loadCredentials() {
  if (!account.value) return
  return run(async () => { credentials.value = (await requestAccount('credentials', undefined, 'GET')).credentials })
}
onShow(loadCredentials)
async function revoke(credential) {
  if (busy.value) return
  const ok = await confirmAction(
    credential.current ? '撤销当前端登录' : '撤销此端登录',
    credential.current ? '撤销当前端将退出本设备登录，确定继续？' : '撤销后该设备需重新登录，确定继续？',
  )
  if (!ok) return
  return run(async () => {
    await requestAccount('credentials/' + credential.id, undefined, 'DELETE')
    if (credential.current) { clearAccount(); credentials.value = [] }
    else credentials.value = credentials.value.filter(item => item.id !== credential.id)
  })
}
async function revokeAll() {
  if (busy.value) return
  if (!(await confirmAction('退出所有端', '将退出所有设备的登录状态，确定继续？'))) return
  return run(async () => {
    await requestAccount('logout-all', {})
    clearAccount()
    credentials.value = []
  })
}
async function updatePassword() {
  if (busy.value) return
  error.value = ''
  if (!currentPassword.value) {
    error.value = '请输入当前密码'
    return
  }
  if (newPassword.value.length < 8 || newPassword.value.length > 128) {
    error.value = '新密码须为 8 至 128 个字符'
    return
  }
  if (newPassword.value !== confirmNewPassword.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  if (!(await confirmAction('修改密码', '修改密码后所有端均需重新登录，确定继续？'))) return
  return run(async () => {
    await requestAccount('password', { current_password: currentPassword.value, new_password: newPassword.value })
    currentPassword.value = newPassword.value = confirmNewPassword.value = ''
    clearAccount()
    credentials.value = []
    uni.showToast({ title: '密码已更新，请重新登录', icon: 'none' })
  })
}

async function submit() {
  if (busy.value) return
  error.value = ''
  const trimmedUsername = username.value.trim()
  if (!/^[a-zA-Z0-9_-]{3,32}$/.test(trimmedUsername)) {
    error.value = '账号须为 3 至 32 位字母、数字、下划线或连字符'
    return
  }
  if (password.value.length < 8 || password.value.length > 128) {
    error.value = '密码须为 8 至 128 个字符'
    return
  }
  if (registering.value && password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  busy.value = true
  try {
    await signIn(registering.value ? 'register' : 'login', trimmedUsername, password.value)
    password.value = ''
    confirmPassword.value = ''
    if (getCurrentPages().length > 1) uni.navigateBack()
    else uni.reLaunch({ url: '/pages/index/index' })
  } catch (failure) {
    error.value = failure.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.account-page { min-height: 100vh; padding: 40rpx; background: #f7f8f3; color: #28372a; }
.account-card { display: flex; flex-direction: column; gap: 16px; max-width: 400px; margin: 48px auto; padding: 24px; background: white; border: 1px solid #e3e9dd; border-radius: 16px; }
.account-title { font-size: 25px; font-weight: 600; }
.account-note { color: #4f6351; line-height: 1.5; }
input { min-height: 42px; border: 1px solid #cbd5c8; border-radius: 8px; padding: 0 12px; }
button { width: 100%; font-size: 16px; }
.account-submit { background: #365940; color: white; }
.account-switch { background: #eef2e9; color: #314d37; }
.account-error { color: #a5372c; }
</style>
