from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.race import DataStatusResponse
from app.services.race_service import get_data_status

router = APIRouter(tags=["data"])


@router.get("/data/status", response_model=DataStatusResponse)
async def data_status(session: AsyncSession = Depends(get_session)):
    status = await get_data_status(session)
    return DataStatusResponse(**status)
