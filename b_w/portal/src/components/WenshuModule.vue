<script setup>
import { ref, reactive, onUnmounted } from 'vue'
import ChatPanel from './ChatPanel.vue'
import { queryDataStream } from '../api/dsApi'

const messages = ref([])
const busy = ref(false)
// unknown=待连接 ok=服务就绪 fail=未连接（由首次请求结果决定）
const conn = ref('unknown')
let controller = null

async function onSend(text) {
  if (busy.value || !text) return
  busy.value = true
  messages.value.push({ role: 'user', text })

  // reactive 包裹，保证闭包内后续赋值走 proxy 触发渲染
  const ai = reactive({ role: 'ai', text: '', stages: [], error: '', streaming: true, done: false })
  messages.value.push(ai)

  controller = new AbortController()
  try {
    await queryDataStream(
      text,
      {
        onStage(stage) {
          ai.stages.push(stage)
        },
        onResult(result) {
          // 行数据（对象数组）→ 渲染成表格；其余原样展示
          if (
            Array.isArray(result) &&
            result.length &&
            result.every((r) => r && typeof r === 'object' && !Array.isArray(r))
          ) {
            const columns = [...new Set(result.flatMap((r) => Object.keys(r)))]
            ai.table = {
              columns,
              rows: result.map((r) =>
                columns.map((c) => (r[c] == null ? '' : String(r[c])))
              ),
            }
            ai.text = `查询完成，共 ${result.length} 行结果：`
          } else {
            ai.text =
              typeof result === 'string' ? result : JSON.stringify(result, null, 2)
          }
        },
        onError(msg) {
          ai.error = msg
        },
      },
      controller.signal
    )
    if (!ai.text && !ai.error) ai.error = '未返回结果'
    conn.value = 'ok'
  } catch (e) {
    if (!controller.signal.aborted) {
      ai.error = (e && e.message) || '请求失败'
      conn.value = 'fail'
    }
  } finally {
    ai.streaming = false
    ai.done = true
    busy.value = false
    controller = null
  }
}

onUnmounted(() => {
  if (controller) controller.abort()
})
</script>

<template>
  <div class="wenshu">
    <div class="mod-header">
      <div class="mod-title">智能问数</div>
      <div class="conn" :class="conn">
        <span class="dot"></span>
        {{ conn === 'ok' ? '服务就绪' : conn === 'fail' ? '未连接' : '待连接' }}
      </div>
    </div>
    <div class="chat-card">
      <ChatPanel
        :messages="messages"
        :busy="busy"
        placeholder="输入你的问题，例如：统计2025年各地区销售总额"
        empty-hint="用自然语言查询数据，例如：统计2025年各地区销售总额"
        @send="onSend"
      />
    </div>
  </div>
</template>

<style scoped>
.wenshu {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 聊天窗口卡片：白底圆角阴影，让"窗口"有明确视觉边界 */
.chat-card {
  flex: 1;
  min-height: 0;
  margin: 0 16px 16px;
  background: var(--bg-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
