<script setup>
import { computed, reactive } from 'vue'

const props = defineProps({
  msg: { type: Object, required: true },
})

/* ===== 富渲染：粗体 / 图片行（与 7954 chat.html 的解析口径一致） ===== */
const IMG_LINE_RE = /^(?:【图片】\s*)?(https?:\/\/\S+)$/i
const IMG_EXT_RE = /\.(jpg|jpeg|png|gif|webp)(\?\S*)?$/i
const BOLD_RE = /\*\*([^*]+)\*\*/g

// minio:9000 是后端容器内部主机名，浏览器不可达 → 重写为宿主机地址
const rewriteImgUrl = (u) => String(u).replace('://minio:9000', '://localhost:9000')

function parseBoldLine(line) {
  const segs = []
  let last = 0
  let m
  BOLD_RE.lastIndex = 0
  while ((m = BOLD_RE.exec(line))) {
    if (m.index > last) segs.push({ b: false, t: line.slice(last, m.index) })
    segs.push({ b: true, t: m[1] })
    last = m.index + m[0].length
  }
  if (last < line.length) segs.push({ b: false, t: line.slice(last) })
  return segs.length ? segs : [{ b: false, t: line }]
}

const rich = computed(() => {
  const lines = String(props.msg.text || '').split('\n')
  const outLines = []
  const images = []
  for (const raw of lines) {
    const t = raw.trim()
    if (!t) {
      outLines.push([{ b: false, t: '' }])
      continue
    }
    // 独立图片行：【图片】http://... 或裸图片 URL
    const m = t.match(IMG_LINE_RE)
    if (m && IMG_EXT_RE.test(m[1])) {
      images.push(m[1])
      continue
    }
    if (t === '【图片】') continue // 仅前缀行，URL 在下一行
    // 列表符号统一为 ·；标题符 ### 去除（加粗由 ** 处理）
    const line = t.replace(/^\s*\*\s+/, '· ').replace(/^#{1,6}\s+/, '')
    outLines.push(parseBoldLine(line))
  }
  return { lines: outLines, images }
})

// 图片加载失败 → 降级为可点击链接
const imgFail = reactive({})
const onImgError = (u) => {
  imgFail[rewriteImgUrl(u)] = true
}

const isUser = computed(() => props.msg.role === 'user')
const hasText = computed(() => !!String(props.msg.text || '').trim())

// 消息本身不带时间戳（历史接口只给 role/text），取组件创建时刻
const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

const hasProgress = computed(() => {
  const done = Array.isArray(props.msg.stages) && props.msg.stages.length > 0
  return done || !!props.msg.current || !!props.msg.streaming
})
const progressOpen = computed(() => !props.msg.done)
const progressSummary = computed(() => {
  const done = Array.isArray(props.msg.stages) ? props.msg.stages.length : 0
  const running = props.msg.current ? 1 : 0
  const status = props.msg.error ? '失败' : props.msg.done ? '已完成' : '处理中'
  return `阶段进度（已完成${done}，进行中${running}，状态：${status}）`
})
</script>

<template>
  <!-- 用户 -->
  <article v-if="isUser" class="msg user">
    <div class="msg-main">
      <div class="bubble">{{ msg.text }}</div>
      <p class="meta">{{ time }}</p>
    </div>
    <div class="avatar me" aria-hidden="true">我</div>
  </article>

  <!-- 智库 -->
  <article v-else class="msg bot">
    <div class="avatar bot" aria-hidden="true">KB</div>
    <div class="msg-main">
      <div class="bubble">
        <span v-if="msg.streaming && !hasText" class="typing" aria-label="正在处理">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </span>

        <div v-if="hasText" class="rich-text">
          <div v-for="(segs, li) in rich.lines" :key="li" class="md-line">
            <template v-for="(s, si) in segs" :key="si">
              <strong v-if="s.b">{{ s.t }}</strong><template v-else>{{ s.t }}</template>
            </template>
          </div>
        </div>

        <div v-if="rich.images.length" class="answer-images">
          <div v-for="(u, i) in rich.images" :key="i">
            <template v-if="!imgFail[rewriteImgUrl(u)]">
              <img
                :src="rewriteImgUrl(u)"
                loading="lazy"
                alt="文档图片"
                referrerpolicy="no-referrer"
                @error="onImgError(u)"
              />
              <a :href="rewriteImgUrl(u)" target="_blank" rel="noopener noreferrer">{{ rewriteImgUrl(u) }}</a>
            </template>
            <a v-else class="img-fallback" :href="rewriteImgUrl(u)" target="_blank" rel="noopener noreferrer">
              图片地址（点击打开）：{{ rewriteImgUrl(u) }}
            </a>
          </div>
        </div>

        <div v-if="msg.error" class="err">（错误：{{ msg.error }}）</div>

        <details v-if="hasProgress" class="progress" :open="progressOpen">
          <summary>{{ progressSummary }}</summary>
          <ul>
            <li v-for="(s, i) in (msg.stages || [])" :key="'d' + i">✓ {{ s }}</li>
            <li v-if="msg.current">… {{ msg.current }}</li>
            <li v-if="!(msg.stages && msg.stages.length) && !msg.current">暂无进度</li>
          </ul>
        </details>
      </div>
      <p class="meta">{{ time }}</p>
    </div>
  </article>
</template>
