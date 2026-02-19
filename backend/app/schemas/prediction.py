"""Pydantic schemas for prediction and model version endpoints."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


# --- Model Version ---

class ModelVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: str
    description: str | None = None
    accuracy: float | None = None
    created_at: datetime.datetime


class ModelVersionListResponse(BaseModel):
    items: list[ModelVersionResponse]


class ModelMetricsResponse(BaseModel):
    version: str
    accuracy: float | None = None
    f1: float | None = None
    roc_auc: float | None = None
    train_rows: int | None = None
    test_rows: int | None = None
    best_iteration: int | None = None
    cutoff_year: int | None = None
    # Verification
    unique_races: int | None = None
    win_hit_rate: float | None = None
    place_hit_rate: float | None = None


# --- Prediction ---

class PredictionEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    horse_id: uuid.UUID
    horse_name: str | None = None
    predicted_position: int | None = None
    predicted_score: float | None = None
    confidence: str | None = None
    explanation: str | None = None
    actual_finish: int | None = None


class RacePredictionResponse(BaseModel):
    race_id: str
    race_date: datetime.date | None = None
    racecourse_name: str | None = None
    race_name: str | None = None
    model_version: str | None = None
    predictions: list[PredictionEntry] = []
