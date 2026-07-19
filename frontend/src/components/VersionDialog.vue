<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'
import type { Version } from '../types'

const props = defineProps<{ modelValue: boolean; documentId: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; restored: [] }>()
const versions = ref<Version[]>([])
const selected = ref<Version | null>(null)
const loading = ref(false)

watch(() => [props.modelValue, props.documentId], async () => {
  if (!props.modelValue || !props.documentId) return
  loading.value = true
  try {
    const { data } = await api.get(`/documents/${props.documentId}/versions`)
    versions.value = data
    selected.value = data[0] || null
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}, { immediate: true })

async function restore() {
  if (!props.documentId || !selected.value) return
  try {
    await api.post(`/documents/${props.documentId}/versions/${selected.value.id}/restore`)
    ElMessage.success(`已恢复版本 ${selected.value.version_number}`)
    emit('restored')
    emit('update:modelValue', false)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="历史版本" width="900px" @update:model-value="emit('update:modelValue', $event)">
    <div class="version-layout" v-loading="loading">
      <div class="version-list">
        <button v-for="item in versions" :key="item.id" :class="{ active: selected?.id === item.id }" @click="selected = item">
          <strong>版本 {{ item.version_number }}</strong>
          <span>{{ new Date(item.created_at).toLocaleString() }}</span>
          <small>{{ item.note || '无备注' }}</small>
        </button>
      </div>
      <div class="version-preview">
        <template v-if="selected">
          <h3>{{ selected.title }}</h3>
          <pre>{{ selected.content }}</pre>
        </template>
        <el-empty v-else description="暂无版本" />
      </div>
    </div>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" :disabled="!selected" @click="restore">恢复所选版本</el-button>
    </template>
  </el-dialog>
</template>
