# API 概览

服务启动后访问 `/docs` 可查看并在线调用完整 OpenAPI 文档。

| 模块 | 路径前缀 | 主要能力 |
|---|---|---|
| 认证 | `/api/auth` | 注册、登录、当前用户、改密 |
| 知识库 | `/api/knowledge-bases` | 增删改查、节点统计 |
| 文档 | `/api/documents` | 树、详情、搜索、移动、版本、收藏、回收站 |
| 标签 | `/api/tags` | 标签管理与使用次数 |
| 附件 | `/api/attachments` | 上传、列表、删除 |
| 分享 | `/api/shares` | 创建、列出、撤销 |
| 公开访问 | `/api/public/share/{token}` | 阅读和下载分享文档 |
| 导入导出 | `/api/transfer` | Markdown/ZIP 导入、知识库导出 |
| 备份 | `/api/backups` | 全量 JSON 备份与合并恢复 |
| 统计 | `/api/stats` | 数量、空间、活动日志 |

认证方式：

```http
Authorization: Bearer <JWT>
```
