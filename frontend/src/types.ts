export interface User {
  id: number
  username: string
  email: string
  is_admin: boolean
  created_at: string
}

export interface KnowledgeBase {
  id: number
  name: string
  description: string
  is_public: boolean
  document_count: number
  created_at: string
  updated_at: string
}

export interface TreeNode {
  id: number
  knowledge_base_id: number
  parent_id: number | null
  title: string
  is_folder: boolean
  sort_order: number
  updated_at: string
  children?: TreeNode[]
}

export interface Tag {
  id: number
  knowledge_base_id: number
  name: string
  document_count?: number
  created_at: string
}

export interface DocumentDetail extends TreeNode {
  content: string
  is_deleted: boolean
  created_at: string
  tags: Tag[]
  is_favorite: boolean
}

export interface Version {
  id: number
  document_id: number
  version_number: number
  title: string
  content: string
  note: string
  created_at: string
}

export interface Attachment {
  id: number
  document_id: number
  original_name: string
  mime_type: string
  size_bytes: number
  created_at: string
  url: string
}

export interface SearchResult {
  id: number
  knowledge_base_id: number
  knowledge_base_name: string
  title: string
  snippet: string
  updated_at: string
  tags: string[]
}
