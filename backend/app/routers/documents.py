from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Document, DocumentVersion, Favorite, KnowledgeBase, Tag, User
from ..schemas import (
    DocumentCreate,
    DocumentMove,
    DocumentOut,
    DocumentUpdate,
    SearchResult,
    TreeNodeOut,
    VersionOut,
)
from ..utils import add_log, get_owned_document, get_owned_kb


router = APIRouter(prefix="/documents", tags=["文档"])


def next_version_number(db: Session, document_id: int) -> int:
    value = db.scalar(select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == document_id))
    return (value or 0) + 1


def create_version(db: Session, document: Document, note: str = "") -> DocumentVersion:
    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version_number(db, document.id),
        title=document.title,
        content=document.content,
        note=note,
    )
    db.add(version)
    return version


def document_out(document: Document, user_id: int, db: Session) -> DocumentOut:
    favorite = db.scalar(
        select(Favorite.id).where(Favorite.user_id == user_id, Favorite.document_id == document.id)
    )
    data = DocumentOut.model_validate(document)
    data.is_favorite = favorite is not None
    return data


def all_descendant_ids(db: Session, document: Document) -> list[int]:
    documents = db.scalars(
        select(Document).where(Document.knowledge_base_id == document.knowledge_base_id)
    ).all()
    children: dict[int | None, list[int]] = {}
    for item in documents:
        children.setdefault(item.parent_id, []).append(item.id)
    result: list[int] = []
    stack = [document.id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.append(current)
        stack.extend(children.get(current, []))
    return result


@router.get("/tree/{kb_id}", response_model=list[TreeNodeOut])
def get_tree(kb_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_kb(db, kb_id, user)
    documents = db.scalars(
        select(Document)
        .where(Document.knowledge_base_id == kb_id, Document.is_deleted.is_(False))
        .order_by(Document.parent_id, Document.sort_order, Document.title)
    ).all()
    return documents


@router.get("/recent", response_model=list[TreeNodeOut])
def recent_documents(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Document)
        .join(KnowledgeBase)
        .where(
            KnowledgeBase.owner_id == user.id,
            Document.is_deleted.is_(False),
            Document.is_folder.is_(False),
        )
        .order_by(Document.updated_at.desc())
        .limit(limit)
    ).all()


@router.get("/favorites", response_model=list[TreeNodeOut])
def favorite_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Document)
        .join(Favorite, Favorite.document_id == Document.id)
        .where(Favorite.user_id == user.id, Document.is_deleted.is_(False))
        .order_by(Favorite.created_at.desc())
    ).all()


@router.get("/search", response_model=list[SearchResult])
def search_documents(
    q: str = Query(min_length=1, max_length=100),
    kb_id: int | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pattern = f"%{q.strip()}%"
    stmt = (
        select(Document)
        .options(selectinload(Document.tags), selectinload(Document.knowledge_base))
        .join(KnowledgeBase)
        .where(
            KnowledgeBase.owner_id == user.id,
            Document.is_deleted.is_(False),
            Document.is_folder.is_(False),
            or_(
                Document.title.ilike(pattern),
                Document.content.ilike(pattern),
                Document.tags.any(Tag.name.ilike(pattern)),
            ),
        )
        .order_by(Document.updated_at.desc())
        .limit(limit)
    )
    if kb_id is not None:
        get_owned_kb(db, kb_id, user)
        stmt = stmt.where(Document.knowledge_base_id == kb_id)
    documents = db.scalars(stmt).unique().all()
    results: list[SearchResult] = []
    keyword = q.strip().lower()
    for document in documents:
        plain = document.content.replace("\n", " ")
        pos = plain.lower().find(keyword)
        start = max(0, pos - 50) if pos >= 0 else 0
        snippet = plain[start : start + 180]
        results.append(
            SearchResult(
                id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                knowledge_base_name=document.knowledge_base.name,
                title=document.title,
                snippet=snippet,
                updated_at=document.updated_at,
                tags=[tag.name for tag in document.tags],
            )
        )
    return results


@router.get("/trash", response_model=list[TreeNodeOut])
def trash_documents(
    kb_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Document)
        .join(KnowledgeBase)
        .where(KnowledgeBase.owner_id == user.id, Document.is_deleted.is_(True))
        .order_by(Document.deleted_at.desc())
    )
    if kb_id is not None:
        get_owned_kb(db, kb_id, user)
        stmt = stmt.where(Document.knowledge_base_id == kb_id)
    return db.scalars(stmt).all()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_kb(db, payload.knowledge_base_id, user)
    if payload.parent_id is not None:
        parent = get_owned_document(db, payload.parent_id, user)
        if parent.knowledge_base_id != payload.knowledge_base_id or not parent.is_folder:
            raise HTTPException(status_code=400, detail="父节点必须是同一知识库中的文件夹")
    document = Document(**payload.model_dump())
    db.add(document)
    db.flush()
    if not document.is_folder:
        create_version(db, document, "创建文档")
    add_log(db, user.id, "create", "folder" if document.is_folder else "document", document.id, document.title)
    db.commit()
    db.refresh(document)
    document = db.scalar(select(Document).options(selectinload(Document.tags)).where(Document.id == document.id))
    return document_out(document, user.id, db)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_document(db, document_id, user)
    document = db.scalar(
        select(Document).options(selectinload(Document.tags)).where(Document.id == document_id)
    )
    return document_out(document, user.id, db)


@router.put("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, document_id, user)
    if document.is_folder and payload.content is not None:
        raise HTTPException(status_code=400, detail="文件夹不能保存正文")
    old_title = document.title
    old_tag_ids = {tag.id for tag in document.tags}
    if payload.title is not None:
        document.title = payload.title.strip()
    if payload.content is not None:
        document.content = payload.content
    if payload.tag_ids is not None:
        tags = db.scalars(
            select(Tag).where(
                Tag.id.in_(payload.tag_ids),
                Tag.knowledge_base_id == document.knowledge_base_id,
            )
        ).all() if payload.tag_ids else []
        if len(tags) != len(set(payload.tag_ids)):
            raise HTTPException(status_code=400, detail="包含无效标签")
        document.tags = tags
    if payload.create_version and not document.is_folder:
        create_version(db, document, payload.version_note or "手动保存")
        add_log(db, user.id, "save_version", "document", document.id, document.title)
    else:
        new_tag_ids = {tag.id for tag in document.tags}
        if document.title != old_title or new_tag_ids != old_tag_ids:
            add_log(db, user.id, "update_metadata", "document", document.id, document.title)
    db.commit()
    document = db.scalar(
        select(Document).options(selectinload(Document.tags)).where(Document.id == document.id)
    )
    return document_out(document, user.id, db)


@router.patch("/{document_id}/move", response_model=TreeNodeOut)
def move_document(
    document_id: int,
    payload: DocumentMove,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, document_id, user)
    if payload.parent_id == document.id:
        raise HTTPException(status_code=400, detail="不能移动到自身")
    if payload.parent_id is not None:
        parent = get_owned_document(db, payload.parent_id, user)
        if parent.knowledge_base_id != document.knowledge_base_id or not parent.is_folder:
            raise HTTPException(status_code=400, detail="目标父节点无效")
        if parent.id in all_descendant_ids(db, document):
            raise HTTPException(status_code=400, detail="不能移动到自己的子目录")
    document.parent_id = payload.parent_id
    document.sort_order = payload.sort_order
    add_log(db, user.id, "move", "document", document.id, document.title)
    db.commit()
    db.refresh(document)
    return document


@router.post("/{document_id}/favorite")
def add_favorite(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_document(db, document_id, user)
    exists = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.document_id == document_id))
    if not exists:
        db.add(Favorite(user_id=user.id, document_id=document_id))
        db.commit()
    return {"message": "已收藏"}


@router.delete("/{document_id}/favorite")
def remove_favorite(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.document_id == document_id))
    if favorite:
        db.delete(favorite)
        db.commit()
    return {"message": "已取消收藏"}


@router.get("/{document_id}/versions", response_model=list[VersionOut])
def list_versions(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_document(db, document_id, user, include_deleted=True)
    return db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    ).all()


@router.post("/{document_id}/versions/{version_id}/restore", response_model=DocumentOut)
def restore_version(
    document_id: int,
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, document_id, user)
    version = db.scalar(
        select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == document.id)
    )
    if not version:
        raise HTTPException(status_code=404, detail="历史版本不存在")
    create_version(db, document, f"恢复版本 {version.version_number} 前快照")
    document.title = version.title
    document.content = version.content
    add_log(db, user.id, "restore_version", "document", document.id, str(version.version_number))
    db.commit()
    document = db.scalar(select(Document).options(selectinload(Document.tags)).where(Document.id == document.id))
    return document_out(document, user.id, db)


@router.delete("/{document_id}")
def move_to_trash(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, document_id, user)
    ids = all_descendant_ids(db, document)
    now = datetime.now(timezone.utc)
    items = db.scalars(select(Document).where(Document.id.in_(ids))).all()
    for item in items:
        item.is_deleted = True
        item.deleted_at = now
    add_log(db, user.id, "trash", "document", document.id, document.title)
    db.commit()
    return {"message": f"已将 {len(items)} 个节点移入回收站"}


@router.post("/{document_id}/restore")
def restore_from_trash(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, document_id, user, include_deleted=True)
    ids = all_descendant_ids(db, document)
    items = db.scalars(select(Document).where(Document.id.in_(ids))).all()
    if document.parent_id:
        parent = db.get(Document, document.parent_id)
        if not parent or parent.is_deleted:
            document.parent_id = None
    for item in items:
        item.is_deleted = False
        item.deleted_at = None
    add_log(db, user.id, "restore", "document", document.id, document.title)
    db.commit()
    return {"message": f"已恢复 {len(items)} 个节点"}


@router.delete("/{document_id}/permanent")
def permanent_delete(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, document_id, user, include_deleted=True)
    if not document.is_deleted:
        raise HTTPException(status_code=400, detail="请先将文档移入回收站")
    ids = all_descendant_ids(db, document)
    items = db.scalars(select(Document).where(Document.id.in_(ids))).all()
    for item in items:
        for attachment in item.attachments:
            (Path(settings.upload_dir) / attachment.relative_path).unlink(missing_ok=True)
    for item in sorted(items, key=lambda x: x.id, reverse=True):
        db.delete(item)
    add_log(db, user.id, "permanent_delete", "document", document.id, document.title)
    db.commit()
    return {"message": "已永久删除"}
