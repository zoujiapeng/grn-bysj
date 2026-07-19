<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'

const token = window.location.pathname.split('/').filter(Boolean).pop() || ''
const password = ref('')
const loading = ref(false)
const needsPassword = ref(false)
const document = ref<{ title: string; content: string; knowledge_base_name: string; updated_at: string; allow_download: boolean } | null>(null)
const html = computed(() => DOMPurify.sanitize(marked.parse(document.value?.content || '') as string))

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/public/share/${token}`, { params: password.value ? { password: password.value } : {} })
    document.value = data
    needsPassword.value = false
  } catch (error: any) {
    if (error.response?.status === 401) needsPassword.value = true
    else ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function download() {
  const query = password.value ? `?password=${encodeURIComponent(password.value)}` : ''
  window.location.href = `/api/public/share/${token}/download${query}`
}

onMounted(load)
</script>

<template>
  <div class="public-page" v-loading="loading">
    <el-card v-if="needsPassword && !document" class="password-card" shadow="never">
      <h2>此文档需要访问密码</h2>
      <el-input v-model="password" type="password" show-password @keyup.enter="load" />
      <el-button type="primary" style="margin-top: 12px" @click="load">查看文档</el-button>
    </el-card>
    <article v-else-if="document" class="public-document">
      <header>
        <div>
          <h1>{{ document.title }}</h1>
          <p>{{ document.knowledge_base_name }} · 更新于 {{ new Date(document.updated_at).toLocaleString() }}</p>
        </div>
        <el-button v-if="document.allow_download" @click="download">下载 Markdown</el-button>
      </header>
      <div class="markdown-body" v-html="html" />
    </article>
  </div>
</template>
