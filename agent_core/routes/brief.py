from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/brief", tags=["brief"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501,
    content={
        "detail": "Morning briefs are Slack-only and not persisted to the database."
    },
)


@router.get("")
async def get_brief() -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.post("/generate")
async def generate_brief() -> JSONResponse:
    return _NOT_IMPLEMENTED
