<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'
import type { SearchResult } from '../types'

const props = defineProps<{ modelValue: boolean; knowledgeBaseId: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; select: [item: SearchResult] }>()
const keyword = ref('')
const results = ref<SearchResult[]>([])
const loading = ref(false)
let timer: number | undefined

watch(keyword, () => {
  clearTimeout(timer)
  timer = window.setTimeout(search, 300)
})
watch(() => props.modelValue, (value) => value && setTimeout(() => document.querySelector<HTMLInputElement>('.search-input input')?.focus(), 100))

async function search() {
  if (!keyword.value.trim()) return (results.value = [])
  loading.value = true
  try {
    const params: Record<string, unknown> = { q: keyword.value.trim() }
    if (props.knowledgeBaseId) params.kb_id = props.knowledgeBaseId
    const { data } = await api.get('/documents/search', { params })
    results.value = data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="全文搜索" width="720px" @update:model-value="emit('update:modelValue', $event)">
    <el-input v-model="keyword" class="search-input" placeholder="搜索标题、正文或标签" clearable />
    <div class="search-results" v-loading="loading">
      <button v-for="item in results" :key="item.id" class="search-item" @click="emit('select', item); emit('update:modelValue', false)">
        <strong>{{ item.title }}</strong>
        <span>{{ item.knowledge_base_name }}</span>
        <p>{{ item.snippet || '正文中没有可显示的摘要' }}</p>
        <small>{{ item.tags.join(' · ') }}</small>
      </button>
      <el-empty v-if="keyword && !loading && results.length === 0" description="没有匹配内容" />
    </div>
  </el-dialog>
</template>
