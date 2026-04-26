import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.db import get_db
from mimir.logger import logger
from mimir.rag.ingest import ingest_file

router = APIRouter()

_ALLOWED_SUFFIXES = {".md", ".pdf"}


@router.post("/ingest")
async def ingest(file: UploadFile, db: AsyncSession = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(_ALLOWED_SUFFIXES)}",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        logger.debug("ingest_file_started", filename=file.filename)
        chunks_inserted = await ingest_file(tmp_path, db)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"chunks_inserted": chunks_inserted, "source_path": file.filename}
