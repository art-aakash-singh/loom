from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", operation_id="getHealth")
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok")
