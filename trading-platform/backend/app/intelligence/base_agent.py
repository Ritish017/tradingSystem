from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel


class AgentOutput(BaseModel):
    agent_name: str
    action: Literal["buy", "sell", "hold"] = "hold"
    confidence: float = 0.5
    risk: float = 0.5
    affected_assets: list[str] = []
    rationale: str = ""
    metadata: dict[str, Any] = {}
    ts: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.ts:
            self.ts = datetime.now(timezone.utc).isoformat()


class BaseAgent(ABC):
    name: str = "base_agent"

    @abstractmethod
    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        """Analyze context and return structured output."""
        ...

    def _clamp(self, value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, value))

    def _output(
        self,
        action: Literal["buy", "sell", "hold"],
        confidence: float,
        risk: float,
        affected_assets: list[str],
        rationale: str,
        metadata: dict[str, Any] | None = None,
    ) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            action=action,
            confidence=self._clamp(confidence),
            risk=self._clamp(risk),
            affected_assets=affected_assets,
            rationale=rationale,
            metadata=metadata or {},
        )
