from pathlib import Path
import sqlite3


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "recoveryos.db"
)


# ============================================================
# SAVE AUDIT EVENT
# ============================================================

def save_audit_event(event: dict) -> int:
    """
    Persist a RecoveryOS agent decision.

    Every recovery run creates an immutable-style
    audit record containing:

        - payment context
        - ML prediction
        - LLM diagnosis
        - selected action
        - expected recovery value
        - execution result
        - verification result
        - final agent status
        - escalation reason
    """

    connection = sqlite3.connect(
        DB_PATH
    )

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO audit_events (

                payment_id,

                timestamp,

                amount,

                failure_code,

                base_recovery_probability,

                diagnosis_source,

                diagnosis,

                severity,

                selected_action,

                selected_probability,

                expected_recovery_value,

                decision_reason,

                execution_status,

                verification_status,

                agent_status,

                escalation_reason

            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                event.get(
                    "payment_id"
                ),

                event.get(
                    "timestamp"
                ),

                event.get(
                    "amount"
                ),

                event.get(
                    "failure_code"
                ),

                event.get(
                    "base_recovery_probability"
                ),

                event.get(
                    "diagnosis_source"
                ),

                event.get(
                    "diagnosis"
                ),

                event.get(
                    "severity"
                ),

                event.get(
                    "selected_action"
                ),

                event.get(
                    "selected_probability"
                ),

                event.get(
                    "expected_recovery_value"
                ),

                event.get(
                    "decision_reason"
                ),

                event.get(
                    "execution_status"
                ),

                event.get(
                    "verification_status"
                ),

                event.get(
                    "agent_status"
                ),

                event.get(
                    "escalation_reason"
                ),
            ),
        )

        audit_id = cursor.lastrowid

        connection.commit()

        return audit_id

    finally:

        connection.close()


# ============================================================
# GET AUDIT EVENTS
# ============================================================

def get_audit_events(
    payment_id: str | None = None,
    limit: int = 50,
):
    """
    Retrieve persisted RecoveryOS audit events.

    If payment_id is supplied, only audit events
    belonging to that payment are returned.
    """

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    try:

        cursor = connection.cursor()

        if payment_id:

            cursor.execute(
                """
                SELECT *
                FROM audit_events

                WHERE payment_id = ?

                ORDER BY audit_id DESC

                LIMIT ?
                """,
                (
                    payment_id,
                    limit,
                ),
            )

        else:

            cursor.execute(
                """
                SELECT *
                FROM audit_events

                ORDER BY audit_id DESC

                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


# ============================================================
# GET TOTAL AUDIT COUNT
# ============================================================

def get_audit_count():
    """
    Return the total number of persisted
    RecoveryOS audit events.
    """

    connection = sqlite3.connect(
        DB_PATH
    )

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM audit_events
            """
        )

        count = cursor.fetchone()[0]

        return count

    finally:

        connection.close()