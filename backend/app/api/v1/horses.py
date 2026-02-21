import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.horse import HorseDetail
from app.services.horse_service import get_horse_detail

router = APIRouter(prefix="/horses", tags=["horses"])


@router.get("/{horse_id}", response_model=HorseDetail)
async def get_horse(horse_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await get_horse_detail(session, horse_id)
    if not result:
        raise HTTPException(status_code=404, detail="Horse not found")
    return result
