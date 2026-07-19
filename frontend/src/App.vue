<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, downloadBlob, errorMessage } from './api'
import type { DocumentDetail, KnowledgeBase, SearchResult, Tag, TreeNode, User } from './types'
import AuthView from './components/AuthView.vue'
import DocumentTree from './components/DocumentTree.vue'
import MarkdownEditor from './components/MarkdownEditor.vue'
import PublicShareView from './components/PublicShareView.vue'
import SearchDialog from './components/SearchDialog.vue'
import ShareDialog from './components/ShareDialog.vue'
import StatsDialog from './components/StatsDialog.vue'
import TrashDialog from './components/TrashDialog.vue'
import VersionDialog from './components/VersionDialog.vue'

const isPublicShare = window.location.pathname.startsWith('/share/')
const token = ref(localStorage.getItem('token'))
const user = ref<User | null>(null)
const loading = ref(false)
const knowledgeBases = ref<KnowledgeBase[]>([])
const activeKbId = ref<number | null>(null)
const nodes = ref<TreeNode[]>([])
const selected = ref<DocumentDetail | null>(null)
const tags = ref<Tag[]>([])
const searchVisible = ref(false)
const versionsVisible = ref(false)
const trashVisible = ref(false)
const statsVisible = ref(false)
const shareVisible = ref(false)
const tagsVisible = ref(false)
const listVisible = ref(false)
const listTitle = ref('')
const quickList = ref<TreeNode[]>([])
const importInput = ref<HTMLInputElement | null>(null)
const backupInput = ref<HTMLInputElement | null>(null)

const activeKb = computed(() => knowledgeBases.value.find(item => item.id === activeKbId.value) || null)
const selectedNode = computed(() => nodes.value.find(item => item.id === selected.value?.id) || null)

function fail(error: unknown) { ElMessage.error(errorMessage(error)) }
function authenticated(_: string, currentUser: User) {
  token.value = localStorage.getItem('token')
  user.value = currentUser
  loadKnowledgeBases()
}
function logout() {
  localStorage.removeItem('token')
  token.value = null
  user.value = null
  knowledgeBases.value = []
  nodes.value = []
  selected.value = null
}

async function bootstrap() {
  if (!token.value || isPublicShare) return
  try {
    user.value = (await api.get('/auth/me')).data
    await loadKnowledgeBases()
  } catch { logout() }
}

async function loadKnowledgeBases(preferredId?: number) {
  loading.value = true
  try {
    knowledgeBases.value = (await api.get('/knowledge-bases')).data
    const nextId = preferredId || activeKbId.value || knowledgeBases.value[0]?.id
    if (nextId) await selectKnowledgeBase(nextId)
    else {
      activeKbId.value = null
      nodes.value = []
      selected.value = null
    }
  } catch (error) { fail(error) }
  finally { loading.value = false }
}

async function selectKnowledgeBase(id: number) {
  activeKbId.value = id
  selected.value = null
  await Promise.all([loadTree(), loadTags()])
}
async function loadTree() {
  if (activeKbId.value) nodes.value = (await api.get(`/documents/tree/${activeKbId.value}`)).data
}
async function loadTags() {
  if (activeKbId.value) tags.value = (await api.get(`/tags/knowledge-base/${activeKbId.value}`)).data
}
async function selectDocument(node: TreeNode) {
  if (node.is_folder) {
    selected.value = { ...node, content: '', is_deleted: false, created_at: node.updated_at, tags: [], is_favorite: false }
    return
  }
  try { selected.value = (await api.get(`/documents/${node.id}`)).data }
  catch (error) { fail(error) }
}

async function createKnowledgeBase() {
  try {
    const { value } = await ElMessageBox.prompt('知识库名称', '新建知识库', { inputPattern: /\S+/, inputErrorMessage: '名称不能为空' })
    const kb = (await api.post('/knowledge-bases', { name: value.trim(), description: '' })).data
    await loadKnowledgeBases(kb.id)
  } catch (error: any) { if (error !== 'cancel') fail(error) }
}
async function manageKnowledgeBase(action: string) {
  if (!activeKb.value) return
  try {
    if (action === 'rename') {
      const { value } = await ElMessageBox.prompt('新名称', '修改知识库', { inputValue: activeKb.value.name, inputPattern: /\S+/ })
      await api.put(`/knowledge-bases/${activeKb.value.id}`, { name: value.trim() })
      await loadKnowledgeBases(activeKb.value.id)
    } else if (action === 'delete') {
      await ElMessageBox.confirm(`确定删除“${activeKb.value.name}”及全部数据？`, '危险操作', { type: 'warning' })
      await api.delete(`/knowledge-bases/${activeKb.value.id}`)
      activeKbId.value = null
      await loadKnowledgeBases()
    } else if (action === 'export') {
      const data = (await api.get(`/transfer/knowledge-base/${activeKb.value.id}/export`, { responseType: 'blob' })).data
      downloadBlob(data, `${activeKb.value.name}.zip`)
    } else if (action === 'import') importInput.value?.click()
  } catch (error: any) { if (error !== 'cancel') fail(error) }
}

function parentForNewNode() {
  if (!selectedNode.value) return null
  return selectedNode.value.is_folder ? selectedNode.value.id : selectedNode.value.parent_id
}
async function createNode(isFolder: boolean) {
  if (!activeKbId.value) return ElMessage.warning('请先创建知识库')
  try {
    const { value } = await ElMessageBox.prompt(isFolder ? '文件夹名称' : '文档标题', isFolder ? '新建文件夹' : '新建文档', { inputPattern: /\S+/ })
    const node = (await api.post('/documents', {
      knowledge_base_id: activeKbId.value,
      parent_id: parentForNewNode(),
      title: value.trim(),
      content: isFolder ? '' : `# ${value.trim()}\n`,
      is_folder: isFolder
    })).data
    await loadTree()
    await selectDocument(node)
  } catch (error: any) { if (error !== 'cancel') fail(error) }
}
async function renameSelected() {
  if (!selected.value) return
  try {
    const { value } = await ElMessageBox.prompt('新名称', '重命名', { inputValue: selected.value.title, inputPattern: /\S+/ })
    await api.put(`/documents/${selected.value.id}`, { title: value.trim() })
    await loadTree()
    const node = nodes.value.find(item => item.id === selected.value?.id)
    if (node) await selectDocument(node)
  } catch (error: any) { if (error !== 'cancel') fail(error) }
}
async function moveNode(id: number, parentId: number | null, sortOrder: number) {
  try { await api.patch(`/documents/${id}/move`, { parent_id: parentId, sort_order: sortOrder }) }
  catch (error) { fail(error) }
  await loadTree()
}

async function autosave(payload: { title: string; content: string; tag_ids: number[] }) {
  if (!selected.value) return
  try {
    selected.value = (await api.put(`/documents/${selected.value.id}`, { ...payload, create_version: false })).data
    const node = nodes.value.find(item => item.id === selected.value?.id)
    if (node && selected.value) node.title = selected.value.title
  } catch (error) { ElMessage.error(`自动保存失败：${errorMessage(error)}`) }
}
async function saveVersion(payload: { title: string; content: string; tag_ids: number[] }) {
  if (!selected.value) return
  try {
    selected.value = (await api.put(`/documents/${selected.value.id}`, { ...payload, create_version: true, version_note: '手动保存' })).data
    await loadTree()
    ElMessage.success('已保存历史版本')
  } catch (error) { fail(error) }
}
async function toggleFavorite(value: boolean) {
  if (!selected.value) return
  try {
    if (value) await api.post(`/documents/${selected.value.id}/favorite`)
    else await api.delete(`/documents/${selected.value.id}/favorite`)
    selected.value.is_favorite = value
  } catch (error) { fail(error) }
}
async function removeSelected() {
  if (!selected.value) return
  try {
    await api.delete(`/documents/${selected.value.id}`)
    selected.value = null
    await loadTree()
    ElMessage.success('已移入回收站')
  } catch (error) { fail(error) }
}

async function selectSearch(item: SearchResult) {
  if (activeKbId.value !== item.knowledge_base_id) await selectKnowledgeBase(item.knowledge_base_id)
  const node = nodes.value.find(value => value.id === item.id)
  if (node) await selectDocument(node)
}
async function openQuickList(type: 'recent' | 'favorites') {
  try {
    listTitle.value = type === 'recent' ? '最近编辑' : '收藏文档'
    quickList.value = (await api.get(`/documents/${type}`)).data
    listVisible.value = true
  } catch (error) { fail(error) }
}
async function chooseQuickNode(node: TreeNode) {
  if (activeKbId.value !== node.knowledge_base_id) await selectKnowledgeBase(node.knowledge_base_id)
  const actual = nodes.value.find(item => item.id === node.id)
  if (actual) await selectDocument(actual)
  listVisible.value = false
}

async function createTag() {
  if (!activeKbId.value) return
  try {
    const { value } = await ElMessageBox.prompt('标签名称', '新建标签', { inputPattern: /\S+/ })
    await api.post('/tags', { knowledge_base_id: activeKbId.value, name: value.trim() })
    await loadTags()
  } catch (error: any) { if (error !== 'cancel') fail(error) }
}
async function deleteTag(id: number) {
  try { await api.delete(`/tags/${id}`); await loadTags() }
  catch (error) { fail(error) }
}
async function importKnowledgeBase(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !activeKbId.value) return
  try {
    const form = new FormData()
    form.append('file', file)
    const parent = parentForNewNode()
    if (parent) form.append('parent_id', String(parent))
    ElMessage.success((await api.post(`/transfer/knowledge-base/${activeKbId.value}/import`, form)).data.message)
    await loadTree()
  } catch (error) { fail(error) }
  finally { input.value = '' }
}
async function dataAction(action: string, event?: Event) {
  try {
    if (action === 'export') {
      const data = (await api.get('/backups/export', { responseType: 'blob' })).data
      downloadBlob(data, `knowledge-backup-${new Date().toISOString().slice(0, 10)}.json`)
    } else if (action === 'import') backupInput.value?.click()
    else if (action === 'password') {
      const oldPassword = (await ElMessageBox.prompt('当前密码', '修改密码', { inputType: 'password' })).value
      const newPassword = (await ElMessageBox.prompt('新密码（至少 6 位）', '修改密码', { inputType: 'password', inputPattern: /^.{6,128}$/ })).value
      await api.put('/auth/password', { old_password: oldPassword, new_password: newPassword })
      ElMessage.success('密码修改成功')
    } else if (action === 'restore' && event) {
      const input = event.target as HTMLInputElement
      const file = input.files?.[0]
      if (!file) return
      await ElMessageBox.confirm('备份将以新知识库方式合并，不覆盖现有数据。继续？', '导入备份')
      const form = new FormData(); form.append('file', file)
      ElMessage.success((await api.post('/backups/import', form)).data.message)
      input.value = ''
      await loadKnowledgeBases()
    }
  } catch (error: any) { if (error !== 'cancel') fail(error) }
}

window.addEventListener('auth-expired', logout)
onMounted(bootstrap)
</script>

<template>
  <PublicShareView v-if="isPublicShare" />
  <AuthView v-else-if="!token || !user" @authenticated="authenticated" />
  <div v-else class="app-shell" v-loading="loading">
    <header class="topbar">
      <strong>个人知识库</strong><span class="muted">{{ user.username }}</span>
      <div class="top-actions">
        <el-button @click="openQuickList('recent')">最近</el-button>
        <el-button @click="openQuickList('favorites')">收藏</el-button>
        <el-button @click="searchVisible = true">搜索</el-button>
        <el-button @click="statsVisible = true">统计</el-button>
        <el-button @click="trashVisible = true">回收站</el-button>
        <el-dropdown @command="dataAction">
          <el-button>数据与账号</el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="export">导出全部备份</el-dropdown-item>
            <el-dropdown-item command="import">导入全部备份</el-dropdown-item>
            <el-dropdown-item command="password" divided>修改密码</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <el-button @click="logout">退出</el-button>
      </div>
    </header>

    <main class="workspace">
      <aside class="kb-sidebar">
        <div class="panel-title"><span>知识库</span><el-button size="small" @click="createKnowledgeBase">新建</el-button></div>
        <button v-for="kb in knowledgeBases" :key="kb.id" class="kb-item" :class="{ active: activeKbId === kb.id }" @click="selectKnowledgeBase(kb.id)">
          <strong>{{ kb.name }}</strong><small>{{ kb.document_count }} 个节点</small>
        </button>
        <el-empty v-if="!knowledgeBases.length" description="暂无知识库" :image-size="55" />
      </aside>

      <aside class="tree-sidebar">
        <div class="panel-title">
          <span class="ellipsis">{{ activeKb?.name || '文档目录' }}</span>
          <el-dropdown v-if="activeKb" @command="manageKnowledgeBase">
            <el-button size="small">管理</el-button>
            <template #dropdown><el-dropdown-menu>
              <el-dropdown-item command="rename">修改名称</el-dropdown-item>
              <el-dropdown-item command="export">导出 ZIP</el-dropdown-item>
              <el-dropdown-item command="import">导入 MD/ZIP</el-dropdown-item>
              <el-dropdown-item command="delete" divided>删除知识库</el-dropdown-item>
            </el-dropdown-menu></template>
          </el-dropdown>
        </div>
        <div class="tree-actions">
          <el-button size="small" :disabled="!activeKbId" @click="createNode(false)">文档</el-button>
          <el-button size="small" :disabled="!activeKbId" @click="createNode(true)">文件夹</el-button>
          <el-button size="small" :disabled="!selected" @click="renameSelected">重命名</el-button>
          <el-button size="small" :disabled="!activeKbId" @click="tagsVisible = true">标签</el-button>
        </div>
        <DocumentTree :nodes="nodes" :selected-id="selected?.id || null" @select="selectDocument" @move="moveNode" />
      </aside>

      <MarkdownEditor :document="selected" :tags="tags" @autosave="autosave" @save-version="saveVersion"
        @favorite="toggleFavorite" @show-versions="versionsVisible = true" @show-share="shareVisible = true" @remove="removeSelected" />
    </main>

    <input ref="importInput" type="file" accept=".md,.zip" hidden @change="importKnowledgeBase" />
    <input ref="backupInput" type="file" accept=".json" hidden @change="dataAction('restore', $event)" />
    <SearchDialog v-model="searchVisible" :knowledge-base-id="activeKbId" @select="selectSearch" />
    <VersionDialog v-model="versionsVisible" :document-id="selected?.is_folder ? null : selected?.id || null" @restored="selected && selectDocument(selected)" />
    <TrashDialog v-model="trashVisible" :knowledge-base-id="activeKbId" @changed="loadTree" />
    <StatsDialog v-model="statsVisible" />
    <ShareDialog v-model="shareVisible" :document-id="selected?.is_folder ? null : selected?.id || null" />

    <el-dialog v-model="tagsVisible" title="标签管理" width="520px">
      <el-button type="primary" @click="createTag">新建标签</el-button>
      <div class="tag-list"><el-tag v-for="tag in tags" :key="tag.id" closable @close="deleteTag(tag.id)">{{ tag.name }}（{{ tag.document_count || 0 }}）</el-tag></div>
      <el-empty v-if="!tags.length" description="暂无标签" />
    </el-dialog>
    <el-dialog v-model="listVisible" :title="listTitle" width="620px">
      <button v-for="item in quickList" :key="item.id" class="quick-item" @click="chooseQuickNode(item)">
        <strong>{{ item.title }}</strong><span>{{ new Date(item.updated_at).toLocaleString() }}</span>
      </button>
      <el-empty v-if="!quickList.length" description="暂无内容" />
    </el-dialog>
  </div>
</template>
