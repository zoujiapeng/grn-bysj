# 基于 Web 的 Markdown 个人知识库管理系统

一个可在 Linux 上独立部署、可长期实际使用的 Markdown 个人知识库。项目面向本科毕业设计，采用容易理解和修改的 Vue 3 + FastAPI 架构，不依赖付费云服务，也不以复杂界面或 AI 功能掩盖基础业务缺失。

## 项目完成度

本仓库提供的是完整应用而不是静态页面或接口演示，包含：

- 多用户注册、登录、JWT 认证和用户数据隔离
- 多知识库创建、修改、删除和文档数量统计
- 文件夹与文档共用的多级目录树
- 拖拽移动和循环父子关系校验
- Markdown 编辑、实时预览和约 1 秒防抖自动保存
- 手动保存历史版本、版本查看和恢复
- 标题、正文、标签联合全文搜索
- 标签管理、收藏、最近编辑
- 图片及普通附件上传，并自动插入 Markdown 链接
- 递归回收站、恢复和永久删除
- 只读分享链接、访问密码、过期时间、下载权限
- 单篇 Markdown / ZIP 批量导入
- 整个知识库导出为 ZIP
- 全量 JSON 备份和合并恢复
- 系统统计、附件空间统计和最近操作日志
- Docker Compose、Nginx 和 Linux 持久化部署
- FastAPI OpenAPI 接口文档和后端主流程测试

## 页面结构

```text
顶部：最近、收藏、搜索、统计、回收站、备份
左栏：知识库列表
中栏：多级目录树和文档管理
右侧：标题、标签、Markdown 编辑、预览、版本、附件和分享
```

前端故意保持简单，主要使用标准 Element Plus 组件，便于学生修改和在答辩时解释。

## 技术栈

### 前端

- Vue 3
- TypeScript
- Vite
- Element Plus
- Axios
- Marked + DOMPurify

### 后端

- Python 3.12
- FastAPI
- SQLAlchemy 2
- SQLite（默认）
- JWT + bcrypt

### 部署

- Docker Compose
- Nginx
- Linux 本地目录持久化

## 最快启动方式

环境要求：Linux、Docker、Docker Compose 插件。

```bash
git clone https://github.com/zoujiapeng/grn-bysj.git
cd grn-bysj
cp .env.example .env
```

编辑 `.env`，至少修改：

```env
JWT_SECRET=替换成足够长的随机字符串
```

启动：

```bash
docker compose up -d --build
```

浏览器访问：

```text
http://服务器IP:8080
```

查看状态：

```bash
docker compose ps
docker compose logs -f
```

停止：

```bash
docker compose down
```

数据保存在仓库根目录的 `data/` 中，执行 `docker compose down` 不会删除数据。

## Linux 非 Docker 开发运行

### 1. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data/uploads
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端接口文档：

```text
http://localhost:8000/docs
```

### 2. 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

访问：

```text
http://localhost:5173
```

也可以在 Linux 中运行：

```bash
./scripts/dev.sh
```

## 默认数据与账号规则

- 系统不内置默认账号。
- 第一个注册的账号会被标记为管理员。
- 每个用户只能访问自己的知识库、文档、附件和分享配置。
- SQLite 数据库默认位于 `data/knowledge.db`。
- 附件默认位于 `data/uploads/`。

## 备份策略

系统内提供两类备份：

1. 页面中的“导出全部备份”：导出结构化 JSON，可在系统中重新导入。
2. Linux 文件级备份：备份数据库和全部附件。

```bash
./scripts/backup-data.sh
```

备份文件默认写入 `backups/`。

## 数据库切换

默认配置适合个人和毕业设计部署：

```env
DATABASE_URL=sqlite:////data/knowledge.db
```

SQLAlchemy 已将业务代码与数据库访问分离。如需 PostgreSQL，可安装 PostgreSQL 驱动并将环境变量替换为对应连接字符串。对于本科答辩和单机部署，不建议无必要引入数据库集群。

## 测试

后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

前端：

```bash
cd frontend
npm install
npm run build
```

完整验收说明见 [docs/TESTING.md](docs/TESTING.md)。

## 项目目录

```text
grn-bysj/
├── backend/
│   ├── app/
│   │   ├── routers/          # 业务接口
│   │   ├── config.py         # 环境配置
│   │   ├── database.py       # 数据库连接
│   │   ├── models.py         # 数据表
│   │   ├── schemas.py        # 请求与响应结构
│   │   └── main.py           # FastAPI 入口
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/       # 简单可拆改的页面组件
│       ├── api.ts
│       ├── types.ts
│       └── App.vue
├── deploy/nginx.conf
├── docs/
├── scripts/
├── data/
└── docker-compose.yml
```

## 设计取舍

本项目没有加入微服务、Kubernetes、Elasticsearch、多人实时协作或必须联网的 AI 模块。这些功能会显著增加部署和答辩解释成本，但不会改善个人知识库最核心的使用逻辑。

当前实现优先保证：

- 数据能保存和迁移
- 目录结构真实可用
- 搜索和版本恢复可用
- 删除操作可挽回
- 分享权限可控制
- Linux 可以一条命令部署
- 每个模块保持学生能够理解的复杂度

详细架构与答辩演示流程见 [docs/PROJECT_DESIGN.md](docs/PROJECT_DESIGN.md)。
