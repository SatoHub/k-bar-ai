"""Prediction and model version API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.prediction import (
    ModelMetricsResponse,
    ModelVersionListResponse,
    RacePredictionResponse,
)
from app.services.prediction_service import (
    get_model_metrics,
    get_model_versions,
    get_race_predictions,
)

router = APIRouter(tags=["predictions"])


@router.get("/predictions/{race_id}", response_model=RacePredictionResponse)
async def get_predictions(
    race_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get predictions for a specific race."""
    result = await get_race_predictions(session, race_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return result


@router.get("/models", response_model=ModelVersionListResponse)
async def list_models(
    session: AsyncSession = Depends(get_session),
):
    """List all trained model versions."""
    items = await get_model_versions(session)
    return ModelVersionListResponse(items=items)


@router.get("/models/{version}/metrics", response_model=ModelMetricsResponse)
async def get_metrics(
    version: str,
    session: AsyncSession = Depends(get_session),
):
    """Get training and verification metrics for a model version."""
    result = await get_model_metrics(session, version)
    if result is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    return result
