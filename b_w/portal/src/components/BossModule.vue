<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import KbChatPanel from './KbChatPanel.vue'
import ImportPanel from './ImportPanel.vue'
import {
  getSessionId,
  submitQuery,
  openStream,
  fetchHistory,
  clearHistory,
  checkHealth,
  SESSION_KEY,
} from '../api/kbQuery'

const messages = ref([])
const busy = ref(false)
const health = ref(false)
const streamOn = ref(true)
const drawerOpen = ref(false)

const THEME_KEY = 'kb-theme'
const theme = ref('light')

let es = null
let sessionId = getSessionId()
let healthTimer = null

onMounted(() => {
  try {
    theme.value = localStorage.getItem(THEME_KEY) || 'light'
  } catch (e) {
    /* 隐私模式下 localStorage 不可用，保持默认 */
  }
  checkHealth().then((v) => (health.value = v))
  healthTimer = setInterval(async () => {
    health.value = await checkHealth()
  }, 30000)
  loadHistory()
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  if (es) es.close()
  if (healthTimer) clearInterval(healthTimer)
  document.removeEventListener('keydown', onKeydown)
})

function onKeydown(e) {
  if (e.key === 'Escape' && drawerOpen.value) drawerOpen.value = false
}

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  try {
    localStorage.setItem(THEME_KEY, theme.value)
  } catch (e) {
    /* 忽略 */
  }
}

async function loadHistory() {
  const items = await fetchHistory(sessionId)
  if (items.length) messages.value = items
}

async function onClear() {
  if (!confirm('确定要清空当前会话的历史记录吗？这将无法恢复。')) return
  if (es) {
    es.close()
    es = null
  }
  await clearHistory(sessionId)
  messages.value = []
  busy.value = false
}

function onSend(text) {
  if (busy.value || !text) return
  busy.value = true
  messages.value.push({ role: 'user', text })

  // reactive 包裹，保证闭包内后续赋值走 proxy 触发渲染
  const ai = reactive({
    role: 'ai',
    text: '',
    stages: [],
    current: '',
    error: '',
    streaming: true,
    done: false,
  })
  messages.value.push(ai)
  handleQuery(text, ai)
}

async function handleQuery(text, ai) {
  try {
    const data = await submitQuery(text, sessionId, streamOn.value)
    if (data && data.session_id) {
      sessionId = data.session_id
      localStorage.setItem(SESSION_KEY, sessionId)
    }

    // 非流式：/query 直接回完整答案
    if (!streamOn.value) {
      ai.stages = Array.isArray(data.done_list) ? data.done_list.map((s) => String(s)) : []
      ai.text = data.answer || ''
      ai.error = data.error || ''
      if (!ai.text && !ai.error) ai.error = '后端未返回答案'
      finish(ai)
      return
    }

    es = openStream(sessionId, {
      onProgress(d) {
        const doneList = Array.isArray(d.done_list) ? d.done_list : []
        const runningList = Array.isArray(d.running_list) ? d.running_list : []
        ai.stages = doneList.map((s) => String(s))
        ai.current = runningList.length ? String(runningList[0]) : ''
      },
      onDelta(t) {
        ai.text += t
      },
      onFinal(d) {
        const ans =
          d && typeof d.answer === 'string' && d.answer.trim()
            ? d.answer
            : ai.text || '（后端未返回答案）'
        ai.text = ans
        finish(ai)
      },
      onError(msg) {
        ai.error = msg
        finish(ai)
      },
      onNativeError() {
        if (!ai.text) ai.error = ai.error || '连接中断，请重试'
        finish(ai)
      },
    })
  } catch (e) {
    ai.error = (e && e.message) || '请求失败'
    finish(ai)
  }
}

function finish(ai) {
  ai.streaming = false
  ai.done = true
  ai.current = ''
  busy.value = false
}
</script>

<template>
  <div class="kb-root" :data-theme="theme">
    <header class="kb-top">
      <div class="kb-brand">
        <svg class="mark ic-lg" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
          <rect x="12" y="12" width="8" height="8" rx="2" />
          <rect x="4" y="4" width="4" height="4" rx="1" />
          <rect x="24" y="4" width="4" height="4" rx="1" />
          <rect x="4" y="24" width="4" height="4" rx="1" />
          <rect x="24" y="24" width="4" height="4" rx="1" />
        </svg>
        <h1>Boss智库</h1>
        <span class="sub">KB AGENT · RAG</span>
      </div>

      <div class="kb-actions">
        <span class="badge" :class="health ? 'badge-online' : 'badge-offline'">
          <span class="status-led" :class="{ 'is-off': !health }"></span>
          {{ health ? 'API 已连接' : 'API 未连接' }}
        </span>

        <button type="button" class="btn btn-sm" @click="drawerOpen = true">
          <svg
            class="ic ic-sm"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M14 3v5h5" />
            <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
          </svg>
          <span>文件导入</span>
        </button>

        <button type="button" class="btn btn-sm btn-ghost" @click="onClear">清空对话</button>

        <button
          type="button"
          class="btn btn-sm btn-ghost"
          :aria-label="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          @click="toggleTheme"
        >
          {{ theme === 'dark' ? '浅色' : '深色' }}
        </button>
      </div>
    </header>

    <div class="kb-body">
      <aside class="kb-rail" aria-label="会话设置">
        <section class="panel">
          <div class="panel-head"><h2>输出设置</h2></div>
          <div class="panel-body">
            <label class="opt-row" for="kb-stream">
              <input id="kb-stream" v-model="streamOn" type="checkbox" />
              <span>流式输出</span>
            </label>
            <p class="rail-hint">开启后答案逐段推送、阶段进度实时更新；关闭后一次性返回完整答案。</p>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head"><h2>使用提示</h2></div>
          <div class="panel-body">
            <p class="rail-hint">
              先在「文件导入」上传资料，再回到本页提问。回答展开「阶段进度」可查看服务端处理链路；答案中的图片会随文附上原链接。
            </p>
          </div>
        </section>
      </aside>

      <main class="kb-pane">
        <KbChatPanel
          :messages="messages"
          :busy="busy"
          placeholder="基于知识库提问，例如：退货政策是什么？"
          empty-hint="提示：可以问「退货政策是什么？」"
          @send="onSend"
        />
      </main>
    </div>

    <Transition name="kb-fade">
      <div v-if="drawerOpen" class="kb-scrim" @click="drawerOpen = false"></div>
    </Transition>

    <Transition name="kb-drawer">
      <aside v-if="drawerOpen" class="kb-drawer" aria-label="文件导入">
        <div class="kb-drawer-head">
          <h2>文件导入</h2>
          <button
            type="button"
            class="btn btn-sm btn-ghost btn-icon"
            aria-label="关闭导入面板"
            @click="drawerOpen = false"
          >
            ✕
          </button>
        </div>
        <div class="kb-drawer-body">
          <ImportPanel />
        </div>
      </aside>
    </Transition>
  </div>
</template>
