import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Document, DocumentVersion, KnowledgeBase, Tag, User
from ..utils import add_log, safe_filename


router = APIRouter(prefix="/backups", tags=["备份"])


@router.get("/export")
def export_backup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kbs = db.scalars(
        select(KnowledgeBase)
        .options(
            selectinload(KnowledgeBase.tags),
            selectinload(KnowledgeBase.documents).selectinload(Document.tags),
            selectinload(KnowledgeBase.documents).selectinload(Document.versions),
        )
        .where(KnowledgeBase.owner_id == user.id)
    ).unique().all()
    payload = {
        "format": "grn-knowledge-backup-v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "knowledge_bases": [],
    }
    for kb in kbs:
        payload["knowledge_bases"].append(
            {
                "name": kb.name,
                "description": kb.description,
                "is_public": kb.is_public,
                "tags": [{"id": tag.id, "name": tag.name} for tag in kb.tags],
                "documents": [
                    {
                        "old_id": document.id,
                        "parent_old_id": document.parent_id,
                        "title": document.title,
                        "content": document.content,
                        "is_folder": document.is_folder,
                        "sort_order": document.sort_order,
                        "is_deleted": document.is_deleted,
                        "tags": [tag.name for tag in document.tags],
                        "versions": [
                            {
                                "version_number": version.version_number,
                                "title": version.title,
                                "content": version.content,
                                "note": version.note,
                            }
                            for version in document.versions
                        ],
                    }
                    for document in kb.documents
                ],
            }
        )
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"knowledge-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/import")
async def import_backup(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw = await file.read(50 * 1024 * 1024 + 1)
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="备份文件不能超过 50MB")
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="备份文件格式错误")
    if payload.get("format") != "grn-knowledge-backup-v1":
        raise HTTPException(status_code=400, detail="不支持的备份版本")
    imported = 0
    for kb_data in payload.get("knowledge_bases", []):
        base_name = safe_filename(str(kb_data.get("name", "导入知识库")), "导入知识库")
        name = base_name
        suffix = 2
        while db.scalar(select(KnowledgeBase.id).where(KnowledgeBase.owner_id == user.id, KnowledgeBase.name == name)):
            name = f"{base_name} ({suffix})"
            suffix += 1
        kb = KnowledgeBase(
            owner_id=user.id,
            name=name,
            description=str(kb_data.get("description", ""))[:500],
            is_public=False,
        )
        db.add(kb)
        db.flush()
        tags_by_name: dict[str, Tag] = {}
        for tag_data in kb_data.get("tags", []):
            tag_name = str(tag_data.get("name", "")).strip()[:50]
            if tag_name and tag_name not in tags_by_name:
                tag = Tag(knowledge_base_id=kb.id, name=tag_name)
                db.add(tag)
                db.flush()
                tags_by_name[tag_name] = tag
        id_map: dict[int, int] = {}
        pending = list(kb_data.get("documents", []))
        for _ in range(len(pending) + 1):
            next_pending = []
            progressed = False
            for doc_data in pending:
                old_parent = doc_data.get("parent_old_id")
                if old_parent is not None and int(old_parent) not in id_map:
                    next_pending.append(doc_data)
                    continue
                document = Document(
                    knowledge_base_id=kb.id,
                    parent_id=id_map.get(int(old_parent)) if old_parent is not None else None,
                    title=str(doc_data.get("title", "未命名"))[:255],
                    content=str(doc_data.get("content", "")),
                    is_folder=bool(doc_data.get("is_folder", False)),
                    sort_order=int(doc_data.get("sort_order", 0)),
                    is_deleted=bool(doc_data.get("is_deleted", False)),
                )
                db.add(document)
                db.flush()
                old_id = int(doc_data.get("old_id", document.id))
                id_map[old_id] = document.id
                for tag_name in doc_data.get("tags", []):
                    if tag_name in tags_by_name:
                        document.tags.append(tags_by_name[tag_name])
                for version_data in doc_data.get("versions", []):
                    db.add(
                        DocumentVersion(
                            document_id=document.id,
                            version_number=int(version_data.get("version_number", 1)),
                            title=str(version_data.get("title", document.title))[:255],
                            content=str(version_data.get("content", "")),
                            note=str(version_data.get("note", ""))[:255],
                        )
                    )
                imported += 1
                progressed = True
            pending = next_pending
            if not pending or not progressed:
                break
        for doc_data in pending:
            document = Document(
                knowledge_base_id=kb.id,
                parent_id=None,
                title=str(doc_data.get("title", "未命名"))[:255],
                content=str(doc_data.get("content", "")),
                is_folder=bool(doc_data.get("is_folder", False)),
            )
            db.add(document)
            imported += 1
    add_log(db, user.id, "restore_backup", "backup", None, f"{imported} documents")
    db.commit()
    return {"message": f"备份导入完成，共恢复 {imported} 个节点", "imported": imported}
