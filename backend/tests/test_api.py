import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test-data/test.db"
os.environ["UPLOAD_DIR"] = "./test-data/uploads"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    Base.metadata.drop_all(bind=engine)
    path = Path("test-data/test.db")
    path.unlink(missing_ok=True)


def auth_headers():
    response = client.post(
        "/api/auth/register",
        json={"username": "student", "email": "student@example.com", "password": "123456"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_core_workflow():
    headers = auth_headers()
    kb = client.post("/api/knowledge-bases", headers=headers, json={"name": "毕业设计", "description": "测试"})
    assert kb.status_code == 201
    kb_id = kb.json()["id"]

    folder = client.post(
        "/api/documents",
        headers=headers,
        json={"knowledge_base_id": kb_id, "title": "系统设计", "is_folder": True},
    )
    assert folder.status_code == 201

    document = client.post(
        "/api/documents",
        headers=headers,
        json={
            "knowledge_base_id": kb_id,
            "parent_id": folder.json()["id"],
            "title": "需求分析",
            "content": "# 需求分析\nMarkdown 知识库",
        },
    )
    assert document.status_code == 201
    document_id = document.json()["id"]

    update = client.put(
        f"/api/documents/{document_id}",
        headers=headers,
        json={"content": "# 已修改", "create_version": True, "version_note": "第一次修改"},
    )
    assert update.status_code == 200

    search = client.get("/api/documents/search?q=修改", headers=headers)
    assert search.status_code == 200
    assert search.json()[0]["id"] == document_id

    trash = client.delete(f"/api/documents/{document_id}", headers=headers)
    assert trash.status_code == 200
    restore = client.post(f"/api/documents/{document_id}/restore", headers=headers)
    assert restore.status_code == 200


def test_extended_features():
    login = client.post('/api/auth/login', json={'username': 'student', 'password': '123456'})
    headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
    kb_id = client.get('/api/knowledge-bases', headers=headers).json()[0]['id']
    tree = client.get(f'/api/documents/tree/{kb_id}', headers=headers).json()
    document_id = next(item['id'] for item in tree if not item['is_folder'])

    tag = client.post('/api/tags', headers=headers, json={'knowledge_base_id': kb_id, 'name': 'Markdown'})
    assert tag.status_code == 201
    update = client.put(
        f'/api/documents/{document_id}',
        headers=headers,
        json={'tag_ids': [tag.json()['id']]},
    )
    assert update.status_code == 200
    assert update.json()['tags'][0]['name'] == 'Markdown'

    assert client.post(f'/api/documents/{document_id}/favorite', headers=headers).status_code == 200
    favorites = client.get('/api/documents/favorites', headers=headers).json()
    assert any(item['id'] == document_id for item in favorites)

    upload = client.post(
        f'/api/attachments/document/{document_id}',
        headers=headers,
        files={'file': ('diagram.txt', b'attachment-data', 'text/plain')},
    )
    assert upload.status_code == 201
    assert upload.json()['size_bytes'] == 15

    share = client.post('/api/shares', headers=headers, json={'document_id': document_id, 'allow_download': True})
    assert share.status_code == 201
    token = share.json()['token']
    public = client.get(f'/api/public/share/{token}')
    assert public.status_code == 200
    assert public.json()['title']
    assert client.get(f'/api/public/share/{token}/download').status_code == 200

    exported = client.get(f'/api/transfer/knowledge-base/{kb_id}/export', headers=headers)
    assert exported.status_code == 200
    assert exported.headers['content-type'].startswith('application/zip')
    assert exported.content[:2] == b'PK'

    backup = client.get('/api/backups/export', headers=headers)
    assert backup.status_code == 200
    assert backup.json()['format'] == 'grn-knowledge-backup-v1'
    restored = client.post(
        '/api/backups/import',
        headers=headers,
        files={'file': ('backup.json', backup.content, 'application/json')},
    )
    assert restored.status_code == 200
    assert restored.json()['imported'] >= 1

    stats = client.get('/api/stats', headers=headers)
    assert stats.status_code == 200
    assert stats.json()['counts']['documents'] >= 1

    attachment_path = Path('test-data/uploads') / upload.json()['url'].removeprefix('/uploads/')
    assert attachment_path.exists()
    assert client.delete(f'/api/documents/{document_id}', headers=headers).status_code == 200
    assert client.delete(f'/api/documents/{document_id}/permanent', headers=headers).status_code == 200
    assert not attachment_path.exists()
