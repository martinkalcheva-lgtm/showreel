<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import ChatMessage from './ChatMessage.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  busy: Boolean,
  placeholder: { type: String, default: '输入消息…' },
  emptyHint: { type: String, default: '' },
})
const emit = defineEmits(['send'])

const input = ref('')
const listEl = ref(null)
const autoScroll = ref(true)

function onScroll() {
  const el = listEl.value
  if (!el) return
  // 距底 48px 以内视为在底部；手动上滚则暂停自动滚动
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 48
}

function scrollToBottom() {
  const el = listEl.value
  if (el) el.scrollTop = el.scrollHeight
}

// 消息数 / 末条文本长度 / 进度节点数 变化时尝试滚底（覆盖流式增量）
const signature = computed(() => {
  const last = props.messages[props.messages.length - 1]
  if (!last) return '0'
  return (
    props.messages.length +
    '|' +
    (last.text || '').length +
    '|' +
    (last.stages ? last.stages.length : 0) +
    '|' +
    (last.current || '')
  )
})
watch(signature, () => {
  if (autoScroll.value) nextTick(scrollToBottom)
})

function autoGrow(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function doSend() {
  const text = input.value.trim()
  if (!text || props.busy) return
  input.value = ''
  autoScroll.value = true
  emit('send', text)
  nextTick(() => {
    const el = inputEl.value
    if (el) el.style.height = 'auto'
    scrollToBottom()
  })
}

const inputEl = ref(null)
</script>

<template>
  <div class="chat-panel">
    <div ref="listEl" class="chat-list" @scroll="onScroll">
      <div v-if="!messages.length" class="empty">
        <svg class="empty-icon" viewBox="0 0 680 680" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M340 96c-150 0-260 96-260 216 0 66 34 124 88 164l-14 92c-2 14 12 24 24 17l96-56c21 5 43 8 66 8 150 0 260-96 260-216S490 96 340 96z"
            fill="#e5e5ea"
          />
          <circle cx="250" cy="312" r="22" fill="#aeaeb2" />
          <circle cx="340" cy="312" r="22" fill="#aeaeb2" />
          <circle cx="430" cy="312" r="22" fill="#aeaeb2" />
        </svg>
        <div class="empty-text">{{ props.emptyHint }}</div>
      </div>
      <ChatMessage v-for="(m, i) in props.messages" :key="i" :msg="m" />
    </div>
    <div class="chat-input">
      <textarea
        ref="inputEl"
        v-model="input"
        rows="1"
        :placeholder="props.placeholder"
        :disabled="props.busy"
        @input="autoGrow"
        @keydown.enter.exact.prevent="doSend"
      ></textarea>
      <button
        class="btn-primary send-btn"
        :disabled="props.busy || !input.trim()"
        @click="doSend"
      >
        发送
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 20px 16px;
}

.empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-2);
}
.empty-icon {
  width: 64px;
  height: 64px;
}
.empty-text {
  font-size: 15px;
  line-height: 1.6;
  max-width: 420px;
  text-align: center;
}

.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px 20px 16px;
}
.chat-input textarea {
  flex: 1;
  resize: none;
  background: var(--bg-input);
  border: 1px solid transparent;
  border-radius: var(--radius-input);
  padding: 11px 14px;
  font-size: 15px;
  line-height: 1.5;
  min-height: 44px;
  max-height: 120px;
  outline: none;
  transition: border-color 160ms var(--ease), background 160ms var(--ease);
}
.chat-input textarea::placeholder {
  color: var(--text-3);
}
.chat-input textarea:focus {
  background: var(--bg-card);
  border-color: var(--blue);
}
.send-btn {
  min-width: 76px;
  height: 44px;
}
</style>
