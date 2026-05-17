from __future__ import annotations

import json
from datetime import datetime, timezone

from app.learning.retraining_job import RetrainingJob
from app.learning.trade_outcome_logger import TradeOutcome


def main() -> None:
    job = RetrainingJob()
    outcomes = [
        TradeOutcome(
            strategy_name="ppo_agent",
            symbol="BTCUSDT",
            side="buy",
            entry_price=100.0,
            exit_price=101.2,
            quantity=1.0,
            holding_period_minutes=60,
            realised_pnl=1.2,
            features_at_entry={"returns_1d": 0.01},
        ),
        TradeOutcome(
            strategy_name="td3_agent",
            symbol="ETHUSDT",
            side="sell",
            entry_price=200.0,
            exit_price=198.0,
            quantity=1.0,
            holding_period_minutes=45,
            realised_pnl=2.0,
            features_at_entry={"returns_1d": -0.01},
        ),
    ]
    job.ingest_outcomes(outcomes)
    result = job.run_nightly()
    print(
        json.dumps(
            [
                {
                    "model_name": item.model_name,
                    "old_sharpe": item.old_sharpe,
                    "new_sharpe": item.new_sharpe,
                    "accepted": item.accepted,
                    "reason": item.reason,
                    "created_at": item.created_at.isoformat(),
                }
                for item in result
            ],
            indent=2,
        )
    )
    print(f"completed at {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()

