<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'
import type { User } from '../types'

const emit = defineEmits<{ authenticated: [token: string, user: User] }>()
const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const form = reactive({ username: '', email: '', password: '' })

async function submit() {
  if (!form.username.trim() || !form.password) return ElMessage.warning('请填写用户名和密码')
  if (mode.value === 'register' && !form.email.trim()) return ElMessage.warning('请填写邮箱')
  loading.value = true
  try {
    const url = mode.value === 'login' ? '/auth/login' : '/auth/register'
    const payload = mode.value === 'login'
      ? { username: form.username, password: form.password }
      : { username: form.username, email: form.email, password: form.password }
    const { data } = await api.post(url, payload)
    localStorage.setItem('token', data.access_token)
    emit('authenticated', data.access_token, data.user)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="never">
      <h1>Markdown 个人知识库</h1>
      <p class="muted">保存、整理、搜索和迁移自己的 Markdown 资料</p>
      <el-tabs v-model="mode" stretch>
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名或邮箱">
          <el-input v-model="form.username" maxlength="50" @keyup.enter="submit" />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" label="邮箱">
          <el-input v-model="form.email" type="email" @keyup.enter="submit" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" :loading="loading" style="width: 100%" @click="submit">
          {{ mode === 'login' ? '登录' : '创建账号' }}
        </el-button>
      </el-form>
      <p class="auth-tip">首个注册账号自动成为管理员。数据默认保存在服务器本地。</p>
    </el-card>
  </div>
</template>
