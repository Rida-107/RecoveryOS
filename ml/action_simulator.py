from pathlib import Path
import sqlite3
import json
import random

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
    / "action_simulation_metrics.json"
)

RANDOM_SEED = 42


# ============================================================
# SYNTHETIC ACTION SUCCESS ASSUMPTIONS
# ============================================================
#
# IMPORTANT:
#
# These values are simulation assumptions.
# They are NOT Razorpay production statistics.
#
# They allow us to simulate what could happen after
# RecoveryOS selects an action.
#
# Later, these can be replaced with real historical
# action-outcome data.
# ============================================================

ACTION_SUCCESS_RATES = {

    "DELAYED_RETRY": {

        "BANK_TIMEOUT": 0.72,

        "NETWORK_ERROR": 0.76,

        "GATEWAY_TIMEOUT": 0.74,

        "default": 0.35,
    },


    "PAYMENT_LINK": {

        "CARD_EXPIRED": 0.68,

        "EXPIRED_CARD": 0.68,

        "INSUFFICIENT_FUNDS": 0.42,

        "LIMIT_EXCEEDED": 0.45,

        "BANK_DECLINED": 0.48,

        "BANK_TIMEOUT": 0.38,

        "NETWORK_ERROR": 0.36,

        "GATEWAY_TIMEOUT": 0.38,

        "AUTH_FAILED": 0.30,

        "default": 0.35,
    },


    "HUMAN_REVIEW": {

        "AUTH_FAILED": 0.62,

        "BANK_DECLINED": 0.58,

        "INSUFFICIENT_FUNDS": 0.50,

        "LIMIT_EXCEEDED": 0.52,

        "default": 0.55,
    },
}


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
# ACTION SUCCESS PROBABILITY
# ============================================================

def get_action_success_probability(
    action,
    failure_code,
):
    """
    Return the synthetic probability that an action
    successfully recovers a payment.
    """

    action_rates = ACTION_SUCCESS_RATES.get(
        action,
        {},
    )

    return action_rates.get(
        failure_code,
        action_rates.get(
            "default",
            0.0,
        ),
    )


# ============================================================
# SIMULATE OUTCOME
# ============================================================

def simulate_outcome(
    action,
    failure_code,
    amount,
    random_generator,
):
    """
    Simulate the outcome of one recovery action.

    Returns either:

        RECOVERED

    or:

        FAILED
    """

    success_probability = (
        get_action_success_probability(
            action,
            failure_code,
        )
    )

    recovered = (
        random_generator.random()
        < success_probability
    )

    if recovered:

        return {

            "status":
                "RECOVERED",

            "recovered_amount":
                round(
                    amount,
                    2,
                ),

            "success_probability":
                success_probability,
        }


    return {

        "status":
            "FAILED",

        "recovered_amount":
            0.0,

        "success_probability":
            success_probability,
    }


# ============================================================
# BASELINE STRATEGY
# ============================================================

def baseline_action(payment):
    """
    Naive baseline.

    The baseline attempts a generic delayed retry
    for every payment.

    This represents a simple non-adaptive recovery
    strategy.
    """

    if payment["previous_retries"] >= 3:

        return "HUMAN_REVIEW"

    return "DELAYED_RETRY"


# ============================================================
# MAIN SIMULATION
# ============================================================

def run_simulation():

    print()

    print("=" * 70)

    print(
        "        RecoveryOS Action-Specific Revenue Simulation"
    )

    print("=" * 70)

    print()


    # --------------------------------------------------------
    # Load payments
    # --------------------------------------------------------

    payments = get_payments()

    if not payments:

        raise RuntimeError(
            "No payments found in database."
        )


    print(
        f"Dataset records: {len(payments)}"
    )

    print()


    # --------------------------------------------------------
    # Reproducible random generator
    # --------------------------------------------------------

    random_generator = random.Random(
        RANDOM_SEED
    )


    # ========================================================
    # AGGREGATES
    # ========================================================

    total_payments = len(payments)

    total_revenue_at_risk = 0.0


    baseline_recovered_amount = 0.0

    recoveryos_recovered_amount = 0.0


    baseline_recovered_count = 0

    recoveryos_recovered_count = 0


    baseline_failed_count = 0

    recoveryos_failed_count = 0


    recoveryos_automated_count = 0

    recoveryos_human_review_count = 0


    recoveryos_action_distribution = {}

    baseline_action_distribution = {}


    recoveryos_results = []

    baseline_results = []


    # ========================================================
    # PROCESS EVERY PAYMENT
    # ========================================================

    for payment in payments:

        amount = float(
            payment["amount"]
        )

        failure_code = payment[
            "failure_code"
        ]

        total_revenue_at_risk += amount


        # ====================================================
        # BASELINE
        # ====================================================

        baseline_selected_action = (
            baseline_action(payment)
        )

        baseline_action_distribution[
            baseline_selected_action
        ] = (
            baseline_action_distribution.get(
                baseline_selected_action,
                0,
            )
            + 1
        )


        baseline_outcome = simulate_outcome(
            baseline_selected_action,
            failure_code,
            amount,
            random_generator,
        )


        if (
            baseline_outcome["status"]
            == "RECOVERED"
        ):

            baseline_recovered_count += 1

            baseline_recovered_amount += (
                baseline_outcome[
                    "recovered_amount"
                ]
            )

        else:

            baseline_failed_count += 1


        baseline_results.append(

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

                "selected_action":
                    baseline_selected_action,

                "simulated_outcome":
                    baseline_outcome[
                        "status"
                    ],

                "recovered_amount":
                    baseline_outcome[
                        "recovered_amount"
                    ],

                "success_probability":
                    baseline_outcome[
                        "success_probability"
                    ],
            }
        )


        # ====================================================
        # RECOVERYOS
        # ====================================================

        # ----------------------------------------------------
        # 1. ML prediction
        # ----------------------------------------------------

        base_probability = predict_recovery(
            payment
        )


        # ----------------------------------------------------
        # 2. Action-specific probabilities
        # ----------------------------------------------------

        action_probabilities = (
            build_action_probabilities(
                payment,
                base_probability,
            )
        )


        # ----------------------------------------------------
        # 3. Actual RecoveryOS decision engine
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

        decision_reason = decision[
            "decision_reason"
        ]


        # ----------------------------------------------------
        # 4. Action distribution
        # ----------------------------------------------------

        recoveryos_action_distribution[
            selected_action
        ] = (
            recoveryos_action_distribution.get(
                selected_action,
                0,
            )
            + 1
        )


        # ----------------------------------------------------
        # 5. Automation / human review
        # ----------------------------------------------------

        if selected_action == "HUMAN_REVIEW":

            recoveryos_human_review_count += 1

        else:

            recoveryos_automated_count += 1


        # ----------------------------------------------------
        # 6. Simulate actual outcome
        # ----------------------------------------------------

        recoveryos_outcome = simulate_outcome(
            selected_action,
            failure_code,
            amount,
            random_generator,
        )


        if (
            recoveryos_outcome["status"]
            == "RECOVERED"
        ):

            recoveryos_recovered_count += 1

            recoveryos_recovered_amount += (
                recoveryos_outcome[
                    "recovered_amount"
                ]
            )

        else:

            recoveryos_failed_count += 1


        # ----------------------------------------------------
        # 7. Store result
        # ----------------------------------------------------

        recoveryos_results.append(

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

                "ml_probability":
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

                "decision_reason":
                    decision_reason,

                "simulated_outcome":
                    recoveryos_outcome[
                        "status"
                    ],

                "recovered_amount":
                    recoveryos_outcome[
                        "recovered_amount"
                    ],

                "action_success_probability":
                    recoveryos_outcome[
                        "success_probability"
                    ],
            }
        )


    # ========================================================
    # RECOVERY RATES
    # ========================================================

    baseline_recovery_rate = (

        baseline_recovered_count
        / total_payments

    )

    recoveryos_recovery_rate = (

        recoveryos_recovered_count
        / total_payments

    )


    # ========================================================
    # REVENUE RECOVERY RATES
    # ========================================================

    baseline_revenue_recovery_rate = (

        baseline_recovered_amount
        / total_revenue_at_risk

    )

    recoveryos_revenue_recovery_rate = (

        recoveryos_recovered_amount
        / total_revenue_at_risk

    )


    # ========================================================
    # REVENUE UPLIFT
    # ========================================================

    if baseline_recovered_amount > 0:

        revenue_uplift_percent = (

            (
                recoveryos_recovered_amount
                - baseline_recovered_amount
            )
            / baseline_recovered_amount

        ) * 100

    else:

        revenue_uplift_percent = 0.0


    # ========================================================
    # RECOVERY COUNT UPLIFT
    # ========================================================

    if baseline_recovered_count > 0:

        recovery_count_uplift_percent = (

            (
                recoveryos_recovered_count
                - baseline_recovered_count
            )
            / baseline_recovered_count

        ) * 100

    else:

        recovery_count_uplift_percent = 0.0


    # ========================================================
    # OPERATION RATES
    # ========================================================

    automation_rate = (

        recoveryos_automated_count
        / total_payments

    )

    human_review_rate = (

        recoveryos_human_review_count
        / total_payments

    )


    # ========================================================
    # RESULTS
    # ========================================================

    results = {

        "simulation": {

            "simulation_type":
                (
                    "Synthetic action-specific "
                    "outcome simulation"
                ),

            "dataset":
                "RecoveryOS payment batch",

            "random_seed":
                RANDOM_SEED,

            "total_payments":
                total_payments,

            "simulation_note":
                (
                    "Outcomes are simulated using "
                    "explicit synthetic action-success "
                    "probabilities. These results are "
                    "benchmark simulations, not real "
                    "production recovery measurements."
                ),
        },


        "revenue": {

            "total_revenue_at_risk":
                round(
                    total_revenue_at_risk,
                    2,
                ),

            "baseline_recovered_amount":
                round(
                    baseline_recovered_amount,
                    2,
                ),

            "recoveryos_recovered_amount":
                round(
                    recoveryos_recovered_amount,
                    2,
                ),

            "baseline_revenue_recovery_rate":
                round(
                    baseline_revenue_recovery_rate,
                    4,
                ),

            "recoveryos_revenue_recovery_rate":
                round(
                    recoveryos_revenue_recovery_rate,
                    4,
                ),

            "revenue_uplift_percent":
                round(
                    revenue_uplift_percent,
                    2,
                ),
        },


        "payments": {

            "baseline_recovered_count":
                baseline_recovered_count,

            "baseline_failed_count":
                baseline_failed_count,

            "recoveryos_recovered_count":
                recoveryos_recovered_count,

            "recoveryos_failed_count":
                recoveryos_failed_count,

            "baseline_recovery_rate":
                round(
                    baseline_recovery_rate,
                    4,
                ),

            "recoveryos_recovery_rate":
                round(
                    recoveryos_recovery_rate,
                    4,
                ),

            "recovery_count_uplift_percent":
                round(
                    recovery_count_uplift_percent,
                    2,
                ),
        },


        "operations": {

            "automated_actions":
                recoveryos_automated_count,

            "human_reviews":
                recoveryos_human_review_count,

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


        "action_distribution": {

            "recoveryos":
                recoveryos_action_distribution,

            "baseline":
                baseline_action_distribution,
        },


        "action_success_assumptions":
            ACTION_SUCCESS_RATES,


        "baseline_results":
            baseline_results,


        "recoveryos_results":
            recoveryos_results,
    }


    # ========================================================
    # SAVE RESULTS
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
            results,
            file,
            indent=2,
        )


    # ========================================================
    # TERMINAL REPORT
    # ========================================================

    print()

    print("=" * 70)

    print(
        "                 SIMULATION RESULTS"
    )

    print("=" * 70)

    print()

    print(
        f"Payments simulated          : "
        f"{total_payments:,}"
    )

    print(
        f"Revenue at risk             : "
        f"₹{total_revenue_at_risk:,.2f}"
    )

    print()


    # --------------------------------------------------------
    # BASELINE
    # --------------------------------------------------------

    print(
        "BASELINE"
    )

    print("-" * 70)

    print(
        f"Recovered payments          : "
        f"{baseline_recovered_count:,}"
    )

    print(
        f"Failed recovery attempts    : "
        f"{baseline_failed_count:,}"
    )

    print(
        f"Recovery rate               : "
        f"{baseline_recovery_rate * 100:.2f}%"
    )

    print(
        f"Revenue recovered           : "
        f"₹{baseline_recovered_amount:,.2f}"
    )

    print(
        f"Revenue recovery rate       : "
        f"{baseline_revenue_recovery_rate * 100:.2f}%"
    )

    print()


    # --------------------------------------------------------
    # RECOVERYOS
    # --------------------------------------------------------

    print(
        "RECOVERYOS"
    )

    print("-" * 70)

    print(
        f"Recovered payments          : "
        f"{recoveryos_recovered_count:,}"
    )

    print(
        f"Failed recovery attempts    : "
        f"{recoveryos_failed_count:,}"
    )

    print(
        f"Recovery rate               : "
        f"{recoveryos_recovery_rate * 100:.2f}%"
    )

    print(
        f"Revenue recovered           : "
        f"₹{recoveryos_recovered_amount:,.2f}"
    )

    print(
        f"Revenue recovery rate       : "
        f"{recoveryos_revenue_recovery_rate * 100:.2f}%"
    )

    print()


    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    print(
        "BASELINE vs RECOVERYOS"
    )

    print("-" * 70)

    print(
        f"Revenue uplift              : "
        f"{revenue_uplift_percent:.2f}%"
    )

    print(
        f"Recovery count uplift       : "
        f"{recovery_count_uplift_percent:.2f}%"
    )

    print()


    # --------------------------------------------------------
    # OPERATIONS
    # --------------------------------------------------------

    print(
        "RECOVERYOS OPERATIONS"
    )

    print("-" * 70)

    print(
        f"Automated actions           : "
        f"{recoveryos_automated_count:,}"
    )

    print(
        f"Human reviews               : "
        f"{recoveryos_human_review_count:,}"
    )

    print(
        f"Automation rate             : "
        f"{automation_rate * 100:.2f}%"
    )

    print(
        f"Human review rate           : "
        f"{human_review_rate * 100:.2f}%"
    )

    print()


    # --------------------------------------------------------
    # ACTION DISTRIBUTION
    # --------------------------------------------------------

    print(
        "RECOVERYOS ACTION DISTRIBUTION"
    )

    print("-" * 70)

    for action, count in sorted(
        recoveryos_action_distribution.items(),
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


    # --------------------------------------------------------
    # BASELINE DISTRIBUTION
    # --------------------------------------------------------

    print(
        "BASELINE ACTION DISTRIBUTION"
    )

    print("-" * 70)

    for action, count in sorted(
        baseline_action_distribution.items(),
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


    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    print("=" * 70)

    print(
        "Simulation complete."
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "These are synthetic benchmark results."
    )

    print(
        "They are NOT real production recovery results."
    )

    print()

    print(
        f"Metrics saved to:"
    )

    print(
        OUTPUT_PATH
    )

    print("=" * 70)

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_simulation()