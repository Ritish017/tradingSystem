from __future__ import annotations

import pandas as pd


def zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if std == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def rank_normalise(series: pd.Series) -> pd.Series:
    ranks = series.rank(pct=True, method="average")
    return (ranks - 0.5) * 2


def neutralise_against(df: pd.DataFrame, value_col: str, by_cols: list[str]) -> pd.Series:
    if value_col not in df.columns:
        raise ValueError(f"{value_col} not found")
    if not by_cols:
        return df[value_col]
    centered = df[value_col]
    for col in by_cols:
        centered = centered - df.groupby(col)[value_col].transform("mean")
    return centered

