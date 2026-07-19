import re
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Document, KnowledgeBase, OperationLog, User


def get_owned_kb(db: Session, kb_id: int, user: User) -> KnowledgeBase:
    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == user.id))
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


def get_owned_document(db: Session, document_id: int, user: User, include_deleted: bool = False) -> Document:
    stmt = (
        select(Document)
        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
        .where(Document.id == document_id, KnowledgeBase.owner_id == user.id)
    )
    if not include_deleted:
        stmt = stmt.where(Document.is_deleted.is_(False))
    document = db.scalar(stmt)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


def add_log(db: Session, user_id: int, action: str, target_type: str = "", target_id: int | None = None, detail: str = "") -> None:
    db.add(OperationLog(user_id=user_id, action=action, target_type=target_type, target_id=target_id, detail=detail[:500]))


def safe_filename(value: str, fallback: str = "untitled") -> str:
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value).strip(" .")
    return value[:100] or fallback


def unique_path(base: Path, name: str) -> Path:
    candidate = base / name
    stem, suffix = candidate.stem, candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = base / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate
