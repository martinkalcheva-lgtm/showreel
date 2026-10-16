<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import KbChatMessage from './KbChatMessage.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  busy: Boolean,
  placeholder: { type: String, default: '输入消息…' },
  emptyHint: { type: String, default: '' },
})
const emit = defineEmits(['send'])

const input = ref('')
const listEl = ref(null)
const inputEl = ref(null)
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
</script>

<template>
  <div class="kb-pane-inner">
    <div ref="listEl" class="stream" @scroll="onScroll">
      <article v-if="!messages.length" class="msg bot">
        <div class="avatar bot" aria-hidden="true">KB</div>
        <div class="msg-main">
          <div class="bubble">你好，我是 Boss 智库。把手册、文档、PDF 灌进去，然后用自然语言把它问出来。</div>
          <p class="meta">{{ emptyHint || '提示：可以问「退货政策是什么？」' }}</p>
        </div>
      </article>

      <KbChatMessage v-for="(m, i) in messages" :key="i" :msg="m" />
    </div>

    <div class="composer-wrap">
      <div class="composer">
        <label class="sr-only" for="kb-input">向知识库提问</label>
        <textarea
          id="kb-input"
          ref="inputEl"
          v-model="input"
          rows="1"
          :placeholder="placeholder"
          :disabled="busy"
          @input="autoGrow"
          @keydown.enter.exact.prevent="doSend"
        ></textarea>
        <div class="composer-actions">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="busy || !input.trim()"
            @click="doSend"
          >
            发送
          </button>
        </div>
      </div>
      <div class="composer-foot">
        <span>Enter 发送 · Shift + Enter 换行</span>
        <span>答案附阶段进度与来源图片</span>
      </div>
    </div>
  </div>
</template>
