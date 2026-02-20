import pandas as pd
import argparse
import re
import sys


def parse_automation_rate(x):
    """
    Converts automation rate to fraction.
    Accepts: 20, 20%, 0.2
    Returns: value between 0 and 1
    """
    if pd.isna(x):
        return 0.0

    x = str(x).strip()

    if "%" in x:
        return float(x.replace("%", "")) / 100.0

    value = float(x)

    if value > 1:
        return value / 100.0

    return value


def main():
    parser = argparse.ArgumentParser(
        description="Rank activities to achieve a target % reduction in total execution time."
    )

    parser.add_argument("--csv", required=True, help="Path to input CSV file")
    parser.add_argument("--goal", type=float, required=True,
                        help="Target reduction percentage (e.g., 10 for 10%)")
    parser.add_argument("--output", default=None,
                        help="Optional: save ranked results to CSV")

    args = parser.parse_args()

    # Load CSV
    df = pd.read_csv(args.csv)

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    required_cols = ["value", "total_duration", "automation_rate"]

    for col in required_cols:
        if col not in df.columns:
            print(f"ERROR: Missing required column '{col}'")
            print("Found columns:", df.columns.tolist())
            sys.exit(1)

    # Clean data
    df["total_duration"] = pd.to_numeric(df["total_duration"], errors="coerce").fillna(0)
    df["automation_rate"] = df["automation_rate"].apply(parse_automation_rate)

    # Compute total execution time
    total_execution_time = df["total_duration"].sum()

    if total_execution_time == 0:
        print("Total execution time is 0. Nothing to reduce.")
        sys.exit(0)

    # Compute target reduction
    goal_fraction = args.goal / 100.0
    target_reduction = total_execution_time * goal_fraction

    # Compute potential savings
    df["potential_savings"] = df["total_duration"] * df["automation_rate"]

    # Rank activities
    ranked = df.sort_values("potential_savings", ascending=False).reset_index(drop=True)

    # Select minimal set to reach goal
    cumulative = 0.0
    selected = []

    for _, row in ranked.iterrows():
        if row["potential_savings"] <= 0:
            continue

        selected.append(row)
        cumulative += row["potential_savings"]

        if cumulative >= target_reduction:
            break

    selected_df = pd.DataFrame(selected)

    # Print results
    print("\n========== RESULTS ==========\n")
    print(f"Total execution time: {total_execution_time:.2f}")
    print(f"Target reduction ({args.goal}%): {target_reduction:.2f}\n")

    print("Ranked activities by potential time savings:")
    print(ranked[["value", "total_duration", "automation_rate", "potential_savings"]])

    print("\nMinimal set of activities to reach target:")
    if not selected_df.empty:
        selected_df["cumulative_savings"] = selected_df["potential_savings"].cumsum()
        print(selected_df[["value", "potential_savings", "cumulative_savings"]])
        achieved_pct = (cumulative / total_execution_time) * 100
        print(f"\nAchieved reduction: {cumulative:.2f} ({achieved_pct:.2f}%)")
    else:
        print("No activities can contribute to reduction based on automation rates.")

    if args.output:
        ranked.to_csv(args.output, index=False)
        print(f"\nSaved ranked results to {args.output}")


if __name__ == "__main__":
    main()

