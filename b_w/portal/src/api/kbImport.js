// 模块二：Boss智库 导入服务（走 /kbapi 代理 -> 8000）
import {
  MOCK,
  mockLoadHistory,
  mockSaveHistory,
  mockUploadTaskIds,
  mockTaskStatus,
} from './mock'
const HISTORY_KEY = 'kb_import_history'

/**
 * 上传多文件，POST /kbapi/upload，FormData 字段名 files
 * 返回 task_ids 数组
 */
export async function uploadFiles(files) {
  // 演示模式：内存假任务，与文件一一对应
  if (MOCK) return mockUploadTaskIds(Array.from(files || []))
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const res = await fetch('/kbapi/upload', { method: 'POST', body: fd })
  if (!res.ok) throw new Error(`上传失败（HTTP ${res.status}）`)
  const data = await res.json()
  if (!Array.isArray(data.task_ids) || !data.task_ids.length) {
    throw new Error(data.message || '上传失败：服务端未返回任务')
  }
  return data.task_ids
}

/** 查询任务状态 GET /kbapi/status/{task_id} */
export async function fetchTaskStatus(taskId) {
  // 演示模式：内存进度机，每调一次推进一步
  if (MOCK) return mockTaskStatus(taskId)
  const res = await fetch(`/kbapi/status/${taskId}`)
  if (!res.ok) throw new Error(`查询失败（HTTP ${res.status}）`)
  return await res.json()
}

/* ===== 导入历史（后端无持久化，前端 localStorage） ===== */

export function loadImportHistory() {
  // 演示模式：纯内存种子数据，不读写 localStorage
  if (MOCK) return mockLoadHistory().map((x) => ({ ...x }))
  try {
    const arr = JSON.parse(localStorage.getItem(HISTORY_KEY))
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

export function saveImportHistory(list) {
  // 演示模式：存内存
  if (MOCK) return mockSaveHistory(list)
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, 50)))
  } catch {
    /* 存储满等异常忽略 */
  }
}

export function addImportRecord(rec) {
  const list = loadImportHistory()
  list.unshift(rec)
  saveImportHistory(list)
  return list
}

export function updateImportRecord(taskId, patch) {
  const list = loadImportHistory()
  const i = list.findIndex((x) => x.task_id === taskId)
  if (i >= 0) {
    list[i] = { ...list[i], ...patch }
    saveImportHistory(list)
  }
  return list
}
