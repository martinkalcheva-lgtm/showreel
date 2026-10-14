// 演示模式（mock）：URL 带 ?mock=1 时启用
// 只在 API 层生效，组件零感知；真实接口逻辑不受影响，正常打开（无参数）即走真后端
export const MOCK =
  typeof location !== 'undefined' &&
  new URLSearchParams(location.search).has('mock')

export function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal && signal.aborted) return reject(new DOMException('Aborted', 'AbortError'))
    const t = setTimeout(() => {
      signal && signal.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    function onAbort() {
      clearTimeout(t)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal && signal.addEventListener('abort', onAbort)
  })
}

/* ================= 问数：模拟 SSE ================= */

export const MOCK_STAGES = [
  '抽取关键字',
  '召回列数据',
  '召回指标数据',
  '召回字段取值',
  '合并召回信息',
  '过滤指标',
  '过滤表',
  '添加额外上下文',
  '生成SQL',
  '校验SQL',
  '执行SQL',
]

export async function mockDataStream(query, handlers = {}, signal) {
  for (const stage of MOCK_STAGES) {
    await sleep(220 + Math.random() * 260, signal)
    handlers.onStage?.(stage)
  }
  await sleep(400, signal)
  handlers.onResult?.(mockRows(query))
}

// 与真实 execute_sql 对齐：返回"行对象数组"，前端渲染成表格
function mockRows(query) {
  return [
    { region_name: '华东', total_quantity: '4382', total_amount: '1724.6' },
    { region_name: '华南', total_quantity: '3107', total_amount: '1289.3' },
    { region_name: '华北', total_quantity: '2651', total_amount: '1051.2' },
    { region_name: '西南', total_quantity: '1705', total_amount: '686.4' },
    { region_name: '东北', total_quantity: '999', total_amount: '402.0' },
  ]
}

/* ================= Boss智库：模拟查询流 ================= */

export const MOCK_KB_HISTORY = [
  {
    role: 'user',
    text: 'LA2608 的默认管理地址是多少？',
  },
  {
    role: 'ai',
    text:
      'H3C LA2608 室内无线网关出厂默认管理地址为 192.168.1.1/24。\n\n' +
      '· 管理账号：admin，首次登录需按引导修改密码\n' +
      '· 配置手册来源：《H3C LA2608室内无线网关 用户手册-6W100》第 2.1 节「登录设备」',
  },
  {
    role: 'user',
    text: ' hak180 产品安全手册里对存储温度有什么要求？',
  },
  {
    role: 'ai',
    text:
      '依据《hak180产品安全手册》第 4 章仓储要求：\n\n' +
      '· 常温存储：-20℃ ~ 60℃，相对湿度 ≤ 85%（无凝结）\n' +
      '· 长期存储（>6 个月）：建议 10℃ ~ 35℃，并每 3 个月通电除潮一次',
  },
]

const KB_STAGES = ['解析文档', '召回片段', '重排序', '生成答案']

/**
 * 模拟 kb 查询 SSE：返回假 EventSource（只需实现 close）
 * 进度推进 → delta 打字机 → final 收尾
 */
export function mockOpenStream(handlers = {}) {
  let closed = false
  const done = []
  const full =
    '根据知识库检索结果：\n\n' +
    '1. 本产品支持双频（2.4GHz / 5GHz）同时接入，单 AP 最大并发 128 终端；\n' +
    '2. 出厂工作在 FIT 模式，需通过无线控制器（AC）下发配置；\n' +
    '3. PoE 供电标准为 802.3at，整机功耗 ≤ 25W。\n\n' +
    '以上内容参考《H3C LA2608室内无线网关 用户手册-6W100》第 3 章「产品规格」。'

  let step = 0
  const progressTimer = setInterval(() => {
    if (closed) return clearInterval(progressTimer)
    if (step < KB_STAGES.length) {
      done.push(KB_STAGES[step++])
      handlers.onProgress?.({ done_list: [...done], running_list: [] })
    }
  }, 550)

  const startDelta = setTimeout(() => {
    if (closed) return
    clearInterval(progressTimer)
    handlers.onProgress?.({ done_list: [...KB_STAGES], running_list: [] })
    let i = 0
    const deltaTimer = setInterval(() => {
      if (closed) return clearInterval(deltaTimer)
      if (i < full.length) {
        // 按小块吐字，接近真实 LLM delta 节奏
        const size = 2 + Math.floor(Math.random() * 4)
        handlers.onDelta?.(full.slice(i, i + size))
        i += size
      } else {
        clearInterval(deltaTimer)
        handlers.onFinal?.({ answer: full })
        handlers.onClose?.()
      }
    }, 30)
  }, 550 * (KB_STAGES.length + 1))

  return {
    close() {
      closed = true
      clearInterval(progressTimer)
      clearTimeout(startDelta)
    },
  }
}

/* ================= 导入：模拟任务与历史（纯内存，不碰 localStorage） ================= */

// 与后端真实节点名保持一致（8 步），前端 TaskItem 做中文映射
const KB_IMPORT_STAGES = [
  'upload_file',
  'node_entry',
  'node_pdf_to_md',
  'node_item_name_recognition',
  'node_document_split',
  'node_md_img',
  'node_bge_embedding',
  'node_import_milvus',
]

const now = Date.now()
const seedHistory = [
  {
    task_id: 'mock-task-0001',
    name: 'H3C LA2608室内无线网关 用户手册-6W100.pdf',
    size: 175112,
    ts: now - 1000 * 60 * 42,
    status: 'completed',
    done_list: [...KB_IMPORT_STAGES],
    running_list: [],
  },
  {
    task_id: 'mock-task-0002',
    name: 'hak180产品安全手册.pdf',
    size: 642910,
    ts: now - 1000 * 60 * 95,
    status: 'failed',
    done_list: KB_IMPORT_STAGES.slice(0, 3),
    running_list: [],
  },
  {
    task_id: 'mock-task-0003',
    name: '2026产品线销售政策V3.docx',
    size: 43210,
    ts: now - 1000 * 60 * 60 * 5,
    status: 'interrupted',
    done_list: KB_IMPORT_STAGES.slice(0, 2),
    running_list: [],
  },
  {
    task_id: 'mock-task-0004',
    name: '企业数据安全管理规范-2026修订版.pdf',
    size: 1204832,
    ts: now - 1000 * 60 * 60 * 26,
    status: 'completed',
    done_list: [...KB_IMPORT_STAGES],
    running_list: [],
  },
]

// mock 会话内的内存历史（初始为种子数据，上传后追加）
let mockHistory = null
// 每个模拟任务的进度计数（fetchTaskStatus 每调一次推进一步）
const progressBook = new Map()

export function mockLoadHistory() {
  if (!mockHistory) mockHistory = seedHistory.map((x) => ({ ...x }))
  return mockHistory
}

/** mock 会话内保存（ImportPanel 的 add/update 都走 load→改→save 链路） */
export function mockSaveHistory(list) {
  mockHistory = (Array.isArray(list) ? list : []).map((x) => ({ ...x }))
}

export function mockUploadTaskIds(files) {
  return files.map((f, i) => `mock-task-${Date.now()}-${i}`)
}

export function mockTaskStatus(taskId) {
  // 种子里已有的任务直接返回其落库状态
  const seeded = mockLoadHistory().find((x) => x.task_id === taskId)
  if (seeded) return seeded
  const n = (progressBook.get(taskId) || 0) + 1
  progressBook.set(taskId, n)
  if (n <= KB_IMPORT_STAGES.length - 1) {
    return {
      task_id: taskId,
      status: 'processing',
      done_list: KB_IMPORT_STAGES.slice(0, n),
      running_list: [KB_IMPORT_STAGES[n]],
    }
  }
  return {
    task_id: taskId,
    status: 'completed',
    done_list: [...KB_IMPORT_STAGES],
    running_list: [],
  }
}
