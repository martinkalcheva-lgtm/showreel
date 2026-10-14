// 模块一：问数（data-agent，走 /dsapi 代理 -> 8002）
// 契约：POST /dsapi/api/query，body { query }，响应 text/event-stream（POST，不能用 EventSource）
// 帧：data: {...}\n\n，事件 JSON 三种：{stage} / {result} / {error}
import { MOCK, mockDataStream } from './mock'

export async function queryDataStream(query, handlers = {}, signal) {
  // 演示模式：URL 带 ?mock=1 时返回模拟流
  if (MOCK) return mockDataStream(query, handlers, signal)
  const res = await fetch('/dsapi/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal,
  })
  if (!res.ok) throw new Error(`请求失败（HTTP ${res.status}）`)
  if (!res.body) throw new Error('当前浏览器不支持流式响应')

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    // 按 \n\n 分帧，缓冲处理跨 chunk 断帧
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      handleFrame(raw, handlers)
    }
  }
  // 流结束后的残余帧
  if (buffer.trim()) handleFrame(buffer, handlers)
}

function handleFrame(raw, handlers) {
  const dataLines = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (!dataLines.length) return
  const text = dataLines.join('\n')
  let payload
  try {
    payload = JSON.parse(text)
  } catch {
    payload = { result: text }
  }
  if (payload == null || typeof payload !== 'object') return
  if (payload.stage != null) {
    handlers.onStage?.(String(payload.stage))
  } else if (payload.error != null) {
    handlers.onError?.(String(payload.error))
  } else if (payload.result !== undefined) {
    handlers.onResult?.(payload.result)
  }
}
