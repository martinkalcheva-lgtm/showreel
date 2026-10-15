<script setup>
import { ref } from 'vue'
import WenshuModule from './components/WenshuModule.vue'
import BossModule from './components/BossModule.vue'

const activeTab = ref('wenshu')
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="topbar-title">Boss 工作台</div>
      <nav class="topbar-tabs">
        <button
          class="tab"
          :class="{ active: activeTab === 'wenshu' }"
          @click="activeTab = 'wenshu'"
        >
          问数
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'boss' }"
          @click="activeTab = 'boss'"
        >
          Boss智库
        </button>
      </nav>
    </header>
    <main class="page">
      <WenshuModule v-show="activeTab === 'wenshu'" />
      <BossModule v-show="activeTab === 'boss'" />
    </main>
  </div>
</template>

<style scoped>
.app {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 56px;
  min-height: 56px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 24px;
}

.topbar-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-1);
}

.topbar-tabs {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 8px;
  height: 100%;
}

.tab {
  position: relative;
  padding: 0 16px;
  font-size: 15px;
  color: var(--text-3);
  transition: color 160ms var(--ease);
}
.tab:hover {
  color: var(--text-1);
}
.tab.active {
  color: var(--accent);
  font-weight: 600;
}
.tab.active::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 0;
  height: 2px;
  background: var(--accent);
  border-radius: 2px;
}

.page {
  flex: 1;
  min-height: 0;
  display: flex;
}
.page > * {
  flex: 1;
  min-width: 0;
}
</style>
