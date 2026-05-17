from __future__ import annotations

from app.strategies.rule_based.crypto_momentum import CryptoMomentumStrategy


def test_crypto_momentum_generates_buy_signal() -> None:
    strategy = CryptoMomentumStrategy(lookback=5)
    prices = [100, 101, 102, 103, 104, 108]
    for price in prices:
        strategy.on_bar("BTCUSDT", price)
    signal = strategy.generate_signal("BTCUSDT")
    assert signal.side == "buy"
    assert signal.strength > 0

