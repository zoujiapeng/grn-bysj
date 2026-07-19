from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class UserOut(ORMModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    is_public: bool = False


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    is_public: Optional[bool] = None


class KnowledgeBaseOut(ORMModel):
    id: int
    name: str
    description: str
    is_public: bool
    created_at: datetime
    updated_at: datetime
    document_count: int = 0


class DocumentCreate(BaseModel):
    knowledge_base_id: int
    parent_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=255)
    content: str = ""
    is_folder: bool = False
    sort_order: int = 0


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = None
    tag_ids: Optional[list[int]] = None
    create_version: bool = False
    version_note: str = Field(default="", max_length=255)


class DocumentMove(BaseModel):
    parent_id: Optional[int] = None
    sort_order: int = 0


class DocumentOut(ORMModel):
    id: int
    knowledge_base_id: int
    parent_id: Optional[int]
    title: str
    content: str
    is_folder: bool
    sort_order: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    tags: list["TagOut"] = []
    is_favorite: bool = False


class TreeNodeOut(ORMModel):
    id: int
    knowledge_base_id: int
    parent_id: Optional[int]
    title: str
    is_folder: bool
    sort_order: int
    updated_at: datetime


class TagCreate(BaseModel):
    knowledge_base_id: int
    name: str = Field(min_length=1, max_length=50)


class TagUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class TagOut(ORMModel):
    id: int
    knowledge_base_id: int
    name: str
    created_at: datetime
    document_count: int = 0


class VersionOut(ORMModel):
    id: int
    document_id: int
    version_number: int
    title: str
    content: str
    note: str
    created_at: datetime


class SearchResult(BaseModel):
    id: int
    knowledge_base_id: int
    knowledge_base_name: str
    title: str
    snippet: str
    updated_at: datetime
    tags: list[str]


class ShareCreate(BaseModel):
    document_id: int
    password: Optional[str] = Field(default=None, max_length=128)
    expires_at: Optional[datetime] = None
    allow_download: bool = True


class ShareOut(BaseModel):
    id: int
    document_id: int
    token: str
    expires_at: Optional[datetime]
    allow_download: bool
    password_protected: bool
    created_at: datetime


class PublicDocumentOut(BaseModel):
    title: str
    content: str
    knowledge_base_name: str
    updated_at: datetime
    allow_download: bool


class AttachmentOut(ORMModel):
    id: int
    document_id: int
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    url: str = ""


DocumentOut.model_rebuild()
