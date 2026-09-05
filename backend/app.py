from pathlib import Path
import sqlite3
import json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ml.predict import predict_recovery

from backend.agent import (
    run_recovery_agent,
    build_action_probabilities,
)

from backend.decision_engine import (
    choose_best_action,
)

from backend.audit_logger import (
    get_audit_events,
    get_audit_count,
)


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "recoveryos.db"
)

FRONTEND_PATH = (
    PROJECT_ROOT
    / "frontend"
)

INDEX_PATH = (
    FRONTEND_PATH
    / "index.html"
)

STRATEGY_METRICS_PATH = (
    PROJECT_ROOT
    / "ml"
    / "models"
    / "strategy_metrics.json"
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="RecoveryOS",
    description=(
        "AI-powered revenue recovery agent with "
        "ML prediction, LLM diagnosis, deterministic "
        "policy guardrails, controlled recovery tools, "
        "verification, persistent audit logging, "
        "and batch simulation metrics."
    ),
    version="1.0.0",
)


# ============================================================
# STATIC FRONTEND
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=FRONTEND_PATH
    ),
    name="static",
)


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def get_payment(
    payment_id: str,
):

    """
    Retrieve a single payment
    from the database.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM payments
            WHERE payment_id = ?
            """,
            (payment_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    finally:

        connection.close()


# ============================================================
# REQUEST MODELS
# ============================================================

class RecoverRequest(BaseModel):

    payment_id: str


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def frontend():

    """
    Serve the RecoveryOS dashboard.
    """

    if not INDEX_PATH.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Frontend not found. "
                "Make sure frontend/index.html exists."
            ),
        )

    return FileResponse(
        INDEX_PATH
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {

        "status":
            "ok",

        "service":
            "RecoveryOS",

        "version":
            "1.0.0",

    }


# ============================================================
# PAYMENTS + RECOVERY OPPORTUNITIES
# ============================================================

@app.get("/payments")
def list_payments(
    limit: int = 20,
):

    """
    Return failed payments together with
    read-only RecoveryOS opportunity scores.

    IMPORTANT:

    This endpoint DOES NOT execute recovery actions.

    It only performs:

        Payment
           ↓
        ML prediction
           ↓
        Action probabilities
           ↓
        Deterministic policy
           ↓
        Expected recovery value

    Actual recovery execution only happens
    through POST /recover.
    """

    # --------------------------------------------------------
    # Keep API responses bounded.
    # --------------------------------------------------------

    limit = min(
        max(limit, 1),
        100,
    )


    connection = get_connection()

    try:

        cursor = connection.cursor()


        cursor.execute(
            """
            SELECT *
            FROM payments
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )


        rows = cursor.fetchall()


        opportunities = []


        # ----------------------------------------------------
        # Score every payment
        # ----------------------------------------------------

        for row in rows:

            payment = dict(row)


            try:

                # --------------------------------------------
                # STEP 1 — ML PREDICTION
                # --------------------------------------------

                base_probability = (
                    predict_recovery(
                        payment
                    )
                )


                # --------------------------------------------
                # STEP 2 — ACTION PROBABILITIES
                # --------------------------------------------

                action_probabilities = (
                    build_action_probabilities(
                        payment,
                        base_probability,
                    )
                )


                # --------------------------------------------
                # STEP 3 — DETERMINISTIC POLICY
                # --------------------------------------------

                decision = (
                    choose_best_action(
                        payment,
                        action_probabilities,
                    )
                )


                selected_action = (
                    decision.get(
                        "selected_action"
                    )
                )


                selected_probability = (
                    decision.get(
                        "selected_probability"
                    )
                )


                expected_recovery_value = (
                    decision.get(
                        "expected_recovery_value"
                    )
                )


                decision_reason = (
                    decision.get(
                        "decision_reason"
                    )
                )


                # --------------------------------------------
                # Add AI decisioning fields
                # --------------------------------------------

                payment[
                    "recovery_probability"
                ] = round(
                    float(
                        selected_probability
                        if selected_probability
                        is not None
                        else base_probability
                    ),
                    4,
                )


                payment[
                    "base_recovery_probability"
                ] = round(
                    float(
                        base_probability
                    ),
                    4,
                )


                payment[
                    "expected_recovery_value"
                ] = round(
                    float(
                        expected_recovery_value
                        or 0
                    ),
                    2,
                )


                payment[
                    "recommended_action"
                ] = selected_action


                payment[
                    "action_probabilities"
                ] = action_probabilities


                payment[
                    "decision_reason"
                ] = decision_reason


                payment[
                    "candidates"
                ] = decision.get(
                    "candidates",
                    [],
                )


            except Exception as error:

                # ------------------------------------------------
                # Do not break the entire dashboard if one
                # opportunity cannot be scored.
                # ------------------------------------------------

                payment[
                    "recovery_probability"
                ] = 0.0


                payment[
                    "base_recovery_probability"
                ] = 0.0


                payment[
                    "expected_recovery_value"
                ] = 0.0


                payment[
                    "recommended_action"
                ] = "HUMAN_REVIEW"


                payment[
                    "action_probabilities"
                ] = {}


                payment[
                    "decision_reason"
                ] = (
                    "Opportunity scoring failed; "
                    "manual review recommended."
                )


                payment[
                    "scoring_error"
                ] = str(error)


            opportunities.append(
                payment
            )


        # ----------------------------------------------------
        # Sort by Expected Recovery Value
        # ----------------------------------------------------

        opportunities.sort(
            key=lambda payment:
                float(
                    payment.get(
                        "expected_recovery_value",
                        0,
                    )
                    or 0
                ),
            reverse=True,
        )


        return {

            "count":
                len(opportunities),

            "payments":
                opportunities,

        }


    finally:

        connection.close()


# ============================================================
# DASHBOARD DATABASE METRICS
# ============================================================

@app.get("/dashboard")
def dashboard():

    connection = get_connection()

    try:

        cursor = connection.cursor()


        cursor.execute(
            """
            SELECT

                COUNT(*) AS total_payments,

                COALESCE(
                    SUM(amount),
                    0
                ) AS total_value,

                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'RECOVERED'
                            THEN amount
                            ELSE 0
                        END
                    ),
                    0
                ) AS recovered_value,

                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'FAILED'
                            THEN amount
                            ELSE 0
                        END
                    ),
                    0
                ) AS failed_value

            FROM payments
            """
        )


        row = cursor.fetchone()


        total_payments = (
            row["total_payments"]
            or 0
        )


        total_value = (
            row["total_value"]
            or 0
        )


        recovered_value = (
            row["recovered_value"]
            or 0
        )


        failed_value = (
            row["failed_value"]
            or 0
        )


        recovery_rate = 0


        if total_value > 0:

            recovery_rate = (
                recovered_value
                / total_value
            )


        return {

            "payments": {

                "total_payments":
                    total_payments,

                "total_value":
                    round(
                        total_value,
                        2,
                    ),

                "recovered_value":
                    round(
                        recovered_value,
                        2,
                    ),

                "failed_value":
                    round(
                        failed_value,
                        2,
                    ),

                "recovery_rate":
                    round(
                        recovery_rate,
                        4,
                    ),

            },


            "audit": {

                "total_audit_events":
                    get_audit_count(),

            },

        }


    finally:

        connection.close()


# ============================================================
# SIMULATION METRICS
# ============================================================

@app.get("/metrics")
def metrics():

    """
    Return the latest RecoveryOS simulation metrics.

    Generated by:

        python -m ml.evaluate_strategy

    These are synthetic counterfactual benchmark results
    and not real production recovery measurements.
    """

    if not STRATEGY_METRICS_PATH.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Strategy metrics not found. "
                "Run "
                "'python -m ml.evaluate_strategy' "
                "first."
            ),
        )


    try:

        with open(
            STRATEGY_METRICS_PATH,
            "r",
            encoding="utf-8",
        ) as file:

            simulation_metrics = (
                json.load(file)
            )


    except json.JSONDecodeError as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Strategy metrics file "
                "contains invalid JSON."
            ),
        ) from error


    return simulation_metrics


# ============================================================
# AUDIT TRAIL
# ============================================================

@app.get("/audit")
def audit(
    payment_id: Optional[str] = None,
    limit: int = 50,
):

    """
    Return persisted RecoveryOS audit events.
    """

    limit = min(
        max(limit, 1),
        100,
    )


    events = get_audit_events(
        payment_id=payment_id,
        limit=limit,
    )


    return {

        "count":
            len(events),

        "total_audit_events":
            get_audit_count(),

        "events":
            events,

    }


# ============================================================
# RECOVERY AGENT
# ============================================================

@app.post("/recover")
def recover(
    request: RecoverRequest,
):

    """
    Start one RecoveryOS agent run.

    Workflow:

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
    # STEP 1 — GET PAYMENT
    # ========================================================

    payment = get_payment(
        request.payment_id
    )


    if payment is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Payment "
                f"{request.payment_id} "
                f"not found."
            ),
        )


    # ========================================================
    # STEP 2 — RUN RECOVERY AGENT
    # ========================================================

    try:

        result = run_recovery_agent(
            payment
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Recovery agent encountered "
                "an unexpected error."
            ),
        ) from error


    # ========================================================
    # STEP 3 — RETURN AGENT RESULT
    # ========================================================

    return {

        "success":
            True,

        "agent":
            result,

    }