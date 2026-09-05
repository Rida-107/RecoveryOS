"""
RecoveryOS adversarial safety tests.

These tests intentionally use values outside the training dataset to verify
that deterministic policy guardrails still protect high-risk cases.

Run:
    python -m pytest -q tests/test_safety_stress.py
"""

from backend.decision_engine import choose_best_action


def make_payment(
    amount=75000,
    failure_code="BANK_TIMEOUT",
    previous_retries=0,
):
    return {
        "payment_id": "stress_test",
        "amount": amount,
        "payment_method": "CARD",
        "failure_code": failure_code,
        "successful_payments": 20,
        "previous_retries": previous_retries,
        "customer_tenure_days": 500,
        "transaction_hour": 14,
        "merchant_category": "E_COMMERCE",
        "days_since_last_success": 3,
        "customer_avg_amount": 8000,
        "status": "FAILED",
    }


def test_high_value_transient_failure_requires_human_review():
    payment = make_payment(
        amount=75000,
        failure_code="BANK_TIMEOUT",
        previous_retries=0,
    )

    probabilities = {
        "DELAYED_RETRY": 0.95,
        "PAYMENT_LINK": 0.95,
        "HUMAN_REVIEW": 0.90,
    }

    decision = choose_best_action(
        payment,
        probabilities,
    )

    assert decision["selected_action"] == "HUMAN_REVIEW"


def test_high_value_payment_link_is_blocked():
    payment = make_payment(
        amount=100000,
        failure_code="EXPIRED_CARD",
        previous_retries=0,
    )

    probabilities = {
        "DELAYED_RETRY": 0.10,
        "PAYMENT_LINK": 0.95,
        "HUMAN_REVIEW": 0.50,
    }

    decision = choose_best_action(
        payment,
        probabilities,
    )

    assert decision["selected_action"] == "HUMAN_REVIEW"

    candidates = {
        item["action"]: item
        for item in decision["candidates"]
    }

    assert candidates["PAYMENT_LINK"]["allowed"] is False


def test_high_value_retry_is_blocked():
    payment = make_payment(
        amount=250000,
        failure_code="BANK_TIMEOUT",
        previous_retries=0,
    )

    probabilities = {
        "DELAYED_RETRY": 0.95,
        "PAYMENT_LINK": 0.10,
        "HUMAN_REVIEW": 0.20,
    }

    decision = choose_best_action(
        payment,
        probabilities,
    )

    assert decision["selected_action"] == "HUMAN_REVIEW"

    candidates = {
        item["action"]: item
        for item in decision["candidates"]
    }

    assert candidates["DELAYED_RETRY"]["allowed"] is False


def test_retry_limit_cannot_be_overridden_by_probability():
    payment = make_payment(
        amount=10000,
        failure_code="BANK_TIMEOUT",
        previous_retries=3,
    )

    probabilities = {
        "DELAYED_RETRY": 0.95,
        "PAYMENT_LINK": 0.10,
        "HUMAN_REVIEW": 0.20,
    }

    decision = choose_best_action(
        payment,
        probabilities,
    )

    assert decision["selected_action"] == "HUMAN_REVIEW"

    candidates = {
        item["action"]: item
        for item in decision["candidates"]
    }

    assert candidates["DELAYED_RETRY"]["allowed"] is False


def test_expired_card_retry_is_blocked():
    payment = make_payment(
        amount=12000,
        failure_code="EXPIRED_CARD",
        previous_retries=0,
    )

    probabilities = {
        "DELAYED_RETRY": 0.95,
        "PAYMENT_LINK": 0.60,
        "HUMAN_REVIEW": 0.40,
    }

    decision = choose_best_action(
        payment,
        probabilities,
    )

    assert decision["selected_action"] != "DELAYED_RETRY"

    candidates = {
        item["action"]: item
        for item in decision["candidates"]
    }

    assert candidates["DELAYED_RETRY"]["allowed"] is False


def test_unknown_action_is_never_authorized():
    payment = make_payment(
        amount=10000,
        failure_code="BANK_TIMEOUT",
        previous_retries=0,
    )

    probabilities = {
        "DELAYED_RETRY": 0.50,
        "PAYMENT_LINK": 0.40,
        "HUMAN_REVIEW": 0.30,
        "MOVE_MONEY": 0.99,
    }

    decision = choose_best_action(
        payment,
        probabilities,
    )

    assert decision["selected_action"] != "MOVE_MONEY"

    candidates = {
        item["action"]: item
        for item in decision["candidates"]
    }

    assert candidates["MOVE_MONEY"]["allowed"] is False
