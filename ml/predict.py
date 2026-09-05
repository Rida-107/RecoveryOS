from pathlib import Path

import joblib
import pandas as pd


# Find the RecoveryOS project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = PROJECT_ROOT / "ml" / "models" / "recovery_model.joblib"


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


# Load the trained model.
model = joblib.load(MODEL_PATH)


def predict_recovery(payment: dict) -> float:
    """
    Predict the probability that a failed payment
    can be successfully recovered.
    """

    row = {
        feature: payment[feature]
        for feature in FEATURES
    }

    dataframe = pd.DataFrame([row])

    probability = model.predict_proba(dataframe)[0][1]

    return round(float(probability), 4)