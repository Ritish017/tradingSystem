from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestIn(BaseModel):
    strategy_name: str
    symbols: list[str]
    start: str
    end: str


class BacktestOut(BaseModel):
    strategy_name: str
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    run_at: str


@router.post("/run", response_model=BacktestOut)
async def run_backtest(payload: BacktestIn) -> BacktestOut:
    # Deterministic synthetic metrics to keep API available before full historical runner.
    base = (sum(ord(c) for c in payload.strategy_name) % 30) / 10
    sharpe = round(0.8 + base / 5, 3)
    sortino = round(sharpe * 1.2, 3)
    calmar = round(sharpe * 0.9, 3)
    max_drawdown = round(0.05 + ((sum(len(s) for s in payload.symbols) % 10) / 100), 3)
    return BacktestOut(
        strategy_name=payload.strategy_name,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=max_drawdown,
        run_at=datetime.now(timezone.utc).isoformat(),
    )

