from typing import Dict, Any


# ============================================================
# RECOVERYOS DECISION ENGINE
# ============================================================
#
# The decision engine is deterministic.
#
# ML predicts recovery probability.
# Claude explains the situation.
# This layer decides what actions are ALLOWED.
#
# The LLM cannot directly authorize financial actions.
#
# ============================================================


# ============================================================
# POLICY CONSTANTS
# ============================================================

MAX_AUTOMATED_RETRIES = 3

HIGH_VALUE_THRESHOLD = 50000

LOW_CONFIDENCE_THRESHOLD = 0.30


# ============================================================
# EXPECTED RECOVERY VALUE
# ============================================================

def calculate_expected_value(
    amount: float,
    probability: float,
) -> float:
    """
    Expected Recovery Value (ERV)

    ERV = payment amount × probability of recovery
    """

    return round(
        amount * probability,
        2,
    )


# ============================================================
# DECISION ENGINE
# ============================================================

def choose_best_action(
    payment: Dict[str, Any],
    action_probabilities: Dict[str, float],
):
    """
    Select the best permitted recovery action.

    Actions:

        DELAYED_RETRY
        PAYMENT_LINK
        HUMAN_REVIEW

    The decision is based on:

        1. Recovery probability
        2. Expected Recovery Value
        3. Retry limits
        4. Payment value
        5. Failure type
        6. Confidence
        7. Safety policies
    """

    amount = float(
        payment["amount"]
    )

    previous_retries = int(
        payment["previous_retries"]
    )

    failure_code = payment[
        "failure_code"
    ]


    # ========================================================
    # GLOBAL SAFETY CONDITIONS
    # ========================================================

    retry_allowed = (
        previous_retries
        < MAX_AUTOMATED_RETRIES
    )

    high_value = (
        amount
        > HIGH_VALUE_THRESHOLD
    )


    # ========================================================
    # BUILD CANDIDATES
    # ========================================================

    candidates = []


    for action, probability in (
        action_probabilities.items()
    ):

        probability = float(
            probability
        )

        allowed = True

        reason = (
            "Action permitted by policy."
        )


        # ====================================================
        # LOW CONFIDENCE PROTECTION
        # ====================================================

        if probability < LOW_CONFIDENCE_THRESHOLD:

            if action != "HUMAN_REVIEW":

                allowed = False

                reason = (
                    "Recovery confidence is "
                    "below the automated-action "
                    "threshold."
                )


        # ====================================================
        # DELAYED RETRY POLICY
        # ====================================================

        if action == "DELAYED_RETRY":

            # Retry limit
            if not retry_allowed:

                allowed = False

                reason = (
                    "Automated retry limit reached."
                )


            # High-value protection
            elif high_value:

                allowed = False

                reason = (
                    "High-value payment requires "
                    "human approval."
                )


            # Failures where retrying same method
            # is unlikely to help
            elif failure_code in [
                "CARD_EXPIRED",
                "EXPIRED_CARD",
                "INSUFFICIENT_FUNDS",
                "LIMIT_EXCEEDED",
            ]:

                allowed = False

                reason = (
                    "Retrying the same payment "
                    "method is unlikely to help."
                )


        # ====================================================
        # PAYMENT LINK POLICY
        # ====================================================

        elif action == "PAYMENT_LINK":

            if high_value:

                allowed = False

                reason = (
                    "High-value payment requires "
                    "human approval before customer "
                    "recovery action."
                )


        # ====================================================
        # HUMAN REVIEW
        # ====================================================

        elif action == "HUMAN_REVIEW":

            allowed = True

            reason = (
                "Human escalation is always permitted."
            )


        # ====================================================
        # UNKNOWN ACTION PROTECTION
        # ====================================================

        else:

            allowed = False

            reason = (
                "Unknown action blocked by policy."
            )


        # ====================================================
        # EXPECTED RECOVERY VALUE
        # ====================================================

        expected_value = (
            calculate_expected_value(
                amount,
                probability,
            )
        )


        candidates.append({

            "action":
                action,

            "probability":
                round(
                    probability,
                    4,
                ),

            "expected_value":
                expected_value,

            "allowed":
                allowed,

            "reason":
                reason,
        })


    # ========================================================
    # SELECT FROM ALLOWED ACTIONS
    # ========================================================

    allowed_candidates = [
        candidate
        for candidate in candidates
        if candidate["allowed"]
    ]


    # ========================================================
    # SAFETY FALLBACK
    # ========================================================

    if not allowed_candidates:

        return {

            "selected_action":
                "HUMAN_REVIEW",

            "selected_probability":
                0.0,

            "expected_recovery_value":
                0.0,

            "decision_reason":
                "No automated action passed "
                "the safety policies. "
                "Escalating to human review.",

            "candidates":
                candidates,
        }


    # ========================================================
    # BEST ACTION
    # ========================================================

    best_action = max(
        allowed_candidates,
        key=lambda candidate:
            candidate["expected_value"],
    )


    return {

        "selected_action":
            best_action["action"],

        "selected_probability":
            best_action["probability"],

        "expected_recovery_value":
            best_action["expected_value"],

        "decision_reason":
            best_action["reason"],

        "candidates":
            candidates,
    }