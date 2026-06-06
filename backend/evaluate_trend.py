"""Walk-forward validation report for Holt's linear trend prediction.

Usage:
    python evaluate_trend.py               # summary table for all flags
    python evaluate_trend.py --flag japan  # detail for one flag
    python evaluate_trend.py --top 10      # worst MAE flags (descending)
"""
import argparse
import sys

from data_pipeline import compute_temporal_trends
from temporal_trend_prediction import walk_forward_validate


def run_validation(trends: list[dict]) -> list:
    results = []
    for entry in trends:
        yearly = [
            {**pt, "flag_key": entry["flag_key"]}
            for pt in entry["yearly"]
        ]
        result = walk_forward_validate(yearly)
        if result is None:
            continue
        result.flag_key = entry["flag_key"]
        results.append((entry["flag"], result))
    return results


def print_summary(results: list, top_n: int | None = None) -> None:
    rows = sorted(
        [(flag, r) for flag, r in results if not _isnan(r.mae)],
        key=lambda x: x[1].mae,
        reverse=True,
    )
    if top_n:
        rows = rows[:top_n]

    header = f"{'Flag':<30} {'Rounds':>6} {'MAE':>10} {'MAPE%':>10}"
    print(header)
    print("-" * len(header))
    for flag, r in rows:
        mape_str = f"{r.mape:10.1f}" if not _isnan(r.mape) else f"{'N/A':>10}"
        print(f"{flag:<30} {len(r.rounds):>6} {r.mae:10.6f} {mape_str}")

    valid_mae  = [r.mae  for _, r in results if not _isnan(r.mae)]
    valid_mape = [r.mape for _, r in results if not _isnan(r.mape)]
    print()
    print(f"Flags evaluated : {len(results)}")
    if valid_mae:
        print(f"Mean MAE        : {sum(valid_mae)  / len(valid_mae):.6f}")
    if valid_mape:
        print(f"Mean MAPE       : {sum(valid_mape) / len(valid_mape):.1f}%")


def print_flag_detail(flag_name: str, results: list) -> None:
    match = [(f, r) for f, r in results if f.lower() == flag_name.lower()
             or r.flag_key == flag_name.lower()]
    if not match:
        print(f"Flag '{flag_name}' not found.")
        sys.exit(1)

    flag, result = match[0]
    print(f"\n{'='*55}")
    print(f"Flag: {flag}  |  Validation rounds: {len(result.rounds)}")
    print(f"MAE: {result.mae:.6f}  MAPE: {result.mape:.1f}%")
    print(f"{'='*55}")
    print(f"{'Train end':>12} {'Predicted':>12} {'Actual':>12} {'Error':>12}")
    print("-" * 55)
    for r in result.rounds:
        print(
            f"{r.train_end_year:>12} "
            f"{r.predicted_rate:>12.6f} "
            f"{r.actual_rate:>12.6f} "
            f"{r.error:>+12.6f}"
        )


def _isnan(v: float) -> bool:
    import math
    return math.isnan(v)


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward validation for Holt trend model")
    parser.add_argument("--flag", metavar="NAME", help="Show detail for one flag")
    parser.add_argument("--top",  metavar="N",    type=int, help="Show top N worst MAE flags")
    args = parser.parse_args()

    print("Loading trend data…", flush=True)
    trends  = compute_temporal_trends()
    print(f"Running walk-forward validation on {len(trends)} flags…", flush=True)
    results = run_validation(trends)
    print()

    if args.flag:
        print_flag_detail(args.flag, results)
    else:
        print_summary(results, top_n=args.top)


if __name__ == "__main__":
    main()
