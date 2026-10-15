<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import XmovAvatar from '@xmov/avatar'
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

// 客服数字人配置
const customerService = {
  name: '小宝',
  title: '金牌客服',
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
  '待发货': 'badge-warn',
  '待揽收': 'badge-warn',
  '运输中': 'badge-info',
  '派送中': 'badge-info',
  '已完成': 'badge-online',
  '已签收': 'badge-online',
  '已取消': 'badge',
  '退款中': 'badge-warn',
  '已退款': 'badge',
}

function getStatusClass(status) {
  return ORDER_STATUS_CLASS[status] || 'badge'
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

// 收起：缩成 56px 的小方块，贴到卡片右侧
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
  <div class="app">
    <!-- ================= 顶栏 ================= -->
    <header class="app-top">
      <div class="brand">
        <svg class="mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
          <rect x="12" y="12" width="8" height="8" rx="2"/>
          <rect x="4" y="4" width="4" height="4" rx="1"/>
          <rect x="24" y="4" width="4" height="4" rx="1"/>
          <rect x="4" y="24" width="4" height="4" rx="1"/>
          <rect x="24" y="24" width="4" height="4" rx="1"/>
        </svg>
        <h1>智能应答台</h1>
        <span class="sub">E-COMMERCE SUPPORT CONSOLE</span>
      </div>
      <nav aria-label="主导航">
        <a href="#thread" aria-current="page">对话台</a>
        <a href="#objects">业务对象</a>
      </nav>
      <div class="top-actions">
        <span class="badge badge-online"><span class="status-led" aria-hidden="true"></span>:18082 ONLINE</span>
        <button type="button" class="btn btn-ghost" @click="resetConversation">新对话</button>
        <button type="button" class="btn btn-ghost" id="themeBtn" aria-label="切换明暗主题">
          <svg class="ic ic-sm" aria-hidden="true" focusable="false"><use href="#i-chev"></use></svg>主题
        </button>
      </div>
    </header>

    <!-- ================= 主体 ================= -->
    <div class="app-body has-aside">
      <!-- ---------- 对话主区 ---------- -->
      <main ref="chatCardEl" class="pane" id="thread">
        <div class="thread">

          <!-- 会话声明带：sender_id 控件 -->
          <div class="ribbon is-inner">
            <label class="sess-field">
              <span class="mono-note">会话</span>
              <input v-model="senderId" type="text" class="input sess-input" placeholder="u1001" />
            </label>
            <span class="mono-note">对象 <strong>{{ orders.length }}</strong> 订单 / <strong>{{ products.length }}</strong> 商品</span>
            <button type="button" class="btn btn-sm" :disabled="isLoadingSidebar" @click="fetchSidebarData">
              {{ isLoadingSidebar ? '加载中…' : '刷新对象列表' }}
            </button>
          </div>

          <section ref="messagesContainer" class="messages">
            <!-- 空态 -->
            <div v-if="turns.length === 0" class="empty welcome">
              <h4>Hi，我是 {{ customerService.name }}</h4>
              <p>你的专属电商客服，随时为你服务。点一个常见问题直接开问：</p>
              <div class="chip-row welcome-chips">
                <button
                  v-for="chip in ['我要退款', '查订单状态', '商品推荐', '退换货政策']"
                  :key="chip"
                  type="button"
                  class="btn btn-ghost"
                  :disabled="isSending"
                  @click="sendQuickText(chip)"
                >{{ chip }}</button>
              </div>
            </div>

            <!-- Turn 结构展示 -->
            <template v-for="(item, index) in turns" :key="item.id || index">
              <!-- 历史消息分隔线 -->
              <div v-if="item.type === 'divider'" class="history-divider">
                <span class="mono-note">{{ item.text }}</span>
              </div>

              <article v-else class="turn">
                <div class="turn-hd">
                  <span class="turn-idx">TURN {{ String(item.index).padStart(2, '0') }}</span>
                  <span class="turn-who">买家 → 应答台</span>
                  <span class="badge">{{ customerService.name }} · {{ customerService.title }}</span>
                </div>

                <!-- 用户消息 -->
                <div v-if="item.userMessage" class="msg msg-user">
                  <div class="msg-avatar me" aria-hidden="true">
                    <img :src="userProfile.avatar" alt="" />
                  </div>
                  <div class="msg-body">
                    <template v-if="item.userMessage.type === 'object'">
                      <article class="obj msg-obj">
                        <div class="obj-cover obj-cover-media">
                          <img
                            v-if="item.userMessage.payload.cover_url"
                            :src="item.userMessage.payload.cover_url"
                            :alt="getObjectTitle(item.userMessage)"
                            @error="$event.target.style.display='none'"
                          />
                          <template v-else>
                            <svg class="ic" aria-hidden="true" focusable="false"><use href="#i-doc"></use></svg>
                            <span>对象封面占位</span>
                          </template>
                        </div>
                        <div class="obj-body">
                          <div class="obj-title">{{ getObjectTitle(item.userMessage) }}</div>
                          <div class="obj-price">{{ getObjectAmount(item.userMessage) }}</div>
                          <div class="obj-meta">
                            <span class="no">{{ getObjectIdentifier(item.userMessage) }}</span>
                            <span v-if="item.userMessage.payload.status" class="badge" :class="getStatusClass(item.userMessage.payload.status)">{{ item.userMessage.payload.status }}</span>
                            <span v-else class="badge">{{ item.userMessage.objectType === 'order' ? '订单对象' : '商品对象' }}</span>
                          </div>
                        </div>
                      </article>
                    </template>
                    <template v-else>
                      <p>{{ item.userMessage.text }}</p>
                    </template>
                  </div>
                </div>

                <!-- 客服回复 -->
                <div
                  v-for="(botMsg, msgIndex) in item.botMessages"
                  :key="msgIndex"
                  class="msg"
                >
                  <div class="msg-avatar bot" aria-hidden="true">
                    <svg class="ic ic-lg" focusable="false"><use href="#i-agent"></use></svg>
                  </div>
                  <div class="msg-body">
                    <template v-if="botMsg.type === 'object'">
                      <article class="obj msg-obj">
                        <div class="obj-cover obj-cover-media">
                          <img
                            v-if="botMsg.payload.cover_url"
                            :src="botMsg.payload.cover_url"
                            :alt="getObjectTitle(botMsg)"
                            @error="$event.target.style.display='none'"
                          />
                          <template v-else>
                            <svg class="ic" aria-hidden="true" focusable="false"><use href="#i-doc"></use></svg>
                            <span>对象封面占位</span>
                          </template>
                        </div>
                        <div class="obj-body">
                          <div class="obj-title">{{ getObjectTitle(botMsg) }}</div>
                          <div class="obj-price">{{ getObjectAmount(botMsg) }}</div>
                          <div class="obj-meta">
                            <span class="no">{{ getObjectIdentifier(botMsg) }}</span>
                            <span v-if="botMsg.payload.status" class="badge" :class="getStatusClass(botMsg.payload.status)">{{ botMsg.payload.status }}</span>
                            <span v-else class="badge">{{ botMsg.objectType === 'order' ? '订单对象' : '商品对象' }}</span>
                          </div>
                        </div>
                      </article>
                    </template>
                    <template v-else>
                      <div class="bot-text-row">
                        <p>{{ botMsg.text }}</p>
                        <div class="bot-actions">
                          <button type="button" class="icon-btn"
                            :class="{ 'is-active': ttsState[botMsg.id] === 'playing' }"
                            :disabled="ttsState[botMsg.id] === 'loading'"
                            :title="ttsState[botMsg.id] === 'playing' ? '正在播放…' : '语音播报'"
                            @click.stop="playTts(botMsg)">
                            <span v-if="ttsState[botMsg.id] === 'loading'" class="status-led is-busy" aria-hidden="true"></span>
                            <span v-else-if="ttsState[botMsg.id] === 'playing'" class="tts-bars" aria-hidden="true">
                              <span></span><span></span><span></span>
                            </span>
                            <svg v-else class="ic ic-sm" aria-hidden="true" focusable="false"><use href="#i-agent"></use></svg>
                          </button>
                          <button type="button" class="icon-btn"
                            :class="{ 'copy-done': copyState[botMsg.id] }"
                            :title="copyState[botMsg.id] ? '已复制' : '复制文字'"
                            @click.stop="copyBotText(botMsg)">
                            <svg v-if="copyState[botMsg.id]" class="ic ic-sm" aria-hidden="true" focusable="false"><use href="#i-check"></use></svg>
                            <svg v-else class="ic ic-sm" aria-hidden="true" focusable="false"><use href="#i-copy"></use></svg>
                          </button>
                        </div>
                      </div>
                    </template>
                    <div v-if="botMsg.suggestions && botMsg.suggestions.length > 0" class="chip-row">
                      <button
                        v-for="sug in botMsg.suggestions"
                        :key="sug"
                        type="button"
                        class="btn btn-ghost btn-sm"
                        :disabled="isSending"
                        @click.stop="sendSuggestion(sug)"
                      >{{ sug }}</button>
                    </div>
                  </div>
                </div>
              </article>
            </template>

            <!-- 输入中指示 -->
            <div v-if="isSending" class="msg typing">
              <div class="msg-avatar bot" aria-hidden="true">
                <svg class="ic ic-lg" focusable="false"><use href="#i-agent"></use></svg>
              </div>
              <div class="msg-body">
                <div class="typing-bubble">
                  <span class="typing-dots" aria-hidden="true">
                    <span></span><span></span><span></span>
                  </span>
                  <span class="typing-label">{{ customerService.name }} 正在输入…</span>
                </div>
              </div>
            </div>

            <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
          </section>

          <!-- ---------- 输入区 ---------- -->
          <div class="composer-bar">
            <form class="composer" :class="{ 'is-off': isSending }" @submit.prevent="sendTextMessage">
              <input
                v-model="draftMessage"
                type="text"
                placeholder="请输入咨询内容…"
                :disabled="isSending"
              />
              <button type="submit" class="btn btn-primary" :disabled="isSending || !draftMessage.trim()">
                {{ isSending ? '发送中…' : '发送' }}
              </button>
            </form>
          </div>

          <!-- ============ 数字人悬浮窗（只能在对话主区内活动）============ -->
          <div ref="dhWidgetEl" class="dh-widget">
            <div class="dh-widget-bar" title="按住这里拖动数字人" @pointerdown="onDhPointerDown">
              <span class="dh-status-dot" :class="`dh-dot-${dhStatus}`"></span>
              <span class="dh-widget-title">{{ DH_STATUS_TEXT[dhStatus] }}</span>
              <span class="dh-widget-grip" aria-hidden="true">⠿</span>
              <button
                type="button"
                class="dh-widget-collapse"
                title="收起为小方块"
                @pointerdown="stopPointerEvent"
                @click.stop="collapseDhWidget"
              >
                <svg class="ic ic-sm" aria-hidden="true" focusable="false"><use href="#i-chev"></use></svg>
              </button>
            </div>

            <div class="dh-stage">
              <div class="dh-stage-inner">
                <!-- 容器常驻 DOM：SDK init 期间就必须能找到它 -->
                <div id="digital-human-sdk" ref="dhContainer" class="dh-canvas"></div>

                <div v-if="dhStatus === 'loading'" class="dh-overlay dh-placeholder dh-placeholder-loading">
                  <span class="status-led is-busy" aria-hidden="true"></span>
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

            <!-- 收起后的小方块：可拖、点一下展开 -->
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
      </main>

      <!-- ---------- aside：业务对象面板 ---------- -->
      <aside ref="sidebarEl" class="aside" id="objects">
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

        <div class="aside-stack">
          <div class="panel">
            <div class="panel-head">
              <h3>业务对象</h3>
              <span class="badge">{{ orders.length }} 订单 / {{ products.length }} 商品</span>
            </div>
            <div class="panel-body">
              <div class="tabs" role="tablist" aria-label="业务对象分类">
                <button
                  type="button"
                  class="tab"
                  role="tab"
                  :aria-selected="activeTab === 'orders'"
                  @click="activeTab = 'orders'"
                >订单 <span class="n">{{ orders.length }}</span></button>
                <button
                  type="button"
                  class="tab"
                  role="tab"
                  :aria-selected="activeTab === 'products'"
                  @click="activeTab = 'products'"
                >商品 <span class="n">{{ products.length }}</span></button>
              </div>

              <p v-if="sidebarError" class="sidebar-error">{{ sidebarError }}</p>

              <!-- 订单 Tab -->
              <div v-if="activeTab === 'orders'" class="obj-list">
                <div v-if="!orders.length && !isLoadingSidebar" class="empty obj-empty">
                  <p>暂无订单数据</p>
                </div>

                <article v-for="order in orders" :key="order.order_id" class="obj">
                  <div class="obj-cover obj-cover-media">
                    <img
                      v-if="order.cover_url"
                      :src="order.cover_url"
                      :alt="order.title"
                      @error="$event.target.style.display='none'"
                    />
                    <template v-else>
                      <svg class="ic" aria-hidden="true" focusable="false"><use href="#i-doc"></use></svg>
                      <span>订单封面占位</span>
                    </template>
                  </div>
                  <div class="obj-body">
                    <div class="obj-title">{{ order.title }}</div>
                    <div class="obj-price">{{ formatAmount(order.amount) }}</div>
                    <div class="obj-meta">
                      <span class="no">{{ getObjectIdentifier({ objectType: 'order', payload: order }) }}</span>
                      <span class="badge" :class="getStatusClass(order.status)">{{ order.status }}</span>
                    </div>
                  </div>
                  <div class="obj-foot">
                    <span class="t-mini mono">订单</span>
                    <button type="button" class="btn" :disabled="isSending" @click="sendOrder(order)">发送订单</button>
                  </div>
                </article>
              </div>

              <!-- 商品 Tab -->
              <div v-else class="obj-list">
                <div v-if="!products.length && !isLoadingSidebar" class="empty obj-empty">
                  <p>暂无商品数据</p>
                </div>

                <article v-for="product in products" :key="product.product_id" class="obj">
                  <div class="obj-cover obj-cover-media">
                    <img
                      v-if="product.cover_url"
                      :src="product.cover_url"
                      :alt="product.title"
                      @error="$event.target.style.display='none'"
                    />
                    <template v-else>
                      <svg class="ic" aria-hidden="true" focusable="false"><use href="#i-search"></use></svg>
                      <span>商品主图占位</span>
                    </template>
                  </div>
                  <div class="obj-body">
                    <div class="obj-title">{{ product.title }}</div>
                    <div class="obj-price">{{ formatAmount(product.price) }}</div>
                    <div class="obj-meta">
                      <span class="no">{{ getObjectIdentifier({ objectType: 'product', payload: product }) }}</span>
                    </div>
                  </div>
                  <div class="obj-foot">
                    <span class="t-mini mono">商品</span>
                    <button type="button" class="btn" :disabled="isSending" @click="sendProduct(product)">发送商品</button>
                  </div>
                </article>
              </div>
            </div>
          </div>
        </div>

        <!-- 收起后的窄竖条：点它展开 -->
        <div class="sidebar-collapsed-face" @click="toggleSidebarPanel">
          <span class="sidebar-vertical-text">业务对象</span>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
/* ========================================================================
   消费 design-system.css 的 token 与组件类，不新增任何颜色/圆角/阴影/字体。
   页面级类（.turn/.ribbon/.tab/.obj 等）照 support.html 设计稿移植，
   全部只取 var(--) 值。零阴影（仅 --shadow-card 一级）/ 零渐变 / 零 emoji 图标。
   ======================================================================== */

/* ---- 结构适配：单屏两栏（左对话 / 右业务对象，右栏可收起） ---- */
.app-body.has-aside { grid-template-columns: minmax(0, 1fr) auto; }

.pane {
  position: relative;
  display: flex; flex-direction: column;
  min-height: 0; min-width: 0;
}
.thread {
  flex: 1; min-height: 0;
  width: 100%; max-width: 58rem; margin-inline: auto;
  display: flex; flex-direction: column;
}
.messages {
  flex: 1; min-height: 0; overflow-y: auto;
  padding-block: var(--sp-4) var(--sp-5);
  display: flex; flex-direction: column;
}

/* ---- 顶栏 ---- */
.app-top .brand h1 { font: inherit; letter-spacing: inherit; text-wrap: wrap; }
.top-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }

/* ---- 会话声明带 ---- */
.mono-note { font-family: var(--font-mono); font-size: var(--fs-mini); color: var(--muted); }
.ribbon.is-inner {
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--sp-3) var(--sp-4); flex-wrap: wrap;
  border: 1px solid var(--border); border-radius: var(--radius);
  margin-bottom: var(--sp-4); padding: .625rem var(--sp-3);
  background: var(--surface-subtle);
}
.sess-field { display: flex; align-items: center; gap: var(--sp-2); }
.sess-input { height: 36px; width: 10rem; }

/* ---- 对话线程 ---- */
.turn { padding: var(--sp-5) 0; border-bottom: 1px solid var(--border); }
.turn:first-child { padding-top: 0; }
.turn:last-child { border-bottom: 0; }
.turn-hd {
  display: flex; align-items: center; gap: var(--sp-2);
  flex-wrap: wrap; margin-bottom: var(--sp-3);
}
.turn-idx {
  font-family: var(--font-mono); font-size: var(--fs-mini); font-weight: 700;
  letter-spacing: .1em; color: var(--border-strong);
}
.turn-who { font-family: var(--font-mono); font-size: var(--fs-mini); color: var(--muted); }
.turn .msg + .msg { margin-top: var(--sp-4); }
.chip-row { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-3); }

.msg-avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: var(--radius); }

/* ---- 历史消息分隔线 ---- */
.history-divider {
  display: flex; align-items: center; gap: var(--sp-3);
  margin-block: var(--sp-4); color: var(--faint);
}
.history-divider::before,
.history-divider::after { content: ""; flex: 1; border-top: 1px dashed var(--border-strong); }

/* ---- 空态（欢迎） ---- */
.welcome { margin-block: auto; }
.welcome .chip-row { justify-content: flex-start; }

/* ---- 客服回复操作按钮 ---- */
.bot-text-row { display: flex; align-items: flex-start; gap: var(--sp-2); }
.bot-text-row p { flex: 1; min-width: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.bot-actions { display: flex; gap: var(--sp-1); flex-shrink: 0; }
.icon-btn {
  width: 28px; height: 28px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); color: var(--muted); cursor: pointer;
  transition: background var(--t-2) var(--ease-state),
              border-color var(--t-2) var(--ease-state),
              color var(--t-2) var(--ease-state);
}
.icon-btn:hover:not(:disabled),
.icon-btn.is-active { border-color: var(--accent); color: var(--accent); background: var(--accent-tint); }
.icon-btn:disabled { opacity: .45; pointer-events: none; }
.icon-btn.copy-done { border-color: var(--border-success); color: var(--success); background: var(--success-tint); }
.tts-bars { display: inline-flex; align-items: flex-end; gap: 2px; height: 14px; }
.tts-bars span { width: 3px; background: var(--accent); animation: bar-bounce .6s var(--ease-loop) infinite; }
.tts-bars span:nth-child(1) { height: 8px; }
.tts-bars span:nth-child(2) { height: 14px; animation-delay: .15s; }
.tts-bars span:nth-child(3) { height: 10px; animation-delay: .3s; }
@keyframes bar-bounce {
  0%, 100% { transform: scaleY(.5); }
  50% { transform: scaleY(1); }
}

/* ---- 输入中指示 ---- */
.typing-bubble {
  display: flex; align-items: center; gap: var(--sp-2); width: fit-content;
  background: var(--surface-subtle); border: 1px solid var(--border);
  border-radius: var(--radius); padding: .5rem .875rem;
}
.typing-dots { display: inline-flex; gap: 4px; align-items: center; }
.typing-dots span {
  width: 6px; height: 6px; border-radius: 50%; background: var(--muted);
  animation: dot-bounce 1.2s ease-in-out infinite;
}
.typing-dots span:nth-child(2) { animation-delay: .2s; }
.typing-dots span:nth-child(3) { animation-delay: .4s; }
@keyframes dot-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: .35; }
  30% { transform: translateY(-4px); opacity: 1; }
}
.typing-label { font-size: var(--fs-mini); color: var(--muted); }

/* ---- 错误横幅 ---- */
.error-message {
  margin: var(--sp-3) 0 0; padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--warn); border-left: 2px solid var(--warn);
  border-radius: var(--radius); background: var(--warn-tint);
  color: var(--warn); font-size: var(--fs-meta);
}

/* ---- 输入区 ---- */
.composer-bar {
  flex-shrink: 0;
  margin-top: var(--sp-4); padding-top: var(--sp-4);
  border-top: 1px solid var(--border-strong);
}
.composer input {
  border: 0; background: none; min-width: 0;
  padding: .375rem 0; line-height: 1.7;
}
.composer input:focus { outline: none; }
.composer input::placeholder { color: var(--faint); }
.composer.is-off { border-color: var(--border); background: var(--surface-subtle); }
.composer.is-off input { color: var(--faint); cursor: not-allowed; }
.composer.is-off input::placeholder { color: var(--faint); }

/* ---- aside：业务对象面板 ---- */
.aside {
  position: relative;
  width: 340px;
  display: flex; flex-direction: column;
  transition: width 240ms var(--ease-state);
}
.aside-stack { display: flex; flex-direction: column; gap: var(--sp-4); flex: 1; }
.panel { box-shadow: var(--shadow-card); }

.tabs { display: flex; gap: .25rem; border-bottom: 1px solid var(--border); margin-bottom: var(--sp-4); }
.tab {
  display: inline-flex; align-items: center; justify-content: center; gap: .4em;
  min-height: 44px; padding: .5rem .875rem;
  border: 1px solid transparent; border-bottom: 0;
  border-radius: var(--radius) var(--radius) 0 0;
  background: transparent; color: var(--muted);
  font-family: var(--font-mono); font-size: var(--fs-mini);
  font-weight: 600; letter-spacing: .06em;
  transition: color var(--t-2) var(--ease-state), background-color var(--t-2) var(--ease-state);
}
.tab:hover { color: var(--fg); background: var(--surface-subtle); }
.tab[aria-selected="true"] {
  background: var(--surface); border-color: var(--border);
  color: var(--fg); margin-bottom: -1px;
}
.tab .n { color: var(--faint); }

.sidebar-error { margin: 0 0 var(--sp-3); font-size: var(--fs-mini); color: var(--warn); }

.obj-list { display: flex; flex-direction: column; gap: var(--sp-3); }
.obj-empty { padding: var(--sp-5) var(--sp-4); }

/* 业务对象卡：封面用占位块 / 真实封面图 */
.obj {
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); overflow: hidden;
}
.obj-cover {
  aspect-ratio: 8 / 3;
  display: grid; place-items: center; gap: .25rem; align-content: center;
  background: var(--surface-sunken); border-bottom: 1px solid var(--border);
  color: var(--faint);
  font-family: var(--font-mono); font-size: var(--fs-mini); letter-spacing: .1em;
}
.obj-cover img { width: 100%; height: 100%; object-fit: cover; }
.obj-body { padding: var(--sp-3); display: flex; flex-direction: column; gap: .375rem; }
.obj-title { font-weight: 700; font-size: var(--fs-meta); line-height: 1.5; }
.obj-price {
  font-family: var(--font-mono); font-weight: 700; font-size: var(--fs-h3);
  color: var(--accent); overflow-wrap: anywhere;
}
.obj-meta {
  display: flex; flex-wrap: wrap; gap: .25rem .5rem;
  font-family: var(--font-mono); font-size: var(--fs-mini); color: var(--faint);
}
.obj-meta .no { overflow-wrap: anywhere; }
.obj-foot {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--sp-2); flex-wrap: wrap;
  padding: var(--sp-3); border-top: 1px solid var(--border);
  background: var(--surface-subtle);
}
.msg-obj { max-width: 24rem; margin-top: var(--sp-2); }

/* ---- 右栏收起态 ---- */
.aside.collapsed {
  width: 58px; padding-left: var(--sp-2); padding-right: var(--sp-2);
  align-items: center;
}
.aside.collapsed > *:not(.sidebar-collapsed-face):not(.biz-edge-btn) { display: none; }
.sidebar-collapsed-face { display: none; }
.aside.collapsed .sidebar-collapsed-face {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  width: 100%; height: 100%;
  cursor: pointer; user-select: none;
}
.sidebar-vertical-text {
  writing-mode: vertical-rl; text-orientation: upright;
  letter-spacing: 4px; font-size: var(--fs-mini); font-weight: 700;
  color: var(--fg); white-space: nowrap;
}
.biz-edge-btn {
  position: absolute; left: -21px; top: 50%; transform: translateY(-50%);
  width: 22px; height: 52px; padding: 0; z-index: 5;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-right: 0;
  border-radius: var(--radius) 0 0 var(--radius);
  background: var(--surface); color: var(--accent);
  cursor: pointer;
  transition: background var(--t-2) var(--ease-state),
              color var(--t-2) var(--ease-state),
              border-color var(--t-2) var(--ease-state);
}
.biz-edge-btn:hover {
  background: var(--accent-solid); border-color: var(--accent-solid); color: var(--on-accent);
}
.biz-edge-btn svg { transition: transform var(--t-3) var(--ease-state); }
.aside.collapsed .biz-edge-btn svg { transform: rotate(180deg); }

/* ---- 数字人悬浮窗（挂在对话主区内，只能在这里活动） ---- */
.boundary-hit { outline: 2px solid var(--accent); outline-offset: -2px; }
.dh-widget {
  position: absolute; left: var(--sp-4); bottom: 104px;
  width: 176px; height: 292px; z-index: 40;
  display: flex; flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.dh-widget.animating {
  transition: width 240ms var(--ease-state), height 240ms var(--ease-state);
}
.dh-widget-bar {
  height: 30px; flex-shrink: 0;
  display: flex; align-items: center; gap: 6px;
  padding: 0 6px 0 10px;
  background: var(--surface-subtle);
  border-bottom: 1px solid var(--border);
  cursor: grab; user-select: none; touch-action: none;
}
.dh-widget-bar:active { cursor: grabbing; }
.dh-status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--muted); flex: none;
}
.dh-dot-ready { background: var(--success); }
.dh-dot-loading { background: var(--warn); animation: dh-pulse 1.4s var(--ease-loop) infinite; }
.dh-dot-error { background: var(--fg); }
@keyframes dh-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .45; transform: scale(.82); }
}
.dh-widget-title {
  flex: 1; min-width: 0;
  font-size: var(--fs-mini); color: var(--fg-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.dh-widget-grip { flex: none; color: var(--faint); letter-spacing: 1px; }
.dh-widget-collapse {
  flex: none; width: 20px; height: 20px; padding: 0;
  display: flex; align-items: center; justify-content: center;
  border: 0; border-radius: var(--radius);
  background: transparent; color: var(--muted); cursor: pointer;
  transition: background var(--t-2) var(--ease-state), color var(--t-2) var(--ease-state);
}
.dh-widget-collapse:hover { background: var(--accent-tint); color: var(--accent); }
.dh-stage { flex: 1; min-height: 0; padding: var(--sp-2); display: flex; }
.dh-stage-inner {
  position: relative; flex: 1; min-height: 0; min-width: 0;
  border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden;
}
.dh-canvas {
  position: absolute; inset: 0; width: 100%; height: 100%;
  background: var(--surface-sunken); overflow: hidden;
}
.dh-overlay { position: absolute; inset: 0; z-index: 1; }
.dh-placeholder {
  flex: 1;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: var(--sp-2); padding: var(--sp-3); text-align: center;
  border: 1px dashed var(--border-strong); border-radius: var(--radius);
  background: var(--surface);
}
.dh-placeholder-title { margin: 0; font-size: var(--fs-mini); font-weight: 700; color: var(--fg-secondary); }
.dh-placeholder-sub { margin: 0; font-size: var(--fs-mini); line-height: 1.6; color: var(--muted); }
.dh-placeholder-icon {
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface-subtle); color: var(--accent);
  font-family: var(--font-mono); font-size: var(--fs-meta); font-weight: 700;
}
.dh-placeholder-error { border-style: solid; border-color: var(--warn); }
.dh-progress {
  width: 100%; max-width: 260px; height: 8px;
  border: 1px solid var(--border-strong); border-radius: var(--radius);
  background: var(--surface-sunken); overflow: hidden;
}
.dh-progress-bar {
  height: 100%; background: var(--accent-solid);
  transition: width .3s var(--ease-state);
}
.dh-actions {
  flex-shrink: 0; padding: var(--sp-2);
  border-top: 1px solid var(--border); background: var(--surface-subtle);
}
.dh-button {
  width: 100%; min-height: 32px; padding: var(--sp-1) var(--sp-2);
  font-size: var(--fs-mini); font-weight: 600;
  border: 1px solid var(--border-strong); border-radius: var(--radius);
  background: var(--surface); color: var(--fg); cursor: pointer;
  transition: background var(--t-2) var(--ease-state),
              border-color var(--t-2) var(--ease-state),
              color var(--t-2) var(--ease-state);
}
.dh-button:hover:not(:disabled) { background: var(--surface-subtle); }
.dh-button:disabled { opacity: .45; pointer-events: none; }
.dh-button-danger { border-color: var(--accent-solid); color: var(--accent); }
.dh-widget-resize {
  position: absolute; right: 0; bottom: 0;
  width: 16px; height: 16px; z-index: 4;
  cursor: nwse-resize; touch-action: none;
  background: var(--surface-subtle);
  border-top: 1px solid var(--border); border-left: 1px solid var(--border);
}
.dh-widget.collapsed { border-radius: var(--radius); }
.dh-widget.collapsed .dh-widget-bar,
.dh-widget.collapsed .dh-stage,
.dh-widget.collapsed .dh-actions,
.dh-widget.collapsed .dh-widget-resize { display: none; }
.dh-widget-circle {
  display: none;
  position: relative; width: 100%; height: 100%;
  align-items: center; justify-content: center;
  cursor: grab; touch-action: none;
  color: var(--fg); background: var(--surface);
}
.dh-widget.collapsed .dh-widget-circle { display: flex; }
.dh-widget-circle:active { cursor: grabbing; }
.dh-widget-circle-dot {
  position: absolute; right: 5px; bottom: 5px;
  width: 8px; height: 8px; border: 2px solid var(--bg);
}

/* ---- 响应式 ---- */
@media (max-width: 1023px) {
  .aside { width: 300px; }
}
@media (max-width: 899px) {
  .app-body.has-aside { grid-template-rows: minmax(0, 1fr) auto; }
  .aside { width: auto; max-height: 45vh; }
}
@media (max-width: 767px) {
  .thread { max-width: none; }
}
</style>
