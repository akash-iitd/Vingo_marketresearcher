"""
Liquidity analyzer — converts raw scrape data into category rankings.

Liquidity Score (0–100):
  40% → listing volume (normalized across all categories on same source)
  40% → freshness — % of listings posted in last 7 days
  20% → activity velocity — % of listings posted in last 24h

High score = people actively listing AND recent = market is alive.
"""

import pandas as pd
import numpy as np
from typing import Optional


def _normalize(series: pd.Series) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([50.0] * len(series), index=series.index)
    return (series - mn) / (mx - mn) * 100


def compute_liquidity_scores(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Drop rows with no data at all
    df = df[df["total_listings"].notna()].copy()
    df["total_listings"] = df["total_listings"].fillna(0).astype(int)
    df["freshness_7d_pct"] = df["freshness_7d_pct"].fillna(0)
    df["freshness_24h_pct"] = df["freshness_24h_pct"].fillna(0)

    # Data quality: flag categories that returned 0 listings with no error
    zero_mask = (df["total_listings"] == 0) & df["error"].isna()
    if zero_mask.any():
        df.loc[zero_mask, "error"] = "No listings found"

    # Normalize volume within each source to avoid OLX vs Quikr bias
    df["volume_score"] = df.groupby("source")["total_listings"].transform(_normalize)

    # Freshness scores already 0–100
    df["freshness_7d_score"] = df["freshness_7d_pct"]
    df["freshness_24h_score"] = df["freshness_24h_pct"]

    # Composite liquidity score
    df["liquidity_score"] = (
        df["volume_score"] * 0.40
        + df["freshness_7d_score"] * 0.40
        + df["freshness_24h_score"] * 0.20
    ).round(1)

    # Sort descending
    df = df.sort_values("liquidity_score", ascending=False).reset_index(drop=True)
    df.index += 1  # rank starts at 1
    df.index.name = "rank"

    return df


def aggregate_cross_platform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge OLX + Quikr data for the same logical category into one
    unified ranking. Uses normalized names for grouping.
    """
    if df.empty:
        return df

    # Normalize category names for grouping
    df = df.copy()
    df["category_norm"] = (
        df["category"]
        .str.lower()
        .str.replace(r"[^a-z0-9 ]", "", regex=True)
        .str.strip()
    )

    # Aggregate: mean liquidity score, sum of listing volumes across sources
    agg = df.groupby("category_norm").agg(
        category=("category", "first"),
        sources=("source", lambda x: " + ".join(sorted(set(x)))),
        avg_liquidity_score=("liquidity_score", "mean"),
        total_listings=("total_listings", "sum"),
        max_freshness_7d=("freshness_7d_pct", "max"),
        max_freshness_24h=("freshness_24h_pct", "max"),
    ).reset_index(drop=True)

    agg["avg_liquidity_score"] = agg["avg_liquidity_score"].round(1)
    agg = agg.sort_values("avg_liquidity_score", ascending=False).reset_index(drop=True)
    agg.index += 1
    agg.index.name = "rank"

    return agg


def tier_label(score: float) -> str:
    if score >= 70:
        return "TIER 1 — High Liquidity"
    if score >= 45:
        return "TIER 2 — Moderate Liquidity"
    if score >= 20:
        return "TIER 3 — Low Liquidity"
    return "TIER 4 — Niche / Illiquid"
