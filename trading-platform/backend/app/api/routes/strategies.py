from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.state import STATE
from app.engine.service import ENGINE

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategyOut(BaseModel):
    name: str
    strategy_type: str
    asset_class: str
    status: str
    allocated_capital: float
    current_weight: float
    consecutive_losses: int


class StrategyStatusUpdate(BaseModel):
    status: str


@router.get("/", response_model=list[StrategyOut])
async def list_strategies() -> list[StrategyOut]:
    ENGINE.register_default_strategies()
    return [
        StrategyOut(
            name=item.name,
            strategy_type=item.strategy_type,
            asset_class=item.asset_class,
            status=item.status,
            allocated_capital=item.allocated_capital,
            current_weight=item.current_weight,
            consecutive_losses=item.consecutive_losses,
        )
        for item in STATE.strategies.values()
    ]


@router.post("/{strategy_name}/status", response_model=StrategyOut)
async def set_strategy_status(strategy_name: str, payload: StrategyStatusUpdate) -> StrategyOut:
    ENGINE.register_default_strategies()
    strategy = STATE.strategies[strategy_name]
    strategy.status = payload.status
    return StrategyOut(
        name=strategy.name,
        strategy_type=strategy.strategy_type,
        asset_class=strategy.asset_class,
        status=strategy.status,
        allocated_capital=strategy.allocated_capital,
        current_weight=strategy.current_weight,
        consecutive_losses=strategy.consecutive_losses,
    )

