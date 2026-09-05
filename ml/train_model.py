import json
from pathlib import Path

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


# ============================================================
# Configuration
# ============================================================

DATA_PATH = Path("data/payments_training.csv")
MODEL_DIR = Path("ml/models")

MODEL_PATH = MODEL_DIR / "recovery_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"


# ============================================================
# Load dataset
# ============================================================

print("=" * 70)
print("RecoveryOS - Recovery Prediction Model Training")
print("=" * 70)

print("\nLoading dataset...")

df = pd.read_csv(DATA_PATH)

print(f"Dataset size: {len(df)} records")


# ============================================================
# Select features
# ============================================================

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

TARGET = "recovered"


X = df[FEATURES]
y = df[TARGET]


# ============================================================
# Feature types
# ============================================================

NUMERIC_FEATURES = [
    "amount",
    "successful_payments",
    "previous_retries",
    "customer_tenure_days",
    "transaction_hour",
    "days_since_last_success",
    "customer_avg_amount",
]

CATEGORICAL_FEATURES = [
    "payment_method",
    "failure_code",
    "merchant_category",
]


# ============================================================
# Preprocessing
# ============================================================

preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            StandardScaler(),
            NUMERIC_FEATURES,
        ),
        (
            "categorical",
            OneHotEncoder(
                handle_unknown="ignore"
            ),
            CATEGORICAL_FEATURES,
        ),
    ]
)


# ============================================================
# Model
# ============================================================

model = LogisticRegression(
    max_iter=1000,
    class_weight="balanced",
)


pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model),
    ]
)


# ============================================================
# Train / test split
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)


print("\nTraining / testing split:")
print(f"Training records: {len(X_train)}")
print(f"Testing records:  {len(X_test)}")


# ============================================================
# Train
# ============================================================

print("\nTraining Logistic Regression model...")

pipeline.fit(X_train, y_train)

print("Training complete.")


# ============================================================
# Predictions
# ============================================================

y_pred = pipeline.predict(X_test)

y_probability = pipeline.predict_proba(X_test)[:, 1]


# ============================================================
# Evaluation
# ============================================================

accuracy = accuracy_score(y_test, y_pred)

precision = precision_score(
    y_test,
    y_pred,
    zero_division=0,
)

recall = recall_score(
    y_test,
    y_pred,
    zero_division=0,
)

f1 = f1_score(
    y_test,
    y_pred,
    zero_division=0,
)

roc_auc = roc_auc_score(
    y_test,
    y_probability,
)


print("\n" + "=" * 70)
print("MODEL EVALUATION")
print("=" * 70)

print(f"\nAccuracy : {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall   : {recall:.4f}")
print(f"F1 Score : {f1:.4f}")
print(f"ROC-AUC  : {roc_auc:.4f}")


# ============================================================
# Classification report
# ============================================================

print("\nClassification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        zero_division=0,
    )
)


# ============================================================
# Confusion matrix
# ============================================================

print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred))


# ============================================================
# Save model
# ============================================================

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

joblib.dump(
    pipeline,
    MODEL_PATH,
)


# ============================================================
# Save metrics
# ============================================================

metrics = {
    "model": "LogisticRegression",
    "records": len(df),
    "training_records": len(X_train),
    "testing_records": len(X_test),
    "accuracy": round(accuracy, 4),
    "precision": round(precision, 4),
    "recall": round(recall, 4),
    "f1": round(f1, 4),
    "roc_auc": round(roc_auc, 4),
}


with open(
    METRICS_PATH,
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        metrics,
        file,
        indent=4,
    )


print("\n" + "=" * 70)
print("MODEL SAVED")
print("=" * 70)

print(f"\nModel : {MODEL_PATH}")
print(f"Metrics: {METRICS_PATH}")

print("\nRecoveryOS ML training completed successfully.")