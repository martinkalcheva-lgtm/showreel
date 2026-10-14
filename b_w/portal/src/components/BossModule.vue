<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import ImportPanel from './ImportPanel.vue'
import ChatPanel from './ChatPanel.vue'
import {
  getSessionId,
  newSessionId,
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
const sidebarOpen = ref(true)

let es = null
let sessionId = getSessionId()
let healthTimer = null

onMounted(() => {
  checkHealth().then((v) => (health.value = v))
  healthTimer = setInterval(async () => {
    health.value = await checkHealth()
  }, 30000)
  loadHistory()
})

onUnmounted(() => {
  if (es) es.close()
  if (healthTimer) clearInterval(healthTimer)
})

async function loadHistory() {
  const items = await fetchHistory(sessionId)
  if (items.length) messages.value = items
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
    markdown: true, // 智库回答走富渲染（粗体/图片），问数模块不受影响
  })
  messages.value.push(ai)
  handleQuery(text, ai)
}

async function handleQuery(text, ai) {
  try {
    const data = await submitQuery(text, sessionId)
    if (data && data.session_id) {
      sessionId = data.session_id
      localStorage.setItem(SESSION_KEY, sessionId)
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

function onNewSession() {
  if (es) {
    es.close()
    es = null
  }
  // 先清旧会话历史（DELETE 打到旧 sessionId），再切换到新会话
  const oldId = sessionId
  sessionId = newSessionId()
  messages.value = []
  busy.value = false
  clearHistory(oldId)
}
</script>

<template>
  <div class="boss">
    <div class="boss-body">
      <aside class="sidebar" :class="{ collapsed: !sidebarOpen }">
        <div class="sidebar-inner">
          <ImportPanel />
        </div>
      </aside>
      <section class="chat-area">
        <div class="mod-header">
          <div class="mod-title">Boss智库</div>
          <div class="header-actions">
            <div class="conn" :class="health ? 'ok' : 'fail'">
              <span class="dot"></span>{{ health ? '已连接' : '未连接' }}
            </div>
            <button class="btn-ghost" @click="onNewSession">新会话</button>
            <button class="btn-ghost" @click="sidebarOpen = !sidebarOpen">
              {{ sidebarOpen ? '收起导入' : '展开导入' }}
            </button>
          </div>
        </div>
        <div class="chat-card">
          <ChatPanel
            :messages="messages"
            :busy="busy"
            placeholder="基于知识库提问，例如：退货政策是什么？"
            empty-hint="把手册、文档、PDF 灌进去，然后用自然语言把它问出来"
            @send="onSend"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.boss {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.boss-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.sidebar {
  width: 340px;
  overflow: hidden;
  background: var(--bg-page);
  border-right: 1px solid var(--border);
  transition: width 240ms var(--ease);
  flex: none;
}
.sidebar.collapsed {
  width: 0;
  border-right: none;
}
.sidebar-inner {
  width: 340px;
  height: 100%;
  overflow-y: auto;
  padding: 12px;
}

.chat-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* 聊天窗口卡片：白底圆角阴影，让"窗口"有明确视觉边界 */
.chat-card {
  flex: 1;
  min-height: 0;
  margin: 0 16px 16px 4px;
  background: var(--bg-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
