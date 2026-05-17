"""Plugin Loader — Law 3.

Auto-discovers all extension points at startup by reading the config YAMLs
and importing the modules declared there. No existing file changes when a
new plugin is added — only a new .py file + a config entry.

Called once in main.py startup:
    from app.plugins.loader import discover_all
    discover_all()
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger
from app.plugins.registry import REGISTRY

logger = get_logger(__name__)

# Config root relative to the repo
_CONFIGS_DIR = Path(__file__).parents[3] / "configs"


def _load_yaml(filename: str) -> dict[str, Any]:
    path = _CONFIGS_DIR / filename
    if not path.exists():
        logger.warning("plugin_config_not_found", path=str(path))
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _import_class(module_path: str, class_name: str) -> type | None:
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name, None)
        if cls is None:
            logger.error("plugin_class_not_found", module=module_path, class_name=class_name)
        return cls
    except Exception as exc:
        logger.error("plugin_import_failed", module=module_path, class_name=class_name, error=str(exc))
        return None


# ── Strategies ────────────────────────────────────────────────────────────────

def discover_strategies() -> int:
    """Read configs/strategies.yml, import each enabled strategy, register it."""
    config = _load_yaml("strategies.yml")
    entries = config.get("strategies", [])
    registered = 0
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        strategy_id = entry["id"]
        cls = _import_class(entry["module"], entry["class_name"])
        if cls is None:
            continue
        REGISTRY.register_strategy(strategy_id, cls)
        registered += 1
        logger.info("strategy_registered", id=strategy_id, class_name=entry["class_name"])
    logger.info("strategies_discovered", count=registered)
    return registered


# ── Execution adapters ────────────────────────────────────────────────────────

def discover_adapters() -> int:
    """Scan app/execution/*.py, register every BaseExecutionAdapter subclass."""
    try:
        from app.execution.base import BaseExecutionAdapter
    except ImportError as exc:
        logger.error("adapter_base_import_failed", error=str(exc))
        return 0

    execution_dir = Path(__file__).parent.parent / "execution"
    registered = 0
    for py_file in execution_dir.glob("*.py"):
        if py_file.name.startswith("_") or py_file.stem == "base":
            continue
        module_path = f"app.execution.{py_file.stem}"
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.warning("adapter_module_import_failed", module=module_path, error=str(exc))
            continue
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseExecutionAdapter)
                and obj is not BaseExecutionAdapter
                and getattr(obj, "adapter_id", "")
            ):
                REGISTRY.register_adapter(obj.adapter_id, obj)
                registered += 1
                logger.info("adapter_registered", adapter_id=obj.adapter_id, class_name=attr_name)
    logger.info("adapters_discovered", count=registered)
    return registered


# ── Intelligence agents ───────────────────────────────────────────────────────

def discover_agents() -> int:
    """Read configs/agents.yml, import each enabled agent, register it."""
    config = _load_yaml("agents.yml")
    entries = config.get("agents", [])
    registered = 0
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        agent_id = entry["id"]
        cls = _import_class(entry["module"], entry["class_name"])
        if cls is None:
            continue
        REGISTRY.register_agent(agent_id, cls)
        registered += 1
        logger.info("agent_registered", id=agent_id, class_name=entry["class_name"])
    logger.info("agents_discovered", count=registered)
    return registered


# ── Ingesters ─────────────────────────────────────────────────────────────────

def discover_ingesters() -> int:
    """Scan app/ingestion/*.py for BaseIngester subclasses and register them."""
    try:
        from app.ingestion.base import BaseIngester
    except ImportError as exc:
        logger.error("ingester_base_import_failed", error=str(exc))
        return 0

    ingestion_dir = Path(__file__).parent.parent / "ingestion"
    registered = 0
    for py_file in ingestion_dir.glob("*.py"):
        if py_file.name.startswith("_") or py_file.stem == "base":
            continue
        module_path = f"app.ingestion.{py_file.stem}"
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            logger.warning("ingester_module_import_failed", module=module_path, error=str(exc))
            continue
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseIngester)
                and obj is not BaseIngester
                and getattr(obj, "source_id", "")
            ):
                REGISTRY.register_ingester(obj.source_id, obj)
                registered += 1
                logger.info("ingester_registered", source_id=obj.source_id, class_name=attr_name)
    logger.info("ingesters_discovered", count=registered)
    return registered


# ── Entry point ───────────────────────────────────────────────────────────────

def discover_all() -> dict[str, int]:
    """Run all discoverers. Call once at startup before any component starts."""
    counts = {
        "strategies": discover_strategies(),
        "adapters": discover_adapters(),
        "agents": discover_agents(),
        "ingesters": discover_ingesters(),
    }
    logger.info("plugin_discovery_complete", **counts)
    return counts
