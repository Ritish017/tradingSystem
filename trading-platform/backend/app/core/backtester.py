from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import vectorbt as vbt

from app.core.costs import Market, calculate_crypto_cost, calculate_indian_equity_cost, calculate_slippage


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    market: Market = Market.NSE_EQUITY
    broker: str = "zerodha"
    is_intraday: bool = False
    slippage_model: str = "fixed"  # "fixed" or "volume"
    fixed_slippage_bps: float = 5.0


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: pd.DataFrame
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    total_cost: float


class Backtester:
    """Vectorbt-based backtester with realistic Indian market costs."""
    
    def __init__(self, config: BacktestConfig) -> None:
        self.config = config
        self._logger = logging.getLogger(__name__)
    
    def run(
        self,
        price_data: pd.DataFrame,
        entries: pd.Series,
        exits: pd.Series,
        size: float | pd.Series = 1.0,
    ) -> BacktestResult:
        """Run backtest with entries/exits signals.
        
        Args:
            price_data: DataFrame with 'open', 'high', 'low', 'close', 'volume'
            entries: Boolean series indicating entry signals
            exits: Boolean series indicating exit signals
            size: Position size (shares or contracts)
        
        Returns:
            BacktestResult with all metrics
        """
        self._logger.info("Running backtest from %s to %s", price_data.index[0], price_data.index[-1])
        
        # Calculate costs per trade
        avg_price = price_data["close"].mean()
        if self.config.market == Market.CRYPTO:
            cost_per_trade = calculate_crypto_cost(avg_price, 1.0).total
        else:
            cost_per_trade = calculate_indian_equity_cost(
                avg_price, 1, self.config.is_intraday, self.config.broker
            ).total
        
        # Add slippage
        if self.config.slippage_model == "fixed":
            slippage = avg_price * self.config.fixed_slippage_bps / 10000
        else:
            slippage = calculate_slippage(avg_price, 1.0, self.config.market)
        
        total_cost_per_trade = cost_per_trade + slippage
        
        # Run vectorbt portfolio simulation
        pf = vbt.Portfolio.from_signals(
            close=price_data["close"],
            entries=entries,
            exits=exits,
            size=size,
            init_cash=self.config.initial_capital,
            fees=total_cost_per_trade,
            freq="1D",
        )
        
        # Extract metrics
        equity_curve = pf.value()
        trades_df = pf.trades.records_readable
        
        total_return = pf.total_return()
        sharpe = pf.sharpe_ratio()
        sortino = pf.sortino_ratio()
        max_dd = pf.max_drawdown()
        
        if len(trades_df) > 0:
            win_rate = (trades_df["PnL"] > 0).sum() / len(trades_df)
            total_cost = trades_df["Fees"].sum()
        else:
            win_rate = 0.0
            total_cost = 0.0
        
        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades_df,
            total_return=total_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            win_rate=win_rate,
            total_trades=len(trades_df),
            total_cost=total_cost,
        )
    
    def optimize(
        self,
        price_data: pd.DataFrame,
        strategy_func: callable,
        param_grid: dict,
    ) -> pd.DataFrame:
        """Run parameter sweep optimization.
        
        Args:
            price_data: OHLCV DataFrame
            strategy_func: Function that takes (price_data, **params) and returns (entries, exits)
            param_grid: Dict of parameter ranges, e.g. {"rsi_period": [10, 14, 20]}
        
        Returns:
            DataFrame with all parameter combinations and their Sharpe ratios
        """
        import itertools
        
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        results = []
        for combo in itertools.product(*param_values):
            params = dict(zip(param_names, combo))
            self._logger.debug("Testing params: %s", params)
            
            try:
                entries, exits = strategy_func(price_data, **params)
                result = self.run(price_data, entries, exits)
                
                results.append({
                    **params,
                    "sharpe": result.sharpe_ratio,
                    "total_return": result.total_return,
                    "max_dd": result.max_drawdown,
                    "trades": result.total_trades,
                })
            except Exception as exc:
                self._logger.warning("Param combo %s failed: %s", params, exc)
        
        return pd.DataFrame(results).sort_values("sharpe", ascending=False)
