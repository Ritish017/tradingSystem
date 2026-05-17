"""initial trading tables

Revision ID: 20260514_0001
Revises:
Create Date: 2026-05-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260514_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("instrument", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_trades_order_id", "trades", ["order_id"])
    op.create_index("ix_trades_instrument", "trades", ["instrument"])

    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("client_order_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("instrument", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("order_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_orders_client_order_id", "orders", ["client_order_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_instrument", "orders", ["instrument"])

    op.create_table(
        "positions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("instrument", sa.String(length=64), nullable=False, unique=True),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("avg_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_positions_instrument", "positions", ["instrument"])

    op.create_table(
        "strategies",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("strategy_type", sa.String(length=32), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("allocated_capital", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("current_weight", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_strategies_name", "strategies", ["name"])
    op.create_index("ix_strategies_type", "strategies", ["strategy_type"])
    op.create_index("ix_strategies_asset", "strategies", ["asset_class"])
    op.create_index("ix_strategies_status", "strategies", ["status"])

    op.create_table(
        "strategy_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_strategy_runs_strategy_id", "strategy_runs", ["strategy_id"])
    op.create_index("ix_strategy_runs_run_type", "strategy_runs", ["run_type"])
    op.create_index("ix_strategy_runs_status", "strategy_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_strategy_runs_status", table_name="strategy_runs")
    op.drop_index("ix_strategy_runs_run_type", table_name="strategy_runs")
    op.drop_index("ix_strategy_runs_strategy_id", table_name="strategy_runs")
    op.drop_table("strategy_runs")

    op.drop_index("ix_strategies_status", table_name="strategies")
    op.drop_index("ix_strategies_asset", table_name="strategies")
    op.drop_index("ix_strategies_type", table_name="strategies")
    op.drop_index("ix_strategies_name", table_name="strategies")
    op.drop_table("strategies")

    op.drop_index("ix_positions_instrument", table_name="positions")
    op.drop_table("positions")

    op.drop_index("ix_orders_instrument", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_client_order_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_trades_instrument", table_name="trades")
    op.drop_index("ix_trades_order_id", table_name="trades")
    op.drop_table("trades")

