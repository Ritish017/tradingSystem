from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.state import STATE
from app.learning.retraining_job import RetrainingJob
from app.learning.strategy_scorer import StrategyScorer
from app.learning.trade_outcome_logger import TradeOutcomeLogger

logger = logging.getLogger(__name__)


class SchedulerService:
    """Background job scheduler for retraining and scoring."""
    
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self.outcome_logger = TradeOutcomeLogger()
        self.retraining_job = RetrainingJob()
        self.strategy_scorer = StrategyScorer()
    
    def start(self) -> None:
        """Start scheduled jobs."""
        # Nightly retraining at 2:00 AM UTC
        self.scheduler.add_job(
            self._run_retraining,
            trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
            id="nightly_retraining",
            name="Nightly RL Agent Retraining",
            replace_existing=True,
        )
        
        # Daily strategy weight update at 3:00 AM UTC
        self.scheduler.add_job(
            self._update_strategy_weights,
            trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
            id="daily_weight_update",
            name="Daily Strategy Weight Update",
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self.scheduler.get_jobs()))
    
    def shutdown(self) -> None:
        """Gracefully shutdown scheduler."""
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")
    
    async def _run_retraining(self) -> None:
        """Nightly retraining job."""
        try:
            logger.info("Starting nightly retraining job")
            
            # Get last 30 days of trade outcomes
            outcomes = self.outcome_logger.all()
            recent_outcomes = [
                o for o in outcomes
                if (datetime.now(o.created_at.tzinfo) - o.created_at).days <= 30
            ]
            
            if len(recent_outcomes) < 10:
                logger.warning("Insufficient trade outcomes (%d) for retraining", len(recent_outcomes))
                return
            
            # Ingest into replay buffer
            self.retraining_job.ingest_outcomes(recent_outcomes)
            
            # Run retraining
            results = self.retraining_job.run_nightly()
            
            for result in results:
                logger.info(
                    "Retraining %s: old_sharpe=%.3f, new_sharpe=%.3f, accepted=%s, reason=%s",
                    result.model_name,
                    result.old_sharpe,
                    result.new_sharpe,
                    result.accepted,
                    result.reason,
                )
            
            logger.info("Nightly retraining completed: %d models processed", len(results))
            
        except Exception as exc:
            logger.error("Retraining job failed: %s", exc, exc_info=True)
    
    async def _update_strategy_weights(self) -> None:
        """Daily strategy weight update based on rolling 30-day performance."""
        try:
            logger.info("Starting daily strategy weight update")
            
            outcomes = self.outcome_logger.all()
            recent_outcomes = [
                o for o in outcomes
                if (datetime.now(o.created_at.tzinfo) - o.created_at).days <= 30
            ]
            
            if not recent_outcomes:
                logger.warning("No recent outcomes for weight update")
                return
            
            weights = self.strategy_scorer.update_weights(recent_outcomes)
            
            for strategy_name, weight in weights.items():
                logger.info("Strategy %s weight updated to %.3f", strategy_name, weight)
            
            logger.info("Strategy weight update completed: %d strategies", len(weights))
            
        except Exception as exc:
            logger.error("Weight update job failed: %s", exc, exc_info=True)


# Global scheduler instance
SCHEDULER = SchedulerService()
