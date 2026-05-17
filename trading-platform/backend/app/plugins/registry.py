"""Plugin Registry — Law 3.

Central catalogue of every discoverable extension point:
  - strategies      (BaseStrategy subclasses)
  - execution adapters (BaseExecutionAdapter subclasses)
  - intelligence agents (BaseAgent subclasses)
  - ingesters       (BaseIngester subclasses)

Nothing else in the codebase holds references to concrete implementations.
"""
from __future__ import annotations

from typing import Any


class PluginRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, type] = {}      # strategy_id → class
        self._adapters: dict[str, type] = {}         # adapter_id → class
        self._agents: dict[str, type] = {}           # agent name → class
        self._ingesters: dict[str, type] = {}        # source_id → class

    # ── Strategies ────────────────────────────────────────────────────────────

    def register_strategy(self, strategy_id: str, cls: type) -> None:
        self._strategies[strategy_id] = cls

    def get_strategy(self, strategy_id: str) -> type | None:
        return self._strategies.get(strategy_id)

    def list_strategies(self) -> dict[str, type]:
        return dict(self._strategies)

    # ── Execution adapters ────────────────────────────────────────────────────

    def register_adapter(self, adapter_id: str, cls: type) -> None:
        self._adapters[adapter_id] = cls

    def get_adapter(self, adapter_id: str) -> type | None:
        return self._adapters.get(adapter_id)

    def list_adapters(self) -> dict[str, type]:
        return dict(self._adapters)

    # ── Intelligence agents ───────────────────────────────────────────────────

    def register_agent(self, agent_name: str, cls: type) -> None:
        self._agents[agent_name] = cls

    def get_agent(self, agent_name: str) -> type | None:
        return self._agents.get(agent_name)

    def list_agents(self) -> dict[str, type]:
        return dict(self._agents)

    # ── Ingesters ─────────────────────────────────────────────────────────────

    def register_ingester(self, source_id: str, cls: type) -> None:
        self._ingesters[source_id] = cls

    def get_ingester(self, source_id: str) -> type | None:
        return self._ingesters.get(source_id)

    def list_ingesters(self) -> dict[str, type]:
        return dict(self._ingesters)

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        return {
            "strategies": list(self._strategies.keys()),
            "adapters": list(self._adapters.keys()),
            "agents": list(self._agents.keys()),
            "ingesters": list(self._ingesters.keys()),
        }


REGISTRY = PluginRegistry()
