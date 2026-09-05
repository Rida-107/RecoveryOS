import random
import uuid
from datetime import datetime, timedelta

import pandas as pd


# -----------------------------
# Configuration
# -----------------------------

NUM_RECORDS = 10000

random.seed(42)


PAYMENT_METHODS = [
    "UPI",
    "CARD",
    "NETBANKING",
    "WALLET",
]

FAILURE_CODES = [
    "BANK_TIMEOUT",
    "NETWORK_ERROR",
    "AUTH_FAILED",
    "INSUFFICIENT_FUNDS",
    "EXPIRED_CARD",
    "LIMIT_EXCEEDED",
    "BANK_DECLINED",
]

MERCHANT_CATEGORIES = [
    "E_COMMERCE",
    "EDUCATION",
    "TRAVEL",
    "FOOD",
    "SAAS",
    "HEALTHCARE",
]


# -----------------------------
# Generate one payment
# -----------------------------

def generate_payment():

    amount = round(random.uniform(200, 50000), 2)

    payment_method = random.choice(PAYMENT_METHODS)

    failure_code = random.choice(FAILURE_CODES)

    successful_payments = random.randint(0, 30)

    previous_retries = random.randint(0, 3)

    customer_tenure_days = random.randint(10, 1500)

    transaction_hour = random.randint(0, 23)

    merchant_category = random.choice(MERCHANT_CATEGORIES)

    days_since_last_success = random.randint(1, 180)

    customer_avg_amount = round(
        random.uniform(300, 15000), 2
    )

    # --------------------------------
    # Create a realistic recovery signal
    # --------------------------------

    recovery_score = 0.20

    # Customer history
    if successful_payments >= 10:
        recovery_score += 0.20
    elif successful_payments >= 5:
        recovery_score += 0.10

    # Retry history
    if previous_retries == 0:
        recovery_score += 0.15
    elif previous_retries >= 3:
        recovery_score -= 0.20

    # Failure type
    if failure_code in [
        "BANK_TIMEOUT",
        "NETWORK_ERROR",
    ]:
        recovery_score += 0.20

    if failure_code in [
        "EXPIRED_CARD",
        "INSUFFICIENT_FUNDS",
        "LIMIT_EXCEEDED",
    ]:
        recovery_score -= 0.15

    # Payment method
    if payment_method == "UPI":
        recovery_score += 0.05

    # Customer tenure
    if customer_tenure_days > 365:
        recovery_score += 0.05

    # Amount risk
    if amount > customer_avg_amount * 3:
        recovery_score -= 0.10

    # Add small randomness
    recovery_score += random.uniform(-0.10, 0.10)

    recovery_score = max(
        0.02,
        min(0.98, recovery_score)
    )

    # --------------------------------
    # Generate actual outcome
    # --------------------------------

    recovered = int(
        random.random() < recovery_score
    )

    # --------------------------------
    # Timestamp
    # --------------------------------

    created_at = datetime.now() - timedelta(
        days=random.randint(0, 365),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )

    return {
        "payment_id": f"pay_{uuid.uuid4().hex[:10]}",
        "amount": amount,
        "payment_method": payment_method,
        "failure_code": failure_code,
        "successful_payments": successful_payments,
        "previous_retries": previous_retries,
        "customer_tenure_days": customer_tenure_days,
        "transaction_hour": transaction_hour,
        "merchant_category": merchant_category,
        "days_since_last_success": days_since_last_success,
        "customer_avg_amount": customer_avg_amount,
        "recovered": recovered,
        "created_at": created_at.isoformat(),
    }


# -----------------------------
# Generate dataset
# -----------------------------

print("Generating RecoveryOS dataset...")

records = [
    generate_payment()
    for _ in range(NUM_RECORDS)
]

df = pd.DataFrame(records)

output_path = "data/payments_training.csv"

df.to_csv(
    output_path,
    index=False
)

print(f"Dataset created successfully: {output_path}")
print(f"Records: {len(df)}")

print("\nRecovery distribution:")
print(df["recovered"].value_counts())

print("\nSample records:")
print(df.head())