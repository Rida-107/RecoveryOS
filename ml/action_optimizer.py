from pathlib import Path
import joblib
import numpy as np
import pandas as pd


# =========================================================
# RecoveryOS Action Optimizer
# =========================================================
#
# Purpose:
# Convert the ML model's base recovery probability into
# action-specific recovery probabilities and Expected
# Recovery Values (ERV).
#
# The optimizer evaluates:
#
#   1. DELAYED_RETRY
#   2. PAYMENT_LINK
#   3. HUMAN_REVIEW
#
# Safety constraints are applied separately by the
# deterministic policy engine.
# =========================================================


BASE = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    BASE
    / "ml"
    / "models"
    / "recovery_model.joblib"
)


FEATURES = [
    "amount",
    "payment_method",
    "failure_code",
    "successful_payments",
    "previous_retries",
    "customer_tenure_days",
    "transaction_hour",
    "merchant_category",
    "days_since_last_success",
    "customer_avg_amount",
]


# =========================================================
# Load model
# =========================================================

_model = None


def load_model():
    """
    Load the trained recovery model once.
    """

    global _model

    if _model is None:
        _model = joblib.load(MODEL_PATH)

    return _model


# =========================================================
# Base ML probability
# =========================================================

def predict_base_probability(payment):
    """
    Predict the base probability that the payment
    can eventually be recovered.

    This is NOT an action-specific probability.
    """

    model = load_model()

    row = pd.DataFrame(
        [{
            feature: payment[feature]
            for feature in FEATURES
        }]
    )

    probability = model.predict_proba(row)[0][1]

    return float(
        np.clip(probability, 0.0, 0.95)
    )


# =========================================================
# Action-specific probability
# =========================================================

def predict_action_probability(
    payment,
    base_probability,
    action,
):
    """
    Estimate recovery probability for a specific
    intervention.

    IMPORTANT:
    These intervention adjustments are part of the
    synthetic offline simulation and prototype decision
    model. They are not claimed to be production-trained
    action outcomes.
    """

    failure = payment["failure_code"]

    previous_retries = int(
        payment["previous_retries"]
    )

    probability = float(
        base_probability
    )

    # -----------------------------------------------------
    # DELAYED RETRY
    # -----------------------------------------------------

    if action == "DELAYED_RETRY":

        # Transient failures are strong retry candidates.
        if failure in [
            "NETWORK_ERROR",
            "BANK_TIMEOUT",
            "GATEWAY_TIMEOUT",
        ]:
            probability += 0.10

        # Repeated retries reduce expected effectiveness.
        if previous_retries >= 2:
            probability -= 0.10

        # Don't repeatedly retry when the payment
        # instrument itself is the likely problem.
        if failure in [
            "CARD_EXPIRED",
            "EXPIRED_CARD",
            "INSUFFICIENT_FUNDS",
            "LIMIT_EXCEEDED",
        ]:
            probability -= 0.20

    # -----------------------------------------------------
    # PAYMENT LINK
    # -----------------------------------------------------

    elif action == "PAYMENT_LINK":

        # Alternate payment method is more useful when
        # the original instrument may be the problem.
        if failure in [
            "CARD_EXPIRED",
            "EXPIRED_CARD",
            "INSUFFICIENT_FUNDS",
            "LIMIT_EXCEEDED",
            "BANK_DECLINED",
        ]:
            probability += 0.18

        # After multiple attempts, alternate payment
        # becomes more attractive.
        if previous_retries >= 2:
            probability += 0.05

    # -----------------------------------------------------
    # HUMAN REVIEW
    # -----------------------------------------------------

    elif action == "HUMAN_REVIEW":

        # Controlled escalation receives a small
        # simulated benefit, but is NOT treated as
        # guaranteed recovery.
        probability += 0.05

    else:

        raise ValueError(
            f"Unknown recovery action: {action}"
        )

    return float(
        np.clip(
            probability,
            0.0,
            0.95,
        )
    )


# =========================================================
# Calculate action scores
# =========================================================

def build_action_scores(
    payment,
    base_probability=None,
):
    """
    Build action-level probability and Expected Recovery
    Value for every available action.

    Returns a dictionary that can be consumed by:
      - the agent
      - the API
      - the evaluator
      - the frontend
    """

    if base_probability is None:

        base_probability = (
            predict_base_probability(payment)
        )

    actions = [
        "DELAYED_RETRY",
        "PAYMENT_LINK",
        "HUMAN_REVIEW",
    ]

    results = {}

    amount = float(
        payment["amount"]
    )

    for action in actions:

        probability = (
            predict_action_probability(
                payment,
                base_probability,
                action,
            )
        )

        expected_recovery_value = (
            amount * probability
        )

        results[action] = {

            "probability": round(
                probability,
                4,
            ),

            "expected_recovery_value": round(
                expected_recovery_value,
                2,
            ),
        }

    return {

        "base_probability": round(
            base_probability,
            4,
        ),

        "actions": results,
    }


# =========================================================
# Choose highest expected value
# =========================================================

def choose_highest_value_action(
    payment,
    base_probability=None,
):
    """
    Select the action with the highest Expected Recovery
    Value.

    IMPORTANT:
    This function does NOT replace deterministic safety
    policy.

    It answers:
        "Which action appears economically best?"

    The policy engine answers:
        "Are we actually allowed to perform it?"
    """

    scores = build_action_scores(
        payment,
        base_probability,
    )

    actions = scores["actions"]

    best_action = max(
        actions,
        key=lambda action:
        actions[action][
            "expected_recovery_value"
        ],
    )

    return {

        "selected_action":
            best_action,

        "selected_probability":
            actions[best_action][
                "probability"
            ],

        "expected_recovery_value":
            actions[best_action][
                "expected_recovery_value"
            ],

        "action_scores":
            scores,
    }


# =========================================================
# Local test
# =========================================================

if __name__ == "__main__":

    print("=" * 70)
    print("RecoveryOS Action Optimizer Test")
    print("=" * 70)

    dataset_path = (
        BASE
        / "data"
        / "payments_training.csv"
    )

    df = pd.read_csv(
        dataset_path
    )

    payment = (
        df.iloc[0]
        .to_dict()
    )

    print()
    print("Test payment")
    print("-" * 70)

    print(
        f"Payment ID:       "
        f"{payment['payment_id']}"
    )

    print(
        f"Amount:            "
        f"₹{payment['amount']:,.2f}"
    )

    print(
        f"Failure:           "
        f"{payment['failure_code']}"
    )

    print(
        f"Previous retries:  "
        f"{payment['previous_retries']}"
    )

    print()

    result = choose_highest_value_action(
        payment
    )

    print("Base probability")
    print("-" * 70)

    print(
        f"{result['action_scores']['base_probability'] * 100:.2f}%"
    )

    print()
    print("ACTION SCORES")
    print("-" * 70)

    for action, values in (
        result[
            "action_scores"
        ]["actions"].items()
    ):

        print(
            f"{action:20}"
            f"Probability: "
            f"{values['probability'] * 100:6.2f}%   "
            f"EV: "
            f"₹{values['expected_recovery_value']:,.2f}"
        )

    print()
    print("BEST ECONOMIC ACTION")
    print("-" * 70)

    print(
        f"Action: "
        f"{result['selected_action']}"
    )

    print(
        f"Probability: "
        f"{result['selected_probability'] * 100:.2f}%"
    )

    print(
        f"Expected Recovery Value: "
        f"₹{result['expected_recovery_value']:,.2f}"
    )

    print()
    print("=" * 70)
    print("Optimizer test complete.")
    print("=" * 70)