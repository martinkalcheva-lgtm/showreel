<script setup>
import { computed } from 'vue'

const props = defineProps({
  task: { type: Object, required: true },
})

// 真实导入流程共 8 个节点（与后端 import_processor 节点一一对应）
const TOTAL_STEPS = 8
const STAGE_LABELS = {
  upload_file: '文件上传',
  node_entry: '任务启动',
  node_pdf_to_md: 'PDF转Markdown',
  node_item_name_recognition: '识别文档标题',
  node_document_split: '文档分块',
  node_md_img: '图片处理',
  node_bge_embedding: '向量化',
  node_import_milvus: '写入向量库',
}
const stageLabel = (s) => STAGE_LABELS[s] || String(s).replace(/^node_/, '')

const extMap = { PDF: 'PDF', MD: 'MD', MARKDOWN: 'MD', DOC: 'DOC', DOCX: 'DOC' }

const badgeText = computed(() => {
  const m = (props.task.name || '').match(/\.([a-z0-9]+)$/i)
  if (!m) return 'FILE'
  const ext = m[1].toUpperCase()
  return extMap[ext] || ext.slice(0, 4)
})

const running = computed(
  () => props.task.status === 'pending' || props.task.status === 'processing'
)

const statusClass = computed(() => {
  if (running.value) return 'running'
  if (props.task.status === 'failed') return 'failed'
  if (props.task.status === 'interrupted') return 'interrupted'
  return 'completed'
})

const statusText = computed(() => {
  if (running.value) return '进行中'
  if (props.task.status === 'failed') return '失败'
  if (props.task.status === 'interrupted') return '已中断'
  return '完成'
})

// 步骤级状态：进行到哪一步 / 停在哪一步
const doneSteps = computed(() =>
  (props.task.done_list || []).map((s) => stageLabel(s))
)
const curStep = computed(() => {
  const c = (props.task.running_list || [])[0]
  return c ? stageLabel(c) : ''
})

const stepText = computed(() => {
  // 特殊说明（进度丢失/查询失败）优先展示
  if (props.task.note) return props.task.note
  const s = props.task.status
  const n = doneSteps.value.length
  if (running.value) {
    return curStep.value
      ? `第 ${n + 1}/${TOTAL_STEPS} 步 · ${curStep.value}`
      : `已完成 ${n}/${TOTAL_STEPS} 步`
  }
  if (s === 'completed') return `共 ${TOTAL_STEPS} 步全部完成`
  if (s === 'failed')
    return n ? `停在第 ${n} 步 · ${doneSteps.value[n - 1]}` : '未开始任何步骤'
  if (s === 'interrupted')
    return n ? `中断于第 ${n} 步 · ${doneSteps.value[n - 1]}` : ''
  return ''
})

const progressPct = computed(() => {
  const s = props.task.status
  if (s === 'completed') return 100
  const base = doneSteps.value.length / TOTAL_STEPS
  const half = running.value && curStep.value ? 0.5 / TOTAL_STEPS : 0
  return Math.min(100, Math.round((base + half) * 100))
})

const sizeText = computed(() => formatBytes(props.task.size))

const timeText = computed(() => {
  const d = new Date(props.task.ts || Date.now())
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
})

function formatBytes(n) {
  if (n == null || isNaN(n)) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <div class="task-item">
    <div class="badge">{{ badgeText }}</div>
    <div class="task-info">
      <div class="task-name" :title="props.task.name">{{ props.task.name }}</div>
      <div class="task-meta">
        <span v-if="sizeText">{{ sizeText }}</span>
        <span v-if="sizeText"> · </span>
        <span>{{ timeText }}</span>
        <span class="task-status" :class="statusClass">{{ statusText }}</span>
      </div>
      <div v-if="stepText" class="step-row">
        <div class="step-bar">
          <div
            class="step-bar-fill"
            :class="statusClass"
            :style="{ width: progressPct + '%' }"
          ></div>
        </div>
        <div class="step-text" :class="statusClass">{{ stepText }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--bg-card);
  border-radius: var(--radius-btn);
  padding: 10px 12px;
  box-shadow: var(--shadow-card);
}
.badge {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-badge);
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #fff;
  background: var(--blue);
  margin-top: 2px;
}

.task-info {
  flex: 1;
  min-width: 0;
}
.task-name {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-meta {
  font-size: 13px;
  color: var(--text-2);
  display: flex;
  align-items: center;
}
.task-status {
  margin-left: auto;
  font-size: 13px;
  font-weight: 500;
  flex: none;
}
.task-status.running {
  color: var(--blue);
}
.task-status.completed {
  color: var(--green);
}
.task-status.failed {
  color: var(--red);
}
.task-status.interrupted {
  color: var(--text-3);
}

/* 步骤进度条 + 步骤文案 */
.step-row {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-bar {
  flex: none;
  width: 64px;
  height: 4px;
  border-radius: 999px;
  background: var(--border);
  overflow: hidden;
}
.step-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 240ms var(--ease);
}
.step-bar-fill.running {
  background: var(--blue);
}
.step-bar-fill.completed {
  background: var(--green);
}
.step-bar-fill.failed {
  background: var(--red);
}
.step-bar-fill.interrupted {
  background: var(--text-3);
}
.step-text {
  font-size: 12px;
  line-height: 16px;
  color: var(--text-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.step-text.running {
  color: var(--blue);
}
.step-text.completed {
  color: var(--green);
}
.step-text.failed {
  color: var(--red);
}
.step-text.interrupted {
  color: var(--text-3);
}
</style>
