from fastapi import APIRouter

from app.api.v1.document_jobs import router as document_jobs_router


router = APIRouter(prefix="/api/v1")
router.include_router(document_jobs_router)
