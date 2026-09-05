from pathlib import Path
import sqlite3
import uuid
import os
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

BASE = Path(__file__).resolve().parent.parent

DB = BASE / "data" / "recoveryos.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def db_conn():

    connection = sqlite3.connect(DB)

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# TOOL ERROR HELPER
# ============================================================

def tool_error(
    tool_name,
    payment_id,
    error_message,
):
    """
    Standardized safe tool-failure response.

    A failed tool NEVER raises an uncontrolled exception
    into the recovery workflow.
    """

    return {

        "tool": tool_name,

        "status": "FAILED",

        "payment_id": payment_id,

        "error": error_message,

        "recoverable": False,

        "requires_human_review": True,

        "message": (
            "Tool execution failed. "
            "No additional automated action "
            "was attempted."
        ),
    }


# ============================================================
# CREATE PAYMENT LINK
# ============================================================

def create_payment_link(payment):
    """
    Simulated payment-link tool.

    In production this would call a payment provider API.

    For the buildathon demo we generate a safe mock link.

    Failure simulation:

        RECOVERYOS_SIMULATE_TOOL_FAILURE=payment_link
    """

    payment_id = payment["payment_id"]


    # --------------------------------------------------------
    # FAILURE SIMULATION
    # --------------------------------------------------------

    if os.getenv(
        "RECOVERYOS_SIMULATE_TOOL_FAILURE"
    ) == "payment_link":

        return tool_error(
            "create_payment_link",
            payment_id,
            "Simulated payment-link service failure.",
        )


    # --------------------------------------------------------
    # NORMAL EXECUTION
    # --------------------------------------------------------

    link_id = (
        f"plink_"
        f"{uuid.uuid4().hex[:10]}"
    )

    return {

        "tool":
            "create_payment_link",

        "status":
            "CREATED",

        "payment_id":
            payment_id,

        "payment_link_id":
            link_id,

        "payment_link":
            (
                f"https://recoveryos.demo/pay/"
                f"{link_id}"
            ),

        "amount":
            payment["amount"],

        "message":
            "Payment link created successfully.",
    }


# ============================================================
# SCHEDULE RETRY
# ============================================================

def schedule_retry(
    payment,
    delay_minutes=30,
):
    """
    Simulated delayed-retry tool.

    In production this would schedule a controlled
    payment retry through the payment provider.

    Failure simulation:

        RECOVERYOS_SIMULATE_TOOL_FAILURE=retry
    """

    payment_id = payment["payment_id"]


    # --------------------------------------------------------
    # FAILURE SIMULATION
    # --------------------------------------------------------

    if os.getenv(
        "RECOVERYOS_SIMULATE_TOOL_FAILURE"
    ) == "retry":

        return tool_error(
            "schedule_retry",
            payment_id,
            "Simulated retry scheduler failure.",
        )


    # --------------------------------------------------------
    # NORMAL EXECUTION
    # --------------------------------------------------------

    return {

        "tool":
            "schedule_retry",

        "status":
            "SCHEDULED",

        "payment_id":
            payment_id,

        "scheduled_after_minutes":
            delay_minutes,

        "message":
            (
                f"Retry scheduled after "
                f"{delay_minutes} minutes."
            ),
    }


# ============================================================
# HUMAN ESCALATION
# ============================================================

def escalate_to_human(
    payment,
    reason,
):
    """
    Escalate a payment to a human operator.

    This is the ultimate safety fallback.
    """

    case_id = (
        f"case_"
        f"{uuid.uuid4().hex[:10]}"
    )

    return {

        "tool":
            "escalate_to_human",

        "status":
            "ESCALATED",

        "payment_id":
            payment["payment_id"],

        "case_id":
            case_id,

        "reason":
            reason,

        "message":
            "Payment escalated for human review.",
    }


# ============================================================
# VERIFY PAYMENT STATUS
# ============================================================

def verify_payment_status(payment):
    """
    Verify the current payment state from the database.

    This is deliberately separate from action execution.

    The agent must verify state before considering
    another automated action.
    """

    payment_id = payment["payment_id"]


    # --------------------------------------------------------
    # FAILURE SIMULATION
    # --------------------------------------------------------

    if os.getenv(
        "RECOVERYOS_SIMULATE_TOOL_FAILURE"
    ) == "verification":

        return {

            "tool":
                "verify_payment_status",

            "payment_id":
                payment_id,

            "status":
                "VERIFICATION_FAILED",

            "verified_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "requires_human_review":
                True,

            "message":
                (
                    "Payment verification failed. "
                    "No additional automated action "
                    "should be attempted."
                ),
        }


    # --------------------------------------------------------
    # DATABASE VERIFICATION
    # --------------------------------------------------------

    with db_conn() as connection:

        row = connection.execute(
            """
            SELECT status
            FROM payments
            WHERE payment_id=?
            """,
            (payment_id,),
        ).fetchone()


    status = (
        row["status"]
        if row
        else "UNKNOWN"
    )


    return {

        "tool":
            "verify_payment_status",

        "payment_id":
            payment_id,

        "status":
            status,

        "verified_at":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "requires_human_review":
            False,

    }


# ============================================================
# EXECUTE ACTION
# ============================================================

def execute_action(
    payment,
    action,
    reason,
):
    """
    Central controlled tool router.

    IMPORTANT:

    The LLM does NOT call these tools directly.

    The deterministic decision engine selects
    an approved action first.

    This function executes ONLY that action.

    If the tool fails, the failure is returned safely
    and no automatic retry is attempted here.
    """

    payment_id = payment["payment_id"]


    # ========================================================
    # PAYMENT LINK
    # ========================================================

    if action == "PAYMENT_LINK":

        result = create_payment_link(
            payment
        )


    # ========================================================
    # DELAYED RETRY
    # ========================================================

    elif action == "DELAYED_RETRY":

        result = schedule_retry(
            payment,
            delay_minutes=30,
        )


    # ========================================================
    # HUMAN REVIEW
    # ========================================================

    elif action == "HUMAN_REVIEW":

        result = escalate_to_human(
            payment,
            reason,
        )


    # ========================================================
    # UNKNOWN ACTION
    # ========================================================

    else:

        return {

            "tool":
                "none",

            "status":
                "BLOCKED",

            "payment_id":
                payment_id,

            "requires_human_review":
                True,

            "message":
                (
                    "Unknown action blocked "
                    "by safety layer."
                ),
        }


    # ========================================================
    # TOOL FAILURE HANDLING
    # ========================================================

    if result.get("status") == "FAILED":

        result["fallback_action"] = (
            "HUMAN_REVIEW"
        )

        result["fallback_reason"] = (
            "Automated tool execution failed; "
            "escalation is required."
        )


    return result