import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.bet import (
    BetListResponse,
    BetRecordCreate,
    BetRecordResponse,
    BetRecordUpdate,
    BetSummaryResponse,
)
from app.services.bet_service import create_bet, delete_bet, get_bet_summary, get_bets, update_bet

router = APIRouter(prefix="/bets", tags=["bets"])


@router.post("", response_model=BetRecordResponse)
async def create(data: BetRecordCreate, session: AsyncSession = Depends(get_session)):
    bet = await create_bet(session, data.model_dump())
    return bet


@router.get("", response_model=BetListResponse)
async def list_bets(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    items, total = await get_bets(session, page=page, per_page=per_page)
    return BetListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/summary", response_model=BetSummaryResponse)
async def summary(session: AsyncSession = Depends(get_session)):
    return await get_bet_summary(session)


@router.put("/{bet_id}", response_model=BetRecordResponse)
async def update(
    bet_id: uuid.UUID,
    data: BetRecordUpdate,
    session: AsyncSession = Depends(get_session),
):
    bet = await update_bet(session, bet_id, data.model_dump(exclude_unset=True))
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    return bet


@router.delete("/{bet_id}", status_code=204)
async def delete(
    bet_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    deleted = await delete_bet(session, bet_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bet not found")
