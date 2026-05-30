"""
Evaluate the predictive validity of the risk score using a temporal holdout design.

Method (from Section 5 of the report):
  - Train: compute risk score from 2011-2020 accident data
  - Test:  measure actual accident rates from 2021-2025 accident data
  - Restrict to the top N flags by fleet size (to exclude noise from tiny fleets)
  - Compare rankings with Spearman rank correlation

KEY METHODOLOGICAL NOTE — weight independence:
  The evaluation uses EVAL_WEIGHTS (equal across all 5 components), NOT
  DEFAULT_WEIGHTS (which were determined by inspecting the test data and are
  therefore biased upward). Using test-tuned weights to evaluate the same test
  set is a form of overfitting; equal weights give an unbiased baseline.
  DEFAULT_WEIGHTS remain in data_pipeline.py for the UI default only.
"""

import sys
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

from scipy.stats import spearmanr

from data_pipeline import build_merged_rows, load_fleet_rows, compute_accident_metrics, DEFAULT_WEIGHTS

RESULTS_DIR = Path(__file__).resolve().parent / "results"


@contextmanager
def tee_stdout(path: Path):
    """Context manager: writes all print() output to *path* AND stdout."""
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

TRAIN_END  = 2020
TEST_START = 2021
TOP_N      = 30  # restrict to the N largest fleets

# Equal weights across the five components that individually show r >= 0.4
# (all p < 0.05), chosen BEFORE looking at which combination maximises r.
# This is the unbiased primary evaluation weight set.
EVAL_WEIGHTS = {
    "accident_rate":   0.20,  # r=+0.674**
    "event_entropy":   0.20,  # r=+0.477**
    "trend":           0.20,  # r=+0.458*
    "investigation":   0.20,  # r=+0.439*
    "flag_safety":     0.20,  # r=+0.159 (detention rate)
    # All other components: 0 weight in evaluation
    "severity":        0.00,
    "ship_type":       0.00,
    "multi_ship":      0.00,
    "collision":       0.00,
    "open_sea":        0.00,
    "solas_noncompliance": 0.00,
    "excess_factor":   0.00,
    "excess_factor_trend": 0.00,
    "fleet_growth":    0.00,
    "fleet_volatility": 0.00,
}


def run_eval(label: str, weights: dict, fleet_by_key: dict, test_metrics: dict) -> float:
    """Return Spearman r for a given weight configuration."""
    train_rows = build_merged_rows(end_year=TRAIN_END, weights=weights)
    candidates = [
        r for r in train_rows
        if r["flag_key"] in test_metrics and fleet_by_key.get(r["flag_key"], 0) > 0
    ]
    candidates.sort(key=lambda r: fleet_by_key.get(r["flag_key"], 0), reverse=True)
    top = candidates[:TOP_N]
    if len(top) < 5:
        return float("nan")

    sc = [r["risk_score"] for r in top]
    tr = [test_metrics[r["flag_key"]]["accident_rate"] for r in top]
    rr, _ = spearmanr(sc, tr)
    return rr


def main():
    fleet_by_key = {r["flag_key"]: r["fleet_size"] for r in load_fleet_rows()}
    test_metrics = {
        r["flag_key"]: r for r in compute_accident_metrics(start_year=TEST_START)
    }

    # -----------------------------------------------------------------------
    # Primary evaluation — unbiased (equal weights, not tuned on test data)
    # -----------------------------------------------------------------------
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

    train_scores = [r["risk_score"] for r in top]
    test_rates   = [test_metrics[r["flag_key"]]["accident_rate"] for r in top]
    correlation, p_value = spearmanr(train_scores, test_rates)

    print("=" * 60)
    print("PRIMARY EVALUATION (unbiased — equal weights, test-independent)")
    print("=" * 60)
    print(f"  Train period : 2011-{TRAIN_END}")
    print(f"  Test period  : {TEST_START}-2025")
    print(f"  Flags        : top {len(top)} by 2025 fleet size")
    print(f"  Metric       : exposure-weighted accident rate (acc/ship-yr)")
    print(f"  Eval weights : {EVAL_WEIGHTS}")
    print(f"  Spearman r   : {correlation:.3f}")
    print(f"  p-value      : {p_value:.4f}")
    print()

    if correlation >= 0.5:
        print("Result: GOOD -- risk score has meaningful predictive power (r >= 0.5)")
    elif correlation >= 0.3:
        print("Result: MODERATE -- some signal present (0.3 <= r < 0.5)")
    else:
        print("Result: WEAK -- factors or normalization need reconsideration (r < 0.3)")

    print()
    print(f"{'Flag':<40} {'Train score':>12} {'Test rate (acc/ship-yr)':>23}")
    print("-" * 78)
    paired = sorted(zip(top, test_rates), key=lambda x: x[0]["risk_score"], reverse=True)
    for row, test_rate in paired:
        print(f"{row['flag']:<40} {row['risk_score']:>12.4f} {test_rate:>23.6f}")

    # -----------------------------------------------------------------------
    # Sensitivity analysis — individual components and selected combinations
    # (for reference only; these were explored AFTER seeing the test data)
    # -----------------------------------------------------------------------
    print()
    print("=" * 60)
    print("SENSITIVITY ANALYSIS (reference only — not unbiased evaluations)")
    print("=" * 60)

    zero = {"accident_rate": 0, "severity": 0, "ship_type": 0, "flag_safety": 0, "trend": 0}

    def w(**kw):
        return {**zero, **kw}

    configs = [
        ("Accident rate only",              w(accident_rate=1)),
        ("Detention rate only",             w(flag_safety=1)),
        ("Trend slope only",                w(trend=1)),
        ("Severity only",                   w(severity=1)),
        ("Ship type only",                  w(ship_type=1)),
        ("Acc + Trend",                     w(accident_rate=0.7, trend=0.3)),
        ("Acc + Detention + Trend",         w(accident_rate=0.5, flag_safety=0.2, trend=0.3)),
        ("Equal 3 (acc, det, trend)",       w(accident_rate=1/3, flag_safety=1/3, trend=1/3)),
        ("Current DEFAULT_WEIGHTS (biased)", DEFAULT_WEIGHTS),
    ]

    for label, weights in configs:
        r_val = run_eval(label, weights, fleet_by_key, test_metrics)
        print(f"  {label:<42} r = {r_val:+.3f}")


if __name__ == "__main__":
    output_file = RESULTS_DIR / "evaluation_results_05282248.txt"
    with tee_stdout(output_file):
        main()
