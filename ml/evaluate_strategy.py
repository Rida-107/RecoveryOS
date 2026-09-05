"""
RecoveryOS - Fast 3-Strategy Benchmark Evaluation

The live agent and RecoveryOS benchmark use the same Action Optimizer.

Important:
- Expected Recovery is a synthetic counterfactual estimate, not observed revenue.
- ML probabilities are generated in one batch for performance.
"""

import json
from pathlib import Path

import pandas as pd

from ml.predict import model, FEATURES
from ml.action_optimizer import build_action_scores
from backend.decision_engine import choose_best_action


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "payments_training.csv"
METRICS_PATH = ROOT / "ml" / "models" / "strategy_metrics.json"


TRANSIENT_FAILURES = {
    "BANK_TIMEOUT",
    "NETWORK_ERROR",
    "GATEWAY_TIMEOUT",
}


ALTERNATE_PAYMENT_FAILURES = {
    "CARD_EXPIRED",
    "EXPIRED_CARD",
    "INSUFFICIENT_FUNDS",
    "LIMIT_EXCEEDED",
    "BANK_DECLINED",
}


MAX_AUTOMATED_RETRIES = 3


def clamp_probability(value):
    return min(max(float(value), 0.0), 0.95)


def simulated_recovery_value(amount, probability):
    return float(amount) * float(probability)


def rule_based_action(payment):
    failure = payment["failure_code"]
    retries = int(payment["previous_retries"])

    if retries >= MAX_AUTOMATED_RETRIES:
        return "HUMAN_REVIEW"

    if failure in TRANSIENT_FAILURES:
        return "DELAYED_RETRY"

    if failure in ALTERNATE_PAYMENT_FAILURES:
        return "PAYMENT_LINK"

    return "HUMAN_REVIEW"


def rule_based_probability(payment, base_probability):
    failure = payment["failure_code"]

    if failure in TRANSIENT_FAILURES:
        probability = base_probability + 0.10
    elif failure in ALTERNATE_PAYMENT_FAILURES:
        probability = base_probability + 0.18
    else:
        probability = 0.0

    return clamp_probability(probability)


def always_retry_action(payment):
    if int(payment["previous_retries"]) >= MAX_AUTOMATED_RETRIES:
        return "HUMAN_REVIEW"

    return "DELAYED_RETRY"


def always_retry_probability(payment, base_probability):
    if int(payment["previous_retries"]) >= MAX_AUTOMATED_RETRIES:
        return 0.0

    return clamp_probability(base_probability)


def get_recoveryos_decision(payment, base_probability):
    """
    Use exactly the same optimizer + deterministic policy as the live agent.
    """

    scores = build_action_scores(
        payment,
        base_probability,
    )

    action_probabilities = {
        action_name: details["probability"]
        for action_name, details in scores["actions"].items()
    }

    decision = choose_best_action(
        payment,
        action_probabilities,
    )

    return (
        decision["selected_action"],
        float(decision["selected_probability"]),
    )


def add_group_value(store, key, expected_recovery):
    if key not in store:
        store[key] = {
            "payments": 0,
            "expected_recovery": 0.0,
        }

    store[key]["payments"] += 1
    store[key]["expected_recovery"] += float(
        expected_recovery
    )


def main():
    print("=" * 70)
    print("RecoveryOS - 3-Strategy Benchmark Evaluation")
    print("=" * 70)

    df = pd.read_csv(DATA_PATH)

    print(f"Dataset records: {len(df):,}")

    # --------------------------------------------------------
    # Batch ML prediction
    # --------------------------------------------------------

    print("Generating ML predictions...")

    model_input = df[FEATURES].copy()

    probabilities = model.predict_proba(
        model_input
    )[:, 1]

    df["base_probability"] = [
        round(float(value), 4)
        for value in probabilities
    ]

    print("ML predictions complete.")

    total_value = float(
        df["amount"].sum()
    )

    print()
    print("=" * 70)
    print("REVENUE AT RISK")
    print("=" * 70)

    print(
        f"Total payment value: ₹{total_value:,.2f}"
    )

    strategies = [
        "Always Retry",
        "Rule Based",
        "RecoveryOS",
    ]

    results = {}

    amount_bands = [
        ("₹0–₹5K", 0, 5000),
        ("₹5K–₹10K", 5000, 10000),
        ("₹10K–₹25K", 10000, 25000),
        ("₹25K–₹50K", 25000, 50000),
        ("₹50K+", 50000, float("inf")),
    ]

    payments = df.to_dict("records")

    for strategy_name in strategies:

        print(
            f"Evaluating {strategy_name}..."
        )

        total_expected_recovery = 0.0
        actions = {}
        by_failure = {}
        by_amount = {}

        for payment in payments:

            amount = float(
                payment["amount"]
            )

            base_probability = float(
                payment["base_probability"]
            )

            if strategy_name == "Always Retry":

                action = always_retry_action(
                    payment
                )

                probability = (
                    always_retry_probability(
                        payment,
                        base_probability,
                    )
                )

            elif strategy_name == "Rule Based":

                action = rule_based_action(
                    payment
                )

                probability = (
                    rule_based_probability(
                        payment,
                        base_probability,
                    )
                )

            else:

                action, probability = (
                    get_recoveryos_decision(
                        payment,
                        base_probability,
                    )
                )

            expected_recovery = (
                simulated_recovery_value(
                    amount,
                    probability,
                )
            )

            total_expected_recovery += (
                expected_recovery
            )

            actions[action] = (
                actions.get(action, 0) + 1
            )

            add_group_value(
                by_failure,
                payment["failure_code"],
                expected_recovery,
            )

            for name, low, high in amount_bands:

                if low <= amount < high:

                    add_group_value(
                        by_amount,
                        name,
                        expected_recovery,
                    )

                    break

        results[strategy_name] = {
            "expected_recovery":
                total_expected_recovery,

            "recovery_rate":
                (
                    total_expected_recovery
                    / total_value
                    if total_value
                    else 0.0
                ),

            "actions":
                actions,

            "by_failure":
                by_failure,

            "by_amount":
                by_amount,
        }

    recoveryos = results["RecoveryOS"]
    always_retry = results["Always Retry"]
    rule_based = results["Rule Based"]

    incremental_retry = (
        recoveryos["expected_recovery"]
        - always_retry["expected_recovery"]
    )

    incremental_rules = (
        recoveryos["expected_recovery"]
        - rule_based["expected_recovery"]
    )

    relative_retry = (
        incremental_retry
        / always_retry["expected_recovery"]
        if always_retry["expected_recovery"]
        else 0.0
    )

    relative_rules = (
        incremental_rules
        / rule_based["expected_recovery"]
        if rule_based["expected_recovery"]
        else 0.0
    )

    print()
    print("=" * 70)
    print("STRATEGY COMPARISON")
    print("=" * 70)
    print()

    print(
        f"{'Metric':<30}"
        f"{'Always Retry':>18}"
        f"{'Rule Based':>18}"
        f"{'RecoveryOS':>18}"
    )

    print("-" * 90)

    print(
        f"{'Expected Recovery':<30}"
        f"₹{always_retry['expected_recovery']:>16,.0f}"
        f"₹{rule_based['expected_recovery']:>16,.0f}"
        f"₹{recoveryos['expected_recovery']:>16,.0f}"
    )

    print(
        f"{'Recovery Rate':<30}"
        f"{always_retry['recovery_rate']:>17.2%}"
        f"{rule_based['recovery_rate']:>17.2%}"
        f"{recoveryos['recovery_rate']:>17.2%}"
    )

    print()
    print("=" * 70)
    print("RECOVERYOS IMPROVEMENT")
    print("=" * 70)

    print(
        f"vs Always Retry: "
        f"{'+' if incremental_retry >= 0 else ''}"
        f"₹{incremental_retry:,.2f}"
    )

    print(
        f"Relative improvement: "
        f"{'+' if relative_retry >= 0 else ''}"
        f"{relative_retry:.2%}"
    )

    print()

    print(
        f"vs Rule Based: "
        f"{'+' if incremental_rules >= 0 else ''}"
        f"₹{incremental_rules:,.2f}"
    )

    print(
        f"Relative improvement: "
        f"{'+' if relative_rules >= 0 else ''}"
        f"{relative_rules:.2%}"
    )

    print()
    print("=" * 70)
    print("ACTION DISTRIBUTION")
    print("=" * 70)

    for strategy in strategies:

        print(f"\n{strategy}:")

        for action, count in sorted(
            results[strategy]["actions"].items()
        ):

            print(
                f"  {action:<20} {count:,}"
            )

    # --------------------------------------------------------
    # Safety
    # --------------------------------------------------------

    retry_limit_blocks = int(
        (
            df["previous_retries"]
            >= MAX_AUTOMATED_RETRIES
        ).sum()
    )

    high_value_cases = int(
        (df["amount"] > 50000).sum()
    )

    low_confidence_escalations = int(
        (
            df["base_probability"]
            < 0.30
        ).sum()
    )

    unsafe_automated_retries = 0

    # The policy check is still performed against every case.
    for payment in payments:

        action, _ = get_recoveryos_decision(
            payment,
            float(payment["base_probability"]),
        )

        if (
            action == "DELAYED_RETRY"
            and int(payment["previous_retries"])
            >= MAX_AUTOMATED_RETRIES
        ):

            unsafe_automated_retries += 1

    print()
    print("=" * 70)
    print("SAFETY")
    print("=" * 70)

    print(
        f"Retry-limit blocks:          "
        f"{retry_limit_blocks:,}"
    )

    print(
        f"High-value cases:            "
        f"{high_value_cases:,}"
    )

    print(
        f"Low-confidence escalations:  "
        f"{low_confidence_escalations:,}"
    )

    print(
        f"Unsafe automated retries:    "
        f"{unsafe_automated_retries:,}"
    )

    # --------------------------------------------------------
    # Failure analysis
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FAILURE-TYPE ANALYSIS")
    print("=" * 70)

    for failure in sorted(
        results["RecoveryOS"]["by_failure"]
    ):

        payments_count = (
            results["RecoveryOS"]
            ["by_failure"][failure]
            ["payments"]
        )

        print(f"\n{failure}:")

        print(
            f"  Payments:       "
            f"{payments_count:,}"
        )

        for strategy in strategies:

            value = (
                results[strategy]
                ["by_failure"][failure]
                ["expected_recovery"]
            )

            print(
                f"  {strategy:<14} "
                f"₹{value:,.0f}"
            )

    # --------------------------------------------------------
    # Amount analysis
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PAYMENT-VALUE ANALYSIS")
    print("=" * 70)

    for band, _, _ in amount_bands:

        recovery_band = (
            results["RecoveryOS"]
            ["by_amount"]
            .get(
                band,
                {
                    "payments": 0,
                    "expected_recovery": 0.0,
                },
            )
        )

        payments_count = recovery_band["payments"]

        print(f"\n{band}:")

        print(
            f"  Payments:       "
            f"{payments_count:,}"
        )

        for strategy in strategies:

            band_data = (
                results[strategy]
                ["by_amount"]
                .get(
                    band,
                    {
                        "payments": 0,
                        "expected_recovery": 0.0,
                    },
                )
            )

            value = band_data[
                "expected_recovery"
            ]

            print(
                f"  {strategy:<14} "
                f"₹{value:,.0f}"
            )

    # --------------------------------------------------------
    # Metrics JSON
    # --------------------------------------------------------

    metrics = {
        "dataset_records":
            len(df),

        "total_payment_value":
            total_value,

        "strategies": {
            strategy: {
                "expected_recovery":
                    result["expected_recovery"],

                "recovery_rate":
                    result["recovery_rate"],

                "actions":
                    result["actions"],

                "by_failure":
                    result["by_failure"],

                "by_amount": {
                    band: result["by_amount"].get(
                        band,
                        {
                            "payments": 0,
                            "expected_recovery": 0.0,
                        },
                    )
                    for band, _, _ in amount_bands
                },
            }
            for strategy, result
            in results.items()
        },

        "recoveryos_improvement": {

            "vs_always_retry": {
                "incremental_expected_recovery":
                    incremental_retry,

                "relative_improvement":
                    relative_retry,
            },

            "vs_rule_based": {
                "incremental_expected_recovery":
                    incremental_rules,

                "relative_improvement":
                    relative_rules,
            },
        },

        "safety": {
            "retry_limit_blocks":
                retry_limit_blocks,

            "high_value_cases":
                high_value_cases,

            "low_confidence_escalations":
                low_confidence_escalations,

            "unsafe_automated_retries":
                unsafe_automated_retries,
        },

        "methodology": {
            "type":
                "synthetic_counterfactual_simulation",

            "note":
                "Expected recovery is simulated economic value, "
                "not observed revenue.",

            "recoveryos_action_scoring":
                "ml.action_optimizer",

            "policy":
                "backend.decision_engine",

            "ml_predictions":
                "single_batch_model_inference",
        },
    }

    METRICS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        METRICS_PATH,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            metrics,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 70)
    print("Benchmark complete.")
    print(
        f"Metrics saved to: "
        f"{METRICS_PATH}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()