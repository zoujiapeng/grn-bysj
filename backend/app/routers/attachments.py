from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Attachment, User
from ..schemas import AttachmentOut
from ..utils import add_log, get_owned_document, safe_filename


router = APIRouter(prefix="/attachments", tags=["附件"])


def attachment_out(item: Attachment) -> AttachmentOut:
    data = AttachmentOut.model_validate(item)
    data.url = f"/uploads/{item.relative_path.replace('\\\\', '/')}"
    return data


@router.get("/document/{document_id}", response_model=list[AttachmentOut])
def list_attachments(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_document(db, document_id, user)
    items = db.scalars(select(Attachment).where(Attachment.document_id == document_id).order_by(Attachment.created_at.desc())).all()
    return [attachment_out(item) for item in items]


@router.post("/document/{document_id}", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    document_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(db, document_id, user)
    if document.is_folder:
        raise HTTPException(status_code=400, detail="不能向文件夹上传附件")
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {settings.max_upload_mb}MB")
    extension = Path(file.filename or "file").suffix[:20]
    stored_name = f"{uuid4().hex}{extension}"
    relative_dir = Path(str(user.id)) / str(document.knowledge_base_id) / str(document.id)
    target_dir = Path(settings.upload_dir) / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / stored_name
    target.write_bytes(data)
    relative_path = str(relative_dir / stored_name).replace("\\", "/")
    item = Attachment(
        document_id=document.id,
        original_name=safe_filename(file.filename or "file"),
        stored_name=stored_name,
        relative_path=relative_path,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
    )
    db.add(item)
    db.flush()
    add_log(db, user.id, "upload", "attachment", item.id, item.original_name)
    db.commit()
    db.refresh(item)
    return attachment_out(item)


@router.delete("/{attachment_id}")
def delete_attachment(attachment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Attachment, attachment_id)
    if not item:
        raise HTTPException(status_code=404, detail="附件不存在")
    get_owned_document(db, item.document_id, user, include_deleted=True)
    path = Path(settings.upload_dir) / item.relative_path
    path.unlink(missing_ok=True)
    db.delete(item)
    add_log(db, user.id, "delete", "attachment", attachment_id, item.original_name)
    db.commit()
    return {"message": "附件已删除"}
