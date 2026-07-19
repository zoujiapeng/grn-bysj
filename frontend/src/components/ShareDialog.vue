<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'

const props = defineProps<{ modelValue: boolean; documentId: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const form = reactive({ password: '', expires_at: '', allow_download: true })
const shares = ref<any[]>([])
const loading = ref(false)

async function load() {
  if (!props.documentId) return
  try {
    const { data } = await api.get('/shares')
    shares.value = data.filter((item: any) => item.document_id === props.documentId)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

watch(() => props.modelValue, (value) => value && load())

function shareUrl(token: string) {
  return `${window.location.origin}/share/${token}`
}

async function create() {
  if (!props.documentId) return
  loading.value = true
  try {
    await api.post('/shares', {
      document_id: props.documentId,
      password: form.password || null,
      expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
      allow_download: form.allow_download
    })
    ElMessage.success('分享链接已创建')
    form.password = ''
    form.expires_at = ''
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function copy(token: string) {
  await navigator.clipboard.writeText(shareUrl(token))
  ElMessage.success('链接已复制')
}

async function revoke(id: number) {
  try {
    await api.delete(`/shares/${id}`)
    ElMessage.success('分享已取消')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="公开分享" width="720px" @update:model-value="emit('update:modelValue', $event)">
    <el-form label-width="100px">
      <el-form-item label="访问密码">
        <el-input v-model="form.password" placeholder="留空表示不需要密码" show-password />
      </el-form-item>
      <el-form-item label="过期时间">
        <el-date-picker v-model="form.expires_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="留空表示永久有效" />
      </el-form-item>
      <el-form-item label="允许下载">
        <el-switch v-model="form.allow_download" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="create">生成分享链接</el-button>
      </el-form-item>
    </el-form>
    <el-table :data="shares" size="small">
      <el-table-column label="链接" min-width="300">
        <template #default="{ row }"><code>{{ shareUrl(row.token) }}</code></template>
      </el-table-column>
      <el-table-column label="限制" width="150">
        <template #default="{ row }">{{ row.password_protected ? '有密码' : '无密码' }} / {{ row.allow_download ? '可下载' : '只读' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="copy(row.token)">复制</el-button>
          <el-button size="small" type="danger" link @click="revoke(row.id)">取消</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>
