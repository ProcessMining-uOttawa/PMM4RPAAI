#!/usr/bin/env python3
"""
Rank activities that help achieve a target % reduction in TOTAL rework time.

Logic (from your table):
- total_rework = sum("Total rework hours")
- target_hours = goal_pct * total_rework
- reducible_rework(activity) = "Total rework hours" * automation_rate
- Rank by reducible_rework desc
- Select the minimal top-ranked set whose cumulative reducible_rework >= target_hours

CSV requirements (case-insensitive, spaces ok):
- value  (activity name)
- Total rework hours
- automation_rate   (examples: "20%", 20, 0.2)

Example:
  python rework_rank.py --csv RepairExample_workingData.csv --goal 5
  python rework_rank.py --csv activities.csv --goal 10 --out ranked.csv
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
                    help="Target reduction percent of TOTAL rework time (e.g., 5 for 5%%)")
    ap.add_argument("--out", default=None, help="Optional: save ranked table to this CSV")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)

    col_activity = find_col(df, ["value", "activity", "activity_name", "name"])
    col_rework = find_col(df, ["total rework hours", "rework_hours", "rework hours"])
    col_rate = find_col(df, ["automation_rate", "automation rate", "automation"])

    missing = []
    if col_activity is None:
        missing.append("value/activity")
    if col_rework is None:
        missing.append("Total rework hours")
    if col_rate is None:
        missing.append("automation_rate")

    if missing:
        print("ERROR: Missing required columns: " + ", ".join(missing), file=sys.stderr)
        print("Found columns:", list(df.columns), file=sys.stderr)
        return 2

    work = df[[col_activity, col_rework, col_rate]].copy()
    work.columns = ["activity", "rework_hours", "automation_rate_raw"]

    work["rework_hours"] = pd.to_numeric(work["rework_hours"], errors="coerce").fillna(0.0)
    work["automation_rate"] = work["automation_rate_raw"].apply(parse_rate)

    total_rework = float(work["rework_hours"].sum())
    if total_rework <= 0:
        print("Total rework hours is 0. Nothing to reduce.")
        return 0

    goal_fraction = args.goal / 100.0
    target_hours = total_rework * goal_fraction

    work["reducible_rework_hours"] = work["rework_hours"] * work["automation_rate"]

    ranked = work.sort_values(
        ["reducible_rework_hours", "rework_hours"],
        ascending=[False, False]
    ).reset_index(drop=True)

    # Select minimal set to hit the goal
    selected = []
    cum = 0.0
    for _, row in ranked.iterrows():
        if row["reducible_rework_hours"] <= 0:
            continue
        selected.append(row)
        cum += float(row["reducible_rework_hours"])
        if cum + 1e-9 >= target_hours:
            break

    achieved_pct = (cum / total_rework) * 100.0

    # Print results
    print(f"Total rework hours: {total_rework:.2f}")
    print(f"Goal reduction:     {args.goal:.2f}% => {target_hours:.2f} hours\n")

    print("Ranked activities:")
    print(ranked[["activity", "rework_hours", "automation_rate", "reducible_rework_hours"]].to_string(index=False))

    print("\nSelected activities to achieve the goal (minimal set):")
    if not selected:
        print("  None (no reducible rework based on automation_rate).")
    else:
        sel_df = pd.DataFrame(selected)[["activity", "rework_hours", "automation_rate", "reducible_rework_hours"]]
        sel_df["cum_reducible_rework_hours"] = sel_df["reducible_rework_hours"].cumsum()
        print(sel_df.to_string(index=False))
        print(f"\nAchieved reduction: {cum:.2f} hours ({achieved_pct:.2f}% of total rework)")

    if args.out:
        ranked.to_csv(args.out, index=False)
        print(f"\nSaved ranked table to: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
