#!/usr/bin/env python
"""Backtest runner CLI with QuantStats tearsheet and MLflow logging."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import mlflow
import pandas as pd
import quantstats as qs

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.backtester import Backtester, BacktestConfig
from app.core.costs import Market
from app.strategies.rule_based.supertrend_rsi import SupertrendRSIStrategy


def load_historical_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Load historical data from InfluxDB or CSV fallback."""
    # TODO: Connect to InfluxDB
    # For now, generate synthetic data
    dates = pd.date_range(start, end, freq="D")
    df = pd.DataFrame({
        "open": 100 + pd.Series(range(len(dates))).cumsum() * 0.1,
        "high": 105 + pd.Series(range(len(dates))).cumsum() * 0.1,
        "low": 95 + pd.Series(range(len(dates))).cumsum() * 0.1,
        "close": 100 + pd.Series(range(len(dates))).cumsum() * 0.1,
        "volume": 1000000,
    }, index=dates)
    df["high"] = df[["open", "close", "high"]].max(axis=1)
    df["low"] = df[["open", "close", "low"]].min(axis=1)
    return df


def main():
    parser = argparse.ArgumentParser(description="Run strategy backtest")
    parser.add_argument("--strategy", required=True, help="Strategy name")
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100000, help="Initial capital")
    parser.add_argument("--market", default="nse_equity", help="Market type")
    parser.add_argument("--output", default="backtest_results", help="Output directory")
    
    args = parser.parse_args()
    
    symbols = args.symbols.split(",")
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)
    
    # Initialize MLflow
    mlflow.set_experiment(f"backtest_{args.strategy}")
    
    with mlflow.start_run(run_name=f"{args.strategy}_{args.start}_{args.end}"):
        mlflow.log_params({
            "strategy": args.strategy,
            "symbols": args.symbols,
            "start_date": args.start,
            "end_date": args.end,
            "initial_capital": args.capital,
            "market": args.market,
        })
        
        all_results = []
        
        for symbol in symbols:
            print(f"\n{'='*60}")
            print(f"Backtesting {args.strategy} on {symbol}")
            print(f"{'='*60}\n")
            
            # Load data
            price_data = load_historical_data(symbol, args.start, args.end)
            
            # Initialize strategy
            if args.strategy == "supertrend_rsi":
                strategy = SupertrendRSIStrategy()
            else:
                raise ValueError(f"Unknown strategy: {args.strategy}")
            
            # Generate signals
            entries, exits = strategy.generate_signals(price_data)
            
            # Run backtest
            config = BacktestConfig(
                initial_capital=args.capital,
                market=Market(args.market),
            )
            backtester = Backtester(config)
            result = backtester.run(price_data, entries, exits)
            
            # Log metrics to MLflow
            mlflow.log_metrics({
                f"{symbol}_total_return": result.total_return,
                f"{symbol}_sharpe": result.sharpe_ratio,
                f"{symbol}_sortino": result.sortino_ratio,
                f"{symbol}_max_dd": result.max_drawdown,
                f"{symbol}_win_rate": result.win_rate,
                f"{symbol}_total_trades": result.total_trades,
            })
            
            # Generate QuantStats tearsheet
            returns = result.equity_curve.pct_change().dropna()
            tearsheet_path = output_dir / f"{symbol}_tearsheet.html"
            qs.reports.html(returns, output=str(tearsheet_path), title=f"{args.strategy} - {symbol}")
            mlflow.log_artifact(str(tearsheet_path))
            
            print(f"\nResults for {symbol}:")
            print(f"  Total Return: {result.total_return:.2%}")
            print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
            print(f"  Sortino Ratio: {result.sortino_ratio:.2f}")
            print(f"  Max Drawdown: {result.max_drawdown:.2%}")
            print(f"  Win Rate: {result.win_rate:.2%}")
            print(f"  Total Trades: {result.total_trades}")
            print(f"  Total Costs: ₹{result.total_cost:.2f}")
            print(f"\n  Tearsheet saved to: {tearsheet_path}")
            
            all_results.append({
                "symbol": symbol,
                "total_return": result.total_return,
                "sharpe": result.sharpe_ratio,
                "sortino": result.sortino_ratio,
                "max_dd": result.max_drawdown,
                "win_rate": result.win_rate,
                "trades": result.total_trades,
            })
        
        # Summary
        summary_df = pd.DataFrame(all_results)
        summary_path = output_dir / "summary.csv"
        summary_df.to_csv(summary_path, index=False)
        mlflow.log_artifact(str(summary_path))
        
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}\n")
        print(summary_df.to_string(index=False))
        print(f"\nAverage Sharpe: {summary_df['sharpe'].mean():.2f}")
        print(f"MLflow run: {mlflow.active_run().info.run_id}")


if __name__ == "__main__":
    main()
