from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine
from .routers import attachments, auth, backups, documents, knowledge_bases, shares, stats, tags, transfer


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_directories()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="可在 Linux 上独立部署的 Markdown 个人知识库系统",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(knowledge_bases.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(tags.router, prefix=settings.api_prefix)
app.include_router(attachments.router, prefix=settings.api_prefix)
app.include_router(shares.router, prefix=settings.api_prefix)
app.include_router(shares.public_router, prefix=settings.api_prefix)
app.include_router(transfer.router, prefix=settings.api_prefix)
app.include_router(backups.router, prefix=settings.api_prefix)
app.include_router(stats.router, prefix=settings.api_prefix)

settings.ensure_directories()
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/")
def root():
    return {"message": "Markdown Knowledge Base API", "docs": "/docs"}
