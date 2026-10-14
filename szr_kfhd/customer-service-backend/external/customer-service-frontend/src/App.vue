<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import XmovAvatar from '@xmov/avatar'
import xiaoerAvatar from './assets/xiaoer.png'
import userProfileAvatar from './assets/userProfileAvatar.svg'

const senderId = ref('u1001')
const draftMessage = ref('')
const isSending = ref(false)
const errorMessage = ref('')
const messages = ref([])
const messagesContainer = ref(null)

const orders = ref([])
const products = ref([])
const isLoadingSidebar = ref(false)
const sidebarError = ref('')
const activeTab = ref('orders')

// TTS state
const ttsState = ref({})
let currentAudio = null

// Copy state
const copyState = ref({})

// ── Canvas 粒子背景系统 ──────────────────────────────────────────────
const bgCanvas = ref(null)
let animFrameId = null
let bgParticles = []
const BG_PARTICLE_COUNT = 80
const BG_CONNECT_DIST = 150
const BG_MOUSE_RADIUS = 180
const bgMouse = { x: null, y: null }

function createBgParticles(w, h) {
  const palette = [
    [13, 148, 136], [20, 184, 166], [245, 158, 11],
    [217, 119, 6], [2, 132, 199], [56, 189, 248],
  ]
  bgParticles = Array.from({ length: BG_PARTICLE_COUNT }, () => {
    const color = palette[Math.floor(Math.random() * palette.length)]
    return {
      x: Math.random() * w, y: Math.random() * h,
      size: Math.random() * 2.5 + 1,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      color, opacity: Math.random() * 0.45 + 0.12,
      phase: Math.random() * Math.PI * 2,
      pulse: Math.random() * 0.015 + 0.005,
    }
  })
}

function animateBg(ctx, w, h, time) {
  ctx.clearRect(0, 0, w, h)

  for (const p of bgParticles) {
    p.x += p.vx + Math.sin(time * 0.001 + p.phase) * 0.25
    p.y += p.vy + Math.cos(time * 0.001 + p.phase + 1) * 0.25

    if (bgMouse.x !== null) {
      const dx = p.x - bgMouse.x, dy = p.y - bgMouse.y
      const dist = Math.hypot(dx, dy)
      if (dist < BG_MOUSE_RADIUS) {
        const force = (BG_MOUSE_RADIUS - dist) / BG_MOUSE_RADIUS
        p.x += (dx / dist) * force * 0.7
        p.y += (dy / dist) * force * 0.7
      }
    }

    if (p.x < -20) p.x = w + 20; if (p.x > w + 20) p.x = -20
    if (p.y < -20) p.y = h + 20; if (p.y > h + 20) p.y = -20
  }

  // 连线
  ctx.lineWidth = 0.5
  for (let i = 0; i < bgParticles.length; i++) {
    for (let j = i + 1; j < bgParticles.length; j++) {
      const dx = bgParticles[i].x - bgParticles[j].x
      const dy = bgParticles[i].y - bgParticles[j].y
      const dist = Math.hypot(dx, dy)
      if (dist < BG_CONNECT_DIST) {
        const alpha = (1 - dist / BG_CONNECT_DIST) * 0.1
        ctx.strokeStyle = `rgba(13,148,136,${alpha})`
        ctx.beginPath()
        ctx.moveTo(bgParticles[i].x, bgParticles[i].y)
        ctx.lineTo(bgParticles[j].x, bgParticles[j].y)
        ctx.stroke()
      }
    }
  }

  // 粒子光晕
  for (const p of bgParticles) {
    const pulse = 1 + Math.sin(time * p.pulse + p.phase) * 0.25
    const r = p.size * pulse
    const [cr, cg, cb] = p.color

    ctx.beginPath()
    ctx.arc(p.x, p.y, r * 2.5, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${cr},${cg},${cb},${p.opacity * 0.08})`
    ctx.fill()

    ctx.beginPath()
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${cr},${cg},${cb},${p.opacity * 0.7})`
    ctx.fill()
  }
}

function initBg() {
  const canvas = bgCanvas.value
  if (!canvas) return
  // 亮色商务主题下 .bg-canvas 已被 display:none 隐藏，粒子动画不再启动
  // （想恢复粒子背景：删掉样式里 .bg-canvas 的 display: none 即可）
  if (window.getComputedStyle(canvas).display === 'none') return
  const ctx = canvas.getContext('2d')

  const resize = () => {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    createBgParticles(canvas.width, canvas.height)
  }
  resize()
  window.addEventListener('resize', resize)

  const onMouseMove = (e) => { bgMouse.x = e.clientX; bgMouse.y = e.clientY }
  const onMouseLeave = () => { bgMouse.x = null; bgMouse.y = null }
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseleave', onMouseLeave)

  const loop = (time) => {
    animateBg(ctx, canvas.width, canvas.height, time)
    animFrameId = requestAnimationFrame(loop)
  }
  animFrameId = requestAnimationFrame(loop)

  canvas._cleanup = () => {
    cancelAnimationFrame(animFrameId)
    window.removeEventListener('resize', resize)
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseleave', onMouseLeave)
  }
}
// ── 粒子背景系统结束 ──────────────────────────────────────────────────

// 客服数字人配置
const customerService = {
  name: '小宝',
  title: '金牌客服',
  avatar: xiaoerAvatar,
  status: '在线'
}

// 用户配置
const userProfile = {
  name: '你',
  avatar: userProfileAvatar
}

// 将消息分组为 Turn 结构
const turns = computed(() => {
  const result = []
  let currentTurn = null
  let turnIndex = 0

  for (const message of messages.value) {
    if (message.type === 'divider') {
      if (currentTurn) {
        result.push(currentTurn)
        currentTurn = null
      }
      result.push({
        type: 'divider',
        text: message.text
      })
      continue
    }

    if (message.role === 'user') {
      // 如果有待处理的当前 turn，先保存
      if (currentTurn) {
        result.push(currentTurn)
      }
      // 创建新的 turn
      turnIndex++
      currentTurn = {
        type: 'turn',
        id: `turn-${turnIndex}`,
        index: turnIndex,
        userMessage: message,
        botMessages: []
      }
    } else if (message.role === 'bot') {
      if (!currentTurn) {
        // 如果没有当前 turn，创建一个（可能是因为历史消息）
        turnIndex++
        currentTurn = {
          type: 'turn',
          id: `turn-${turnIndex}`,
          index: turnIndex,
          userMessage: null,
          botMessages: []
        }
      }
      currentTurn.botMessages.push(message)
    }
  }

  if (currentTurn) {
    result.push(currentTurn)
  }

  return result
})

const chatEndpoint = computed(() => '/api/chat')
const chatHistoryEndpoint = computed(
  () => `/api/chat/history?sender_id=${encodeURIComponent(senderId.value.trim())}`
)
const commerceOrdersEndpoint = computed(
  () => `/commerce/users/${encodeURIComponent(senderId.value.trim())}/orders`
)
const commerceProductsEndpoint = computed(
  () => `/commerce/users/${encodeURIComponent(senderId.value.trim())}/products`
)

function createBaseMessage(role) {
  return {
    id: crypto.randomUUID(),
    role,
    buttons: [],
  }
}

function appendUserText(text) {
  messages.value.push({
    ...createBaseMessage('user'),
    type: 'text',
    text,
  })
}

function appendUserObject(objectType, payload) {
  messages.value.push({
    ...createBaseMessage('user'),
    type: 'object',
    objectType,
    payload,
  })
}

function appendBotMessages(botMessages) {
  for (const message of botMessages) {
    appendMessage('bot', message)
  }
}

function appendMessage(role, message) {
  if (role === 'divider') {
    messages.value.push({
      ...createBaseMessage('divider'),
      type: 'divider',
      text: message.text ?? '以上为历史消息',
    })
    return
  }

  if (message.object) {
    messages.value.push({
      ...createBaseMessage(role),
      type: 'object',
      objectType: message.object.type,
      payload: message.object,
    })
  } else {
    messages.value.push({
      ...createBaseMessage(role),
      type: 'text',
      text: message.text ?? '',
      suggestions: message.suggestions ?? null,
    })
  }
}

function setHistoryMessages(historyMessages) {
  messages.value = []
  for (const message of historyMessages) {
    const role = ['user', 'bot', 'divider'].includes(message.role) ? message.role : 'bot'
    appendMessage(role, message)
  }
}

async function scrollToBottom() {
  await nextTick()
  const container = messagesContainer.value
  if (!container) {
    return
  }
  container.scrollTop = container.scrollHeight
}

watch(
  () => messages.value.length,
  async () => {
    await scrollToBottom()
  }
)

function resetConversation() {
  messages.value = []
  errorMessage.value = ''
}

function formatAmount(amount) {
  const numericAmount = Number(amount)
  if (Number.isNaN(numericAmount)) {
    return '￥0.00'
  }
  return `￥${numericAmount.toFixed(2)}`
}

function formatOrderSummary(order) {
  return order.status ? `订单状态：${order.status}` : '订单'
}

const ORDER_STATUS_CLASS = {
  '待发货': 'status-warning',
  '待揽收': 'status-warning',
  '运输中': 'status-info',
  '派送中': 'status-info',
  '已完成': 'status-success',
  '已签收': 'status-success',
  '已取消': 'status-muted',
  '退款中': 'status-danger',
  '已退款': 'status-muted',
}

function getStatusClass(status) {
  return ORDER_STATUS_CLASS[status] || 'status-muted'
}

function formatProductSummary(product) {
  if (product.description) {
    return product.description
  }
  if (product.attributes?.price) {
    return `商品价格：${formatAmount(product.attributes.price)}`
  }
  return '商品信息'
}

function getObjectTitle(message) {
  const payload = message.payload ?? {}
  if (payload.title) {
    return payload.title
  }
  return message.objectType === 'order' ? '订单对象' : '商品对象'
}

function getObjectIdentifier(message) {
  const payload = message.payload ?? {}
  const id = payload.order_id ?? payload.product_id ?? payload.id
  const label = message.objectType === 'order' ? '订单号' : '商品号'
  return id ? `${label}：${id}` : label
}

function getObjectSummary(message) {
  const payload = message.payload ?? {}
  if (message.objectType === 'order') {
    const status = payload.status ?? payload.attributes?.status
    return status ? `订单状态：${status}` : '订单'
  }
  return formatProductSummary(payload)
}

function getObjectAmount(message) {
  const payload = message.payload ?? {}
  const amount = message.objectType === 'order'
    ? payload.amount ?? payload.attributes?.amount
    : payload.price ?? payload.attributes?.price
  return formatAmount(amount)
}

async function fetchSidebarData() {
  const currentSenderId = senderId.value.trim()
  orders.value = []
  products.value = []
  sidebarError.value = ''

  if (!currentSenderId) {
    return
  }

  isLoadingSidebar.value = true
  try {
    const [ordersResponse, productsResponse] = await Promise.all([
      fetch(commerceOrdersEndpoint.value),
      fetch(commerceProductsEndpoint.value),
    ])

    const [ordersPayload, productsPayload] = await Promise.all([
      ordersResponse.json(),
      productsResponse.json(),
    ])

    if (!ordersResponse.ok) {
      throw new Error(ordersPayload.detail || '加载订单列表失败。')
    }
    if (!productsResponse.ok) {
      throw new Error(productsPayload.detail || '加载商品列表失败。')
    }

    orders.value = Array.isArray(ordersPayload?.data?.orders) ? ordersPayload.data.orders : []
    products.value = Array.isArray(productsPayload?.data?.products) ? productsPayload.data.products : []
  } catch (error) {
    sidebarError.value = error instanceof Error ? error.message : '加载右侧列表失败。'
  } finally {
    isLoadingSidebar.value = false
  }
}

async function fetchChatHistory() {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    messages.value = []
    return
  }

  try {
    const response = await fetch(chatHistoryEndpoint.value)
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || '加载历史消息失败。')
    }
    if (currentSenderId === senderId.value.trim()) {
      setHistoryMessages(Array.isArray(data?.messages) ? data.messages : [])
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载历史消息失败。'
  }
}

async function sendPayload(payload) {
  if (isSending.value) {
    return
  }

  errorMessage.value = ''
  isSending.value = true

  try {
    const response = await fetch(chatEndpoint.value, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sender_id: senderId.value.trim(),
        ...payload,
      }),
    })

    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || '请求失败。')
    }

    appendBotMessages(data.messages ?? [])
    // 数字人已连接时，同步朗读本次后端返回的内容
    speakByDigitalHuman(extractSpeakText(data.messages ?? []))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求失败。'
  } finally {
    isSending.value = false
  }
}

async function sendSuggestion(text) {
  appendUserText(text)
  await sendPayload({ text })
}

async function sendQuickText(text) {
  draftMessage.value = text
  await sendTextMessage()
}
async function sendTextMessage() {
  const text = draftMessage.value.trim()
  const currentSenderId = senderId.value.trim()

  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }
  if (!text) {
    return
  }

  draftMessage.value = ''
  appendUserText(text)
  await sendPayload({ text })
}

async function sendOrder(order) {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }

  appendUserObject('order', { ...order })
  await sendPayload({
    object: {
      type: 'order',
      id: order.order_id,
      title: order.title,
      attributes: {
        status: order.status,
        amount: order.amount,
        created_at: order.created_at,
        cover_url: order.cover_url,
      },
    },
  })
}

async function sendProduct(product) {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }

  appendUserObject('product', { ...product })
  await sendPayload({
    object: {
      type: 'product',
      id: product.product_id,
      title: product.title,
      attributes: {
        price: product.price,
        cover_url: product.cover_url,
        description: product.description,
      },
    },
  })
}

watch(
  () => senderId.value.trim(),
  async (value, previousValue) => {
    if (value === previousValue) {
      return
    }

    resetConversation()
    if (!value) {
      orders.value = []
      products.value = []
      return
    }
    await Promise.all([fetchSidebarData(), fetchChatHistory()])
  }
)

// ── 数字人（魔珐星云）─────────────────────────────────────────────
const dhStatus = ref('idle') // idle | loading | ready | error
const dhProgress = ref(0)
const dhError = ref('')
const dhStageText = ref('')
const dhContainer = ref(null)
let liteSDK = null

const DH_STATUS_TEXT = {
  idle: '数字人 · 未连接',
  loading: '数字人 · 加载中',
  ready: '数字人 · 已连接',
  error: '数字人 · 连接失败',
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// 等 Vue 把 v-if 里带 ref 的容器真正渲染到 DOM 再交给 SDK，
// 否则 SDK 拿不到 containerId 对应的元素（错误码 10001）
async function waitForContainer(maxTries = 20) {
  for (let i = 0; i < maxTries; i += 1) {
    if (dhContainer.value) return dhContainer.value
    await nextTick()
    await sleep(50)
  }
  return null
}

async function connectDigitalHuman() {
  if (dhStatus.value === 'loading' || dhStatus.value === 'ready') return

  dhStatus.value = 'loading'
  dhProgress.value = 0
  dhError.value = ''
  dhStageText.value = '正在获取数字人凭证…'

  // 凭证从后端拿，app_secret 不出现在前端源码里
  let cred
  try {
    const resp = await fetch('/api/digital-human/credentials')
    if (!resp.ok) throw new Error(`接口返回 ${resp.status}`)
    cred = await resp.json()
  } catch (e) {
    dhStatus.value = 'error'
    dhError.value = '获取数字人凭证失败，请确认客服后端已启动。'
    console.error('[数字人] 获取凭证失败:', e)
    return
  }

  if (!cred?.app_id || !cred?.app_secret) {
    dhStatus.value = 'error'
    dhError.value = '后端未配置数字人凭证，请检查 .env。'
    return
  }

  const el = await waitForContainer()
  if (!el) {
    dhStatus.value = 'error'
    dhError.value = '数字人容器未就绪，请重试。'
    return
  }

  dhStageText.value = '正在连接数字人服务…'
  try {
    liteSDK = new XmovAvatar({
      containerId: '#digital-human-sdk',
      appId: cred.app_id,
      appSecret: cred.app_secret,
      gatewayServer: cred.gateway_server,
      hardwareAcceleration: 'prefer-hardware',
      enableLogger: true,

      onMessage(message) {
        // 50001/50002 是在线/离线模式切换，属正常状态而非错误
        if (message?.code && message.code !== 50001 && message.code !== 50002) {
          dhError.value = `数字人错误 code=${message.code} ${message.message || ''}`
          // 加载阶段的 SDK 错误直接判定为失败，避免卡在"连接中"
          if (dhStatus.value === 'loading') dhStatus.value = 'error'
          console.error('[数字人] SDK 消息:', message)
        }
      },
      onStateChange(state) {
        if (state === 'speak') dhStageText.value = '数字人正在朗读…'
        else if (state === 'interactive_idle') dhStageText.value = '已就绪，等待提问'
      },
      onVoiceStateChange(state) {
        if (state === 'start') dhStageText.value = '数字人正在朗读…'
        else if (state === 'end') dhStageText.value = '已就绪，等待提问'
      },
      onStartSessionWarning(msg) {
        console.warn('[数字人] 会话配置警告:', msg)
      },
    })

    await liteSDK.init({
      initModel: 'normal',
      onDownloadProgress(progress) {
        dhProgress.value = Math.max(0, Math.min(100, Math.round(progress)))
        if (progress < 100) dhStageText.value = '正在下载 3D 模型与表情资源…'
      },
    })

    dhProgress.value = 100
    dhStatus.value = 'ready'
    dhStageText.value = '已就绪，等待提问'
    await nextTick()
    applyDigitalHumanLayout()
  } catch (e) {
    dhStatus.value = 'error'
    // 透出真实原因（SDK 错误码 / 异常信息），方便定位，别只给通用文案
    const detail = e?.message || (e?.code != null ? `code=${e.code}` : String(e))
    dhError.value = `数字人初始化失败：${detail}`
    console.error('[数字人] 初始化失败:', e)
    try {
      await liteSDK?.destroy()
    } catch (_) {
      /* 忽略销毁异常 */
    }
    liteSDK = null
  }
}

async function disconnectDigitalHuman() {
  const instance = liteSDK
  liteSDK = null
  dhStatus.value = 'idle'
  dhProgress.value = 0
  dhError.value = ''
  dhStageText.value = ''
  try {
    await instance?.destroy()
  } catch (_) {
    /* 忽略销毁异常 */
  }
}

function toggleDigitalHuman() {
  if (dhStatus.value === 'ready') disconnectDigitalHuman()
  else if (dhStatus.value !== 'loading') connectDigitalHuman()
}

// 左栏宽度在 1760px 上限下约 580px，远宽于官方 9:16 竖屏比例。
// 这里让 SDK 按容器宽度等比缩放并底部对齐，避免人物被横向拉伸变形。
function applyDigitalHumanLayout() {
  const el = dhContainer.value
  if (!liteSDK || !el) return
  const width = el.clientWidth
  const height = el.clientHeight
  if (!width || !height) return
  // SDK scale 语义：数字 = 相对原生 1080x1920 的倍率（传小数会把人物放大出框）；
  // "95vh" 字符串 = 人物高度取容器高度的 95%，底部对齐时全身完整、头顶留 5% 余量
  const scale = '95vh'
  try {
    liteSDK.changeLayout({
      container: { size: [width, height] },
      avatar: {
        v_align: 'bottom',
        h_align: 'center',
        scale,
        offset_x: 0,
        offset_y: 0,
      },
    })
  } catch (e) {
    console.warn('[数字人] 布局适配失败，使用默认布局:', e)
  }
}

// 从后端响应里提取要朗读的内容
function extractSpeakText(botMessages) {
  const parts = []
  for (const msg of botMessages) {
    if (msg?.text) {
      parts.push(String(msg.text).trim())
    } else if (msg?.object) {
      // 只回了订单/商品对象、没有文字时给一句兜底，避免数字人毫无反应
      const label = msg.object.type === 'order' ? '订单' : '商品'
      const title = msg.object.title ? `「${msg.object.title}」` : ''
      parts.push(`已为您找到${title}${label}信息，请问需要了解什么？`)
    }
  }
  return parts.filter(Boolean).join(' ')
}

function speakByDigitalHuman(text) {
  if (dhStatus.value !== 'ready' || !liteSDK || !text) return
  try {
    // 上一段可能刚说完，先切回互动待机，再起新的一段，避免口型错位
    liteSDK.interactiveidle()
    liteSDK.speak(text, true, true)
  } catch (e) {
    console.warn('[数字人] 朗读失败:', e)
  }
}

function handleDhWindowResize() {
  // 窗口尺寸变化时，先把悬浮窗夹回卡片内，再让数字人重新适配布局
  const widget = dhWidgetEl.value
  if (widget) dhClampToCard(parseFloat(widget.style.left) || 0, parseFloat(widget.style.top) || 0)
  if (dhStatus.value === 'ready') applyDigitalHumanLayout()
}

function handleDhBeforeUnload() {
  // 刷新/关闭页面时主动断开，避免占用魔珐星云并发额度（错误码 10005）
  try {
    liteSDK?.destroy()
  } catch (_) {
    /* 忽略销毁异常 */
  }
}

// ── 数字人悬浮窗：拖动 / 缩放 / 收起（只能在聊天卡片内活动）──────────
const dhWidgetEl = ref(null)
const chatCardEl = ref(null)
const sidebarEl = ref(null)
const dhCollapsed = ref(false)

const DH_MIN_W = 130
const DH_MIN_H = 210
const DH_MAX_W = 340
const DH_MAX_H = 560
const DH_CIRCLE = 56
const DH_RIGHT_GAP = 18
const DH_ANIM_MS = 340

let dhDragState = null
let dhResizeState = null
let dhDragMoved = false
let dhSavedBox = { left: 24, top: 120, width: 176, height: 292 }

// 阻止事件继续冒泡（收起按钮要用，免得点一下被当成拖动）
function stopPointerEvent(event) {
  event.stopPropagation()
}

function dhBump() {
  const card = chatCardEl.value
  if (!card) return
  card.classList.add('boundary-hit')
  window.setTimeout(() => card.classList.remove('boundary-hit'), 280)
}

function dhClampToCard(left, top) {
  const card = chatCardEl.value
  const widget = dhWidgetEl.value
  if (!card || !widget) return
  const maxX = Math.max(6, card.clientWidth - widget.offsetWidth - 6)
  const maxY = Math.max(6, card.clientHeight - widget.offsetHeight - 6)
  const nx = Math.min(Math.max(left, 6), maxX)
  const ny = Math.min(Math.max(top, 6), maxY)
  if (Math.round(nx) !== Math.round(left) || Math.round(ny) !== Math.round(top)) dhBump()
  widget.style.left = nx + 'px'
  widget.style.top = ny + 'px'
  widget.style.bottom = 'auto'
}

// 初始摆位：卡片左下角、离底部 104px
function initDhWidgetPlacement() {
  const card = chatCardEl.value
  const widget = dhWidgetEl.value
  if (!card || !widget) return
  widget.style.width = '176px'
  widget.style.height = '292px'
  dhClampToCard(24, card.clientHeight - widget.offsetHeight - 104)
}

function onDhPointerDown(event) {
  const widget = dhWidgetEl.value
  const card = chatCardEl.value
  if (!widget || !card) return
  const wr = widget.getBoundingClientRect()
  const cr = card.getBoundingClientRect()
  dhDragMoved = false
  dhDragState = {
    startX: event.clientX,
    startY: event.clientY,
    originLeft: wr.left - cr.left,
    originTop: wr.top - cr.top,
  }
  widget.classList.add('dragging')
  try { event.currentTarget.setPointerCapture(event.pointerId) } catch (_) { /* 忽略 */ }
  event.preventDefault()
}

function onDhResizeDown(event) {
  const widget = dhWidgetEl.value
  if (!widget) return
  dhResizeState = {
    startX: event.clientX,
    startY: event.clientY,
    width: widget.offsetWidth,
    height: widget.offsetHeight,
  }
  try { event.currentTarget.setPointerCapture(event.pointerId) } catch (_) { /* 忽略 */ }
  event.preventDefault()
}

function onDhPointerMove(event) {
  if (dhDragState) {
    const dx = event.clientX - dhDragState.startX
    const dy = event.clientY - dhDragState.startY
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dhDragMoved = true
    dhClampToCard(dhDragState.originLeft + dx, dhDragState.originTop + dy)
    return
  }
  if (dhResizeState) {
    const widget = dhWidgetEl.value
    if (!widget) return
    const width = Math.min(Math.max(dhResizeState.width + (event.clientX - dhResizeState.startX), DH_MIN_W), DH_MAX_W)
    const height = Math.min(Math.max(dhResizeState.height + (event.clientY - dhResizeState.startY), DH_MIN_H), DH_MAX_H)
    widget.style.width = width + 'px'
    widget.style.height = height + 'px'
    dhClampToCard(parseFloat(widget.style.left) || 0, parseFloat(widget.style.top) || 0)
  }
}

function onDhPointerUp() {
  const widget = dhWidgetEl.value
  if (dhDragState) {
    dhDragState = null
    if (widget) widget.classList.remove('dragging')
    // 收起态圆圈上「没拖动」的一下 = 展开；拖动过就不算点击
    if (dhCollapsed.value && !dhDragMoved) expandDhWidget()
    else if (dhStatus.value === 'ready') applyDigitalHumanLayout()
    return
  }
  if (dhResizeState) {
    dhResizeState = null
    if (dhStatus.value === 'ready') applyDigitalHumanLayout()
  }
}

// 收起：缩成 56px 的小圆圈，贴到卡片右侧
function collapseDhWidget() {
  const widget = dhWidgetEl.value
  const card = chatCardEl.value
  if (!widget || !card || dhCollapsed.value) return
  const wr = widget.getBoundingClientRect()
  const cr = card.getBoundingClientRect()
  dhSavedBox = {
    left: wr.left - cr.left,
    top: wr.top - cr.top,
    width: widget.offsetWidth,
    height: widget.offsetHeight,
  }
  widget.classList.add('animating')
  widget.classList.add('collapsed')
  dhCollapsed.value = true
  widget.style.width = DH_CIRCLE + 'px'
  widget.style.height = DH_CIRCLE + 'px'
  const nx = Math.max(6, card.clientWidth - DH_CIRCLE - DH_RIGHT_GAP)
  const ny = Math.min(Math.max(dhSavedBox.top, 6), Math.max(6, card.clientHeight - DH_CIRCLE - 6))
  widget.style.left = nx + 'px'
  widget.style.top = ny + 'px'
  widget.style.bottom = 'auto'
  window.setTimeout(() => widget.classList.remove('animating'), DH_ANIM_MS)
}

// 展开：回到收起前的位置与尺寸
function expandDhWidget() {
  const widget = dhWidgetEl.value
  if (!widget || !dhCollapsed.value) return
  widget.classList.add('animating')
  widget.classList.remove('collapsed')
  dhCollapsed.value = false
  widget.style.width = dhSavedBox.width + 'px'
  widget.style.height = dhSavedBox.height + 'px'
  dhClampToCard(dhSavedBox.left, dhSavedBox.top)
  window.setTimeout(() => {
    widget.classList.remove('animating')
    if (dhStatus.value === 'ready') applyDigitalHumanLayout()
  }, DH_ANIM_MS)
}

// 业务对象面板：收起 / 展开（聊天卡片会跟着变宽，数字人要重新夹边）
function toggleSidebarPanel() {
  const el = sidebarEl.value
  if (!el) return
  el.classList.toggle('collapsed')
  window.setTimeout(() => {
    const widget = dhWidgetEl.value
    if (widget && !dhCollapsed.value) {
      dhClampToCard(parseFloat(widget.style.left) || 0, parseFloat(widget.style.top) || 0)
    }
    if (dhStatus.value === 'ready') applyDigitalHumanLayout()
  }, DH_ANIM_MS)
}

onMounted(async () => {
  initBg()
  window.addEventListener('resize', handleDhWindowResize)
  window.addEventListener('beforeunload', handleDhBeforeUnload)
  window.addEventListener('pointermove', onDhPointerMove)
  window.addEventListener('pointerup', onDhPointerUp)
  await Promise.all([fetchSidebarData(), fetchChatHistory()])
  await nextTick()
  initDhWidgetPlacement()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleDhWindowResize)
  window.removeEventListener('beforeunload', handleDhBeforeUnload)
  window.removeEventListener('pointermove', onDhPointerMove)
  window.removeEventListener('pointerup', onDhPointerUp)
  if (bgCanvas.value?._cleanup) bgCanvas.value._cleanup()
  // 释放魔珐星云连接，避免占用并发额度（错误码 10005）
  try {
    liteSDK?.destroy()
  } catch (_) {
    /* 忽略销毁异常 */
  }
  liteSDK = null
})

async function playTts(botMsg) {
  const msgId = botMsg.id
  if (!botMsg.text || ttsState.value[msgId] === 'loading') return

  // 数字人正在说话时，先打断它，避免两路语音叠在一起
  if (dhStatus.value === 'ready' && liteSDK) {
    try {
      liteSDK.interactiveidle()
    } catch (_) {
      /* 忽略打断异常 */
    }
  }

  if (currentAudio) { currentAudio.pause(); currentAudio = null }
  for (const key of Object.keys(ttsState.value)) {
    if (ttsState.value[key] === 'playing') ttsState.value[key] = 'idle'
  }

  ttsState.value[msgId] = 'loading'
  try {
    const response = await fetch('/api/chat/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: botMsg.text }),
    })
    if (!response.ok) throw new Error('TTS 请求失败')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    currentAudio = new Audio(url)
    ttsState.value[msgId] = 'playing'
    currentAudio.onended = () => { ttsState.value[msgId] = 'idle'; URL.revokeObjectURL(url); currentAudio = null }
    currentAudio.onerror = () => { ttsState.value[msgId] = 'idle'; URL.revokeObjectURL(url); currentAudio = null }
    await currentAudio.play()
  } catch (error) {
    ttsState.value[msgId] = 'idle'
    console.error('TTS error:', error)
  }
}

async function copyBotText(botMsg) {
  const msgId = botMsg.id
  try {
    await navigator.clipboard.writeText(botMsg.text)
    copyState.value[msgId] = true
    setTimeout(() => { copyState.value[msgId] = false }, 1800)
  } catch (error) {
    console.error('Copy failed:', error)
  }
}
</script>

<template>
  <div class="app-shell">
    <canvas ref="bgCanvas" class="bg-canvas"></canvas>
    <div class="app-layout">
      <div class="workspace">
      <div ref="chatCardEl" class="chat-card">
        <header class="chat-header">
          <div class="header-content">
            <div class="header-info">
              <h1>电商客服系统</h1>
              <div class="service-info">
                <div class="service-avatar-wrapper">
                  <img :src="customerService.avatar" class="service-avatar" />
                  <span class="status-indicator"></span>
                </div>
                <div class="service-details">
                  <span class="service-name">{{ customerService.name }}</span>
                  <span class="service-status">{{ customerService.status }}</span>
                </div>
              </div>
            </div>
            <button type="button" class="clear-button" title="清空对话" @click="resetConversation">
              <span>🔄</span>
              <span>新对话</span>
            </button>
          </div>
        </header>

        <section class="controls">
          <label class="field">
            <span>sender_id</span>
            <div class="field-row">
              <input v-model="senderId" type="text" placeholder="u1001" />
              <button
                type="button"
                class="secondary-button"
                :disabled="isLoadingSidebar"
                @click="fetchSidebarData"
              >
                {{ isLoadingSidebar ? '加载中...' : '刷新对象列表' }}
              </button>
            </div>
          </label>
        </section>

        <section ref="messagesContainer" class="messages">
          <div v-if="turns.length === 0" class="welcome">
            <div class="welcome-card">
              <div class="welcome-glow"></div>
              <div class="welcome-avatar-wrapper">
                <img :src="customerService.avatar" class="welcome-avatar" alt="小宝" />
                <span class="welcome-status-pulse"></span>
              </div>
              <h2 class="welcome-greeting">Hi，我是 {{ customerService.name }}</h2>
              <p class="welcome-subtitle">你的专属电商客服，随时为你服务</p>
              <div class="welcome-chips">
                <button
                  v-for="chip in ['我要退款', '查订单状态', '商品推荐', '退换货政策']"
                  :key="chip"
                  type="button"
                  class="welcome-chip"
                  :disabled="isSending"
                  @click="sendQuickText(chip)"
                >{{ chip }}</button>
              </div>
              <p class="welcome-features">
                <span>💬 文字对话</span>
                <span>🔊 语音播报</span>
                <span>📦 订单查询</span>
                <span>🛍️ 商品咨询</span>
              </p>
            </div>
          </div>

          <!-- Turn 结构展示 -->
          <template v-for="(item, index) in turns" :key="item.id || index">
            <!-- 分隔线 -->
            <div v-if="item.type === 'divider'" class="history-divider">
              <span>{{ item.text }}</span>
            </div>

            <!-- Turn 卡片 -->
            <div v-else class="turn-card" :class="{ 'has-user-message': item.userMessage }">
              <!-- Turn 标识 -->
              <div class="turn-header">
                <span class="turn-badge">Turn {{ item.index }}</span>
                <span class="turn-label">对话轮次</span>
              </div>

              <!-- 用户消息区域 -->
              <div v-if="item.userMessage" class="turn-section user-section">
                <div class="section-header">
                  <div class="avatar-wrapper user-avatar">
                    <img :src="userProfile.avatar" class="avatar" />
                  </div>
                  <div class="agent-info">
                    <span class="agent-name">{{ userProfile.name }}</span>
                    <span class="agent-label">用户</span>
                  </div>
                </div>
                <div class="turn-bubble user-bubble">
                  <template v-if="item.userMessage.type === 'object'">
                    <div class="object-card" :class="`object-card-${item.userMessage.objectType}`">
                      <div class="object-card-badge">
                        {{ item.userMessage.objectType === 'order' ? '订单对象' : '商品对象' }}
                      </div>
                      <img
                        v-if="item.userMessage.type === 'object' && item.userMessage.payload.cover_url"
                        :src="item.userMessage.payload.cover_url"
                        :alt="getObjectTitle(item.userMessage)"
                        class="object-card-image"
                        @error="$event.target.style.display='none'"
                      />
                      <div class="object-card-title">{{ getObjectTitle(item.userMessage) }}</div>
                      <div class="object-card-meta">{{ getObjectIdentifier(item.userMessage) }}</div>
                      <div class="object-card-meta">
                        <span v-if="item.userMessage.objectType === 'order' && item.userMessage.payload.status" class="status-badge" :class="getStatusClass(item.userMessage.payload.status)">{{ item.userMessage.payload.status }}</span>
                        <span v-else>{{ getObjectSummary(item.userMessage) }}</span>
                      </div>
                      <div class="object-card-price">{{ getObjectAmount(item.userMessage) }}</div>
                    </div>
                  </template>
                  <template v-else>
                    <p>{{ item.userMessage.text }}</p>
                  </template>
                </div>
              </div>

              <!-- 客服回复区域 -->
              <div v-if="item.botMessages.length > 0" class="turn-section bot-section">
                <div class="section-header">
                  <div class="avatar-wrapper service-avatar">
                    <img :src="customerService.avatar" class="avatar" />
                    <span class="status-dot"></span>
                  </div>
                  <div class="agent-info">
                    <span class="agent-name">{{ customerService.name }}</span>
                    <span class="agent-label">{{ customerService.title }}</span>
                  </div>
                </div>
                <div class="bot-messages">
                  <div
                    v-for="(botMsg, msgIndex) in item.botMessages"
                    :key="msgIndex"
                    class="turn-bubble bot-bubble"
                  >
                    <template v-if="botMsg.type === 'object'">
                      <div class="object-card" :class="`object-card-${botMsg.objectType}`">
                        <div class="object-card-badge">
                          {{ botMsg.objectType === 'order' ? '订单对象' : '商品对象' }}
                        </div>
                        <img
                          v-if="botMsg.type === 'object' && botMsg.payload.cover_url"
                          :src="botMsg.payload.cover_url"
                          :alt="getObjectTitle(botMsg)"
                          class="object-card-image"
                          @error="$event.target.style.display='none'"
                        />
                        <div class="object-card-title">{{ getObjectTitle(botMsg) }}</div>
                        <div class="object-card-meta">{{ getObjectIdentifier(botMsg) }}</div>
                        <div class="object-card-meta">
                          <span v-if="botMsg.objectType === 'order' && botMsg.payload.status" class="status-badge" :class="getStatusClass(botMsg.payload.status)">{{ botMsg.payload.status }}</span>
                          <span v-else>{{ getObjectSummary(botMsg) }}</span>
                        </div>
                        <div class="object-card-price">{{ getObjectAmount(botMsg) }}</div>
                      </div>
                    </template>
                    <template v-else>
                      <div class="bot-text-row">
                        <p>{{ botMsg.text }}</p>
                        <div class="bot-actions">
                          <button type="button" class="tts-button"
                            :class="{ 'tts-loading': ttsState[botMsg.id] === 'loading', 'tts-playing': ttsState[botMsg.id] === 'playing' }"
                            :disabled="ttsState[botMsg.id] === 'loading'"
                            :title="ttsState[botMsg.id] === 'playing' ? '正在播放...' : '语音播报'"
                            @click.stop="playTts(botMsg)">
                            <span v-if="ttsState[botMsg.id] === 'loading'" class="tts-spinner"></span>
                            <span v-else-if="ttsState[botMsg.id] === 'playing'" class="tts-bars">
                              <span></span><span></span><span></span>
                            </span>
                            <span v-else>🔈</span>
                          </button>
                          <button type="button" class="copy-button"
                            :class="{ 'copy-done': copyState[botMsg.id] }"
                            :title="copyState[botMsg.id] ? '已复制' : '复制文字'"
                            @click.stop="copyBotText(botMsg)">
                            <span v-if="copyState[botMsg.id]">✓</span>
                            <span v-else>📋</span>
                          </button>
                        </div>
                      </div>
                    </template>
                    <div v-if="botMsg.suggestions && botMsg.suggestions.length > 0" class="suggestion-chips">
                      <button
                        v-for="sug in botMsg.suggestions"
                        :key="sug"
                        type="button"
                        class="suggestion-chip"
                        :disabled="isSending"
                        @click.stop="sendSuggestion(sug)"
                      >{{ sug }}</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </section>

        <div v-if="isSending" class="typing-indicator">
          <div class="typing-avatar">
            <img :src="customerService.avatar" class="avatar-small" alt="小宝" />
          </div>
          <div class="typing-bubble">
            <span class="typing-dots">
              <span></span><span></span><span></span>
            </span>
            <span class="typing-label">小宝正在输入...</span>
          </div>
        </div>

        <p v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </p>

        <form class="composer" @submit.prevent="sendTextMessage">
          <input
            v-model="draftMessage"
            type="text"
            placeholder="请输入咨询内容..."
            :disabled="isSending"
          />
          <button type="submit" :disabled="isSending || !draftMessage.trim()">
            {{ isSending ? '发送中...' : '发送' }}
          </button>
        </form>

        <!-- ============ 数字人悬浮窗（只能在这张卡片内活动）============ -->
        <div ref="dhWidgetEl" class="dh-widget">
          <div class="dh-widget-bar" title="按住这里拖动数字人" @pointerdown="onDhPointerDown">
            <span class="dh-status-dot" :class="`dh-dot-${dhStatus}`"></span>
            <span class="dh-widget-title">{{ DH_STATUS_TEXT[dhStatus] }}</span>
            <span class="dh-widget-grip">⠿</span>
            <button
              type="button"
              class="dh-widget-collapse"
              title="收起为小圆圈"
              @pointerdown="stopPointerEvent"
              @click.stop="collapseDhWidget"
            >➖</button>
          </div>

          <div class="dh-stage">
            <div class="dh-stage-inner">
              <!-- 容器常驻 DOM：SDK init 期间就必须能找到它 -->
              <div id="digital-human-sdk" ref="dhContainer" class="dh-canvas"></div>

              <div v-if="dhStatus === 'loading'" class="dh-overlay dh-placeholder dh-placeholder-loading">
                <div class="dh-spinner"></div>
                <p class="dh-placeholder-title">正在加载数字人…</p>
                <div class="dh-progress">
                  <div class="dh-progress-bar" :style="{ width: dhProgress + '%' }"></div>
                </div>
                <p class="dh-placeholder-sub">{{ dhProgress }}% · {{ dhStageText }}</p>
              </div>

              <div v-else-if="dhStatus === 'error'" class="dh-overlay dh-placeholder dh-placeholder-error">
                <div class="dh-placeholder-icon">!</div>
                <p class="dh-placeholder-title">连接失败</p>
                <p class="dh-placeholder-sub">{{ dhError }}</p>
              </div>

              <div v-else-if="dhStatus === 'idle'" class="dh-overlay dh-placeholder">
                <div class="dh-placeholder-icon dh-placeholder-icon-idle">
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="8" r="3.4" />
                    <path d="M4.6 20c0-3.6 3.3-6.2 7.4-6.2s7.4 2.6 7.4 6.2" />
                  </svg>
                </div>
                <p class="dh-placeholder-title">数字人待连接</p>
                <p class="dh-placeholder-sub">点下方按钮加载 3D 形象</p>
              </div>
            </div>
          </div>

          <div class="dh-actions">
            <button
              type="button"
              class="dh-button"
              :class="{ 'dh-button-danger': dhStatus === 'ready' }"
              :disabled="dhStatus === 'loading'"
              @click="toggleDigitalHuman"
            >
              <template v-if="dhStatus === 'loading'">连接中… {{ dhProgress }}%</template>
              <template v-else-if="dhStatus === 'ready'">断开连接</template>
              <template v-else-if="dhStatus === 'error'">重试连接</template>
              <template v-else>连接数字人</template>
            </button>
          </div>

          <div class="dh-widget-resize" title="拖动可放大/缩小" @pointerdown="onDhResizeDown"></div>

          <!-- 收起后的圆圈：可拖、点一下展开 -->
          <div class="dh-widget-circle" title="点击展开数字人" @pointerdown="onDhPointerDown">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.6" stroke-linecap="round">
              <circle cx="12" cy="8" r="3.6" />
              <path d="M4.8 20c0-3.7 3.3-6.5 7.2-6.5s7.2 2.8 7.2 6.5" />
            </svg>
            <span class="dh-status-dot dh-widget-circle-dot" :class="`dh-dot-${dhStatus}`"></span>
          </div>
        </div>

      </div>

      <aside ref="sidebarEl" class="sidebar">
        <button
          type="button"
          class="biz-edge-btn"
          title="收起业务对象"
          aria-label="收起业务对象"
          @click="toggleSidebarPanel"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 5 16 12 9 19" />
          </svg>
        </button>

        <div class="sidebar-header">
          <h2>业务对象</h2>
        </div>

        <div class="tabs">
          <button
            type="button"
            class="tab-button"
            :class="{ active: activeTab === 'orders' }"
            @click="activeTab = 'orders'"
          >
            订单
          </button>
          <button
            type="button"
            class="tab-button"
            :class="{ active: activeTab === 'products' }"
            @click="activeTab = 'products'"
          >
            商品
          </button>
        </div>

        <p v-if="sidebarError" class="sidebar-error">{{ sidebarError }}</p>

        <div v-if="activeTab === 'orders'" class="sidebar-list">
          <div v-if="!orders.length && !isLoadingSidebar" class="sidebar-empty">
            暂无订单数据
          </div>

          <article v-for="order in orders" :key="order.order_id" class="sidebar-card">
            <div class="card-image-wrapper">
              <img
                v-if="order.cover_url"
                :src="order.cover_url"
                :alt="order.title"
                class="card-image"
                @error="$event.target.style.display='none'"
              />
              <div v-else class="card-image-placeholder">📦</div>
            </div>
            <div class="card-top">
              <div class="card-title">{{ order.title }}</div>
              <div class="card-amount">{{ formatAmount(order.amount) }}</div>
            </div>
            <div class="card-meta">订单号：{{ order.order_id }}</div>
            <div class="card-meta">
              <span class="status-badge" :class="getStatusClass(order.status)">{{ order.status }}</span>
            </div>
            <button
              type="button"
              class="secondary-button full-width"
              :disabled="isSending"
              @click="sendOrder(order)"
            >
              发送订单
            </button>
          </article>
        </div>

        <div v-else class="sidebar-list">
          <div v-if="!products.length && !isLoadingSidebar" class="sidebar-empty">
            暂无商品数据
          </div>

          <article v-for="product in products" :key="product.product_id" class="sidebar-card">
            <div class="card-image-wrapper">
              <img
                v-if="product.cover_url"
                :src="product.cover_url"
                :alt="product.title"
                class="card-image"
                @error="$event.target.style.display='none'"
              />
              <div v-else class="card-image-placeholder">🛍️</div>
            </div>
            <div class="card-top">
              <div class="card-title">{{ product.title }}</div>
              <div class="card-amount">{{ formatAmount(product.price) }}</div>
            </div>
            <div class="card-meta">商品号：{{ product.product_id }}</div>
            <div class="card-meta">商品信息：最近浏览 / 购买商品</div>
            <button
              type="button"
              class="secondary-button full-width"
              :disabled="isSending"
              @click="sendProduct(product)"
            >
              发送商品
            </button>
          </article>
        </div>

        <!-- 收起后的窄竖条：点它展开 -->
        <div class="sidebar-collapsed-face" @click="toggleSidebarPanel">
          <span class="sidebar-vertical-text">业务对象</span>
        </div>
      </aside>
      </div>
    </div>
  </div>
</template>
<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300..700&family=Zen+Maru+Gothic:wght@400;500;700&display=swap');

:global(*) {
  box-sizing: border-box;
}

:global(:root) {
  color-scheme: light;
  /* ── Palette ── */
  --color-bg-deep: #eef2f8;
  --color-bg-mid: #f5f7fb;
  --color-bg-surface: #ffffff;
  /* 亮色卡片表面（纯白）*/
  --color-surface: #ffffff;
  --color-surface-hover: #f7f9fc;
  --color-surface-dim: #f7f9fc;
  --color-surface-raised: #f7f9fc;
  --color-surface-field: #ffffff;
  /* 深色文字压在亮色表面上 */
  --color-text-primary: #16233a;
  --color-text-secondary: #5b6b83;
  --color-text-muted: #8a97ab;
  --color-text-inverse: #ffffff;
  /* Accent — 商务蓝 */
  --color-accent: #1a56db;
  --color-accent-strong: #1444b8;
  --color-accent-soft: rgba(26, 86, 219, 0.10);
  --color-accent-glow: rgba(26, 86, 219, 0.16);
  --color-accent-soft-bg: rgba(26, 86, 219, 0.05);
  /* Warm — 暖棕 */
  --color-warm: #b45309;
  --color-warm-strong: #92400e;
  --color-warm-soft: rgba(180, 83, 9, 0.10);
  --color-warm-glow: rgba(180, 83, 9, 0.12);
  --color-warm-soft-bg: rgba(180, 83, 9, 0.05);
  /* Semantic */
  --color-success: #15803d;
  --color-success-soft: rgba(21, 128, 61, 0.12);
  --color-info: #0369a1;
  --color-info-soft: rgba(3, 105, 161, 0.10);
  --color-danger: #dc2626;
  --color-danger-soft: rgba(220, 38, 38, 0.10);
  /* 边框：浅灰细线 */
  --color-border: #e2e8f0;
  --color-border-light: #eef2f7;
  --color-border-strong: #cbd5e1;
  /* ── Radii ── */
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 24px;
  --radius-xl: 28px;
  --radius-full: 9999px;
  /* ── 阴影（浅色主题：柔和投影）── */
  --shadow-xs: 0 1px 2px rgba(15, 42, 74, 0.06);
  --shadow-sm: 0 2px 8px rgba(15, 42, 74, 0.07);
  --shadow-md: 0 6px 20px rgba(15, 42, 74, 0.08);
  --shadow-lg: 0 12px 32px rgba(15, 42, 74, 0.08);
  --shadow-glow-teal: 0 8px 30px rgba(26, 86, 219, 0.10);
  --shadow-glow-amber: 0 8px 30px rgba(180, 83, 9, 0.08);
  --shadow-inner-glow: inset 0 1px 0 rgba(255, 255, 255, 0.60);
  /* ── Transitions ── */
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-out-back: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --duration-fast: 150ms;
  --duration-base: 250ms;
  --duration-slow: 400ms;
}

:global(body) {
  margin: 0;
  font-family: "Outfit", "Zen Maru Gothic", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--color-bg-deep);
  color: var(--color-text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

:global(button),
:global(input) {
  font: inherit;
}

:global(#app) {
  min-height: 100vh;
}

.app-shell {
  min-height: 100vh;
  padding: 24px;
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, #f8fafd 0%, #eef2f8 100%);
}
/* Subtle grain texture overlay */
.app-shell::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.028;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

.bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  /* 亮色商务主题下隐藏粒子画布；想恢复删掉这行 */
  display: none;
}

.app-shell::after {
  content: "";
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
}
/* Teal orb — top left */
.app-shell::after {
  width: 820px; height: 820px;
  background: radial-gradient(circle, rgba(26, 86, 219, 0.10) 0%, rgba(26, 86, 219, 0.04) 38%, transparent 70%);
  top: -320px; left: -280px;
  animation: orb1 20s ease-in-out infinite;
}
/* Amber orb — bottom right */
.workspace::before {
  content: "";
  position: fixed;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
  width: 640px; height: 640px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.03) 42%, transparent 70%);
  bottom: -280px; right: -220px;
  animation: orb2 24s ease-in-out infinite;
}

@keyframes bgShift {
  0%, 100% { background-position: 0% 0%; }
  25% { background-position: 100% 0%; }
  50% { background-position: 100% 100%; }
  75% { background-position: 0% 100%; }
}
@keyframes orb1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(140px, 90px) scale(1.22); }
  66% { transform: translate(-50px, 150px) scale(0.82); }
}
@keyframes orb2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-110px, -70px) scale(1.18); }
  66% { transform: translate(70px, -130px) scale(0.88); }
}

/* 整页横向二分：左侧 1/3 数字人，右侧 2/3 现有前端工程 */
.app-layout {
  display: flex;
  gap: 22px;
  align-items: stretch;
  position: relative;
  z-index: 1;
}

.workspace {
  flex: 1;
  min-width: 0;
  width: auto;
  margin: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 22px;
  position: relative;
  z-index: 1;
}

/* ── 数字人悬浮窗（见下方 .dh-widget）── ──────────────────────────────────────────── */
.dh-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-muted);
  flex-shrink: 0;
}
.dh-dot-ready { background: var(--color-success); }
.dh-dot-loading { background: var(--color-warm); animation: dhPulse 1.2s ease-in-out infinite; }
.dh-dot-error { background: var(--color-danger); }
@keyframes dhPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(0.82); }
}

.dh-stage {
  flex: 1;
  min-height: 0;
  padding: 16px;
  display: flex;
}
.dh-stage-inner {
  position: relative;
  flex: 1;
  min-height: 0;
  min-width: 0;
  border-radius: var(--radius-md);
  overflow: hidden;
}
.dh-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, #eef4ff, #dce7fa);
  overflow: hidden;
}

/* 占位/加载/错误内容覆盖在常驻容器之上 */
.dh-overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.dh-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  text-align: center;
  border-radius: var(--radius-md);
  background: var(--color-accent-soft-bg);
  border: 1px dashed var(--color-border-strong);
}
.dh-placeholder-title {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-secondary);
}
.dh-placeholder-sub {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-text-muted);
}
.dh-placeholder-icon {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 500;
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.dh-placeholder-icon-idle {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}
.dh-placeholder-error { border-style: solid; border-color: var(--color-danger); }

.dh-spinner {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-accent);
  animation: dh-spin 0.8s linear infinite;
}
@keyframes dh-spin { to { transform: rotate(360deg); } }

.dh-progress {
  width: 100%;
  max-width: 260px;
  height: 5px;
  border-radius: 3px;
  background: var(--color-border-light);
  overflow: hidden;
}
.dh-progress-bar {
  height: 100%;
  border-radius: 3px;
  background: var(--color-accent);
  transition: width 0.3s var(--ease-out-expo);
}

.dh-actions {
  padding: 0 16px 16px;
  flex-shrink: 0;
}
.dh-button {
  width: 100%;
  min-height: 42px;
  padding: 10px 16px;
  font-size: 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-accent);
  background: var(--color-accent-soft);
  color: var(--color-accent-strong);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out-expo);
}
.dh-button:hover:not(:disabled) {
  background: var(--color-accent);
  color: #ffffff;
}
.dh-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
  border-color: var(--color-border-strong);
  background: var(--color-border-light);
  color: var(--color-text-muted);
}
.dh-button-danger {
  border-color: var(--color-danger);
  background: transparent;
  color: var(--color-danger);
}
.dh-button-danger:hover:not(:disabled) {
  background: var(--color-danger-soft);
}

/* ── 数字人悬浮窗（挂在聊天卡片内部，只能在这张卡片里活动）──────────── */
.dh-widget {
  position: absolute;
  left: 24px;
  bottom: 104px;
  width: 176px;
  height: 292px;
  z-index: 40;
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-md);
}
.dh-widget:hover {
  box-shadow: var(--shadow-lg), 0 0 0 2px rgba(26, 86, 219, 0.16);
}
.dh-widget.animating {
  transition: width 240ms cubic-bezier(0.2, 0.8, 0.2, 1),
              height 240ms cubic-bezier(0.2, 0.8, 0.2, 1),
              border-radius 240ms ease,
              box-shadow var(--duration-base) var(--ease-in-out);
}

.dh-widget-bar {
  height: 30px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 6px 0 10px;
  background: var(--color-accent-soft-bg);
  border-bottom: 1px solid var(--color-border-light);
  cursor: grab;
  user-select: none;
  touch-action: none;
}
.dh-widget-bar:active { cursor: grabbing; }
.dh-widget-title {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dh-widget-grip {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-accent);
  letter-spacing: 1px;
  padding: 2px 4px;
  border-radius: 6px;
}
.dh-widget-collapse {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  transition: background var(--duration-fast) ease, color var(--duration-fast) ease;
}
.dh-widget-collapse:hover {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

/* 悬浮窗内的舞台与按钮：把大面板时的尺寸压小 */
.dh-widget .dh-stage { padding: 0; }
.dh-widget .dh-stage-inner { border-radius: 0; }
.dh-widget .dh-actions {
  padding: 7px 8px 8px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-surface-raised);
}
.dh-widget .dh-button {
  min-height: 30px;
  padding: 5px 8px;
  font-size: 11px;
  border-radius: 8px;
}
.dh-widget .dh-placeholder { gap: 6px; padding: 10px; }
.dh-widget .dh-placeholder-title { font-size: 12px; }
.dh-widget .dh-placeholder-sub { font-size: 10px; line-height: 1.5; }
.dh-widget .dh-placeholder-icon { width: 34px; height: 34px; font-size: 14px; }

.dh-widget-resize {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 16px;
  height: 16px;
  z-index: 4;
  cursor: nwse-resize;
  touch-action: none;
  background: linear-gradient(135deg, transparent 45%, rgba(26, 86, 219, 0.45) 45%, rgba(26, 86, 219, 0.45) 60%, transparent 60%,
                                      transparent 72%, rgba(26, 86, 219, 0.45) 72%, rgba(26, 86, 219, 0.45) 87%, transparent 87%);
}

/* 收起态：变成贴在卡片右侧的小圆圈 */
.dh-widget.collapsed { border-radius: 50%; }
.dh-widget.collapsed .dh-widget-bar,
.dh-widget.collapsed .dh-stage,
.dh-widget.collapsed .dh-actions,
.dh-widget.collapsed .dh-widget-resize { display: none; }
.dh-widget-circle {
  display: none;
  position: relative;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  cursor: grab;
  touch-action: none;
  color: var(--color-accent);
  background: radial-gradient(circle at 38% 30%, #f4f8ff, #d7e4ff 74%);
}
.dh-widget.collapsed .dh-widget-circle { display: flex; }
.dh-widget-circle:active { cursor: grabbing; }
.dh-widget-circle-dot {
  position: absolute;
  right: 5px;
  bottom: 5px;
  width: 9px;
  height: 9px;
  border: 2px solid #ffffff;
}
.chat-card.boundary-hit {
  box-shadow: var(--shadow-lg), inset 0 0 0 2px rgba(26, 86, 219, 0.45);
}

/* ── 业务对象面板：左侧中间的收起按钮 + 收起态竖条 ────────────────────── */
.biz-edge-btn {
  position: absolute;
  left: -21px;
  top: 50%;
  transform: translateY(-50%);
  width: 22px;
  height: 52px;
  padding: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  border-right: none;
  border-radius: 10px 0 0 10px;
  background: #ffffff;
  color: var(--color-accent);
  box-shadow: -4px 0 12px rgba(15, 42, 74, 0.08);
  cursor: pointer;
  transition: background var(--duration-fast) ease, color var(--duration-fast) ease, border-color var(--duration-fast) ease;
}
.biz-edge-btn:hover {
  background: var(--color-accent);
  color: #ffffff;
  border-color: var(--color-accent);
}
.biz-edge-btn svg { transition: transform 260ms ease; }
.sidebar.collapsed .biz-edge-btn svg { transform: rotate(180deg); }

.sidebar.collapsed {
  width: 58px;
  padding: 16px 8px;
  align-items: center;
}
.sidebar.collapsed > *:not(.sidebar-collapsed-face):not(.biz-edge-btn) { display: none; }
.sidebar-collapsed-face { display: none; }
.sidebar.collapsed .sidebar-collapsed-face {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  cursor: pointer;
  user-select: none;
}
.sidebar-vertical-text {
  writing-mode: vertical-rl;
  text-orientation: upright;
  letter-spacing: 4px;
  font-size: 13px;
  font-weight: 700;
  color: #12263f;
  white-space: nowrap;
}

.chat-card,
.sidebar {
  min-height: calc(100vh - 48px);
  height: calc(100vh - 48px);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: border-color var(--duration-slow) var(--ease-in-out), box-shadow var(--duration-slow) var(--ease-in-out);
}
.chat-card {
  position: relative;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-glow-teal), var(--shadow-lg), var(--shadow-inner-glow);
}
.chat-card:hover {
  border-color: rgba(26, 86, 219, 0.22);
}
.sidebar {
  position: relative;
  width: 370px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-glow-amber), var(--shadow-lg), var(--shadow-inner-glow);
  transition: width 280ms cubic-bezier(0.2, 0.8, 0.2, 1), padding 280ms ease,
              border-color var(--duration-slow) var(--ease-in-out),
              box-shadow var(--duration-slow) var(--ease-in-out);
}
.sidebar:hover {
  border-color: rgba(26, 86, 219, 0.22);
}

.chat-header,
.sidebar-header {
  padding: 24px 24px 16px;
  border-bottom: 1px solid var(--color-border-light);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.chat-header h1,
.sidebar-header h2 {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: #12263f;
  padding-left: 12px;
  border-left: 4px solid var(--color-accent);
}

.sidebar-header h2 {
  font-size: 22px;
}

.chat-header p,
.sidebar-header p {
  margin: 10px 0 0;
  color: var(--color-text-secondary);
}

/* 客服信息 */
.service-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.service-avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.service-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
  padding: 3px;
  background: conic-gradient(var(--color-success), var(--color-accent), var(--color-warm), var(--color-success));
  animation: avatarSpin 4s linear infinite;
  box-shadow: 0 0 20px var(--color-accent-glow), 0 4px 12px var(--color-success-soft);
}
@keyframes avatarSpin {
  to { transform: rotate(360deg); }
}

.status-indicator {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 14px;
  height: 14px;
  background: var(--color-success);
  border: 3px solid #ffffff;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

.service-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.service-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.service-status {
  font-size: 12px;
  color: var(--color-success);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}

.service-status::before {
  content: '';
  width: 6px;
  height: 6px;
  background: var(--color-success);
  border-radius: 50%;
}

.clear-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out-expo);
  white-space: nowrap;
}
.clear-button:hover {
  background: rgba(251, 113, 133, 0.10);
  border-color: var(--color-danger);
  color: var(--color-danger);
  transform: translateY(-1px);
  box-shadow: 0 4px 18px var(--color-danger-soft);
}

.controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border-light);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field span {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
}

.field-row {
  display: flex;
  gap: 12px;
}

.field input,
.composer input {
  width: 100%;
  min-width: 0;
  min-height: 46px;
  padding: 11px 14px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface-field);
  color: var(--color-text-primary);
  font-size: 15px;
  line-height: 1.4;
  transition: border-color var(--duration-fast) var(--ease-in-out), box-shadow var(--duration-fast) var(--ease-in-out);
}
.field input::placeholder,
.composer input::placeholder {
  color: var(--color-text-muted);
}
.field input:focus,
.composer input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft);
}

.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Turn 卡片样式 */
.turn-card {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: all var(--duration-base) var(--ease-out-expo);
  position: relative;
  overflow: hidden;
  animation: msgEnter 0.4s var(--ease-out-back) both;
}
@keyframes msgEnter {
  from { opacity: 0; transform: translateY(24px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.turn-card::before {
  content: "";
  position: absolute;
  top: 0; left: -100%;
  width: 100%; height: 100%;
  background: linear-gradient(105deg, transparent 40%, rgba(26, 86, 219, 0.06) 50%, transparent 60%);
  transition: left 0.5s ease;
  pointer-events: none;
  z-index: 2;
}
.turn-card:hover::before {
  left: 100%;
}
.turn-card:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-md), 0 0 40px rgba(26, 86, 219, 0.08);
  transform: translateY(-2px);
}

.turn-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--color-border);
}

.turn-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  background: linear-gradient(135deg, var(--color-accent), var(--color-accent-strong));
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 12px var(--color-accent-glow);
}

.turn-label {
  font-size: 12px;
  color: var(--color-text-muted);
  font-weight: 500;
}

.turn-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  font-weight: 600;
}

/* 头像样式 */
.avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #e5e7eb;
  background: #f3f4f6;
  transition: all var(--duration-base) var(--ease-out-expo);
}

.user-avatar .avatar {
  border: 3px solid transparent;
  background: linear-gradient(#ffffff, #ffffff) padding-box,
              linear-gradient(135deg, var(--color-info), var(--color-accent)) border-box;
  box-shadow: 0 2px 14px var(--color-info-soft);
}

.service-avatar .avatar {
  border-color: var(--color-success);
  box-shadow: 0 2px 10px var(--color-success-soft);
}

.status-dot {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  background: var(--color-success);
  border: 2px solid #ffffff;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.65;
    transform: scale(1.12);
  }
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.agent-label {
  font-size: 12px;
  color: var(--color-text-muted);
  font-weight: 500;
}

.user-section .agent-name {
  color: var(--color-info);
}

.bot-section .agent-name {
  color: var(--color-success);
}

.role-icon {
  font-size: 16px;
}

.role-label {
  color: var(--color-text-secondary);
}

.user-section .role-label {
  color: var(--color-info);
}

.bot-section .role-label {
  color: var(--color-success);
}

.turn-bubble {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  max-width: 100%;
}

.user-bubble {
  background: linear-gradient(135deg, var(--color-accent), var(--color-accent-strong));
  border: 1px solid transparent;
  color: #ffffff;
  box-shadow: 0 4px 18px var(--color-accent-glow);
  margin-left: auto;
  max-width: 85%;
}

.bot-bubble {
  background: var(--color-surface-field);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
  box-shadow: var(--shadow-xs);
}

.bot-messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.turn-bubble p {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.user-bubble p {
  color: #ffffff;
}

/* 历史消息分隔线 */
.history-divider {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  color: var(--color-text-muted);
  font-size: 13px;
  padding: 8px 0;
}

.history-divider::before,
.history-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--color-border-strong);
}

.history-divider span {
  padding: 6px 14px;
  border-radius: var(--radius-full);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  font-size: 12px;
}

.welcome {
  flex-shrink: 0;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.welcome-card {
  position: relative;
  max-width: 480px;
  width: 100%;
  padding: 44px 40px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  text-align: center;
  box-shadow: var(--shadow-glow-teal), var(--shadow-lg);
  overflow: hidden;
  animation: welcomeFloat 0.6s var(--ease-out-back);
}
@keyframes welcomeFloat {
  from { opacity: 0; transform: translateY(36px) scale(0.94); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.welcome-glow {
  position: absolute;
  top: -100px; left: 50%; transform: translateX(-50%);
  width: 350px; height: 350px;
  background: radial-gradient(circle, rgba(26, 86, 219, 0.10) 0%, rgba(26, 86, 219, 0.03) 45%, transparent 70%);
  pointer-events: none;
}
.welcome-avatar-wrapper {
  position: relative;
  display: inline-block;
  margin-bottom: 20px;
}
.welcome-avatar {
  width: 88px; height: 88px;
  border-radius: 50%;
  padding: 4px;
  background: conic-gradient(var(--color-success), var(--color-accent), var(--color-warm), var(--color-success));
  animation: avatarSpin 4s linear infinite;
  box-shadow: 0 0 36px var(--color-accent-glow);
}
.welcome-status-pulse {
  position: absolute;
  bottom: 6px; right: 6px;
  width: 18px; height: 18px;
  background: var(--color-success);
  border: 3px solid var(--color-bg-mid);
  border-radius: 50%;
  animation: pulse 2s infinite;
  box-shadow: 0 0 16px rgba(21, 128, 61, 0.35);
}
.welcome-greeting {
  margin: 0 0 8px;
  font-size: 26px;
  font-weight: 700;
  background: linear-gradient(135deg, #e8f0ff, var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.welcome-subtitle {
  margin: 0 0 28px;
  color: var(--color-text-secondary);
  font-size: 15px;
}
.welcome-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-bottom: 28px;
}
.welcome-chip {
  padding: 10px 20px;
  border: 1px solid rgba(26, 86, 219, 0.18);
  border-radius: var(--radius-full);
  background: var(--color-accent-soft-bg);
  color: var(--color-accent);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out-expo);
}
.welcome-chip:hover:not(:disabled) {
  background: var(--color-accent-soft);
  border-color: var(--color-accent);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px var(--color-accent-glow);
}
.welcome-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.welcome-features {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.sidebar-empty {
  margin: auto;
  max-width: 420px;
  color: var(--color-text-muted);
  text-align: center;
  line-height: 1.7;
}

.typing-indicator {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 0 20px;
  animation: msgEnter 0.3s var(--ease-out-expo);
}
.avatar-small {
  width: 34px; height: 34px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--color-success);
  box-shadow: 0 0 12px rgba(21, 128, 61, 0.25);
}
.typing-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: 20px 20px 20px 6px;
  box-shadow: var(--shadow-sm);
}
.typing-dots {
  display: flex;
  gap: 4px;
  align-items: center;
}
.typing-dots span {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: dotBounce 1.2s ease-in-out infinite;
}
.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
  30% { transform: translateY(-8px); opacity: 1; }
}
.typing-label {
  font-size: 13px;
  color: var(--color-text-muted);
}

.object-card-price {
  font-size: 15px;
  font-weight: 600;
}

/* ── 状态徽章 ────────────────────────────────────────────── */
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.status-warning {
  background: var(--color-warm-soft);
  color: var(--color-warm-strong);
  border: 1px solid rgba(180, 83, 9, 0.28);
}
.status-info {
  background: var(--color-info-soft);
  color: var(--color-info);
  border: 1px solid rgba(3, 105, 161, 0.28);
}
.status-success {
  background: var(--color-success-soft);
  color: var(--color-success);
  border: 1px solid rgba(21, 128, 61, 0.28);
}
.status-muted {
  background: rgba(138, 151, 171, 0.18);
  color: var(--color-text-muted);
  border: 1px solid rgba(138, 151, 171, 0.28);
}
.status-danger {
  background: var(--color-danger-soft);
  color: var(--color-danger);
  border: 1px solid rgba(220, 38, 38, 0.28);
}

/* ── 商品图片（侧边栏） ────────────────────────────────────── */
.card-image-wrapper {
  width: 100%;
  height: 140px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-surface-field);
  border: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform var(--duration-base) var(--ease-out-expo);
}
.sidebar-card:hover .card-image {
  transform: scale(1.05);
}
.card-image-placeholder {
  font-size: 40px;
  opacity: 0.5;
}

/* ── 对象卡片图片（聊天区） ─────────────────────────────────── */
.object-card-image {
  width: 100%;
  height: 150px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
  border: 1px solid var(--color-border-light);
  background: var(--color-surface-field);
}

/* Turn 卡片中的对象卡片样式调整 */
.turn-bubble .object-card {
  min-width: 200px;
}

.user-bubble .object-card-badge {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

.composer button,
.secondary-button,
.tab-button {
  min-height: 42px;
  padding: 9px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text-primary);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
  transition:
    transform var(--duration-fast) var(--ease-out-expo),
    box-shadow var(--duration-fast) var(--ease-out-expo),
    background var(--duration-fast) var(--ease-in-out),
    border-color var(--duration-fast) var(--ease-in-out);
}

.composer button:hover:not(:disabled),
.secondary-button:hover:not(:disabled),
.tab-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.composer button:active:not(:disabled),
.secondary-button:active:not(:disabled),
.tab-button:active:not(:disabled) {
  transform: translateY(0);
}

.composer button:disabled,
.secondary-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.error-message,
.sidebar-error {
  margin: 0;
  padding: 0 24px 14px;
  color: var(--color-danger);
  font-size: 13px;
  font-weight: 500;
}

.composer {
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-surface-dim);
}

.composer button {
  min-width: 96px;
  padding-inline: 20px;
  background: linear-gradient(135deg, var(--color-accent), var(--color-accent-strong));
  border-color: transparent;
  color: #ffffff;
  box-shadow: 0 14px 28px var(--color-accent-glow);
}
.composer button:hover:not(:disabled) {
  box-shadow: 0 18px 36px var(--color-accent-glow);
  transform: translateY(-2px);
}

.sidebar {
  display: flex;
  flex-direction: column;
}

.tabs {
  display: flex;
  gap: 8px;
  padding: 16px 24px 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.tab-button {
  min-width: 80px;
}

.tab-button.active {
  background: linear-gradient(135deg, var(--color-accent-strong), var(--color-accent));
  border-color: transparent;
  color: #ffffff;
  box-shadow: 0 4px 14px var(--color-accent-glow);
}

.sidebar-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sidebar-card {
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: all var(--duration-base) var(--ease-out-expo);
}
.sidebar-card:hover {
  background: var(--color-surface-hover);
  border-color: rgba(26, 86, 219, 0.22);
  transform: translateY(-3px);
  box-shadow: var(--shadow-md), var(--shadow-glow-amber);
}

.card-top {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: flex-start;
}

.card-title {
  font-size: 15px;
  line-height: 1.5;
  color: var(--color-text-primary);
  font-weight: 600;
}

.card-amount {
  flex-shrink: 0;
  color: var(--color-warm-strong);
  font-weight: 700;
}

.card-meta {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.bot-text-row { display: flex; align-items: flex-start; gap: 8px; }
.bot-text-row p { flex: 1; margin: 0; }
.bot-actions {
  display: flex; gap: 6px; flex-shrink: 0; align-items: center;
}
.tts-button, .copy-button {
  flex-shrink: 0; width: 32px; height: 32px; padding: 0;
  border: 1px solid var(--color-border-light); border-radius: 8px;
  background: var(--color-surface); cursor: pointer;
  font-size: 14px; display: inline-flex; align-items: center; justify-content: center;
  transition: all var(--duration-base) var(--ease-out-expo); color: var(--color-text-muted);
}
.tts-button:hover:not(:disabled), .copy-button:hover:not(:disabled) {
  background: var(--color-accent-soft); border-color: var(--color-accent); color: var(--color-accent-strong);
  transform: scale(1.1);
}
.tts-button:disabled, .copy-button:disabled { cursor: not-allowed; opacity: 0.65; }
.tts-button.tts-playing { background: var(--color-accent-soft); border-color: var(--color-accent); color: var(--color-accent-strong); }
.tts-bars {
  display: inline-flex; align-items: flex-end; gap: 3px; height: 16px;
}
.tts-bars span {
  width: 3px;
  background: var(--color-accent);
  border-radius: 2px;
  animation: barBounce 0.6s ease-in-out infinite;
}
.tts-bars span:nth-child(1) { height: 8px; animation-delay: 0s; }
.tts-bars span:nth-child(2) { height: 14px; animation-delay: 0.15s; }
.tts-bars span:nth-child(3) { height: 10px; animation-delay: 0.3s; }
@keyframes barBounce {
  0%, 100% { transform: scaleY(0.5); }
  50% { transform: scaleY(1); }
}
.tts-spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--color-accent-soft); border-top-color: var(--color-accent);
  border-radius: 50%; animation: tts-spin 0.6s linear infinite;
}
@keyframes tts-spin { to { transform: rotate(360deg); } }
.copy-button.copy-done {
  background: var(--color-success-soft);
  border-color: var(--color-success);
  color: var(--color-success);
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}
.suggestion-chip {
  padding: 6px 14px;
  border: 1px solid rgba(26, 86, 219, 0.18);
  border-radius: var(--radius-full);
  background: var(--color-accent-soft-bg);
  color: var(--color-accent);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out-expo);
}
.suggestion-chip:hover:not(:disabled) {
  background: var(--color-accent-soft);
  border-color: var(--color-accent);
  transform: translateY(-1px);
}
.suggestion-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.full-width {
  width: 100%;
}

.sidebar .secondary-button.full-width {
  min-height: 42px;
}

.sidebar-empty {
  margin: auto;
  max-width: 420px;
  color: var(--color-text-muted);
  text-align: center;
  line-height: 1.7;
}

/* Turn 卡片中的对象卡片样式调整 */
.turn-bubble .object-card {
  min-width: 200px;
}

.user-bubble .object-card-badge {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

@media (max-width: 1180px) {
  .app-layout {
    flex-direction: column;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .chat-header {
    flex-direction: column;
  }

  .sidebar {
    min-height: auto;
    height: auto;
  }
}

@media (max-width: 720px) {
  .app-shell {
    padding: 0;
  }

  .workspace {
    gap: 0;
  }

  .chat-card,
  .sidebar {
    min-height: auto;
    height: auto;
    border-radius: 0;
    border-left: none;
    border-right: none;
  }

  .chat-card {
    min-height: 100vh;
  }

  .message {
    max-width: 100%;
  }

  .composer,
  .field-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
