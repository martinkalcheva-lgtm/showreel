<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import TaskItem from './TaskItem.vue'
import {
  uploadFiles,
  fetchTaskStatus,
  loadImportHistory,
  saveImportHistory,
  addImportRecord,
  updateImportRecord,
} from '../api/kbImport'

const dragOver = ref(false)
const fileInput = ref(null)
const uploadError = ref('')
// 进行中的任务（响应式，供轮询实时刷新）
const tasks = ref([])
// 导入历史（localStorage，最近 10 条）
const history = ref([])
const timers = new Map()

// 页面（重）加载后：localStorage 里非终态的任务恢复轮询
// —— 任务可能仍在后端运行；若服务重启丢进度，tick 里的 lost 检测会标记「进度丢失」
onMounted(() => {
  const list = loadImportHistory()
  history.value = list.slice(0, 10)
  for (const rec of list) {
    if (rec.status === 'pending' || rec.status === 'processing') {
      if (tasks.value.some((t) => t.task_id === rec.task_id)) continue
      const live = reactive({ ...rec })
      tasks.value.push(live)
      startPolling(live)
    }
  }
})

const displayList = computed(() =>
  history.value.map((h) => tasks.value.find((t) => t.task_id === h.task_id) || h)
)

function pickFiles() {
  fileInput.value?.click()
}

function onFileChange(e) {
  handleFiles(e.target.files)
  e.target.value = ''
}

function onDrop(e) {
  dragOver.value = false
  handleFiles(e.dataTransfer.files)
}

async function handleFiles(fileList) {
  const files = Array.from(fileList || [])
  if (!files.length) return
  try {
    const taskIds = await uploadFiles(files)
    // 数量不一致直接报错，绝不错位映射
    if (taskIds.length !== files.length) {
      throw new Error('服务端返回任务数与文件数不符')
    }
    files.forEach((f, i) => {
      // reactive 包裹：轮询闭包里的赋值必须走 proxy，否则 UI 永远不更新（同聊天模块的 P0 教训）
      const rec = reactive({
        task_id: taskIds[i],
        name: f.name,
        size: f.size,
        ts: Date.now(),
        status: 'pending',
        done_list: [],
        running_list: [],
      })
      tasks.value.push(rec)
      addImportRecord(rec)
      refreshHistory()
      startPolling(rec)
    })
  } catch (e) {
    uploadError.value = (e && e.message) || '上传失败'
    setTimeout(() => (uploadError.value = ''), 4000)
  }
}

function startPolling(task) {
  let failCount = 0
  const tick = async () => {
    try {
      const d = await fetchTaskStatus(task.task_id)
      failCount = 0
      // 导入服务重启会丢失内存态任务：状态与进度全空 → 标记中断，停止轮询
      const lost =
        !d.status &&
        !(Array.isArray(d.done_list) && d.done_list.length) &&
        !(Array.isArray(d.running_list) && d.running_list.length)
      if (lost) {
        task.status = 'interrupted'
        task.note = '进度丢失（导入服务已重启），请重新上传'
        updateImportRecord(task.task_id, { status: 'interrupted', note: task.note })
        refreshHistory()
        stopPolling(task.task_id)
        return
      }
      task.status = d.status || task.status
      task.done_list = Array.isArray(d.done_list) ? d.done_list : []
      task.running_list = Array.isArray(d.running_list) ? d.running_list : []
      if (task.status === 'completed' || task.status === 'failed') {
        updateImportRecord(task.task_id, {
          status: task.status,
          done_list: task.done_list,
          running_list: task.running_list,
        })
        refreshHistory()
        stopPolling(task.task_id)
      }
    } catch {
      // 连续多次查询失败才放弃，避免网络抖动误杀
      failCount++
      if (failCount >= 5) {
        task.status = 'interrupted'
        task.note = '状态查询连续失败，已停止轮询'
        updateImportRecord(task.task_id, { status: 'interrupted', note: task.note })
        refreshHistory()
        stopPolling(task.task_id)
      }
    }
  }
  timers.set(task.task_id, setInterval(tick, 1500))
}

function stopPolling(taskId) {
  const t = timers.get(taskId)
  if (t) {
    clearInterval(t)
    timers.delete(taskId)
  }
}

function refreshHistory() {
  history.value = loadImportHistory().slice(0, 10)
}

onUnmounted(() => {
  timers.forEach((t) => clearInterval(t))
  timers.clear()
})
</script>

<template>
  <div class="import-panel">
    <div
      class="upload-card"
      :class="{ dragover: dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
      @click="pickFiles"
    >
      <svg class="upload-icon" viewBox="0 0 680 680" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M340 520V230M340 230l-110 110M340 230l110 110"
          stroke="#007aff"
          stroke-width="48"
          stroke-linecap="round"
          stroke-linejoin="round"
          fill="none"
        />
        <path
          d="M180 420H140c-40 0-70-30-70-70s30-70 70-70h30c10-90 85-160 170-160s160 70 170 160h30c40 0 70 30 70 70s-30 70-70 70h-40"
          stroke="#007aff"
          stroke-width="44"
          stroke-linecap="round"
          fill="none"
          opacity="0.35"
        />
      </svg>
      <div class="upload-title">把文件拖到这里</div>
      <div class="upload-sub">PDF / Markdown / Word，可一次多个</div>
      <button class="btn-primary" @click.stop="pickFiles">选择文件</button>
      <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>
    </div>

    <input
      ref="fileInput"
      type="file"
      multiple
      accept=".pdf,.md,.markdown,.doc,.docx"
      hidden
      @change="onFileChange"
    />

    <div class="section">
      <div class="section-title">导入记录（最近 10 条）</div>
      <div v-if="!displayList.length" class="section-empty">暂无导入记录</div>
      <div v-else class="queue">
        <TaskItem v-for="(t, i) in displayList" :key="t.task_id || i" :task="t" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.import-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-card {
  background: var(--bg-card);
  border: 2px dashed #c7c7cc;
  border-radius: var(--radius-card);
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  cursor: pointer;
  transition: border-color 160ms var(--ease), background 160ms var(--ease),
    box-shadow 160ms var(--ease);
}
.upload-card:hover {
  box-shadow: var(--shadow-hover);
}
.upload-card.dragover {
  border-color: var(--blue);
  background: rgba(0, 122, 255, 0.04);
}

.upload-icon {
  width: 40px;
  height: 40px;
}
.upload-title {
  font-size: 15px;
  font-weight: 500;
}
.upload-sub {
  font-size: 13px;
  color: var(--text-2);
}
.upload-card .btn-primary {
  margin-top: 6px;
  font-size: 13px;
  padding: 8px 18px;
}
.upload-error {
  font-size: 13px;
  color: var(--red);
}

.section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}
.section-empty {
  font-size: 13px;
  color: var(--text-3);
  padding: 8px 2px;
}
.queue {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
