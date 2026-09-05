from pathlib import Path
import sqlite3
import json

from ml.predict import predict_recovery
from backend.agent import build_action_probabilities
from backend.decision_engine import choose_best_action


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = PROJECT_ROOT / "data" / "recoveryos.db"

OUTPUT_PATH = (
    PROJECT_ROOT
    / "ml"
    / "models"
    / "evaluation_metrics.json"
)


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def get_payments():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM payments
            ORDER BY payment_id
            """
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


# ============================================================
# BASELINE
# ============================================================

def calculate_baseline(
    payment,
    base_probability,
):
    """
    Naive baseline.

    The baseline assumes that the merchant uses the
    generic recovery probability directly rather than
    selecting a failure-specific recovery action.

    This is an EXPECTED-VALUE simulation baseline.

    It is NOT a production recovery measurement.
    """

    amount = float(
        payment["amount"]
    )

    return amount * base_probability


# ============================================================
# EVALUATION
# ============================================================

def evaluate():

    payments = get_payments()

    if not payments:

        raise RuntimeError(
            "No payments found in database."
        )


    # ========================================================
    # AGGREGATE METRICS
    # ========================================================

    total_payments = len(payments)

    total_revenue_at_risk = 0.0

    baseline_expected_recovery = 0.0

    recoveryos_expected_recovery = 0.0

    automated_actions = 0

    human_reviews = 0

    payments_with_policy_blocks = 0

    total_blocked_candidates = 0

    total_candidates = 0

    action_distribution = {}

    failure_distribution = {}

    failure_action_distribution = {}

    probability_sum = 0.0

    payment_results = []


    # ========================================================
    # PROCESS PAYMENTS
    # ========================================================

    for payment in payments:

        amount = float(
            payment["amount"]
        )

        total_revenue_at_risk += amount


        # ----------------------------------------------------
        # ML PREDICTION
        # ----------------------------------------------------

        base_probability = predict_recovery(
            payment
        )

        probability_sum += (
            base_probability
        )


        # ----------------------------------------------------
        # BASELINE
        # ----------------------------------------------------

        baseline_value = calculate_baseline(
            payment,
            base_probability,
        )

        baseline_expected_recovery += (
            baseline_value
        )


        # ----------------------------------------------------
        # ACTION PROBABILITIES
        # ----------------------------------------------------

        action_probabilities = (
            build_action_probabilities(
                payment,
                base_probability,
            )
        )


        # ----------------------------------------------------
        # POLICY / DECISION ENGINE
        # ----------------------------------------------------

        decision = choose_best_action(
            payment,
            action_probabilities,
        )


        selected_action = decision[
            "selected_action"
        ]

        selected_probability = decision[
            "selected_probability"
        ]

        expected_recovery_value = decision[
            "expected_recovery_value"
        ]

        candidates = decision.get(
            "candidates",
            [],
        )


        recoveryos_expected_recovery += (
            expected_recovery_value
        )


        # ====================================================
        # POLICY METRICS
        # ====================================================

        blocked_candidates = sum(
            1
            for candidate in candidates
            if candidate.get("allowed") is False
        )

        candidate_count = len(candidates)

        total_blocked_candidates += (
            blocked_candidates
        )

        total_candidates += (
            candidate_count
        )


        if blocked_candidates > 0:

            payments_with_policy_blocks += 1


        # ====================================================
        # ACTION METRICS
        # ====================================================

        action_distribution[
            selected_action
        ] = (
            action_distribution.get(
                selected_action,
                0,
            )
            + 1
        )


        if selected_action == "HUMAN_REVIEW":

            human_reviews += 1

        else:

            automated_actions += 1


        # ====================================================
        # FAILURE CODE METRICS
        # ====================================================

        failure_code = payment[
            "failure_code"
        ]

        failure_distribution[
            failure_code
        ] = (
            failure_distribution.get(
                failure_code,
                0,
            )
            + 1
        )


        # ----------------------------------------------------
        # Failure → Selected Action
        # ----------------------------------------------------

        if failure_code not in failure_action_distribution:

            failure_action_distribution[
                failure_code
            ] = {}


        failure_action_distribution[
            failure_code
        ][
            selected_action
        ] = (
            failure_action_distribution[
                failure_code
            ].get(
                selected_action,
                0,
            )
            + 1
        )


        # ====================================================
        # STORE PAYMENT RESULT
        # ====================================================

        payment_results.append(

            {

                "payment_id":
                    payment["payment_id"],

                "amount":
                    round(
                        amount,
                        2,
                    ),

                "failure_code":
                    failure_code,

                "base_probability":
                    round(
                        base_probability,
                        4,
                    ),

                "action_probabilities":
                    action_probabilities,

                "selected_action":
                    selected_action,

                "selected_probability":
                    round(
                        selected_probability,
                        4,
                    ),

                "expected_recovery_value":
                    round(
                        expected_recovery_value,
                        2,
                    ),

                "blocked_candidate_count":
                    blocked_candidates,

                "candidate_count":
                    candidate_count,

                "decision_reason":
                    decision[
                        "decision_reason"
                    ],
            }
        )


    # ========================================================
    # FINAL METRICS
    # ========================================================

    if total_revenue_at_risk > 0:

        baseline_recovery_rate = (
            baseline_expected_recovery
            / total_revenue_at_risk
        )

        recoveryos_recovery_rate = (
            recoveryos_expected_recovery
            / total_revenue_at_risk
        )

    else:

        baseline_recovery_rate = 0.0

        recoveryos_recovery_rate = 0.0


    # --------------------------------------------------------
    # Expected uplift
    # --------------------------------------------------------

    if baseline_expected_recovery > 0:

        uplift_percent = (

            (
                recoveryos_expected_recovery
                - baseline_expected_recovery
            )
            / baseline_expected_recovery

        ) * 100

    else:

        uplift_percent = 0.0


    # --------------------------------------------------------
    # Agent operation rates
    # --------------------------------------------------------

    automation_rate = (
        automated_actions
        / total_payments
    )

    human_review_rate = (
        human_reviews
        / total_payments
    )


    # --------------------------------------------------------
    # Policy metrics
    # --------------------------------------------------------

    payment_policy_block_rate = (

        payments_with_policy_blocks
        / total_payments

    )

    candidate_policy_block_rate = (

        total_blocked_candidates
        / total_candidates

        if total_candidates > 0

        else 0.0
    )


    # --------------------------------------------------------
    # Average ML probability
    # --------------------------------------------------------

    average_probability = (
        probability_sum
        / total_payments
    )


    # ========================================================
    # TOP OPPORTUNITIES
    # ========================================================

    top_recovery_opportunities = sorted(
        payment_results,
        key=lambda item:
            item["expected_recovery_value"],
        reverse=True,
    )[:20]


    # ========================================================
    # RESULTS OBJECT
    # ========================================================

    metrics = {

        "evaluation": {

            "dataset":
                "RecoveryOS synthetic payment batch",

            "total_payments":
                total_payments,

            "simulation_note":
                (
                    "Expected recovery values are "
                    "synthetic simulation estimates. "
                    "They are not production recovery "
                    "results or causal estimates."
                ),
        },


        "revenue": {

            "total_revenue_at_risk":
                round(
                    total_revenue_at_risk,
                    2,
                ),

            "baseline_expected_recovery":
                round(
                    baseline_expected_recovery,
                    2,
                ),

            "recoveryos_expected_recovery":
                round(
                    recoveryos_expected_recovery,
                    2,
                ),

            "baseline_expected_recovery_rate":
                round(
                    baseline_recovery_rate,
                    4,
                ),

            "recoveryos_expected_recovery_rate":
                round(
                    recoveryos_recovery_rate,
                    4,
                ),

            "expected_recovery_uplift_percent":
                round(
                    uplift_percent,
                    2,
                ),
        },


        "agent_operations": {

            "automated_actions":
                automated_actions,

            "human_reviews":
                human_reviews,

            "automation_rate":
                round(
                    automation_rate,
                    4,
                ),

            "human_review_rate":
                round(
                    human_review_rate,
                    4,
                ),
        },


        "policy": {

            "payments_with_policy_blocks":
                payments_with_policy_blocks,

            "payment_policy_block_rate":
                round(
                    payment_policy_block_rate,
                    4,
                ),

            "total_blocked_candidates":
                total_blocked_candidates,

            "total_candidates":
                total_candidates,

            "candidate_policy_block_rate":
                round(
                    candidate_policy_block_rate,
                    4,
                ),
        },


        "model": {

            "average_recovery_probability":
                round(
                    average_probability,
                    4,
                ),
        },


        "action_distribution":
            action_distribution,


        "failure_distribution":
            failure_distribution,


        "failure_action_distribution":
            failure_action_distribution,


        "top_recovery_opportunities":
            top_recovery_opportunities,
    }


    # ========================================================
    # SAVE JSON
    # ========================================================

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metrics,
            file,
            indent=2,
        )


    # ========================================================
    # TERMINAL REPORT
    # ========================================================

    print()

    print("=" * 70)

    print(
        "                 RecoveryOS Evaluation"
    )

    print("=" * 70)

    print()

    print(
        f"Payments evaluated        : "
        f"{total_payments:,}"
    )

    print(
        f"Revenue at risk           : "
        f"₹{total_revenue_at_risk:,.2f}"
    )

    print()

    print(
        "EXPECTED RECOVERY"
    )

    print("-" * 70)

    print(
        f"Baseline                  : "
        f"₹{baseline_expected_recovery:,.2f}"
    )

    print(
        f"RecoveryOS                : "
        f"₹{recoveryos_expected_recovery:,.2f}"
    )

    print(
        f"Baseline recovery rate    : "
        f"{baseline_recovery_rate * 100:.2f}%"
    )

    print(
        f"RecoveryOS recovery rate  : "
        f"{recoveryos_recovery_rate * 100:.2f}%"
    )

    print(
        f"Expected uplift            : "
        f"{uplift_percent:.2f}%"
    )

    print()

    print(
        "AGENT OPERATIONS"
    )

    print("-" * 70)

    print(
        f"Automated actions          : "
        f"{automated_actions:,}"
    )

    print(
        f"Human reviews              : "
        f"{human_reviews:,}"
    )

    print(
        f"Automation rate            : "
        f"{automation_rate * 100:.2f}%"
    )

    print(
        f"Human review rate          : "
        f"{human_review_rate * 100:.2f}%"
    )

    print()

    print(
        "POLICY / GUARDRAILS"
    )

    print("-" * 70)

    print(
        f"Payments with policy block : "
        f"{payments_with_policy_blocks:,}"
    )

    print(
        f"Payment block rate         : "
        f"{payment_policy_block_rate * 100:.2f}%"
    )

    print(
        f"Blocked candidates         : "
        f"{total_blocked_candidates:,}"
    )

    print(
        f"Total candidates           : "
        f"{total_candidates:,}"
    )

    print(
        f"Candidate block rate       : "
        f"{candidate_policy_block_rate * 100:.2f}%"
    )

    print()

    print(
        "MODEL"
    )

    print("-" * 70)

    print(
        f"Average ML probability     : "
        f"{average_probability * 100:.2f}%"
    )

    print()

    print(
        "ACTION DISTRIBUTION"
    )

    print("-" * 70)

    for action, count in sorted(
        action_distribution.items(),
        key=lambda item: item[1],
        reverse=True,
    ):

        percentage = (
            count
            / total_payments
        ) * 100

        print(
            f"{action:<22}"
            f"{count:>6}"
            f"  ({percentage:>6.2f}%)"
        )

    print()

    print(
        "FAILURE → ACTION"
    )

    print("-" * 70)

    for failure_code in sorted(
        failure_action_distribution
    ):

        actions = (
            failure_action_distribution[
                failure_code
            ]
        )

        action_text = ", ".join(
            f"{action}={count}"
            for action, count
            in sorted(
                actions.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )

        print(
            f"{failure_code:<22}"
            f"{action_text}"
        )

    print()

    print(
        "TOP 5 RECOVERY OPPORTUNITIES"
    )

    print("-" * 70)

    for item in top_recovery_opportunities[:5]:

        print(
            f"{item['payment_id']} | "
            f"₹{item['amount']:,.2f} | "
            f"{item['failure_code']:<20} | "
            f"{item['selected_action']:<15} | "
            f"EV ₹{item['expected_recovery_value']:,.2f}"
        )

    print()

    print(
        "Full metrics saved to:"
    )

    print(
        OUTPUT_PATH
    )

    print()

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    evaluate()