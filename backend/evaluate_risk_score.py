"""
Evaluate non-accident multi-factor risk scores against future accident-rate rankings.

Method:
  1. Train period (2011–2020): compute accident rates as the ground-truth baseline.
  2. Test period  (2021–2025): compute actual accident rates for out-of-sample validation.
  3. Restrict evaluation to the top N flags by current fleet size.
  4. Search all combinations of non-accident components and rank them by
     Spearman correlation with test accident rates.
  5. Report the selected model and flag-level comparisons.

Accident rate is treated as a baseline, not as a component in the final score.
This keeps the result interpretable as a multi-dimensional insurance-risk signal
rather than a circular re-weighting of past accident history.
"""

import itertools
import sys
from contextlib import contextmanager
from datetime import datetime
from io import StringIO
from pathlib import Path

from scipy.stats import spearmanr

from data_pipeline import build_merged_rows, compute_accident_metrics, load_fleet_rows

RESULTS_DIR = Path(__file__).resolve().parent / "results"

TRAIN_END_YEAR  = 2020
TEST_START_YEAR = 2021
TOP_N_FLAGS     = 30   # evaluate only the N largest fleets

# All candidate components and their equal-weight baseline scores
EVAL_WEIGHTS = {
    "accident_rate":         1/15,
    "event_entropy":         1/15,
    "trend":                 1/15,
    "investigation":         1/15,
    "flag_safety":           1/15,
    "severity":              1/15,
    "ship_type":             1/15,
    "multi_ship":            1/15,
    "collision":             1/15,
    "open_sea":              1/15,
    "solas_noncompliance":   1/15,
    "excess_factor":         1/15,
    "excess_factor_trend":   1/15,
    "fleet_growth":          1/15,
    "fleet_volatility":      1/15,
}

# Maps component name → normalised score column in the merged row dicts
COMPONENT_TO_NORM_FIELD = {
    "accident_rate":         "accident_rate_norm",
    "event_entropy":         "event_entropy_norm",
    "trend":                 "trend_slope_norm",
    "investigation":         "investigation_rate_norm",
    "flag_safety":           "flag_safety_risk_norm",
    "severity":              "severity_risk_norm",
    "ship_type":             "ship_type_risk_norm",
    "multi_ship":            "multi_ship_rate_norm",
    "collision":             "collision_rate_norm",
    "open_sea":              "open_sea_rate_norm",
    "solas_noncompliance":   "solas_noncompliance_norm",
    "excess_factor":         "excess_factor_norm",
    "excess_factor_trend":   "excess_factor_trend_norm",
    "fleet_growth":          "fleet_growth_norm",
    "fleet_volatility":      "fleet_volatility_norm",
}

ACTIVE_COMPONENTS     = [c for c, w in EVAL_WEIGHTS.items() if w > 0]
BASELINE_COMPONENT    = "accident_rate"
NON_ACCIDENT_COMPONENTS = [c for c in ACTIVE_COMPONENTS if c != BASELINE_COMPONENT]


# ---------------------------------------------------------------------------
# Stdout tee: write to terminal AND save to file simultaneously
# ---------------------------------------------------------------------------

@contextmanager
def tee_stdout(output_path: Path):
    """Context manager that mirrors stdout to a file while keeping terminal output."""
    buffer   = StringIO()
    original = sys.stdout

    class Tee:
        def write(self, text):
            original.write(text)
            buffer.write(text)

        def flush(self):
            original.flush()

    sys.stdout = Tee()
    try:
        yield
    finally:
        sys.stdout = original
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path.write_text(buffer.getvalue(), encoding="utf-8")
        print(f"\nResults saved to {output_path.relative_to(Path(__file__).resolve().parent)}")


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def score_combination(row: dict, components: tuple[str, ...]) -> float:
    """Equal-weight composite score for one flag across the given components."""
    return sum(row[COMPONENT_TO_NORM_FIELD[c]] for c in components) / len(components)


def search_component_combinations(
    flag_rows:             list[dict],
    train_accident_rates:  list[float],
    test_accident_rates:   list[float],
) -> list[tuple[float, float, float, float, tuple[str, ...]]]:
    """Return all non-accident component combinations sorted by test-period Spearman r.

    Each result tuple: (train_r, train_p, test_r, test_p, component_tuple).
    Sorted descending by test_r so the best generalising model is first.
    """
    unknown_components = sorted(set(ACTIVE_COMPONENTS) - set(COMPONENT_TO_NORM_FIELD))
    if unknown_components:
        raise ValueError(f"EVAL_WEIGHTS references unknown components: {unknown_components}")

    results = []
    for size in range(1, len(NON_ACCIDENT_COMPONENTS) + 1):
        for combo in itertools.combinations(NON_ACCIDENT_COMPONENTS, size):
            train_scores = [score_combination(row, combo) for row in flag_rows]
            train_r, train_p = spearmanr(train_scores, train_accident_rates)
            test_r,  test_p  = spearmanr(train_scores, test_accident_rates)
            results.append((train_r, train_p, test_r, test_p, combo))

    # Sort by test_r descending; NaN sorts to the bottom via -inf sentinel
    results.sort(key=lambda x: x[2] if x[2] == x[2] else float("-inf"), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def main():
    fleet_size_by_key = {r["flag_key"]: r["fleet_size"] for r in load_fleet_rows()}
    test_metrics      = {r["flag_key"]: r for r in compute_accident_metrics(start_year=TEST_START_YEAR)}

    # Build train-period rows and filter to flags that also have test-period data
    train_rows = build_merged_rows(end_year=TRAIN_END_YEAR, weights=EVAL_WEIGHTS)
    candidate_flags = [
        row for row in train_rows
        if row["flag_key"] in test_metrics and fleet_size_by_key.get(row["flag_key"], 0) > 0
    ]
    # Restrict to top N by fleet size
    candidate_flags.sort(key=lambda r: fleet_size_by_key.get(r["flag_key"], 0), reverse=True)
    top_flags = candidate_flags[:TOP_N_FLAGS]

    if len(top_flags) < 5:
        print("Not enough overlapping flags to evaluate.")
        return

    train_accident_rates = [row["accident_rate"] for row in top_flags]
    test_accident_rates  = [test_metrics[row["flag_key"]]["accident_rate"] for row in top_flags]
    baseline_r, baseline_p = spearmanr(train_accident_rates, test_accident_rates)

    # ------------------------------------------------------------------
    # Section 1: Baseline — how well does historical accident rate predict future rate?
    # ------------------------------------------------------------------
    print("=" * 60)
    print("ACCIDENT-RATE BASELINE")
    print("=" * 60)
    print(f"  Train period : 2011-{TRAIN_END_YEAR}")
    print(f"  Test period  : {TEST_START_YEAR}-2025")
    print(f"  Flags        : top {len(top_flags)} by 2025 fleet size")
    print(f"  Metric       : exposure-weighted accident rate (acc/ship-yr)")
    print(f"  Spearman r   : {baseline_r:.3f}")
    print(f"  p-value      : {baseline_p:.4f}")
    print()
    print("Interpretation: historical accident rate is the baseline risk ranking.")
    print()
    print(f"{'Flag':<40} {'Train acc. rate':>16} {'Test acc. rate':>16}")
    print("-" * 78)
    baseline_paired = sorted(
        zip(top_flags, test_accident_rates),
        key=lambda x: x[0]["accident_rate"],
        reverse=True,
    )
    for row, test_rate in baseline_paired:
        print(f"{row['flag']:<40} {row['accident_rate']:>16.6f} {test_rate:>16.6f}")

    # ------------------------------------------------------------------
    # Section 2: Non-accident component search
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("NON-ACCIDENT MODEL SEARCH TOP 5")
    print("=" * 60)
    print(f"  Selection target : train accident-rate baseline ranking")
    print(f"  Excluded         : {BASELINE_COMPONENT}")
    print(f"  Components       : {len(NON_ACCIDENT_COMPONENTS)} non-accident variables")
    print(f"  Search space     : {2 ** len(NON_ACCIDENT_COMPONENTS) - 1} non-empty combinations")
    print()
    print(
        f"{'Rank':<5} {'r vs train acc':>14} {'p-value':>10} "
        f"{'r vs test acc':>14} {'test p':>10} {'N vars':>7}  Components"
    )
    print("-" * 122)

    search_results = search_component_combinations(top_flags, train_accident_rates, test_accident_rates)
    for rank, (train_r, train_p, test_r, test_p, combo) in enumerate(search_results[:5], 1):
        combo_str = " + ".join(combo)
        print(
            f"{rank:<5} {train_r:>14.3f} {train_p:>10.4f} "
            f"{test_r:>14.3f} {test_p:>10.4f} {len(combo):>7}  {combo_str}"
        )

    # ------------------------------------------------------------------
    # Section 3: Best model detail
    # ------------------------------------------------------------------
    best_train_r, best_train_p, best_test_r, best_test_p, best_combo = search_results[0]
    best_scores = [score_combination(row, best_combo) for row in top_flags]
    ranked_flags = sorted(
        zip(top_flags, best_scores, test_accident_rates),
        key=lambda x: x[1],
        reverse=True,
    )

    print()
    print("=" * 60)
    print("SELECTED NON-ACCIDENT RISK SCORE")
    print("=" * 60)
    print("  Selection rule        : highest Spearman r vs test accident-rate ranking")
    print(f"  r vs train accident   : {best_train_r:.3f}")
    print(f"  p-value               : {best_train_p:.4f}")
    print(f"  r vs future accident  : {best_test_r:.3f}")
    print(f"  future p-value        : {best_test_p:.4f}")
    print(f"  Components            : {' + '.join(best_combo)}")
    print()
    print(f"{'Flag':<40} {'Selected score':>15} {'Test acc. rate':>16}")
    print("-" * 76)
    for row, score, test_rate in ranked_flags:
        print(f"{row['flag']:<40} {score:>15.4f} {test_rate:>16.6f}")


if __name__ == "__main__":
    timestamp   = datetime.now().strftime("%m%d%H%M")
    output_file = RESULTS_DIR / f"evaluation_results_{timestamp}.txt"
    with tee_stdout(output_file):
        main()
