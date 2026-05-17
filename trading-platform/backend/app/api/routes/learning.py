from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.state import STATE

router = APIRouter(prefix="/learning", tags=["learning"])


class LearningRun(BaseModel):
    model_name: str
    old_sharpe: float
    new_sharpe: float
    accepted: str
    reason: str
    created_at: str


@router.get("/runs", response_model=list[LearningRun])
async def get_learning_runs() -> list[LearningRun]:
    return [LearningRun(**item) for item in STATE.retraining_runs]

