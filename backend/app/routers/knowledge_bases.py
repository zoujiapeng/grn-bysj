from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Attachment, Document, KnowledgeBase, User
from ..schemas import KnowledgeBaseCreate, KnowledgeBaseOut, KnowledgeBaseUpdate
from ..utils import add_log, get_owned_kb


router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])


def to_out(kb: KnowledgeBase, count: int = 0) -> KnowledgeBaseOut:
    data = KnowledgeBaseOut.model_validate(kb)
    data.document_count = count
    return data


@router.get("", response_model=list[KnowledgeBaseOut])
def list_knowledge_bases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(KnowledgeBase, func.count(Document.id))
        .outerjoin(Document, (Document.knowledge_base_id == KnowledgeBase.id) & (Document.is_deleted.is_(False)))
        .where(KnowledgeBase.owner_id == user.id)
        .group_by(KnowledgeBase.id)
        .order_by(KnowledgeBase.updated_at.desc())
    ).all()
    return [to_out(kb, count) for kb, count in rows]


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = KnowledgeBase(owner_id=user.id, **payload.model_dump())
    db.add(kb)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="同名知识库已存在")
    add_log(db, user.id, "create", "knowledge_base", kb.id, kb.name)
    db.commit()
    db.refresh(kb)
    return to_out(kb)


@router.put("/{kb_id}", response_model=KnowledgeBaseOut)
def update_knowledge_base(
    kb_id: int,
    payload: KnowledgeBaseUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_owned_kb(db, kb_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(kb, field, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="同名知识库已存在")
    add_log(db, user.id, "update", "knowledge_base", kb.id, kb.name)
    db.commit()
    db.refresh(kb)
    count = db.scalar(select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id, Document.is_deleted.is_(False))) or 0
    return to_out(kb, count)


@router.delete("/{kb_id}")
def delete_knowledge_base(
    kb_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_owned_kb(db, kb_id, user)
    name = kb.name
    attachments = db.scalars(
        select(Attachment)
        .join(Document, Attachment.document_id == Document.id)
        .where(Document.knowledge_base_id == kb.id)
    ).all()
    for attachment in attachments:
        (Path(settings.upload_dir) / attachment.relative_path).unlink(missing_ok=True)
    db.delete(kb)
    add_log(db, user.id, "delete", "knowledge_base", kb_id, name)
    db.commit()
    return {"message": "知识库已删除"}
