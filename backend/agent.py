from datetime import datetime
from typing import Dict, Any


from ml.predict import predict_recovery

from ml.action_optimizer import (
    predict_action_probability,
    build_action_scores,
)

from backend.llm_diagnosis import (
    diagnose_with_claude,
)

from backend.decision_engine import (
    choose_best_action,
)

from backend.recovery_tools import (
    execute_action,
    verify_payment_status,
)

from backend.audit_logger import (
    save_audit_event,
)


# ============================================================
# CONFIGURATION
# ============================================================

MAX_AUTOMATED_RETRIES = 3

HIGH_VALUE_THRESHOLD = 50000

LOW_CONFIDENCE_THRESHOLD = 0.30


# ============================================================
# ACTION PROBABILITIES
# ============================================================

def build_action_probabilities(
    payment: Dict[str, Any],
    base_probability: float,
):
    """
    Build action-specific recovery probabilities.

    RecoveryOS uses the centralized Action Optimizer
    as the single source of truth for action scoring.

    The ML model provides the base probability.

    The Action Optimizer estimates:

        P(recovery | DELAYED_RETRY)
        P(recovery | PAYMENT_LINK)
        P(recovery | HUMAN_REVIEW)

    These are synthetic MVP strategy scores and are NOT
    production causal estimates.
    """

    scores = build_action_scores(
        payment,
        base_probability,
    )

    actions = scores["actions"]

    return {
        "DELAYED_RETRY": actions[
            "DELAYED_RETRY"
        ]["probability"],

        "PAYMENT_LINK": actions[
            "PAYMENT_LINK"
        ]["probability"],

        "HUMAN_REVIEW": actions[
            "HUMAN_REVIEW"
        ]["probability"],
    }


# ============================================================
# VERIFICATION
# ============================================================

def verify_recovery_action(
    payment: Dict[str, Any],
    selected_action: str,
    execution_result: Dict[str, Any],
):
    """
    Verify the result of the recovery intervention.

    A Payment Link or Delayed Retry does not immediately mean
    that the payment itself has been recovered.

        CREATED / SCHEDULED
                ↓
          ACTION_VERIFIED
                ↓
       customer/retry outcome
                ↓
            RECOVERED

    RecoveryOS therefore does not falsely claim that money
    was recovered merely because an intervention was created.
    """

    execution_status = (
        execution_result.get("status")
    )

    # --------------------------------------------------------
    # Tool failure
    # --------------------------------------------------------

    if execution_status == "FAILED":

        return {
            "status": "VERIFICATION_FAILED",
            "verified": False,
            "verification_type": "ACTION_EXECUTION",
            "message": (
                "Recovery action failed to execute. "
                "Human review is required."
            ),
        }

    # --------------------------------------------------------
    # Payment Link
    # --------------------------------------------------------

    if selected_action == "PAYMENT_LINK":

        if execution_status == "CREATED":

            return {
                "status": "ACTION_VERIFIED",
                "verified": True,
                "verification_type": "ACTION_EXECUTION",
                "message": (
                    "Payment link successfully created. "
                    "Payment remains pending customer recovery."
                ),
            }

    # --------------------------------------------------------
    # Delayed Retry
    # --------------------------------------------------------

    if selected_action == "DELAYED_RETRY":

        if execution_status in [
            "SCHEDULED",
            "CREATED",
        ]:

            return {
                "status": "ACTION_VERIFIED",
                "verified": True,
                "verification_type": "ACTION_EXECUTION",
                "message": (
                    "Retry successfully scheduled. "
                    "Payment outcome will be evaluated after retry."
                ),
            }

    # --------------------------------------------------------
    # Human Review
    # --------------------------------------------------------

    if selected_action == "HUMAN_REVIEW":

        if execution_status in [
            "ESCALATED",
            "CREATED",
        ]:

            return {
                "status": "ACTION_VERIFIED",
                "verified": True,
                "verification_type": "ESCALATION",
                "message": (
                    "Case successfully escalated to human review."
                ),
            }

    # --------------------------------------------------------
    # Existing payment status
    # --------------------------------------------------------

    try:

        payment_status = (
            verify_payment_status(payment)
        )

        if payment_status.get("status") == "RECOVERED":

            return {
                "status": "PAYMENT_RECOVERED",
                "verified": True,
                "verification_type": "PAYMENT_STATUS",
                "message": (
                    "Payment is confirmed as recovered."
                ),
            }

    except Exception:
        pass

    # --------------------------------------------------------
    # Unknown / unexpected result
    # --------------------------------------------------------

    return {
        "status": "VERIFICATION_FAILED",
        "verified": False,
        "verification_type": "ACTION_EXECUTION",
        "message": (
            "Recovery action result could not be verified."
        ),
    }


# ============================================================
# MAIN RECOVERY AGENT
# ============================================================

def run_recovery_agent(
    payment: Dict[str, Any],
):
    """
    Run the complete RecoveryOS agent workflow.

    Pipeline:

        OBSERVE
           ↓
        PREDICT
           ↓
        DIAGNOSE
           ↓
        PLAN
           ↓
        POLICY
           ↓
        ACT
           ↓
        VERIFY
           ↓
        AUDIT
    """

    # ========================================================
    # STEP 1 — OBSERVE
    # ========================================================

    payment_id = payment["payment_id"]

    # ========================================================
    # STEP 2 — PREDICT
    # ========================================================

    base_probability = predict_recovery(
        payment
    )

    # ========================================================
    # STEP 3 — DIAGNOSE
    # ========================================================

    diagnosis = diagnose_with_claude(
        payment
    )

    # ========================================================
    # STEP 4 — PLAN
    # ========================================================

    action_probabilities = (
        build_action_probabilities(
            payment,
            base_probability,
        )
    )

    # ========================================================
    # STEP 5 — POLICY / DECISION
    # ========================================================

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

    candidates = decision.get(
        "candidates",
        [],
    )

    # ========================================================
    # STEP 6 — ACT
    # ========================================================

    execution_result = execute_action(
        payment,
        selected_action,
        decision_reason,
    )

    # ========================================================
    # STEP 7 — VERIFY
    # ========================================================

    verification_result = verify_recovery_action(
        payment,
        selected_action,
        execution_result,
    )

    # ========================================================
    # DETERMINE FINAL AGENT STATUS
    # ========================================================

    execution_status = (
        execution_result.get("status")
    )

    verification_status = (
        verification_result.get("status")
    )

    requires_human_review = bool(
        execution_result.get(
            "requires_human_review",
            False,
        )
    )

    escalation_reason = (
        execution_result.get("error")
        or execution_result.get("message")
        or None
    )

    # --------------------------------------------------------
    # Tool failure
    # --------------------------------------------------------

    if execution_status == "FAILED":

        agent_status = (
            "HUMAN_REVIEW_REQUIRED"
        )

        escalation_reason = (
            escalation_reason
            or "Recovery tool execution failed."
        )

    # --------------------------------------------------------
    # Verification failure
    # --------------------------------------------------------

    elif verification_status == (
        "VERIFICATION_FAILED"
    ):

        agent_status = (
            "HUMAN_REVIEW_REQUIRED"
        )

        escalation_reason = (
            escalation_reason
            or "Recovery action could not be verified."
        )

    # --------------------------------------------------------
    # Explicit human review
    # --------------------------------------------------------

    elif selected_action == "HUMAN_REVIEW":

        agent_status = (
            "HUMAN_REVIEW_REQUIRED"
        )

        escalation_reason = (
            escalation_reason
            or "Decision engine selected human review."
        )

    # --------------------------------------------------------
    # Payment Link
    # --------------------------------------------------------

    elif selected_action == "PAYMENT_LINK":

        agent_status = (
            "AWAITING_CUSTOMER_RECOVERY"
        )

    # --------------------------------------------------------
    # Delayed Retry
    # --------------------------------------------------------

    elif selected_action == "DELAYED_RETRY":

        agent_status = (
            "RETRY_SCHEDULED"
        )

    # --------------------------------------------------------
    # Payment already recovered
    # --------------------------------------------------------

    elif verification_status == (
        "PAYMENT_RECOVERED"
    ):

        agent_status = (
            "PAYMENT_RECOVERED"
        )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    else:

        agent_status = (
            "ACTION_COMPLETED"
        )

    # ========================================================
    # STEP 8 — AUDIT EVENT
    # ========================================================

    audit_event = {

        "timestamp":
            datetime.utcnow().isoformat(),

        "payment_id":
            payment["payment_id"],

        "amount":
            payment["amount"],

        "failure_code":
            payment["failure_code"],

        "base_recovery_probability":
            base_probability,

        "diagnosis_source":
            diagnosis.get("source"),

        "diagnosis":
            diagnosis.get("diagnosis"),

        "severity":
            diagnosis.get("severity"),

        "selected_action":
            selected_action,

        "selected_probability":
            selected_probability,

        "expected_recovery_value":
            expected_recovery_value,

        "decision_reason":
            decision_reason,

        "execution_status":
            execution_status,

        "verification_status":
            verification_status,

        "agent_status":
            agent_status,

        "escalation_reason":
            escalation_reason,
    }

    # ========================================================
    # STEP 9 — PERSIST AUDIT
    # ========================================================

    audit_id = save_audit_event(
        audit_event
    )

    audit_event["audit_id"] = (
        audit_id
    )

    # ========================================================
    # STEP 10 — RETURN RESULT
    # ========================================================

    return {

        # ----------------------------------------------------
        # PAYMENT
        # ----------------------------------------------------

        "payment": {

            "payment_id":
                payment["payment_id"],

            "amount":
                payment["amount"],

            "payment_method":
                payment["payment_method"],

            "failure_code":
                payment["failure_code"],

            "previous_retries":
                payment["previous_retries"],

            "status":
                payment["status"],
        },

        # ----------------------------------------------------
        # ML
        # ----------------------------------------------------

        "ml_prediction": {

            "base_recovery_probability":
                base_probability,
        },

        # ----------------------------------------------------
        # LLM
        # ----------------------------------------------------

        "llm_diagnosis":
            diagnosis,

        # ----------------------------------------------------
        # ACTION PROBABILITIES
        # ----------------------------------------------------

        "action_probabilities":
            action_probabilities,

        # ----------------------------------------------------
        # DECISION
        # ----------------------------------------------------

        "decision": {

            "selected_action":
                selected_action,

            "selected_probability":
                selected_probability,

            "expected_recovery_value":
                expected_recovery_value,

            "decision_reason":
                decision_reason,

            "candidates":
                candidates,
        },

        # ----------------------------------------------------
        # EXECUTION
        # ----------------------------------------------------

        "execution":
            execution_result,

        # ----------------------------------------------------
        # VERIFICATION
        # ----------------------------------------------------

        "verification":
            verification_result,

        # ----------------------------------------------------
        # FINAL AGENT STATUS
        # ----------------------------------------------------

        "agent_status":
            agent_status,

        "escalation_reason":
            escalation_reason,

        # ----------------------------------------------------
        # GUARDRAILS
        # ----------------------------------------------------

        "guardrails": {

            "max_retries":
                MAX_AUTOMATED_RETRIES,

            "verification_required":
                True,

            "high_value_threshold":
                HIGH_VALUE_THRESHOLD,

            "low_confidence_threshold":
                LOW_CONFIDENCE_THRESHOLD,

            "money_movement_controlled_by_deterministic_tools":
                True,

            "llm_authorized_to_move_money":
                False,
        },

        # ----------------------------------------------------
        # AUDIT
        # ----------------------------------------------------

        "audit_event":
            audit_event,
    }