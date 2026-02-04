#!/usr/bin/env python3
"""
Rank activities that help achieve a target % reduction in TOTAL rework COST.

CSV requirements (case-insensitive):
- value  (activity name)
- Total rework cost
- automation_rate   (examples: "20%", 20, 0.2)

Logic:
- total_cost = sum(Total rework cost)
- target_cost = goal_pct * total_cost
- reducible_cost(activity) = Total rework cost * automation_rate
- Rank by reducible_cost desc
- Select minimal set with cumulative reducible_cost >= target_cost

Example:
  python rework_cost_rank.py --csv RepairExample_workingData.csv --goal 5
  python rework_cost_rank.py --csv RepairExample_workingData.csv --goal 10 --out ranked_cost.csv
"""

from __future__ import annotations
import argparse
import re
import sys
from typing import Optional, List

import pandas as pd


def find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Return the first matching column name (case-insensitive) from candidates."""
    lookup = {c.strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in lookup:
            return lookup[key]
    return None


def parse_rate(x) -> float:
    """
    Parse automation_rate values into a fraction in [0, 1].
    Accepts: "20%", "20", 20, 0.2
    """
    if pd.isna(x):
        return 0.0
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return 0.0
        m = re.search(r"[-+]?\d*\.?\d+", s)
        if not m:
            return 0.0
        v = float(m.group(0))
        if "%" in s:
            return max(0.0, min(1.0, v / 100.0))
        return max(0.0, min(1.0, v / 100.0 if v > 1 else v))

    v = float(x)
    if v > 1:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to input CSV")
    ap.add_argument("--goal", type=float, required=True,
                    help="Target reduction percent of TOTAL rework COST (e.g., 5 for 5%%)")
    ap.add_argument("--out", default=None, help="Optional: save ranked table to this CSV")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)

    col_activity = find_col(df, ["value", "activity", "activity_name", "name"])
    col_cost = find_col(df, ["total rework cost", "rework_cost", "rework cost", "total_rework_cost"])
    col_rate = find_col(df, ["automation_rate", "automation rate", "automation"])

    missing = []
    if col_activity is None:
        missing.append("value/activity")
    if col_cost is None:
        missing.append("Total rework cost")
    if col_rate is None:
        missing.append("automation_rate")

    if missing:
        print("ERROR: Missing required columns: " + ", ".join(missing), file=sys.stderr)
        print("Found columns:", list(df.columns), file=sys.stderr)
        return 2

    work = df[[col_activity, col_cost, col_rate]].copy()
    work.columns = ["activity", "rework_cost", "automation_rate_raw"]

    work["rework_cost"] = pd.to_numeric(work["rework_cost"], errors="coerce").fillna(0.0)
    work["automation_rate"] = work["automation_rate_raw"].apply(parse_rate)

    total_cost = float(work["rework_cost"].sum())
    if total_cost <= 0:
        print("Total rework cost is 0. Nothing to reduce.")
        return 0

    goal_fraction = args.goal / 100.0
    target_cost = total_cost * goal_fraction

    work["reducible_rework_cost"] = work["rework_cost"] * work["automation_rate"]

    ranked = work.sort_values(
        ["reducible_rework_cost", "rework_cost"],
        ascending=[False, False]
    ).reset_index(drop=True)

    # Select minimal set to hit the goal
    selected = []
    cum = 0.0
    for _, row in ranked.iterrows():
        if row["reducible_rework_cost"] <= 0:
            continue
        selected.append(row)
        cum += float(row["reducible_rework_cost"])
        if cum + 1e-9 >= target_cost:
            break

    achieved_pct = (cum / total_cost) * 100.0

    # Print results
    print(f"Total rework cost:  {total_cost:.2f}")
    print(f"Goal reduction:     {args.goal:.2f}% => {target_cost:.2f}\n")

    print("Ranked activities:")
    print(ranked[["activity", "rework_cost", "automation_rate", "reducible_rework_cost"]].to_string(index=False))

    print("\nSelected activities to achieve the goal (minimal set):")
    if not selected:
        print("  None (no reducible rework cost based on automation_rate).")
    else:
        sel_df = pd.DataFrame(selected)[["activity", "rework_cost", "automation_rate", "reducible_rework_cost"]]
        sel_df["cum_reducible_rework_cost"] = sel_df["reducible_rework_cost"].cumsum()
        print(sel_df.to_string(index=False))
        print(f"\nAchieved reduction: {cum:.2f} ({achieved_pct:.2f}% of total rework cost)")

    if args.out:
        ranked.to_csv(args.out, index=False)
        print(f"\nSaved ranked table to: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
