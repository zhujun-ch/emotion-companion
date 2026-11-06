const API = import.meta.env?.VITE_API_BASE || 'http://127.0.0.1:5000'

export function demoRequest(path, method = 'GET', data, { header, timeout = 10000 } = {}) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: API + '/api/demo' + path,
      method,
      data,
      header,
      timeout,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data)
        } else {
          const failure = new Error(response.data?.message || '演示接口不可用，请检查后端配置')
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
