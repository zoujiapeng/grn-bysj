from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Tag, User, document_tags
from ..schemas import TagCreate, TagOut, TagUpdate
from ..utils import get_owned_kb


router = APIRouter(prefix="/tags", tags=["标签"])


@router.get("/knowledge-base/{kb_id}", response_model=list[TagOut])
def list_tags(kb_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_kb(db, kb_id, user)
    rows = db.execute(
        select(Tag, func.count(document_tags.c.document_id))
        .outerjoin(document_tags, document_tags.c.tag_id == Tag.id)
        .where(Tag.knowledge_base_id == kb_id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    ).all()
    result = []
    for tag, count in rows:
        item = TagOut.model_validate(tag)
        item.document_count = count
        result.append(item)
    return result


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_kb(db, payload.knowledge_base_id, user)
    tag = Tag(knowledge_base_id=payload.knowledge_base_id, name=payload.name.strip())
    db.add(tag)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="标签已存在")
    db.refresh(tag)
    return tag


@router.put("/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, payload: TagUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tag = db.scalar(select(Tag).where(Tag.id == tag_id))
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    get_owned_kb(db, tag.knowledge_base_id, user)
    tag.name = payload.name.strip()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="标签已存在")
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    get_owned_kb(db, tag.knowledge_base_id, user)
    db.delete(tag)
    db.commit()
    return {"message": "标签已删除"}
