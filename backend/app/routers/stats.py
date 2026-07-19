from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Attachment, Document, KnowledgeBase, OperationLog, ShareLink, Tag, User


router = APIRouter(prefix="/stats", tags=["统计"])


@router.get("")
def get_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb_ids = select(KnowledgeBase.id).where(KnowledgeBase.owner_id == user.id)
    document_ids = select(Document.id).where(Document.knowledge_base_id.in_(kb_ids))
    counts = {
        "knowledge_bases": db.scalar(select(func.count(KnowledgeBase.id)).where(KnowledgeBase.owner_id == user.id)) or 0,
        "documents": db.scalar(select(func.count(Document.id)).where(Document.knowledge_base_id.in_(kb_ids), Document.is_folder.is_(False), Document.is_deleted.is_(False))) or 0,
        "folders": db.scalar(select(func.count(Document.id)).where(Document.knowledge_base_id.in_(kb_ids), Document.is_folder.is_(True), Document.is_deleted.is_(False))) or 0,
        "trash": db.scalar(select(func.count(Document.id)).where(Document.knowledge_base_id.in_(kb_ids), Document.is_deleted.is_(True))) or 0,
        "tags": db.scalar(select(func.count(Tag.id)).where(Tag.knowledge_base_id.in_(kb_ids))) or 0,
        "attachments": db.scalar(select(func.count(Attachment.id)).where(Attachment.document_id.in_(document_ids))) or 0,
        "shares": db.scalar(select(func.count(ShareLink.id)).where(ShareLink.document_id.in_(document_ids))) or 0,
    }
    storage = db.scalar(select(func.sum(Attachment.size_bytes)).where(Attachment.document_id.in_(document_ids))) or 0
    per_kb = db.execute(
        select(KnowledgeBase.name, func.count(Document.id))
        .outerjoin(Document, (Document.knowledge_base_id == KnowledgeBase.id) & (Document.is_deleted.is_(False)))
        .where(KnowledgeBase.owner_id == user.id)
        .group_by(KnowledgeBase.id)
        .order_by(func.count(Document.id).desc())
    ).all()
    recent_logs = db.scalars(
        select(OperationLog)
        .where(OperationLog.user_id == user.id)
        .order_by(OperationLog.created_at.desc())
        .limit(20)
    ).all()
    return {
        "counts": counts,
        "storage_bytes": storage,
        "knowledge_bases": [{"name": name, "count": count} for name, count in per_kb],
        "recent_activity": [
            {
                "action": item.action,
                "target_type": item.target_type,
                "detail": item.detail,
                "created_at": item.created_at,
            }
            for item in recent_logs
        ],
    }
