from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.intelligence.orchestrator import ORCHESTRATOR
from app.cross_market.regime_detector import detect_regime
from app.cross_market.correlation_engine import get_mock_correlations

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/regime")
async def get_regime() -> dict[str, Any]:
    """Current market regime detection."""
    regime = detect_regime({})
    return regime.model_dump()


@router.get("/cross-market")
async def get_cross_market() -> list[dict[str, Any]]:
    """Cross-market correlation matrix."""
    correlations = get_mock_correlations()
    return [c.model_dump() for c in correlations]


@router.post("/analyze")
async def trigger_analysis(context: dict[str, Any] = {}) -> dict[str, Any]:
    """Run multi-agent analysis with provided context."""
    result = await ORCHESTRATOR.run(context)
    return result.model_dump()


@router.get("/agents")
async def get_agent_info() -> list[dict[str, str]]:
    """List all available agents."""
    return [
        {"name": a.name, "type": type(a).__name__}
        for a in ORCHESTRATOR._agents
    ]
