import io
import json
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Document, User
from ..utils import add_log, get_owned_kb, safe_filename


router = APIRouter(prefix="/transfer", tags=["导入导出"])


def unique_title(db: Session, kb_id: int, parent_id: int | None, title: str, is_folder: bool) -> str:
    base = title.strip() or "未命名"
    candidate = base
    index = 1
    while db.scalar(
        select(Document.id).where(
            Document.knowledge_base_id == kb_id,
            Document.parent_id == parent_id,
            Document.title == candidate,
            Document.is_folder == is_folder,
            Document.is_deleted.is_(False),
        )
    ):
        index += 1
        candidate = f"{base} ({index})"
    return candidate


def build_paths(documents: list[Document]) -> dict[int, str]:
    by_id = {item.id: item for item in documents}
    cache: dict[int, str] = {}

    def resolve(item: Document, stack: set[int] | None = None) -> str:
        if item.id in cache:
            return cache[item.id]
        stack = set(stack or set())
        if item.id in stack:
            return safe_filename(item.title)
        stack.add(item.id)
        own = safe_filename(item.title)
        if item.parent_id and item.parent_id in by_id:
            value = f"{resolve(by_id[item.parent_id], stack)}/{own}"
        else:
            value = own
        cache[item.id] = value
        return value

    for document in documents:
        resolve(document)
    return cache


@router.get("/knowledge-base/{kb_id}/export")
def export_knowledge_base(kb_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb = get_owned_kb(db, kb_id, user)
    documents = db.scalars(
        select(Document)
        .options(selectinload(Document.tags), selectinload(Document.attachments))
        .where(Document.knowledge_base_id == kb.id, Document.is_deleted.is_(False))
        .order_by(Document.id)
    ).unique().all()
    paths = build_paths(documents)
    output = io.BytesIO()
    manifest = {"knowledge_base": kb.name, "documents": []}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for document in documents:
            path = paths[document.id]
            if document.is_folder:
                archive.writestr(path.rstrip("/") + "/.keep", "")
                continue
            tag_line = ", ".join(tag.name for tag in document.tags)
            header = f"---\ntitle: {document.title}\ntags: [{tag_line}]\n---\n\n"
            archive.writestr(path + ".md", header + document.content)
            manifest["documents"].append({"id": document.id, "path": path + ".md", "tags": [tag.name for tag in document.tags]})
            for attachment in document.attachments:
                from pathlib import Path
                from ..config import settings

                source = Path(settings.upload_dir) / attachment.relative_path
                if source.exists():
                    archive.write(source, f"_attachments/{document.id}/{safe_filename(attachment.original_name)}")
        archive.writestr("knowledge-base.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    output.seek(0)
    filename = safe_filename(kb.name) + ".zip"
    return StreamingResponse(
        output,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/knowledge-base/{kb_id}/import")
async def import_files(
    kb_id: int,
    file: UploadFile = File(...),
    parent_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = get_owned_kb(db, kb_id, user)
    if parent_id is not None:
        parent = db.get(Document, parent_id)
        if not parent or parent.knowledge_base_id != kb.id or not parent.is_folder or parent.is_deleted:
            raise HTTPException(status_code=400, detail="目标目录无效")
    raw = await file.read(30 * 1024 * 1024 + 1)
    if len(raw) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="导入文件不能超过 30MB")
    filename = (file.filename or "").lower()
    created = 0
    if filename.endswith(".md"):
        title = unique_title(db, kb.id, parent_id, PurePosixPath(file.filename or "note.md").stem, False)
        db.add(Document(knowledge_base_id=kb.id, parent_id=parent_id, title=title, content=raw.decode("utf-8-sig"), is_folder=False))
        created = 1
    elif filename.endswith(".zip"):
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="ZIP 文件损坏")
        folder_cache: dict[tuple[int | None, str], int] = {}

        def ensure_folder(name: str, current_parent: int | None) -> int:
            key = (current_parent, name)
            if key in folder_cache:
                return folder_cache[key]
            existing = db.scalar(
                select(Document).where(
                    Document.knowledge_base_id == kb.id,
                    Document.parent_id == current_parent,
                    Document.title == name,
                    Document.is_folder.is_(True),
                    Document.is_deleted.is_(False),
                )
            )
            if existing:
                folder_cache[key] = existing.id
                return existing.id
            folder = Document(knowledge_base_id=kb.id, parent_id=current_parent, title=name, is_folder=True)
            db.add(folder)
            db.flush()
            folder_cache[key] = folder.id
            return folder.id

        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if info.is_dir() or path.suffix.lower() != ".md" or ".." in path.parts:
                continue
            current_parent = parent_id
            for part in path.parts[:-1]:
                if part.startswith("_") or not part.strip():
                    continue
                current_parent = ensure_folder(safe_filename(part), current_parent)
            content = archive.read(info).decode("utf-8-sig")
            title = unique_title(db, kb.id, current_parent, safe_filename(path.stem), False)
            db.add(Document(knowledge_base_id=kb.id, parent_id=current_parent, title=title, content=content, is_folder=False))
            created += 1
    else:
        raise HTTPException(status_code=400, detail="仅支持 .md 或 .zip 文件")
    add_log(db, user.id, "import", "knowledge_base", kb.id, f"{created} documents")
    db.commit()
    return {"message": f"成功导入 {created} 篇文档", "created": created}
