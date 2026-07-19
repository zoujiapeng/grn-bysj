<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'
import type { Attachment, DocumentDetail, Tag } from '../types'

const props = defineProps<{ document: DocumentDetail | null; tags: Tag[] }>()
const emit = defineEmits<{
  autosave: [payload: { title: string; content: string; tag_ids: number[] }]
  saveVersion: [payload: { title: string; content: string; tag_ids: number[] }]
  favorite: [value: boolean]
  showVersions: []
  showShare: []
  remove: []
}>()

const title = ref('')
const content = ref('')
const selectedTagIds = ref<number[]>([])
const preview = ref(true)
const initialized = ref(false)
const savingAttachment = ref(false)
const attachments = ref<Attachment[]>([])
let timer: number | undefined

const rendered = computed(() => DOMPurify.sanitize(marked.parse(content.value || '') as string))

async function loadAttachments() {
  if (!props.document || props.document.is_folder) return (attachments.value = [])
  try {
    const { data } = await api.get(`/attachments/document/${props.document.id}`)
    attachments.value = data
  } catch {
    attachments.value = []
  }
}

watch(
  () => props.document?.id,
  async () => {
    initialized.value = false
    clearTimeout(timer)
    title.value = props.document?.title || ''
    content.value = props.document?.content || ''
    selectedTagIds.value = props.document?.tags.map((tag) => tag.id) || []
    await loadAttachments()
    await nextTick()
    initialized.value = true
  },
  { immediate: true }
)

watch([title, content, selectedTagIds], () => {
  if (!initialized.value || !props.document || props.document.is_folder) return
  clearTimeout(timer)
  timer = window.setTimeout(() => {
    emit('autosave', { title: title.value, content: content.value, tag_ids: [...selectedTagIds.value] })
  }, 900)
}, { deep: true })

onBeforeUnmount(() => clearTimeout(timer))

function saveVersion() {
  if (!props.document || props.document.is_folder) return
  emit('saveVersion', { title: title.value, content: content.value, tag_ids: [...selectedTagIds.value] })
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !props.document) return
  savingAttachment.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const { data } = await api.post(`/attachments/document/${props.document.id}`, form)
    attachments.value.unshift(data)
    const isImage = data.mime_type.startsWith('image/')
    content.value += `\n${isImage ? '!' : ''}[${data.original_name}](${data.url})\n`
    ElMessage.success('附件已上传并插入正文')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    input.value = ''
    savingAttachment.value = false
  }
}

async function deleteAttachment(item: Attachment) {
  try {
    await api.delete(`/attachments/${item.id}`)
    attachments.value = attachments.value.filter((value) => value.id !== item.id)
    ElMessage.success('附件已删除')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}
</script>

<template>
  <div v-if="!document" class="empty-editor">
    <el-empty description="从左侧选择或新建一篇文档" />
  </div>
  <div v-else-if="document.is_folder" class="empty-editor">
    <el-empty description="当前节点是文件夹" />
  </div>
  <section v-else class="editor-shell">
    <div class="editor-toolbar">
      <el-input v-model="title" class="title-input" maxlength="255" />
      <el-select v-model="selectedTagIds" multiple collapse-tags placeholder="标签" style="width: 220px">
        <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
      </el-select>
      <el-button @click="emit('favorite', !document.is_favorite)">{{ document.is_favorite ? '取消收藏' : '收藏' }}</el-button>
      <el-button @click="emit('showVersions')">历史</el-button>
      <el-button @click="emit('showShare')">分享</el-button>
      <el-button type="primary" @click="saveVersion">保存版本</el-button>
      <el-popconfirm title="确定移入回收站？" @confirm="emit('remove')">
        <template #reference><el-button type="danger" plain>删除</el-button></template>
      </el-popconfirm>
    </div>

    <div class="editor-secondary">
      <el-radio-group v-model="preview" size="small">
        <el-radio-button :value="false">仅编辑</el-radio-button>
        <el-radio-button :value="true">编辑 + 预览</el-radio-button>
      </el-radio-group>
      <label class="upload-button">
        <input type="file" hidden @change="upload" />
        <el-button :loading="savingAttachment" size="small">上传图片或附件</el-button>
      </label>
      <span class="muted">输入停止约 1 秒后自动保存；“保存版本”用于生成可恢复历史。</span>
    </div>

    <div class="editor-body" :class="{ 'single-pane': !preview }">
      <textarea v-model="content" spellcheck="false" placeholder="# 开始写 Markdown..." />
      <div v-if="preview" class="markdown-body" v-html="rendered" />
    </div>

    <div v-if="attachments.length" class="attachment-bar">
      <strong>附件：</strong>
      <el-tag v-for="item in attachments" :key="item.id" closable @close="deleteAttachment(item)">
        <a :href="item.url" target="_blank">{{ item.original_name }}</a>
      </el-tag>
    </div>
  </section>
</template>
