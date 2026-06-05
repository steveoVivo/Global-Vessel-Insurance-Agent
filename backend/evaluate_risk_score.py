"""
Evaluate a non-accident multi-factor risk score against accident-rate rankings.

Method:
  - Train period: 2011-2020
  - Test period:  2021-2025
  - Restrict evaluation to the top N flags by fleet size
  - Use historical accident_rate as the baseline risk ordering
  - Search for accident_rate-excluded component combinations that reproduce that
    baseline ordering
  - Validate the selected non-accident model against future accident rates

This treats accident_rate as a baseline, not as part of the selected
multi-factor score. That keeps the final score useful for visualization and
light analysis across multiple interpretable insurance-risk dimensions.
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

TRAIN_END  = 2020
TEST_START = 2021
TOP_N      = 30  # restrict to the N largest fleets

# Components available for evaluation. Positive weights mark active components.
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

COMPONENT_SCORE_COLUMNS = {
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

ACTIVE_COMPONENTS = [component for component, weight in EVAL_WEIGHTS.items() if weight > 0]
BASELINE_COMPONENT = "accident_rate"
NON_ACCIDENT_COMPONENTS = [c for c in ACTIVE_COMPONENTS if c != BASELINE_COMPONENT]


@contextmanager
def tee_stdout(path: Path):
    buf = StringIO()
    original = sys.stdout

    class Tee:
        def write(self, s):
            original.write(s)
            buf.write(s)

        def flush(self):
            original.flush()

    sys.stdout = Tee()
    try:
        yield
    finally:
        sys.stdout = original
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(buf.getvalue(), encoding="utf-8")
        print(f"\nResults saved to {path.relative_to(Path(__file__).resolve().parent)}")


def score_combo(row: dict, combo: tuple[str, ...]) -> float:
    """Equal-weight risk score for one component combination."""
    return sum(row[COMPONENT_SCORE_COLUMNS[c]] for c in combo) / len(combo)


def combination_search(
    top_rows: list[dict],
    train_accident_rates: list[float],
    test_accident_rates: list[float],
) -> list[tuple[float, float, float, float, tuple[str, ...]]]:
    """
    Return accident-rate-excluded combinations sorted by similarity to the
    train accident-rate baseline ranking.
    """
    unknown = sorted(set(ACTIVE_COMPONENTS) - set(COMPONENT_SCORE_COLUMNS))
    if unknown:
        raise ValueError(f"EVAL_WEIGHTS contains unknown components: {unknown}")

    results = []

    for size in range(1, len(NON_ACCIDENT_COMPONENTS) + 1):
        for combo in itertools.combinations(NON_ACCIDENT_COMPONENTS, size):
            train_scores = [score_combo(row, combo) for row in top_rows]
            target_r, target_p = spearmanr(train_scores, train_accident_rates)
            future_r, future_p = spearmanr(train_scores, test_accident_rates)
            results.append((target_r, target_p, future_r, future_p, combo))

    results.sort(key=lambda x: x[0] if x[0] == x[0] else float("-inf"), reverse=True)
    return results


def main():
    fleet_by_key = {r["flag_key"]: r["fleet_size"] for r in load_fleet_rows()}
    test_metrics = {r["flag_key"]: r for r in compute_accident_metrics(start_year=TEST_START)}

    train_rows = build_merged_rows(end_year=TRAIN_END, weights=EVAL_WEIGHTS)
    candidates = [
        r for r in train_rows
        if r["flag_key"] in test_metrics and fleet_by_key.get(r["flag_key"], 0) > 0
    ]
    candidates.sort(key=lambda r: fleet_by_key.get(r["flag_key"], 0), reverse=True)
    top = candidates[:TOP_N]

    if len(top) < 5:
        print("Not enough overlapping flags to evaluate.")
        return

    train_accident_rates = [r["accident_rate"] for r in top]
    test_accident_rates = [test_metrics[r["flag_key"]]["accident_rate"] for r in top]
    baseline_r, baseline_p = spearmanr(train_accident_rates, test_accident_rates)

    print("=" * 60)
    print("ACCIDENT-RATE BASELINE")
    print("=" * 60)
    print(f"  Train period : 2011-{TRAIN_END}")
    print(f"  Test period  : {TEST_START}-2025")
    print(f"  Flags        : top {len(top)} by 2025 fleet size")
    print(f"  Metric       : exposure-weighted accident rate (acc/ship-yr)")
    print(f"  Spearman r   : {baseline_r:.3f}")
    print(f"  p-value      : {baseline_p:.4f}")
    print()
    print("Interpretation: historical accident rate is the baseline risk ranking.")

    print()
    print(f"{'Flag':<40} {'Train acc. rate':>16} {'Test acc. rate':>16}")
    print("-" * 78)
    baseline_paired = sorted(zip(top, test_accident_rates), key=lambda x: x[0]["accident_rate"], reverse=True)
    for row, test_rate in baseline_paired:
        print(f"{row['flag']:<40} {row['accident_rate']:>16.6f} {test_rate:>16.6f}")

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

    search_results = combination_search(top, train_accident_rates, test_accident_rates)
    for rank, (target_r, target_p, future_r, future_p, combo) in enumerate(search_results[:5], 1):
        combo_str = " + ".join(combo)
        print(
            f"{rank:<5} {target_r:>14.3f} {target_p:>10.4f} "
            f"{future_r:>14.3f} {future_p:>10.4f} {len(combo):>7}  {combo_str}"
        )

    selected_target_r, selected_target_p, selected_future_r, selected_future_p, selected_combo = search_results[0]
    selected_scores = [score_combo(row, selected_combo) for row in top]
    selected_rows = sorted(zip(top, selected_scores, test_accident_rates), key=lambda x: x[1], reverse=True)

    print()
    print("=" * 60)
    print("SELECTED NON-ACCIDENT RISK SCORE")
    print("=" * 60)
    print("  Selection rule        : highest Spearman r vs train accident-rate ranking")
    print(f"  r vs train accident   : {selected_target_r:.3f}")
    print(f"  p-value               : {selected_target_p:.4f}")
    print(f"  r vs future accident  : {selected_future_r:.3f}")
    print(f"  future p-value        : {selected_future_p:.4f}")
    print(f"  Components            : {' + '.join(selected_combo)}")
    print()
    print(f"{'Flag':<40} {'Selected score':>15} {'Test acc. rate':>16}")
    print("-" * 76)
    for row, score, test_rate in selected_rows:
        print(f"{row['flag']:<40} {score:>15.4f} {test_rate:>16.6f}")


if __name__ == "__main__":
    ts = datetime.now().strftime("%m%d%H%M")
    output_file = RESULTS_DIR / f"evaluation_results_{ts}.txt"
    with tee_stdout(output_file):
        main()
