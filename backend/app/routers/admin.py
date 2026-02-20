import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.db import Book, Source
from app.models.schemas import BookResponse, SourceResponse, UploadResponse
from app.middleware.rate_limit import limiter
from app.services.ingestion import _detect_file_type, run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("5/minute")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
    title: str = Form(...),
    author: str = Form(""),
    language: str = Form("both"),
    madhab: str = Form("general"),
    category: str = Form("general"),
    chunk_type: str = Form("paragraph"),
    session: AsyncSession = Depends(get_session),
):
    """Upload a file for ingestion into the knowledge base.

    The file is saved to disk, and ingestion runs in the background.
    """
    # Validate file type
    file_type = _detect_file_type(file.filename)

    # Ensure upload directory exists
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file to disk
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix
    saved_filename = f"{file_id}{ext}"
    file_path = upload_dir / saved_filename

    content = await file.read()
    file_path.write_bytes(content)

    # Create or find book
    book = Book(
        title=title,
        author=author,
        language=language,
        madhab=madhab,
        category=category,
    )
    session.add(book)
    await session.flush()

    # Create source record
    source = Source(
        book_id=book.id,
        filename=file.filename,
        file_type=file_type,
        file_path=str(file_path),
        status="pending",
    )
    session.add(source)
    await session.commit()

    # Run ingestion in background
    background_tasks.add_task(
        _run_ingestion_with_session,
        source_id=source.id,
        book_id=book.id,
        chunk_type=chunk_type,
    )

    return UploadResponse(
        source_id=source.id,
        book_id=book.id,
        status="pending",
        message=f"File '{file.filename}' uploaded. Ingestion started in background.",
    )


async def _run_ingestion_with_session(
    source_id: uuid.UUID,
    book_id: uuid.UUID,
    chunk_type: str,
):
    """Create a fresh session for background ingestion task."""
    from app.database import async_session

    async with async_session() as session:
        source = await session.get(Source, source_id)
        book = await session.get(Book, book_id)
        if source and book:
            await run_ingestion(session, source, book, chunk_type)


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    session: AsyncSession = Depends(get_session),
):
    """List all uploaded sources and their ingestion status."""
    result = await session.execute(
        select(Source).order_by(Source.created_at.desc())
    )
    return result.scalars().all()


@router.get("/books", response_model=list[BookResponse])
async def list_books(
    session: AsyncSession = Depends(get_session),
):
    """List all books in the knowledge base."""
    result = await session.execute(
        select(Book).order_by(Book.created_at.desc())
    )
    return result.scalars().all()
