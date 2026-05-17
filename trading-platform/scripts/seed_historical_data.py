from __future__ import annotations

import argparse
from datetime import UTC, date, datetime

from app.ingestion.india_equities import IndiaEquityIngestionService


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


async def main_async(symbols: list[str], start: date, end: date) -> None:
    ingestor = IndiaEquityIngestionService()
    total_rows = 0
    for symbol in symbols:
        rows = await ingestor.ingest_symbol_history(symbol=symbol, start=start, end=end)
        total_rows += rows
    print(
        f"seeded {total_rows} rows across {len(symbols)} symbols at "
        f"{datetime.now(UTC).isoformat()}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed historical data into ingestion pipeline")
    parser.add_argument("--symbols", nargs="+", default=["RELIANCE", "TCS", "INFY"])
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args()
    import asyncio

    asyncio.run(main_async(args.symbols, _parse_date(args.start), _parse_date(args.end)))


if __name__ == "__main__":
    main()

