import pandas as pd


DATA_PATH = "data/payments_training.csv"


print("=" * 60)
print("RecoveryOS Dataset Inspection")
print("=" * 60)


# Load dataset
df = pd.read_csv(DATA_PATH)


# 1. Dataset shape
print("\n1. DATASET SHAPE")
print("-" * 30)
print(f"Rows: {df.shape[0]}")
print(f"Columns: {df.shape[1]}")


# 2. Column names
print("\n2. COLUMNS")
print("-" * 30)

for column in df.columns:
    print(column)


# 3. Data types
print("\n3. DATA TYPES")
print("-" * 30)
print(df.dtypes)


# 4. Missing values
print("\n4. MISSING VALUES")
print("-" * 30)

missing = df.isnull().sum()

print(missing)

if missing.sum() == 0:
    print("\nNo missing values found.")


# 5. Target distribution
print("\n5. RECOVERY DISTRIBUTION")
print("-" * 30)

print(df["recovered"].value_counts())

print("\nPercentage:")
print(
    (df["recovered"].value_counts(normalize=True) * 100)
    .round(2)
)


# 6. Payment methods
print("\n6. PAYMENT METHODS")
print("-" * 30)
print(df["payment_method"].value_counts())


# 7. Failure codes
print("\n7. FAILURE CODES")
print("-" * 30)
print(df["failure_code"].value_counts())


# 8. Merchant categories
print("\n8. MERCHANT CATEGORIES")
print("-" * 30)
print(df["merchant_category"].value_counts())


# 9. Numeric statistics
print("\n9. NUMERIC STATISTICS")
print("-" * 30)

print(
    df.describe().round(2)
)


# 10. Recovery rate by failure type
print("\n10. RECOVERY RATE BY FAILURE CODE")
print("-" * 30)

recovery_by_failure = (
    df.groupby("failure_code")["recovered"]
    .mean()
    .sort_values(ascending=False)
)

print(
    (recovery_by_failure * 100).round(2)
)


# 11. Recovery rate by payment method
print("\n11. RECOVERY RATE BY PAYMENT METHOD")
print("-" * 30)

recovery_by_method = (
    df.groupby("payment_method")["recovered"]
    .mean()
    .sort_values(ascending=False)
)

print(
    (recovery_by_method * 100).round(2)
)


print("\n" + "=" * 60)
print("Inspection complete.")
print("=" * 60)