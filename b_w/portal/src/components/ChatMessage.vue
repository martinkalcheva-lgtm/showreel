<script setup>
import { computed, reactive } from 'vue'

const props = defineProps({
  msg: { type: Object, required: true },
})

/* ===== 富渲染（仅 msg.markdown 为 true 时启用，问数模块不受影响） ===== */
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
  if (!props.msg.markdown) return null
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
</script>

<template>
  <div class="msg" :class="props.msg.role">
    <div class="bubble">
      <template v-if="props.msg.role === 'ai' && rich">
        <div v-if="props.msg.stages && props.msg.stages.length" class="stages" :class="{ dim: props.msg.done }">
          <div v-for="(s, i) in props.msg.stages" :key="i" class="stage">
            <span class="stage-dot"></span>{{ s }}
          </div>
        </div>
        <div v-if="props.msg.current" class="stage current">
          <span class="stage-dot pulse"></span>当前：{{ props.msg.current }}
        </div>
        <div v-if="props.msg.text" class="text rich-text">
          <div v-for="(segs, li) in rich.lines" :key="li" class="md-line">
            <template v-for="(s, si) in segs" :key="si"><strong v-if="s.b">{{ s.t }}</strong><template v-else>{{ s.t }}</template></template>
          </div>
        </div>
        <div v-if="rich.images.length" class="answer-images">
          <div v-for="(u, i) in rich.images" :key="i" class="answer-image">
            <img
              v-if="!imgFail[rewriteImgUrl(u)]"
              :src="rewriteImgUrl(u)"
              loading="lazy"
              alt="文档图片"
              @error="onImgError(u)"
            />
            <a v-else class="img-fallback" :href="rewriteImgUrl(u)" target="_blank" rel="noopener">
              图片地址（点击打开）：{{ rewriteImgUrl(u) }}
            </a>
          </div>
        </div>
        <div v-if="props.msg.error" class="error">（错误：{{ props.msg.error }}）</div>
        <div v-if="props.msg.streaming && !props.msg.text" class="dots">
          <span></span><span></span><span></span>
        </div>
      </template>
      <template v-else-if="props.msg.role === 'ai'">
        <div v-if="props.msg.stages && props.msg.stages.length" class="stages" :class="{ dim: props.msg.done }">
          <div v-for="(s, i) in props.msg.stages" :key="i" class="stage">
            <span class="stage-dot"></span>{{ s }}
          </div>
        </div>
        <div v-if="props.msg.current" class="stage current">
          <span class="stage-dot pulse"></span>当前：{{ props.msg.current }}
        </div>
        <div v-if="props.msg.text" class="text">{{ props.msg.text }}</div>
        <div v-if="props.msg.table" class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th v-for="(c, i) in props.msg.table.columns" :key="'c' + i">{{ c }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in props.msg.table.rows" :key="'r' + ri">
                <td v-for="(cell, ci) in row" :key="'d' + ri + '-' + ci">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="props.msg.error" class="error">（错误：{{ props.msg.error }}）</div>
        <div v-if="props.msg.streaming && !props.msg.text" class="dots">
          <span></span><span></span><span></span>
        </div>
      </template>
      <template v-else>
        <div class="text">{{ props.msg.text }}</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.msg {
  display: flex;
  margin-bottom: 16px;
}
.msg.user {
  justify-content: flex-end;
}

.bubble {
  max-width: 72%;
  padding: 12px 16px;
  border-radius: var(--radius-bubble);
  font-size: 15px;
  line-height: 1.6;
  word-break: break-word;
}
.msg.user .bubble {
  background: var(--blue);
  color: #fff;
  border-bottom-right-radius: 6px;
}
.msg.ai .bubble {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-bottom-left-radius: 6px;
  box-shadow: var(--shadow-card);
}
/* 带表格的回答放宽气泡宽度 */
.msg.ai .bubble:has(.table-wrap) {
  max-width: 92%;
}

/* 查询结果表格（iOS 商务风） */
.table-wrap {
  margin-top: 10px;
  overflow-x: auto;
}
.data-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
  line-height: 1.5;
}
.data-table th {
  background: var(--bg-page);
  color: var(--text-2);
  font-weight: 600;
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.data-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-1);
}
.data-table tbody tr:last-child td {
  border-bottom: none;
}
.data-table tbody tr:hover td {
  background: var(--bg-page);
}

.text {
  white-space: pre-wrap;
}

/* 进度时间线 */
.stages {
  margin-bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stage {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-2);
}
.stages.dim .stage {
  color: var(--text-3);
}
.stage-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--blue);
  flex: none;
}
.stages.dim .stage-dot {
  background: var(--text-3);
}
.stage.current {
  font-size: 13px;
  color: var(--blue);
  margin-bottom: 8px;
}
.stage-dot.pulse {
  animation: pulse 1s var(--ease) infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.error {
  color: var(--red);
  font-size: 13px;
  margin-top: 8px;
}

/* ===== 富渲染（智库 markdown + 图片） ===== */
.rich-text .md-line {
  min-height: 1em;
}
.rich-text strong {
  font-weight: 600;
}
.answer-images {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.answer-image img {
  display: block;
  max-width: min(100%, 600px);
  max-height: 600px;
  width: auto;
  height: auto;
  border-radius: 12px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-card);
  background: #fff;
}
.img-fallback {
  font-size: 12px;
  color: var(--text-2);
  word-break: break-all;
  text-decoration: none;
}
.img-fallback:hover {
  color: var(--blue);
}

/* 流式输出三点跳动 */
.dots {
  display: inline-flex;
  gap: 4px;
  padding: 4px 0;
}
.dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-3);
  animation: dotJump 1.2s infinite var(--ease);
}
.dots span:nth-child(2) {
  animation-delay: 0.2s;
}
.dots span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes dotJump {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
</style>
