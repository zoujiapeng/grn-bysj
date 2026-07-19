# 测试说明

## 后端自动测试

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

测试覆盖注册、创建知识库、创建树形目录、保存版本、全文搜索、回收站和恢复的主要流程。

## 前端构建检查

```bash
cd frontend
npm install
npm run build
```

## Docker 验收

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8080/health
```

浏览器打开 `http://localhost:8080`，完成以下验收：

- 注册、登录和退出正常。
- 创建知识库、文件夹、文档正常。
- 自动保存后刷新页面内容不丢失。
- 搜索、版本、附件、分享、回收站可用。
- 导出后 ZIP 内存在 Markdown 文件。
- 重启容器后数据仍存在于 `data/`。
