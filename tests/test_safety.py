from backend.decision_engine import choose_best_action


# ============================================================
# TEST HELPERS
# ============================================================

def make_payment(
    amount=10000,
    failure_code="BANK_TIMEOUT",
    previous_retries=0,
):
    return {
        "payment_id": "test_payment",
        "amount": amount,
        "payment_method": "CARD",
        "failure_code": failure_code,
        "successful_payments": 10,
        "previous_retries": previous_retries,
        "customer_tenure_days": 500,
        "transaction_hour": 14,
        "merchant_category": "E_COMMERCE",
        "days_since_last_success": 5,
        "customer_avg_amount": 5000,
        "status": "FAILED",
        "created_at": "2026-09-03T20:00:00",
    }


def get_candidate(result, action):
    for candidate in result["candidates"]:
        if candidate["action"] == action:
            return candidate

    return None


# ============================================================
# TEST 1 — RETRY LIMIT
# ============================================================

def test_retry_limit():

    payment = make_payment(
        previous_retries=3
    )

    result = choose_best_action(
        payment,
        {
            "DELAYED_RETRY": 0.90,
            "PAYMENT_LINK": 0.40,
            "HUMAN_REVIEW": 0.50,
        },
    )

    retry = get_candidate(
        result,
        "DELAYED_RETRY",
    )

    assert retry is not None

    assert retry["allowed"] is False

    assert (
        "retry limit"
        in retry["reason"].lower()
    )

    print("PASS: Retry limit")


# ============================================================
# TEST 2 — HIGH VALUE PAYMENT
# ============================================================

def test_high_value_payment():

    payment = make_payment(
        amount=75000
    )

    result = choose_best_action(
        payment,
        {
            "DELAYED_RETRY": 0.90,
            "PAYMENT_LINK": 0.85,
            "HUMAN_REVIEW": 0.60,
        },
    )

    retry = get_candidate(
        result,
        "DELAYED_RETRY",
    )

    payment_link = get_candidate(
        result,
        "PAYMENT_LINK",
    )

    assert retry["allowed"] is False

    assert payment_link["allowed"] is False

    assert result["selected_action"] == "HUMAN_REVIEW"

    print("PASS: High-value protection")


# ============================================================
# TEST 3 — EXPIRED CARD
# ============================================================

def test_expired_card():

    payment = make_payment(
        failure_code="CARD_EXPIRED"
    )

    result = choose_best_action(
        payment,
        {
            "DELAYED_RETRY": 0.90,
            "PAYMENT_LINK": 0.70,
            "HUMAN_REVIEW": 0.40,
        },
    )

    retry = get_candidate(
        result,
        "DELAYED_RETRY",
    )

    assert retry["allowed"] is False

    assert (
        "unlikely"
        in retry["reason"].lower()
    )

    assert result["selected_action"] == "PAYMENT_LINK"

    print("PASS: Expired-card protection")


# ============================================================
# TEST 4 — LOW CONFIDENCE
# ============================================================

def test_low_confidence():

    payment = make_payment()

    result = choose_best_action(
        payment,
        {
            "DELAYED_RETRY": 0.20,
            "PAYMENT_LINK": 0.25,
            "HUMAN_REVIEW": 0.10,
        },
    )

    retry = get_candidate(
        result,
        "DELAYED_RETRY",
    )

    payment_link = get_candidate(
        result,
        "PAYMENT_LINK",
    )

    assert retry["allowed"] is False

    assert payment_link["allowed"] is False

    assert result["selected_action"] == "HUMAN_REVIEW"

    print("PASS: Low-confidence protection")


# ============================================================
# TEST 5 — UNKNOWN ACTION
# ============================================================

def test_unknown_action():

    payment = make_payment()

    result = choose_best_action(
        payment,
        {
            "DELETE_PAYMENT": 0.99,
            "DELAYED_RETRY": 0.20,
            "PAYMENT_LINK": 0.20,
            "HUMAN_REVIEW": 0.20,
        },
    )

    unknown = get_candidate(
        result,
        "DELETE_PAYMENT",
    )

    assert unknown is not None

    assert unknown["allowed"] is False

    assert (
        "unknown action"
        in unknown["reason"].lower()
    )

    print("PASS: Unknown-action protection")


# ============================================================
# TEST 6 — HUMAN REVIEW ALWAYS AVAILABLE
# ============================================================

def test_human_review_available():

    payment = make_payment()

    result = choose_best_action(
        payment,
        {
            "DELAYED_RETRY": 0.10,
            "PAYMENT_LINK": 0.15,
            "HUMAN_REVIEW": 0.05,
        },
    )

    human_review = get_candidate(
        result,
        "HUMAN_REVIEW",
    )

    assert human_review is not None

    assert human_review["allowed"] is True

    assert result["selected_action"] == "HUMAN_REVIEW"

    print("PASS: Human-review fallback")


# ============================================================
# RUN ALL TESTS
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("RecoveryOS Safety Test Suite")
    print("=" * 60)
    print()

    test_retry_limit()

    test_high_value_payment()

    test_expired_card()

    test_low_confidence()

    test_unknown_action()

    test_human_review_available()

    print()
    print("=" * 60)
    print("ALL SAFETY TESTS PASSED")
    print("=" * 60)