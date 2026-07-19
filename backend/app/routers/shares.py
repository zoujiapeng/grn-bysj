from datetime import datetime, timezone
from secrets import token_urlsafe
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user
from ..models import Document, KnowledgeBase, ShareLink, User
from ..schemas import PublicDocumentOut, ShareCreate, ShareOut
from ..security import hash_password, verify_password
from ..utils import add_log, get_owned_document, safe_filename


router = APIRouter(prefix="/shares", tags=["分享"])
public_router = APIRouter(prefix="/public", tags=["公开访问"])


def share_out(item: ShareLink) -> ShareOut:
    return ShareOut(
        id=item.id,
        document_id=item.document_id,
        token=item.token,
        expires_at=item.expires_at,
        allow_download=item.allow_download,
        password_protected=bool(item.password_hash),
        created_at=item.created_at,
    )


def ensure_available(item: ShareLink, password: str | None) -> None:
    now = datetime.now(timezone.utc)
    expires = item.expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires < now:
        raise HTTPException(status_code=410, detail="分享链接已过期")
    if item.password_hash and (not password or not verify_password(password, item.password_hash)):
        raise HTTPException(status_code=401, detail="访问密码错误")


@router.get("", response_model=list[ShareOut])
def list_shares(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(
        select(ShareLink)
        .join(Document, ShareLink.document_id == Document.id)
        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
        .where(KnowledgeBase.owner_id == user.id)
        .order_by(ShareLink.created_at.desc())
    ).all()
    return [share_out(item) for item in items]


@router.post("", response_model=ShareOut, status_code=status.HTTP_201_CREATED)
def create_share(payload: ShareCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_owned_document(db, payload.document_id, user)
    if document.is_folder:
        raise HTTPException(status_code=400, detail="文件夹不能分享")
    if payload.expires_at:
        expires = payload.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="过期时间必须晚于当前时间")
    item = ShareLink(
        document_id=document.id,
        token=token_urlsafe(24),
        password_hash=hash_password(payload.password) if payload.password else None,
        expires_at=payload.expires_at,
        allow_download=payload.allow_download,
    )
    db.add(item)
    db.flush()
    add_log(db, user.id, "share", "document", document.id, item.token)
    db.commit()
    db.refresh(item)
    return share_out(item)


@router.delete("/{share_id}")
def revoke_share(share_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(ShareLink, share_id)
    if not item:
        raise HTTPException(status_code=404, detail="分享链接不存在")
    get_owned_document(db, item.document_id, user, include_deleted=True)
    db.delete(item)
    db.commit()
    return {"message": "分享已取消"}


@public_router.get("/share/{token}", response_model=PublicDocumentOut)
def read_public_share(token: str, password: str | None = Query(default=None), db: Session = Depends(get_db)):
    item = db.scalar(
        select(ShareLink)
        .options(joinedload(ShareLink.document).joinedload(Document.knowledge_base))
        .where(ShareLink.token == token)
    )
    if not item or item.document.is_deleted:
        raise HTTPException(status_code=404, detail="分享内容不存在")
    ensure_available(item, password)
    document = item.document
    return PublicDocumentOut(
        title=document.title,
        content=document.content,
        knowledge_base_name=document.knowledge_base.name,
        updated_at=document.updated_at,
        allow_download=item.allow_download,
    )


@public_router.get("/share/{token}/download")
def download_public_share(token: str, password: str | None = Query(default=None), db: Session = Depends(get_db)):
    item = db.scalar(select(ShareLink).options(joinedload(ShareLink.document)).where(ShareLink.token == token))
    if not item or item.document.is_deleted:
        raise HTTPException(status_code=404, detail="分享内容不存在")
    ensure_available(item, password)
    if not item.allow_download:
        raise HTTPException(status_code=403, detail="分享者未允许下载")
    filename = safe_filename(item.document.title) + ".md"
    return Response(
        content=item.document.content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
