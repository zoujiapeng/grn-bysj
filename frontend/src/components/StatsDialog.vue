<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const data = ref<any>(null)
const loading = ref(false)

watch(() => props.modelValue, async (value) => {
  if (!value) return
  loading.value = true
  try {
    data.value = (await api.get('/stats')).data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
})

function size(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="知识库统计" width="800px" @update:model-value="emit('update:modelValue', $event)">
    <div v-loading="loading">
      <div v-if="data" class="stats-grid">
        <el-statistic title="知识库" :value="data.counts.knowledge_bases" />
        <el-statistic title="文档" :value="data.counts.documents" />
        <el-statistic title="文件夹" :value="data.counts.folders" />
        <el-statistic title="标签" :value="data.counts.tags" />
        <el-statistic title="附件" :value="data.counts.attachments" />
        <el-statistic title="分享" :value="data.counts.shares" />
        <el-statistic title="回收站" :value="data.counts.trash" />
        <el-statistic title="附件空间" :value="size(data.storage_bytes)" />
      </div>
      <h3>各知识库节点数量</h3>
      <el-table v-if="data" :data="data.knowledge_bases" size="small">
        <el-table-column prop="name" label="知识库" />
        <el-table-column prop="count" label="节点数" width="100" />
      </el-table>
      <h3>最近操作</h3>
      <el-timeline v-if="data" style="max-height: 260px; overflow: auto">
        <el-timeline-item v-for="(item, index) in data.recent_activity" :key="index" :timestamp="new Date(item.created_at).toLocaleString()">
          {{ item.action }} {{ item.target_type }} {{ item.detail }}
        </el-timeline-item>
      </el-timeline>
    </div>
  </el-dialog>
</template>
