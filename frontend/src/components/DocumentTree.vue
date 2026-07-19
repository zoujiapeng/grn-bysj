<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TreeNode } from '../types'

const props = defineProps<{ nodes: TreeNode[]; selectedId: number | null }>()
const emit = defineEmits<{
  select: [node: TreeNode]
  move: [documentId: number, parentId: number | null, sortOrder: number]
}>()

const treeRef = ref()
const filterText = ref('')

const treeData = computed(() => {
  const map = new Map<number, TreeNode>()
  props.nodes.forEach((node) => map.set(node.id, { ...node, children: [] }))
  const roots: TreeNode[] = []
  for (const node of map.values()) {
    const parent = node.parent_id ? map.get(node.parent_id) : undefined
    if (parent) parent.children!.push(node)
    else roots.push(node)
  }
  const sort = (items: TreeNode[]) => {
    items.sort((a, b) => Number(b.is_folder) - Number(a.is_folder) || a.sort_order - b.sort_order || a.title.localeCompare(b.title))
    items.forEach((item) => sort(item.children || []))
  }
  sort(roots)
  return roots
})

watch(filterText, (value) => treeRef.value?.filter(value))
watch(() => props.selectedId, (value) => value && treeRef.value?.setCurrentKey(value))

function filterNode(value: string, data: TreeNode) {
  return !value || data.title.toLowerCase().includes(value.toLowerCase())
}

function nodeDrop(draggingNode: any, dropNode: any, dropType: 'before' | 'after' | 'inner') {
  const dragged = draggingNode.data as TreeNode
  const target = dropNode.data as TreeNode
  let parentId: number | null = null
  let sortOrder = target.sort_order
  if (dropType === 'inner') parentId = target.id
  else {
    parentId = target.parent_id
    if (dropType === 'after') sortOrder += 1
  }
  emit('move', dragged.id, parentId, sortOrder)
}

function allowDrop(_: any, dropNode: any, type: string) {
  return type !== 'inner' || dropNode.data.is_folder
}
</script>

<template>
  <div class="document-tree">
    <el-input v-model="filterText" placeholder="筛选目录" clearable size="small" />
    <el-tree
      ref="treeRef"
      :data="treeData"
      node-key="id"
      highlight-current
      default-expand-all
      draggable
      :allow-drop="allowDrop"
      :filter-node-method="filterNode"
      :expand-on-click-node="false"
      @node-click="(node: TreeNode) => emit('select', node)"
      @node-drop="nodeDrop"
    >
      <template #default="{ data }">
        <span class="tree-label" :title="data.title">
          <span>{{ data.is_folder ? '📁' : '📄' }}</span>
          <span>{{ data.title }}</span>
        </span>
      </template>
    </el-tree>
    <el-empty v-if="nodes.length === 0" description="暂无文档" :image-size="60" />
  </div>
</template>
