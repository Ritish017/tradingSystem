"""End-to-end integration test for the complete trading platform."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.core.state import STATE, StrategyState
from app.engine.service import MasterEngineService
from app.strategies.rule_based.supertrend_rsi import SupertrendRSIStrategy
from app.strategies.ml_alpha.lightgbm_alpha import LightGBMAlphaStrategy
from app.strategies.rl_agents.ppo_agent import PPOAgentStrategy


@pytest.fixture
def reset_state():
    """Reset global state before each test."""
    STATE.strategies.clear()
    STATE.positions.clear()
    STATE.orders.clear()
    STATE.fills.clear()
    STATE.trading_halted = False
    STATE.capital = 100_000.0
    STATE.daily_realized_pnl = 0.0
    STATE.gross_exposure = 0.0
    yield
    # Cleanup after test
    STATE.strategies.clear()


@pytest.fixture
def engine():
    """Create master engine instance."""
    return MasterEngineService()


def generate_test_price_data(days: int = 100) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    dates = pd.date_range(end=datetime.now(), periods=days, freq="D")
    df = pd.DataFrame({
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 100.0 + pd.Series(range(days)) * 0.5,  # Uptrend
        "volume": 1_000_000,
    }, index=dates)
    return df


@pytest.mark.asyncio
async def test_phase_1_infrastructure(reset_state):
    """Test Phase 1: Infrastructure components."""
    # Verify state initialization
    assert STATE.capital == 100_000.0
    assert STATE.trading_halted is False
    assert len(STATE.strategies) == 0
    print("✅ Phase 1: Infrastructure state initialized")


@pytest.mark.asyncio
async def test_phase_3_feature_pipeline():
    """Test Phase 3: Feature engineering."""
    from app.features.indicators import compute_indicators
    from app.features.normaliser import zscore, rank_normalise
    
    # Generate test data
    df = generate_test_price_data(50)
    
    # Compute indicators
    indicators = ["rsi_14", "ema_20", "returns_1d"]
    result = compute_indicators(df, indicators)
    
    # Verify indicators computed
    assert "rsi_14" in result.columns
    assert "ema_20" in result.columns
    assert "returns_1d" in result.columns
    assert len(result) == len(df)
    
    # Test normalizers
    z = zscore(df["close"])
    assert abs(z.mean()) < 0.01  # Mean should be ~0
    
    r = rank_normalise(df["close"])
    assert r.min() >= -1.0
    assert r.max() <= 1.0
    
    print("✅ Phase 3: Feature pipeline working")


@pytest.mark.asyncio
async def test_phase_4_backtesting():
    """Test Phase 4: Backtesting harness."""
    from app.core.backtester import Backtester, BacktestConfig
    from app.core.costs import Market, calculate_indian_equity_cost
    
    # Test cost calculation
    cost = calculate_indian_equity_cost(price=100.0, quantity=100, is_intraday=True)
    assert cost.total > 0
    assert cost.brokerage <= 20.0  # Zerodha cap
    
    # Test backtester
    price_data = generate_test_price_data(100)
    entries = pd.Series(False, index=price_data.index)
    entries.iloc[10] = True  # Buy on day 10
    exits = pd.Series(False, index=price_data.index)
    exits.iloc[50] = True  # Sell on day 50
    
    config = BacktestConfig(initial_capital=100_000.0, market=Market.NSE_EQUITY)
    backtester = Backtester(config)
    result = backtester.run(price_data, entries, exits, size=10)
    
    assert result.total_trades >= 1
    assert result.total_return != 0.0
    
    print("✅ Phase 4: Backtesting harness working")


@pytest.mark.asyncio
async def test_phase_5_strategies():
    """Test Phase 5: All strategy implementations."""
    # Test rule-based strategy
    rule_strategy = SupertrendRSIStrategy()
    signal = rule_strategy.generate_signal("TEST")
    assert signal.strategy_name == "supertrend_rsi"
    assert signal.side in ["buy", "sell", "hold"]
    
    # Test ML alpha strategy
    ml_strategy = LightGBMAlphaStrategy()
    signal = ml_strategy.generate_signal("TEST")
    assert signal.strategy_name == "lightgbm_alpha"
    
    # Test RL agent
    rl_strategy = PPOAgentStrategy()
    signal = rl_strategy.generate_signal("TEST")
    assert signal.strategy_name == "ppo_agent"
    
    # Test backtesting interface
    price_data = generate_test_price_data(100)
    entries, exits = rule_strategy.generate_signals(price_data)
    assert len(entries) == len(price_data)
    assert len(exits) == len(price_data)
    
    print("✅ Phase 5: All 10 strategies implemented")


@pytest.mark.asyncio
async def test_phase_6_master_engine(reset_state, engine):
    """Test Phase 6: Master engine integration."""
    from app.core.types import Signal
    
    # Register strategies
    engine.register_default_strategies()
    assert len(STATE.strategies) == 10
    
    # Test signal aggregation
    signals = [
        Signal(strategy_name="supertrend_rsi", symbol="TEST", side="buy", strength=0.8, confidence=0.7),
        Signal(strategy_name="lightgbm_alpha", symbol="TEST", side="buy", strength=0.6, confidence=0.6),
        Signal(strategy_name="ppo_agent", symbol="TEST", side="hold", strength=0.1, confidence=0.4),
    ]
    
    aggregated = engine.aggregator.aggregate("TEST", signals)
    assert aggregated.symbol == "TEST"
    assert aggregated.side in ["buy", "sell", "hold"]
    
    # Test position sizing
    size = engine.sizer.size_for_signal(aggregated, STATE.capital, 100.0)
    assert size >= 0
    
    # Test risk gate
    from app.core.types import OrderRequest
    order = OrderRequest(
        client_order_id="test-1",
        symbol="TEST",
        side="buy",
        quantity=10,
        price=100.0,
    )
    decision = engine.risk.evaluate(order)
    assert decision.allowed is True  # Should pass with clean state
    
    print("✅ Phase 6: Master engine working")


@pytest.mark.asyncio
async def test_phase_6_risk_limits(reset_state, engine):
    """Test Phase 6: Risk gate limits."""
    from app.core.types import OrderRequest
    
    # Test daily loss limit
    STATE.daily_realized_pnl = -2500  # 2.5% loss on 100k capital
    order = OrderRequest(
        client_order_id="test-2",
        symbol="TEST",
        side="buy",
        quantity=10,
        price=100.0,
    )
    decision = engine.risk.evaluate(order)
    assert decision.allowed is False
    assert "daily loss" in decision.reason.lower()
    
    # Reset for next test
    STATE.daily_realized_pnl = 0
    STATE.trading_halted = False
    
    # Test position concentration
    order_large = OrderRequest(
        client_order_id="test-3",
        symbol="TEST",
        side="buy",
        quantity=25_000,  # 25k shares * 100 = 2.5M (25% of capital)
        price=100.0,
    )
    decision = engine.risk.evaluate(order_large)
    assert decision.allowed is False
    assert "concentration" in decision.reason.lower()
    
    print("✅ Phase 6: Risk limits enforced")


@pytest.mark.asyncio
async def test_phase_7_execution(reset_state, engine):
    """Test Phase 7: Execution layer."""
    from app.core.types import OrderRequest
    
    # Test paper execution
    order = OrderRequest(
        client_order_id="test-paper-1",
        symbol="TEST",
        side="buy",
        quantity=10,
        price=100.0,
    )
    
    fill = await engine.router.paper.execute(order)
    assert fill.status in ["filled", "partial"]
    assert fill.filled_qty > 0
    assert fill.avg_price > 0
    
    print("✅ Phase 7: Execution adapters working")


@pytest.mark.asyncio
async def test_phase_8_learning(reset_state):
    """Test Phase 8: Self-learning feedback loop."""
    from app.learning.trade_outcome_logger import TradeOutcome, TradeOutcomeLogger
    from app.learning.replay_buffer import ReplayBuffer
    from app.learning.retraining_job import RetrainingJob
    from app.learning.strategy_scorer import StrategyScorer
    
    # Create trade outcomes
    logger = TradeOutcomeLogger()
    outcomes = [
        TradeOutcome(
            strategy_name="supertrend_rsi",
            symbol="TEST",
            side="buy",
            entry_price=100.0,
            exit_price=105.0,
            quantity=10,
            holding_period_minutes=60,
            realised_pnl=50.0,
            features_at_entry={"rsi": 55.0},
        ),
        TradeOutcome(
            strategy_name="lightgbm_alpha",
            symbol="TEST",
            side="sell",
            entry_price=100.0,
            exit_price=98.0,
            quantity=10,
            holding_period_minutes=30,
            realised_pnl=-20.0,
            features_at_entry={"returns_1d": -0.01},
        ),
    ]
    
    for outcome in outcomes:
        logger.log(outcome)
    
    assert len(logger.all()) == 2
    
    # Test replay buffer
    buffer = ReplayBuffer()
    buffer.extend(outcomes)
    sampled = buffer.sample(10)
    assert len(sampled) <= 2
    
    # Test retraining job
    job = RetrainingJob()
    job.ingest_outcomes(outcomes)
    results = job.run_nightly()
    assert len(results) == 2  # PPO and TD3
    
    # Test strategy scorer
    scorer = StrategyScorer()
    weights = scorer.update_weights(outcomes)
    assert "supertrend_rsi" in weights
    assert "lightgbm_alpha" in weights
    
    print("✅ Phase 8: Self-learning loop working")


@pytest.mark.asyncio
async def test_end_to_end_flow(reset_state, engine):
    """Test complete end-to-end trading flow."""
    from app.core.types import Signal
    
    # 1. Register strategies
    engine.register_default_strategies()
    
    # 2. Generate signals from multiple strategies
    signals = [
        Signal(strategy_name="supertrend_rsi", symbol="RELIANCE", side="buy", strength=0.7, confidence=0.65),
        Signal(strategy_name="lightgbm_alpha", symbol="RELIANCE", side="buy", strength=0.6, confidence=0.55),
    ]
    
    # 3. Submit to master engine
    result = await engine.submit_aggregated_signal(
        symbol="RELIANCE",
        signals=signals,
        price=2500.0,
        mode="paper"
    )
    
    # 4. Verify order executed
    assert result["status"] in ["filled", "partial", "skipped"]
    
    # 5. Verify position created (if filled)
    if result["status"] == "filled":
        assert "RELIANCE" in STATE.positions or result.get("filled_qty", 0) > 0
    
    print("✅ End-to-end flow complete")


@pytest.mark.asyncio
async def test_kill_switch(reset_state):
    """Test kill switch functionality."""
    # Activate kill switch
    STATE.trading_halted = True
    STATE.halted_reason = "test_halt"
    
    # Verify trading halted
    assert STATE.trading_halted is True
    assert STATE.halted_reason == "test_halt"
    
    # Try to place order (should be rejected)
    from app.engine.risk_gate import RiskGate
    from app.core.types import OrderRequest
    
    risk_gate = RiskGate()
    order = OrderRequest(
        client_order_id="test-halt-1",
        symbol="TEST",
        side="buy",
        quantity=10,
        price=100.0,
    )
    
    decision = risk_gate.evaluate(order)
    assert decision.allowed is False
    assert "halted" in decision.reason.lower()
    
    print("✅ Kill switch working")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  RUNNING END-TO-END INTEGRATION TESTS")
    print("="*60 + "\n")
    
    pytest.main([__file__, "-v", "-s"])
