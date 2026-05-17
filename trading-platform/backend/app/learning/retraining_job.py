from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.state import STATE
from app.learning.replay_buffer import ReplayBuffer
from app.learning.trade_outcome_logger import TradeOutcome


@dataclass(frozen=True)
class RetrainingResult:
    model_name: str
    old_sharpe: float
    new_sharpe: float
    accepted: bool
    reason: str
    created_at: datetime


class RetrainingJob:
    def __init__(self) -> None:
        self.buffer = ReplayBuffer()
        self.production_sharpe: dict[str, float] = {"ppo_agent": 1.0, "td3_agent": 1.0}

    def ingest_outcomes(self, outcomes: list[TradeOutcome]) -> None:
        self.buffer.extend(outcomes)

    def run_nightly(self) -> list[RetrainingResult]:
        sampled = self.buffer.sample(200)
        if not sampled:
            return []
        mean_pnl = sum(x.realised_pnl for x in sampled) / len(sampled)
        synthetic_sharpe = mean_pnl / (max(abs(mean_pnl), 1.0) / 10 + 0.1)
        results: list[RetrainingResult] = []
        for model_name in ("ppo_agent", "td3_agent"):
            old = self.production_sharpe.get(model_name, 1.0)
            new = max(0.0, old + (synthetic_sharpe * 0.05))
            accepted = new > (0.9 * old)
            reason = "accepted" if accepted else "rejected_degradation"
            if accepted:
                self.production_sharpe[model_name] = new
            result = RetrainingResult(
                model_name=model_name,
                old_sharpe=old,
                new_sharpe=new,
                accepted=accepted,
                reason=reason,
                created_at=datetime.now(timezone.utc),
            )
            results.append(result)
            STATE.retraining_runs.append(
                {
                    "model_name": result.model_name,
                    "old_sharpe": result.old_sharpe,
                    "new_sharpe": result.new_sharpe,
                    "accepted": "true" if result.accepted else "false",
                    "reason": result.reason,
                    "created_at": result.created_at.isoformat(),
                }
            )
        return results

