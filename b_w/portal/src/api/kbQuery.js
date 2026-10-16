// 模块二：Boss智库 查询服务（走 /kbq 代理 -> 8001）
import { MOCK, MOCK_KB_HISTORY, mockOpenStream } from './mock'
const BASE = '/kbq'
export const SESSION_KEY = 'kb_session_id'

export function genUuid() {
  if (crypto && crypto.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/** 取会话 id，不存在则生成并持久化 */
export function getSessionId() {
  let id = localStorage.getItem(SESSION_KEY)
  if (!id) {
    id = genUuid()
    localStorage.setItem(SESSION_KEY, id)
  }
  return id
}

/** 生成新会话 id 并持久化 */
export function newSessionId() {
  const id = genUuid()
  localStorage.setItem(SESSION_KEY, id)
  return id
}

/**
 * 提交查询（流式），响应 JSON 含 session_id
 * POST /kbq/query  { query, session_id, is_stream: true }
 */
export async function submitQuery(query, sessionId, isStream = true) {
  // 演示模式
  if (MOCK) return { session_id: sessionId }
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId, is_stream: isStream }),
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => '')
    throw new Error(msg || `请求失败（HTTP ${res.status}）`)
  }
  return await res.json()
}

/**
 * 打开 SSE 流（具名事件），返回 EventSource 实例（组件卸载时需 close）
 * 事件：ready / progress(done_list) / delta / final / final_answer / error / __close__
 */
export function openStream(sessionId, handlers = {}) {
  // 演示模式：假 EventSource（只需实现 close）
  if (MOCK) return mockOpenStream(handlers)
  const es = new EventSource(`${BASE}/stream/${sessionId}`)
  const parse = (e) => {
    try {
      return e && e.data ? JSON.parse(e.data) : {}
    } catch {
      return null
    }
  }

  es.addEventListener('ready', (e) => handlers.onReady?.(parse(e)))

  es.addEventListener('progress', (e) => handlers.onProgress?.(parse(e) || {}))

  es.addEventListener('delta', (e) => {
    const d = parse(e)
    handlers.onDelta?.((d && d.delta) || '')
  })

  const onFinal = (e) => {
    const d = parse(e) || {}
    handlers.onFinal?.(d)
    es.close()
    handlers.onClose?.()
  }
  es.addEventListener('final', onFinal)
  // 兜底事件，同 final 处理
  es.addEventListener('final_answer', onFinal)

  es.addEventListener('error', (e) => {
    if (e && typeof e.data === 'string') {
      // 后端具名 error 事件
      const d = parse(e)
      handlers.onError?.((d && d.error) || 'SSE 连接中断/失败')
      es.close()
      handlers.onClose?.()
    } else {
      // 原生连接错误：直接收尾，避免 EventSource 无限重连
      es.close()
      handlers.onNativeError?.()
      handlers.onClose?.()
    }
  })

  es.addEventListener('__close__', () => {
    es.close()
    handlers.onClose?.()
  })

  return es
}

/**
 * 加载历史消息，GET /kbq/history/{session_id}?limit=50
 * 结构容错：数组 或 {items|records|messages|history|data: [...]}；
 * 条目兼容 role/content 或 query/answer 对；解析失败静默返回空
 */
export async function fetchHistory(sessionId, limit = 50) {
  // 演示模式
  if (MOCK) return MOCK_KB_HISTORY
  try {
    const res = await fetch(`${BASE}/history/${sessionId}?limit=${limit}`)
    if (!res.ok) return []
    const data = await res.json()
    let items = data
    if (!Array.isArray(items)) {
      items =
        data.items || data.records || data.messages || data.history || data.data || []
    }
    if (!Array.isArray(items)) return []
    const msgs = []
    for (const it of items) {
      if (!it || typeof it !== 'object') continue
      if (it.role) {
        const text = it.text != null ? it.text : it.content != null ? it.content : ''
        if (!String(text)) continue
        msgs.push({
          role: it.role === 'user' || it.role === 'human' ? 'user' : 'ai',
          text: String(text),
        })
      } else {
        const q = it.query != null ? it.query : it.question != null ? it.question : ''
        const a = it.answer != null ? it.answer : it.response != null ? it.response : ''
        if (q) msgs.push({ role: 'user', text: String(q) })
        if (a) msgs.push({ role: 'ai', text: String(a) })
      }
    }
    return msgs
  } catch {
    return []
  }
}

/** 清空历史 DELETE /kbq/history/{session_id}，失败不阻塞 */
export async function clearHistory(sessionId) {
  try {
    await fetch(`${BASE}/history/${sessionId}`, { method: 'DELETE' })
  } catch {
    /* 忽略 */
  }
}

/** 健康检查 GET /kbq/health */
export async function checkHealth() {
  // 演示模式
  if (MOCK) return true
  try {
    const res = await fetch(`${BASE}/health`)
    return res.ok
  } catch {
    return false
  }
}
