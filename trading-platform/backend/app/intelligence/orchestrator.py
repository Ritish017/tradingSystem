"""Plugin-based Multi-Agent Orchestrator — Law 3 + Law 5 + Law 7.

Before (violations):
- Hardcoded imports of all 9 agent classes at top of file.
- Hardcoded _WEIGHTS dict — adding/reweighting an agent required editing this file.
- Adding a new agent required editing this file.

After:
- Agents loaded from REGISTRY (auto-discovered from configs/agents.yml).
- Weights, veto threshold, ensemble thresholds all from configs/agents.yml.
- Adding a new agent: create one file + add one entry in agents.yml.
  Zero changes to this file required.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.intelligence.base_agent import AgentOutput
from app.plugins.registry import REGISTRY

logger = get_logger(__name__)
_settings = get_settings()


def _load_agents_config() -> dict[str, Any]:
    path = Path(_settings.agents_config)
    if not path.exists():
        logger.warning("agents_config_not_found", path=str(path))
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class OrchestratorOutput(BaseModel):
    final_action: Literal["buy", "sell", "hold"]
    ensemble_confidence: float
    ensemble_risk: float
    agent_outputs: list[dict[str, Any]]
    rationale: str
    affected_assets: list[str]


class MultiAgentOrchestrator:
    """Runs all enabled agents concurrently, weights their votes, applies risk veto.

    Agents and weights are read from configs/agents.yml via REGISTRY.
    No agent class name appears in this file.
    """

    def __init__(self) -> None:
        self._config = _load_agents_config()
        self._agents_cfg: dict[str, dict[str, Any]] = {
            entry["id"]: entry
            for entry in self._config.get("agents", [])
            if entry.get("enabled", True)
        }
        self._ensemble_cfg: dict[str, float] = self._config.get("ensemble", {
            "buy_min_score": 0.15,
            "sell_min_score": 0.12,
        })

    def _build_agents(self) -> list[Any]:
        agents = []
        for agent_id, cfg in self._agents_cfg.items():
            cls = REGISTRY.get_agent(agent_id)
            if cls is None:
                logger.warning("orchestrator_agent_not_in_registry", agent_id=agent_id)
                continue
            agents.append(cls())
        return agents

    async def run(self, context: dict[str, Any]) -> OrchestratorOutput:
        import asyncio

        agents = self._build_agents()
        if not agents:
            logger.warning("orchestrator_no_agents_registered")
            return OrchestratorOutput(
                final_action="hold",
                ensemble_confidence=0.0,
                ensemble_risk=0.5,
                agent_outputs=[],
                rationale="no_agents_registered",
                affected_assets=[],
            )

        outputs: list[AgentOutput] = await asyncio.gather(
            *[agent.analyze(context) for agent in agents],
            return_exceptions=False,
        )

        context["agent_outputs"] = [o.model_dump() for o in outputs]

        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        weighted_confidence = 0.0
        weighted_risk = 0.0
        all_assets: set[str] = set()
        veto_action: str | None = None
        veto_rationale = ""

        for output in outputs:
            cfg = self._agents_cfg.get(output.agent_name, {})
            w = float(cfg.get("weight", 0.05))
            total_weight += w
            weighted_confidence += output.confidence * w
            weighted_risk += output.risk * w
            all_assets.update(output.affected_assets)

            # Check veto condition
            if cfg.get("is_veto_agent") and output.risk > float(cfg.get("veto_risk_threshold", 0.75)):
                veto_action = "sell"
                veto_rationale = (
                    f"{output.agent_name}_veto: risk={output.risk:.2f} "
                    f"> threshold={cfg.get('veto_risk_threshold', 0.75)}"
                )

            if output.action == "buy":
                buy_score += w * output.confidence
            elif output.action == "sell":
                sell_score += w * output.confidence

        if total_weight > 0:
            weighted_confidence /= total_weight
            weighted_risk /= total_weight

        buy_min = float(self._ensemble_cfg.get("buy_min_score", 0.15))
        sell_min = float(self._ensemble_cfg.get("sell_min_score", 0.12))

        if veto_action:
            final_action: Literal["buy", "sell", "hold"] = "sell"
            rationale = veto_rationale
        elif buy_score > sell_score and buy_score > buy_min:
            final_action = "buy"
            rationale = f"ensemble_buy: buy={buy_score:.3f} > sell={sell_score:.3f}"
        elif sell_score > buy_score and sell_score > sell_min:
            final_action = "sell"
            rationale = f"ensemble_sell: sell={sell_score:.3f} > buy={buy_score:.3f}"
        else:
            final_action = "hold"
            rationale = f"no_consensus: buy={buy_score:.3f}, sell={sell_score:.3f}"

        logger.info(
            "orchestrator_result",
            action=final_action,
            confidence=round(weighted_confidence, 3),
            risk=round(weighted_risk, 3),
            agents=len(agents),
        )

        return OrchestratorOutput(
            final_action=final_action,
            ensemble_confidence=round(weighted_confidence, 4),
            ensemble_risk=round(weighted_risk, 4),
            agent_outputs=[o.model_dump() for o in outputs],
            rationale=rationale,
            affected_assets=sorted(all_assets)[:15],
        )


ORCHESTRATOR = MultiAgentOrchestrator()
