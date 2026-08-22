import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.bet import BetSuggestionRequest, BetSuggestionResponse, HedgeRequest
from app.schemas.race import (
    AptitudeResponse,
    ComboOddsRequest,
    ComboOddsResponse,
    ConfirmedDataResponse,
    OddsComboEntry,
    OddsHistoryResponse,
    OddsResponse,
    OddsTableResponse,
    PastPerformancesResponse,
    RaceDetail,
    RaceListResponse,
    RacePedigreeResponse,
    SleeperResponse,
    TrackConditionResponse,
)
from app.services.horse_service import get_course_aptitude_bulk
from app.services.race_service import (
    get_confirmed_data,
    get_latest_odds,
    get_odds_history,
    get_past_performances,
    get_race_detail,
    get_race_pedigree,
    get_race_track_condition,
    get_races,
)

router = APIRouter(prefix="/races", tags=["races"])


@router.get("", response_model=RaceListResponse)
async def list_races(
    date: datetime.date | None = Query(
        None, description="Filter by race date (YYYY-MM-DD)"
    ),
    year_month: str | None = Query(None, description="Filter by year-month (YYYY-MM)"),
    week: int | None = Query(None, ge=1, le=5, description="Week of month (1-5)"),
    racecourse: str | None = Query(None, description="Filter by racecourse name"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
):
    ym_year: int | None = None
    ym_month: int | None = None
    if year_month:
        m = re.match(r"^(\d{4})-(\d{2})$", year_month)
        if not m:
            raise HTTPException(status_code=400, detail="year_month must be YYYY-MM")
        ym_year, ym_month = int(m.group(1)), int(m.group(2))
        if not (1 <= ym_month <= 12):
            raise HTTPException(
                status_code=400, detail="month must be between 01 and 12"
            )

    items, total = await get_races(
        session,
        date=date,
        year_month=(ym_year, ym_month) if ym_year and ym_month else None,
        week=week,
        racecourse=racecourse,
        page=page,
        per_page=per_page,
    )
    return RaceListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{race_id}", response_model=RaceDetail)
async def get_race(race_id: str, session: AsyncSession = Depends(get_session)):
    race = await get_race_detail(session, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    return race


@router.get("/{race_id}/past-performances", response_model=PastPerformancesResponse)
async def get_race_past_performances(
    race_id: str,
    limit: int = Query(5, ge=1, le=10, description="Past races per horse"),
    session: AsyncSession = Depends(get_session),
):
    """過去走（馬柱）: 各出走馬の現レースより前の直近N走を返す。"""
    result = await get_past_performances(session, race_id, limit_per_horse=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.get("/{race_id}/pedigree", response_model=RacePedigreeResponse)
async def get_race_pedigree_endpoint(
    race_id: str, session: AsyncSession = Depends(get_session)
):
    """血統: 各出走馬の父/母/母父（JRA-VAN NL_UM をFDW経由で突合）。"""
    result = await get_race_pedigree(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.get("/{race_id}/confirmed", response_model=ConfirmedDataResponse)
async def get_race_confirmed_endpoint(
    race_id: str, session: AsyncSession = Depends(get_session)
):
    """確定オッズ・払戻: JV-Data由来の確定単勝オッズと確定払戻（自己完結テーブル）。"""
    result = await get_confirmed_data(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.get("/{race_id}/track-condition", response_model=TrackConditionResponse)
async def get_race_track_condition_endpoint(
    race_id: str, session: AsyncSession = Depends(get_session)
):
    """馬場情報: 含水率・クッション値（JRA公式・開催日スクレイピング）。"""
    result = await get_race_track_condition(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.get("/{race_id}/odds", response_model=OddsResponse)
async def get_odds(race_id: str, session: AsyncSession = Depends(get_session)):
    result = await get_latest_odds(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.post("/{race_id}/odds/refresh", response_model=OddsResponse)
async def refresh_odds(race_id: str, session: AsyncSession = Depends(get_session)):
    # For now, just return latest odds (scraper integration later)
    result = await get_latest_odds(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.get("/{race_id}/odds/history", response_model=OddsHistoryResponse)
async def get_odds_hist(race_id: str, session: AsyncSession = Depends(get_session)):
    result = await get_odds_history(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.post("/{race_id}/odds/combo", response_model=ComboOddsResponse)
async def get_combo_odds(
    race_id: str,
    body: ComboOddsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Fetch real-time odds for a specific bet type and horse combination."""
    from app.scraper.parsers.odds import NETKEIBA_ODDS_TYPE_MAP

    if body.bet_type not in NETKEIBA_ODDS_TYPE_MAP:
        raise HTTPException(
            status_code=400, detail=f"Unknown bet_type: {body.bet_type}"
        )
    if not body.selections:
        raise HTTPException(status_code=400, detail="selections must not be empty")

    # Resolve race_id string to DB race_id for validation
    from app.models import Race
    from sqlalchemy import select

    result = await session.execute(select(Race).where(Race.race_id == race_id))
    race = result.scalar_one_or_none()
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    # Fetch odds from netkeiba (lightweight: uses browser JSON fetch, no full page)
    from app.scraper.netkeiba import NetkeibaScraper

    try:
        async with NetkeibaScraper(headless=True) as nk:
            odds = await nk.scrape_combo_odds(race_id, body.bet_type, body.selections)
    except Exception:
        odds = None

    return ComboOddsResponse(
        race_id=race_id,
        bet_type=body.bet_type,
        selections=body.selections,
        odds=odds,
    )


@router.get("/{race_id}/odds/table", response_model=OddsTableResponse)
async def get_odds_table(
    race_id: str,
    bet_type: str = Query(..., description="Bet type (tansho, umaren, sanrentan, ...)"),
    session: AsyncSession = Depends(get_session),
):
    """Fetch the full real-time odds table for one bet type (all combinations).

    A single typed-odds fetch returns every combination, so the client can look
    up any box/formation/nagashi combo locally without per-combo requests.
    """
    from app.scraper.parsers.odds import NETKEIBA_ODDS_TYPE_MAP

    if bet_type not in NETKEIBA_ODDS_TYPE_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown bet_type: {bet_type}")

    from sqlalchemy import select

    from app.models import Race

    result = await session.execute(select(Race).where(Race.race_id == race_id))
    race = result.scalar_one_or_none()
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    from app.scraper.netkeiba import NetkeibaScraper

    parsed: dict | None = None
    try:
        async with NetkeibaScraper(headless=True) as nk:
            parsed = await nk.scrape_full_odds(race_id, bet_type)
    except Exception:
        parsed = None

    if not parsed:
        return OddsTableResponse(race_id=race_id, bet_type=bet_type, combos=[])

    combos = [
        OddsComboEntry(
            combo=key,
            odds=val.get("odds"),
            odds_low=val.get("odds_low"),
            odds_high=val.get("odds_high"),
            favorite=val.get("favorite"),
        )
        for key, val in parsed.get("combos", {}).items()
    ]
    return OddsTableResponse(
        race_id=race_id,
        bet_type=bet_type,
        status=parsed.get("status"),
        official_datetime=parsed.get("official_datetime"),
        combos=combos,
    )


@router.post("/{race_id}/bet-suggestion", response_model=BetSuggestionResponse)
async def post_bet_suggestion(
    race_id: str,
    body: BetSuggestionRequest,
    session: AsyncSession = Depends(get_session),
):
    """予算から券種・買い目・配分を自動提案(おまかせ＝荒れ度連動／ガミ防止)。"""
    from app.services.bet_suggestion_service import suggest_bets

    if body.budget < 100:
        raise HTTPException(status_code=400, detail="予算は100円以上にしてください")

    res = await suggest_bets(
        session,
        race_id,
        budget=body.budget,
        alloc_mode=body.alloc_mode,
        bet_types=body.bet_types,
        type_budgets=body.type_budgets,
    )
    if res is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return res


@router.post("/{race_id}/hedge", response_model=BetSuggestionResponse)
async def post_hedge(
    race_id: str,
    body: HedgeRequest,
    session: AsyncSession = Depends(get_session),
):
    """荒れ対応ヘッジ: 本命=三連複 / 穴=ワイド の2本立て(相互カバー・ガミ防止)。

    穴馬検出でnetkeibaをスクレイプするため時間がかかる(数十秒)。
    """
    from app.services.hedge_service import suggest_hedge

    if body.budget < 200:
        raise HTTPException(status_code=400, detail="予算は200円以上にしてください")
    allowed = {"tansho", "fukusho", "umaren", "wide", "umatan", "trio", "trifecta"}
    if body.honmei_bet not in allowed or body.ana_bet not in allowed:
        raise HTTPException(status_code=400, detail="券種の指定が不正です")
    ratio = min(1.0, max(0.0, body.honmei_ratio))
    res = await suggest_hedge(
        session,
        race_id,
        budget=body.budget,
        honmei_ratio=ratio,
        min_fav=body.min_fav,
        honmei_bet=body.honmei_bet,
        ana_bet=body.ana_bet,
    )
    if res is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return res


@router.get("/{race_id}/sleepers", response_model=SleeperResponse)
async def get_sleepers(
    race_id: str,
    min_fav: int = Query(5, ge=1, le=18),
    session: AsyncSession = Depends(get_session),
):
    """巻き返し穴の検出。人気薄馬のnetkeiba全成績から今走馬場での実力を評価。

    netkeibaを馬ごとにスクレイプするため時間がかかる(数十秒〜)。
    """
    from app.services.sleeper_service import find_sleepers

    res = await find_sleepers(session, race_id, min_fav=min_fav)
    if res is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return res


@router.get("/{race_id}/aptitude", response_model=AptitudeResponse)
async def get_aptitude(race_id: str, session: AsyncSession = Depends(get_session)):
    race = await get_race_detail(session, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    entries = await get_course_aptitude_bulk(
        session, race.id, race.surface, race.distance_m
    )
    return AptitudeResponse(race_id=race_id, entries=entries)
