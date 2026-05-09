from fastapi import APIRouter

from agent_core.memory.semantic import SemanticMemory
from shared.schemas import MemoryResponse, MemoryWriteRequest, MemoryWriteResponse

router = APIRouter(prefix="/memory", tags=["memory"])

_memory = SemanticMemory()


@router.get("", response_model=MemoryResponse)
async def get_memory() -> MemoryResponse:
    return MemoryResponse(content=_memory.read())


# No auth — self-hosted on a trusted network (LAN/Tailscale). Unsafe if exposed to the internet
# without a reverse-proxy auth layer.
@router.put("", response_model=MemoryWriteResponse)
async def write_memory(body: MemoryWriteRequest) -> MemoryWriteResponse:
    _memory.write(body.content)
    return MemoryWriteResponse()
