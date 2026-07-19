<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, errorMessage } from '../api'
import type { TreeNode } from '../types'

const props = defineProps<{ modelValue: boolean; knowledgeBaseId: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; changed: [] }>()
const items = ref<TreeNode[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/documents/trash', { params: props.knowledgeBaseId ? { kb_id: props.knowledgeBaseId } : {} })
    items.value = data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, (value) => value && load())

async function restore(id: number) {
  try {
    await api.post(`/documents/${id}/restore`)
    ElMessage.success('已恢复')
    await load()
    emit('changed')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function remove(id: number) {
  try {
    await ElMessageBox.confirm('永久删除后无法恢复，确定继续？', '危险操作', { type: 'warning' })
    await api.delete(`/documents/${id}/permanent`)
    ElMessage.success('已永久删除')
    await load()
    emit('changed')
  } catch (error: any) {
    if (error !== 'cancel') ElMessage.error(errorMessage(error))
  }
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="回收站" width="760px" @update:model-value="emit('update:modelValue', $event)">
    <el-table :data="items" v-loading="loading">
      <el-table-column prop="title" label="名称" min-width="220">
        <template #default="{ row }">{{ row.is_folder ? '📁' : '📄' }} {{ row.title }}</template>
      </el-table-column>
      <el-table-column label="最后更新" width="190">
        <template #default="{ row }">{{ new Date(row.updated_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="190">
        <template #default="{ row }">
          <el-button size="small" @click="restore(row.id)">恢复</el-button>
          <el-button size="small" type="danger" plain @click="remove(row.id)">永久删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && items.length === 0" description="回收站为空" />
  </el-dialog>
</template>
